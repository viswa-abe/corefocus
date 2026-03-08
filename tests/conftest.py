"""Shared fixtures for corefocus tests."""

import pytest
from pathlib import Path
from corefocus.store import LoopStore


@pytest.fixture
def store(tmp_path: Path) -> LoopStore:
    """A LoopStore backed by a temporary directory."""
    s = LoopStore(base=tmp_path)
    s.ensure_dirs()
    return s
