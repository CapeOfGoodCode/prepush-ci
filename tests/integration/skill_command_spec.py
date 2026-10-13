"""`prepush-ci skill`: the setup skill of the installed version, printed or written as the project skill."""

import os
import re
import subprocess
import sys
from collections.abc import Callable
from importlib.metadata import PackagePath
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from prepush_ci import skill_command

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "prepush-ci-setup" / "SKILL.md"
PROJECT_SKILL = Path(".claude") / "skills" / "prepush-ci-setup" / "SKILL.md"
Git = Callable[..., "subprocess.CompletedProcess[str]"]


def skill(
    where: Path, *args: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[bytes]":
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "skill", *args],
        cwd=where,
        capture_output=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


def listed_data_file(directory: Path, content: bytes | None) -> list[PackagePath]:
    """What `distribution(...).files` holds for a wheel that installed the skill below `directory`."""
    entry = PackagePath("../../../prepush-ci-setup/SKILL.md")
    entry.dist = SimpleNamespace(locate_file=lambda _: directory / "SKILL.md")  # type: ignore[assignment]
    if content is not None:
        (directory / "SKILL.md").write_bytes(content)
    return [entry]


# --- The skill command prints the installed skill ----------------------------------------------


def test_skill_prints_the_bytes_of_the_skill_outside_a_repository(
    tmp_path: Path,
) -> None:
    result = skill(tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == SKILL.read_bytes()
    assert result.stderr == b""


def test_the_help_lists_the_skill_command(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "skill" in result.stdout.split("{", 1)[1].split("}", 1)[0].split(",")


def test_the_installed_data_file_is_printed_when_no_checkout_has_the_skill(
    tmp_path: Path, capsysbinary: Any
) -> None:
    files = listed_data_file(tmp_path, b"installed skill\n")

    code = skill_command.run(
        False, tmp_path, checkout=tmp_path / "no-checkout.md", files=files
    )

    assert code == 0
    assert capsysbinary.readouterr().out == b"installed skill\n"


def test_the_checkout_file_is_printed_before_the_installed_data_file(
    tmp_path: Path, capsysbinary: Any
) -> None:
    checkout = tmp_path / "checkout.md"
    checkout.write_bytes(b"checkout skill\n")
    files = listed_data_file(tmp_path, b"installed skill\n")

    code = skill_command.run(False, tmp_path, checkout=checkout, files=files)

    assert code == 0
    assert capsysbinary.readouterr().out == b"checkout skill\n"


@pytest.mark.parametrize("installed", [None, b"gone"])
def test_the_command_exits_1_and_says_so_when_neither_file_exists(
    tmp_path: Path, capsysbinary: Any, installed: bytes | None
) -> None:
    files = [] if installed is None else listed_data_file(tmp_path, None)

    code = skill_command.run(
        False, tmp_path, checkout=tmp_path / "no-checkout.md", files=files
    )

    captured = capsysbinary.readouterr()
    assert code == 1
    assert captured.out == b""
    assert b"the skill is not part of this installation" in captured.err


# --- The skill command can write the project skill ---------------------------------------------


def test_write_creates_the_project_skill_and_changes_nothing_else(
    repo: Path, git: Git
) -> None:
    result = skill(repo, "--write")

    assert result.returncode == 0, result.stderr
    assert result.stdout.decode().splitlines() == [
        "wrote .claude/skills/prepush-ci-setup/SKILL.md"
    ]
    assert (repo / PROJECT_SKILL).read_bytes() == SKILL.read_bytes()
    assert git(repo, "status", "--porcelain").stdout.splitlines() == ["?? .claude/"]
    assert git(repo, "diff", "--cached", "--name-only").stdout == ""


def test_write_replaces_an_older_copy(repo: Path) -> None:
    target = repo / PROJECT_SKILL
    target.parent.mkdir(parents=True)
    target.write_text("an older copy\n")

    result = skill(repo, "--write")

    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == SKILL.read_bytes()


def test_write_from_a_subdirectory_writes_under_the_root_of_the_working_tree(
    repo: Path,
) -> None:
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)

    result = skill(sub, "--write")

    assert result.returncode == 0, result.stderr
    assert (repo / PROJECT_SKILL).read_bytes() == SKILL.read_bytes()
    assert not (sub / ".claude").exists()


def test_write_in_a_linked_worktree_writes_under_that_worktree(
    repo: Path, git: Git, tmp_path: Path
) -> None:
    git(repo, "commit", "-q", "--allow-empty", "-m", "start")
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", str(linked))

    result = skill(linked, "--write")

    assert result.returncode == 0, result.stderr
    assert (linked / PROJECT_SKILL).read_bytes() == SKILL.read_bytes()
    assert not (repo / ".claude").exists()


def test_write_outside_a_repository_exits_1_and_writes_nothing(tmp_path: Path) -> None:
    where = tmp_path / "plain"
    where.mkdir()

    result = skill(where, "--write")

    assert result.returncode == 1
    assert b"git repository" in result.stderr
    assert result.stdout == b""
    assert list(where.iterdir()) == []


def test_write_in_a_repository_whose_path_is_non_ascii_works_under_an_ascii_locale(
    tmp_path: Path, git: Git
) -> None:
    where = tmp_path / "dé"
    where.mkdir()
    git(where, "init", "-q")
    ascii_only = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}

    result = skill(where, "--write", env=ascii_only)

    assert result.returncode == 0, result.stderr
    assert b"Traceback" not in result.stderr
    assert (where / PROJECT_SKILL).read_bytes() == SKILL.read_bytes()


# --- A target that cannot be written ends in one line, not a traceback ---------------------------


def blocked_by_a_file(root: Path) -> None:
    (root / ".claude").write_text("not a directory\n")


def blocked_by_a_directory(root: Path) -> None:
    (root / PROJECT_SKILL).mkdir(parents=True)


@pytest.mark.parametrize("block", [blocked_by_a_file, blocked_by_a_directory])
def test_a_target_that_cannot_be_written_exits_1_with_one_line_naming_it_and_the_reason(
    repo: Path,
    git: Git,
    block: Callable[[Path], None],
    printed: Callable[[str], str],
) -> None:
    block(repo)
    before = git(repo, "status", "--porcelain").stdout
    target = printed((repo.resolve() / PROJECT_SKILL).as_posix())

    result = skill(repo, "--write")

    assert result.returncode == 1
    assert b"Traceback" not in result.stderr
    shown = (
        "cp1252" if sys.platform == "win32" else "utf-8"
    )  # what the tool prints is encoded for the terminal
    lines = result.stderr.decode(shown, "replace").splitlines()
    assert len(lines) == 1
    assert re.fullmatch(
        rf"prepush-ci skill: cannot write {re.escape(target)}: \S.*", lines[0]
    )
    assert result.stdout == b""
    assert git(repo, "status", "--porcelain").stdout == before


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows does not keep a trailing space in a name"
)
def test_write_in_a_repository_whose_directory_name_ends_with_a_space_writes_there(
    tmp_path: Path, git: Git
) -> None:
    where = tmp_path / "spaced "
    where.mkdir()
    git(where, "init", "-q")

    result = skill(where, "--write")

    assert result.returncode == 0, result.stderr
    assert (where / PROJECT_SKILL).read_bytes() == SKILL.read_bytes()
    assert not (tmp_path / "spaced" / ".claude").exists()
