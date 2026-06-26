"""Unit tests for the GST/HST engine.

Run from the grandview/ directory:  python -m pytest tests/
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Make system/scripts importable without installing a package.
SCRIPTS = Path(__file__).resolve().parents[1] / "system" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import Transaction, UnverifiedRatesError, money  # noqa: E402
from gst_calculator import compute_gst  # noqa: E402

# A controlled rate table so tests don't depend on the (placeholder) config.
RATES = {
    "gst_hst": {
        "verified": True,
        "rates_by_province": {"ON": 0.13, "AB": 0.05},
    }
}


def _txn(amount, tax_code=None):
    return Transaction(None, "t", money(amount), tax_code=tax_code)


def test_basic_net_tax_ontario():
    sales = [_txn("10000.00"), _txn("5000.00")]
    purchases = [_txn("2000.00")]
    r = compute_gst(sales, purchases, "ON", rates=RATES)
    assert r.tax_collected == Decimal("1950.00")     # 15000 * 0.13
    assert r.input_tax_credits == Decimal("260.00")  # 2000 * 0.13
    assert r.net_tax == Decimal("1690.00")           # 1950 - 260


def test_zero_rated_excluded_from_base():
    sales = [_txn("10000.00"), _txn("3000.00", tax_code="zero")]
    r = compute_gst(sales, [], "ON", rates=RATES)
    assert r.taxable_sales == Decimal("10000.00")    # zero-rated excluded
    assert r.tax_collected == Decimal("1300.00")


def test_refund_when_itcs_exceed_collected():
    sales = [_txn("1000.00")]
    purchases = [_txn("5000.00")]
    r = compute_gst(sales, purchases, "ON", rates=RATES)
    assert r.net_tax < 0  # net refund position


def test_alberta_gst_only_rate():
    r = compute_gst([_txn("1000.00")], [], "AB", rates=RATES)
    assert r.tax_collected == Decimal("50.00")       # 1000 * 0.05


def test_unverified_rates_blocked():
    unverified = {"gst_hst": {"verified": False, "rates_by_province": {"ON": 0.13}}}
    with pytest.raises(UnverifiedRatesError):
        compute_gst([_txn("100")], [], "ON", rates=unverified)


def test_unknown_province_raises():
    with pytest.raises(KeyError):
        compute_gst([_txn("100")], [], "QC", rates=RATES)
