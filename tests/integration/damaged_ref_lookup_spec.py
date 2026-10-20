"""The lookup of a result on `origin` with a damaged ref in the clone: the result is still reused
where git can write the key's ref, and a miss where it cannot; git does no housekeeping meanwhile."""

import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
SKIPPED = "passed earlier"


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "ran.log"


def runs(log: Path) -> int:
    return len(log.read_text().splitlines()) if log.exists() else 0


def prepare(clone: Path, log: Path) -> None:
    """The ignored config, whose check logs to `log`, and the native pre-push hook."""
    (clone / ".git" / "info" / "exclude").write_text(".prepush-ci.toml\nready\n")
    (clone / ".prepush-ci.toml").write_text(
        f"check = 'echo ran >> {log.as_posix()}'\nrequire_up_to_date = false\n"
    )
    hook = clone / ".git" / "hooks" / "pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        f'exec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def fresh(repo: Path, tmp_path: Path, git: Git, log: Path) -> Path:
    """A clone of `origin`, which holds the result of a pass on the tree of its tip, with a tip of
    the same tree that carries the trailer and no result of its own."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    prepare(repo, log)
    git(repo, "commit", "--allow-empty", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "commit", "--allow-empty", "-q", "-m", "work" + TRAILER)
    assert git(repo, "push", "origin", "main", check=False).returncode == 0
    assert runs(log) == 1
    clone = tmp_path / "fresh"
    git(tmp_path, "clone", "-q", str(remote), str(clone))
    for key, value in (
        ("user.name", "Other"),
        ("user.email", "other@example.com"),
        ("commit.gpgsign", "false"),
    ):
        git(clone, "config", key, value)
    prepare(clone, log)
    git(clone, "commit", "--allow-empty", "-q", "--amend", "-m", "other" + TRAILER)
    return clone


def push(repo: Path, git: Git) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", "origin", "main:refs/heads/second", check=False)


def key_ref(tmp_path: Path, git: Git) -> str:
    """The result ref `origin` holds."""
    [ref] = git(
        tmp_path / "remote.git",
        "for-each-ref",
        "--format=%(refname)",
        "refs/prepush-ci/results",
    ).stdout.split()
    return ref


def damage(clone: Path, ref: str) -> Path:
    """An empty file where the ref `ref` is stored."""
    path = clone / ".git" / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def test_another_emptied_result_ref_does_not_hide_the_result_on_origin(
    fresh: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    passed = git(tmp_path / "remote.git", "rev-parse", "main").stdout.strip()
    damage(fresh, "refs/prepush-ci/results/another")

    result = push(fresh, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 1
    [line] = [line for line in result.stderr.splitlines() if SKIPPED in line]
    assert "origin" in line
    assert git(fresh, "rev-parse", "HEAD^{tree}").stdout.strip()[:12] in line
    assert passed[:12] in line


def test_a_ref_with_a_refused_name_does_not_hide_the_result_on_origin(
    fresh: Path, git: Git, log: Path
) -> None:
    broken = fresh / ".git" / "refs" / "prepush-ci" / "results" / "bad..name"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text((fresh / ".git" / "refs" / "heads" / "main").read_text())

    result = push(fresh, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 1


def test_a_broken_ref_that_holds_the_only_copy_of_a_commit_does_not_let_the_lookup_prune_it(
    fresh: Path, git: Git, log: Path
) -> None:
    # two packs, so that a fetch would start `gc --auto` if it may
    git(fresh, "repack", "-q", "-d")
    filler = git(fresh, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "filler")
    git(fresh, "update-ref", "refs/heads/filler", filler.stdout.strip())
    git(fresh, "repack", "-q", "-d")
    only = git(fresh, "commit-tree", "HEAD^{tree}", "-m", "only copy").stdout.strip()
    broken = fresh / ".git" / "refs" / "prepush-ci" / "results" / "bad..name"
    broken.parent.mkdir(parents=True)
    broken.write_text(only + "\n")
    for key, value in (
        ("gc.auto", "1"),
        ("gc.autoPackLimit", "1"),
        ("gc.autoDetach", "false"),
        ("gc.pruneExpire", "now"),
    ):
        git(fresh, "config", key, value)

    result = push(fresh, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 1
    assert git(fresh, "cat-file", "-e", only, check=False).returncode == 0


def test_a_damaged_ref_of_the_name_of_the_key_makes_the_lookup_a_miss_and_the_check_runs(
    fresh: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    damage(fresh, key_ref(tmp_path, git))

    result = push(fresh, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 2


def test_a_cache_path_that_is_a_file_makes_the_lookup_a_miss_and_the_check_runs(
    fresh: Path, git: Git, log: Path
) -> None:
    (fresh / ".git" / "refs" / "prepush-ci").write_text("in the way")

    result = push(fresh, git)

    assert result.returncode == 0, result.stderr
    assert runs(log) == 2
