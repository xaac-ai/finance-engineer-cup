import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_copy(tmp_path) -> Path:
    """An isolated copy of the repo's data/ so tests can mutate inputs and write outputs."""
    shutil.copytree(REPO / "data", tmp_path / "data")
    return tmp_path
