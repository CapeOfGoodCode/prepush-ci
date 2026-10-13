"""The pre-push hook run by a real pre-commit, which hands it variables instead of git's input."""

import os
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"


@pytest.fixture
def pre_commit_env(
    tmp_path: Path, pre_commit_locale: Callable[..., dict[str, str]]
) -> dict[str, str]:
    """Keeps pre-commit's cache out of the developer's home, and gives its processes the three
    variables of a hostile variant as they were before it: pre-commit itself does not run under an
    ASCII locale in a non-ASCII directory. The tool its hook starts is held by the other specs."""
    return pre_commit_locale({"PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home")})


@pytest.fixture
def pre_commit_repo(
    pushing_repo: Path, tmp_path: Path, git: Git, pre_commit_env: dict[str, str]
) -> Path:
    """`pushing_repo` whose pre-push hook is installed by pre-commit instead of by hand."""
    (pushing_repo / ".git" / "hooks" / "pre-push").unlink()
    wrapper = tmp_path / "hook.sh"
    wrapper.write_text(
        f'#!/bin/sh\necho started >> "{tmp_path.as_posix()}/started.log"\n'
        f'exec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    (pushing_repo / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: prepush-ci\n"
        "        name: prepush-ci\n"
        f"        entry: sh {wrapper.as_posix()}\n"
        "        language: system\n"
        "        always_run: true\n"
        "        pass_filenames: false\n"
        "        stages: [pre-push]\n"
    )
    git(pushing_repo, "add", ".pre-commit-config.yaml")
    git(pushing_repo, "commit", "-q", "-m", "configure pre-commit")
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-push"],
        cwd=pushing_repo,
        env={
            **{k: v for k, v in os.environ.items() if not k.startswith("PRE_COMMIT_")},
            **pre_commit_env,
        },
        capture_output=True,
        text=True,
        check=True,
    )
    return pushing_repo


def started(repo: Path) -> int:
    log = repo.parent / "started.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def ran(repo: Path) -> int:
    log = repo.parent / "ran.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def push(
    repo: Path, git: Git, env: dict[str, str], *refs: str
) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", "origin", *refs, env=env, check=False)


def test_pre_commit_runs_the_check_on_a_pushed_commit_with_the_trailer(
    pre_commit_repo: Path, git: Git, pre_commit_env: dict[str, str]
) -> None:
    git(pre_commit_repo, "commit", "--allow-empty", "-q", "-m", "work" + TRAILER)

    result = push(pre_commit_repo, git, pre_commit_env, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pre_commit_repo) == 1


def test_pre_commit_refuses_a_trailer_commit_when_the_worktree_is_dirty(
    pre_commit_repo: Path, git: Git, pre_commit_env: dict[str, str]
) -> None:
    git(pre_commit_repo, "commit", "--allow-empty", "-q", "-m", "work" + TRAILER)
    (pre_commit_repo / "scratch.txt").write_text("x\n")

    result = push(pre_commit_repo, git, pre_commit_env, "main")

    assert result.returncode != 0
    assert "scratch.txt" in result.stdout + result.stderr
    assert ran(pre_commit_repo) == 0


def test_pre_commit_pushing_a_root_commit_runs_the_check_on_the_local_branch(
    pre_commit_repo: Path, git: Git, pre_commit_env: dict[str, str]
) -> None:
    git(pre_commit_repo, "checkout", "-q", "--orphan", "root")
    git(pre_commit_repo, "commit", "--allow-empty", "-q", "-m", "first" + TRAILER)

    result = push(pre_commit_repo, git, pre_commit_env, "root")

    assert result.returncode == 0, result.stderr
    assert ran(pre_commit_repo) == 1


def test_known_limit_pre_commit_gives_the_hook_one_of_two_pushed_refs(
    pre_commit_repo: Path, git: Git, pre_commit_env: dict[str, str]
) -> None:
    git(pre_commit_repo, "checkout", "-q", "-b", "b", "main")
    git(pre_commit_repo, "commit", "--allow-empty", "-q", "-m", "b" + TRAILER)
    git(pre_commit_repo, "checkout", "-q", "main")
    git(pre_commit_repo, "commit", "--allow-empty", "-q", "-m", "main" + TRAILER)

    result = push(pre_commit_repo, git, pre_commit_env, "main", "b")

    assert result.returncode == 0, result.stderr
    assert started(pre_commit_repo) == 1
    assert ran(pre_commit_repo) == 1  # main was checked; b, not HEAD, was not seen
    remote = pre_commit_repo.parent / "remote.git"
    assert git(remote, "rev-parse", "--verify", "-q", "refs/heads/b").returncode == 0


def test_known_limit_pre_commit_does_not_run_the_hook_for_commits_the_remote_has(
    pre_commit_repo: Path, git: Git, pre_commit_env: dict[str, str]
) -> None:
    git(pre_commit_repo, "commit", "--allow-empty", "-q", "-m", "work")
    assert push(pre_commit_repo, git, pre_commit_env, "main").returncode == 0
    before = started(pre_commit_repo)
    git(pre_commit_repo, "branch", "copy")

    result = push(pre_commit_repo, git, pre_commit_env, "copy")

    assert result.returncode == 0, result.stderr
    assert started(pre_commit_repo) == before
