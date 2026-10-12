import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
NO_SHA = "0" * 40


def commit(repo: Path, git: Git, message: str) -> str:
    """Make an empty commit with `message`; return its sha."""
    git(repo, "commit", "--allow-empty", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def push(
    repo: Path, git: Git, *args: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", "origin", *args, env=env, check=False)


def ran(repo: Path) -> int:
    """How many times the check ran (it appends a line to `ran.log` next to the repository)."""
    log = repo.parent / "ran.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def remote_has(repo: Path, git: Git, ref: str) -> bool:
    remote = repo.parent / "remote.git"
    return git(remote, "rev-parse", "--verify", "-q", ref, check=False).returncode == 0


def run_hook(
    cwd: Path,
    stdin: str = "",
    env: dict[str, str] | None = None,
    args: tuple[str, ...] = (),
) -> "subprocess.CompletedProcess[str]":
    """Run the hook directly, the way git or pre-commit would start it."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "hook", "pre-push", *args],
        cwd=cwd,
        input=stdin,
        env={**inherited, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def ref_line(local_ref: str, sha: str, remote_ref: str) -> str:
    return f"{local_ref} {sha} {remote_ref} {NO_SHA}\n"


def head(repo: Path, git: Git) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.strip()


# Pushed refs


def test_native_git_push_runs_the_check_on_a_commit_with_the_trailer(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1
    assert remote_has(pushing_repo, git, "refs/heads/main")


def test_no_refs_on_standard_input_and_no_pre_commit_variables_exit_zero_without_a_check(
    pushing_repo: Path,
) -> None:
    result = run_hook(pushing_repo)

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0


def test_git_arguments_remote_name_and_url_are_accepted(pushing_repo: Path) -> None:
    result = run_hook(pushing_repo, args=("origin", "/some/url"))

    assert result.returncode == 0, result.stderr


def test_a_ref_line_the_hook_cannot_read_refuses_the_push(pushing_repo: Path) -> None:
    result = run_hook(pushing_repo, stdin="garbage\n")

    assert result.returncode != 0
    assert "garbage" in result.stderr


# The pre-commit fallback


def test_pre_commit_variables_run_the_check_on_the_given_commit(
    pushing_repo: Path, git: Git
) -> None:
    sha = commit(pushing_repo, git, "work" + TRAILER)
    env = {"PRE_COMMIT_TO_REF": sha, "PRE_COMMIT_REMOTE_BRANCH": "refs/heads/main"}

    result = run_hook(pushing_repo, env=env)

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


def test_pre_commit_without_a_remote_branch_runs_the_check_on_the_commit(
    pushing_repo: Path, git: Git
) -> None:
    sha = commit(pushing_repo, git, "work" + TRAILER)

    result = run_hook(pushing_repo, env={"PRE_COMMIT_TO_REF": sha})

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


def test_pre_commit_pushing_the_root_commit_resolves_the_local_branch(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "checkout", "-q", "--orphan", "root")
    commit(pushing_repo, git, "first" + TRAILER)
    env = {
        "PRE_COMMIT_LOCAL_BRANCH": "refs/heads/root",
        "PRE_COMMIT_REMOTE_BRANCH": "refs/heads/root",
    }

    result = run_hook(pushing_repo, env=env)

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


def test_an_unresolvable_local_branch_refuses_the_push_and_names_it(
    pushing_repo: Path,
) -> None:
    result = run_hook(pushing_repo, env={"PRE_COMMIT_LOCAL_BRANCH": "refs/heads/gone"})

    assert result.returncode != 0
    assert "refs/heads/gone" in result.stderr


# Only branch updates count


def test_a_tag_push_succeeds_without_a_check(pushing_repo: Path, git: Git) -> None:
    commit(pushing_repo, git, "work" + TRAILER)
    git(pushing_repo, "tag", "v1")

    result = push(pushing_repo, git, "v1")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0


def test_a_branch_deletion_succeeds_without_a_check(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "branch", "old")
    assert push(pushing_repo, git, "old").returncode == 0

    result = push(pushing_repo, git, "--delete", "old")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0
    assert not remote_has(pushing_repo, git, "refs/heads/old")


def test_a_tag_push_in_a_repository_without_a_config_succeeds(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "rm", "-q", ".prepush-ci.toml")
    commit(pushing_repo, git, "drop the config")
    git(pushing_repo, "tag", "v1")

    result = push(pushing_repo, git, "v1")

    assert result.returncode == 0, result.stderr


def test_a_push_to_a_ref_that_is_not_a_branch_succeeds_without_a_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "HEAD:refs/notes/x")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0


def test_a_branch_pushed_under_another_local_name_runs_the_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "HEAD:refs/heads/x")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


# A tip demands the check when it carries the trailer


def test_a_tip_with_the_trailer_runs_the_check(pushing_repo: Path, git: Git) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    push(pushing_repo, git, "main")

    assert ran(pushing_repo) == 1


def test_a_tip_without_a_trailer_is_pushed_without_a_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work")

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0


def test_a_trailer_on_an_earlier_commit_of_the_push_does_not_demand_the_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "first" + TRAILER)
    commit(pushing_repo, git, "second")

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0


def test_a_trailer_key_in_another_case_runs_the_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work\n\nprepush-ci: full")

    push(pushing_repo, git, "main")

    assert ran(pushing_repo) == 1


def test_any_value_of_the_trailer_runs_the_check(pushing_repo: Path, git: Git) -> None:
    commit(pushing_repo, git, "work\n\nPrepush-CI: off")

    push(pushing_repo, git, "main")

    assert ran(pushing_repo) == 1


def test_a_legacy_key_runs_the_check(pushing_repo: Path, git: Git) -> None:
    ran_log = pushing_repo.parent / "ran.log"
    (pushing_repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran_log}"\nlegacy_keys = ["Full-Pre-Push"]\n'
    )
    git(pushing_repo, "commit", "-q", "-a", "-m", "legacy key")
    commit(pushing_repo, git, "work\n\nFull-Pre-Push: required")

    push(pushing_repo, git, "main")

    assert ran(pushing_repo) == 1


def test_a_configured_key_runs_the_check(pushing_repo: Path, git: Git) -> None:
    ran_log = pushing_repo.parent / "ran.log"
    (pushing_repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran_log}"\n'
        'trailer = { key = "Full-Check", value = "yes" }\n'
    )
    git(pushing_repo, "commit", "-q", "-a", "-m", "configured key")
    commit(pushing_repo, git, "work\n\nFull-Check: yes")

    push(pushing_repo, git, "main")

    assert ran(pushing_repo) == 1


def test_a_trailer_behind_a_divider_line_runs_the_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work\n\nbody\n---\nmore body" + TRAILER)

    push(pushing_repo, git, "main")

    assert ran(pushing_repo) == 1


def test_trailer_text_in_the_body_does_not_demand_the_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work\n\nPrepush-CI: full\n\nand more text afterwards")

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0


# Which config decides the demand


def test_a_key_set_only_by_the_worktree_config_demands_the_check(
    pushing_repo: Path, git: Git
) -> None:
    ran_log = pushing_repo.parent / "ran.log"
    # The tip commits pyproject.toml; the dedicated file that wins in the worktree is ignored.
    (pushing_repo / "pyproject.toml").write_text('[tool.prepush-ci]\ncheck = "true"\n')
    (pushing_repo / ".gitignore").write_text(".prepush-ci.toml\n")
    git(pushing_repo, "rm", "-q", "--cached", ".prepush-ci.toml")
    (pushing_repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran_log}"\nlegacy_keys = ["Full-Pre-Push"]\n'
    )
    git(pushing_repo, "add", "pyproject.toml", ".gitignore")
    git(pushing_repo, "commit", "-q", "-m", "work\n\nFull-Pre-Push: required")

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


def test_a_tip_without_a_config_adds_no_keys_and_the_worktree_config_decides(
    pushing_repo: Path, git: Git
) -> None:
    (pushing_repo / ".gitignore").write_text(".prepush-ci.toml\n")
    git(pushing_repo, "rm", "-q", "--cached", ".prepush-ci.toml")
    git(pushing_repo, "add", ".gitignore")
    git(pushing_repo, "commit", "-q", "-m", "work" + TRAILER)

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


def test_an_invalid_config_in_the_tip_refuses_the_push_and_names_the_unknown_key(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "checkout", "-q", "-b", "bad")
    (pushing_repo / ".prepush-ci.toml").write_text('check = "true"\nbogus = 1\n')
    git(pushing_repo, "commit", "-q", "-a", "-m", "work")
    git(pushing_repo, "checkout", "-q", "main")

    result = push(pushing_repo, git, "bad")

    assert result.returncode != 0
    assert "bogus" in result.stderr
    assert not remote_has(pushing_repo, git, "refs/heads/bad")


# A branch push needs a valid config


def test_a_branch_push_without_a_config_is_aborted_and_the_error_names_the_file(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "rm", "-q", ".prepush-ci.toml")
    commit(pushing_repo, git, "drop the config")

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert ".prepush-ci.toml" in result.stderr


def test_a_branch_push_with_an_invalid_config_is_aborted_and_the_error_names_the_key(
    pushing_repo: Path, git: Git
) -> None:
    (pushing_repo / ".prepush-ci.toml").write_text('check = "true"\nbogus = 1\n')
    git(pushing_repo, "commit", "-q", "-a", "-m", "break the config")

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert "bogus" in result.stderr


# Unknown variable values are refused


def test_a_misspelled_variable_aborts_the_push_and_names_full_and_off(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work")

    result = push(pushing_repo, git, "main", env={"PREPUSH_CI": "ful"})

    assert result.returncode != 0
    assert "full" in result.stderr
    assert "off" in result.stderr
    assert ran(pushing_repo) == 0


def test_a_misspelled_variable_is_refused_before_any_ref_is_read(
    pushing_repo: Path,
) -> None:
    result = run_hook(pushing_repo, stdin="garbage\n", env={"PREPUSH_CI": "ful"})

    assert "garbage" not in result.stderr
    assert "PREPUSH_CI" in result.stderr


# A demanding tip runs the check


def test_a_passing_check_lets_the_push_through(pushing_repo: Path, git: Git) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert remote_has(pushing_repo, git, "refs/heads/main")


def test_a_failing_check_aborts_the_push_and_the_output_names_the_check(
    pushing_repo: Path, git: Git
) -> None:
    (pushing_repo / ".prepush-ci.toml").write_text('check = "exit 1"\n')
    git(pushing_repo, "commit", "-q", "-a", "-m", "work" + TRAILER)

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert "the check failed" in result.stderr
    assert "exit 1" in result.stderr
    assert not remote_has(pushing_repo, git, "refs/heads/main")


def test_the_check_runs_with_the_variable_unset(pushing_repo: Path, git: Git) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    push(pushing_repo, git, "main", env={})

    assert ran(pushing_repo) == 1


def test_the_check_runs_from_the_repository_root_when_pushing_from_a_subdirectory(
    pushing_repo: Path, git: Git
) -> None:
    marker = pushing_repo.parent / "cwd.txt"
    (pushing_repo / ".prepush-ci.toml").write_text(f'check = "pwd > {marker}"\n')
    (pushing_repo / "sub").mkdir()
    git(pushing_repo, "add", "-A")
    git(pushing_repo, "commit", "-q", "-a", "-m", "work" + TRAILER)

    result = push(pushing_repo / "sub", git, "main")

    assert result.returncode == 0, result.stderr
    assert marker.read_text().strip() == str(pushing_repo.resolve())


def test_two_refs_with_the_same_tip_run_the_check_once(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "main:a", "main:b")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


# The pushed tip must be the checked-out HEAD
def test_a_key_set_only_by_the_tips_config_demands_the_check(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "checkout", "-q", "-b", "feature")
    (pushing_repo / ".prepush-ci.toml").write_text(
        'check = "true"\ntrailer = { key = "Full-Check", value = "yes" }\n'
    )
    git(pushing_repo, "commit", "-q", "-a", "-m", "work\n\nFull-Check: yes")
    git(pushing_repo, "checkout", "-q", "main")

    result = push(pushing_repo, git, "feature")

    assert result.returncode != 0
    assert "HEAD" in result.stderr
    assert not remote_has(pushing_repo, git, "refs/heads/feature")


def test_pushing_another_branch_is_refused_without_a_check_and_the_reason_names_head(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "checkout", "-q", "-b", "other")
    commit(pushing_repo, git, "work" + TRAILER)
    git(pushing_repo, "checkout", "-q", "main")

    result = push(pushing_repo, git, "other")

    assert result.returncode != 0
    assert "HEAD" in result.stderr
    assert ran(pushing_repo) == 0


def test_pushing_an_older_commit_is_refused_without_a_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "older" + TRAILER)
    commit(pushing_repo, git, "newer" + TRAILER)

    result = push(pushing_repo, git, "HEAD~1:refs/heads/x")

    assert result.returncode != 0
    assert ran(pushing_repo) == 0


def test_two_different_demanding_tips_are_refused_without_a_check(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "checkout", "-q", "-b", "a")
    commit(pushing_repo, git, "a" + TRAILER)
    git(pushing_repo, "checkout", "-q", "-b", "b", "main")
    commit(pushing_repo, git, "b" + TRAILER)

    result = push(pushing_repo, git, "a", "b")

    assert result.returncode != 0
    assert ran(pushing_repo) == 0


def test_a_detached_head_with_the_trailer_is_checked(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)
    git(pushing_repo, "checkout", "-q", "--detach")

    result = push(pushing_repo, git, "HEAD:refs/heads/x")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


# The worktree must be clean


def test_an_unstaged_change_refuses_the_push_without_a_check_and_names_the_file(
    pushing_repo: Path, git: Git
) -> None:
    (pushing_repo / "tracked.txt").write_text("one\n")
    git(pushing_repo, "add", "tracked.txt")
    git(pushing_repo, "commit", "-q", "-m", "work" + TRAILER)
    (pushing_repo / "tracked.txt").write_text("two\n")

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert "tracked.txt" in result.stderr
    assert ran(pushing_repo) == 0


def test_a_staged_change_refuses_the_push_without_a_check(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)
    (pushing_repo / "staged.txt").write_text("x\n")
    git(pushing_repo, "add", "staged.txt")

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert ran(pushing_repo) == 0


def test_an_untracked_file_refuses_the_push_and_names_the_file(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)
    (pushing_repo / "scratch.txt").write_text("x\n")

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert "scratch.txt" in result.stderr
    assert ran(pushing_repo) == 0


def test_an_ignored_file_does_not_make_the_worktree_dirty(
    pushing_repo: Path, git: Git
) -> None:
    (pushing_repo / ".gitignore").write_text("junk.txt\n")
    git(pushing_repo, "add", ".gitignore")
    git(pushing_repo, "commit", "-q", "-m", "work" + TRAILER)
    (pushing_repo / "junk.txt").write_text("x\n")

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 1


def test_an_assume_unchanged_file_refuses_the_push_without_a_check_and_names_it(
    pushing_repo: Path, git: Git
) -> None:
    (pushing_repo / "tracked.txt").write_text("one\n")
    git(pushing_repo, "add", "tracked.txt")
    git(pushing_repo, "commit", "-q", "-m", "work" + TRAILER)
    git(pushing_repo, "update-index", "--assume-unchanged", "tracked.txt")
    (pushing_repo / "tracked.txt").write_text("two\n")
    assert git(pushing_repo, "status", "--short").stdout == ""

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert "tracked.txt" in result.stderr
    assert ran(pushing_repo) == 0
    assert not remote_has(pushing_repo, git, "refs/heads/main")


def test_a_sparse_checkout_that_hides_a_file_refuses_the_push_and_names_it(
    pushing_repo: Path, git: Git
) -> None:
    (pushing_repo / "sub").mkdir()
    (pushing_repo / "sub" / "t.sh").write_text("exit 1\n")
    git(pushing_repo, "add", "sub/t.sh")
    git(pushing_repo, "commit", "-q", "-m", "work" + TRAILER)
    git(pushing_repo, "sparse-checkout", "set", "--no-cone", "/*", "!/sub/")
    assert not (pushing_repo / "sub").exists()
    assert git(pushing_repo, "status", "--short").stdout == ""

    result = push(pushing_repo, git, "main")

    assert result.returncode != 0
    assert "sub/t.sh" in result.stderr
    assert ran(pushing_repo) == 0
    assert not remote_has(pushing_repo, git, "refs/heads/main")


def test_a_hidden_file_does_not_matter_for_a_tip_without_the_trailer(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "update-index", "--assume-unchanged", ".prepush-ci.toml")
    commit(pushing_repo, git, "work")

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr
    assert ran(pushing_repo) == 0


def test_a_dirty_worktree_does_not_matter_for_a_tip_without_the_trailer(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work")
    (pushing_repo / ".prepush-ci.toml").write_text('check = "true"\n# edited\n')

    result = push(pushing_repo, git, "main")

    assert result.returncode == 0, result.stderr


# Off refuses a demanding tip


def test_off_refuses_a_tip_with_the_trailer_without_a_check_and_names_the_variable(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "main", env={"PREPUSH_CI": "off"})

    assert result.returncode != 0
    assert "PREPUSH_CI=off" in result.stderr
    assert ran(pushing_repo) == 0
    assert not remote_has(pushing_repo, git, "refs/heads/main")


def test_off_pushes_a_tip_without_the_trailer_without_a_hint(
    pushing_repo: Path, git: Git
) -> None:
    commit(pushing_repo, git, "work")

    result = push(pushing_repo, git, "main", env={"PREPUSH_CI": "off"})

    assert result.returncode == 0, result.stderr
    assert "git commit --amend --no-edit" not in result.stderr
