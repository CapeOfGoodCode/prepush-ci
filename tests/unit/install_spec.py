from prepush_ci.core.install import (
    HOOKS,
    PREVIOUS_FILE,
    PYTHON_FILE,
    desired_files,
    forwardable,
    forwarder_script,
    hook_script,
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
