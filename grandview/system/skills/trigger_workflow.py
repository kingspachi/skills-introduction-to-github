"""Route a classified document to the right engine / engagement queue.

This is the dispatcher between intake (``watch_client_portal`` +
``classify_documents``) and the calculation engines. It deliberately does NOT
auto-run filings; it queues work and notifies the CPA, who decides what to run.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import notify_cpa

# Map a document category to the engine/workflow that should handle it.
ROUTES: dict[str, str] = {
    "T1": "tax_calculator (personal)",
    "T2": "tax_calculator (corporate)",
    "T3": "trust engagement (manual)",
    "GST_HST": "gst_calculator",
    "PAYROLL": "payroll_processor",
    "BANK": "bank_rec_engine",
    "WRITEUP": "write-up / compilation queue",
    "UNKNOWN": "manual triage",
}

# Below this confidence (or for UNKNOWN) a document needs human confirmation.
LOW_CONFIDENCE_THRESHOLD = 0.5


def route(path: Path, classification, *, notifier: Callable | None = None) -> dict:
    """Queue a document for its workflow and notify the CPA.

    ``notifier`` defaults to :func:`notify_cpa.notify` but can be injected
    (tests, alternate channels). Returns the queued work item, including a
    ``needs_review`` flag for low-confidence/unknown classifications.
    """
    notifier = notifier or notify_cpa.notify
    target = ROUTES.get(classification.category, "manual triage")
    low_conf = (
        classification.confidence < LOW_CONFIDENCE_THRESHOLD
        or classification.category == "UNKNOWN"
    )
    item = {
        "file": str(path.name),
        "category": classification.category,
        "confidence": classification.confidence,
        "workflow": target,
        "needs_review": low_conf,
    }
    notifier(
        subject=f"New document: {path.name} -> {classification.category}",
        body=(
            f"Routed to: {target}\n"
            f"Confidence: {classification.confidence}\n"
            + ("⚠️ Low confidence — please confirm classification.\n" if low_conf else "")
        ),
        urgent=low_conf,
    )
    return item
