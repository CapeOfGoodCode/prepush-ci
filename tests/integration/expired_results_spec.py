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


def install_hook(repo: Path, *, before: str = "", arguments: bool = True) -> None:
    """The native pre-push hook; without `arguments` it does not pass the remote on, as lefthook
    and pre-commit do not."""
    passed = ' "$@"' if arguments else ""
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        f"{before}"
        f'exec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push{passed}\n'
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


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    return tmp_path / "remote.git"


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


def old_ref(repo: Path, git: Git, name: str, days: int) -> str:
    """A result ref of the tree of `HEAD` whose commit is `days` days old (a negative number: in
    the future); returns the ref."""
    date = ago(days)
    made = git(
        repo,
        "commit-tree",
        "HEAD^{tree}",
        "-m",
        "an old result",
        env={"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date},
    )
    ref = f"{RESULTS}/{name}"
    git(repo, "update-ref", ref, made.stdout.strip())
    return ref


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


# --- A result older than 30 days is deleted ------------------------------------------------------


def test_an_expired_ref_is_deleted_by_a_run_without_a_remote(
    local: Path, git: Git
) -> None:
    old = old_ref(local, git, "old", 31)

    result = run_cli(local)

    assert result.returncode == 0
    [new] = results(local, git)
    assert new != old


def test_a_ref_of_29_days_stays(local: Path, git: Git) -> None:
    old = old_ref(local, git, "recent", 29)

    assert run_cli(local).returncode == 0
    assert old in results(local, git)
    assert len(results(local, git)) == 2


def test_a_ref_dated_in_the_future_stays(local: Path, git: Git) -> None:
    future = old_ref(local, git, "future", -1)

    assert run_cli(local).returncode == 0
    assert future in results(local, git)


def test_a_ref_that_cannot_be_read_stays(local: Path, git: Git) -> None:
    broken = old_ref(local, git, "broken", 31)
    (local / ".git" / broken).write_text("")

    result = run_cli(local)

    assert result.returncode == 0
    assert (local / ".git" / broken).exists()
    assert len(results(local, git)) == 1


def damage(repo: Path, name: str) -> str:
    """A result ref whose object is missing: git cannot give its date, and it stops a listing of
    the refs around it."""
    ref = f"{RESULTS}/{name}"
    path = repo / ".git" / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("1" * 40 + "\n")
    return ref


def test_a_ref_whose_object_is_missing_stays_and_the_expired_refs_around_it_go(
    local: Path, git: Git
) -> None:
    damaged = damage(local, "damaged")
    expired = [old_ref(local, git, name, 31) for name in ("aaa", "bbb", "ccc")]
    recent = old_ref(local, git, "recent", 29)

    result = run_cli(local)

    assert result.returncode == 0
    left = results(local, git)
    assert damaged in left and recent in left
    assert not set(expired) & set(left)


def test_a_ref_whose_object_is_missing_stays_among_hundreds_of_expired_refs(
    local: Path, git: Git
) -> None:
    template = old_ref(local, git, "template", 31)
    sha = git(local, "rev-parse", template).stdout.strip()
    git(local, "update-ref", "-d", template)
    folder = local / ".git" / RESULTS
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(250):
        (folder / f"old-{number}").write_text(sha + "\n")
    damaged = damage(local, "damaged")

    result = run_cli(local)

    assert result.returncode == 0
    assert damaged in results(local, git)
    assert len(results(local, git)) == 2


def test_two_thousand_expired_refs_are_deleted(local: Path, git: Git) -> None:
    template = old_ref(local, git, "template", 31)
    sha = git(local, "rev-parse", template).stdout.strip()
    git(local, "update-ref", "-d", template)
    folder = local / ".git" / RESULTS
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(2000):
        (folder / f"old-{number}").write_text(sha + "\n")

    result = run_cli(local)

    assert result.returncode == 0
    assert len(results(local, git)) == 1


def test_a_hook_pass_in_a_push_to_another_remote_deletes_an_expired_ref(
    local: Path, git: Git, tmp_path: Path
) -> None:
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "other.git"))
    old = old_ref(local, git, "old", 31)

    result = git(local, "push", str(tmp_path / "other.git"), "main", check=False)

    assert result.returncode == 0
    [new] = results(local, git)
    assert new != old


