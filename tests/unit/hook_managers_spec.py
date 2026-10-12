import pytest

from prepush_ci.core.hook_managers import (
    BEGIN,
    END,
    Refusal,
    find_block,
    join_lines,
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
