"""Watch the client intake folder for newly uploaded documents.

A lightweight polling watcher (no external deps). For each new file it sees, it
classifies the document and hands off to ``trigger_workflow``. In production you
might replace polling with an OS file-watcher or a real portal webhook.

Usage:
    python system/skills/watch_client_portal.py --once   # single scan
    python system/skills/watch_client_portal.py          # poll every 30s
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import classify_documents
import trigger_workflow

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
INTAKE_DIR = PACKAGE_ROOT / "clients"
STATE_FILE = PACKAGE_ROOT / "system" / "skills" / ".seen_files.txt"


def _load_seen() -> set[str]:
    if STATE_FILE.exists():
        return set(STATE_FILE.read_text(encoding="utf-8").splitlines())
    return set()


def _save_seen(seen: set[str]) -> None:
    STATE_FILE.write_text("\n".join(sorted(seen)), encoding="utf-8")


def scan_once() -> list[Path]:
    """Process any unseen files and return the list handled this pass."""
    seen = _load_seen()
    handled: list[Path] = []
    for path in INTAKE_DIR.rglob("*"):
        if not path.is_file() or path.name in {".gitkeep", "README.md"}:
            continue
        key = str(path.relative_to(PACKAGE_ROOT))
        if key in seen:
            continue
        classification = classify_documents.classify(path.name)
        trigger_workflow.route(path, classification)
        seen.add(key)
        handled.append(path)
    _save_seen(seen)
    return handled


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch client intake folder")
    parser.add_argument("--once", action="store_true", help="Scan once and exit")
    parser.add_argument("--interval", type=int, default=30, help="Poll seconds")
    args = parser.parse_args()

    if args.once:
        handled = scan_once()
        print(f"Handled {len(handled)} new file(s).")
        return
    print(f"Watching {INTAKE_DIR} every {args.interval}s (Ctrl-C to stop)...")
    while True:
        for p in scan_once():
            print(f"  processed: {p.name}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
