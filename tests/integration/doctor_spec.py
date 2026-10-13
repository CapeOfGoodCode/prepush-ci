"""`prepush-ci doctor` in real temporary git repositories, started as the module."""

import http.server
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

CONFIG = 'check = "true"\nrequire_up_to_date = false\n'


def doctor(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
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
        timeout=timeout,
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


# Hooks


PRE_COMMIT_CONFIG = (
    "repos:\n  - repo: local\n    hooks:\n"
    "      - id: lint\n        name: lint\n        entry: 'true'\n"
    "        language: system\n"
)
LEFTHOOK_CONFIG = (
    "pre-commit:\n  commands:\n    lint:\n      run: make lint\n"
    "pre-push:\n  commands:\n    test:\n      run: make test\n"
)
NATIVE = Path(".git") / "prepush-ci" / "hooks"
POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows has no executable bit"
)


def install(repo: Path, *args: str) -> None:
    """Run `prepush-ci install` in `repo`; it must succeed."""
    subprocess.run(
        [sys.executable, "-m", "prepush_ci", "install", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def pre_commit_install(repo: Path, tmp_path: Path) -> None:
    """The step the fix line asks for: `pre-commit install` installs the hook types the config names."""
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home")},
    )


def activate(repo: Path, directory: Path, text: str, *hooks: str) -> None:
    """Executable scripts named `hooks` in `directory` that contain `text`."""
    directory.mkdir(parents=True, exist_ok=True)
    for hook in hooks:
        path = directory / hook
        path.write_text(f"#!/bin/sh\n# {text}\n")
        path.chmod(0o755)


def both(result: "subprocess.CompletedProcess[str]") -> tuple[str, str]:
    return status(result, "commit-msg"), status(result, "pre-push")


def hook_lines(result: "subprocess.CompletedProcess[str]") -> str:
    """The two hook lines and the fix line after each failed one."""
    out = result.stdout.splitlines()
    kept: list[str] = []
    for index, text in enumerate(out):
        if text.startswith(("ok commit-msg", "fail commit-msg")) or text.startswith(
            ("ok pre-push", "fail pre-push")
        ):
            kept.append(text)
            if text.startswith("fail") and out[index + 1].startswith("  fix:"):
                kept.append(out[index + 1])
    return "\n".join(kept)


def test_nothing_is_set_up_fails_the_config_and_both_hooks_and_exits_1(
    repo: Path,
) -> None:
    result = doctor(repo)

    assert result.returncode == 1
    assert status(result, "config") == "fail"
    assert both(result) == ("fail", "fail")
    assert len(result.stdout.splitlines()) >= 6


def test_a_failure_does_not_stop_the_later_checks(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "x"\nfoo = 1\n')
    install(repo)

    result = doctor(repo)

    assert status(result, "config") == "fail"
    assert both(result) == ("ok", "ok")
    assert result.returncode == 1


def test_a_skip_is_not_a_pass_and_the_last_line_counts_it(repo: Path) -> None:
    install(repo)

    result = doctor(repo, env={"PREPUSH_CI": "full"})

    assert status(result, "config") == "fail"
    assert status(result, "preflight") == "skip"
    assert status(result, "up-to-date") == "skip"
    assert result.returncode == 1
    assert result.stdout.splitlines()[-1] == "3 of 6 checks did not pass"


def test_the_hook_checks_do_not_read_the_config(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text("check = = =\n")
    install(repo)

    result = doctor(repo)

    assert both(result) == ("ok", "ok")


def test_missing_hooks_are_failures_with_the_install_command_as_the_fix(
    repo: Path,
) -> None:
    result = doctor(repo)

    for name in ("commit-msg", "pre-push"):
        assert status(result, name) == "fail"
        assert fix_after(result, name).startswith("  fix:")
        assert "prepush-ci install" in fix_after(result, name)


# Native hooks


def test_native_hooks_installed_by_install_pass(repo: Path) -> None:
    install(repo)

    assert both(doctor(repo)) == ("ok", "ok")


def test_native_hooks_before_install_fail_and_name_core_hooks_path(repo: Path) -> None:
    result = doctor(repo)

    for name in ("commit-msg", "pre-push"):
        assert status(result, name) == "fail"
        assert "core.hooksPath" in line(result, name)


def test_hooks_that_another_tool_took_over_fail_and_name_its_directory(
    repo: Path, git: Git
) -> None:
    install(repo)
    git(repo, "config", "core.hooksPath", ".githooks")

    result = doctor(repo)

    for name in ("commit-msg", "pre-push"):
        assert status(result, name) == "fail"
        assert ".githooks" in line(result, name)


def test_a_deleted_native_script_fails_only_its_own_check(repo: Path) -> None:
    install(repo)
    (repo / NATIVE / "pre-push").unlink()

    result = doctor(repo)

    assert both(result) == ("ok", "fail")
    assert "pre-push" in line(result, "pre-push")


@POSIX_ONLY
def test_a_native_script_that_is_not_executable_fails_and_says_so(repo: Path) -> None:
    install(repo)
    (repo / NATIVE / "commit-msg").chmod(0o644)

    result = doctor(repo)

    assert both(result) == ("fail", "ok")
    assert "not executable" in line(result, "commit-msg")


def test_a_vanished_interpreter_fails_both_hooks_and_names_its_path(repo: Path) -> None:
    install(repo)
    (repo / NATIVE / "python").write_text("/nonexistent/interpreter/python\n")

    result = doctor(repo)

    for name in ("commit-msg", "pre-push"):
        assert status(result, name) == "fail"
        assert "/nonexistent/interpreter/python" in line(result, name)


def test_a_missing_python_file_fails_both_hooks(repo: Path) -> None:
    install(repo)
    (repo / NATIVE / "python").unlink()

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert "python" in line(result, "pre-push")


def test_native_hooks_installed_in_the_main_worktree_pass_in_a_linked_one(
    repo: Path, git: Git, tmp_path: Path
) -> None:
    git(repo, "commit", "--allow-empty", "-q", "-m", "first")
    install(repo)
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", str(linked))

    assert both(doctor(linked)) == ("ok", "ok")


def test_a_relative_hooks_path_is_judged_from_the_worktree_root(
    repo: Path, git: Git
) -> None:
    install(repo)
    git(repo, "config", "core.hooksPath", ".git/prepush-ci/hooks")
    (repo / "sub").mkdir()

    assert both(doctor(repo / "sub")) == ("ok", "ok")


# The choice of hooks


def test_a_detected_manager_is_judged_without_hooks(repo: Path, tmp_path: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    install(repo)
    pre_commit_install(repo, tmp_path)

    assert both(doctor(repo)) == ("ok", "ok")


def test_native_hooks_can_be_forced_next_to_a_manager(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    install(repo, "--hooks", "native")

    assert both(doctor(repo, "--hooks", "native")) == ("ok", "ok")


def test_an_unknown_hooks_value_exits_2_without_a_check_line_and_lists_the_values(
    repo: Path,
) -> None:
    result = doctor(repo, "--hooks", "jenkins")

    assert result.returncode == 2
    assert result.stdout == ""
    for value in ("native", "pre-commit", "husky", "lefthook", "none"):
        assert value in result.stderr


def test_native_hooks_next_to_a_manager_fail_without_hooks_and_the_fix_names_native(
    repo: Path,
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    install(repo, "--hooks", "native")

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert "--hooks native" in fix_after(result, "commit-msg")
    assert "--hooks native" in fix_after(result, "pre-push")


def test_two_managers_fail_both_hooks_and_name_them_and_the_option(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    for word in ("pre-commit", "lefthook", "--hooks"):
        assert word in line(result, "commit-msg")
        assert word in line(result, "pre-push")


def test_the_option_settles_two_managers(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(repo, "--hooks", "lefthook")
    activate(repo, repo / ".git" / "hooks", "lefthook", "commit-msg", "pre-push")

    assert both(doctor(repo, "--hooks", "lefthook")) == ("ok", "ok")


def test_a_named_manager_that_is_not_set_up_fails_and_names_its_file(
    repo: Path,
) -> None:
    result = doctor(repo, "--hooks", "pre-commit")

    assert both(result) == ("fail", "fail")
    assert ".pre-commit-config.yaml" in line(result, "commit-msg")
    assert ".pre-commit-config.yaml" in line(result, "pre-push")


def test_no_local_hooks_wanted_passes_both_hooks_and_says_so(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)

    result = doctor(repo, "--hooks", "none")

    assert both(result) == ("ok", "ok")
    assert "no local hooks are wanted" in line(result, "commit-msg") or (
        "no local hooks wanted" in line(result, "commit-msg")
    )
    assert "no local hooks wanted" in line(result, "pre-push")


def test_install_does_not_accept_none(repo: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "install", "--hooks", "none"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2


# A manager's block


def test_a_pre_commit_file_without_the_block_fails_and_names_the_file(
    repo: Path,
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert ".pre-commit-config.yaml" in line(result, "commit-msg")
    assert ".pre-commit-config.yaml" in line(result, "pre-push")


def test_a_pre_commit_file_with_an_unfinished_block_fails_instead_of_crashing(
    repo: Path,
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        PRE_COMMIT_CONFIG + "  # prepush-ci: begin\n"
    )

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert "begin" in line(result, "commit-msg")


def test_a_manager_file_that_is_not_text_has_no_block(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_bytes(b"repos: \xff\xfe\n")

    result = doctor(repo)

    assert both(result) == ("fail", "fail")


def test_one_husky_file_without_the_block_fails_only_its_own_check(
    repo: Path, git: Git
) -> None:
    (repo / ".husky").mkdir()
    install(repo, "--hooks", "husky")
    git(repo, "config", "core.hooksPath", ".husky/_")
    activate(repo, repo / ".husky" / "_", "husky", "commit-msg", "pre-push")
    (repo / ".husky" / "pre-push").write_text("#!/bin/sh\nnpm test\n")

    result = doctor(repo)

    assert both(result) == ("ok", "fail")
    assert ".husky/pre-push" in line(result, "pre-push")


def test_a_lefthook_section_that_lost_its_block_fails_only_its_own_check(
    repo: Path,
) -> None:
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(repo, "--hooks", "lefthook")
    activate(repo, repo / ".git" / "hooks", "lefthook", "commit-msg", "pre-push")
    text = (repo / "lefthook.yml").read_text()
    start = text.rindex("# prepush-ci: begin", 0, text.index("hook commit-msg"))
    end = text.index("# prepush-ci: end", start) + len("# prepush-ci: end\n")
    (repo / "lefthook.yml").write_text(text[:start].rstrip(" ") + text[end:])

    result = doctor(repo)

    assert both(result) == ("fail", "ok")
    assert "lefthook.yml" in line(result, "commit-msg")


# Activation of pre-commit and lefthook


def test_pre_commit_that_was_activated_passes(repo: Path, tmp_path: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    install(repo)
    pre_commit_install(repo, tmp_path)

    assert both(doctor(repo)) == ("ok", "ok")


def test_pre_commit_that_was_not_activated_fails_and_the_fix_is_pre_commit_install(
    repo: Path,
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    install(repo)

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert "pre-commit install" in fix_after(result, "commit-msg")
    assert "pre-commit install" in fix_after(result, "pre-push")


def test_pre_commit_activated_for_the_default_hook_type_only_fails_both(
    repo: Path, tmp_path: Path
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    install(repo)
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-commit"],
        cwd=repo,
        capture_output=True,
        check=True,
        env={**os.environ, "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home")},
    )

    assert both(doctor(repo)) == ("fail", "fail")


def test_lefthook_that_was_not_activated_fails_and_the_fix_is_lefthook_install(
    repo: Path,
) -> None:
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(repo, "--hooks", "lefthook")
    activate(repo, repo / ".git" / "hooks", "lefthook", "commit-msg")

    result = doctor(repo)

    assert both(result) == ("ok", "fail")
    assert "lefthook install" in fix_after(result, "pre-push")


def test_lefthook_activated_with_executable_scripts_naming_it_passes(
    repo: Path,
) -> None:
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(repo, "--hooks", "lefthook")
    activate(repo, repo / ".git" / "hooks", "lefthook", "commit-msg", "pre-push")

    assert both(doctor(repo)) == ("ok", "ok")


@POSIX_ONLY
def test_a_lefthook_script_that_is_not_executable_is_not_activated(repo: Path) -> None:
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(repo, "--hooks", "lefthook")
    activate(repo, repo / ".git" / "hooks", "lefthook", "commit-msg", "pre-push")
    (repo / ".git" / "hooks" / "pre-push").chmod(0o644)

    result = doctor(repo)

    assert both(result) == ("ok", "fail")
    assert "not executable" in line(result, "pre-push")


def test_a_hook_script_of_another_tool_is_not_the_activation_of_lefthook(
    repo: Path,
) -> None:
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(repo, "--hooks", "lefthook")
    activate(repo, repo / ".git" / "hooks", "something else", "commit-msg", "pre-push")

    assert both(doctor(repo)) == ("fail", "fail")


def test_the_hooks_directory_git_uses_is_the_one_checked_for_activation(
    repo: Path, git: Git
) -> None:
    (repo / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(repo, "--hooks", "lefthook")
    activate(repo, repo / ".git" / "hooks", "lefthook", "commit-msg", "pre-push")
    git(repo, "config", "core.hooksPath", ".githooks")

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert ".githooks" in line(result, "pre-push")


# husky


def test_husky_with_its_hooks_path_and_stubs_passes(repo: Path, git: Git) -> None:
    (repo / ".husky").mkdir()
    install(repo, "--hooks", "husky")
    git(repo, "config", "core.hooksPath", ".husky/_")
    activate(repo, repo / ".husky" / "_", "husky", "commit-msg", "pre-push")

    assert both(doctor(repo)) == ("ok", "ok")


def test_husky_hooks_run_from_the_husky_directory_itself_pass(
    repo: Path, git: Git
) -> None:
    (repo / ".husky").mkdir()
    install(repo, "--hooks", "husky")
    git(repo, "config", "core.hooksPath", ".husky")

    assert both(doctor(repo)) == ("ok", "ok")


def test_husky_on_a_clone_where_it_never_ran_fails_and_the_fix_is_npx_husky(
    repo: Path,
) -> None:
    (repo / ".husky").mkdir()
    install(repo, "--hooks", "husky")

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    for name in ("commit-msg", "pre-push"):
        assert "core.hooksPath" in line(result, name)
        assert "husky" in line(result, name)
        assert "npx husky" in fix_after(result, name)


def test_husky_whose_stubs_were_removed_fails_and_names_the_missing_hook(
    repo: Path, git: Git
) -> None:
    (repo / ".husky").mkdir()
    install(repo, "--hooks", "husky")
    git(repo, "config", "core.hooksPath", ".husky/_")

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert "husky" in line(result, "pre-push")
    assert ".husky/_/pre-push" in line(result, "pre-push")
    assert "npx husky" in fix_after(result, "pre-push")


@POSIX_ONLY
def test_a_husky_stub_that_is_not_executable_fails(repo: Path, git: Git) -> None:
    (repo / ".husky").mkdir()
    install(repo, "--hooks", "husky")
    git(repo, "config", "core.hooksPath", ".husky/_")
    activate(repo, repo / ".husky" / "_", "husky", "commit-msg", "pre-push")
    (repo / ".husky" / "_" / "commit-msg").chmod(0o644)

    result = doctor(repo)

    assert both(result) == ("fail", "ok")
    assert "not executable" in line(result, "commit-msg")


def test_husky_with_another_hooks_path_fails(repo: Path, git: Git) -> None:
    (repo / ".husky").mkdir()
    install(repo, "--hooks", "husky")
    git(repo, "config", "core.hooksPath", "/somewhere/else")

    result = doctor(repo)

    assert both(result) == ("fail", "fail")
    assert "/somewhere/else" in line(result, "commit-msg")


def test_the_native_hint_is_only_given_for_a_detected_manager(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)

    detected = doctor(repo)
    named = doctor(repo, "--hooks", "pre-commit")

    assert "--hooks native" in fix_after(detected, "commit-msg")
    assert "--hooks native" not in fix_after(named, "commit-msg")
    assert "install --hooks pre-commit" in fix_after(named, "commit-msg")


# A repository where everything passes


@pytest.fixture
def ready(repo: Path, tmp_path: Path, git: Git) -> Path:
    """`repo` on `main` with a config, native hooks installed and a bare `origin` that has `main`."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".prepush-ci.toml").write_text('check = "true"\n')
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    install(repo)
    return repo


def configure(repo: Path, *lines: str) -> None:
    """Replace the config with a passing check and `lines`."""
    (repo / ".prepush-ci.toml").write_text("\n".join(['check = "true"', *lines, ""]))


def python_command(tmp_path: Path, name: str, source: str) -> str:
    """A command that runs `source` and means the same to `sh` and to `cmd.exe`.

    `check` and `preflight` run through the shell, which is `cmd.exe` on Windows: `;`, `&`,
    `cat`, `sleep` and `pwd` mean nothing there, a Python script means the same everywhere.
    """
    script = tmp_path / f"{name}.py"
    script.write_text(source)
    return f'"{sys.executable}" "{script}"'


def preflight(command: str) -> str:
    """The `preflight` line of a config, the command as a TOML string whatever it contains."""
    return f"preflight = {json.dumps(command)}"


FULL = {"PREPUSH_CI": "full"}


def test_everything_set_up_passes_all_six_checks_and_exits_0(ready: Path) -> None:
    result = doctor(ready, env=FULL)

    assert result.returncode == 0, result.stdout
    assert [text.split()[0] for text in result.stdout.splitlines()[:-1]] == ["ok"] * 6
    assert result.stdout.splitlines()[-1] == "all checks passed"


def test_passing_checks_print_no_fix_line(ready: Path) -> None:
    result = doctor(ready, env=FULL)

    assert "fix:" not in result.stdout


def test_a_subdirectory_of_the_worktree_is_checked_as_the_whole_worktree(
    ready: Path,
) -> None:
    (ready / "src").mkdir()

    result = doctor(ready / "src", env=FULL)

    assert result.returncode == 0, result.stdout


def test_the_last_line_counts_every_check_that_did_not_pass(ready: Path) -> None:
    (ready / "gone").mkdir()
    subprocess.run(
        ["git", "remote", "set-url", "origin", str(ready / "gone" / "nowhere")],
        cwd=ready,
        check=True,
    )

    result = doctor(ready, env={"PREPUSH_CI": "foo"})

    assert status(result, "PREPUSH_CI") == "fail"
    assert status(result, "up-to-date") == "fail"
    assert result.returncode == 1
    assert result.stdout.splitlines()[-1] == "2 of 6 checks did not pass"


# The preflight check


def test_variables_that_are_set_and_a_passing_command_pass(ready: Path) -> None:
    configure(ready, 'require_env = ["DATABASE_URL"]', 'preflight = "true"')

    result = doctor(ready, env={"DATABASE_URL": "postgres://x"})

    assert status(result, "preflight") == "ok"


def test_missing_variables_fail_and_name_every_one(ready: Path) -> None:
    configure(ready, 'require_env = ["A_URL", "B_URL"]')

    result = doctor(ready)

    assert status(result, "preflight") == "fail"
    assert "A_URL" in line(result, "preflight")
    assert "B_URL" in line(result, "preflight")


def test_a_missing_variable_stops_the_preflight_command(
    ready: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "ran.marker"
    command = python_command(
        tmp_path, "touch", "import sys, pathlib; pathlib.Path(sys.argv[1]).touch()"
    )
    configure(ready, 'require_env = ["A_URL"]', preflight(f'{command} "{marker}"'))

    doctor(ready)

    assert not marker.exists()


def test_a_failing_preflight_names_the_command_and_status_and_shows_its_output(
    ready: Path, tmp_path: Path
) -> None:
    command = python_command(
        tmp_path, "down", "import sys; print('db is down'); sys.exit(3)"
    )
    configure(ready, preflight(command))

    result = doctor(ready)

    text = line(result, "preflight")
    assert status(result, "preflight") == "fail"
    assert command in text and "3" in text
    assert "    db is down" in result.stdout.splitlines()


def test_a_passing_preflight_stays_quiet(ready: Path) -> None:
    configure(ready, "preflight = 'echo all good'")

    result = doctor(ready)

    assert status(result, "preflight") == "ok"
    assert "all good" not in result.stdout


def test_the_preflight_runs_from_the_repository_root(
    ready: Path, tmp_path: Path
) -> None:
    where = tmp_path / "cwd.txt"
    command = python_command(
        tmp_path,
        "cwd",
        "import os, sys, pathlib; pathlib.Path(sys.argv[1]).write_text(os.getcwd())",
    )
    configure(ready, preflight(f'{command} "{where}"'))
    (ready / "src").mkdir()

    doctor(ready / "src")

    assert Path(where.read_text()).resolve() == ready.resolve()


def test_a_preflight_that_reads_standard_input_does_not_wait_for_it(
    ready: Path, tmp_path: Path
) -> None:
    command = python_command(tmp_path, "stdin", "import sys; sys.stdin.read()")
    configure(ready, preflight(command))

    result = doctor(ready)

    assert status(result, "preflight") == "ok"


def test_a_preflight_that_leaves_a_background_process_does_not_hold_doctor(
    ready: Path, tmp_path: Path
) -> None:
    command = python_command(
        tmp_path,
        "service",
        "import subprocess, sys, tempfile\n"
        "subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(30)'], cwd=tempfile.gettempdir()\n"
        ")\n"
        "print('service started')\n",
    )
    configure(ready, preflight(command))

    started = time.monotonic()
    result = doctor(ready, timeout=20)

    assert time.monotonic() - started < 20
    assert status(result, "preflight") == "ok"


def test_no_preflight_and_no_variables_is_nothing_to_verify(ready: Path) -> None:
    result = doctor(ready)

    assert status(result, "preflight") == "ok"
    assert "nothing to verify" in line(result, "preflight")


# The up-to-date check


def test_a_branch_the_remote_has_passes_and_the_ref_is_named(ready: Path) -> None:
    result = doctor(ready)

    assert status(result, "up-to-date") == "ok"
    assert "origin/main" in line(result, "up-to-date")


def test_a_remote_that_is_ahead_still_passes(
    ready: Path, tmp_path: Path, git: Git
) -> None:
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", "main", str(tmp_path / "remote.git"), str(other))
    git(
        other,
        "-c",
        "user.name=T",
        "-c",
        "user.email=t@e",
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "ahead",
    )
    git(other, "push", "-q", "origin", "main")

    result = doctor(ready)

    assert status(result, "up-to-date") == "ok"


def test_a_disabled_check_passes_without_contacting_the_remote(
    ready: Path, git: Git
) -> None:
    configure(ready, "require_up_to_date = false")
    git(ready, "remote", "set-url", "origin", str(ready / "nowhere"))

    result = doctor(ready)

    assert status(result, "up-to-date") == "ok"
    assert "disabled" in line(result, "up-to-date")


def test_a_ref_without_a_remote_fails_and_the_fix_names_the_way_out(
    ready: Path,
) -> None:
    configure(ready, 'require_up_to_date = "main"')

    result = doctor(ready)

    assert status(result, "up-to-date") == "fail"
    assert "<remote>/<branch>" in line(result, "up-to-date")
    assert "require_up_to_date = false" in fix_after(result, "up-to-date")


def test_a_remote_that_is_not_configured_fails_and_is_named(ready: Path) -> None:
    configure(ready, 'require_up_to_date = "upstream/develop"')

    result = doctor(ready)

    assert status(result, "up-to-date") == "fail"
    assert "upstream" in line(result, "up-to-date")


def test_an_unreachable_remote_fails_and_the_fix_names_the_way_out(
    ready: Path, git: Git
) -> None:
    git(ready, "remote", "set-url", "origin", str(ready / "no" / "such" / "dir"))

    result = doctor(ready)

    assert status(result, "up-to-date") == "fail"
    assert "cannot be reached" in line(result, "up-to-date")
    assert "require_up_to_date = false" in fix_after(result, "up-to-date")


def test_a_branch_the_remote_lacks_fails_and_names_the_ref(ready: Path) -> None:
    configure(ready, 'require_up_to_date = "origin/gone"')

    result = doctor(ready)

    assert status(result, "up-to-date") == "fail"
    assert "origin/gone" in line(result, "up-to-date")


def test_a_branch_name_with_a_slash_is_looked_up_whole(ready: Path, git: Git) -> None:
    git(ready, "push", "-q", "origin", "main:refs/heads/release/1")
    configure(ready, 'require_up_to_date = "origin/release/1"')

    result = doctor(ready)

    assert status(result, "up-to-date") == "ok"


class _Unauthorized(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (the name http.server calls)
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="repo"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """Say nothing."""


def _without_credential_helpers() -> dict[str, str]:
    """git's environment with `credential.helper` emptied, appended to the suite's own settings.

    Git Credential Manager, which Git for Windows configures, prints its own warning for a
    plain HTTP remote before git says why the remote failed; the spec is about git not asking.
    """
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    return {
        f"GIT_CONFIG_KEY_{count}": "credential.helper",
        f"GIT_CONFIG_VALUE_{count}": "",
        "GIT_CONFIG_COUNT": str(count + 1),
    }


def test_a_remote_that_wants_credentials_is_unreachable_without_a_prompt(
    ready: Path, git: Git
) -> None:
    server = http.server.HTTPServer(("127.0.0.1", 0), _Unauthorized)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        git(
            ready,
            "remote",
            "set-url",
            "origin",
            f"http://127.0.0.1:{server.server_port}/repo.git",
        )

        result = doctor(ready, env=_without_credential_helpers())
    finally:
        server.shutdown()
        server.server_close()

    assert status(result, "up-to-date") == "fail"
    assert "cannot be reached" in line(result, "up-to-date")
    assert "terminal prompts disabled" in line(result, "up-to-date")


# Doctor changes nothing


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """Every file and directory below `root` with its size and modification time."""
    found: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        found[path.relative_to(root).as_posix()] = (info.st_size, info.st_mtime_ns)
    return found


def test_a_set_up_repository_is_left_exactly_as_it_was(ready: Path) -> None:
    before = snapshot(ready)

    result = doctor(ready, env=FULL)

    assert result.returncode == 0, result.stdout
    assert snapshot(ready) == before


def test_a_broken_repository_is_left_exactly_as_it_was(repo: Path, git: Git) -> None:
    before = snapshot(repo)

    result = doctor(repo)

    assert result.returncode == 1
    assert snapshot(repo) == before
    assert git(repo, "config", "core.hooksPath", check=False).stdout == ""


def test_doctor_does_not_fetch(ready: Path, tmp_path: Path, git: Git) -> None:
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", "main", str(tmp_path / "remote.git"), str(other))
    git(
        other,
        "-c",
        "user.name=T",
        "-c",
        "user.email=t@e",
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "ahead",
    )
    git(other, "push", "-q", "origin", "main")
    tracking = git(ready, "rev-parse", "origin/main").stdout

    doctor(ready, env=FULL)

    assert git(ready, "rev-parse", "origin/main").stdout == tracking


def test_a_config_with_an_empty_required_variable_name_fails_naming_the_key(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "true"\nrequire_env = [""]\n')

    result = doctor(repo)

    assert status(result, "config") == "fail"
    assert "`require_env`" in line(result, "config")
    assert status(result, "preflight") == "skip"


# A terminal that cannot show the characters of the report


def test_a_config_message_quoting_a_non_ascii_key_is_reported_when_stdout_is_ascii(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text(
        'check = "true"\n"unknownÉ" = 1\n', encoding="utf-8"
    )
    ascii_only = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}

    result = doctor(repo, env=ascii_only)

    assert "Traceback" not in result.stderr
    assert status(result, "config") == "fail"
    # `?` where the terminal cannot show the É (a Windows console may print it)
    assert any(f"unknown{c}" in line(result, "config") for c in "?É")
    assert result.returncode == 1


def test_doctor_reports_a_repository_whose_path_has_a_non_ascii_character_under_an_ascii_locale(
    tmp_path: Path, git: Git
) -> None:
    where = tmp_path / "dé"
    where.mkdir()
    git(where, "init", "-q")
    (where / ".prepush-ci.toml").write_text(CONFIG)
    ascii_only = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}

    result = doctor(where, "--hooks", "none", env=ascii_only)

    assert "Traceback" not in result.stderr
    assert status(result, "config") == "ok"
