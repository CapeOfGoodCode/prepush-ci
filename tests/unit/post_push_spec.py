import json
import time

import pytest

from prepush_ci.core.post_push import (
    Payload,
    find_comment,
    is_push,
    marker_of,
    parse_payload,
    results_pattern,
)


def payload(**fields: object) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": "x"}, **fields})


# --- The payload ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "",
        "[1, 2]",
        '"a string"',
        pytest.param("[" * 100_000, id="deep nesting"),
    ],
)
def test_a_payload_that_is_not_a_json_object_is_nothing(text: str) -> None:
    assert parse_payload(text) is None


def test_a_payload_of_another_tool_is_nothing() -> None:
    assert parse_payload(payload(tool_name="Edit")) is None


@pytest.mark.parametrize("command", [7, None, ["git", "push"]])
def test_a_command_that_is_not_a_string_is_nothing(command: object) -> None:
    assert parse_payload(payload(tool_input={"command": command})) is None


@pytest.mark.parametrize("tool_input", [None, "git push", [], {}])
def test_a_tool_input_without_a_command_is_nothing(tool_input: object) -> None:
    assert parse_payload(payload(tool_input=tool_input)) is None


def test_the_command_and_the_directory_are_read() -> None:
    text = payload(tool_input={"command": "git push"}, cwd="/work/sub")
    assert parse_payload(text) == Payload("git push", "/work/sub")


@pytest.mark.parametrize("cwd", [None, 3, ""])
def test_a_directory_that_is_not_a_name_is_left_out(cwd: object) -> None:
    assert parse_payload(payload(cwd=cwd)) == Payload("x", None)


def test_a_payload_without_a_directory_has_none() -> None:
    assert parse_payload(payload()) == Payload("x", None)


# --- A push is recognized from the command ----------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push -u origin feat/x",
        "cd sub && git push",
        "git commit -m x; git push",
        "git commit -m x\ngit push",
        "git commit -m x\r\ngit push",
        "git commit -m x & git push",
        "git commit -m x || git push",
        "git -C sub push",
        "git -c push.default=current push",
        "git --no-pager push",
        "GIT_SSH_COMMAND=ssh git push",
        "A=1 B='two words' git push",
        "git push 2>&1 | tail -3",
        "git commit -m 'a\nb' && git push",
        'git commit -m "say \\"hi\\"" && git push',
        "git commit -m a\\ b && git push",
        "git push --dry-run && git push",
        "git push origin main || true",
    ],
)
def test_a_command_with_a_git_push_counts_as_a_push(command: str) -> None:
    assert is_push(command)


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git stash push",
        "git log --grep push",
        "git pull",
        "git",
        "",
        "   ",
        "git -C",
        "git -c",
        "git --no-pager",
        "FOO=1",
        "echo git push",
        "git pushall",
        'git commit -m "fix; git push"',
        "git commit -m 'fix && git push'",
        "git commit -m 'a\ngit push'",
        'git commit -m "a\\"; git push"',
        'git push "origin',
        "git push 'origin",
        "git status; git push 'origin",
    ],
)
def test_a_command_without_a_git_push_does_not_count_as_a_push(command: str) -> None:
    assert not is_push(command)


@pytest.mark.parametrize(
    "command",
    [
        "git push --dry-run",
        "git push -n origin main",
        "git push origin --delete old",
        "git push -d origin old",
        "git -C sub push --dry-run",
    ],
)
def test_a_dry_run_and_a_deletion_do_not_count_as_a_push(command: str) -> None:
    assert not is_push(command)


def test_a_backslash_at_the_end_of_the_command_is_dropped() -> None:
    assert is_push("git push \\")


@pytest.mark.parametrize(
    "command",
    [
        "(git push)",
        "(cd sub && git push) 2>&1 | tail -3",
        "(time git push --force-with-lease) 2>&1 | tail -25",
    ],
)
def test_a_push_in_a_subshell_counts_as_a_push(command: str) -> None:
    assert is_push(command)


@pytest.mark.parametrize("command", ["echo $(git push)", "echo `git push`"])
def test_a_push_in_a_command_substitution_counts_as_a_push(command: str) -> None:
    assert is_push(command)


def test_parentheses_inside_quotes_do_not_count_as_a_push() -> None:
    assert not is_push('git commit -m "fix (git push)"')


# --- A wrapper does not hide a push -----------------------------------------------------------


@pytest.mark.parametrize("command", ["time git push", "time -p git push"])
def test_time_does_not_hide_a_push(command: str) -> None:
    assert is_push(command)


@pytest.mark.parametrize(
    "command",
    [
        "env GIT_SSH_COMMAND=ssh git push",
        "env -u HTTP_PROXY git push",
        "env -i A=1 git push",
        "env -C sub git push",
    ],
)
def test_env_does_not_hide_a_push(command: str) -> None:
    assert is_push(command)


@pytest.mark.parametrize(
    "command", ["timeout 60 git push", "timeout -k 5 -s INT 60 git push"]
)
def test_timeout_does_not_hide_a_push(command: str) -> None:
    assert is_push(command)


@pytest.mark.parametrize(
    "command", ["command git push", "exec git push", "nohup git push"]
)
def test_command_exec_and_nohup_do_not_hide_a_push(command: str) -> None:
    assert is_push(command)


def test_wrappers_together_do_not_hide_a_push() -> None:
    assert is_push("time env A=1 timeout 60 git push")


