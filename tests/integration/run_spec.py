"""`prepush-ci run`: the pre-push hook's sequence started by hand, against real repositories."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]


def run_cli(
    repo: Path, *, env: dict[str, str] | None = None, cwd: Path | None = None
) -> "subprocess.CompletedProcess[str]":
    inherited = {k: v for k, v in os.environ.items() if k != "PREPUSH_CI"}
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "run"],
        cwd=cwd or repo,
        capture_output=True,
        text=True,
        check=False,
        env={**inherited, **(env or {})},
    )


@pytest.fixture
def log(tmp_path: Path) -> Path:
    """The file the config's commands append to."""
    return tmp_path / "ran.log"


def ran(log: Path) -> list[str]:
    return log.read_text().split() if log.exists() else []


def configure(
    repo: Path, git: Git, log: Path, *lines: str, check: str | None = None
) -> None:
    """Commit a config whose `check` appends `check` to `log`; extra TOML lines follow."""
    body = [
        f'check = "{check or f"echo check >> {log.as_posix()}"}"',
        "require_up_to_date = false",
        *lines,
    ]
    (repo / ".prepush-ci.toml").write_text("\n".join(body) + "\n")
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")


@pytest.fixture
def configured(repo: Path, git: Git, log: Path) -> Path:
    configure(repo, git, log)
    return repo


def records(repo: Path) -> list[Path]:
    directory = repo / ".git" / "prepush-ci"
    return sorted(directory.iterdir()) if directory.is_dir() else []


def test_run_exits_0_when_the_check_passes(configured: Path, log: Path) -> None:
    result = run_cli(configured)

    assert result.returncode == 0
    assert ran(log) == ["check"]


def test_run_exits_1_and_names_the_check_when_it_fails(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, check="exit 1")

    result = run_cli(repo)

    assert result.returncode == 1
    assert "exit 1" in result.stderr


def test_run_from_a_subdirectory_runs_the_check_from_the_repository_root(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, check="echo here > cwd-marker")
    (repo / "sub").mkdir()

    result = run_cli(repo, cwd=repo / "sub")

    assert result.returncode == 0, result.stderr
    assert (repo / "cwd-marker").exists()
    assert not (repo / "sub" / "cwd-marker").exists()


def test_run_refuses_a_dirty_worktree_naming_the_file_without_running_the_check(
    configured: Path, log: Path
) -> None:
    (configured / ".prepush-ci.toml").write_text("# changed\n")

    result = run_cli(configured)

    assert result.returncode == 1
    assert ".prepush-ci.toml" in result.stderr
    assert ran(log) == []


def test_run_refuses_a_change_git_hides_without_running_the_check(
    configured: Path, git: Git, log: Path
) -> None:
    (configured / "a.txt").write_text("a")
    git(configured, "add", "a.txt")
    git(configured, "commit", "-q", "-m", "add a")
    git(configured, "update-index", "--assume-unchanged", "a.txt")

    result = run_cli(configured)

    assert result.returncode == 1
    assert "a.txt" in result.stderr
    assert ran(log) == []


def test_run_stops_at_a_failing_preflight_without_running_the_check(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, 'preflight = "exit 1"')

    result = run_cli(repo)

    assert result.returncode == 1
    assert "preflight" in result.stderr
    assert ran(log) == []


def test_run_runs_the_preflight_before_the_check(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, f'preflight = "echo preflight >> {log.as_posix()}"')

    assert run_cli(repo).returncode == 0

    assert ran(log) == ["preflight", "check"]


def test_run_with_an_unknown_config_key_exits_1_naming_the_key(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, "bogus = 1")

    result = run_cli(repo)

    assert result.returncode == 1
    assert "bogus" in result.stderr
    assert ran(log) == []


def test_run_in_a_repository_without_a_commit_exits_1_without_running_the_check(
    repo: Path, log: Path
) -> None:
    (repo / ".prepush-ci.toml").write_text(
        f'check = "echo check >> {log.as_posix()}"\nrequire_up_to_date = false\n'
    )

    result = run_cli(repo)

    assert result.returncode == 1
    assert "no commit" in result.stderr
    assert ran(log) == []


def test_run_outside_a_repository_exits_1(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "run"],
        cwd=outside,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(tmp_path)},
    )

    assert result.returncode == 1


def test_run_checks_a_commit_without_the_trailer(configured: Path, log: Path) -> None:
    assert run_cli(configured).returncode == 0

    assert ran(log) == ["check"]


def test_run_ignores_prepush_ci_off(configured: Path, log: Path) -> None:
    assert run_cli(configured, env={"PREPUSH_CI": "off"}).returncode == 0

    assert ran(log) == ["check"]


def test_run_runs_the_check_again_after_a_pass_was_cached(
    configured: Path, log: Path
) -> None:
    run_cli(configured)

    assert run_cli(configured).returncode == 0

    assert ran(log) == ["check", "check"]


def test_a_pass_of_run_is_recorded_under_prepush_ci_in_the_git_directory(
    configured: Path,
) -> None:
    run_cli(configured)

    assert len(records(configured)) == 1


def test_a_failing_run_records_nothing(repo: Path, git: Git, log: Path) -> None:
    configure(repo, git, log, check="exit 1")

    run_cli(repo)

    assert records(repo) == []


def test_a_refused_run_records_nothing(configured: Path) -> None:
    (configured / ".prepush-ci.toml").write_text("# changed\n")

    run_cli(configured)

    assert records(configured) == []


def test_run_with_the_cache_off_records_nothing(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, "cache = false")

    assert run_cli(repo).returncode == 0

    assert records(repo) == []


def test_run_that_passes_with_an_unwritable_cache_exits_0_and_warns(
    configured: Path,
) -> None:
    (configured / ".git" / "prepush-ci").write_text("in the way")

    result = run_cli(configured)

    assert result.returncode == 0
    assert "could not be cached" in result.stderr


def test_run_that_fails_with_an_unwritable_cache_still_exits_1(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, check="exit 1")
    (repo / ".git" / "prepush-ci").write_text("in the way")

    assert run_cli(repo).returncode == 1


def test_run_records_the_commit_it_checked_when_the_check_makes_a_commit(
    repo: Path, git: Git, log: Path
) -> None:
    configure(repo, git, log, check="git commit --allow-empty -q -m moved")
    checked = git(repo, "rev-parse", "HEAD").stdout.strip()

    result = run_cli(repo)

    assert result.returncode == 0, result.stderr
    assert git(repo, "rev-parse", "HEAD").stdout.strip() != checked
    assert [p.read_text().split()[0] for p in records(repo)] == [checked]


def test_run_works_in_a_repository_whose_path_has_a_non_ascii_character_under_an_ascii_locale(
    tmp_path: Path, git: Git, log: Path
) -> None:
    where = tmp_path / "dé"
    where.mkdir()
    git(where, "init", "-q")
    git(where, "config", "user.name", "Test")
    git(where, "config", "user.email", "test@example.com")
    git(where, "config", "commit.gpgsign", "false")
    configure(where, git, log)
    ascii_only = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}

    result = run_cli(where, env=ascii_only)

    assert "Traceback" not in result.stderr
    assert result.returncode == 0, result.stderr
    assert ran(log) == ["check"]
