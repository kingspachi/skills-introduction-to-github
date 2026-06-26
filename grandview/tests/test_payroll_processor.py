"""Unit tests for the payroll processor.

Run from the grandview/ directory:  python -m pytest tests/

Rates here are fictional but marked verified so the engine will run; they are
chosen to make the arithmetic easy to check by hand.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "system" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import UnverifiedRatesError, money  # noqa: E402
from payroll_processor import (  # noqa: E402
    EmployeeInput,
    compute_cpp_ei,
    process_payrun,
)

RATES = {
    "payroll": {
        "verified": True,
        "cpp": {
            "employee_rate": 0.05,
            "employer_rate": 0.05,
            "basic_exemption": 2600,   # /26 periods = 100 exemption per period
            "max_pensionable_earnings": 60000,
        },
        "ei": {
            "employee_rate": 0.02,
            "employer_multiplier": 1.4,
            "max_insurable_earnings": 50000,
        },
    }
}


def test_cpp_applies_prorated_basic_exemption():
    d = compute_cpp_ei("1000.00", "0", "0", pay_periods_per_year=26, rates=RATES)
    # CPP base = 1000 - (2600/26 = 100) = 900; * 0.05 = 45.00
    assert d["cpp_employee"] == Decimal("45.00")
    assert d["cpp_employer"] == Decimal("45.00")


def test_ei_is_rate_times_insurable():
    d = compute_cpp_ei("1000.00", "0", "0", rates=RATES)
    assert d["ei_employee"] == Decimal("20.00")            # 1000 * 0.02
    assert d["ei_employer"] == Decimal("28.00")            # 20 * 1.4


def test_cpp_ceiling_caps_pensionable():
    # Already at the YMPE: no further pensionable earnings -> no CPP.
    d = compute_cpp_ei("1000.00", "60000", "0", rates=RATES)
    assert d["cpp_employee"] == Decimal("0.00")


def test_ei_ceiling_caps_insurable():
    d = compute_cpp_ei("1000.00", "0", "50000", rates=RATES)
    assert d["ei_employee"] == Decimal("0.00")


def test_net_pay_and_missing_tax_is_flagged():
    emps = [EmployeeInput("No Tax", money("1000.00"))]
    lines, summary = process_payrun(emps, rates=RATES)
    line = lines[0]
    # gross 1000 - cpp 45 - ei 20 - tax 0 = 935
    assert line.net_pay == Decimal("935.00")
    assert line.income_tax == Decimal("0.00")
    assert any("withholding" in f.lower() for f in line.flags)


def test_remittance_summary_totals():
    emps = [
        EmployeeInput("A", money("1000.00"), income_tax=money("100.00")),
        EmployeeInput("B", money("1000.00"), income_tax=money("100.00")),
    ]
    _, s = process_payrun(emps, rates=RATES)
    # Per employee: cpp_ee 45, cpp_er 45, ei_ee 20, ei_er 28, tax 100
    assert s.cpp_employee == Decimal("90.00")
    assert s.ei_employer == Decimal("56.00")
    assert s.income_tax == Decimal("200.00")
    # total = 90 + 90 + 40 + 56 + 200
    assert s.total_remittance == Decimal("476.00")


def test_unverified_rates_blocked():
    bad = {"payroll": {"verified": False, "cpp": {}, "ei": {}}}
    with pytest.raises(UnverifiedRatesError):
        compute_cpp_ei("1000", "0", "0", rates=bad)
