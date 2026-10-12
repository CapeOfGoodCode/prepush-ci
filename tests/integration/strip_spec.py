import os
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
CONFIG = 'check = "true"\n'
NO_SHA = "0" * 40


def strip(
    cwd: Path, *args: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci strip` the way a user would."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "strip", *args],
        cwd=cwd,
        env={**inherited, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def commit(
    repo: Path, git: Git, message: str, env: dict[str, str] | None = None
) -> str:
    """Make an empty commit; return its sha."""
    git(repo, "commit", "--allow-empty", "-q", "-m", message, env=env)
    return head(repo, git)


def head(repo: Path, git: Git, rev: str = "HEAD") -> str:
    return git(repo, "rev-parse", rev).stdout.strip()


def message_of(repo: Path, git: Git, rev: str = "HEAD") -> str:
    """The message as stored in the commit object, byte for byte."""
    raw = git(repo, "cat-file", "commit", rev).stdout
    return raw.partition("\n\n")[2]


def trailers_of(repo: Path, git: Git, rev: str = "HEAD") -> str:
    return git(
        repo, "log", "-1", "--format=%(trailers:only,unfold)", rev, "--"
    ).stdout.strip()


def has_trailer(repo: Path, git: Git, rev: str = "HEAD") -> bool:
    return "prepush-ci" in trailers_of(repo, git, rev).lower()


@pytest.fixture
def session(repo: Path, git: Git) -> Path:
    """`repo` on `main` with a committed config, then on a branch `topic` forked from it."""
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".prepush-ci.toml").write_text(CONFIG)
    git(repo, "add", ".prepush-ci.toml")
    commit(repo, git, "init")
    git(repo, "checkout", "-q", "-b", "topic")
    return repo


# Strip removes the demanding trailer


def test_strip_removes_the_trailer_from_head(session: Path, git: Git) -> None:
    commit(session, git, "work" + TRAILER)

    result = strip(session)

    assert result.returncode == 0, result.stderr
    assert not has_trailer(session, git)


def test_strip_restores_a_message_made_by_the_commit_msg_hook(
    hooked_repo: Path, git: Git
) -> None:
    git(hooked_repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(hooked_repo, "add", ".prepush-ci.toml")
    commit(hooked_repo, git, "init")
    git(hooked_repo, "checkout", "-q", "-b", "topic")
    commit(hooked_repo, git, "add x", env={"PREPUSH_CI": "full"})
    assert has_trailer(hooked_repo, git)

    result = strip(hooked_repo)

    assert result.returncode == 0, result.stderr
    assert message_of(hooked_repo, git) == "add x\n"


def test_strip_keeps_other_trailers_and_the_rest_of_the_message(
    session: Path, git: Git
) -> None:
    commit(
        session,
        git,
        "work\n\nbody\n\nPrepush-CI: full\nCo-Authored-By: A <a@example.com>",
    )

    strip(session)

    assert message_of(session, git) == (
        "work\n\nbody\n\nCo-Authored-By: A <a@example.com>\n"
    )


def test_strip_removes_the_configured_key_and_leaves_the_default_key(
    session: Path, git: Git
) -> None:
    (session / ".prepush-ci.toml").write_text(
        CONFIG + 'trailer = { key = "Full-Check", value = "yes" }\n'
    )
    git(session, "add", ".prepush-ci.toml")
    commit(session, git, "work\n\nFull-Check: yes\nPrepush-CI: full")

    strip(session)

    assert trailers_of(session, git) == "Prepush-CI: full"


def test_strip_removes_a_legacy_key(session: Path, git: Git) -> None:
    (session / ".prepush-ci.toml").write_text(
        CONFIG + 'legacy_keys = ["Full-Pre-Push"]\n'
    )
    git(session, "add", ".prepush-ci.toml")
    commit(session, git, "work\n\nFull-Pre-Push: required")

    strip(session)

    assert trailers_of(session, git) == ""


def test_strip_removes_a_key_in_another_case_and_any_value(
    session: Path, git: Git
) -> None:
    commit(session, git, "one\n\nprepush-ci: full")
    commit(session, git, "two\n\nPrepush-CI: off")

    strip(session)

    assert not has_trailer(session, git)
    assert not has_trailer(session, git, "HEAD~1")


def test_strip_removes_every_matching_line_of_a_block(session: Path, git: Git) -> None:
    commit(session, git, "work\n\nPrepush-CI: full\nPrepush-CI: full")

    strip(session)

    assert message_of(session, git) == "work\n"


def test_strip_keeps_the_body_around_a_divider_line(session: Path, git: Git) -> None:
    commit(session, git, "work\n\nbody\n---\nmore\n\nPrepush-CI: full")

    strip(session)

    assert message_of(session, git) == "work\n\nbody\n---\nmore\n"


def test_strip_leaves_trailer_text_in_the_body_alone(session: Path, git: Git) -> None:
    sha = commit(session, git, "work\n\nPrepush-CI: full\n\nmore text, no trailer")

    strip(session)

    assert head(session, git) == sha


def test_strip_removes_the_continuation_lines_of_a_folded_trailer(
    session: Path, git: Git
) -> None:
    commit(
        session,
        git,
        "work\n\nCo-Authored-By: A <a@example.com>\nPrepush-CI: full\n  because the db changed",
    )

    strip(session)

    assert trailers_of(session, git) == "Co-Authored-By: A <a@example.com>"
    assert message_of(session, git) == "work\n\nCo-Authored-By: A <a@example.com>\n"


# Strip runs no hooks


def test_strip_with_the_variable_set_does_not_add_the_trailer_back(
    hooked_repo: Path, git: Git
) -> None:
    git(hooked_repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(hooked_repo, "add", ".prepush-ci.toml")
    commit(hooked_repo, git, "init")
    git(hooked_repo, "checkout", "-q", "-b", "topic")
    commit(hooked_repo, git, "one", env={"PREPUSH_CI": "full"})
    commit(hooked_repo, git, "two", env={"PREPUSH_CI": "full"})

    result = strip(hooked_repo, env={"PREPUSH_CI": "full"})

    assert result.returncode == 0, result.stderr
    assert not has_trailer(hooked_repo, git)
    assert not has_trailer(hooked_repo, git, "HEAD~1")


def test_strip_runs_no_git_hook(session: Path, git: Git) -> None:
    markers = session / "markers"
    markers.mkdir()
    for name in ("commit-msg", "pre-commit", "post-commit", "post-rewrite"):
        hook = session / ".git" / "hooks" / name
        hook.write_text(f"#!/bin/sh\ntouch '{(markers / name).as_posix()}'\n")
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    commit(session, git, "work" + TRAILER)
    for marker in markers.iterdir():
        marker.unlink()

    result = strip(session)

    assert result.returncode == 0, result.stderr
    assert not has_trailer(session, git)
    assert list(markers.iterdir()) == []


# The rest of the history stays


def test_strip_keeps_tree_author_and_committer_with_their_dates(
    session: Path, git: Git
) -> None:
    (session / "f.txt").write_text("content\n")
    git(session, "add", "f.txt")
    env = {
        "GIT_AUTHOR_NAME": "Au Thor",
        "GIT_AUTHOR_EMAIL": "author@example.com",
        "GIT_AUTHOR_DATE": "2020-01-02T03:04:05+0100",
        "GIT_COMMITTER_NAME": "Com Mitter",
        "GIT_COMMITTER_EMAIL": "committer@example.com",
        "GIT_COMMITTER_DATE": "2021-02-03T04:05:06+0200",
    }
    old = commit(session, git, "work" + TRAILER, env=env)
    fmt = "--format=%T|%an|%ae|%aI|%cn|%ce|%cI"

    before = git(session, "log", "-1", fmt, old).stdout
    strip(session)
    after = git(session, "log", "-1", fmt, "HEAD").stdout

    assert head(session, git) != old
    assert after == before


def test_strip_keeps_a_server_committer(session: Path, git: Git) -> None:
    commit(
        session,
        git,
        "work" + TRAILER,
        env={
            "GIT_COMMITTER_NAME": "GitHub",
            "GIT_COMMITTER_EMAIL": "noreply@github.com",
        },
    )

    strip(session)

    assert (
        git(session, "log", "-1", "--format=%ce").stdout.strip() == "noreply@github.com"
    )


def test_strip_rewrites_a_merge_and_both_sides_and_keeps_the_trees(
    session: Path, git: Git
) -> None:
    git(session, "checkout", "-q", "-b", "side")
    (session / "side.txt").write_text("side\n")
    git(session, "add", "side.txt")
    commit(session, git, "side work" + TRAILER)
    git(session, "checkout", "-q", "topic")
    (session / "top.txt").write_text("top\n")
    git(session, "add", "top.txt")
    commit(session, git, "top work" + TRAILER)
    git(session, "merge", "--no-ff", "-q", "-m", "merge" + TRAILER, "side")
    old_tree = git(session, "rev-parse", "HEAD^{tree}").stdout
    old_parents = git(session, "rev-list", "--parents", "-1", "HEAD").stdout.split()[1:]

    result = strip(session)

    assert result.returncode == 0, result.stderr
    parents = git(session, "rev-list", "--parents", "-1", "HEAD").stdout.split()[1:]
    assert len(parents) == 2
    assert not set(parents) & set(old_parents)
    for rev in git(session, "rev-list", "main..HEAD").stdout.split():
        assert not has_trailer(session, git, rev)
    assert git(session, "rev-parse", "HEAD^{tree}").stdout == old_tree


def test_strip_leaves_the_base_commit_and_its_sha_alone(
    session: Path, git: Git
) -> None:
    base = commit(session, git, "base" + TRAILER)
    commit(session, git, "work" + TRAILER)

    strip(session, base)

    assert has_trailer(session, git, base)
    assert git(session, "rev-parse", "HEAD~1").stdout.strip() == base
    assert not has_trailer(session, git)


# No needless rewrites


def test_strip_keeps_the_sha_of_the_commits_before_the_first_trailer(
    session: Path, git: Git
) -> None:
    a = commit(session, git, "a")
    commit(session, git, "b" + TRAILER)
    commit(session, git, "c")

    strip(session)

    assert head(session, git, "HEAD~2") == a
    assert message_of(session, git) == "c\n"
    assert git(session, "log", "-1", "--format=%s", "HEAD~1").stdout.strip() == "b"


def test_strip_with_nothing_to_strip_leaves_head_where_it_is_and_reports_zero(
    session: Path, git: Git
) -> None:
    sha = commit(session, git, "work")

    result = strip(session)

    assert result.returncode == 0
    assert head(session, git) == sha
    assert " 0 of 1 " in result.stdout
    assert "force" not in result.stdout


# Which commits are in range


def test_strip_starts_at_the_merge_base_with_the_remote_default_branch(
    session: Path, git: Git
) -> None:
    git(session, "checkout", "-q", "main")
    remote_tip = commit(session, git, "published" + TRAILER)
    git(session, "update-ref", "refs/remotes/origin/main", remote_tip)
    git(session, "reset", "-q", "--hard", "HEAD~1")
    git(session, "checkout", "-q", "-B", "topic", remote_tip)
    commit(session, git, "one" + TRAILER)
    commit(session, git, "two" + TRAILER)

    result = strip(session)

    assert result.returncode == 0, result.stderr
    assert has_trailer(session, git, remote_tip)
    assert not has_trailer(session, git)
    assert not has_trailer(session, git, "HEAD~1")
    assert git(session, "rev-parse", "HEAD~2").stdout.strip() == remote_tip


def test_strip_falls_back_to_the_local_default_branch_without_a_remote(
    session: Path, git: Git
) -> None:
    commit(session, git, "one" + TRAILER)
    commit(session, git, "two" + TRAILER)

    result = strip(session)

    assert result.returncode == 0, result.stderr
    assert "rewrote 2 of 2" in result.stdout


def test_strip_uses_the_configured_default_branch(session: Path, git: Git) -> None:
    git(session, "branch", "trunk", "main")
    (session / ".prepush-ci.toml").write_text(CONFIG + 'default_branch = "trunk"\n')
    git(session, "add", ".prepush-ci.toml")
    commit(session, git, "config" + TRAILER)
    git(session, "update-ref", "refs/remotes/origin/trunk", head(session, git, "main"))

    result = strip(session)

    assert result.returncode == 0, result.stderr
    assert "rewrote 1 of 1" in result.stdout


def test_strip_with_a_base_rewrites_only_the_commits_after_it(
    session: Path, git: Git
) -> None:
    older = commit(session, git, "older" + TRAILER)
    commit(session, git, "newer" + TRAILER)

    strip(session, "HEAD~1")

    assert has_trailer(session, git, older)
    assert not has_trailer(session, git)


def test_strip_without_a_default_branch_or_a_base_asks_for_a_base_and_changes_nothing(
    session: Path, git: Git
) -> None:
    git(session, "branch", "-q", "-m", "main", "other")
    sha = commit(session, git, "work" + TRAILER)

    result = strip(session)

    assert result.returncode == 1
    assert "<base>" in result.stderr
    assert head(session, git) == sha


def orphan(session: Path, git: Git) -> str:
    git(session, "checkout", "-q", "--orphan", "fresh")
    git(session, "rm", "-rfq", ".")
    (session / ".prepush-ci.toml").write_text(CONFIG)
    git(session, "add", ".prepush-ci.toml")
    commit(session, git, "fresh root")
    return commit(session, git, "fresh work" + TRAILER)


def test_strip_on_a_branch_without_common_history_asks_for_a_base_and_changes_nothing(
    session: Path, git: Git
) -> None:
    sha = orphan(session, git)

    result = strip(session)

    assert result.returncode == 1
    assert "<base>" in result.stderr
    assert head(session, git) == sha


def test_strip_with_a_base_works_on_a_branch_without_common_history(
    session: Path, git: Git
) -> None:
    orphan(session, git)

    result = strip(session, "HEAD~1")

    assert result.returncode == 0, result.stderr
    assert "rewrote 1 of 1" in result.stdout


def test_strip_with_an_unknown_base_names_it_and_changes_nothing(
    session: Path, git: Git
) -> None:
    sha = commit(session, git, "work" + TRAILER)

    result = strip(session, "nonsense")

    assert result.returncode == 1
    assert "nonsense" in result.stderr
    assert head(session, git) == sha


def test_strip_with_a_base_that_is_no_ancestor_says_so_and_changes_nothing(
    session: Path, git: Git
) -> None:
    git(session, "checkout", "-q", "-b", "other", "main")
    other = commit(session, git, "other work")
    git(session, "checkout", "-q", "topic")
    sha = commit(session, git, "work" + TRAILER)

    result = strip(session, other)

    assert result.returncode == 1
    assert "not an ancestor of HEAD" in result.stderr
    assert head(session, git) == sha


def test_strip_never_hands_an_option_to_git_as_a_base(session: Path, git: Git) -> None:
    sha = commit(session, git, "work" + TRAILER)

    result = strip(session, "--", "--help-me")

    assert result.returncode == 1
    assert head(session, git) == sha


# Refusals change nothing


def refused(session: Path, git: Git, *args: str, mention: str) -> None:
    before = head(session, git)
    status = git(session, "status", "--porcelain").stdout

    result = strip(session, *args)

    assert result.returncode == 1, result.stdout
    assert mention in result.stderr
    assert git(session, "status", "--porcelain").stdout == status
    assert head(session, git) == before


def test_strip_refuses_an_unstaged_change_and_lists_the_file(
    session: Path, git: Git
) -> None:
    (session / "f.txt").write_text("one\n")
    git(session, "add", "f.txt")
    commit(session, git, "work" + TRAILER)
    (session / "f.txt").write_text("two\n")

    refused(session, git, mention="f.txt")

    assert (session / "f.txt").read_text() == "two\n"
    assert has_trailer(session, git)


def test_strip_refuses_a_staged_change_and_lists_the_file(
    session: Path, git: Git
) -> None:
    commit(session, git, "work" + TRAILER)
    (session / "f.txt").write_text("one\n")
    git(session, "add", "f.txt")

    refused(session, git, mention="f.txt")

    assert has_trailer(session, git)


def test_strip_refuses_an_untracked_file_and_lists_it(session: Path, git: Git) -> None:
    commit(session, git, "work" + TRAILER)
    (session / "scratch.txt").write_text("x\n")

    refused(session, git, mention="scratch.txt")


def test_strip_ignores_an_ignored_file(session: Path, git: Git) -> None:
    (session / ".gitignore").write_text("*.log\n")
    git(session, "add", ".gitignore")
    commit(session, git, "work" + TRAILER)
    (session / "debug.log").write_text("x\n")

    result = strip(session)

    assert result.returncode == 0, result.stderr
    assert (session / "debug.log").read_text() == "x\n"


def test_strip_refuses_a_change_git_hides_and_never_overwrites_it(
    session: Path, git: Git
) -> None:
    (session / "f.txt").write_text("one\n")
    git(session, "add", "f.txt")
    commit(session, git, "work" + TRAILER)
    git(session, "update-index", "--assume-unchanged", "f.txt")
    (session / "f.txt").write_text("local edit\n")

    refused(session, git, mention="f.txt")

    assert (session / "f.txt").read_text() == "local edit\n"


def test_strip_refuses_while_a_rebase_is_in_progress(session: Path, git: Git) -> None:
    commit(session, git, "one" + TRAILER)
    commit(session, git, "two" + TRAILER)
    git(
        session,
        "rebase",
        "-i",
        "main",
        env={"GIT_SEQUENCE_EDITOR": "sed -i '1s/^pick/edit/'"},
    )
    state = (session / ".git" / "rebase-merge").is_dir()

    refused(session, git, mention="a rebase is in progress")

    assert state
    assert (session / ".git" / "rebase-merge").is_dir()


def conflict(session: Path, git: Git) -> str:
    """Leave `topic` and `main` with conflicting changes to f.txt; return the sha on main."""
    (session / "f.txt").write_text("base\n")
    git(session, "add", "f.txt")
    commit(session, git, "f")
    git(session, "checkout", "-q", "-b", "other")
    (session / "f.txt").write_text("other\n")
    git(session, "commit", "-aqm", "other change")
    other = head(session, git)
    git(session, "checkout", "-q", "topic")
    (session / "f.txt").write_text("topic\n")
    git(session, "commit", "-aqm", "topic change" + TRAILER)
    return other


def test_strip_refuses_while_a_merge_is_in_progress(session: Path, git: Git) -> None:
    conflict(session, git)
    git(session, "merge", "other", check=False)

    refused(session, git, mention="a merge is in progress")


def test_strip_refuses_while_a_cherry_pick_is_in_progress(
    session: Path, git: Git
) -> None:
    other = conflict(session, git)
    git(session, "cherry-pick", other, check=False)

    refused(session, git, mention="a cherry-pick is in progress")


def test_strip_refuses_while_a_revert_is_in_progress(session: Path, git: Git) -> None:
    (session / "f.txt").write_text("one\n")
    git(session, "add", "f.txt")
    commit(session, git, "one")
    first = head(session, git)
    (session / "f.txt").write_text("two\n")
    git(session, "commit", "-aqm", "two" + TRAILER)
    git(session, "revert", "--no-edit", first, check=False)

    refused(session, git, mention="a revert is in progress")


def test_strip_refuses_while_git_am_is_in_progress(session: Path, git: Git) -> None:
    (session / "f.txt").write_text("one\n")
    git(session, "add", "f.txt")
    commit(session, git, "one")
    (session / "f.txt").write_text("two\n")
    git(session, "commit", "-aqm", "two")
    patch = session.parent / "two.patch"
    patch.write_text(git(session, "format-patch", "-1", "--stdout").stdout)
    git(session, "reset", "-q", "--hard", "HEAD~1")
    (session / "f.txt").write_text("three\n")
    git(session, "commit", "-aqm", "three" + TRAILER)
    git(session, "am", str(patch), check=False)
    assert (session / ".git" / "rebase-apply" / "applying").exists()

    refused(session, git, mention="git am is in progress")


def test_strip_refuses_while_a_bisect_is_in_progress(session: Path, git: Git) -> None:
    commit(session, git, "one")
    commit(session, git, "two" + TRAILER)
    git(session, "bisect", "start", "--no-checkout", "HEAD", "HEAD~1")
    assert (
        git(session, "symbolic-ref", "-q", "HEAD").stdout.strip() == "refs/heads/topic"
    )

    refused(session, git, mention="a bisect is in progress")


def test_strip_refuses_a_detached_head_and_asks_for_a_branch(
    session: Path, git: Git
) -> None:
    commit(session, git, "work" + TRAILER)
    git(session, "checkout", "-q", "--detach")

    refused(session, git, mention="branch")


# Strip moves only the current branch


def test_strip_leaves_other_branches_and_tags_where_they_are(
    session: Path, git: Git
) -> None:
    old = commit(session, git, "work" + TRAILER)
    git(session, "branch", "keep", old)
    git(session, "tag", "v1", old)

    strip(session)

    assert head(session, git, "keep") == old
    assert head(session, git, "v1^{commit}") == old
    assert head(session, git, "topic") == head(session, git)
    assert head(session, git) != old


def test_the_old_tip_stays_reachable_and_reset_restores_the_branch(
    session: Path, git: Git
) -> None:
    old = commit(session, git, "work" + TRAILER)

    result = strip(session)

    assert old in result.stdout
    git(session, "cat-file", "-e", f"{old}^{{commit}}")
    git(session, "reset", "--hard", old)
    assert head(session, git) == old


def test_the_worktree_is_clean_and_equals_the_old_tip_after_strip(
    session: Path, git: Git
) -> None:
    (session / "f.txt").write_text("one\n")
    git(session, "add", "f.txt")
    commit(session, git, "work" + TRAILER)

    strip(session)

    assert git(session, "status", "--porcelain").stdout == ""
    assert (session / "f.txt").read_text() == "one\n"


# The report


def test_strip_reports_the_counts_both_tips_and_the_force_hint(
    session: Path, git: Git
) -> None:
    commit(session, git, "one")
    old_b = commit(session, git, "two" + TRAILER)
    old_tip = commit(session, git, "three" + TRAILER)
    assert old_b != old_tip

    result = strip(session)

    assert result.returncode == 0
    first = result.stdout.splitlines()[0]
    assert first.startswith("strip:")
    assert "rewrote 2 of 3" in first
    assert old_tip in first and head(session, git) in first
    assert "git push --force-with-lease" in result.stdout


def test_strip_reports_that_nothing_needs_pushing_when_nothing_changed(
    session: Path, git: Git
) -> None:
    commit(session, git, "one")

    result = strip(session)

    assert result.returncode == 0
    assert result.stdout.splitlines()[0].startswith("strip:")
    assert "nothing needs pushing again" in result.stdout
    assert "--force-with-lease" not in result.stdout


# Config and command line


def test_strip_without_a_config_exits_1_and_changes_nothing(
    repo: Path, git: Git
) -> None:
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    commit(repo, git, "init")
    sha = commit(repo, git, "work" + TRAILER)

    result = strip(repo, "HEAD~1")

    assert result.returncode == 1
    assert ".prepush-ci.toml" in result.stderr
    assert head(repo, git) == sha


def test_strip_with_an_invalid_config_names_the_key_and_changes_nothing(
    session: Path, git: Git
) -> None:
    (session / ".prepush-ci.toml").write_text(CONFIG + "chek = 1\n")
    git(session, "add", ".prepush-ci.toml")
    sha = commit(session, git, "work" + TRAILER)

    result = strip(session)

    assert result.returncode == 1
    assert "chek" in result.stderr
    assert head(session, git) == sha


def test_strip_with_an_extra_argument_exits_1_and_changes_nothing(
    session: Path, git: Git
) -> None:
    sha = commit(session, git, "work" + TRAILER)

    result = strip(session, "HEAD~1", "HEAD~2")

    assert result.returncode == 1
    assert head(session, git) == sha


def test_strip_in_a_repository_without_commits_exits_1(repo: Path) -> None:
    result = strip(repo)

    assert result.returncode == 1
    assert "no commit" in result.stderr


def test_strip_outside_a_repository_exits_1(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()

    result = strip(outside, env={"GIT_CEILING_DIRECTORIES": str(tmp_path)})

    assert result.returncode == 1
    assert "worktree" in result.stderr


# A stripped branch pushes without a check


def ran(repo: Path) -> int:
    log = repo.parent / "ran.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def test_a_push_after_strip_runs_no_check_and_a_push_before_it_does(
    pushing_repo: Path, git: Git
) -> None:
    git(pushing_repo, "checkout", "-q", "-b", "topic")
    commit(pushing_repo, git, "one" + TRAILER)
    commit(pushing_repo, git, "two" + TRAILER)
    pushed = git(pushing_repo, "push", "origin", "topic", check=False)
    assert pushed.returncode == 0, pushed.stderr
    assert ran(pushing_repo) == 1

    result = strip(pushing_repo, "main")
    assert result.returncode == 0, result.stderr
    forced = git(
        pushing_repo, "push", "--force-with-lease", "origin", "topic", check=False
    )

    assert forced.returncode == 0, forced.stderr
    assert ran(pushing_repo) == 1