@pytest.mark.parametrize(
    "command",
    [
        "time git status",
        "env A=1 git pull",
        "timeout 60 echo git push",
        "time",
        "timeout",
    ],
)
def test_a_wrapper_before_something_else_does_not_count_as_a_push(command: str) -> None:
    assert not is_push(command)


# --- A shell keyword does not hide a push -----------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "if git push; then echo ok; fi",
        "{ git push; }",
        "! git push",
        "for b in a b; do git push origin $b; done",
        "while git push; do :; done",
        "if false; then :; elif git push; then :; fi",
        "if false; then :; else git push; fi",
        "until git push; do :; done",
    ],
)
def test_a_push_after_a_shell_keyword_counts_as_a_push(command: str) -> None:
    assert is_push(command)


def test_a_keyword_inside_a_command_does_not_hide_a_push() -> None:
    assert not is_push("echo then git push")


# --- A shell started with -c is read ----------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        'bash -c "git push"',
        "sh -c 'cd sub && git push'",
        "zsh -c \"bash -c 'git push'\"",
    ],
)
def test_a_shell_script_with_a_push_counts_as_a_push(command: str) -> None:
    assert is_push(command)


@pytest.mark.parametrize("command", ['bash -lc "git push"', 'bash -e -c "git push"'])
def test_options_before_the_script_do_not_hide_a_push(command: str) -> None:
    assert is_push(command)


@pytest.mark.parametrize(
    "command",
    [
        'sh -c "echo git push"',
        'bash -c "git status"',
        'bash -c "git push --dry-run"',
        'bash -o pipefail -c "git push"',
    ],
)
def test_a_shell_script_that_only_mentions_push_does_not_count_as_a_push(
    command: str,
) -> None:
    assert not is_push(command)


@pytest.mark.parametrize(
    "command", ["bash script.sh git push", "bash -c", "bash", "bash -e", "bash --norc"]
)
def test_a_shell_without_a_script_does_not_count_as_a_push(command: str) -> None:
    assert not is_push(command)


def test_a_long_option_word_after_a_shell_is_read_within_the_time_the_hook_has() -> (
    None
):
    word = "-" + "c" * 32_000 + "1"
    started = time.monotonic()
    assert not is_push(f"bash {word} git push")
    assert time.monotonic() - started < 1


@pytest.mark.parametrize(
    ("repeated", "prefix", "suffix"),
    [
        pytest.param("env -u x ", "", "git push", id="env options"),
        pytest.param("time ", "", "git push", id="wrappers"),
        pytest.param("-k 1 ", "timeout ", " 5 git push", id="timeout options"),
        pytest.param("A=1 ", "", "git push", id="assignments"),
        pytest.param("-c a=b ", "git ", "push", id="git options"),
    ],
)
def test_a_command_of_many_words_is_read_in_time_linear_in_its_word_count(
    repeated: str, prefix: str, suffix: str
) -> None:
    def seconds_for(words: int) -> float:
        command = prefix + repeated * words + suffix
        durations = []
        for _ in range(3):
            started = time.process_time()
            assert is_push(command)
            durations.append(time.process_time() - started)
        return min(durations)

    # Four times the words cost about four times as long when linear and sixteen
    # times as long when quadratic; the bound sits between them, so it holds on any
    # machine, with or without tracing, where a fixed number of seconds does not.
    assert seconds_for(100_000) < 8 * seconds_for(25_000)


# --- Forms that are not recognized ------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        'echo "$(git push)"',
        'eval "git push"',
        "sudo git push",
        "echo origin | xargs git push",
        "p",
        "./push.sh",
    ],
)
def test_a_push_that_is_not_recognized_does_not_count_as_a_push(command: str) -> None:
    assert not is_push(command)


@pytest.mark.parametrize("command", ["f() { git push; }; f", "f() ( git push ); f"])
def test_a_function_defined_on_the_line_counts_as_a_push(command: str) -> None:
    assert is_push(command)


# --- The comment of the check -----------------------------------------------------------------


def test_the_marker_is_the_first_line_of_the_body() -> None:
    assert marker_of("<!-- prepush-ci:a / b -->\n### a / b: Passed\nCommit x") == (
        "<!-- prepush-ci:a / b -->"
    )


def test_the_marker_of_a_body_of_one_line_is_the_line() -> None:
    assert marker_of("<!-- prepush-ci:a -->") == "<!-- prepush-ci:a -->"


MARKER = "<!-- prepush-ci:prepush-ci / full -->"


def test_the_comment_found_is_the_first_whose_body_starts_with_the_marker() -> None:
    comments = [
        (1, f"I saw {MARKER} in a comment"),
        (2, f"{MARKER}\nold"),
        (3, f"{MARKER}\nsecond"),
    ]
    assert find_comment(comments, MARKER) == (2, f"{MARKER}\nold")


def test_a_comment_of_another_check_is_not_found() -> None:
    comments = [(1, "<!-- prepush-ci:prepush-ci / unit -->\nx")]
    assert find_comment(comments, MARKER) is None


def test_no_comments_find_nothing() -> None:
    assert find_comment([], MARKER) is None


# --- The result of the tree -------------------------------------------------------------------


def test_the_results_of_a_tree_are_the_refs_that_start_with_its_hash_and_a_dash() -> (
    None
):
    assert results_pattern("ab" * 20) == f"refs/prepush-ci/results/{'ab' * 20}-*"