# --- Only a recorded pass cleans up --------------------------------------------------------------


def test_a_reused_result_cleans_nothing(
    local: Path, git: Git, tmp_path: Path, log: Path
) -> None:
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "other.git"))
    assert run_cli(local).returncode == 0
    old = old_ref(local, git, "old", 31)

    result = git(local, "push", str(tmp_path / "other.git"), "main", check=False)

    assert result.returncode == 0
    assert "passed earlier" in result.stderr
    assert len(log.read_text().splitlines()) == 1
    assert old in results(local, git)


def test_a_failing_check_cleans_nothing(local: Path, git: Git, log: Path) -> None:
    write_config(local, log, check="exit 1")
    old = old_ref(local, git, "old", 31)

    result = run_cli(local)

    assert result.returncode == 1
    assert results(local, git) == [old]


def test_a_refusal_cleans_nothing(local: Path, git: Git) -> None:
    (local / "stray.txt").write_text("not committed")
    old = old_ref(local, git, "old", 31)

    result = run_cli(local)

    assert result.returncode == 1
    assert results(local, git) == [old]


def test_with_the_cache_off_nothing_is_cleaned(
    local: Path, git: Git, log: Path
) -> None:
    write_config(local, log, "cache = false")
    old = old_ref(local, git, "old", 31)

    result = run_cli(local)

    assert result.returncode == 0
    assert results(local, git) == [old]


# --- A cleanup that fails costs a warning and nothing else ---------------------------------------


def test_a_clone_that_cannot_delete_is_a_warning_and_the_run_passes(
    local: Path, git: Git
) -> None:
    old = old_ref(local, git, "locked", 31)
    (local / ".git" / f"{old}.lock").write_text("")

    result = run_cli(local)

    assert result.returncode == 0
    assert "old results could not be removed" in result.stderr
    assert old in results(local, git)


# --- A push to origin cleans origin too ----------------------------------------------------------


def both_hold(repo: Path, git: Git, name: str, days: int) -> str:
    """A result ref of `days` days ago held by the clone and by `origin`."""
    ref = old_ref(repo, git, name, days)
    git(repo, "push", "--no-verify", "origin", f"{ref}:{ref}")
    return ref


def push_main(repo: Path, git: Git, *words: str) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", *(words or ("origin", "main")), check=False)


def warnings_of_the_cleanup(stderr: str) -> list[str]:
    return [
        line
        for line in stderr.splitlines()
        if "old results could not be removed" in line
    ]


def test_an_expired_ref_leaves_both_sides_in_a_push_to_origin(
    pushing: Path, git: Git, origin: Path
) -> None:
    old = both_hold(pushing, git, "old", 31)

    result = push_main(pushing, git)

    assert result.returncode == 0
    for repo in (pushing, origin):
        [new] = results(repo, git)
        assert new != old


def test_a_ref_whose_object_is_missing_does_not_stop_a_push_to_origin_from_cleaning(
    pushing: Path, git: Git, origin: Path
) -> None:
    damaged = damage(pushing, "damaged")
    old = both_hold(pushing, git, "old", 31)

    result = push_main(pushing, git)

    assert result.returncode == 0
    assert old not in results(pushing, git)
    assert old not in results(origin, git)
    assert damaged in results(pushing, git)


def test_a_ref_of_29_days_stays_on_both_sides(
    pushing: Path, git: Git, origin: Path
) -> None:
    recent = both_hold(pushing, git, "recent", 29)

    assert push_main(pushing, git).returncode == 0
    for repo in (pushing, origin):
        assert recent in results(repo, git)
        assert len(results(repo, git)) == 2


