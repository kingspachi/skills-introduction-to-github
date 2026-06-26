"""QuickBooks Online data source adapter.

The calculation engines consume ``common.Transaction`` objects and never call
external services directly. QuickBooks data arrives through MCP tools that only
the agent / integration layer can invoke — Python scripts cannot reach MCP at
runtime. So this adapter is **decoupled by a normalized JSON cache**:

    1. A sync step (agent-mediated today; a server integration later) calls the
       QBO MCP tools, maps the responses into the normalized schema below, and
       writes ``clients/<client>/qbo_<period>.json``. See ``qbo_sync.py``.
    2. :class:`QuickBooksDataSource` reads that cache and yields ``Transaction``
       objects — exactly like :class:`common.FileDataSource`, so engines don't
       change.

Normalized cache schema (the contract between sync and engines):

    {
      "client": "ACME",
      "period": "2025-Q1",
      "source": "quickbooks",
      "synced_at": "2026-06-26T12:00:00",
      "transactions": [
        {"date": "2025-01-15", "description": "Invoice 1001",
         "amount": "10000.00", "account": "Revenue",
         "tax_code": "standard", "kind": "sale"}
      ]
    }

``kind`` is one of ``sale`` / ``purchase`` / ``other`` and lets engines that need
sales and purchases separately (e.g. GST) split a flat list.

The mapping from raw QBO responses to this schema lives in the ``normalize_*``
functions. Their field access is deliberately tolerant and the exact QBO field
names are marked CONFIRM — finalize them against a live response before
production. This mirrors the project's rule: don't bake in external facts we
haven't verified.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from common import CLIENTS_DIR, DataSource, Transaction, money, _parse_date

NORMALIZED_KEYS = ("date", "description", "amount", "account", "tax_code", "kind")


class QuickBooksDataSource(DataSource):
    """Reads normalized QBO cache files written by the sync step."""

    def __init__(self, cache_root: Path = CLIENTS_DIR) -> None:
        self.cache_root = Path(cache_root)

    def cache_path(self, client: str, period: str) -> Path:
        return self.cache_root / client / f"qbo_{period}.json"

    def transactions(self, client: str, period: str) -> list[Transaction]:
        path = self.cache_path(client, period)
        if not path.exists():
            raise FileNotFoundError(
                f"No QBO cache found: {path}. Run the sync step first "
                f"(see qbo_sync.py) to populate it from QuickBooks."
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        return transactions_from_cache(payload)


def _to_transaction(row: dict[str, Any]) -> Transaction:
    return Transaction(
        date=_parse_date(row.get("date")),
        description=str(row.get("description", "")).strip(),
        amount=money(row.get("amount", 0)),
        account=row.get("account"),
        tax_code=row.get("tax_code"),
        raw={**row, "kind": row.get("kind", "other")},
    )


def transactions_from_cache(payload: dict[str, Any]) -> list[Transaction]:
    """Parse a normalized cache payload into Transaction objects."""
    rows = payload.get("transactions", [])
    if not isinstance(rows, list):
        raise ValueError("Cache 'transactions' must be a list.")
    return [_to_transaction(r) for r in rows]


def split_sales_purchases(
    txns: list[Transaction],
) -> tuple[list[Transaction], list[Transaction]]:
    """Split a flat transaction list into (sales, purchases) by ``kind``."""
    sales = [t for t in txns if (t.raw.get("kind") == "sale")]
    purchases = [t for t in txns if (t.raw.get("kind") == "purchase")]
    return sales, purchases


# --- Raw QBO -> normalized mappers -----------------------------------------
# These convert QBO MCP tool responses into normalized rows. Field names below
# are best-effort and marked CONFIRM; verify against an actual response and
# adjust. Keeping access tolerant (.get) means a shape change degrades to empty
# fields rather than crashing mid-engagement.

def normalize_invoice(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one QBO invoice (from qbo_sales_get_invoices) to a 'sale' row."""
    return {
        "date": raw.get("TxnDate") or raw.get("date"),            # CONFIRM
        "description": raw.get("DocNumber") or raw.get("description") or "Invoice",
        "amount": raw.get("TotalAmt") or raw.get("amount") or 0,  # CONFIRM (excl. vs incl. tax)
        "account": "Revenue",
        "tax_code": _map_tax_code(raw.get("TxnTaxDetail")),       # CONFIRM
        "kind": "sale",
    }


def normalize_expense(raw: dict[str, Any]) -> dict[str, Any]:
    """Map one QBO bill/expense to a 'purchase' row."""
    return {
        "date": raw.get("TxnDate") or raw.get("date"),            # CONFIRM
        "description": raw.get("DocNumber") or raw.get("description") or "Expense",
        "amount": raw.get("TotalAmt") or raw.get("amount") or 0,  # CONFIRM
        "account": raw.get("AccountRef", {}).get("name") if isinstance(raw.get("AccountRef"), dict) else raw.get("account"),
        "tax_code": _map_tax_code(raw.get("TxnTaxDetail")),       # CONFIRM
        "kind": "purchase",
    }


def _map_tax_code(detail: Any) -> str:
    """Best-effort map of a QBO tax detail to our codes. CONFIRM mapping.

    Returns one of: standard / zero / exempt / out. Defaults to 'standard'
    (the conservative choice for GST) — but the GST prompt template flags any
    transaction whose code wasn't explicitly confirmed.
    """
    if not detail:
        return "standard"
    if isinstance(detail, dict):
        total_tax = detail.get("TotalTax")
        if total_tax in (0, "0", "0.00", None):
            return "zero"
    return "standard"


def build_cache_payload(
    client: str, period: str, normalized_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Assemble a cache payload from normalized rows (used by the sync step)."""
    return {
        "client": client,
        "period": period,
        "source": "quickbooks",
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "transactions": normalized_rows,
    }
