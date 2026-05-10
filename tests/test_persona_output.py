"""Validate that persona outputs (if any exist on disk) conform to the schema.

This test does NOT invoke any LLM. It scans test fixture directories for any
persona-finding JSON files (typically saved during a prior live E2E run) and
verifies they conform to schemas/persona-finding.schema.json.

If no fixture outputs exist, the test is skipped — typical for clean checkouts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import jsonschema
import pytest


def _find_fixture_outputs(fixtures_dir: Path) -> Iterable[Path]:
    """Yield every persona-finding JSON file under any fixture's .review/runs/."""
    for fixture in fixtures_dir.iterdir():
        if not fixture.is_dir():
            continue
        runs = fixture / ".review" / "runs"
        if not runs.exists():
            continue
        for run_dir in runs.iterdir():
            for stage_dir in run_dir.glob("stage_*"):
                for finding_file in stage_dir.glob("*.json"):
                    yield finding_file


def test_all_persona_outputs_validate(
    fixtures_dir: Path, schemas_dir: Path
) -> None:
    schema = json.loads((schemas_dir / "persona-finding.schema.json").read_text())
    outputs = list(_find_fixture_outputs(fixtures_dir))
    if not outputs:
        pytest.skip("no fixture outputs to validate (run live E2E first)")
    failures: list[str] = []
    for output_file in outputs:
        try:
            data = json.loads(output_file.read_text())
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            failures.append(f"{output_file}: {e.message}")
        except json.JSONDecodeError as e:
            failures.append(f"{output_file}: invalid JSON ({e})")
    assert not failures, "\n".join(failures)
