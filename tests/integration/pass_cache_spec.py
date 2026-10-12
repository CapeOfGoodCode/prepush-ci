"""The result cache against real repositories: what is stored, found, missed and survived."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from prepush_ci import pass_cache
from prepush_ci.core.config import Config, parse_config
from prepush_ci.git import GitError

Git = Callable[..., "subprocess.CompletedProcess[str]"]


def config(**table: object) -> Config:
    return parse_config({"check": "true", **table})


def record(cfg: Config, root: Path) -> None:
    pass_cache.record_pass(cfg, root, pass_cache.current_key(cfg, root))


def has(cfg: Config, root: Path) -> bool:
    return pass_cache.has_pass(cfg, root, pass_cache.current_key(cfg, root))


@pytest.fixture
def committed(repo: Path, git: Git) -> Path:
    """`repo` with one commit."""
    (repo / "a.txt").write_text("a")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def records(repo: Path) -> list[Path]:
    directory = repo / ".git" / "prepush-ci"
    return sorted(directory.iterdir()) if directory.is_dir() else []


def test_a_recorded_pass_is_found_for_the_same_commit_and_config(
    committed: Path,
) -> None:
    record(config(), committed)

    assert has(config(), committed)


def test_nothing_is_found_before_a_pass_was_recorded(committed: Path) -> None:
    assert not has(config(), committed)


def test_a_pass_is_recorded_under_prepush_ci_in_the_git_directory(
    committed: Path,
) -> None:
    record(config(), committed)

    assert len(records(committed)) == 1


def test_a_pass_recorded_from_a_subdirectory_lands_in_the_same_place(
    committed: Path,
) -> None:
    (committed / "sub").mkdir()
    record(config(), committed / "sub")

    assert len(records(committed)) == 1
    assert has(config(), committed)


def test_an_amended_commit_does_not_find_the_pass_of_the_old_one(
    committed: Path, git: Git
) -> None:
    record(config(), committed)
    git(committed, "commit", "-q", "--amend", "-m", "other message")

    assert not has(config(), committed)


def test_a_changed_check_command_does_not_find_the_pass(committed: Path) -> None:
    record(config(), committed)

    assert not has(config(check="true # other"), committed)


def test_a_key_that_does_not_change_the_result_still_finds_the_pass(
    committed: Path,
) -> None:
    record(config(require_up_to_date="origin/main"), committed)

    assert has(
        config(require_up_to_date="origin/main", default_branch="trunk"), committed
    )


def test_a_truncated_record_is_a_miss(committed: Path) -> None:
    record(config(), committed)
    records(committed)[0].write_text("")

    assert not has(config(), committed)


def test_a_record_of_another_key_under_this_keys_name_is_a_miss(
    committed: Path, git: Git
) -> None:
    record(config(), committed)
    first = records(committed)[0]
    (committed / "b.txt").write_text("b")
    git(committed, "add", "b.txt")
    git(committed, "commit", "-q", "-m", "second")
    record(config(), committed)
    second = next(p for p in records(committed) if p != first)
    first.write_text(
        second.read_text()
    )  # the record of the new commit under the old name
    git(committed, "reset", "-q", "--hard", "HEAD~1")

    assert not has(config(), committed)


def test_a_directory_in_place_of_the_record_is_a_miss(committed: Path) -> None:
    record(config(), committed)
    stored = records(committed)[0]
    stored.unlink()
    stored.mkdir()

    assert not has(config(), committed)


def test_nothing_is_recorded_when_the_cache_is_off(committed: Path) -> None:
    record(config(cache=False), committed)

    assert records(committed) == []


def test_a_record_is_ignored_when_the_cache_is_off(committed: Path) -> None:
    record(config(), committed)

    assert not has(config(cache=False), committed)


def test_a_cache_that_cannot_be_written_warns_and_does_not_raise(
    committed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (committed / ".git" / "prepush-ci").write_text("in the way")

    record(config(), committed)

    assert "could not be cached" in capsys.readouterr().err
    assert not has(config(), committed)


def test_a_repository_without_a_commit_has_no_key(repo: Path) -> None:
    with pytest.raises(GitError):
        pass_cache.current_key(config(), repo)
