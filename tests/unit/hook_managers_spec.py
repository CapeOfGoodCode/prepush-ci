import pytest

from prepush_ci.core.hook_managers import (
    BEGIN,
    END,
    PRE_COMMIT_FILE,
    Refusal,
    choose,
    edit_file,
    edit_pre_commit,
    find_block,
    holds_block,
    join_lines,
    manager_files,
    manager_report,
    missing_message,
    place_block,
    split_lines,
)

BLOCK = [BEGIN, "ours", END]


def test_lines_are_split_without_their_line_ends_and_joined_back_with_them() -> None:
    lines, eol = split_lines("a\nb\n")

    assert (lines, eol) == (["a", "b"], "\n")
    assert join_lines(lines, eol) == "a\nb\n"


def test_a_file_with_crlf_line_ends_keeps_them() -> None:
    lines, eol = split_lines("a\r\nb\r\n")

    assert (lines, eol) == (["a", "b"], "\r\n")
    assert join_lines(lines, eol) == "a\r\nb\r\n"


def test_a_file_without_a_final_line_end_has_the_same_lines() -> None:
    assert split_lines("a\nb") == (["a", "b"], "\n")


def test_an_empty_file_has_no_lines() -> None:
    assert split_lines("") == ([], "\n")
    assert join_lines([], "\n") == ""


def test_a_block_is_found_by_its_markers_whatever_their_indentation() -> None:
    lines = ["x", f"  {BEGIN}", "  ours", f"  {END}", "y"]

    assert find_block(lines) == (1, 3)


def test_a_file_without_a_block_has_none() -> None:
    assert find_block(["x", "y"]) is None


def test_the_block_that_holds_the_needle_is_the_one_found() -> None:
    lines = [BEGIN, "one", END, "x", BEGIN, "two", END]

    assert find_block(lines, "two") == (4, 6)
    assert find_block(lines, "one") == (0, 2)
    assert find_block(lines, "three") is None


def test_a_begin_marker_without_an_end_marker_is_refused() -> None:
    with pytest.raises(Refusal, match="without a matching"):
        find_block(["x", BEGIN, "ours"])


def test_a_new_block_goes_in_before_the_line_it_is_given() -> None:
    assert place_block(["a", "b", "c"], BLOCK, 1) == ["a", *BLOCK, "b", "c"]


def test_a_new_block_can_end_the_file() -> None:
    assert place_block(["a"], BLOCK, 1) == ["a", *BLOCK]


def test_an_existing_block_is_replaced_in_place_and_no_other_line_changes() -> None:
    lines = ["a", BEGIN, "old", "older", END, "b"]

    assert place_block(lines, BLOCK, 0) == ["a", *BLOCK, "b"]


TWO_REPOS = (
    "repos:\n"
    "  - repo: https://example.com/one\n"
    "    rev: v1\n"
    "    hooks:\n"
    "      - id: one\n"
    "  - repo: https://example.com/two\n"
    "    rev: v2\n"
    "    hooks:\n"
    "      - id: two\n"
)


def test_the_pre_commit_block_follows_the_last_repo_and_precedes_the_next_key() -> None:
    text = edit_pre_commit(TWO_REPOS + "exclude: '^vendor/'\n")

    lines = text.splitlines()
    begin = lines.index(f"  {BEGIN}")
    assert lines[begin - 1] == "      - id: two"
    assert lines[lines.index(f"  {END}") + 1] == "exclude: '^vendor/'"
    assert TWO_REPOS.splitlines()[1] in lines


def test_the_pre_commit_block_takes_the_indentation_of_the_other_repos() -> None:
    text = edit_pre_commit("repos:\n- repo: local\n  hooks: []\n")

    assert (
        f"\n{BEGIN}\n- repo: local\n  hooks:\n    - id: prepush-ci-commit-msg\n" in text
    )


