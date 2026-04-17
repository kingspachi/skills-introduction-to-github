import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch

from backend.ocr.models import ReceiptData, LineItem, derive_gst
from backend.ocr.google_docai import GoogleDocAIBackend, _parse_money, _parse_date


class TestParseMoney:
    def test_plain(self):         assert _parse_money("7.35") == Decimal("7.35")
    def test_dollar_sign(self):   assert _parse_money("$12.50") == Decimal("12.50")
    def test_comma(self):         assert _parse_money("1,234.56") == Decimal("1234.56")
    def test_none(self):          assert _parse_money(None) is None
    def test_empty(self):         assert _parse_money("") is None
    def test_invalid(self):       assert _parse_money("N/A") is None


class TestParseDate:
    def test_iso(self):           assert _parse_date("2024-03-15") == date(2024, 3, 15)
    def test_us_format(self):     assert _parse_date("03/15/2024") == date(2024, 3, 15)
    def test_none(self):          assert _parse_date(None) is None
    def test_invalid(self):       assert _parse_date("not-a-date") is None


class TestDeriveGst:
    def test_derive_gst_from_total_and_subtotal(self):
        data = ReceiptData(total=Decimal("10.50"), subtotal=Decimal("10.00"))
        result = derive_gst(data)
        assert result.gst_amount == Decimal("0.50")

    def test_derive_subtotal_from_total_and_gst(self):
        data = ReceiptData(total=Decimal("10.50"), gst_amount=Decimal("0.50"))
        result = derive_gst(data)
        assert result.subtotal == Decimal("10.00")

    def test_derive_total_from_subtotal_and_gst(self):
        data = ReceiptData(subtotal=Decimal("10.00"), gst_amount=Decimal("0.50"))
        result = derive_gst(data)
        assert result.total == Decimal("10.50")

    def test_all_present_unchanged(self):
        data = ReceiptData(
            total=Decimal("10.50"),
            subtotal=Decimal("10.00"),
            gst_amount=Decimal("0.50"),
        )
        result = derive_gst(data)
        assert result.total == Decimal("10.50")

    def test_nothing_to_derive(self):
        data = ReceiptData(vendor_name="Test")
        result = derive_gst(data)
        assert result.gst_amount is None
        assert result.total is None


class TestGoogleDocAIParseResponse:
    def _make_entity(self, type_: str, text: str, properties=None):
        entity = MagicMock()
        entity.type_ = type_
        entity.mention_text = text
        entity.properties = properties or []
        return entity

    def _make_backend(self):
        with patch("backend.ocr.google_docai.GoogleDocAIBackend.__init__", return_value=None):
            backend = GoogleDocAIBackend.__new__(GoogleDocAIBackend)
        return backend

    def test_parse_supplier_and_date(self):
        backend = self._make_backend()
        doc = MagicMock()
        doc.text = "Starbucks\n2024-03-15\n$7.35"
        doc.entities = [
            self._make_entity("supplier_name", "Starbucks"),
            self._make_entity("receipt_date", "2024-03-15"),
            self._make_entity("total_amount", "$7.35"),
            self._make_entity("net_amount", "$7.00"),
            self._make_entity("tax_amount", "$0.35"),
        ]
        result = backend._parse_response(doc)
        assert result.vendor_name == "Starbucks"
        assert result.transaction_date == date(2024, 3, 15)
        assert result.total == Decimal("7.35")
        assert result.subtotal == Decimal("7.00")
        assert result.gst_amount == Decimal("0.35")

    def test_parse_line_items(self):
        backend = self._make_backend()
        item_entity = self._make_entity("line_item", "Latte $5.00")
        desc_prop = MagicMock()
        desc_prop.type_ = "line_item/description"
        desc_prop.mention_text = "Latte"
        amt_prop = MagicMock()
        amt_prop.type_ = "line_item/amount"
        amt_prop.mention_text = "$5.00"
        item_entity.properties = [desc_prop, amt_prop]

        doc = MagicMock()
        doc.text = ""
        doc.entities = [item_entity]
        result = backend._parse_response(doc)
        assert len(result.line_items) == 1
        assert result.line_items[0].description == "Latte"
        assert result.line_items[0].amount == Decimal("5.00")

    def test_empty_document(self):
        backend = self._make_backend()
        doc = MagicMock()
        doc.text = ""
        doc.entities = []
        result = backend._parse_response(doc)
        assert isinstance(result, ReceiptData)
        assert result.vendor_name is None
        assert result.line_items == []
