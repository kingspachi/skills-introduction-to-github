"""Shared utilities for the Grandview CPA automation engines.

Everything that more than one engine needs lives here:

* config loading (rates + firm settings)
* exact-money arithmetic helpers (Decimal, banker's rounding off)
* a verification guard so unverified rates can't silently reach production
* a pluggable ``DataSource`` adapter (file today, QuickBooks later)
* a small Markdown workpaper builder

Python 3.11+.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Sequence

# --- Paths ------------------------------------------------------------------
# grandview/system/scripts/common.py -> grandview/
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PACKAGE_ROOT / "config"
CLIENTS_DIR = PACKAGE_ROOT / "clients"
WORKPAPERS_DIR = PACKAGE_ROOT / "workpapers"


# --- Errors -----------------------------------------------------------------
class ConfigError(RuntimeError):
    """Raised when configuration is missing or malformed."""


class UnverifiedRatesError(RuntimeError):
    """Raised when an engine tries to use a rates section not yet CPA-verified."""


# --- Config loading ---------------------------------------------------------
def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - env dependent
        raise ConfigError(
            "PyYAML is required to read config files. Install with "
            "`pip install pyyaml` (see grandview/requirements.txt)."
        ) from exc
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError(f"Config file {path} did not parse to a mapping.")
    return data


def load_rates(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    """Load the tax-rate configuration."""
    return _load_yaml(config_dir / "tax_rates_2025.yaml")


def load_firm_config(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    """Load firm-level settings."""
    return _load_yaml(config_dir / "firm_config.yaml")


def require_verified(rates: dict[str, Any], section: str) -> dict[str, Any]:
    """Return a rates section, but only if a human has marked it verified.

    This is the safety gate that stops placeholder numbers from reaching a
    real filing. Engines should call this instead of indexing ``rates``
    directly. In a review/demo context, callers may catch the error and warn.
    """
    block = rates.get(section)
    if not isinstance(block, dict):
        raise ConfigError(f"Rates section '{section}' is missing or malformed.")
    if not block.get("verified", False):
        raise UnverifiedRatesError(
            f"Rates section '{section}' is not marked verified. A CPA must "
            f"confirm every value against {block.get('source', 'the CRA source')} "
            f"and set `verified: true` before production use."
        )
    return block


# --- Money helpers ----------------------------------------------------------
def money(value: Any) -> Decimal:
    """Coerce a value to a Decimal safely (via str to avoid float artefacts)."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value: Any, dp: int = 2) -> Decimal:
    """Round to currency precision using ROUND_HALF_UP (CRA convention)."""
    quant = Decimal(1).scaleb(-dp)  # 2 -> 0.01
    return money(value).quantize(quant, rounding=ROUND_HALF_UP)


# --- Data source adapter ----------------------------------------------------
@dataclass
class Transaction:
    """A normalized source transaction shared by the engines."""

    date: date | None
    description: str
    amount: Decimal
    account: str | None = None
    tax_code: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class DataSource:
    """Adapter interface for pulling source data.

    Subclass and implement :meth:`transactions`. Today only the file-based
    adapter exists; a QuickBooks adapter can be dropped in later without any
    change to the calculation engines.
    """

    def transactions(self, client: str, period: str) -> list[Transaction]:
        raise NotImplementedError


class FileDataSource(DataSource):
    """Reads transactions from a client's CSV files under ``clients/``.

    Expected CSV columns (case-insensitive, extras preserved in ``raw``):
    ``date, description, amount`` and optionally ``account, tax_code``.
    """

    def __init__(self, client_root: Path = CLIENTS_DIR) -> None:
        self.client_root = client_root

    def transactions(self, client: str, period: str) -> list[Transaction]:
        path = self.client_root / client / f"{period}.csv"
        if not path.exists():
            raise ConfigError(f"No transaction file found: {path}")
        out: list[Transaction] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                lower = {(k or "").strip().lower(): v for k, v in row.items()}
                out.append(
                    Transaction(
                        date=_parse_date(lower.get("date")),
                        description=(lower.get("description") or "").strip(),
                        amount=money(lower.get("amount") or 0),
                        account=lower.get("account"),
                        tax_code=lower.get("tax_code"),
                        raw=dict(row),
                    )
                )
        return out


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def get_data_source(firm_config: dict[str, Any] | None = None) -> DataSource:
    """Factory that returns the configured data source adapter."""
    firm_config = firm_config or load_firm_config()
    sources = firm_config.get("data_sources", {})
    active = sources.get("active", "file")
    if active == "file":
        return FileDataSource()
    if active == "quickbooks":
        # Imported lazily to avoid a hard dependency when only files are used.
        from qbo_adapter import QuickBooksDataSource

        cache_root = sources.get("quickbooks", {}).get("cache_root")
        if cache_root:
            return QuickBooksDataSource(PACKAGE_ROOT / cache_root)
        return QuickBooksDataSource()
    raise ConfigError(
        f"Data source '{active}' is not implemented. "
        "Available: 'file', 'quickbooks'."
    )


# --- Workpaper builder ------------------------------------------------------
class Workpaper:
    """Tiny helper to assemble a reviewable Markdown workpaper."""

    def __init__(self, title: str, client: str, period: str) -> None:
        self.title = title
        self.client = client
        self.period = period
        self._lines: list[str] = []
        self._qc: list[str] = []

    def section(self, heading: str) -> "Workpaper":
        self._lines.append(f"\n## {heading}\n")
        return self

    def line(self, text: str = "") -> "Workpaper":
        self._lines.append(text)
        return self

    def kv(self, label: str, value: Any) -> "Workpaper":
        self._lines.append(f"- **{label}:** {value}")
        return self

    def table(self, headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> "Workpaper":
        self._lines.append("| " + " | ".join(headers) + " |")
        self._lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows:
            self._lines.append("| " + " | ".join(str(c) for c in row) + " |")
        return self

    def qc(self, item: str) -> "Workpaper":
        self._qc.append(item)
        return self

    def render(self) -> str:
        header = [
            f"# {self.title}",
            "",
            f"- **Client:** {self.client}",
            f"- **Period:** {self.period}",
            f"- **Prepared:** {date.today().isoformat()} (DRAFT — for CPA review)",
            "",
            "> ⚠️ All figures are computer-generated drafts. A CPA must review "
            "inputs, verify rates against CRA, and sign off before filing.",
        ]
        body = header + self._lines
        if self._qc:
            body.append("\n## QC checklist\n")
            body.extend(f"- [ ] {item}" for item in self._qc)
        body.append("\n## Reviewer sign-off\n")
        body.append("- Prepared by: ______________   Date: __________")
        body.append("- Reviewed by: ______________   Date: __________")
        return "\n".join(body) + "\n"

    def save(self, filename: str | None = None) -> Path:
        WORKPAPERS_DIR.mkdir(parents=True, exist_ok=True)
        name = filename or f"{self.client}_{self.period}_{self.title}".replace(" ", "_")
        path = WORKPAPERS_DIR / f"{name}.md"
        path.write_text(self.render(), encoding="utf-8")
        return path
