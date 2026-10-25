"""What the post-push comment says of the facts of a run, and which pass they come from."""

from prepush_ci.core.post_push import facts_block, latest_ref
from prepush_ci.core.report import Counts
from prepush_ci.core.run_facts import RunFacts

HEAD = "a" * 40
EARLIER = "b" * 40
RESULTS = "refs/prepush-ci/results"


def block(facts: RunFacts, checked: str = HEAD) -> list[str]:
    return facts_block(facts, checked, HEAD).split("\n")


FULL = RunFacts(
    seconds=492,
    tests=Counts(passed=812, failed=0, skipped=3),
    files=(
        ("tests/a_spec.py", Counts(passed=3, skipped=1)),
        ("tests/b|c_spec.py", Counts(failed=2)),
    ),
    other=Counts(passed=2),
    coverage="94.5",
    ruff=2,
    mypy=0,
)


def test_the_visible_line_holds_the_tests_the_coverage_and_the_duration() -> None:
    assert block(FULL)[0] == (
        "Facts of the run: 812 passed, 0 failed, 3 skipped; coverage 94.5%; "
        "duration 8m 12s"
    )


def test_a_coverage_that_is_a_whole_number_is_shown_whole() -> None:
    facts = RunFacts(seconds=1, coverage="100")

    assert block(facts)[0] == "Facts of the run: coverage 100%; duration 1s"


def test_the_visible_line_without_tests_or_coverage_holds_only_the_duration() -> None:
    assert block(RunFacts(seconds=492)) == [
        "Facts of the run: duration 8m 12s",
        "Checked on this commit.",
    ]


def test_the_visible_line_without_coverage_joins_the_tests_and_the_duration() -> None:
    facts = RunFacts(seconds=5, tests=Counts(passed=1))

    assert block(facts)[0] == (
        "Facts of the run: 1 passed, 0 failed, 0 skipped; duration 5s"
    )


def test_a_pass_on_this_commit_says_so_on_the_line_after_the_visible_line() -> None:
    assert block(FULL)[1] == "Checked on this commit."


def test_a_pass_of_an_earlier_commit_with_the_same_tree_names_it() -> None:
    assert block(FULL, EARLIER)[1] == f"Reused from the run on {'b' * 12}, same tree."


def test_the_details_are_collapsed_after_the_visible_line_and_the_visible_line_is_outside() -> (
    None
):
    lines = block(FULL)

    assert lines.index("<details><summary>Details</summary>") > 1
    assert lines[-1] == "</details>"
    assert "Facts of the run" not in "\n".join(
        lines[lines.index("<details><summary>Details</summary>") :]
    )


def test_the_details_hold_a_row_for_each_tool_that_the_facts_hold() -> None:
    text = facts_block(FULL, HEAD, HEAD)

    assert "| Tests | 812 passed, 0 failed, 3 skipped |" in text
    assert "| Coverage | 94.5% |" in text
    assert "| Ruff | 2 errors |" in text
    assert "| Mypy | 0 errors |" in text


def test_the_details_leave_out_a_tool_that_the_facts_do_not_hold() -> None:
    text = facts_block(RunFacts(seconds=1, ruff=1), HEAD, HEAD)

    assert "| Ruff | 1 error |" in text
    assert "Tests" not in text
    assert "Coverage" not in text
    assert "Mypy" not in text


def test_the_details_hold_a_row_for_each_test_file_in_a_code_span_and_one_for_other() -> (
    None
):
    text = facts_block(FULL, HEAD, HEAD)

    assert "| ` tests/a_spec.py ` | 3 | 0 | 1 |" in text
    assert "| ` tests/b\\|c_spec.py ` | 0 | 2 | 0 |" in text
    assert "| other | 2 | 0 | 0 |" in text


def test_cases_under_other_alone_are_still_a_row_of_the_table_of_files() -> None:
    facts = RunFacts(seconds=1, tests=Counts(passed=2), other=Counts(passed=2))

    text = facts_block(facts, HEAD, HEAD)

    assert "| Test file |" in text  # `other` alone is still a row of files
    assert "| other | 2 | 0 | 0 |" in text


def test_only_a_duration_has_no_details() -> None:
    assert "<details>" not in facts_block(RunFacts(seconds=1), HEAD, HEAD)


def test_a_test_total_without_files_or_other_has_no_table_of_files() -> None:
    text = facts_block(RunFacts(seconds=1, tests=Counts(passed=2)), HEAD, HEAD)

    assert "| Test file |" not in text
    assert "<details>" in text


def test_the_latest_pass_is_the_ref_with_the_latest_date() -> None:
    listing = f"{RESULTS}/t-aaa 100\n{RESULTS}/t-bbb 300\n{RESULTS}/t-ccc 200\n"

    assert latest_ref(listing) == f"{RESULTS}/t-bbb"


def test_of_equal_dates_the_last_ref_by_name_is_the_latest() -> None:
    listing = f"{RESULTS}/t-ccc 100\n{RESULTS}/t-aaa 100\n{RESULTS}/t-bbb 100\n"

    assert latest_ref(listing) == f"{RESULTS}/t-ccc"


def test_a_ref_without_a_readable_date_is_not_a_pass() -> None:
    assert latest_ref(f"{RESULTS}/t-aaa \n{RESULTS}/t-bbb soon\n") is None
    assert latest_ref("") is None
