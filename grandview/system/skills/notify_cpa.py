"""Notify the CPA about workflow events.

Default channel is an append-only local log so the system works with zero
configuration. Email/Slack/Teams channels can be added behind the same
``notify()`` interface without changing callers.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
NOTIFY_LOG = PACKAGE_ROOT / "system" / "skills" / "notifications.log"


def notify(subject: str, body: str = "", *, urgent: bool = False) -> None:
    """Record/emit a notification. Returns nothing; never raises on I/O."""
    stamp = datetime.now().isoformat(timespec="seconds")
    flag = "URGENT" if urgent else "INFO"
    entry = f"[{stamp}] [{flag}] {subject}\n{body}\n{'-' * 60}\n"
    try:
        with NOTIFY_LOG.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    except OSError:
        pass
    # Also surface to stdout so it's visible when run interactively.
    print(f"[notify:{flag}] {subject}")


if __name__ == "__main__":
    notify("Test notification", "Notification channel is working.", urgent=False)
