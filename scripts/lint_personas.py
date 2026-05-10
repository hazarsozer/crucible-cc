"""Validate Crucible persona file frontmatter.

Usage:
    uv run python scripts/lint_personas.py agents/peer-python-reviewer.md
    uv run python scripts/lint_personas.py agents/*.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


VALID_MODELS = frozenset({
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
})

# Stage 0 is reserved for profiler/aggregator (pipeline bookends).
VALID_STAGES = frozenset({0, 1, 2, 3})

REQUIRED_FIELDS = ("name", "description", "stage", "model", "casting_trigger")

NAME_PATTERN = re.compile(r"^(profiler|aggregator|peer-|team-|lead-)[a-z0-9-]*$")

FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(?P<body>.*?)\n---\s*\n",
    re.DOTALL,
)


class LintError(ValueError):
    """Raised when a persona file fails lint."""


def _parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        raise LintError("missing or malformed frontmatter (expected leading --- block)")
    try:
        data = yaml.safe_load(match.group("body"))
    except yaml.YAMLError as e:
        raise LintError(f"frontmatter is not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise LintError("frontmatter must be a mapping")
    return data


def lint_persona_file(path: Path) -> None:
    text = path.read_text()
    data = _parse_frontmatter(text)

    for field in REQUIRED_FIELDS:
        if field not in data:
            raise LintError(f"missing required field: {field}")

    name = data["name"]
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        raise LintError(
            f"invalid name {name!r}: must start with profiler|aggregator|peer-|team-|lead-"
        )

    if name != path.stem:
        raise LintError(f"name {name!r} does not match filename stem {path.stem!r}")

    stage = data["stage"]
    if stage not in VALID_STAGES:
        raise LintError(f"invalid stage {stage!r}: must be 0, 1, 2, or 3")

    model = data["model"]
    if model not in VALID_MODELS:
        raise LintError(
            f"invalid model {model!r}: must be one of {sorted(VALID_MODELS)}"
        )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: lint_personas.py <persona.md> [<persona.md> ...]", file=sys.stderr)
        return 2

    failed = 0
    for arg in argv[1:]:
        path = Path(arg)
        try:
            lint_persona_file(path)
        except LintError as e:
            print(f"✗ {path}: {e}", file=sys.stderr)
            failed += 1
        except OSError as e:
            print(f"✗ {path}: {e}", file=sys.stderr)
            failed += 1
        else:
            print(f"✓ {path}: ok")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
