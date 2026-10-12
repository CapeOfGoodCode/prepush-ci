"""`prepush-ci init`: one command sets a repository up, run as users run it."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from prepush_ci.core.config import Config
from prepush_ci.core.config_source import load_config

Git = Callable[..., "subprocess.CompletedProcess[str]"]


def init(
    where: Path,
    *args: str,
    stdin: str | None = None,
    env: dict[str, str | None] | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci init` in `where`; standard input is closed unless `stdin` gives lines."""
    merged: dict[str, str | None] = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "init", *args],
        cwd=where,
        capture_output=True,
        text=True,
        check=False,
        input=stdin,
        stdin=subprocess.DEVNULL if stdin is None else None,
        env={k: v for k, v in merged.items() if v is not None},
    )


def config_of(repo: Path) -> Config:
    """The config the repository's files load as."""

    def read(name: str) -> str | None:
        path = repo / name
        return path.read_text(encoding="utf-8") if path.exists() else None

    return load_config(read(".prepush-ci.toml"), read("pyproject.toml"))


def files(root: Path) -> set[str]:
    """Every file below `root`, as posix paths relative to it; of `.git` only the hooks this
    tool wrote."""
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and (
            p.relative_to(root).parts[0] != ".git"
            or p.relative_to(root).parts[1] == "prepush-ci"
        )
    }


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Contents and modification time of the files `files` lists."""
    return {
        name: ((root / name).read_bytes(), (root / name).stat().st_mtime_ns)
        for name in files(root)
    }


def hooks_path(repo: Path, git: Git) -> str:
    return git(repo, "config", "--get", "core.hooksPath", check=False).stdout.strip()


def test_every_flag_lands_in_the_config(repo: Path) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "make ci",
        "--preflight",
        "make up",
        "--require-env",
        "A",
        "--require-env",
        "B",
        "--default-branch",
        "trunk",
        "--require-up-to-date",
        "upstream/trunk",
        "--hooks",
        "none",
    )

    assert result.returncode == 0, result.stderr
    config = config_of(repo)
    assert config.check == "make ci"
    assert config.preflight == "make up"
    assert config.require_env == ("A", "B")
    assert config.default_branch == "trunk"
    assert config.require_up_to_date == "upstream/trunk"


def test_only_the_check_gives_a_config_with_only_the_check(repo: Path) -> None:
    init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert (repo / ".prepush-ci.toml").read_text() == 'check = "scripts/ci"\n'


def test_a_flag_equal_to_the_default_is_written(repo: Path) -> None:
    init(
        repo,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--default-branch",
        "main",
        "--hooks",
        "none",
    )

    keys = {
        line.split(" = ")[0]
        for line in (repo / ".prepush-ci.toml").read_text().splitlines()
    }
    assert keys == {"check", "default_branch"}


def test_up_to_date_can_be_switched_off(repo: Path) -> None:
    init(
        repo,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--require-up-to-date",
        "false",
        "--hooks",
        "none",
    )

    assert config_of(repo).require_up_to_date is None


def test_a_check_with_quotes_survives(repo: Path) -> None:
    init(
        repo,
        "--non-interactive",
        "--check",
        'sh -c "make ci"',
        "--hooks",
        "none",
    )

    assert config_of(repo).check == 'sh -c "make ci"'


def test_a_check_with_a_character_outside_the_basic_plane_survives(repo: Path) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "echo \N{GRINNING FACE}",
        "--hooks",
        "none",
    )

    assert result.returncode == 0, result.stderr
    assert config_of(repo).check == "echo \N{GRINNING FACE}"


def test_a_check_that_is_not_valid_text_is_refused_with_a_message_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "echo \udcff",
        "--hooks",
        "none",
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "not valid" in result.stderr
    assert not (repo / ".prepush-ci.toml").exists()


def test_no_check_is_a_usage_error_that_writes_nothing(repo: Path) -> None:
    result = init(repo, "--non-interactive", "--hooks", "none")

    assert result.returncode == 2
    assert "--check" in result.stderr
    assert files(repo) == set()


def test_an_empty_check_is_refused_naming_the_key(repo: Path) -> None:
    result = init(repo, "--non-interactive", "--check", "", "--hooks", "none")

    assert result.returncode == 1
    assert "check" in result.stderr
    assert files(repo) == set()


def test_flags_that_agree_with_the_config_change_nothing(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')
    before = snapshot(repo)

    result = init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert snapshot(repo)[".prepush-ci.toml"] == before[".prepush-ci.toml"]


def test_a_flag_that_disagrees_with_the_config_is_refused_before_any_write(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')
    before = snapshot(repo)

    result = init(repo, "--non-interactive", "--check", "make ci", "--hooks", "none")

    assert result.returncode == 1
    assert "check" in result.stderr
    assert snapshot(repo) == before


def test_a_config_that_does_not_load_is_refused_with_its_own_message(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text('chekc = "scripts/ci"\n')
    before = snapshot(repo)

    result = init(repo, "--non-interactive", "--hooks", "native")

    assert result.returncode == 1
    assert "chekc" in result.stderr
    assert snapshot(repo) == before


def test_a_config_in_pyproject_is_used_and_no_file_is_made_for_it(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[tool.prepush-ci]\ncheck = "make ci"\n')

    result = init(repo, "--non-interactive", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert not (repo / ".prepush-ci.toml").exists()


def test_a_detected_manager_gets_the_block_and_git_is_left_alone(
    repo: Path, git: Git
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n"
    )

    result = init(repo, "--non-interactive", "--check", "scripts/ci")

    assert result.returncode == 0, result.stderr
    assert "prepush-ci: begin" in (repo / ".pre-commit-config.yaml").read_text()
    assert hooks_path(repo, git) == ""


def push_after_init(
    repo: Path, tmp_path: Path, git: Git, team_hook: str | None
) -> "subprocess.CompletedProcess[str]":
    """Run `init`, commit what it wrote and one more file with the trailer, and push them to a
    bare remote; `team_hook` is the body of an existing `.git/hooks/pre-push`, if any."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    if team_hook is not None:
        hook = repo / ".git" / "hooks" / "pre-push"
        hook.write_text(f"#!/bin/sh\n{team_hook}\n")
        hook.chmod(0o755)
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "true",
        "--require-up-to-date",
        "false",
    )
    assert result.returncode == 0, result.stderr
    assert hooks_path(repo, git).endswith(".git/prepush-ci/hooks")
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "add init files", env={"PREPUSH_CI": "full"})
    return git(repo, "push", "-q", "origin", "main", check=False)


