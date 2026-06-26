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
from typing import Callable

import classify_documents
import trigger_workflow

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
INTAKE_DIR = PACKAGE_ROOT / "clients"
STATE_FILE = PACKAGE_ROOT / "system" / "skills" / ".seen_files.txt"

# Files that are part of the repo scaffolding, not client uploads.
IGNORED_NAMES = {".gitkeep", "README.md"}


def _load_seen(state_file: Path) -> set[str]:
    if state_file.exists():
        return set(state_file.read_text(encoding="utf-8").splitlines())
    return set()


def _save_seen(state_file: Path, seen: set[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("\n".join(sorted(seen)), encoding="utf-8")


def _default_handler(path: Path) -> dict:
    """Classify a new file and route it."""
    classification = classify_documents.classify(path.name)
    return trigger_workflow.route(path, classification)


def scan_once(
    intake_dir: Path = INTAKE_DIR,
    state_file: Path = STATE_FILE,
    *,
    on_new: Callable[[Path], object] | None = None,
) -> list[Path]:
    """Process any unseen files and return the list handled this pass.

    State is keyed by path relative to ``intake_dir`` so a file is handled once.
    ``on_new`` defaults to classify+route but can be injected for tests.
    """
    on_new = on_new or _default_handler
    seen = _load_seen(state_file)
    handled: list[Path] = []
    for path in sorted(intake_dir.rglob("*")):
        if not path.is_file() or path.name in IGNORED_NAMES:
            continue
        key = str(path.relative_to(intake_dir))
        if key in seen:
            continue
        on_new(path)
        seen.add(key)
        handled.append(path)
    _save_seen(state_file, seen)
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
