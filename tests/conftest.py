"""Shared pytest fixtures for Crucible tests."""
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the plugin repo root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def schemas_dir(repo_root: Path) -> Path:
    return repo_root / "schemas"


@pytest.fixture(scope="session")
def agents_dir(repo_root: Path) -> Path:
    return repo_root / "agents"


@pytest.fixture(scope="session")
def fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures"
