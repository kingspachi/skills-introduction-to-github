"""Payroll source-deduction processor.

Computes CPP and EI source deductions (employee + employer) for a pay run using
rates from ``config/tax_rates_2025.yaml``, applies the prorated CPP basic
exemption, respects year-to-date annual maximums, assembles a payroll register,
and totals the employer's CRA remittance.

Income-tax withholding is **not** invented here. CRA withholding must follow the
T4127 payroll deductions formulas / PDOC; this module accepts a withholding
amount per employee (e.g. from PDOC) and flags when it is missing, rather than
guessing. See :func:`income_tax_withholding`.

The shipped config has placeholder (null) rates and ``verified: false``, so the
engine refuses to run on it until a CPA populates and verifies the ``payroll``
section. Tests and the demo inject controlled, marked-verified rates.

Draft output for CPA review only.

Run a demo:
    python system/scripts/payroll_processor.py --demo
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from decimal import Decimal

from common import Workpaper, load_rates, money, require_verified, round_money


@dataclass
class EmployeeInput:
    """One employee's inputs for a single pay period."""

    name: str
    gross: Decimal
    province: str = "ON"
    ytd_pensionable: Decimal = Decimal("0")
    ytd_insurable: Decimal = Decimal("0")
    # Income-tax withholding from PDOC/T4127. None means "not yet determined".
    income_tax: Decimal | None = None


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
    flags: list[str] = field(default_factory=list)


@dataclass
class RemittanceSummary:
    cpp_employee: Decimal
    cpp_employer: Decimal
    ei_employee: Decimal
    ei_employer: Decimal
    income_tax: Decimal

    @property
    def total_remittance(self) -> Decimal:
        return round_money(
            self.cpp_employee
            + self.cpp_employer
            + self.ei_employee
            + self.ei_employer
            + self.income_tax
        )


def compute_cpp_ei(
    gross_period,
    ytd_pensionable,
    ytd_insurable,
    *,
    pay_periods_per_year: int = 26,
    rates: dict | None = None,
) -> dict[str, Decimal]:
    """Compute CPP & EI for one pay period (employee + employer portions).

    CPP contributory earnings for the period are the pensionable earnings (capped
    so YTD does not exceed the annual maximum) less the prorated annual basic
    exemption. EI is charged on insurable earnings capped at the annual maximum.
    Income-tax withholding is NOT computed here.
    """
    rates = rates if rates is not None else load_rates()
    block = require_verified(rates, "payroll")
    cpp, ei = block["cpp"], block["ei"]

    gross = money(gross_period)

    # --- CPP ---------------------------------------------------------------
    cpp_ceiling = money(cpp["max_pensionable_earnings"])
    pensionable_room = max(Decimal("0"), cpp_ceiling - money(ytd_pensionable))
    pensionable = min(gross, pensionable_room)
    # Prorate the annual basic exemption across pay periods (CRA convention).
    exemption_per_period = money(cpp["basic_exemption"]) / Decimal(pay_periods_per_year)
    cpp_base = max(Decimal("0"), pensionable - exemption_per_period)
    cpp_employee = round_money(cpp_base * money(cpp["employee_rate"]))
    cpp_employer = round_money(cpp_base * money(cpp["employer_rate"]))

    # --- EI ----------------------------------------------------------------
    ei_ceiling = money(ei["max_insurable_earnings"])
    insurable_room = max(Decimal("0"), ei_ceiling - money(ytd_insurable))
    insurable = min(gross, insurable_room)
    ei_employee = round_money(insurable * money(ei["employee_rate"]))
    ei_employer = round_money(ei_employee * money(ei["employer_multiplier"]))

    return {
        "cpp_pensionable": round_money(pensionable),
        "cpp_employee": cpp_employee,
        "cpp_employer": cpp_employer,
        "ei_insurable": round_money(insurable),
        "ei_employee": ei_employee,
        "ei_employer": ei_employer,
    }


def income_tax_withholding(gross_period, province: str) -> Decimal:
    """Income-tax withholding integration point.

    CRA withholding must follow the T4127 payroll deductions formulas (or PDOC).
    This is intentionally left unimplemented rather than approximated, so nobody
    relies on a guessed number. Wire in the official formula here, then have
    callers pass the result via ``EmployeeInput.income_tax``.
    """
    raise NotImplementedError(
        "Income-tax withholding must use the CRA T4127 formulas / PDOC. "
        "Implement against the official source, then verify."
    )


