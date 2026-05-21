"""
Tests for scripts/render_report.py — the deterministic report renderer.

The byte-stability test against the checked-in golden is the load-bearing
guarantee: it catches any change in the template, the renderer, or the
sample fixture that would cause user-visible report drift.

Update the golden intentionally (with a CHANGELOG entry) when the report
format is meant to change. Do not silently regenerate it to make the test
pass — that defeats its purpose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.render_report import (  # noqa: E402
    blockquote,
    build_context,
    emoji_for,
    line_range_for,
    load_report,
    render,
    title_from,
)

FIXTURE_RUN_DIR = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "pytorch-trainer"
    / ".review"
    / "runs"
    / "2026-05-12-1513-pytorch-trainer"
)
GOLDEN = REPO_ROOT / "tests" / "golden" / "2026-05-12-1513-pytorch-trainer.md"


# -- Byte stability --------------------------------------------------------


def test_render_matches_checked_in_golden():
    """
    Renders the pytorch-trainer fixture and compares byte-for-byte against
    the committed golden output. If this fails, either:
    - The template / renderer changed unintentionally (regression), or
    - The change is intentional and the golden needs an explicit update
      with a matching CHANGELOG entry.
    """
    report = load_report(FIXTURE_RUN_DIR / "final-report.json")
    rendered = render(report)
    expected = GOLDEN.read_text()
    assert rendered == expected, (
        "Rendered output differs from committed golden. "
        "If this change is intentional, update "
        f"{GOLDEN.relative_to(REPO_ROOT)} and document it in CHANGELOG.md."
    )


def test_render_is_idempotent():
    """Two renders of the same input must produce identical bytes."""
    report = load_report(FIXTURE_RUN_DIR / "final-report.json")
    first = render(report)
    second = render(report)
    assert first == second


# -- Pure functions --------------------------------------------------------


def test_emoji_mapping_for_all_persona_prefixes():
    cases = [
        ("lead-senior-architect", "🏗️"),
        ("lead-project-manager", "📋"),
        ("team-security-reviewer", "🛡️"),
        ("team-frontend-reviewer", "🎨"),
        ("team-backend-reviewer", "⚙️"),
        ("team-database-reviewer", "🗄️"),
        ("team-network-reviewer", "🌐"),
        ("team-devops-infra-reviewer", "🚀"),
        ("team-performance-reviewer", "⚡"),
        ("team-accessibility-reviewer", "♿"),
        ("team-observability-reviewer", "📊"),
        ("team-privacy-compliance-reviewer", "🔒"),
        ("team-data-ml-reviewer", "🤖"),
        ("peer-python-reviewer", "👨‍💻"),
        ("peer-quality-engineer", "👨‍💻"),
        ("team-fictional-reviewer", "🏢"),
    ]
    for persona, expected in cases:
        assert emoji_for(persona) == expected, f"persona={persona}"


def test_emoji_unknown_persona_is_empty():
    assert emoji_for("aggregator") == ""
    assert emoji_for("profiler") == ""


def test_blockquote_single_paragraph():
    assert blockquote("hello world") == "> hello world"


def test_blockquote_multi_paragraph():
    text = "first paragraph.\n\nsecond paragraph."
    assert blockquote(text) == "> first paragraph.\n>\n> second paragraph."


def test_blockquote_preserves_internal_newlines():
    text = "line one\nline two"
    assert blockquote(text) == "> line one\n> line two"


def test_line_range_for_single_line():
    assert line_range_for({"line_start": 42}) == "42"


def test_line_range_for_explicit_range():
    assert line_range_for({"line_start": 10, "line_end": 25}) == "10-25"


def test_line_range_collapses_same_start_and_end():
    assert line_range_for({"line_start": 5, "line_end": 5}) == "5"


def test_title_from_extracts_slug():
    report = {"review_id": "2026-05-12-1513-pytorch-trainer"}
    assert title_from(report) == "pytorch-trainer"


def test_title_from_falls_back_to_description():
    report = {
        "review_id": "ad-hoc-no-timestamp",
        "casting_roster": {"review_scope": {"description": "scoped review"}},
    }
    assert title_from(report) == "scoped review"


def test_title_from_falls_back_to_review_id_when_nothing_else():
    report = {"review_id": "no-timestamp", "casting_roster": {}}
    assert title_from(report) == "no-timestamp"


# -- Build context handles enriched data ----------------------------------


def test_build_context_assembles_committee_lists():
    report = load_report(FIXTURE_RUN_DIR / "final-report.json")
    ctx = build_context(report)
    assert ctx["committee_stage_1"] == (
        "peer-python-reviewer, peer-quality-engineer, peer-readability-engineer"
    )
    assert ctx["committee_stage_2"] == (
        "team-security-reviewer, team-data-ml-reviewer, team-performance-reviewer"
    )
    assert ctx["committee_stage_3"] == (
        "lead-senior-architect, lead-project-manager"
    )


def test_build_context_score_label_is_one_decimal():
    report = load_report(FIXTURE_RUN_DIR / "final-report.json")
    ctx = build_context(report)
    assert ctx["final_score_label"] == "3.0"


def test_build_context_verdict_label_uppercases_with_spaces():
    report = load_report(FIXTURE_RUN_DIR / "final-report.json")
    ctx = build_context(report)
    assert ctx["verdict_label"] == "BLOCKED"


# -- Failure modes ---------------------------------------------------------


def test_render_raises_on_missing_required_field(tmp_path):
    """StrictUndefined must catch missing top-level fields."""
    minimal_template = tmp_path / "broken.tpl"
    minimal_template.write_text("Plugin: v{{ does_not_exist_in_context }}\n")
    report = load_report(FIXTURE_RUN_DIR / "final-report.json")
    with pytest.raises(Exception):
        render(report, minimal_template)


def test_load_report_enriches_summary_only_stage_reports(tmp_path):
    """
    When the Aggregator drifted and saved stripped-down stage_reports,
    load_report() restores per-persona findings from sibling stage_<N>/
    files.
    """
    # The v0.1.0 fixture is the canonical example of this drift case.
    report = load_report(FIXTURE_RUN_DIR / "final-report.json")
    for stage_n in (1, 2, 3):
        for entry in report["stage_reports"][f"stage_{stage_n}"]:
            assert "findings" in entry, (
                f"stage_{stage_n} entry {entry.get('persona')} not enriched"
            )
            assert "summary_quote" in entry


def test_load_report_passes_through_full_stage_reports(tmp_path):
    """
    When the Aggregator already emitted full PersonaFinding objects in
    stage_reports, load_report() leaves them as-is.
    """
    # Build a synthetic final-report.json with full stage_reports already inline,
    # and no per-stage sibling dir to enrich from.
    base = json.loads((FIXTURE_RUN_DIR / "final-report.json").read_text())
    full = json.loads(
        (FIXTURE_RUN_DIR / "stage_1" / "peer-python-reviewer.json").read_text()
    )
    base["stage_reports"]["stage_1"] = [full]
    base["stage_reports"]["stage_2"] = []
    base["stage_reports"]["stage_3"] = []

    p = tmp_path / "final-report.json"
    p.write_text(json.dumps(base))
    report = load_report(p, run_dir=tmp_path)
    assert report["stage_reports"]["stage_1"][0]["summary_quote"].startswith(
        "Production-like"
    )
