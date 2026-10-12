"""`prepush-ci doctor` in real temporary git repositories, started as the module."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

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
