from prepush_ci.core.install import HOOKS, PYTHON_FILE, desired_files, hook_script


def test_a_hook_script_starts_the_tool_with_the_recorded_interpreter() -> None:
    script = hook_script("pre-push")

    assert script.startswith("#!/bin/sh\n")
    assert f'"$dir/{PYTHON_FILE}"' in script
    assert '-m prepush_ci hook pre-push "$@"' in script


def test_a_hook_script_never_looks_for_the_tool_on_path() -> None:
    assert "prepush-ci hook" not in hook_script("commit-msg")


def test_the_files_are_the_two_hooks_and_the_interpreter_record() -> None:
    files = desired_files("/usr/bin/python3")

    assert set(files) == {*HOOKS, PYTHON_FILE}
    assert files[PYTHON_FILE] == "/usr/bin/python3\n"
