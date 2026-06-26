"""Bank reconciliation engine.

Matches book (ledger) transactions to bank statement transactions and reports
the reconciling items, so a reviewer can confirm the adjusted balances agree.

Matching strategy (in order):
1. exact amount + date within a tolerance window
2. exact amount only (date unknown / timing difference)
Unmatched items on either side become reconciling items.

This is fully usable for straightforward cases; fuzzy description matching and
many-to-one matching are deliberate future enhancements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from common import Transaction, Workpaper, money, round_money


@dataclass
class ReconResult:
    matched: list[tuple[Transaction, Transaction]] = field(default_factory=list)
    unmatched_book: list[Transaction] = field(default_factory=list)
    unmatched_bank: list[Transaction] = field(default_factory=list)

    @property
    def outstanding_book(self) -> Decimal:
        return round_money(sum((money(t.amount) for t in self.unmatched_book), Decimal("0")))

    @property
    def outstanding_bank(self) -> Decimal:
        return round_money(sum((money(t.amount) for t in self.unmatched_bank), Decimal("0")))


def reconcile(
    book: list[Transaction],
    bank: list[Transaction],
    *,
    date_tolerance_days: int = 3,
) -> ReconResult:
    result = ReconResult()
    remaining_bank = list(bank)

    def date_close(a: Transaction, b: Transaction) -> bool:
        if a.date is None or b.date is None:
            return False
        return abs((a.date - b.date).days) <= date_tolerance_days

    for bt in book:
        match = None
        # Pass 1: amount + close date
        for cand in remaining_bank:
            if money(cand.amount) == money(bt.amount) and date_close(bt, cand):
                match = cand
                break
        # Pass 2: amount only
        if match is None:
            for cand in remaining_bank:
                if money(cand.amount) == money(bt.amount):
                    match = cand
                    break
        if match is not None:
            result.matched.append((bt, match))
            remaining_bank.remove(match)
        else:
            result.unmatched_book.append(bt)

    result.unmatched_bank = remaining_bank
    return result


def build_workpaper(client: str, period: str, result: ReconResult) -> Workpaper:
    wp = Workpaper("Bank Reconciliation", client, period)
    wp.section("Summary")
    wp.kv("Matched items", len(result.matched))
    wp.kv("Outstanding (book, not on bank)", f"{result.outstanding_book:,.2f}")
    wp.kv("Outstanding (bank, not in book)", f"{result.outstanding_bank:,.2f}")
    if result.unmatched_book:
        wp.section("Reconciling items — in books, not on bank")
        wp.table(
            ["Date", "Description", "Amount"],
            [[t.date, t.description, f"{money(t.amount):,.2f}"] for t in result.unmatched_book],
        )
    if result.unmatched_bank:
        wp.section("Reconciling items — on bank, not in books")
        wp.table(
            ["Date", "Description", "Amount"],
            [[t.date, t.description, f"{money(t.amount):,.2f}"] for t in result.unmatched_bank],
        )
    wp.qc("Investigate every reconciling item; confirm none are errors/omissions")
    wp.qc("Confirm adjusted book balance equals adjusted bank balance")
    return wp