def test_the_pre_commit_hooks_name_their_stages_and_call_the_tool_from_path() -> None:
    block = edit_pre_commit(TWO_REPOS)

    assert "entry: prepush-ci hook commit-msg\n" in block
    assert "stages: [commit-msg]" in block
    assert "entry: prepush-ci hook pre-push\n" in block
    assert (
        "stages: [pre-push]\n        pass_filenames: false\n        always_run" in block
    )
    assert "args" not in block


def test_comments_and_blank_lines_after_the_last_repo_stay_after_the_block() -> None:
    text = edit_pre_commit(TWO_REPOS + "\n# keep\nfail_fast: true\n")

    assert text.index(END) < text.index("# keep") < text.index("fail_fast")


def test_a_comment_between_repos_does_not_end_the_list() -> None:
    text = edit_pre_commit(
        "repos:\n  - repo: a\n    hooks: []\n# a comment\n  - repo: b\n    hooks: []\n"
    )

    assert text.index("repo: b") < text.index(BEGIN)


def test_a_missing_hook_types_key_is_added_before_repos_with_the_default_stage() -> (
    None
):
    text = edit_pre_commit(TWO_REPOS)

    assert text.startswith(
        "default_install_hook_types: [pre-commit, commit-msg, pre-push]\n"
        "default_stages: [pre-commit]\n"
        "repos:\n"
    )


def test_a_flow_list_lacking_one_type_gets_it_appended() -> None:
    text = edit_pre_commit(
        "default_install_hook_types: [pre-commit, pre-push]\n" + TWO_REPOS
    )

    assert text.startswith(
        "default_install_hook_types: [pre-commit, pre-push, commit-msg]\n"
        "default_stages: [pre-commit, pre-push]\n"
    )


def test_a_flow_list_keeps_its_comment_and_its_quotes() -> None:
    text = edit_pre_commit(
        "default_install_hook_types: ['pre-commit']  # types\n" + TWO_REPOS
    )

    assert text.startswith(
        "default_install_hook_types: ['pre-commit', commit-msg, pre-push] # types\n"
    )
    assert "default_stages: [pre-commit]\n" in text


def test_a_block_list_gets_the_missing_types_each_on_its_own_line() -> None:
    text = edit_pre_commit(
        "default_install_hook_types:\n  - pre-commit\n  # note\n" + TWO_REPOS
    )

    assert text.startswith(
        "default_install_hook_types:\n"
        "  - pre-commit\n  - commit-msg\n  - pre-push\n  # note\n"
    )
    assert "default_stages: [pre-commit]\n" in text


def test_a_block_list_at_the_indentation_of_its_key_is_read() -> None:
    text = edit_pre_commit("default_install_hook_types:\n- pre-push\n" + TWO_REPOS)

    assert "default_install_hook_types:\n- pre-push\n- commit-msg\n" in text
    assert "default_stages: [pre-push]\n" in text


def test_hook_types_already_covered_add_no_default_stages() -> None:
    config = (
        "default_install_hook_types: [pre-commit, commit-msg, pre-push]\n" + TWO_REPOS
    )

    assert "default_stages" not in edit_pre_commit(config)


def test_hook_types_already_covered_in_a_block_list_change_nothing() -> None:
    config = "default_install_hook_types:\n  - commit-msg\n  - 'pre-push'\n" + TWO_REPOS

    text = edit_pre_commit(config)

    assert text.startswith(config.split("repos:")[0])
    assert "default_stages" not in text


def test_chosen_default_stages_are_left_alone() -> None:
    text = edit_pre_commit("default_stages: [pre-commit, pre-push]\n" + TWO_REPOS)

    assert text.count("default_stages") == 1
    assert text.startswith("default_stages: [pre-commit, pre-push]\n")


def test_a_second_run_changes_nothing() -> None:
    once = edit_pre_commit(TWO_REPOS)

    assert edit_pre_commit(once) == once


def test_a_hand_edit_of_the_pre_commit_block_is_undone() -> None:
    once = edit_pre_commit(TWO_REPOS)

    edited = once.replace("language: system", "language: python", 1)

    assert edit_pre_commit(edited) == once


