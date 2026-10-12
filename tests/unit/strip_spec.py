from prepush_ci.core.strip import (
    commit_message,
    in_progress,
    message_detached,
    message_dirty,
    message_hidden,
    message_needs_base,
    message_not_ancestor,
    message_unknown_base,
    parent_shas,
    rebuild_commit,
    report,
    strip_message,
)

KEYS = {"prepush-ci", "full-pre-push"}
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def stripped(message: str, trailers: str) -> str:
    return strip_message(message, trailers, KEYS)


def test_a_message_made_by_the_commit_msg_hook_is_restored_exactly() -> None:
    assert stripped("add x\n\nPrepush-CI: full\n", "Prepush-CI: full\n") == "add x\n"


def test_other_trailers_stay_and_the_rest_of_the_message_is_unchanged() -> None:
    message = "add x\n\nbody\n\nPrepush-CI: full\nCo-Authored-By: A <a@example.com>\n"

    assert stripped(
        message, "Prepush-CI: full\nCo-Authored-By: A <a@example.com>\n"
    ) == ("add x\n\nbody\n\nCo-Authored-By: A <a@example.com>\n")


def test_the_trailer_between_two_other_trailers_goes_alone() -> None:
    message = "x\n\nSigned-off-by: A\nPrepush-CI: full\nCo-Authored-By: B\n"

    assert stripped(
        message, "Signed-off-by: A\nPrepush-CI: full\nCo-Authored-By: B\n"
    ) == ("x\n\nSigned-off-by: A\nCo-Authored-By: B\n")


def test_a_legacy_key_in_another_case_with_any_value_is_removed() -> None:
    assert stripped("x\n\nfull-pre-push: required\n", "full-pre-push: required\n") == (
        "x\n"
    )
    assert stripped("x\n\nPREPUSH-CI: off\n", "PREPUSH-CI: off\n") == "x\n"


def test_every_matching_line_of_the_block_is_removed() -> None:
    message = "x\n\nPrepush-CI: full\nPrepush-CI: full\n"

    assert stripped(message, "Prepush-CI: full\nPrepush-CI: full\n") == "x\n"


def test_the_body_around_a_divider_line_stays_in_order() -> None:
    message = "subject\n\nbody\n---\nmore\n\nPrepush-CI: full\n"

    assert stripped(message, "Prepush-CI: full\n") == "subject\n\nbody\n---\nmore\n"


def test_trailer_text_in_the_body_is_left_alone() -> None:
    message = "x\n\nPrepush-CI: full\n\nmore text\n"

    assert stripped(message, "") == message


def test_trailer_text_in_an_earlier_paragraph_stays_when_the_last_block_is_stripped() -> (
    None
):
    message = "x\n\nPrepush-CI: full\n\nSigned-off-by: A\nPrepush-CI: full\n"

    assert stripped(message, "Signed-off-by: A\nPrepush-CI: full\n") == (
        "x\n\nPrepush-CI: full\n\nSigned-off-by: A\n"
    )


def test_a_removed_trailer_takes_its_continuation_lines() -> None:
    message = "x\n\nCo-Authored-By: A <a@example.com>\nPrepush-CI: full\n  because the db changed\n"

    assert (
        stripped(
            message,
            "Co-Authored-By: A <a@example.com>\nPrepush-CI: full because the db changed\n",
        )
        == "x\n\nCo-Authored-By: A <a@example.com>\n"
    )


def test_the_continuation_lines_of_a_trailer_that_stays_stay() -> None:
    message = "x\n\nCo-Authored-By: A\n\tand B\nPrepush-CI: full\n"

    assert stripped(message, "Co-Authored-By: A and B\nPrepush-CI: full\n") == (
        "x\n\nCo-Authored-By: A\n\tand B\n"
    )


def test_blank_lines_after_an_emptied_block_go_with_it() -> None:
    assert stripped("x\n\nPrepush-CI: full\n\n\n", "Prepush-CI: full\n") == "x\n"


def test_blank_lines_after_a_block_that_stays_stay() -> None:
    message = "x\n\nPrepush-CI: full\nSigned-off-by: A\n\n"

    assert stripped(message, "Prepush-CI: full\nSigned-off-by: A\n") == (
        "x\n\nSigned-off-by: A\n\n"
    )


def test_a_message_without_a_final_newline_loses_the_trailer_too() -> None:
    assert stripped("x\n\nPrepush-CI: full", "Prepush-CI: full\n") == "x\n"
    assert stripped(
        "x\n\nSigned-off-by: A\nPrepush-CI: full", "Prepush-CI: full\n"
    ) == ("x\n\nSigned-off-by: A\n")


def test_a_message_without_the_trailer_is_returned_as_it_is() -> None:
    message = "x\n\nSigned-off-by: A\n"

    assert stripped(message, "Signed-off-by: A\n") == message


def test_prose_lines_in_the_block_stay() -> None:
    message = "x\n\nnot a trailer\nPrepush-CI: full\nSigned-off-by: A\n"

    assert stripped(message, "Prepush-CI: full\nSigned-off-by: A\n") == (
        "x\n\nnot a trailer\nSigned-off-by: A\n"
    )


