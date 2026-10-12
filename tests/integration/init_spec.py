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
    """Every file below `root` outside `.git`, as posix paths relative to it."""
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts[:1]
    }


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Contents and modification time of every file below `root` outside `.git`."""
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
