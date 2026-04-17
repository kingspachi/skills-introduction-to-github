from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional


class LineItem(BaseModel):
    description: str
    amount: Optional[Decimal] = None


class ReceiptData(BaseModel):
    vendor_name: Optional[str] = None
    transaction_date: Optional[date] = None
    line_items: list[LineItem] = []
    subtotal: Optional[Decimal] = None
    gst_amount: Optional[Decimal] = None
    total: Optional[Decimal] = None
    raw_text: Optional[str] = None


class ExportRow(BaseModel):
    date: Optional[str] = None
    category: str = "Unclassified"
    description: str = ""
    vendor: Optional[str] = None
    gst: Optional[Decimal] = None
    total: Optional[Decimal] = None
    base_amount: Optional[Decimal] = None


def derive_gst(data: ReceiptData) -> ReceiptData:
    """Fill in missing GST or subtotal by derivation when possible."""
    if data.gst_amount and data.subtotal and data.total:
        return data
    if data.total and data.subtotal and not data.gst_amount:
        data.gst_amount = data.total - data.subtotal
    elif data.total and data.gst_amount and not data.subtotal:
        data.subtotal = data.total - data.gst_amount
    elif data.subtotal and data.gst_amount and not data.total:
        data.total = data.subtotal + data.gst_amount
    return data
