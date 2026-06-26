"""Classify an incoming client document into a workflow category.

Keyword/heuristic based — a deliberately simple, transparent first pass. The
intent is that ``trigger_workflow`` routes on the returned category, and a CPA
confirms borderline cases. Swap in an LLM classifier (see prompts/) later for
harder documents.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# category -> keywords (lowercased substring match on filename + extracted text)
RULES: dict[str, list[str]] = {
    "T1":      ["t1", "t4 ", "t4a", "t5", "rrsp", "personal tax", "notice of assessment"],
    "T2":      ["t2", "corporate tax", "gifi", "schedule 100", "schedule 125"],
    "T3":      ["t3", "trust"],
    "GST_HST": ["gst", "hst", "gst34", "sales tax"],
    "PAYROLL": ["payroll", "t4 summary", "pd7a", "remittance", "roe", "pay stub"],
    "BANK":    ["bank statement", "e-statement", "chequing", "savings", "visa", "mastercard"],
    "WRITEUP": ["general ledger", "trial balance", "journal", "receipts", "invoices"],
}


@dataclass
class Classification:
    category: str
    confidence: float       # 0..1 crude score
    matched_terms: list[str]


def classify(filename: str, text: str = "") -> Classification:
    """Return the best-matching category for a document.

    ``text`` is optional extracted content (e.g. from PDF/OCR). When absent,
    only the filename is considered.
    """
    haystack = f"{filename}\n{text}".lower()
    best = Classification("UNKNOWN", 0.0, [])
    for category, terms in RULES.items():
        hits = [t for t in terms if t in haystack]
        if not hits:
            continue
        score = min(1.0, 0.4 + 0.2 * len(hits))  # more hits -> higher confidence
        if score > best.confidence:
            best = Classification(category, round(score, 2), hits)
    return best


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "2025_GST34_Q1.pdf"
    c = classify(name)
    print(f"{name} -> {c.category} (confidence {c.confidence}, matched {c.matched_terms})")
