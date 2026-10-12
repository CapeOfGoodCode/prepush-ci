"""`prepush-ci install`: native hooks through core.hooksPath, run by real git."""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "Prepush-CI: full"


def install(
    repo: Path, *, python: str | None = None, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci install` in `repo` with `python` (default: this interpreter)."""
    return subprocess.run(
        [python or sys.executable, "-m", "prepush_ci", "install"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


def hooks_dir(repo: Path) -> Path:
    return repo / ".git" / "prepush-ci" / "hooks"


@pytest.fixture
def ran(tmp_path: Path) -> Path:
    """The file the config's check appends to."""
    return tmp_path / "ran.log"


@pytest.fixture
def pushing(repo: Path, tmp_path: Path, git: Git, ran: Path) -> Path:
    """`repo` on `main` with one commit, a config whose check logs to `ran`, a bare `origin` and
    no hook installed: specs call `install` themselves."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()}"\nrequire_up_to_date = false\n'
    )
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return repo


def commit_with_trailer(repo: Path, git: Git, name: str = "x") -> str:
    (repo / f"{name}.txt").write_text(name)
    git(repo, "add", f"{name}.txt")
    git(repo, "commit", "-q", "-m", f"add {name}", env={"PREPUSH_CI": "full"})
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def remote_has(repo: Path, git: Git, sha: str) -> bool:
    return git(repo, "ls-remote", "origin", "refs/heads/main").stdout.startswith(sha)


def test_a_commit_after_install_gets_the_trailer(pushing: Path, git: Git) -> None:
    assert install(pushing).returncode == 0

    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")
    git(pushing, "commit", "-q", "-m", "add x", env={"PREPUSH_CI": "full"})

    message = git(pushing, "log", "-1", "--format=%B").stdout
    assert message.strip().endswith(TRAILER)


def test_a_push_after_install_runs_the_check_and_reaches_the_remote(
    pushing: Path, git: Git, ran: Path
) -> None:
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    git(pushing, "push", "-q", "origin", "main")

    assert ran.read_text().split() == ["ran"]  # cmd keeps the space before >>
    assert remote_has(pushing, git, sha)


def test_install_leaves_the_worktree_clean(pushing: Path, git: Git) -> None:
    install(pushing)

    assert git(pushing, "status", "--porcelain").stdout == ""


def test_install_points_core_hooks_path_at_its_own_directory(
    pushing: Path, git: Git
) -> None:
    install(pushing)

    configured = git(pushing, "config", "--local", "core.hooksPath").stdout.strip()
    assert Path(configured) == hooks_dir(pushing).resolve()
    assert os.access(hooks_dir(pushing) / "commit-msg", os.X_OK)
    assert os.access(hooks_dir(pushing) / "pre-push", os.X_OK)


def test_the_hooks_start_the_tool_without_prepush_ci_on_path(
    pushing: Path, git: Git
) -> None:
    scripts = str(Path(sys.executable).parent)
    path = os.pathsep.join(
        p for p in os.environ["PATH"].split(os.pathsep) if p != scripts
    )
    assert shutil.which("prepush-ci", path=path) is None
    install(pushing)

    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")
    git(
        pushing,
        "commit",
        "-q",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full", "PATH": path},
    )

    assert git(pushing, "log", "-1", "--format=%B").stdout.strip().endswith(TRAILER)
