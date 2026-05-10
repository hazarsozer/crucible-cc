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
