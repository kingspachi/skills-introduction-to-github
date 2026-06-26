"""T1 (personal) and T2 (corporate) income-tax estimation engine.

Bracket-based, fully config-driven: it never hard-codes a rate. Brackets come
from ``config/tax_rates_2025.yaml`` as ``[upper_bound_or_null, rate]`` pairs.

⚠️ This produces a **planning estimate / workpaper draft only**. It does NOT
model the full Income Tax Act — credits, deductions, AMT, integration, refundable
taxes, etc. are out of scope until added deliberately and verified. Do not file
from these numbers.

The config currently ships with placeholder (null) brackets, so the engine will
raise until a CPA populates and verifies them.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from common import (
    Workpaper,
    load_rates,
    money,
    require_verified,
    round_money,
)


@dataclass
class TaxBand:
    income_in_band: Decimal
    rate: Decimal
    tax: Decimal


def _validate_brackets(brackets: list) -> list[tuple[Decimal | None, Decimal]]:
    parsed: list[tuple[Decimal | None, Decimal]] = []
    for pair in brackets:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"Malformed bracket entry: {pair!r}")
        upper, rate = pair
        if rate is None:
            raise ValueError(
                "Bracket rate is null — the config still holds placeholder "
                "values. A CPA must populate and verify brackets first."
            )
        parsed.append((None if upper is None else money(upper), money(rate)))
    return parsed


def tax_from_brackets(taxable_income: Decimal, brackets: list) -> tuple[Decimal, list[TaxBand]]:
    """Apply a progressive bracket schedule and return (total_tax, breakdown)."""
    parsed = _validate_brackets(brackets)
    income = money(taxable_income)
    total = Decimal("0")
    lower = Decimal("0")
    bands: list[TaxBand] = []
    for upper, rate in parsed:
        cap = income if upper is None else min(income, upper)
        in_band = cap - lower if cap > lower else Decimal("0")
        if in_band > 0:
            band_tax = round_money(in_band * rate)
            bands.append(TaxBand(in_band, rate, band_tax))
            total += band_tax
        lower = upper if upper is not None else lower
        if upper is not None and income <= upper:
            break
    return round_money(total), bands


def estimate_personal_tax(
    taxable_income, province: str, *, rates: dict | None = None
) -> dict:
    """Estimate combined federal + provincial personal tax (T1, simplified)."""
    rates = rates if rates is not None else load_rates()
    block = require_verified(rates, "personal_income_tax")
    fed_tax, fed_bands = tax_from_brackets(taxable_income, block["federal"]["brackets"])
    prov_cfg = block.get("provincial", {}).get(province)
    if not prov_cfg:
        raise KeyError(f"No provincial T1 brackets configured for '{province}'.")
    prov_tax, prov_bands = tax_from_brackets(taxable_income, prov_cfg["brackets"])
    return {
        "taxable_income": money(taxable_income),
        "federal_tax": fed_tax,
        "provincial_tax": prov_tax,
        "total_tax": round_money(fed_tax + prov_tax),
        "federal_bands": fed_bands,
        "provincial_bands": prov_bands,
    }


def estimate_corporate_tax(
    active_business_income, province: str, *, rates: dict | None = None
) -> dict:
    """Estimate T2 tax using small-business vs general rates (simplified)."""
    rates = rates if rates is not None else load_rates()
    block = require_verified(rates, "corporate_income_tax")
    fed = block["federal"]
    income = money(active_business_income)
    sbd_limit = money(fed["small_business_limit"])
    sb_income = min(income, sbd_limit)
    gen_income = max(Decimal("0"), income - sbd_limit)
    fed_tax = round_money(
        sb_income * money(fed["small_business_rate"])
        + gen_income * money(fed["general_rate"])
    )
    prov = block.get("provincial", {}).get(province)
    if not prov:
        raise KeyError(f"No provincial T2 rates configured for '{province}'.")
    prov_tax = round_money(
        sb_income * money(prov["small_business_rate"])
        + gen_income * money(prov["general_rate"])
    )
    return {
        "active_business_income": income,
        "federal_tax": fed_tax,
        "provincial_tax": prov_tax,
        "total_tax": round_money(fed_tax + prov_tax),
    }


def build_t1_workpaper(client: str, period: str, result: dict) -> Workpaper:
    wp = Workpaper("T1 Estimate", client, period)
    wp.section("Inputs")
    wp.kv("Taxable income", f"{result['taxable_income']:,.2f}")
    wp.section("Estimated tax")
    wp.kv("Federal", f"{result['federal_tax']:,.2f}")
    wp.kv("Provincial", f"{result['provincial_tax']:,.2f}")
    wp.kv("Total (before credits)", f"**{result['total_tax']:,.2f}**")
    wp.qc("Confirm brackets & basic personal amount against CRA")
    wp.qc("This estimate excludes credits/deductions — review completeness")
    return wp