def test_a_ref_only_origin_holds_stays(pushing: Path, git: Git, origin: Path) -> None:
    only = both_hold(pushing, git, "only", 31)
    git(pushing, "update-ref", "-d", only)

    assert push_main(pushing, git).returncode == 0
    assert only in results(origin, git)


def test_a_ref_origin_never_held_is_dropped_from_the_clone_without_a_warning(
    pushing: Path, git: Git
) -> None:
    old_ref(pushing, git, "local-only", 31)

    result = push_main(pushing, git)

    assert result.returncode == 0
    assert len(results(pushing, git)) == 1
    assert "old results" not in result.stderr


def test_cleaning_does_not_start_the_hook_again(
    pushing: Path, git: Git, origin: Path, tmp_path: Path
) -> None:
    started = tmp_path / "hook-started.log"
    install_hook(pushing, before=f'echo started >> "{started.as_posix()}"\n')
    old = both_hold(pushing, git, "old", 31)

    result = push_main(pushing, git)

    assert result.returncode == 0
    assert started.read_text().splitlines() == ["started"]
    assert old not in results(origin, git)


def expired_on_both_sides(pushing: Path, git: Git, origin: Path, count: int) -> None:
    """`count` result refs of 31 days ago held by the clone and by `origin`."""
    template = old_ref(pushing, git, "template", 31)
    sha = git(pushing, "rev-parse", template).stdout.strip()
    git(pushing, "update-ref", "-d", template)
    folder = pushing / ".git" / RESULTS
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(count):
        (folder / f"old-{number}").write_text(sha + "\n")
    git(pushing, "push", "--no-verify", "origin", f"{RESULTS}/*:{RESULTS}/*")
    assert len(results(origin, git)) == count


def test_two_hundred_and_fifty_expired_refs_leave_both_sides(
    pushing: Path, git: Git, origin: Path
) -> None:
    expired_on_both_sides(pushing, git, origin, 250)

    result = push_main(pushing, git)

    assert result.returncode == 0
    assert len(results(pushing, git)) == 1
    assert len(results(origin, git)) == 1


# --- A dry run or a declined push to origin still cleans -----------------------------------------


def decline_main(remote: Path) -> None:
    """A `pre-receive` hook that declines `refs/heads/main` and takes any other ref."""
    hook = remote / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        '  [ "$ref" = refs/heads/main ] && { echo "main is closed" >&2; exit 1; }\n'
        "done\n"
        "exit 0\n"
    )
    hook.chmod(0o755)


def test_a_dry_run_to_origin_cleans_and_main_does_not_move(
    pushing: Path, git: Git, origin: Path
) -> None:
    old = both_hold(pushing, git, "old", 31)

    result = push_main(pushing, git, "--dry-run", "origin", "main")

    assert result.returncode == 0
    for repo in (pushing, origin):
        assert old not in results(repo, git)
        assert len(results(repo, git)) == 1
    assert git(origin, "rev-parse", "refs/heads/main", check=False).returncode != 0


def test_a_push_that_origin_declines_cleans_and_main_does_not_move(
    pushing: Path, git: Git, origin: Path
) -> None:
    old = both_hold(pushing, git, "old", 31)
    decline_main(origin)

    result = push_main(pushing, git)

    assert result.returncode != 0
    assert "main is closed" in result.stderr
    for repo in (pushing, origin):
        assert old not in results(repo, git)
        assert len(results(repo, git)) == 1
    assert git(origin, "rev-parse", "refs/heads/main", check=False).returncode != 0


# --- A repository with origin cleans only in a push to origin ------------------------------------


def test_run_cleans_nothing_in_a_repository_with_origin(
    pushing: Path, git: Git, origin: Path
) -> None:
    old = both_hold(pushing, git, "old", 31)

    result = run_cli(pushing)

    assert result.returncode == 0
    assert old in results(pushing, git)
    assert old in results(origin, git)


