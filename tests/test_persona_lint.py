"""Tests for scripts/lint_personas.py."""
import sys
from pathlib import Path

import pytest


# Make `scripts` importable as a top-level package.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lint_personas import lint_persona_file, LintError  # noqa: E402


def test_valid_persona_file_passes(tmp_path: Path) -> None:
    f = tmp_path / "peer-test-reviewer.md"
    f.write_text("""---
name: peer-test-reviewer
description: A test persona
stage: 1
model: claude-haiku-4-5-20251001
casting_trigger: always
---

# Identity

Test content.
""")
    lint_persona_file(f)


def test_missing_frontmatter_fails(tmp_path: Path) -> None:
    f = tmp_path / "peer-bad.md"
    f.write_text("# No frontmatter here")
    with pytest.raises(LintError, match="frontmatter"):
        lint_persona_file(f)


def test_missing_required_field_fails(tmp_path: Path) -> None:
    f = tmp_path / "peer-missing-stage.md"
    f.write_text("""---
name: peer-missing-stage
description: Missing stage field
model: claude-haiku-4-5-20251001
casting_trigger: always
---
""")
    with pytest.raises(LintError, match="stage"):
        lint_persona_file(f)


def test_invalid_stage_value_fails(tmp_path: Path) -> None:
    f = tmp_path / "peer-bad-stage.md"
    f.write_text("""---
name: peer-bad-stage
description: Stage out of range
stage: 99
model: claude-haiku-4-5-20251001
casting_trigger: always
---
""")
    with pytest.raises(LintError, match="stage"):
        lint_persona_file(f)


def test_invalid_model_fails(tmp_path: Path) -> None:
    f = tmp_path / "peer-bad-model.md"
    f.write_text("""---
name: peer-bad-model
description: Unknown model
stage: 1
model: gpt-4
casting_trigger: always
---
""")
    with pytest.raises(LintError, match="model"):
        lint_persona_file(f)


def test_stage_zero_valid_for_profiler(tmp_path: Path) -> None:
    f = tmp_path / "profiler.md"
    f.write_text("""---
name: profiler
description: bookend
stage: 0
model: claude-sonnet-4-6
casting_trigger: always
---
""")
    lint_persona_file(f)


def test_all_shipped_personas_pass_lint(repo_root: Path) -> None:
    """Every persona in agents/ must pass lint."""
    agents_dir = repo_root / "agents"
    persona_files = sorted(agents_dir.glob("*.md"))
    assert persona_files, "no persona files found in agents/"
    for f in persona_files:
        # Will raise LintError on failure
        lint_persona_file(f)


def test_persona_library_completeness(repo_root: Path) -> None:
    """The library ships every persona referenced in the implementation plan."""
    agents_dir = repo_root / "agents"
    available = {f.stem for f in agents_dir.glob("*.md")}

    expected = {
        # Bookends
        "profiler",
        "aggregator",
        # Stage 1 — peers
        "peer-python-reviewer",
        "peer-typescript-reviewer",
        "peer-go-reviewer",
        "peer-rust-reviewer",
        "peer-java-kotlin-reviewer",
        "peer-c-cpp-reviewer",
        "peer-swift-reviewer",
        "peer-sql-reviewer",
        "peer-quality-engineer",
        "peer-readability-engineer",
        # Stage 2 — teams
        "team-security-reviewer",
        "team-frontend-reviewer",
        "team-backend-reviewer",
        "team-network-reviewer",
        "team-database-reviewer",
        "team-devops-infra-reviewer",
        "team-performance-reviewer",
        "team-accessibility-reviewer",
        "team-observability-reviewer",
        "team-privacy-compliance-reviewer",
        "team-data-ml-reviewer",
        # Stage 3 — leadership
        "lead-senior-architect",
        "lead-project-manager",
    }

    missing = expected - available
    assert not missing, f"persona library missing: {sorted(missing)}"
