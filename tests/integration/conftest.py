import os
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]


@pytest.fixture
def git() -> Git:
    """Run real git in a directory; a failing command fails the test unless `check=False`.

    `PREPUSH_CI` and `PRE_COMMIT_*` are dropped from the inherited environment so a developer's
    own opt-in, or the pre-commit run that started the suite as a pre-push hook, never leaks
    into a spec; pass them through `env` when a spec needs them.
    """

    def run(
        repo: Path,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> "subprocess.CompletedProcess[str]":
        inherited = {
            k: v
            for k, v in os.environ.items()
            if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
        }
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=check,
            env={**inherited, **(env or {})},
        )

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


@pytest.fixture
def hooked_repo(repo: Path) -> Path:
    """`repo` with a valid config and the commit-msg hook installed the way git runs it."""
    (repo / ".prepush-ci.toml").write_text('check = "true"\n')
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook commit-msg "$1"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    return repo


@pytest.fixture
def pushing_repo(repo: Path, tmp_path: Path, git: Git) -> Path:
    """`repo` on `main` with one commit, a config whose check logs to `ran.log`, a bare `origin`
    and the pre-push hook installed the way git runs it."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    ran = tmp_path / "ran.log"
    (repo / ".prepush-ci.toml").write_text(f'check = "echo ran >> {ran.as_posix()}"\n')
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return repo
