"""GST/HST calculation engine.

Given a set of transactions (sales and purchases) for a filing period, computes:

* GST/HST **collected** on taxable sales
* **Input tax credits** (ITCs) on purchases
* **Net tax** to remit to (or refund from) CRA

and renders a reviewable Markdown workpaper.

Rates come from ``config/tax_rates_2025.yaml`` (place-of-supply based). The
engine refuses to run on un-verified rates unless ``allow_unverified=True`` is
passed (used by ``--demo`` and tests). This is a draft-preparation aid only —
a CPA must verify rates and review every figure before filing.

Run a demo:
    python system/scripts/gst_calculator.py --demo
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from common import (
    Transaction,
    Workpaper,
    load_firm_config,
    load_rates,
    money,
    require_verified,
    round_money,
)


@dataclass
class GstResult:
    province: str
    rate: Decimal
    taxable_sales: Decimal
    tax_collected: Decimal
    eligible_purchases: Decimal
    input_tax_credits: Decimal
    net_tax: Decimal  # positive = remit to CRA, negative = refund


def _rate_for_province(rates: dict, province: str, allow_unverified: bool) -> Decimal:
    if allow_unverified:
        block = rates.get("gst_hst", {})
    else:
        block = require_verified(rates, "gst_hst")
    table = block.get("rates_by_province", {})
    if province not in table or table[province] is None:
        raise KeyError(
            f"No GST/HST rate configured for province '{province}'. "
            "Add it to config/tax_rates_2025.yaml and verify against CRA."
        )
    return money(table[province])


def compute_gst(
    sales: Iterable[Transaction],
    purchases: Iterable[Transaction],
    province: str,
    *,
    rates: dict | None = None,
    allow_unverified: bool = False,
) -> GstResult:
    """Compute net GST/HST for a period.

    ``sales`` and ``purchases`` amounts are treated as **tax-exclusive** base
    amounts. Transactions with ``tax_code`` in {"exempt", "zero", "0", "out"}
    are excluded from the taxable base (but still informative for the workpaper).
    """
    rates = rates if rates is not None else load_rates()
    rate = _rate_for_province(rates, province, allow_unverified)

    def taxable_base(txns: Iterable[Transaction]) -> Decimal:
        total = Decimal("0")
        for t in txns:
            code = (t.tax_code or "").strip().lower()
            if code in {"exempt", "zero", "zero-rated", "0", "out", "out-of-scope"}:
                continue
            total += money(t.amount)
        return total

    taxable_sales = round_money(taxable_base(sales))
    eligible_purchases = round_money(taxable_base(purchases))

    tax_collected = round_money(taxable_sales * rate)
    input_tax_credits = round_money(eligible_purchases * rate)
    net_tax = round_money(tax_collected - input_tax_credits)

    return GstResult(
        province=province,
        rate=rate,
        taxable_sales=taxable_sales,
        tax_collected=tax_collected,
        eligible_purchases=eligible_purchases,
        input_tax_credits=input_tax_credits,
        net_tax=net_tax,
    )


def build_workpaper(client: str, period: str, result: GstResult) -> Workpaper:
    wp = Workpaper("GST-HST Return", client, period)
    wp.section("Summary")
    wp.kv("Place of supply", result.province)
    wp.kv("GST/HST rate applied", f"{result.rate:.4f}")
    wp.section("Computation")
    wp.table(
        ["Line", "Amount (CAD)"],
        [
            ["101  Taxable sales (excl. tax)", f"{result.taxable_sales:,.2f}"],
            ["105  GST/HST collected", f"{result.tax_collected:,.2f}"],
            ["106  Input tax credits (ITCs)", f"{result.input_tax_credits:,.2f}"],
            ["109  Net tax", f"{result.net_tax:,.2f}"],
        ],
    )
    direction = "REMIT to CRA" if result.net_tax >= 0 else "REFUND from CRA"
    wp.line()
    wp.kv("Result", f"**{direction}: {abs(result.net_tax):,.2f} CAD**")
    wp.qc("Confirm place of supply and rate against CRA for the period")
    wp.qc("Confirm exempt/zero-rated transactions were classified correctly")
    wp.qc("Reconcile taxable sales (line 101) to the general ledger / revenue")
    wp.qc("Confirm all ITCs are supported by valid invoices")
    wp.qc("Check whether the Quick Method applies (different remittance basis)")
    return wp


# --- Demo / CLI -------------------------------------------------------------
def _demo() -> None:
    print("Running GST/HST demo (using UNVERIFIED placeholder rates)...\n")
    sales = [
        Transaction(None, "Consulting invoice #1001", money("10000.00")),
        Transaction(None, "Consulting invoice #1002", money("5000.00")),
        Transaction(None, "Export sale (zero-rated)", money("3000.00"), tax_code="zero"),
    ]
    purchases = [
        Transaction(None, "Office rent", money("2000.00")),
        Transaction(None, "Software subscription", money("800.00")),
    ]
    firm = load_firm_config()
    province = firm.get("firm", {}).get("default_province", "ON")
    result = compute_gst(sales, purchases, province, allow_unverified=True)
    wp = build_workpaper("DEMO_CLIENT", "2025-Q1", result)
    print(wp.render())
    print("\n[demo] Rates were UNVERIFIED placeholders — do not rely on these numbers.")


def main() -> None:
    parser = argparse.ArgumentParser(description="GST/HST calculation engine")
    parser.add_argument("--demo", action="store_true", help="Run a self-contained demo")
    args = parser.parse_args()
    if args.demo:
        _demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
