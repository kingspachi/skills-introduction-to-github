"""Workpaper / report generation helpers.

The core builder lives in :class:`common.Workpaper`. This module adds
convenience routines for batch-generating and saving workpapers, and a single
entry point engines can share.
"""
from __future__ import annotations

from pathlib import Path

from common import Workpaper


def save_workpaper(wp: Workpaper, filename: str | None = None) -> Path:
    """Persist a workpaper to the (git-ignored) workpapers/ directory."""
    path = wp.save(filename)
    print(f"Workpaper written: {path}")
    return path


def combine(title: str, client: str, period: str, sections: list[Workpaper]) -> Workpaper:
    """Merge several engine workpapers into a single engagement file."""
    master = Workpaper(title, client, period)
    for wp in sections:
        master.line(f"\n---\n\n# {wp.title}")
        master.line(wp.render())
    return master
