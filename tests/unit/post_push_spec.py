import json

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
