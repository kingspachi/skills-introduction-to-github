"""Unit tests for the bank reconciliation engine.

Run from the grandview/ directory:  python -m pytest tests/
"""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "system" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import Transaction, money  # noqa: E402
from bank_rec_engine import build_proof, reconcile  # noqa: E402


def _txn(d, desc, amount):
    return Transaction(d, desc, money(amount))


def test_exact_match_by_amount_and_date():
    book = [_txn(date(2025, 1, 5), "dep", "100.00")]
    bank = [_txn(date(2025, 1, 6), "dep", "100.00")]
    r = reconcile(book, bank)
    assert len(r.matched) == 1
    assert not r.unmatched_book and not r.unmatched_bank


def test_unmatched_items_become_reconciling():
    book = [_txn(date(2025, 1, 5), "outstanding cheque", "-200.00")]
    bank = [_txn(date(2025, 1, 9), "bank charge", "-15.00")]
    r = reconcile(book, bank)
    assert r.outstanding_book == Decimal("-200.00")
    assert r.outstanding_bank == Decimal("-15.00")


def test_date_only_outside_tolerance_still_matches_by_amount():
    # Same amount, far-apart dates: phase 1 misses, phase 2 matches by amount.
    book = [_txn(date(2025, 1, 1), "dep", "500.00")]
    bank = [_txn(date(2025, 1, 20), "dep", "500.00")]
    r = reconcile(book, bank, date_tolerance_days=3)
    assert len(r.matched) == 1


def test_global_two_phase_prefers_date_match():
    # Two book deposits of 100; one bank item dated close to the first, one far.
    # Phase 1 should pair the close dates; phase 2 pairs the remainder.
    book = [
        _txn(date(2025, 1, 1), "dep A", "100.00"),
        _txn(date(2025, 1, 20), "dep B", "100.00"),
    ]
    bank = [
        _txn(date(2025, 1, 21), "dep", "100.00"),
        _txn(date(2025, 1, 2), "dep", "100.00"),
    ]
    r = reconcile(book, bank)
    assert len(r.matched) == 2
    # Verify the close-date pairing happened (A<->Jan2, B<->Jan21).
    pairs = {(bt.description, bk.date) for bt, bk in r.matched}
    assert ("dep A", date(2025, 1, 2)) in pairs
    assert ("dep B", date(2025, 1, 21)) in pairs


def test_balance_proof_reconciles():
    book = [
        _txn(date(2025, 1, 5), "dep", "1500.00"),
        _txn(date(2025, 1, 12), "chq101", "-600.00"),
        _txn(date(2025, 1, 28), "chq102 outstanding", "-2000.00"),
        _txn(date(2025, 1, 30), "dep in transit", "900.00"),
    ]
    bank = [
        _txn(date(2025, 1, 6), "dep", "1500.00"),
        _txn(date(2025, 1, 14), "chq101", "-600.00"),
        _txn(date(2025, 1, 31), "charge", "-25.00"),
    ]
    r = reconcile(book, bank)
    proof = build_proof(r, book_balance="-200.00", bank_balance="875.00")
    assert proof.adjusted_bank == Decimal("-225.00")
    assert proof.adjusted_book == Decimal("-225.00")
    assert proof.difference == Decimal("0.00")
    assert proof.is_reconciled


def test_balance_proof_flags_out_of_balance():
    book = [_txn(date(2025, 1, 5), "dep", "100.00")]
    bank = [_txn(date(2025, 1, 6), "dep", "100.00")]
    r = reconcile(book, bank)
    proof = build_proof(r, book_balance="100.00", bank_balance="90.00")
    assert not proof.is_reconciled
    assert proof.difference == Decimal("-10.00")
