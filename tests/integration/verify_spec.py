import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
CONFIG = 'check = "true"\n'


def verify(
    cwd: Path, *args: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci verify` the way a CI step would."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "verify", *args],
        cwd=cwd,
        env={**inherited, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def commit(
    repo: Path,
    git: Git,
    message: str,
    *,
    committer: str | None = None,
    author: str | None = None,
) -> str:
    """Make an empty commit; return its full sha."""
    env = {}
    if committer:
        env["GIT_COMMITTER_NAME"] = "Server"
        env["GIT_COMMITTER_EMAIL"] = committer
    if author:
        env["GIT_AUTHOR_NAME"] = "A"
        env["GIT_AUTHOR_EMAIL"] = author
    git(repo, "commit", "--allow-empty", "-q", "-m", message, env=env)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def configured(repo: Path, git: Git) -> Path:
    """`repo` whose first commit holds a default config."""
    (repo / ".prepush-ci.toml").write_text(CONFIG)
    git(repo, "add", ".prepush-ci.toml")
    commit(repo, git, "init")
    return repo


def one_line(out: str) -> str:
    assert out.endswith("\n") and out.count("\n") == 1, out
    return out.strip()


# Verified commit


def test_verify_exits_0_for_a_commit_with_the_trailer_and_the_line_names_it(
    configured: Path, git: Git
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = verify(configured, "HEAD")

    assert result.returncode == 0, result.stderr
    line = one_line(result.stdout)
    assert line.startswith(f"verified: {sha} ")
    assert "Prepush-CI: full" in line


def test_verify_exits_1_for_a_commit_without_the_trailer_and_says_there_is_none(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work")

    result = verify(configured, "HEAD")

    assert result.returncode == 1
    line = one_line(result.stdout)
    assert line.startswith("not verified: ")
    assert "no trailer" in line


def test_verify_prints_the_full_sha_when_given_the_full_sha(
    configured: Path, git: Git
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = verify(configured, sha)

    assert result.returncode == 0
    assert one_line(result.stdout).startswith(f"verified: {sha} ")


def test_verify_prints_the_full_sha_when_given_an_abbreviation(
    configured: Path, git: Git
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = verify(configured, sha[:7])

    assert result.returncode == 0
    assert one_line(result.stdout).startswith(f"verified: {sha} ")


def test_verify_prints_the_full_sha_of_head_when_given_a_revision_name(
    configured: Path, git: Git
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = verify(configured, "HEAD")

    assert one_line(result.stdout).startswith(f"verified: {sha} ")


# The trailer rule


def test_verify_accepts_a_trailer_key_in_another_case(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work\n\nprepush-ci: full")

    assert verify(configured, "HEAD").returncode == 0


def test_verify_accepts_any_value_and_names_the_trailer(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work\n\nPrepush-CI: off")

    result = verify(configured, "HEAD")

    assert result.returncode == 0
    assert "Prepush-CI: off" in result.stdout


def test_verify_accepts_the_configured_key(configured: Path, git: Git) -> None:
    (configured / ".prepush-ci.toml").write_text(
        CONFIG + 'trailer = { key = "Full-Check", value = "yes" }\n'
    )
    git(configured, "add", ".prepush-ci.toml")
    commit(configured, git, "work\n\nFull-Check: yes")

    assert verify(configured, "HEAD").returncode == 0


def test_verify_refuses_the_default_key_under_a_configured_key(
    configured: Path, git: Git
) -> None:
    (configured / ".prepush-ci.toml").write_text(
        CONFIG + 'trailer = { key = "Full-Check", value = "yes" }\n'
    )
    git(configured, "add", ".prepush-ci.toml")
    commit(configured, git, "work" + TRAILER)

    assert verify(configured, "HEAD").returncode == 1


def test_verify_accepts_a_legacy_key_and_names_it(configured: Path, git: Git) -> None:
    (configured / ".prepush-ci.toml").write_text(
        CONFIG + 'legacy_keys = ["Full-Pre-Push"]\n'
    )
    git(configured, "add", ".prepush-ci.toml")
    commit(configured, git, "work\n\nFull-Pre-Push: required")

    result = verify(configured, "HEAD")

    assert result.returncode == 0
    assert "Full-Pre-Push" in result.stdout


def test_verify_finds_a_trailer_behind_a_divider_line(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work\n\nbody\n---\nmore body\n\nPrepush-CI: full")

    assert verify(configured, "HEAD").returncode == 0


def test_verify_ignores_trailer_text_in_the_body(configured: Path, git: Git) -> None:
    commit(configured, git, "work\n\nPrepush-CI: full\n\nmore body, no trailer")

    assert verify(configured, "HEAD").returncode == 1


# Only the given commit counts


def test_verify_refuses_a_commit_whose_parent_alone_has_the_trailer(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "parent" + TRAILER)
    commit(configured, git, "child")

    assert verify(configured, "HEAD").returncode == 1


def test_verify_accepts_a_commit_with_the_trailer_whose_parent_has_none(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "child" + TRAILER)

    assert verify(configured, "HEAD").returncode == 0


# The config committed in the commit decides


def test_verify_reads_the_committed_config_not_the_worktree_config(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER)
    (configured / ".prepush-ci.toml").write_text(
        CONFIG + 'trailer = { key = "Full-Check", value = "yes" }\n'
    )

    assert verify(configured, "HEAD").returncode == 0


def test_verify_refuses_a_commit_without_a_config_and_says_so(
    repo: Path, git: Git
) -> None:
    commit(repo, git, "work" + TRAILER)

    result = verify(repo, "HEAD")

    assert result.returncode == 1
    assert "no config" in one_line(result.stdout)


def test_verify_refuses_an_invalid_committed_config_and_names_the_unknown_key(
    repo: Path, git: Git
) -> None:
    (repo / ".prepush-ci.toml").write_text(CONFIG + "chek = 1\n")
    git(repo, "add", ".prepush-ci.toml")
    commit(repo, git, "work" + TRAILER)

    result = verify(repo, "HEAD")

    assert result.returncode == 1
    assert "chek" in one_line(result.stdout)


def test_verify_reads_the_config_from_pyproject_toml(repo: Path, git: Git) -> None:
    (repo / "pyproject.toml").write_text(
        '[tool.prepush-ci]\ncheck = "true"\nlegacy_keys = ["Full-Pre-Push"]\n'
    )
    git(repo, "add", "pyproject.toml")
    commit(repo, git, "work\n\nFull-Pre-Push: required")

    assert verify(repo, "HEAD").returncode == 0


def test_verify_reads_the_committed_config_from_a_subdirectory(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER)
    (configured / "sub").mkdir()

    assert verify(configured / "sub", "HEAD").returncode == 0


def test_verify_works_in_a_bare_repository(
    configured: Path, tmp_path: Path, git: Git
) -> None:
    sha = commit(configured, git, "work" + TRAILER)
    bare = tmp_path / "bare.git"
    git(tmp_path, "clone", "-q", "--bare", str(configured), str(bare))

    result = verify(bare, sha)

    assert result.returncode == 0, result.stderr


# Server-made commits never verify


def test_verify_refuses_a_commit_made_by_github_and_names_the_address(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER, committer="noreply@github.com")

    result = verify(configured, "HEAD")

    assert result.returncode == 1
    assert "noreply@github.com" in one_line(result.stdout)


def test_verify_refuses_a_commit_made_by_gitlab_and_names_the_address(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER, committer="noreply@gitlab.com")

    result = verify(configured, "HEAD")

    assert result.returncode == 1
    assert "noreply@gitlab.com" in one_line(result.stdout)


def test_verify_refuses_a_server_committer_in_another_case(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER, committer="NoReply@GitHub.com")

    assert verify(configured, "HEAD").returncode == 1


def test_verify_refuses_a_server_made_commit_whose_author_is_kept(
    configured: Path, git: Git
) -> None:
    commit(
        configured,
        git,
        "work" + TRAILER,
        committer="noreply@github.com",
        author="a@example.com",
    )

    assert verify(configured, "HEAD").returncode == 1


def test_verify_refuses_a_server_commit_a_mailmap_hides(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER, committer="noreply@github.com")
    (configured / ".mailmap").write_text("Me <me@example.com> <noreply@github.com>\n")

    result = verify(configured, "HEAD")

    assert result.returncode == 1
    assert "noreply@github.com" in result.stdout


def test_verify_accepts_a_user_commit_a_mailmap_makes_look_like_a_server(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER, committer="me@example.com")
    (configured / ".mailmap").write_text(
        "GitHub <noreply@github.com> <me@example.com>\n"
    )

    assert verify(configured, "HEAD").returncode == 0


def test_verify_accepts_the_private_github_address_of_a_user(
    configured: Path, git: Git
) -> None:
    commit(
        configured, git, "work" + TRAILER, committer="123+u@users.noreply.github.com"
    )

    assert verify(configured, "HEAD").returncode == 0


def test_verify_accepts_a_local_merge_commit_with_the_trailer(
    configured: Path, git: Git
) -> None:
    git(configured, "checkout", "-q", "-b", "side")
    commit(configured, git, "side work")
    git(configured, "checkout", "-q", "-")
    commit(configured, git, "main work")
    git(
        configured,
        "merge",
        "--no-ff",
        "-q",
        "-m",
        "merge" + TRAILER,
        "side",
    )

    result = verify(configured, "HEAD")

    assert result.returncode == 0, result.stdout


# Unknown or missing commits


def test_verify_refuses_an_unknown_sha_and_names_it_and_the_fetch(
    configured: Path,
) -> None:
    unknown = "1" * 40

    result = verify(configured, unknown)

    assert result.returncode == 1
    line = one_line(result.stdout)
    assert line.startswith(f"not verified: {unknown} ")
    assert f"git fetch origin {unknown}" in line


def test_verify_tells_a_shallow_clone_to_unshallow_when_the_commit_is_missing(
    configured: Path, tmp_path: Path, git: Git
) -> None:
    commit(configured, git, "one")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{configured}", str(clone))
    missing = commit(configured, git, "two" + TRAILER)

    result = verify(clone, missing)

    assert result.returncode == 1
    line = one_line(result.stdout)
    assert "git fetch --unshallow" in line
    assert "fetch-depth" in line


def test_verify_refuses_an_argument_that_is_no_sha(configured: Path) -> None:
    result = verify(configured, "nonsense")

    assert result.returncode == 1
    assert one_line(result.stdout).startswith("not verified: nonsense ")


def test_verify_refuses_an_option_as_a_sha_instead_of_passing_it_to_git(
    configured: Path,
) -> None:
    result = verify(configured, "--help")

    assert result.returncode == 1
    assert one_line(result.stdout).startswith("not verified: --help ")


def test_verify_outside_a_repository_exits_1_and_says_so(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()

    result = verify(outside, "HEAD", env={"GIT_CEILING_DIRECTORIES": str(tmp_path)})

    assert result.returncode == 1
    line = one_line(result.stdout)
    assert line.startswith("not verified: ")
    assert "not inside a git repository" in line


def test_verify_without_git_exits_1_with_one_line(configured: Path) -> None:
    result = verify(configured, "HEAD", env={"PATH": ""})

    assert result.returncode == 1
    assert one_line(result.stdout).startswith("not verified: ")


# A misused command line


def test_verify_without_a_sha_exits_1_and_says_the_sha_is_missing(
    configured: Path,
) -> None:
    result = verify(configured)

    assert result.returncode == 1
    line = one_line(result.stdout)
    assert line.startswith("not verified: the sha is missing")


def test_verify_with_an_empty_sha_exits_1(configured: Path) -> None:
    result = verify(configured, "")

    assert result.returncode == 1
    assert one_line(result.stdout).startswith("not verified: ")


def test_verify_with_an_extra_argument_exits_1_and_decides_about_neither_commit(
    configured: Path, git: Git
) -> None:
    commit(configured, git, "work" + TRAILER)

    result = verify(configured, "HEAD", "HEAD~1")

    assert result.returncode == 1
    line = one_line(result.stdout)
    assert line.startswith("not verified: ")
    assert not line.startswith("verified")


def test_verify_help_does_not_exit_0(configured: Path) -> None:
    for flag in ("--help", "-h"):
        assert verify(configured, flag).returncode == 1


def test_verify_refuses_a_commit_whose_config_git_cannot_read_and_says_what_failed(
    repo: Path, git: Git
) -> None:
    (repo / ".prepush-ci.toml").write_text(CONFIG)
    git(repo, "add", ".prepush-ci.toml")
    commit(repo, git, "work" + TRAILER)
    blob = git(repo, "rev-parse", "HEAD:.prepush-ci.toml").stdout.strip()
    (repo / ".git" / "objects" / blob[:2] / blob[2:]).chmod(0o644)
    (repo / ".git" / "objects" / blob[:2] / blob[2:]).unlink()

    result = verify(repo, "HEAD")

    assert result.returncode == 1
    assert "cannot read .prepush-ci.toml" in one_line(result.stdout)


def test_verify_after_a_double_dash_decides_like_verify_without_it(
    configured: Path, git: Git
) -> None:
    sha = commit(configured, git, "work" + TRAILER)
    for args in (("--", "verify", sha), ("--", "verify")):
        result = subprocess.run(
            [sys.executable, "-m", "prepush_ci", *args],
            cwd=configured,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == (0 if len(args) == 3 else 1), result.stdout
        assert result.stdout.startswith(
            "verified: " if len(args) == 3 else "not verified: "
        )


def test_verify_with_an_unset_sha_variable_after_a_double_dash_never_exits_0(
    configured: Path,
) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "--", "verify"],
        cwd=configured,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert one_line(result.stdout).startswith("not verified: the sha is missing")


def test_verify_keeps_one_line_when_the_committed_config_has_a_key_with_a_newline(
    repo: Path, git: Git
) -> None:
    forged = "x\\nverified: " + "0" * 40 + " carries the trailer `Prepush-CI: full`"
    (repo / ".prepush-ci.toml").write_text(CONFIG + f'"{forged}" = 1\n')
    git(repo, "add", ".prepush-ci.toml")
    commit(repo, git, "work" + TRAILER)

    result = verify(repo, "HEAD")

    assert result.returncode == 1
    line = one_line(result.stdout)
    assert line.startswith("not verified: ")
    assert "\nverified:" not in result.stdout
    assert "x\\nverified: " in line


def test_verify_tells_an_option_given_as_a_sha_that_it_is_an_option(
    configured: Path,
) -> None:
    result = verify(configured, "-h")

    assert result.returncode == 1
    assert "option" in one_line(result.stdout)