def process_payrun(
    employees: list[EmployeeInput],
    *,
    pay_periods_per_year: int = 26,
    rates: dict | None = None,
) -> tuple[list[PayrollLine], RemittanceSummary]:
    """Process a full pay run and return (register lines, employer remittance)."""
    rates = rates if rates is not None else load_rates()
    lines: list[PayrollLine] = []
    tot_cpp_ee = tot_cpp_er = tot_ei_ee = tot_ei_er = tot_tax = Decimal("0")

    for emp in employees:
        d = compute_cpp_ei(
            emp.gross,
            emp.ytd_pensionable,
            emp.ytd_insurable,
            pay_periods_per_year=pay_periods_per_year,
            rates=rates,
        )
        flags: list[str] = []
        if emp.income_tax is None:
            tax = Decimal("0.00")
            flags.append("Income tax withholding not provided (run PDOC/T4127)")
        else:
            tax = round_money(emp.income_tax)

        net = round_money(money(emp.gross) - d["cpp_employee"] - d["ei_employee"] - tax)
        lines.append(
            PayrollLine(
                employee=emp.name,
                gross=round_money(emp.gross),
                cpp_employee=d["cpp_employee"],
                ei_employee=d["ei_employee"],
                cpp_employer=d["cpp_employer"],
                ei_employer=d["ei_employer"],
                income_tax=tax,
                net_pay=net,
                flags=flags,
            )
        )
        tot_cpp_ee += d["cpp_employee"]
        tot_cpp_er += d["cpp_employer"]
        tot_ei_ee += d["ei_employee"]
        tot_ei_er += d["ei_employer"]
        tot_tax += tax

    summary = RemittanceSummary(
        cpp_employee=round_money(tot_cpp_ee),
        cpp_employer=round_money(tot_cpp_er),
        ei_employee=round_money(tot_ei_ee),
        ei_employer=round_money(tot_ei_er),
        income_tax=round_money(tot_tax),
    )
    return lines, summary


def build_workpaper(
    client: str,
    period: str,
    lines: list[PayrollLine],
    summary: RemittanceSummary,
) -> Workpaper:
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
    wp.section("Employer remittance to CRA")
    wp.table(
        ["Component", "Amount (CAD)"],
        [
            ["CPP (employee)", f"{summary.cpp_employee:,.2f}"],
            ["CPP (employer)", f"{summary.cpp_employer:,.2f}"],
            ["EI (employee)", f"{summary.ei_employee:,.2f}"],
            ["EI (employer)", f"{summary.ei_employer:,.2f}"],
            ["Income tax withheld", f"{summary.income_tax:,.2f}"],
            ["**Total remittance**", f"**{summary.total_remittance:,.2f}**"],
        ],
    )
    flagged = [l for l in lines if l.flags]
    if flagged:
        wp.section("⚠️ Items needing attention")
        for l in flagged:
            for f in l.flags:
                wp.line(f"- {l.employee}: {f}")
    wp.qc("Confirm CPP/EI rates, basic exemption, and annual maximums against CRA")
    wp.qc("Confirm income-tax withholding via PDOC / T4127 for each employee")
    wp.qc("Confirm CPP2 (second additional contribution) applicability")
    wp.qc("Confirm pay-period count and proration are correct")
    wp.qc("Reconcile total remittance and confirm the due date is met")
    return wp


# --- Demo / CLI -------------------------------------------------------------
# Controlled, clearly-fictional rates marked verified ONLY so the demo can run.
_DEMO_RATES = {
    "payroll": {
        "verified": True,
        "cpp": {
            "employee_rate": 0.0595,
            "employer_rate": 0.0595,
            "basic_exemption": 3500,
            "max_pensionable_earnings": 68500,
        },
        "ei": {
            "employee_rate": 0.0164,
            "employer_multiplier": 1.4,
            "max_insurable_earnings": 63200,
        },
    }
}


def _demo() -> None:
    print("Running payroll demo (using FICTIONAL placeholder rates)...\n")
    employees = [
        EmployeeInput("Alice Wong", money("3000.00"), income_tax=money("450.00")),
        EmployeeInput("Bob Singh", money("2500.00")),  # no withholding provided
    ]
    lines, summary = process_payrun(employees, pay_periods_per_year=26, rates=_DEMO_RATES)
    wp = build_workpaper("DEMO_CLIENT", "2025-PP01", lines, summary)
    print(wp.render())
    print("\n[demo] Rates were FICTIONAL — do not rely on these numbers.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Payroll source-deduction processor")
    parser.add_argument("--demo", action="store_true", help="Run a self-contained demo")
    args = parser.parse_args()
    if args.demo:
        _demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
