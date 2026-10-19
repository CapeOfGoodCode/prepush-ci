"""Result refs shared through `origin`: published by a push to `origin`, looked up before a check.

Real `git push` to bare repositories; the config is an ignored file, so a spec can change it
without dirtying the worktree.
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
NOT_SHARED = "not shared through origin"
NOT_ASKED = "origin could not be asked"
SKIPPED = "passed earlier"
# A remote that takes branches and nothing else, as a Claude Code cloud session's proxy does.
BRANCHES_ONLY = (
    "#!/bin/sh\n"
    "while read old new ref; do\n"
    '  case "$ref" in refs/heads/*) ;; *) echo "only branches" >&2; exit 1;; esac\n'
    "done\n"
)


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


def install_hook(repo: Path, *, arguments: bool = True, before: str = "") -> None:
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
def pushing(repo: Path, tmp_path: Path, git: Git, log: Path) -> Path:
    """`repo` on `main` with a commit that carries the trailer, an ignored config whose check logs
    to `log`, the pre-push hook, a bare `origin` and a bare `other`."""
    for name in ("remote", "other"):
        git(tmp_path, "init", "-q", "--bare", str(tmp_path / f"{name}.git"))
        git(tmp_path / f"{name}.git", "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".git" / "info" / "exclude").write_text(".prepush-ci.toml\nready\n")
    write_config(repo, log)
    install_hook(repo)
    git(repo, "commit", "--allow-empty", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    git(repo, "remote", "add", "other", str(tmp_path / "other.git"))
    git(repo, "commit", "--allow-empty", "-q", "-m", "work" + TRAILER)
    return repo


def push(
    repo: Path,
    git: Git,
    *words: str,
    env: dict[str, str] | None = None,
) -> "subprocess.CompletedProcess[str]":
    """`git push origin main` unless the words say otherwise."""
    return git(repo, "push", *(words or ("origin", "main")), env=env, check=False)


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


def shared(remote: Path, git: Git) -> list[str]:
    """The result refs a bare repository holds."""
    listing = git(
        remote, "for-each-ref", "--format=%(refname)", "refs/prepush-ci/results"
    )
    return listing.stdout.split()


def local_results(repo: Path, git: Git) -> list[str]:
    return shared(repo, git)


def warnings_naming_origin(stderr: str) -> list[str]:
    """The lines of prepush-ci that name `origin`."""
    return [
        line
        for line in stderr.splitlines()
        if "prepush-ci:" in line and "origin" in line
    ]


def tree_of_head(repo: Path, git: Git) -> str:
    return git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()


def refuse_other_refs(remote: Path) -> Path:
    hook = remote / "hooks" / "pre-receive"
    hook.write_text(BRANCHES_ONLY)
    hook.chmod(0o755)
    return hook


# --- A pass is published to origin by a push to origin -------------------------------------------


def test_a_hook_pass_in_a_push_to_origin_publishes_the_result_and_the_check_runs_once(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    result = push(pushing, git)

    assert result.returncode == 0
    [ref] = shared(tmp_path / "remote.git", git)
    assert ref.startswith(f"refs/prepush-ci/results/{tree_of_head(pushing, git)}-")
    assert runs(log) == 1


def test_publishing_does_not_start_the_hook_again(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    started = tmp_path / "hook-started.log"
    install_hook(pushing, before=f'echo started >> "{started.as_posix()}"\n')

    result = push(pushing, git)

    assert result.returncode == 0
    assert started.read_text().splitlines() == ["started"]
    assert len(shared(tmp_path / "remote.git", git)) == 1


def test_a_reused_local_result_is_published_by_a_later_push_to_origin(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    remote = tmp_path / "remote.git"
    refusing = refuse_other_refs(remote)
    first = push(pushing, git)
    refusing.unlink()

    second = push(pushing, git, "origin", "main:elsewhere")

    assert first.returncode == 0
    assert second.returncode == 0
    assert runs(log) == 1
    assert len(shared(remote, git)) == 1


def test_a_push_to_another_remote_publishes_nothing(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    result = push(pushing, git, "other", "main")

    assert result.returncode == 0
    assert shared(tmp_path / "remote.git", git) == []
    assert shared(tmp_path / "other.git", git) == []


def test_a_reused_local_result_is_not_published_by_a_push_to_another_remote(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0

    result = push(pushing, git, "other", "main")

    assert result.returncode == 0
    assert runs(log) == 1
    assert shared(tmp_path / "other.git", git) == []


def test_run_publishes_nothing(pushing: Path, git: Git, tmp_path: Path) -> None:
    assert run_cli(pushing).returncode == 0

    assert len(local_results(pushing, git)) == 1
    assert shared(tmp_path / "remote.git", git) == []


def test_a_failing_check_publishes_nothing_and_warns_of_nothing(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    write_config(pushing, log, check="exit 1")

    result = push(pushing, git)

    assert result.returncode != 0
    assert shared(tmp_path / "remote.git", git) == []
    assert warnings_naming_origin(result.stderr) == []


# --- Only origin and only with the cache ---------------------------------------------------------


def test_with_the_cache_off_nothing_is_published(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    write_config(pushing, log, "cache = false")

    result = push(pushing, git)

    assert result.returncode == 0
    assert shared(tmp_path / "remote.git", git) == []


def test_without_an_origin_a_push_to_another_remote_succeeds_and_says_nothing(
    pushing: Path, git: Git
) -> None:
    git(pushing, "remote", "remove", "origin")

    result = push(pushing, git, "other", "main")

    assert result.returncode == 0
    assert "prepush-ci:" not in result.stderr


def test_without_an_origin_a_remote_name_origin_from_pre_commit_shares_nothing_and_says_nothing(
    pushing: Path, git: Git
) -> None:
    git(pushing, "remote", "remove", "origin")
    install_hook(pushing, arguments=False)

    result = push(
        pushing, git, "other", "main", env={"PRE_COMMIT_REMOTE_NAME": "origin"}
    )

    assert result.returncode == 0
    assert "prepush-ci:" not in result.stderr


# --- A remote that fails costs time and nothing else ---------------------------------------------


def test_a_remote_that_refuses_the_ref_is_a_warning_and_the_push_goes_through(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    remote = tmp_path / "remote.git"
    refuse_other_refs(remote)

    result = push(pushing, git)

    assert result.returncode == 0
    assert NOT_SHARED in result.stderr
    assert shared(remote, git) == []
    assert git(remote, "rev-parse", "refs/heads/main", check=False).returncode == 0


def decline_main(remote: Path) -> Path:
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
    return hook


def push_the_first_commit(repo: Path, git: Git) -> str:
    """Put the commit before the tip (no trailer, so the hook leaves it alone) on `origin`'s
    `main`, and return its id: the id a push of the tip must not move `main` from."""
    first = git(repo, "rev-parse", "HEAD~1").stdout.strip()
    assert git(repo, "push", "origin", "HEAD~1:refs/heads/main").returncode == 0
    return first


def test_a_dry_run_to_origin_publishes_the_result_and_main_does_not_move(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    remote = tmp_path / "remote.git"
    first = push_the_first_commit(pushing, git)

    result = push(pushing, git, "--dry-run", "origin", "main")

    assert result.returncode == 0
    assert runs(log) == 1
    [ref] = shared(remote, git)
    assert ref.startswith(f"refs/prepush-ci/results/{tree_of_head(pushing, git)}-")
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == first


def test_a_push_that_origin_declines_publishes_the_result_and_main_does_not_move(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    remote = tmp_path / "remote.git"
    first = push_the_first_commit(pushing, git)
    decline_main(remote)

    result = push(pushing, git)

    assert result.returncode != 0
    assert "main is closed" in result.stderr
    assert runs(log) == 1
    [ref] = shared(remote, git)
    assert ref.startswith(f"refs/prepush-ci/results/{tree_of_head(pushing, git)}-")
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == first


# --- The hook reads the remote of the push from its arguments or pre-commit ----------------------


def test_the_remote_name_in_the_first_argument_publishes_to_origin(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    assert push(pushing, git, "origin", "main").returncode == 0

    assert len(shared(tmp_path / "remote.git", git)) == 1


def test_the_remote_name_pre_commit_sets_publishes_to_origin(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    install_hook(pushing, arguments=False)

    result = push(pushing, git, env={"PRE_COMMIT_REMOTE_NAME": "origin"})

    assert result.returncode == 0
    assert len(shared(tmp_path / "remote.git", git)) == 1


def test_the_first_argument_wins_over_the_name_pre_commit_sets(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    result = push(
        pushing, git, "other", "main", env={"PRE_COMMIT_REMOTE_NAME": "origin"}
    )

    assert result.returncode == 0
    assert shared(tmp_path / "remote.git", git) == []


def test_a_push_by_the_url_of_origin_is_not_a_push_to_origin(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    result = push(pushing, git, str(tmp_path / "remote.git"), "main")

    assert result.returncode == 0
    assert shared(tmp_path / "remote.git", git) == []


# --- A hook that does not know the remote publishes nothing --------------------------------------


def test_a_hook_that_cannot_tell_the_remote_publishes_nothing_and_says_nothing(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    install_hook(pushing, arguments=False)

    result = push(pushing, git)

    assert result.returncode == 0
    assert shared(tmp_path / "remote.git", git) == []
    assert "prepush-ci:" not in result.stderr


# --- A result on the remote is reused ------------------------------------------------------------


def fresh_clone(pushing: Path, git: Git, tmp_path: Path, log: Path) -> Path:
    """A clone of `origin` with its own config and hook, and a tip of the same tree that carries
    the trailer: what another session or a reviewer has."""
    clone = tmp_path / "fresh"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(clone))
    git(clone, "config", "user.name", "Other")
    git(clone, "config", "user.email", "other@example.com")
    git(clone, "config", "commit.gpgsign", "false")
    (clone / ".git" / "info" / "exclude").write_text(".prepush-ci.toml\nready\n")
    write_config(clone, log)
    install_hook(clone)
    git(clone, "commit", "--allow-empty", "-q", "--amend", "-m", "other" + TRAILER)
    return clone


def forget_locally(repo: Path, git: Git) -> None:
    for ref in local_results(repo, git):
        git(repo, "update-ref", "-d", ref)


def skip_line(result: "subprocess.CompletedProcess[str]") -> str:
    [line] = [line for line in result.stderr.splitlines() if SKIPPED in line]
    return line


def test_a_fresh_clone_reuses_the_result_from_origin_and_the_line_says_where_it_came_from(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0
    passed = git(pushing, "rev-parse", "HEAD").stdout.strip()
    clone = fresh_clone(pushing, git, tmp_path, log)
    amended = git(clone, "rev-parse", "HEAD").stdout.strip()

    result = push(clone, git, "origin", "main:refs/heads/second")

    assert result.returncode == 0
    assert runs(log) == 1
    line = skip_line(result)
    assert "origin" in line
    assert tree_of_head(clone, git)[:12] in line
    assert passed[:12] in line
    assert amended[:12] not in line


def test_a_result_reused_from_origin_is_kept_in_the_clone(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0
    clone = fresh_clone(pushing, git, tmp_path, log)

    assert push(clone, git, "origin", "main:refs/heads/second").returncode == 0

    assert local_results(clone, git) == shared(tmp_path / "remote.git", git)


def test_the_preflight_still_runs_for_a_result_from_origin(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0
    clone = fresh_clone(pushing, git, tmp_path, log)
    script = tmp_path / "ready_check.py"
    script.write_text("import sys\nsys.exit(1)\n")
    command = f"{Path(sys.executable).as_posix()} {script.as_posix()}"
    write_config(clone, log, f"preflight = '{command}'")
    forget_locally(clone, git)

    result = push(clone, git, "origin", "main:refs/heads/second")

    assert result.returncode != 0
    assert "preflight" in result.stderr
    assert runs(log) == 1


def test_a_result_made_with_another_check_on_origin_runs_the_check(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0
    clone = fresh_clone(pushing, git, tmp_path, log)
    write_config(clone, log, check=f"echo other >> {log.as_posix()}")

    result = push(clone, git, "origin", "main:refs/heads/second")

    assert result.returncode == 0
    assert runs(log) == 2
    assert SKIPPED not in result.stderr


def test_a_ref_of_another_tree_on_origin_is_a_miss_and_the_check_runs(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    remote = tmp_path / "remote.git"
    assert push(pushing, git).returncode == 0
    [ref] = shared(remote, git)
    (pushing / "extra.txt").write_text("extra")
    git(pushing, "add", "extra.txt")
    git(pushing, "commit", "-q", "-m", "another tree")
    other = git(pushing, "rev-parse", "HEAD").stdout.strip()
    assert push(pushing, git, "origin", "HEAD:refs/heads/extra").returncode == 0
    git(pushing, "reset", "-q", "--hard", "HEAD~1")
    git(remote, "update-ref", ref, other)
    forget_locally(pushing, git)

    result = push(pushing, git, "origin", "main:refs/heads/second")

    assert result.returncode == 0
    assert runs(log) == 2
    assert SKIPPED not in result.stderr
    # the new pass replaces the ref of the other tree, which is no fast-forward
    assert NOT_SHARED not in result.stderr
    assert git(remote, "rev-parse", f"{ref}^{{tree}}").stdout.strip() == tree_of_head(
        pushing, git
    )


def test_a_local_result_is_not_looked_up_and_the_line_does_not_name_origin(
    pushing: Path, git: Git, log: Path
) -> None:
    assert push(pushing, git).returncode == 0

    result = push(pushing, git, "origin", "main:refs/heads/second")

    assert runs(log) == 1
    assert "origin" not in skip_line(result)


def test_an_origin_without_the_result_runs_the_check_and_warns_of_nothing(
    pushing: Path, git: Git, log: Path
) -> None:
    result = push(pushing, git, "other", "main")

    assert result.returncode == 0
    assert runs(log) == 1
    assert NOT_ASKED not in result.stderr
    assert "prepush-ci:" not in result.stderr


def test_with_the_cache_off_the_result_on_origin_is_ignored(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0
    clone = fresh_clone(pushing, git, tmp_path, log)
    write_config(clone, log, "cache = false")

    result = push(clone, git, "origin", "main:refs/heads/second")

    assert result.returncode == 0
    assert runs(log) == 2


def test_with_the_cache_off_origin_is_not_contacted_at_all(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    write_config(pushing, log, "cache = false")
    git(pushing, "remote", "set-url", "origin", str(tmp_path / "nowhere"))

    result = push(pushing, git, "other", "main")

    assert result.returncode == 0
    assert "prepush-ci:" not in result.stderr


def test_run_does_not_read_the_result_on_origin(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0
    clone = fresh_clone(pushing, git, tmp_path, log)

    assert run_cli(clone).returncode == 0

    assert runs(log) == 2


def test_an_unreachable_origin_is_a_warning_and_a_miss_in_a_push_to_another_remote(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    git(pushing, "remote", "set-url", "origin", str(tmp_path / "nowhere"))

    result = push(pushing, git, "other", "main")

    assert result.returncode == 0
    assert runs(log) == 1
    assert NOT_ASKED in result.stderr


def test_a_hook_that_cannot_tell_the_remote_still_reuses_the_result_from_origin(
    pushing: Path, git: Git, log: Path, tmp_path: Path
) -> None:
    assert push(pushing, git).returncode == 0
    clone = fresh_clone(pushing, git, tmp_path, log)
    install_hook(clone, arguments=False)

    result = push(clone, git, "origin", "main:refs/heads/second")

    assert result.returncode == 0
    assert runs(log) == 1
    assert "origin" in skip_line(result)