RAW = (
    f"tree {SHA_C}\n"
    f"parent {SHA_A}\n"
    f"parent {SHA_B}\n"
    "author A <a@example.com> 1700000000 +0100\n"
    "committer GitHub <noreply@github.com> 1700000100 +0000\n"
    "encoding ISO-8859-1\n"
    "gpgsig -----BEGIN PGP SIGNATURE-----\n"
    " \n"
    " abc\n"
    " -----END PGP SIGNATURE-----\n"
    "\n"
    "subject\n\nPrepush-CI: full\n"
)


def test_the_parents_of_a_commit_are_read_in_order() -> None:
    assert parent_shas(RAW) == [SHA_A, SHA_B]


def test_a_root_commit_has_no_parents() -> None:
    assert parent_shas(f"tree {SHA_C}\n\nroot\n") == []


def test_the_message_of_a_commit_is_everything_after_the_first_blank_line() -> None:
    assert commit_message(RAW) == "subject\n\nPrepush-CI: full\n"


def test_a_rebuilt_commit_has_the_new_message_and_the_mapped_parents() -> None:
    new = "d" * 40

    rebuilt = rebuild_commit(RAW, {SHA_A: new}, "subject\n")

    assert parent_shas(rebuilt) == [new, SHA_B]
    assert commit_message(rebuilt) == "subject\n"


def test_a_rebuilt_commit_keeps_tree_author_committer_and_encoding() -> None:
    rebuilt = rebuild_commit(RAW, {}, "subject\n")

    for header in (
        f"tree {SHA_C}\n",
        "author A <a@example.com> 1700000000 +0100\n",
        "committer GitHub <noreply@github.com> 1700000100 +0000\n",
        "encoding ISO-8859-1\n",
    ):
        assert header in rebuilt


def test_a_rebuilt_commit_loses_its_signature_with_every_continuation_line() -> None:
    rebuilt = rebuild_commit(RAW, {}, "subject\n")

    assert "gpgsig" not in rebuilt
    assert "PGP" not in rebuilt
    assert rebuilt.index("encoding") < rebuilt.index("\n\nsubject")


def test_a_rebuilt_commit_keeps_a_mergetag_header() -> None:
    raw = f"tree {SHA_C}\nmergetag object {SHA_A}\n type commit\n\nmerge\n"

    assert "mergetag" in rebuild_commit(raw, {}, "merge\n")


def test_nothing_is_in_progress_when_no_marker_exists() -> None:
    assert in_progress(set()) is None


def test_each_marker_names_its_operation() -> None:
    expected = {
        "rebase-merge": "rebase",
        "rebase-apply": "rebase",
        "MERGE_HEAD": "merge",
        "CHERRY_PICK_HEAD": "cherry-pick",
        "REVERT_HEAD": "revert",
        "rebase-apply/applying": "git am",
        "BISECT_LOG": "bisect",
    }
    for marker, name in expected.items():
        problem = in_progress({marker})
        assert problem is not None
        assert name in problem


def test_a_mailbox_apply_is_not_called_a_rebase() -> None:
    problem = in_progress({"rebase-apply", "rebase-apply/applying"})

    assert problem is not None
    assert "git am" in problem
    assert "rebase" not in problem


def test_the_refusal_for_a_detached_head_asks_for_a_checked_out_branch() -> None:
    assert "branch" in message_detached()


def test_the_refusal_without_a_default_branch_asks_for_a_base() -> None:
    message = message_needs_base("origin/main")

    assert "<base>" in message
    assert "origin/main" in message


def test_the_refusal_for_an_unknown_base_names_it() -> None:
    assert "nonsense" in message_unknown_base("nonsense")


def test_the_refusal_for_a_base_that_is_no_ancestor_says_so() -> None:
    assert "not an ancestor of HEAD" in message_not_ancestor("topic")


def test_the_report_after_a_rewrite_holds_the_counts_both_tips_and_the_force_hint() -> (
    None
):
    lines = report(2, 3, SHA_A, SHA_B)

    assert lines[0].startswith("strip:")
    assert "2" in lines[0] and "3" in lines[0]
    assert SHA_A in lines[0] and SHA_B in lines[0]
    assert "git push --force-with-lease" in lines[1]


def test_the_report_with_nothing_to_rewrite_says_nothing_needs_pushing_again() -> None:
    lines = report(0, 3, SHA_A, SHA_A)

    assert lines[0].startswith("strip:")
    assert "0" in lines[0]
    assert "nothing needs pushing again" in lines[1]
    assert "force" not in " ".join(lines)


def test_a_message_whose_last_paragraph_has_no_demanding_line_is_returned_as_it_is() -> (
    None
):
    message = "x\n\nSigned-off-by: A\n"

    assert stripped(message, "Prepush-CI: full\n") == message


def test_the_refusal_for_a_dirty_worktree_lists_every_path() -> None:
    message = message_dirty(["a.txt", "b/c.txt"])

    assert "not clean" in message
    assert "  a.txt\n  b/c.txt" in message


def test_the_refusal_for_hidden_changes_lists_every_path_and_says_how_to_clear_them() -> (
    None
):
    message = message_hidden(["a.txt"])

    assert "  a.txt" in message
    assert "--no-assume-unchanged" in message
