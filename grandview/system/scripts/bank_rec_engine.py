"""Bank reconciliation engine.

Matches book (ledger) transactions to bank statement transactions, reports the
reconciling items, and — when ending balances are supplied — produces a balance
proof showing that the adjusted bank balance equals the adjusted book balance.

Amount sign convention: **positive = increases cash** (deposit / bank credit),
**negative = decreases cash** (cheque / withdrawal / bank charge).

Matching strategy (global, two-phase so early items can't greedily steal a
candidate a later item needs):
  Phase 1 — exact amount AND date within a tolerance window.
  Phase 2 — exact amount only (timing difference / unknown date).
Anything still unmatched on either side is a reconciling item.

Fuzzy description matching and many-to-one matching are deliberate future work.

Run a demo:
    python system/scripts/bank_rec_engine.py --demo
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from common import Transaction, Workpaper, money, round_money


@dataclass
class ReconResult:
    matched: list[tuple[Transaction, Transaction]] = field(default_factory=list)
    unmatched_book: list[Transaction] = field(default_factory=list)
    unmatched_bank: list[Transaction] = field(default_factory=list)

    @property
    def outstanding_book(self) -> Decimal:
        """Net of items recorded in books but not yet on the bank statement."""
        return round_money(sum((money(t.amount) for t in self.unmatched_book), Decimal("0")))

    @property
    def outstanding_bank(self) -> Decimal:
        """Net of items on the bank statement but not yet recorded in books."""
        return round_money(sum((money(t.amount) for t in self.unmatched_bank), Decimal("0")))


@dataclass
class BalanceProof:
    book_balance: Decimal
    bank_balance: Decimal
    outstanding_book: Decimal
    outstanding_bank: Decimal

    @property
    def adjusted_bank(self) -> Decimal:
        # Bank balance plus items already in books that haven't hit the bank yet.
        return round_money(self.bank_balance + self.outstanding_book)

    @property
    def adjusted_book(self) -> Decimal:
        # Book balance plus items on the bank not yet recorded in the books.
        return round_money(self.book_balance + self.outstanding_bank)

    @property
    def difference(self) -> Decimal:
        return round_money(self.adjusted_bank - self.adjusted_book)

    @property
    def is_reconciled(self) -> bool:
        return self.difference == Decimal("0.00")


def reconcile(
    book: list[Transaction],
    bank: list[Transaction],
    *,
    date_tolerance_days: int = 3,
) -> ReconResult:
    """Match book vs bank transactions using global two-phase matching."""
    result = ReconResult()
    remaining_bank = list(bank)
    remaining_book = list(book)

    def date_close(a: Transaction, b: Transaction) -> bool:
        if a.date is None or b.date is None:
            return False
        return abs((a.date - b.date).days) <= date_tolerance_days

    def run_phase(predicate) -> None:
        still_book: list[Transaction] = []
        for bt in remaining_book:
            match = next((c for c in remaining_bank if predicate(bt, c)), None)
            if match is not None:
                result.matched.append((bt, match))
                remaining_bank.remove(match)
            else:
                still_book.append(bt)
        remaining_book[:] = still_book

    # Phase 1: exact amount + close date.
    run_phase(lambda bt, c: money(c.amount) == money(bt.amount) and date_close(bt, c))
    # Phase 2: exact amount only.
    run_phase(lambda bt, c: money(c.amount) == money(bt.amount))

    result.unmatched_book = remaining_book
    result.unmatched_bank = remaining_bank
    return result


def build_proof(
    result: ReconResult, book_balance, bank_balance
) -> BalanceProof:
    return BalanceProof(
        book_balance=money(book_balance),
        bank_balance=money(bank_balance),
        outstanding_book=result.outstanding_book,
        outstanding_bank=result.outstanding_bank,
    )


def build_workpaper(
    client: str,
    period: str,
    result: ReconResult,
    proof: BalanceProof | None = None,
) -> Workpaper:
    wp = Workpaper("Bank Reconciliation", client, period)
    wp.section("Summary")
    wp.kv("Matched items", len(result.matched))
    wp.kv("Net outstanding (book, not on bank)", f"{result.outstanding_book:,.2f}")
    wp.kv("Net outstanding (bank, not in book)", f"{result.outstanding_bank:,.2f}")

    if proof is not None:
        wp.section("Balance proof")
        wp.table(
            ["Line", "Amount (CAD)"],
            [
                ["Balance per bank statement", f"{proof.bank_balance:,.2f}"],
                ["Add/less: items in books not on bank", f"{proof.outstanding_book:,.2f}"],
                ["= Adjusted bank balance", f"{proof.adjusted_bank:,.2f}"],
                ["Balance per books", f"{proof.book_balance:,.2f}"],
                ["Add/less: items on bank not in books", f"{proof.outstanding_bank:,.2f}"],
                ["= Adjusted book balance", f"{proof.adjusted_book:,.2f}"],
                ["Difference", f"{proof.difference:,.2f}"],
            ],
        )
        verdict = "✅ RECONCILED" if proof.is_reconciled else "❌ NOT reconciled — investigate"
        wp.line()
        wp.kv("Result", f"**{verdict}**")

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
    wp.qc("Record bank-only items (charges, interest, NSF) in the books")
    wp.qc("Confirm adjusted bank balance equals adjusted book balance (nil difference)")
    return wp


# --- Demo / CLI -------------------------------------------------------------
def _demo() -> None:
    print("Running bank reconciliation demo...\n")
    book = [
        Transaction(date(2025, 1, 5), "Deposit - customer A", money("1500.00")),
        Transaction(date(2025, 1, 12), "Cheque #101 - supplier", money("-600.00")),
        Transaction(date(2025, 1, 28), "Cheque #102 - rent", money("-2000.00")),  # outstanding
        Transaction(date(2025, 1, 30), "Deposit - customer B", money("900.00")),  # in transit
    ]
    bank = [
        Transaction(date(2025, 1, 6), "Deposit", money("1500.00")),
        Transaction(date(2025, 1, 14), "Cheque 101", money("-600.00")),
        Transaction(date(2025, 1, 31), "Bank service charge", money("-25.00")),  # bank-only
    ]
    # Ending balances (illustrative, chosen so the rec proves out).
    book_balance = money("-200.00")   # 1500 - 600 - 2000 + 900 (- 0 charges not yet booked)
    bank_balance = money("875.00")    # 1500 - 600 - 25
    result = reconcile(book, bank)
    proof = build_proof(result, book_balance, bank_balance)
    wp = build_workpaper("DEMO_CLIENT", "2025-01", result, proof)
    print(wp.render())
    print(f"\n[demo] Reconciled: {proof.is_reconciled} (difference {proof.difference})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bank reconciliation engine")
    parser.add_argument("--demo", action="store_true", help="Run a self-contained demo")
    args = parser.parse_args()
    if args.demo:
        _demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
