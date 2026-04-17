import asyncio
from decimal import Decimal, InvalidOperation
from datetime import date
from typing import Optional

from .base import OCRBackend
from .models import ReceiptData, LineItem


def _parse_money(value: Optional[str]) -> Optional[Decimal]:
    if not value:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    from dateutil import parser as dateparser
    try:
        return dateparser.parse(value).date()
    except Exception:
        return None


class GoogleDocAIBackend(OCRBackend):
    def __init__(self, project_id: str, location: str, processor_id: str):
        from google.cloud import documentai_v1 as documentai
        from google.api_core.client_options import ClientOptions

        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        self.client = documentai.DocumentProcessorServiceClient(client_options=opts)
        self.processor_name = self.client.processor_path(project_id, location, processor_id)
        self._documentai = documentai

    async def process(self, file_bytes: bytes, mime_type: str) -> ReceiptData:
        raw_doc = self._documentai.RawDocument(content=file_bytes, mime_type=mime_type)
        request = self._documentai.ProcessRequest(
            name=self.processor_name, raw_document=raw_doc
        )
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self.client.process_document, request
        )
        return self._parse_response(result.document)

    def _parse_response(self, document) -> ReceiptData:
        data = ReceiptData(raw_text=document.text)
        line_items: list[LineItem] = []

        for entity in document.entities:
            t = entity.type_
            text = entity.mention_text.strip() if entity.mention_text else ""

            if t == "supplier_name":
                data.vendor_name = text or None
            elif t == "receipt_date":
                data.transaction_date = _parse_date(text)
            elif t in ("total_amount", "purchase_total"):
                data.total = _parse_money(text)
            elif t in ("net_amount", "subtotal_amount"):
                data.subtotal = _parse_money(text)
            elif t in ("tax_amount", "gst_amount"):
                data.gst_amount = _parse_money(text)
            elif t == "line_item":
                desc = ""
                amount = None
                for prop in entity.properties:
                    if prop.type_ == "line_item/description":
                        desc = prop.mention_text.strip()
                    elif prop.type_ == "line_item/amount":
                        amount = _parse_money(prop.mention_text)
                if desc:
                    line_items.append(LineItem(description=desc, amount=amount))

        data.line_items = line_items
        return data
