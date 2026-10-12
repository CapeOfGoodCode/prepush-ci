"""`prepush-ci doctor` in real temporary git repositories, started as the module."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Git = Callable[..., "subprocess.CompletedProcess[str]"]

CONFIG = 'check = "true"\nrequire_up_to_date = false\n'


def doctor(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci doctor` in `repo`, without any `PREPUSH_CI` the developer has set."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "doctor", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**inherited, **(env or {})},
    )


def line(result: "subprocess.CompletedProcess[str]", name: str) -> str:
    """The report line of the check `name`."""
    prefixes = (f"ok {name}:", f"fail {name}:", f"skip {name}:")
    found = [text for text in result.stdout.splitlines() if text.startswith(prefixes)]
    assert len(found) == 1, result.stdout
    return found[0]


def status(result: "subprocess.CompletedProcess[str]", name: str) -> str:
    return line(result, name).split()[0]


def fix_after(result: "subprocess.CompletedProcess[str]", name: str) -> str:
    """The line right after the failed check `name`."""
    lines = result.stdout.splitlines()
    return lines[lines.index(line(result, name)) + 1]


# The config check


def test_a_config_in_the_dedicated_file_passes_and_names_it(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')

    result = doctor(repo)

    assert status(result, "config") == "ok"
    assert ".prepush-ci.toml" in line(result, "config")


def test_a_config_in_pyproject_toml_passes_and_names_it(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[tool.prepush-ci]\ncheck = "scripts/ci"\n')

    result = doctor(repo)

    assert status(result, "config") == "ok"
    assert "pyproject.toml" in line(result, "config")


def test_no_config_fails_and_names_both_places_and_init(repo: Path) -> None:
    result = doctor(repo)

    assert status(result, "config") == "fail"
    assert ".prepush-ci.toml" in line(result, "config")
    assert "[tool.prepush-ci]" in line(result, "config")
    assert "prepush-ci init" in fix_after(result, "config")


def test_several_config_problems_are_all_named(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "x"\nfoo = 1\ndefault_branch = 3\n')

    result = doctor(repo)

    assert status(result, "config") == "fail"
    assert "foo" in line(result, "config")
    assert "default_branch" in line(result, "config")


def test_a_malformed_config_file_fails_and_names_the_file(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text("check = = =\n")

    result = doctor(repo)

    assert status(result, "config") == "fail"
    assert ".prepush-ci.toml" in line(result, "config")


def test_a_config_file_that_is_not_text_fails_instead_of_crashing(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_bytes(b"check = \xff\xfe\n")

    result = doctor(repo)

    assert status(result, "config") == "fail"
    assert "cannot read .prepush-ci.toml" in line(result, "config")
    assert "Traceback" not in result.stderr


# Checks that need the config


def test_an_invalid_config_skips_preflight_and_up_to_date_and_nothing_else(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "x"\nfoo = 1\n')

    result = doctor(repo)

    assert status(result, "preflight") == "skip"
    assert status(result, "up-to-date") == "skip"
    assert status(result, "PREPUSH_CI") == "ok"
    assert "config" in line(result, "preflight")


def test_every_check_has_a_line_in_the_fixed_order(repo: Path) -> None:
    result = doctor(repo)

    lines = [text for text in result.stdout.splitlines() if text[0] != " "]
    assert [text.split()[1].rstrip(":") for text in lines[:-1]] == [
        "config",
        "commit-msg",
        "pre-push",
        "preflight",
        "PREPUSH_CI",
        "up-to-date",
    ]


# The PREPUSH_CI check


def test_prepush_ci_full_passes_and_says_so(repo: Path) -> None:
    result = doctor(repo, env={"PREPUSH_CI": "full"})

    assert status(result, "PREPUSH_CI") == "ok"
    assert "full" in line(result, "PREPUSH_CI")


def test_prepush_ci_unset_passes_and_says_no_trailer_is_written(repo: Path) -> None:
    result = doctor(repo)

    assert status(result, "PREPUSH_CI") == "ok"
    assert "no trailer is written" in line(result, "PREPUSH_CI")


def test_a_misspelled_prepush_ci_fails_with_the_valid_values_and_a_fix(
    repo: Path,
) -> None:
    result = doctor(repo, env={"PREPUSH_CI": "ful"})

    text = line(result, "PREPUSH_CI")
    assert status(result, "PREPUSH_CI") == "fail"
    assert "ful" in text and "full" in text and "off" in text
    assert "PREPUSH_CI=full" in fix_after(result, "PREPUSH_CI")


# The expected mode


def test_the_expected_mode_passes_when_the_variable_has_it(repo: Path) -> None:
    result = doctor(repo, "--mode", "full", env={"PREPUSH_CI": "full"})

    assert status(result, "PREPUSH_CI") == "ok"


def test_the_expected_mode_fails_when_the_variable_is_unset(repo: Path) -> None:
    result = doctor(repo, "--mode", "full")

    text = line(result, "PREPUSH_CI")
    assert status(result, "PREPUSH_CI") == "fail"
    assert "unset" in text and "full" in text
    assert "export PREPUSH_CI=full" in fix_after(result, "PREPUSH_CI")


def test_the_expected_unset_fails_when_the_variable_is_set(repo: Path) -> None:
    result = doctor(repo, "--mode", "unset", env={"PREPUSH_CI": "off"})

    assert status(result, "PREPUSH_CI") == "fail"
    assert "unset PREPUSH_CI" in fix_after(result, "PREPUSH_CI")


def test_an_empty_variable_counts_as_unset_for_the_expected_mode(repo: Path) -> None:
    result = doctor(repo, "--mode", "unset", env={"PREPUSH_CI": ""})

    assert status(result, "PREPUSH_CI") == "ok"


def test_an_unknown_mode_exits_2_without_a_check_line_and_names_the_modes(
    repo: Path,
) -> None:
    result = doctor(repo, "--mode", "on")

    assert result.returncode == 2
    assert result.stdout == ""
    for mode in ("full", "off", "unset"):
        assert mode in result.stderr


# Where doctor runs


def test_outside_a_repository_it_exits_1_without_a_check_line(tmp_path: Path) -> None:
    empty = tmp_path / "plain"
    empty.mkdir()

    result = doctor(empty, env={"GIT_CEILING_DIRECTORIES": str(tmp_path)})

    assert result.returncode == 1
    assert result.stdout == ""
    assert "no git repository" in result.stderr


def test_in_a_bare_repository_it_exits_1_without_a_check_line(
    tmp_path: Path, git: Git
) -> None:
    bare = tmp_path / "bare.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))

    result = doctor(bare)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "no working tree" in result.stderr


def test_it_checks_the_whole_worktree_from_a_subdirectory(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text(CONFIG)
    (repo / "src" / "deep").mkdir(parents=True)

    result = doctor(repo / "src" / "deep")

    assert status(result, "config") == "ok"
