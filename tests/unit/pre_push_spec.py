import pytest

from prepush_ci.core.config import Config, Trailer
from prepush_ci.core.pre_push import (
    MalformedRefLine,
    PreCommitPush,
    PushedRef,
    branch_tips,
    demand_keys,
    demands_check,
    dirty_paths,
    hidden_paths,
    is_branch_update,
    message_dirty,
    message_hidden,
    message_not_head,
    message_off,
    parse_ref_lines,
    pre_commit_push,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
ZEROS = "0" * 40


def config(key: str = "Prepush-CI", legacy: tuple[str, ...] = ()) -> Config:
    return Config(
        check="true",
        preflight=None,
        require_env=(),
        require_up_to_date=None,
        default_branch="main",
        trailer=Trailer(key, "full"),
        legacy_keys=legacy,
        cache=True,
    )


def test_a_ref_line_is_read_as_local_ref_sha_and_remote_ref() -> None:
    line = f"refs/heads/main {SHA_A} refs/heads/main {ZEROS}\n"

    assert parse_ref_lines(line) == [
        PushedRef("refs/heads/main", SHA_A, "refs/heads/main")
    ]


def test_every_ref_line_of_a_push_is_read_in_order_and_blank_lines_are_skipped() -> (
    None
):
    text = (
        f"refs/heads/a {SHA_A} refs/heads/x {ZEROS}\n"
        "\n"
        f"(delete) {ZEROS} refs/heads/old {SHA_B}\n"
    )

    assert [ref.remote_ref for ref in parse_ref_lines(text)] == [
        "refs/heads/x",
        "refs/heads/old",
    ]


def test_empty_input_holds_no_ref_lines() -> None:
    assert parse_ref_lines("") == []


@pytest.mark.parametrize("line", ["refs/heads/main", f"a {SHA_A} c d e"])
def test_a_ref_line_with_the_wrong_number_of_fields_is_refused(line: str) -> None:
    with pytest.raises(MalformedRefLine) as error_info:
        parse_ref_lines(line + "\n")

    assert line in str(error_info.value)


def test_pre_commit_gives_the_pushed_sha_and_the_remote_ref() -> None:
    env = {
        "PRE_COMMIT_TO_REF": SHA_A,
        "PRE_COMMIT_REMOTE_BRANCH": "refs/heads/main",
        "PRE_COMMIT_LOCAL_BRANCH": "refs/heads/main",
    }

    assert pre_commit_push(env) == PreCommitPush(
        sha=SHA_A, local_branch="refs/heads/main", remote_ref="refs/heads/main"
    )


def test_pre_commit_without_a_sha_gives_the_local_branch_to_resolve() -> None:
    env = {"PRE_COMMIT_LOCAL_BRANCH": "refs/heads/main"}

    assert pre_commit_push(env) == PreCommitPush(
        sha=None, local_branch="refs/heads/main", remote_ref=None
    )


def test_pre_commit_with_an_empty_remote_branch_has_no_remote_ref() -> None:
    env = {"PRE_COMMIT_TO_REF": SHA_A, "PRE_COMMIT_REMOTE_BRANCH": ""}

    assert pre_commit_push(env) == PreCommitPush(
        sha=SHA_A, local_branch=None, remote_ref=None
    )


def test_without_pre_commit_variables_there_is_no_pre_commit_push() -> None:
    assert pre_commit_push({"PRE_COMMIT_REMOTE_BRANCH": "refs/heads/main"}) is None


@pytest.mark.parametrize(
    ("remote_ref", "sha", "expected"),
    [
        ("refs/heads/main", SHA_A, True),
        ("refs/heads/feature/x", SHA_A, True),
        (None, SHA_A, True),
        ("refs/tags/v1", SHA_A, False),
        ("refs/notes/x", SHA_A, False),
        ("refs/heads/old", ZEROS, False),
        ("refs/heads/old", "0" * 64, False),
    ],
)
def test_only_updates_of_branches_count(
    remote_ref: str | None, sha: str, expected: bool
) -> None:
    assert is_branch_update(PushedRef("x", sha, remote_ref)) is expected


def test_branch_tips_lists_each_distinct_sha_once_in_push_order() -> None:
    refs = [
        PushedRef("a", SHA_B, "refs/heads/a"),
        PushedRef("t", SHA_A, "refs/tags/t"),
        PushedRef("b", SHA_A, "refs/heads/b"),
        PushedRef("c", SHA_B, "refs/heads/c"),
        PushedRef("(delete)", ZEROS, "refs/heads/old"),
    ]

    assert branch_tips(refs) == [SHA_B, SHA_A]


def test_the_configured_key_and_the_legacy_keys_demand_the_check_in_any_case() -> None:
    keys = demand_keys(config("Full-Check", ("Full-Pre-Push",)))

    assert keys == {"full-check", "full-pre-push"}


def test_the_keys_of_several_configs_are_united() -> None:
    keys = demand_keys(config("A-Key"), config("B-Key", ("C-Key",)))

    assert keys == {"a-key", "b-key", "c-key"}


@pytest.mark.parametrize(
    "trailers",
    [
        "Prepush-CI: full\n",
        "prepush-ci: full\n",
        "PREPUSH-CI: off\n",
        "Co-Authored-By: A <a@example.com>\nPrepush-CI: anything at all\n",
        "Prepush-CI:\n",
    ],
)
def test_a_trailer_with_a_demanding_key_demands_the_check_whatever_its_value(
    trailers: str,
) -> None:
    assert demands_check(trailers, {"prepush-ci"})


@pytest.mark.parametrize(
    "trailers",
    ["", "\n", "Signed-off-by: A <a@example.com>\n", "Prepush-CI-Not: full\n"],
)
def test_without_a_demanding_key_among_the_trailers_the_check_is_not_demanded(
    trailers: str,
) -> None:
    assert not demands_check(trailers, {"prepush-ci"})


def test_text_without_a_colon_is_not_a_trailer() -> None:
    assert not demands_check("Prepush-CI full\n", {"prepush-ci"})


def test_a_clean_status_has_no_dirty_paths() -> None:
    assert dirty_paths("") == []


def test_every_changed_staged_and_untracked_path_is_dirty() -> None:
    status = " M tracked.py\0A  staged.py\0?? new file.txt\0"

    assert dirty_paths(status) == ["tracked.py", "staged.py", "new file.txt"]


def test_a_rename_lists_the_new_path_and_skips_the_old_one() -> None:
    status = "R  new.py\0old.py\0 M other.py\0"

    assert dirty_paths(status) == ["new.py", "other.py"]


def test_the_off_refusal_names_the_tip_the_demand_and_the_variable() -> None:
    message = message_off([SHA_A])

    assert SHA_A[:12] in message
    assert "PREPUSH_CI=off" in message
    assert "full check" in message


def test_the_not_head_refusal_names_each_tip_and_head() -> None:
    message = message_not_head([SHA_A, SHA_B], "c" * 40)

    assert SHA_A[:12] in message
    assert SHA_B[:12] in message
    assert ("c" * 40)[:12] in message
    assert "HEAD" in message


def test_the_dirty_refusal_lists_every_path() -> None:
    message = message_dirty(["a.py", "b.py"])

    assert "a.py" in message
    assert "b.py" in message


def test_an_index_without_flagged_entries_hides_no_paths() -> None:
    assert hidden_paths("H a.py\0H dir/b.py\0") == []
    assert hidden_paths("") == []


def test_an_assume_unchanged_entry_is_hidden() -> None:
    assert hidden_paths("H a.py\0h check.sh\0") == ["check.sh"]


def test_a_skip_worktree_entry_is_hidden() -> None:
    assert hidden_paths("H a.py\0S sub/t.sh\0") == ["sub/t.sh"]


def test_an_entry_with_both_flags_is_hidden_once_and_a_path_with_spaces_is_kept() -> (
    None
):
    assert hidden_paths("s my file.txt\0H a.py\0") == ["my file.txt"]


def test_the_hidden_refusal_lists_every_path_and_says_why() -> None:
    message = message_hidden(["a.py", "sub/b.py"])

    assert "a.py" in message
    assert "sub/b.py" in message
    assert "assume-unchanged" in message
    assert "skip-worktree" in message
