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


def test_casting_roster_example_validates(schemas_dir: Path) -> None:
    schema = json.loads((schemas_dir / "casting-roster.schema.json").read_text())
    example = {
        "review_id": "2026-05-10-1430-auth-refactor",
        "started_at": "2026-05-10T14:30:00Z",
        "project_profile": {
            "type": "web-app",
            "languages": ["typescript", "sql"],
            "frameworks": ["nextjs", "prisma"],
            "datastores": ["postgres"]
        },
        "review_scope": {
            "kind": "phase",
            "description": "auth module rewrite",
            "files": ["app/auth/**", "prisma/migrations/2026*.sql"],
            "diff_source": "branch:auth-rewrite vs main"
        },
        "aims_snapshot_path": ".review/aims.md",
        "casting": {
            "stage_1": [
                {"persona": "peer-typescript-reviewer", "files": ["app/auth/*.ts"]}
            ],
            "stage_2": [
                {"persona": "team-security-reviewer", "files": ["app/auth/**"]}
            ],
            "stage_3": [
                {"persona": "lead-senior-architect", "files": "all"},
                {"persona": "lead-project-manager", "files": "all"}
            ]
        },
        "casting_reasoning": "TypeScript-first project; security-sensitive auth."
    }
    jsonschema.validate(example, schema)


def test_final_report_example_validates(schemas_dir: Path) -> None:
    schema = json.loads((schemas_dir / "final-report.schema.json").read_text())
    example = {
        "review_id": "2026-05-10-1430-auth-refactor",
        "completed_at": "2026-05-10T14:38:22Z",
        "final_score": 7.1,
        "final_verdict": "conditional_approval",
        "verdict_reasoning": "Strong technical execution; one high-severity security gap blocks 'production-ready' status.",
        "executive_summary": "The auth module rewrite is structurally sound, with clean SQL migrations and good API contract design. Two areas demand attention before merge: session storage strategy and rate limiting on the login route.",
        "what_is_good": ["SQL migrations are clean and reversible"],
        "what_is_concerning": ["Session tokens in localStorage"],
        "key_quotes": [
            {"persona": "team-security-reviewer", "quote": "Move session storage to httpOnly cookies before merge."}
        ],
        "stage_reports": {"stage_1": [], "stage_2": [], "stage_3": []},
        "aims_snapshot": "# Project Aims\n...",
        "casting_roster": {},
        "metadata": {
            "plugin_version": "0.1.0",
            "wall_clock_seconds": 312,
            "models_used": ["sonnet-4-6", "haiku-4-5", "opus-4-7"],
            "estimated_cost_usd": 0.74
        }
    }
    jsonschema.validate(example, schema)