def test_a_push_to_another_remote_cleans_nothing(
    pushing: Path, git: Git, origin: Path, tmp_path: Path
) -> None:
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "other.git"))
    git(pushing, "remote", "add", "other", str(tmp_path / "other.git"))
    old = both_hold(pushing, git, "old", 31)

    result = push_main(pushing, git, "other", "main")

    assert result.returncode == 0
    assert old in results(pushing, git)
    assert old in results(origin, git)


def test_a_push_by_url_cleans_nothing(pushing: Path, git: Git, origin: Path) -> None:
    old = both_hold(pushing, git, "old", 31)

    result = push_main(pushing, git, str(origin), "main")

    assert result.returncode == 0
    assert old in results(pushing, git)
    assert old in results(origin, git)


def test_a_hook_that_cannot_tell_the_remote_cleans_nothing(
    pushing: Path, git: Git, origin: Path
) -> None:
    install_hook(pushing, arguments=False)
    old = both_hold(pushing, git, "old", 31)

    result = push_main(pushing, git)

    assert result.returncode == 0
    assert old in results(pushing, git)
    assert old in results(origin, git)


# --- A cleanup of origin that fails costs a warning and nothing else -----------------------------


def refuse_deletions(remote: Path) -> Path:
    """A `pre-receive` hook that declines every deletion of a ref."""
    hook = remote / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        '  case "$new" in 0000*) echo "no deletions" >&2; exit 1;; esac\n'
        "done\n"
        "exit 0\n"
    )
    hook.chmod(0o755)
    return hook


def test_an_origin_that_declines_the_delete_is_a_warning_and_the_push_goes_through(
    pushing: Path, git: Git, origin: Path
) -> None:
    old = both_hold(pushing, git, "old", 31)
    refuse_deletions(origin)

    result = push_main(pushing, git)

    assert result.returncode == 0
    [warning] = warnings_of_the_cleanup(result.stderr)
    assert "origin" in warning
    assert old in results(pushing, git)
    assert old in results(origin, git)
    assert git(origin, "rev-parse", "refs/heads/main").returncode == 0


def test_two_batches_that_origin_declines_are_one_warning_and_the_clone_keeps_the_refs(
    pushing: Path, git: Git, origin: Path
) -> None:
    expired_on_both_sides(pushing, git, origin, 250)
    refuse_deletions(origin)

    result = push_main(pushing, git)

    assert result.returncode == 0
    [warning] = warnings_of_the_cleanup(result.stderr)
    assert "no deletions" in warning
    for side in (pushing, origin):
        kept = [ref for ref in results(side, git) if "/old-" in ref]
        assert len(kept) == 250


def test_an_origin_that_cannot_be_reached_is_a_warning_and_the_clone_keeps_the_ref(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    old = old_ref(pushing, git, "old", 31)
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    git(pushing, "remote", "set-url", "origin", str(nowhere))
    tip = git(pushing, "rev-parse", "HEAD").stdout.strip()
    zeros = "0" * 40

    hook = subprocess.run(
        [
            sys.executable,
            "-m",
            "prepush_ci",
            "hook",
            "pre-push",
            "origin",
            str(nowhere),
        ],
        cwd=pushing,
        input=f"refs/heads/main {tip} refs/heads/main {zeros}\n",
        capture_output=True,
        text=True,
        check=False,
        env={k: v for k, v in os.environ.items() if k != "PREPUSH_CI"},
    )

    assert hook.returncode == 0
    [warning] = warnings_of_the_cleanup(hook.stderr)
    assert "origin" in warning
    assert old in results(pushing, git)


def test_the_next_push_to_origin_tries_again(
    pushing: Path, git: Git, origin: Path
) -> None:
    old = both_hold(pushing, git, "old", 31)
    refusing = refuse_deletions(origin)
    assert push_main(pushing, git).returncode == 0
    refusing.unlink()
    (pushing / "next.txt").write_text("next")
    git(pushing, "add", "next.txt")
    git(pushing, "commit", "-q", "-m", "next" + TRAILER)

    result = push_main(pushing, git)

    assert result.returncode == 0
    assert old not in results(pushing, git)
    assert old not in results(origin, git)
