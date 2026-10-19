"""The up-to-date step with a damaged ref under `refs/prepush-ci`: the fetch goes on, `run` and the
pre-push hook behave as the result cache says, and git does no housekeeping meanwhile."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "ran.log"


def runs(log: Path) -> int:
    return len(log.read_text().splitlines()) if log.exists() else 0


@pytest.fixture
def damaged(pushing_repo: Path, git: Git, log: Path) -> Path:
    """`pushing_repo` whose remote holds `main`, with a config that keeps the default up-to-date
    step (`origin/main`) and a tip with the trailer on top."""
    git(pushing_repo, "commit", "--allow-empty", "-q", "-m", "first")
    assert git(pushing_repo, "push", "origin", "main", check=False).returncode == 0
    (pushing_repo / ".prepush-ci.toml").write_text(
        f'check = "echo check >> {log.as_posix()}"\n'
    )
    git(pushing_repo, "add", ".prepush-ci.toml")
    git(pushing_repo, "commit", "-q", "-m", "configure")
    git(pushing_repo, "commit", "--allow-empty", "-q", "-m", "work" + TRAILER)
    return pushing_repo


def push(repo: Path, git: Git, *words: str) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", *(words or ("origin", "main")), check=False)


def run_cli(repo: Path) -> "subprocess.CompletedProcess[str]":
    env = {
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
        env=env,
    )


def make_the_cache_path_a_file(repo: Path) -> None:
    (repo / ".git" / "refs" / "prepush-ci").write_text("in the way")


def empty_the_result_ref(repo: Path, git: Git) -> None:
    [ref] = git(
        repo, "for-each-ref", "--format=%(refname)", "refs/prepush-ci/results"
    ).stdout.split()
    (repo / ".git" / ref).write_text("")


def refuse_a_ref_name(repo: Path) -> None:
    """A ref under the namespace whose name git refuses (`..`) but whose content is a commit."""
    broken = repo / ".git" / "refs" / "prepush-ci" / "results" / "bad..name"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text((repo / ".git" / "refs" / "heads" / "main").read_text())


def advance_remote_main(repo: Path, tmp_path: Path, git: Git) -> None:
    """Another clone pushes a commit to the remote `main` that `repo` does not contain."""
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(other))
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.com")
    git(other, "config", "commit.gpgsign", "false")
    git(other, "checkout", "-q", "main")
    git(other, "commit", "--allow-empty", "-q", "-m", "someone else's work")
    git(other, "push", "-q", "origin", "main")


def test_an_emptied_result_ref_does_not_stop_the_hook_and_the_check_runs(
    damaged: Path, git: Git, log: Path
) -> None:
    assert run_cli(damaged).returncode == 0
    empty_the_result_ref(damaged, git)

    result = push(damaged, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 2


def test_a_cache_path_that_is_a_file_does_not_stop_the_hook_and_warns(
    damaged: Path, git: Git, log: Path
) -> None:
    make_the_cache_path_a_file(damaged)

    result = push(damaged, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 1
    assert "could not be cached" in result.stderr


def test_a_cache_path_that_is_a_file_does_not_stop_run_and_warns(
    damaged: Path, log: Path
) -> None:
    make_the_cache_path_a_file(damaged)

    result = run_cli(damaged)

    assert result.returncode == 0, result.stderr
    assert "could not be cached" in result.stderr


def test_an_emptied_result_ref_does_not_stop_run(damaged: Path, git: Git) -> None:
    assert run_cli(damaged).returncode == 0
    empty_the_result_ref(damaged, git)

    result = run_cli(damaged)

    assert result.returncode == 0, result.stderr


def test_a_ref_with_a_refused_name_does_not_stop_the_hook(
    damaged: Path, git: Git, log: Path
) -> None:
    refuse_a_ref_name(damaged)

    result = push(damaged, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 1


def test_a_ref_with_a_refused_name_does_not_stop_run(damaged: Path, log: Path) -> None:
    refuse_a_ref_name(damaged)

    result = run_cli(damaged)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 1


def test_a_damaged_ref_does_not_hide_a_branch_that_is_not_up_to_date(
    damaged: Path, git: Git, tmp_path: Path
) -> None:
    make_the_cache_path_a_file(damaged)
    advance_remote_main(damaged, tmp_path, git)

    result = push(damaged, git, "origin", "main:topic")

    assert result.returncode != 0
    assert "origin/main" in result.stderr
    assert "rebase" in result.stderr
    assert "merge" in result.stderr


def test_a_damaged_ref_does_not_hide_an_unreachable_remote(
    damaged: Path, git: Git, tmp_path: Path
) -> None:
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "second.git"))
    git(damaged, "remote", "add", "second", str(tmp_path / "second.git"))
    git(damaged, "remote", "set-url", "origin", str(tmp_path / "nowhere"))
    make_the_cache_path_a_file(damaged)

    result = push(damaged, git, "second", "main")

    assert result.returncode != 0
    assert "could not fetch origin/main" in result.stderr


def test_a_broken_ref_that_holds_the_only_copy_of_a_commit_does_not_let_gc_prune_it(
    damaged: Path, git: Git
) -> None:
    # two packs, so that a fetch would start `gc --auto` if it may
    git(damaged, "repack", "-q", "-d")
    filler = git(damaged, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "filler")
    git(damaged, "update-ref", "refs/heads/filler", filler.stdout.strip())
    git(damaged, "repack", "-q", "-d")
    only = git(damaged, "commit-tree", "HEAD^{tree}", "-m", "only copy").stdout.strip()
    broken = damaged / ".git" / "refs" / "prepush-ci" / "results" / "bad..name"
    broken.parent.mkdir(parents=True)
    broken.write_text(only + "\n")
    for key, value in (
        ("gc.auto", "1"),
        ("gc.autoPackLimit", "1"),
        ("gc.autoDetach", "false"),
        ("gc.pruneExpire", "now"),
    ):
        git(damaged, "config", key, value)

    result = push(damaged, git)

    assert result.returncode == 0, result.stderr
    assert git(damaged, "cat-file", "-e", only, check=False).returncode == 0
