"""E2E sanity tests for the Crucible plugin.

These tests do NOT invoke real subagents (which require an API key and
several minutes to run). They verify structural integrity:
  - Every persona referenced in the orchestrator skill exists
  - Every fixture has an aims file with the expected sections
  - Templates parse cleanly with no leftover unfilled-marker text
  - Example reports exist and have minimum structure

The live E2E test (test_crucible_runs_on_nextjs_fixture) IS gated by
RUN_LIVE_E2E=1 and shells out to the `claude` CLI. Use only before
release. Run cost is ~$1-2 per fixture.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


def test_orchestrator_references_only_existing_personas(
    repo_root: Path, agents_dir: Path
) -> None:
    """Every subagent_type the orchestrator dispatches must exist as agents/<name>.md."""
    skill_text = (repo_root / "skills" / "crucible" / "SKILL.md").read_text()
    referenced = set(re.findall(r'subagent_type=(?:"|f")?([a-z0-9-]+)"', skill_text))
    referenced |= set(
        re.findall(r"subagent_type=cast_entry\.persona", skill_text) and []
    )
    # The orchestrator dispatches via cast_entry.persona at runtime — we can't
    # statically resolve every dispatch. But it MUST reference profiler and
    # aggregator as literal strings.
    expected_minimum = {"profiler", "aggregator"}
    assert expected_minimum.issubset(
        referenced
    ), f"orchestrator missing references to bookend agents; found {referenced}"

    available = {f.stem for f in agents_dir.glob("*.md")}
    missing = referenced - available
    assert not missing, f"orchestrator references nonexistent agents: {missing}"


def test_every_fixture_has_aims_file(fixtures_dir: Path) -> None:
    fixtures = [
        d for d in fixtures_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]
    assert fixtures, f"no fixtures found under {fixtures_dir}"
    for fixture in fixtures:
        aims = fixture / ".review" / "aims.md"
        assert aims.exists(), f"fixture {fixture.name} missing .review/aims.md"
        content = aims.read_text()
        assert "# Project Aims" in content, f"{aims} missing '# Project Aims' header"
        assert "## Goal" in content, f"{aims} missing '## Goal' section"
        assert "## Project type" in content, f"{aims} missing '## Project type' section"


def test_templates_have_no_unfilled_marker_in_static_parts(repo_root: Path) -> None:
    """Templates use {{...}} for runtime fill, but static prose shouldn't have stray markers."""
    for tpl in (repo_root / "templates").glob("*"):
        text = tpl.read_text()
        # Avoid matching the literal strings as substrings inside this test file's prose
        # by searching for them as standalone tokens.
        forbidden = ["T" + "ODO", "T" + "BD", "FIX" + "ME", "XXX" + "X"]
        for marker in forbidden:
            assert marker not in text, f"{tpl.name} contains unresolved marker: {marker}"


def test_examples_directory_present_with_three_reports(repo_root: Path) -> None:
    examples = list((repo_root / "examples").glob("*.md"))
    assert (
        len(examples) >= 3
    ), f"expected 3 example reports under examples/, found {len(examples)}"


def test_orchestrator_skill_has_valid_frontmatter(repo_root: Path) -> None:
    """The /crucible skill must have the required frontmatter shape."""
    skill = repo_root / "skills" / "crucible" / "SKILL.md"
    text = skill.read_text()
    assert text.startswith("---\n"), "skill must start with YAML frontmatter"
    end_marker = text.find("\n---\n", 4)
    assert end_marker > 0, "skill frontmatter is not properly closed"
    fm = text[4:end_marker]
    assert "name: crucible" in fm
    assert "description:" in fm


def test_aux_skills_have_valid_frontmatter(repo_root: Path) -> None:
    for skill_dir in ("crucible-aims-edit", "crucible-history"):
        skill = repo_root / "skills" / skill_dir / "SKILL.md"
        assert skill.exists(), f"missing {skill}"
        text = skill.read_text()
        assert text.startswith("---\n"), f"{skill} must start with YAML frontmatter"
        end_marker = text.find("\n---\n", 4)
        assert end_marker > 0, f"{skill} frontmatter not closed"


def test_plugin_manifest_is_well_formed(repo_root: Path) -> None:
    """Plugin manifest must be valid JSON with the required fields."""
    import json

    manifest_path = repo_root / ".claude-plugin" / "plugin.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["name"] == "crucible"
    assert "description" in manifest
    assert re.match(
        r"^\d+\.\d+\.\d+", manifest["version"]
    ), "version must be semver-like"


# ─────────────────────────────────────────────────────────────────────────────
# Live E2E (gated by RUN_LIVE_E2E=1)
# ─────────────────────────────────────────────────────────────────────────────


RUN_LIVE_E2E = os.environ.get("RUN_LIVE_E2E") == "1"


@pytest.mark.skipif(
    not RUN_LIVE_E2E, reason="live E2E disabled (set RUN_LIVE_E2E=1 to enable)"
)
def test_crucible_runs_on_nextjs_fixture(fixtures_dir: Path) -> None:
    """Run /crucible on the nextjs-auth fixture and assert the report has the right shape.

    Requires:
      - `claude` CLI on PATH
      - This plugin installed locally
      - ANTHROPIC_API_KEY in env
      - ~5 minutes per fixture
      - ~$1-2 per fixture run

    Content is stochastic; this test only checks structural invariants.
    """
    fixture = fixtures_dir / "nextjs-auth"
    result = subprocess.run(
        [
            "claude",
            "--cwd",
            str(fixture),
            "--non-interactive",
            "/crucible",
        ],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, f"crucible failed: {result.stderr}"

    reports = list((fixture / ".review" / "reports").glob("*.md"))
    assert reports, "no report generated"
    # Pick the most recent
    report = max(reports, key=lambda p: p.stat().st_mtime).read_text()

    # Structural assertions — content is stochastic, sections must exist.
    assert "# Crucible Review" in report
    assert "## Final Verdict" in report
    assert "## Executive Summary" in report
    assert "## Stage 1 — Peer Review" in report
    assert "## Stage 2 — Cross-functional" in report
    assert "## Stage 3 — Leadership" in report
    assert "## Aims Snapshot" in report
    assert "## Run Metadata" in report
