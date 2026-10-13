from prepush_ci.core.install import (
    HOOKS,
    PREVIOUS_FILE,
    PYTHON_FILE,
    Changes,
    Existing,
    changes,
    desired_files,
    forwardable,
    forwarder_script,
    hook_script,
    native_hooks_refusal,
    outcome,
    report,
)


def test_a_hook_script_starts_the_tool_with_the_recorded_interpreter() -> None:
    script = hook_script("pre-push")

    assert script.startswith("#!/bin/sh\n")
    assert f'"$dir/{PYTHON_FILE}"' in script
    assert '-m prepush_ci hook pre-push "$@"' in script


def test_a_hook_script_never_looks_for_the_tool_on_path() -> None:
    assert "prepush-ci hook" not in hook_script("commit-msg")


def test_the_files_are_the_two_hooks_and_the_interpreter_record() -> None:
    files = desired_files("/usr/bin/python3", "/p", [])

    assert set(files) == {*HOOKS, PYTHON_FILE, PREVIOUS_FILE}
    assert files[PYTHON_FILE] == "/usr/bin/python3\n"


def test_the_pre_push_script_feeds_the_saved_input_to_the_previous_hook_and_to_ours() -> (
    None
):
    script = hook_script("pre-push")

    assert 'cat > "$input"' in script
    assert '"$prev/pre-push" "$@" < "$input" || exit $?' in script
    assert '"$py" -m prepush_ci hook pre-push "$@" < "$input"' in script


def test_the_commit_msg_script_runs_the_previous_hook_first_and_aborts_when_it_fails() -> (
    None
):
    script = hook_script("commit-msg")

    assert script.index('"$prev/commit-msg" "$@" || exit $?') < script.index("exec")


def test_the_scripts_run_a_previous_hook_only_when_it_is_executable() -> None:
    assert 'if [ -x "$prev/commit-msg" ]' in hook_script("commit-msg")
    assert 'if [ -x "$prev/pre-push" ]' in hook_script("pre-push")
    assert 'if [ -x "$prev/post-merge" ]' in forwarder_script("post-merge")


def test_a_forwarder_hands_everything_to_the_previous_hook_and_succeeds_without_one() -> (
    None
):
    script = forwarder_script("post-checkout")

    assert 'exec "$prev/post-checkout" "$@"' in script
    assert script.endswith("fi\nexit 0\n")


def test_ordinary_hook_names_are_forwarded() -> None:
    assert all(forwardable(n) for n in ("pre-commit", "post-merge", "p4.changelist"))


def test_samples_and_our_own_hooks_are_not_forwarded() -> None:
    assert not any(
        forwardable(n)
        for n in ("pre-commit.sample", "commit-msg", "pre-push", "pre-push.sample")
    )


def test_names_that_are_unsafe_in_a_script_are_not_forwarded() -> None:
    assert not any(
        forwardable(n) for n in ("a b", "$(x)", "x;y", "-rf", ".hidden", "it's", "")
    )


def test_forwarders_and_records_join_the_two_hooks() -> None:
    files = desired_files("/py", "/old/hooks", ["pre-commit"])

    assert set(files) == {*HOOKS, "pre-commit", PYTHON_FILE, PREVIOUS_FILE}
    assert files[PREVIOUS_FILE] == "/old/hooks\n"
    assert files["pre-commit"] == forwarder_script("pre-commit")


def test_nothing_differs_when_every_file_exists_executable_with_the_wanted_content() -> (
    None
):
    desired = {"pre-push": "a", "python": "b"}
    existing = {name: Existing(text, True) for name, text in desired.items()}

    assert not changes(existing, desired).any


def test_a_missing_file_is_written() -> None:
    result = changes({}, {"pre-push": "a"})

    assert result == Changes(write=["pre-push"], remove=[])
    assert result.any


def test_a_file_with_other_content_is_written() -> None:
    assert changes({"python": Existing("old", True)}, {"python": "new"}).write == [
        "python"
    ]


def test_a_file_that_lost_the_executable_bit_is_written() -> None:
    assert changes({"pre-push": Existing("a", False)}, {"pre-push": "a"}).write == [
        "pre-push"
    ]


def test_a_file_nothing_wants_any_more_is_removed() -> None:
    result = changes({"post-merge": Existing("a", True)}, {})

    assert result == Changes(write=[], remove=["post-merge"])
    assert result.any


def test_the_first_run_is_installed_whatever_it_wrote() -> None:
    assert outcome(was_installed=False, changed=True) == "installed"
    assert outcome(was_installed=False, changed=False) == "installed"


def test_a_rerun_is_updated_when_something_changed_and_already_installed_otherwise() -> (
    None
):
    assert outcome(was_installed=True, changed=True) == "updated"
    assert outcome(was_installed=True, changed=False) == "already installed"


def test_the_report_names_the_directory_and_the_previous_one_when_there_is_one() -> (
    None
):
    assert report("installed", "/g/hooks", "/g/old") == (
        "installed: /g/hooks\nhooks kept from: /g/old"
    )


def test_the_report_has_one_line_when_nothing_is_kept() -> None:
    assert report("installed", "/g/hooks", None) == "installed: /g/hooks"


def test_the_pre_push_script_fails_closed_when_the_interpreter_is_gone() -> None:
    script = hook_script("pre-push")

    assert 'if [ ! -x "$py" ]' in script
    assert "prepush-ci install" in script
    assert script.index("exit 1", script.index('[ ! -x "$py" ]')) < script.index(
        "-m prepush_ci"
    )


def test_the_commit_msg_script_warns_and_lets_the_commit_go_when_the_interpreter_is_gone() -> (
    None
):
    script = hook_script("commit-msg")

    assert 'if [ ! -x "$py" ]' in script
    assert "prepush-ci install" in script
    assert script.index("exit 0", script.index('[ ! -x "$py" ]')) < script.index(
        "-m prepush_ci"
    )


def test_the_native_hooks_refusal_names_the_setting_the_command_and_the_rerun() -> None:
    message = native_hooks_refusal("pre-commit", None)

    assert "core.hooksPath" in message
    assert "git config --local --unset core.hooksPath" in message
    assert "pre-commit" in message
    assert "install" in message and "again" in message


def test_the_native_hooks_refusal_says_nothing_about_lost_hooks_when_none_are_lost() -> (
    None
):
    assert "no longer run" not in native_hooks_refusal("lefthook", None)


def test_the_native_hooks_refusal_names_the_directory_whose_hooks_stop_running() -> (
    None
):
    message = native_hooks_refusal("lefthook", "/work/custom-hooks")

    assert "/work/custom-hooks" in message and "no longer run" in message
