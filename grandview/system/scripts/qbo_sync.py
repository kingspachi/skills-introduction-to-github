"""QuickBooks Online sync — the bridge that fills the normalized cache.

Why this exists as a separate step
----------------------------------
The QBO MCP tools can only be called by the agent / integration layer, not by a
plain Python process. So syncing is a two-part handoff:

  * The **agent** (or a future server-side job) calls the QBO MCP tools, passes
    each raw response through the matching ``qbo_adapter.normalize_*`` mapper,
    and collects the normalized rows.
  * This module's :func:`write_cache` persists those rows to
    ``clients/<client>/qbo_<period>.json`` (git-ignored), which
    :class:`qbo_adapter.QuickBooksDataSource` then reads.

Tool -> mapper map (confirm tool names against the connected QBO server)
-----------------------------------------------------------------------
  qbo_sales_get_invoices        -> qbo_adapter.normalize_invoice    (sales)
  qbo_accounting (bills/expense) -> qbo_adapter.normalize_expense   (purchases)
  qbo_payroll_get_payslips      -> (feed payroll_processor.EmployeeInput)
  qbo_accounting_get_profit_loss / balance_sheet -> reconciliation inputs

Confidentiality: the cache holds real client financials and lives under the
git-ignored ``clients/`` tree. Never commit it; never move it into the repo.

CLI: write a cache from an already-normalized rows file (e.g. produced by the
agent) so the flow is scriptable/testable end to end:

    python system/scripts/qbo_sync.py --client ACME --period 2025-Q1 \
        --rows /path/to/normalized_rows.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import CLIENTS_DIR
from qbo_adapter import build_cache_payload


def write_cache(
    client: str,
    period: str,
    normalized_rows: list[dict[str, Any]],
    cache_root: Path = CLIENTS_DIR,
) -> Path:
    """Persist normalized rows as the QBO cache for (client, period)."""
    payload = build_cache_payload(client, period, normalized_rows)
    out_dir = cache_root / client
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"qbo_{period}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a QBO normalized cache file")
    parser.add_argument("--client", required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument(
        "--rows",
        required=True,
        help="Path to a JSON file containing a list of normalized rows.",
    )
    args = parser.parse_args()
    rows = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("--rows file must contain a JSON list of normalized rows.")
    path = write_cache(args.client, args.period, rows)
    print(f"Wrote QBO cache: {path} ({len(rows)} transactions)")


if __name__ == "__main__":
    main()