def test_a_pre_commit_file_keeps_its_crlf_line_ends() -> None:
    text = edit_pre_commit(TWO_REPOS.replace("\n", "\r\n"))

    assert text.count("\r\n") == text.count("\n")


@pytest.mark.parametrize(
    "config",
    ["repos: []\n", "repos: [{repo: local}]\n", "hooks: []\n", ""],
)
def test_repos_that_is_not_a_block_list_is_refused(config: str) -> None:
    with pytest.raises(Refusal, match="repos"):
        edit_pre_commit(config)


@pytest.mark.parametrize("config", ["repos:\n", "repos:\nexclude: x\n"])
def test_repos_without_entries_is_refused(config: str) -> None:
    with pytest.raises(Refusal, match="no entries"):
        edit_pre_commit(config)


def test_repos_whose_first_line_is_not_a_list_item_is_refused() -> None:
    with pytest.raises(Refusal, match="block list of"):
        edit_pre_commit("repos:\n  repo: local\n")


@pytest.mark.parametrize(
    "key",
    ["default_install_hook_types: pre-push\n", "default_install_hook_types: [a,\n"],
)
def test_hook_types_in_another_form_are_refused(key: str) -> None:
    with pytest.raises(Refusal, match="default_install_hook_types"):
        edit_pre_commit(key + TWO_REPOS)


def test_hook_types_with_a_block_list_that_has_no_items_are_refused() -> None:
    with pytest.raises(Refusal, match="no items"):
        edit_pre_commit("default_install_hook_types:\n" + TWO_REPOS)


def test_hook_types_after_repos_at_the_end_of_the_file_are_extended() -> None:
    text = edit_pre_commit(TWO_REPOS + "default_install_hook_types:\n  - pre-commit\n")

    assert text.endswith(
        "default_install_hook_types:\n  - pre-commit\n  - commit-msg\n  - pre-push\n"
    )
    assert text.index("default_stages: [pre-commit]") < text.index("repos:")


def test_without_a_manager_or_an_option_the_hooks_are_native() -> None:
    assert choose(None, []) == "native"


def test_a_single_manager_found_is_the_one_chosen() -> None:
    assert choose(None, ["pre-commit"]) == "pre-commit"


def test_the_option_wins_over_what_is_found() -> None:
    assert choose("native", ["pre-commit"]) == "native"
    assert choose("pre-commit", []) == "pre-commit"


def test_several_managers_are_refused_naming_them_and_the_option() -> None:
    with pytest.raises(Refusal) as refusal:
        choose(None, ["pre-commit", "husky"])

    assert "pre-commit, husky" in str(refusal.value)
    assert "--hooks" in str(refusal.value)


def test_a_missing_manager_names_the_file_it_needs() -> None:
    assert ".pre-commit-config.yaml" in missing_message("pre-commit")


def test_pre_commit_edits_its_one_config_file() -> None:
    assert manager_files("pre-commit", [PRE_COMMIT_FILE]) == [PRE_COMMIT_FILE]
    assert BEGIN in edit_file("pre-commit", PRE_COMMIT_FILE, TWO_REPOS)


def test_a_text_holds_the_block_once_edited() -> None:
    assert not holds_block(TWO_REPOS)
    assert holds_block(edit_pre_commit(TWO_REPOS))


def test_the_report_names_the_files_and_the_step_that_activates_the_hooks() -> None:
    report = manager_report("installed", "pre-commit", [PRE_COMMIT_FILE])

    assert report.splitlines()[0] == "installed: pre-commit"
    assert f"  {PRE_COMMIT_FILE}" in report
    assert "`pre-commit install`" in report


def test_the_report_of_a_manager_without_an_activation_step_names_none() -> None:
    report = manager_report("installed", "husky", [".husky/pre-push"])

    assert report == "installed: husky\n  .husky/pre-push"
