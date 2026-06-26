"""Payroll source-deduction processor (config-driven scaffold).

Computes CPP, EI, and (optionally) income-tax withholding for a pay run, using
rates from ``config/tax_rates_2025.yaml``. Ships with placeholder (null) rates,
so it raises until a CPA populates and verifies the ``payroll`` section.

⚠️ Withholding tax in Canada is normally computed via CRA's payroll deductions
formulas/tables (T4127). This module implements the CPP/EI mechanics and leaves
income-tax withholding as an explicit integration point — it does not invent a
formula. Draft output for review only.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from common import Workpaper, load_rates, money, require_verified, round_money


@dataclass
class PayrollLine:
    employee: str
    gross: Decimal
    cpp_employee: Decimal
    ei_employee: Decimal
    cpp_employer: Decimal
    ei_employer: Decimal
    income_tax: Decimal
    net_pay: Decimal


def compute_cpp_ei(gross_period, ytd_pensionable, ytd_insurable, *, rates: dict | None = None):
    """Compute CPP & EI for one pay period (employee + employer portions).

    Caps are applied against year-to-date amounts so contributions stop once the
    annual maximums are reached. Income-tax withholding is NOT computed here.
    """
    rates = rates if rates is not None else load_rates()
    block = require_verified(rates, "payroll")
    cpp, ei = block["cpp"], block["ei"]

    gross = money(gross_period)

    # CPP: rate on (pensionable earnings - prorated basic exemption), capped.
    cpp_ceiling = money(cpp["max_pensionable_earnings"])
    pensionable_room = max(Decimal("0"), cpp_ceiling - money(ytd_pensionable))
    pensionable = min(gross, pensionable_room)
    cpp_employee = round_money(pensionable * money(cpp["employee_rate"]))
    cpp_employer = round_money(pensionable * money(cpp["employer_rate"]))

    # EI: rate on insurable earnings, capped at max insurable.
    ei_ceiling = money(ei["max_insurable_earnings"])
    insurable_room = max(Decimal("0"), ei_ceiling - money(ytd_insurable))
    insurable = min(gross, insurable_room)
    ei_employee = round_money(insurable * money(ei["employee_rate"]))
    ei_employer = round_money(ei_employee * money(ei["employer_multiplier"]))

    return {
        "cpp_employee": cpp_employee,
        "cpp_employer": cpp_employer,
        "ei_employee": ei_employee,
        "ei_employer": ei_employer,
    }


def income_tax_withholding(gross_period, province: str) -> Decimal:
    """Income-tax withholding integration point.

    CRA withholding must follow the T4127 payroll deductions formulas (or PDOC).
    This is intentionally left unimplemented rather than approximated, so nobody
    relies on a guessed number. Wire in the official formula here.
    """
    raise NotImplementedError(
        "Income-tax withholding must use the CRA T4127 formulas / PDOC. "
        "Implement against the official source, then verify."
    )


def build_workpaper(client: str, period: str, lines: list[PayrollLine]) -> Workpaper:
    wp = Workpaper("Payroll Register", client, period)
    wp.section("Pay run")
    wp.table(
        ["Employee", "Gross", "CPP (ee)", "EI (ee)", "Income tax", "Net pay"],
        [
            [l.employee, f"{l.gross:,.2f}", f"{l.cpp_employee:,.2f}",
             f"{l.ei_employee:,.2f}", f"{l.income_tax:,.2f}", f"{l.net_pay:,.2f}"]
            for l in lines
        ],
    )
    wp.qc("Confirm CPP/EI rates and annual maximums against CRA for the year")
    wp.qc("Confirm income-tax withholding via PDOC / T4127")
    wp.qc("Reconcile employer remittance (CPP + EI + tax) before due date")
    return wp