def test_an_existing_pre_push_hook_still_refuses_a_push_after_init(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    mark = tmp_path / "team-hook-ran"

    push = push_after_init(
        repo, tmp_path, git, f"echo ran > '{mark.as_posix()}'; exit 1"
    )

    assert push.returncode != 0
    assert mark.read_text().strip() == "ran"
    assert "worktree is not clean" not in push.stderr
    assert git(tmp_path, "ls-remote", str(tmp_path / "remote.git")).stdout == ""


def test_the_same_push_goes_through_without_the_existing_pre_push_hook(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    push = push_after_init(repo, tmp_path, git, None)

    assert push.returncode == 0, push.stderr
    assert (
        "refs/heads/main"
        in git(tmp_path, "ls-remote", str(tmp_path / "remote.git")).stdout
    )


def test_no_local_hooks_leaves_git_and_the_hook_files_alone(
    repo: Path, git: Git
) -> None:
    result = init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert hooks_path(repo, git) == ""
    assert not (repo / ".git" / "prepush-ci").exists()


def test_native_hooks_set_core_hooks_path_and_show_what_install_printed(
    repo: Path, git: Git
) -> None:
    result = init(
        repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "native"
    )

    assert result.returncode == 0, result.stderr
    assert hooks_path(repo, git).endswith(".git/prepush-ci/hooks")
    assert "installed:" in result.stdout


def test_one_command_sets_a_repository_up(repo: Path, git: Git) -> None:
    result = init(
        repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "native"
    )

    assert result.returncode == 0, result.stderr
    assert (repo / ".prepush-ci.toml").is_file()
    assert hooks_path(repo, git).endswith(".git/prepush-ci/hooks")


def test_two_managers_end_init_with_the_refusal_before_the_session_hook(
    repo: Path,
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n"
    )
    (repo / "lefthook.yml").write_text("")

    result = init(repo, "--non-interactive", "--check", "scripts/ci")

    assert result.returncode == 1
    assert "--hooks" in result.stderr
    assert not (repo / ".claude").exists()


def last_line(result: "subprocess.CompletedProcess[str]") -> str:
    return result.stdout.rstrip("\n").splitlines()[-1]


def test_outside_a_repository_init_says_so_and_writes_nothing(tmp_path: Path) -> None:
    result = init(tmp_path, "--non-interactive", "--check", "scripts/ci")

    assert result.returncode == 1
    assert "no git repository" in result.stderr
    assert files(tmp_path) == set()


def test_the_config_goes_to_the_root_of_the_worktree_from_a_subdirectory(
    repo: Path,
) -> None:
    sub = repo / "sub"
    sub.mkdir()

    result = init(sub, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert files(repo) == {".prepush-ci.toml"}


def test_a_first_run_ends_with_set_up_and_reports_each_step(repo: Path) -> None:
    result = init(
        repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "native"
    )

    assert "set up" in last_line(result)
    assert "already set up" not in last_line(result)
    assert "written: .prepush-ci.toml" in result.stdout


def test_a_second_run_changes_nothing_and_says_already_set_up(repo: Path) -> None:
    args = ("--non-interactive", "--check", "scripts/ci", "--hooks", "native")
    init(repo, *args)
    before = snapshot(repo)

    second = init(repo, *args)

    assert second.returncode == 0, second.stderr
    assert "already set up" in last_line(second)
    assert "kept: .prepush-ci.toml" in second.stdout
    assert snapshot(repo) == before


def test_a_second_run_with_a_manager_file_leaves_it_alone(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n"
    )
    init(repo, "--non-interactive", "--check", "scripts/ci")
    before = snapshot(repo)

    second = init(repo, "--non-interactive", "--check", "scripts/ci")

    assert "already set up" in last_line(second)
    assert snapshot(repo) == before
