import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., str]


@pytest.fixture
def git() -> Git:
    """Run real git in a directory and return its stdout; a failing command fails the test."""

    def run(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, **(env or {})},
        )
        return result.stdout

    return run


@pytest.fixture
def repo(tmp_path: Path, git: Git) -> Path:
    """An empty git repository with an identity, in a temporary directory."""
    path = tmp_path / "work"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "commit.gpgsign", "false")
    return path
