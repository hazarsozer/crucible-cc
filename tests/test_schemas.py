"""Validate that schema examples conform to their schemas."""
import json
from pathlib import Path

import jsonschema
import pytest


SCHEMA_FILES = [
    "persona-finding.schema.json",
    "casting-roster.schema.json",
    "final-report.schema.json",
]


@pytest.mark.parametrize("schema_file", SCHEMA_FILES)
def test_schema_is_valid_jsonschema(schemas_dir: Path, schema_file: str) -> None:
    schema_path = schemas_dir / schema_file
    schema = json.loads(schema_path.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)


def test_persona_finding_example_validates(schemas_dir: Path) -> None:
    schema = json.loads((schemas_dir / "persona-finding.schema.json").read_text())
    example = {
        "persona": "team-security-reviewer",
        "stage": 2,
        "model_used": "claude-sonnet-4-6",
        "started_at": "2026-05-10T14:33:12Z",
        "completed_at": "2026-05-10T14:34:05Z",
        "scope_assessed": ["app/auth/login.ts"],
        "verdict": "concerns",
        "score": 6,
        "summary_quote": "Move session storage to httpOnly cookies before merge.",
        "findings": [
            {
                "severity": "high",
                "category": "security",
                "title": "Session token stored in localStorage",
                "location": "app/auth/session.ts:42",
                "explanation": "localStorage is accessible to any JS on the page including injection payloads.",
                "suggestion": "Use httpOnly Secure SameSite=Lax cookies."
            }
        ],
        "stage_handoff_notes": "Architect should weigh in on session storage strategy."
    }
    jsonschema.validate(example, schema)
