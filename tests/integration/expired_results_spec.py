"""Result refs older than 30 days are deleted when a pass is recorded, and their date is the day of
the pass.

Real `git push` to bare repositories; the config is an ignored file, so a spec can change it
without dirtying the worktree.
"""

import os
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
DAY = 24 * 60 * 60
RESULTS = "refs/prepush-ci/results"


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "ran.log"


def write_config(repo: Path, log: Path, *lines: str, check: str | None = None) -> None:
    body = [
        f"check = '{check or f'echo ran >> {log.as_posix()}'}'",
        "require_up_to_date = false",
        *lines,
    ]
    (repo / ".prepush-ci.toml").write_text("\n".join(body) + "\n")


def install_hook(repo: Path, *, before: str = "") -> None:
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        f"{before}"
        f'exec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def local(repo: Path, git: Git, log: Path) -> Path:
    """`repo` on `main` with a commit that carries the trailer, an ignored config whose check logs
    to `log` and the pre-push hook; it has no remote."""
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".git" / "info" / "exclude").write_text(".prepush-ci.toml\n")
    write_config(repo, log)
    install_hook(repo)
    git(repo, "commit", "--allow-empty", "-q", "-m", "init")
    git(repo, "commit", "--allow-empty", "-q", "-m", "work" + TRAILER)
    return repo


@pytest.fixture
def pushing(local: Path, tmp_path: Path, git: Git) -> Path:
    """`local` with a bare `origin`."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(tmp_path / "remote.git", "symbolic-ref", "HEAD", "refs/heads/main")
    git(local, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return local


def run_cli(
    repo: Path, *, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "run"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**inherited, **(env or {})},
    )


def ago(days: int) -> str:
    """A git date `days` days back."""
    return f"{int(time.time()) - days * DAY} +0000"


def results(repo: Path, git: Git) -> list[str]:
    listing = git(repo, "for-each-ref", "--format=%(refname)", RESULTS)
    return listing.stdout.split()


def dates_of(repo: Path, git: Git, ref: str) -> tuple[int, int]:
    """The author and the committer time of the commit a ref points at."""
    shown = git(repo, "log", "-1", "--format=%at %ct", ref).stdout.split()
    return int(shown[0]), int(shown[1])


def is_recent(seconds: int) -> bool:
    return abs(time.time() - seconds) < 60


# --- A recorded pass is dated when it is recorded ------------------------------------------------


def test_a_date_in_the_environment_does_not_date_the_pass(
    local: Path, git: Git
) -> None:
    old = ago(31)

    run_cli(local, env={"GIT_COMMITTER_DATE": old, "GIT_AUTHOR_DATE": old})

    [ref] = results(local, git)
    assert all(is_recent(seconds) for seconds in dates_of(local, git, ref))


def test_a_pass_under_old_dates_survives_in_a_push_to_origin(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    old = ago(31)

    result = git(
        pushing,
        "push",
        "origin",
        "main",
        env={"GIT_COMMITTER_DATE": old, "GIT_AUTHOR_DATE": old},
        check=False,
    )

    assert result.returncode == 0
    for repo in (pushing, tmp_path / "remote.git"):
        [ref] = results(repo, git)
        assert all(is_recent(seconds) for seconds in dates_of(repo, git, ref))
