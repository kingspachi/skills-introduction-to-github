"""Unit tests for the intake skills chain (classify -> route -> notify, watch).

Run from the grandview/ directory:  python -m pytest tests/

Everything is parameterized to temp dirs / injected callables, so tests never
write to the repo's clients/ or skills/ paths.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "system" / "skills"
sys.path.insert(0, str(SKILLS))

import classify_documents  # noqa: E402
import notify_cpa  # noqa: E402
import trigger_workflow  # noqa: E402
import watch_client_portal  # noqa: E402


# --- classify_documents -----------------------------------------------------
def test_classify_known_categories():
    assert classify_documents.classify("2025_GST34_Q1.pdf").category == "GST_HST"
    assert classify_documents.classify("T2_return.pdf").category == "T2"
    assert classify_documents.classify("Chequing statement.pdf").category == "BANK"


def test_classify_is_case_insensitive():
    assert classify_documents.classify("PAYROLL_register.XLSX").category == "PAYROLL"


def test_classify_unknown_when_no_match():
    c = classify_documents.classify("random_photo.jpg")
    assert c.category == "UNKNOWN"
    assert c.confidence == 0.0


def test_classify_confidence_rises_with_more_hits():
    one = classify_documents.classify("hst.pdf")
    many = classify_documents.classify("gst hst gst34 sales tax.pdf")
    assert many.confidence > one.confidence


# --- trigger_workflow.route -------------------------------------------------
def test_route_maps_category_to_workflow():
    calls = []
    cls = classify_documents.classify("2025_GST34_Q1.pdf")
    item = trigger_workflow.route(
        Path("2025_GST34_Q1.pdf"), cls, notifier=lambda **k: calls.append(k)
    )
    assert item["workflow"] == "gst_calculator"
    assert item["needs_review"] is False
    assert len(calls) == 1  # CPA was notified exactly once


def test_route_flags_unknown_for_review_and_marks_urgent():
    calls = []
    cls = classify_documents.classify("mystery.bin")
    item = trigger_workflow.route(
        Path("mystery.bin"), cls, notifier=lambda **k: calls.append(k)
    )
    assert item["category"] == "UNKNOWN"
    assert item["needs_review"] is True
    assert calls[0]["urgent"] is True


# --- notify_cpa -------------------------------------------------------------
def test_notify_writes_to_given_log(tmp_path):
    log = tmp_path / "n.log"
    entry = notify_cpa.notify("Subject", "Body", log_path=log, echo=False)
    assert log.exists()
    contents = log.read_text(encoding="utf-8")
    assert "Subject" in contents and "Subject" in entry


def test_notify_urgent_flag_in_entry(tmp_path):
    entry = notify_cpa.notify("x", urgent=True, log_path=tmp_path / "n.log", echo=False)
    assert "[URGENT]" in entry


# --- watch_client_portal.scan_once ------------------------------------------
def test_scan_processes_new_files_once(tmp_path):
    intake = tmp_path / "clients"
    (intake / "acme").mkdir(parents=True)
    (intake / "acme" / "2025_GST34.pdf").write_text("x")
    (intake / "acme" / ".gitkeep").write_text("")  # must be ignored
    state = tmp_path / "state.txt"
    seen_paths = []

    handled = watch_client_portal.scan_once(
        intake, state, on_new=lambda p: seen_paths.append(p.name)
    )
    assert [p.name for p in handled] == ["2025_GST34.pdf"]
    assert seen_paths == ["2025_GST34.pdf"]

    # Second pass: already seen -> nothing re-processed.
    handled2 = watch_client_portal.scan_once(
        intake, state, on_new=lambda p: seen_paths.append(p.name)
    )
    assert handled2 == []
    assert seen_paths == ["2025_GST34.pdf"]


def test_scan_picks_up_a_newly_added_file(tmp_path):
    intake = tmp_path / "clients"
    intake.mkdir()
    state = tmp_path / "state.txt"
    (intake / "a.pdf").write_text("x")
    watch_client_portal.scan_once(intake, state, on_new=lambda p: None)
    # Add a second file; only it should be handled on the next pass.
    (intake / "b.pdf").write_text("x")
    handled = watch_client_portal.scan_once(intake, state, on_new=lambda p: None)
    assert [p.name for p in handled] == ["b.pdf"]


def test_scan_end_to_end_through_real_chain(tmp_path):
    """classify -> route -> notify, with notify redirected to a temp log."""
    intake = tmp_path / "clients"
    intake.mkdir()
    (intake / "payroll_register.xlsx").write_text("x")
    state = tmp_path / "state.txt"
    log = tmp_path / "n.log"

    def handler(path: Path) -> dict:
        cls = classify_documents.classify(path.name)
        return trigger_workflow.route(
            path, cls, notifier=lambda **k: notify_cpa.notify(**k, log_path=log, echo=False)
        )

    handled = watch_client_portal.scan_once(intake, state, on_new=handler)
    assert len(handled) == 1
    assert "payroll_processor" in log.read_text(encoding="utf-8")
