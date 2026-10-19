"""The pre-push hook and the result cache, with real `git push` to a bare repository.

The config is an ignored file here, so a spec can change it without dirtying the worktree.
"""

import os
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
    """How many times a check ran (each appends a line)."""
    return len(log.read_text().splitlines()) if log.exists() else 0


def write_config(repo: Path, log: Path, *lines: str, check: str | None = None) -> None:
    body = [
        f"check = '{check or f'echo ran >> {log.as_posix()}'}'",
        "require_up_to_date = false",
        *lines,
    ]
    (repo / ".prepush-ci.toml").write_text("\n".join(body) + "\n")


@pytest.fixture
def pushing(repo: Path, tmp_path: Path, git: Git, log: Path) -> Path:
    """`repo` on `main` with an empty first commit, an ignored config whose check logs to `log`,
    a bare `origin` and the pre-push hook installed the way git runs it."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".git" / "info" / "exclude").write_text(".prepush-ci.toml\nready\n")
    write_config(repo, log)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    git(repo, "commit", "--allow-empty", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    git(repo, "commit", "--allow-empty", "-q", "-m", "work" + TRAILER)
    return repo


def push(
    repo: Path, git: Git, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", "origin", "main", env=env, check=False)


def run_cli(
    repo: Path, extra: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    env = {k: v for k, v in os.environ.items() if k != "PREPUSH_CI"}
    env.update(extra or {})
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "run"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def refs(repo: Path, git: Git) -> list[str]:
    """The result refs, as `refname`."""
    listing = git(
        repo, "for-each-ref", "--format=%(refname)", "refs/prepush-ci/results"
    )
    return listing.stdout.split()


def head_of(repo: Path, git: Git, rev: str = "HEAD") -> str:
    return git(repo, "rev-parse", rev).stdout.strip()


def remote_has(repo: Path, git: Git) -> bool:
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    return (
        git(repo.parent / "remote.git", "cat-file", "-e", head, check=False).returncode
        == 0
    )


def write_versions(repo: Path, log: Path, tmp_path: Path) -> None:
    """A config whose `preflight` prints the variable `TOOL_VERSION`, as a tool reports its version."""
    script = tmp_path / "version.py"
    script.write_text("import os\nprint(os.environ['TOOL_VERSION'])\n")
    # no quotes around the paths: cmd strips the outer pair of a command that starts with one
    command = f"{Path(sys.executable).as_posix()} {script.as_posix()}"
    write_config(repo, log, f"preflight = '{command}'")


def test_a_push_after_a_passing_run_skips_the_check_and_says_so(
    pushing: Path, git: Git, log: Path
) -> None:
    assert run_cli(pushing).returncode == 0

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 1
    assert SKIPPED in result.stderr
    assert remote_has(pushing, git)


def test_a_push_the_remote_rejected_is_retried_without_running_the_check_again(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    rejecting = tmp_path / "remote.git" / "hooks" / "pre-receive"
    rejecting.write_text("#!/bin/sh\nexit 1\n")
    rejecting.chmod(0o755)
    first = push(pushing, git)
    rejecting.unlink()

    second = push(pushing, git)

    assert first.returncode != 0
    assert SKIPPED not in first.stderr
    assert second.returncode == 0
    assert runs(log) == 1
    assert SKIPPED in second.stderr


def test_the_preflight_still_runs_for_a_cached_pass(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    script = tmp_path / "ready_check.py"
    script.write_text(
        "import pathlib, sys\nsys.exit(not pathlib.Path('ready').exists())\n"
    )
    # no quotes around the paths: cmd strips the outer pair of a command that starts with one
    command = f"{Path(sys.executable).as_posix()} {script.as_posix()}"
    write_config(pushing, log, f"preflight = '{command}'")
    (pushing / "ready").write_text("")
    assert run_cli(pushing).returncode == 0
    (pushing / "ready").unlink()

    result = push(pushing, git)

    assert result.returncode != 0
    assert "preflight" in result.stderr
    assert runs(log) == 1
    assert not remote_has(pushing, git)


def test_a_dirty_worktree_is_still_refused_for_a_cached_pass(
    pushing: Path, git: Git, log: Path
) -> None:
    run_cli(pushing)
    (pushing / "stray.txt").write_text("x")

    result = push(pushing, git)

    assert result.returncode != 0
    assert "stray.txt" in result.stderr
    assert runs(log) == 1


def test_a_pass_in_the_hook_is_recorded_for_the_tree_of_the_tip(
    pushing: Path, git: Git
) -> None:
    assert push(pushing, git).returncode == 0

    tree = head_of(pushing, git, "HEAD^{tree}")
    [ref] = refs(pushing, git)
    assert ref.startswith(f"refs/prepush-ci/results/{tree}-")
    assert head_of(pushing, git, f"{ref}^{{tree}}") == tree


def test_a_failing_check_in_the_hook_records_nothing(
    pushing: Path, git: Git, log: Path
) -> None:
    write_config(pushing, log, check="exit 1")

    assert push(pushing, git).returncode != 0

    assert refs(pushing, git) == []


def test_an_amended_message_skips_the_check(pushing: Path, git: Git, log: Path) -> None:
    run_cli(pushing)
    git(pushing, "commit", "--allow-empty", "-q", "--amend", "-m", "other" + TRAILER)

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 1
    assert SKIPPED in result.stderr


def test_squashed_commits_skip_the_check(pushing: Path, git: Git, log: Path) -> None:
    git(pushing, "commit", "--allow-empty", "-q", "-m", "more" + TRAILER)
    run_cli(pushing)
    git(pushing, "reset", "--soft", "HEAD~2")
    git(pushing, "commit", "--allow-empty", "-q", "-m", "squashed" + TRAILER)

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 1
    assert SKIPPED in result.stderr


def test_the_skip_line_names_the_tree_and_the_commit_that_passed(
    pushing: Path, git: Git
) -> None:
    run_cli(pushing)
    passed = head_of(pushing, git)
    git(pushing, "commit", "--allow-empty", "-q", "--amend", "-m", "other" + TRAILER)
    amended = head_of(pushing, git)
    tree = head_of(pushing, git, "HEAD^{tree}")

    result = push(pushing, git)

    assert tree[:12] in result.stderr
    assert passed[:12] in result.stderr
    assert amended[:12] not in result.stderr


def test_another_tree_runs_the_check_again(pushing: Path, git: Git, log: Path) -> None:
    run_cli(pushing)
    (pushing / "new.txt").write_text("new")
    git(pushing, "add", "new.txt")
    git(pushing, "commit", "-q", "-m", "more" + TRAILER)

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 2
    assert SKIPPED not in result.stderr


def test_a_changed_check_command_runs_the_check_again(
    pushing: Path, git: Git, log: Path
) -> None:
    run_cli(pushing)
    write_config(pushing, log, check=f"echo other >> {log.as_posix()}")

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 2
    assert SKIPPED not in result.stderr


def test_a_changed_list_of_required_variables_runs_the_check_again(
    pushing: Path, git: Git, log: Path
) -> None:
    run_cli(pushing)
    write_config(pushing, log, 'require_env = ["PREPUSH_CI_SPEC_VAR"]')

    result = push(pushing, git, {"PREPUSH_CI_SPEC_VAR": "x"})

    assert result.returncode == 0
    assert runs(log) == 2


def test_a_key_that_does_not_change_the_result_still_skips_the_check(
    pushing: Path, git: Git, log: Path
) -> None:
    run_cli(pushing)
    write_config(pushing, log, 'default_branch = "trunk"')

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 1
    assert SKIPPED in result.stderr


def test_a_changed_tool_version_runs_the_check_again(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    write_versions(pushing, log, tmp_path)
    assert run_cli(pushing, {"TOOL_VERSION": "1"}).returncode == 0

    result = push(pushing, git, {"TOOL_VERSION": "2"})

    assert result.returncode == 0
    assert runs(log) == 2
    assert SKIPPED not in result.stderr


def test_the_same_tool_version_skips_the_check(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    write_versions(pushing, log, tmp_path)
    assert run_cli(pushing, {"TOOL_VERSION": "1"}).returncode == 0

    result = push(pushing, git, {"TOOL_VERSION": "1"})

    assert result.returncode == 0
    assert runs(log) == 1
    assert SKIPPED in result.stderr


def test_the_error_stream_of_the_preflight_is_not_in_the_key(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    script = tmp_path / "version_to_stderr.py"
    script.write_text(
        "import os, sys\nprint(os.environ['TOOL_VERSION'], file=sys.stderr)\n"
    )
    command = f"{Path(sys.executable).as_posix()} {script.as_posix()}"
    write_config(pushing, log, f"preflight = '{command}'")
    assert run_cli(pushing, {"TOOL_VERSION": "1"}).returncode == 0

    result = push(pushing, git, {"TOOL_VERSION": "2"})

    assert result.returncode == 0
    assert runs(log) == 1
    assert SKIPPED in result.stderr


def test_the_output_of_the_preflight_is_still_shown(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    write_versions(pushing, log, tmp_path)

    run = run_cli(pushing, {"TOOL_VERSION": "versions-ok"})
    pushed = push(pushing, git, {"TOOL_VERSION": "versions-ok"})

    assert "versions-ok" in run.stdout
    assert "versions-ok" in pushed.stdout + pushed.stderr


def test_with_the_cache_off_a_result_is_ignored(
    pushing: Path, git: Git, log: Path
) -> None:
    run_cli(pushing)
    write_config(pushing, log, "cache = false")

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 2


def test_with_the_cache_off_the_hook_records_nothing(
    pushing: Path, git: Git, log: Path
) -> None:
    write_config(pushing, log, "cache = false")

    assert push(pushing, git).returncode == 0

    assert refs(pushing, git) == []


def test_an_emptied_result_ref_runs_the_check_again(
    pushing: Path, git: Git, log: Path
) -> None:
    run_cli(pushing)
    [ref] = refs(pushing, git)
    (pushing / ".git" / ref).write_text("")

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 2


def test_a_result_ref_moved_to_a_commit_of_another_tree_runs_the_check_again(
    pushing: Path, git: Git, log: Path
) -> None:
    (pushing / "other.txt").write_text("other")
    git(pushing, "add", "other.txt")
    git(pushing, "commit", "-q", "-m", "other tree" + TRAILER)
    run_cli(pushing)
    [other] = refs(pushing, git)
    elsewhere = head_of(pushing, git, other)
    git(pushing, "reset", "-q", "--hard", "HEAD~1")
    run_cli(pushing)
    [ref] = [name for name in refs(pushing, git) if name != other]
    git(pushing, "update-ref", ref, elsewhere)

    result = push(pushing, git)

    assert result.returncode == 0
    assert runs(log) == 3
    assert SKIPPED not in result.stderr


def test_a_push_goes_through_with_a_warning_when_the_cache_cannot_be_written(
    pushing: Path, git: Git
) -> None:
    (pushing / ".git" / "refs" / "prepush-ci").write_text("in the way")

    result = push(pushing, git)

    assert result.returncode == 0
    assert "could not be cached" in result.stderr


def test_a_commit_made_during_the_check_is_not_taken_for_a_checked_one(
    pushing: Path, git: Git, log: Path
) -> None:
    checked = head_of(pushing, git, "HEAD^{tree}")
    moving = (
        f"echo ran >> {log.as_posix()} && "
        "echo more >> more.txt && git add more.txt && "
        'git commit -q -m moved -m "Prepush-CI: full"'
    )
    write_config(pushing, log, check=moving)
    assert push(pushing, git).returncode == 0
    [ref] = refs(pushing, git)

    result = push(pushing, git)

    assert result.returncode == 0
    assert ref.startswith(f"refs/prepush-ci/results/{checked}-")
    assert runs(log) == 2
    assert SKIPPED not in result.stderr
