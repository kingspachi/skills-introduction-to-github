"""Unit tests for the QuickBooks data source adapter.

Run from the grandview/ directory:  python -m pytest tests/

These tests use fixture dicts and a temp cache dir — they never touch the real
clients/ tree and never call MCP.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "system" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from gst_calculator import compute_gst  # noqa: E402
from qbo_adapter import (  # noqa: E402
    QuickBooksDataSource,
    build_cache_payload,
    normalize_expense,
    normalize_invoice,
    split_sales_purchases,
    transactions_from_cache,
)
from qbo_sync import write_cache  # noqa: E402

VERIFIED_RATES = {"gst_hst": {"verified": True, "rates_by_province": {"ON": 0.13}}}


def test_normalize_invoice_to_sale_row():
    raw = {"TxnDate": "2025-01-15", "DocNumber": "1001", "TotalAmt": "10000.00"}
    row = normalize_invoice(raw)
    assert row["kind"] == "sale"
    assert row["amount"] == "10000.00"
    assert row["description"] == "1001"


def test_normalize_expense_to_purchase_row():
    raw = {"TxnDate": "2025-01-31", "DocNumber": "B-9", "TotalAmt": "2000.00",
           "AccountRef": {"name": "Rent expense"}}
    row = normalize_expense(raw)
    assert row["kind"] == "purchase"
    assert row["account"] == "Rent expense"


def test_transactions_from_cache_parses_rows():
    payload = build_cache_payload(
        "ACME", "2025-Q1",
        [normalize_invoice({"TxnDate": "2025-01-15", "TotalAmt": "100.00"})],
    )
    txns = transactions_from_cache(payload)
    assert len(txns) == 1
    assert txns[0].amount == Decimal("100.00")
    assert txns[0].raw["kind"] == "sale"


def test_split_sales_purchases():
    rows = [
        normalize_invoice({"TotalAmt": "100", "TxnDate": "2025-01-01"}),
        normalize_expense({"TotalAmt": "40", "TxnDate": "2025-01-02"}),
    ]
    txns = transactions_from_cache(build_cache_payload("A", "P", rows))
    sales, purchases = split_sales_purchases(txns)
    assert len(sales) == 1 and len(purchases) == 1


def test_datasource_reads_written_cache(tmp_path):
    rows = [
        normalize_invoice({"TotalAmt": "10000.00", "TxnDate": "2025-01-15"}),
        normalize_expense({"TotalAmt": "2000.00", "TxnDate": "2025-01-20"}),
    ]
    write_cache("ACME", "2025-Q1", rows, cache_root=tmp_path)
    src = QuickBooksDataSource(cache_root=tmp_path)
    txns = src.transactions("ACME", "2025-Q1")
    assert len(txns) == 2


def test_end_to_end_qbo_into_gst_engine(tmp_path):
    rows = [
        normalize_invoice({"TotalAmt": "10000.00", "TxnDate": "2025-01-15"}),
        normalize_expense({"TotalAmt": "2000.00", "TxnDate": "2025-01-20"}),
    ]
    write_cache("ACME", "2025-Q1", rows, cache_root=tmp_path)
    txns = QuickBooksDataSource(cache_root=tmp_path).transactions("ACME", "2025-Q1")
    sales, purchases = split_sales_purchases(txns)
    result = compute_gst(sales, purchases, "ON", rates=VERIFIED_RATES)
    assert result.tax_collected == Decimal("1300.00")   # 10000 * 0.13
    assert result.input_tax_credits == Decimal("260.00")  # 2000 * 0.13
    assert result.net_tax == Decimal("1040.00")


def test_missing_cache_raises(tmp_path):
    src = QuickBooksDataSource(cache_root=tmp_path)
    try:
        src.transactions("NOPE", "2025-Q1")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
