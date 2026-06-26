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


def notify(
    subject: str,
    body: str = "",
    *,
    urgent: bool = False,
    log_path: Path | None = None,
    echo: bool = True,
) -> str:
    """Record/emit a notification and return the log entry written.

    Never raises on I/O. ``log_path`` overrides the default file (useful for
    tests); ``echo`` controls the stdout line.
    """
    target = log_path or NOTIFY_LOG
    stamp = datetime.now().isoformat(timespec="seconds")
    flag = "URGENT" if urgent else "INFO"
    entry = f"[{stamp}] [{flag}] {subject}\n{body}\n{'-' * 60}\n"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    except OSError:
        pass
    if echo:
        # Surface to stdout so it's visible when run interactively.
        print(f"[notify:{flag}] {subject}")
    return entry


if __name__ == "__main__":
    notify("Test notification", "Notification channel is working.", urgent=False)
