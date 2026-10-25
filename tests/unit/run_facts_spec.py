"""The facts of a run: read from the files the check wrote, kept as numbers, written into one line."""

import json

import pytest

from prepush_ci.core.report import Counts
from prepush_ci.core.run_facts import (
    MAX_FILES,
    FactError,
    RunFacts,
    Tally,
    coverage_of,
    from_line,
    junit_tally,
    message_left_alone,
    message_no_fact,
    mypy_errors,
    ruff_errors,
    run_facts,
    to_line,
)

TOP = "/work/repo"


def case(file: str | None, outcome: str = "") -> str:
    where = "" if file is None else f' file="{file}"'
    inner = f"<{outcome}/>" if outcome else ""
    return f'<testcase classname="c" name="n"{where}>{inner}</testcase>'


def junit(*cases: str) -> bytes:
    return f"<testsuites><testsuite>{''.join(cases)}</testsuite></testsuites>".encode()


def tally(data: bytes, tree: frozenset[str] = frozenset()) -> Tally:
    return junit_tally(data, "a.xml", TOP, tree.__contains__)


def test_cases_are_counted_per_test_file_of_the_tree() -> None:
    data = junit(
        case("tests/a_spec.py"),
        case("tests/a_spec.py"),
        case("tests/a_spec.py"),
        case("tests/a_spec.py", "skipped"),
        case("tests/b_spec.py", "failure"),
    )

    found = tally(data, frozenset({"tests/a_spec.py", "tests/b_spec.py"}))

    assert found.files == {
        "tests/a_spec.py": Counts(passed=3, skipped=1),
        "tests/b_spec.py": Counts(failed=1),
    }
    assert found.other == Counts()


def test_an_error_case_counts_as_failed_as_report_counts_it() -> None:
    found = tally(junit(case("a.py", "error")), frozenset({"a.py"}))

    assert found.files == {"a.py": Counts(failed=1)}


def test_a_file_that_is_not_in_the_tree_is_counted_under_other() -> None:
    found = tally(junit(case("/home/someone/secret.py")), frozenset({"a.py"}))

    assert found.files == {}
    assert found.other == Counts(passed=1)


def test_a_relative_file_name_that_is_not_in_the_tree_is_counted_under_other() -> None:
    found = tally(junit(case("tests/gone_spec.py")), frozenset({"a.py"}))

    assert found.files == {}
    assert found.other == Counts(passed=1)


def test_a_case_without_a_file_is_counted_under_other() -> None:
    found = tally(junit(case(None), case(None, "skipped")), frozenset({"a.py"}))

    assert found.files == {}
    assert found.other == Counts(passed=1, skipped=1)


def test_a_file_written_with_backslashes_is_taken_as_report_takes_paths() -> None:
    found = tally(junit(case("tests\\a_spec.py")), frozenset({"tests/a_spec.py"}))

    assert found.files == {"tests/a_spec.py": Counts(passed=1)}


def test_a_file_that_climbs_out_of_the_worktree_is_counted_under_other() -> None:
    found = tally(junit(case("../a.py")), frozenset({"a.py"}))

    assert found.files == {}
    assert found.other == Counts(passed=1)


def test_xml_that_is_not_junit_has_no_facts() -> None:
    with pytest.raises(FactError) as caught:
        tally(b"<html/>")

    assert "JUnit" in str(caught.value)
    assert "html" not in str(caught.value)


def test_two_tallies_add_up_file_by_file() -> None:
    first = tally(junit(case("a.py"), case(None)), frozenset({"a.py"}))
    second = tally(
        junit(case("a.py", "failure"), case("b.py")), frozenset({"a.py", "b.py"})
    )

    total = first + second

    assert total.files == {
        "a.py": Counts(passed=1, failed=1),
        "b.py": Counts(passed=1),
    }
    assert total.other == Counts(passed=1)


def test_the_facts_add_the_tests_of_every_junit_file() -> None:
    first = tally(junit(case("a.py"), case("a.py")), frozenset({"a.py"}))
    second = tally(junit(case("a.py"), case("a.py"), case("a.py")), frozenset({"a.py"}))

    facts = run_facts(5, [first, second])

    assert facts.tests == Counts(passed=5)
    assert facts.files == (("a.py", Counts(passed=5)),)
    assert facts.other is None


def test_the_facts_hold_only_the_duration_when_nothing_is_named() -> None:
    assert run_facts(492, []) == RunFacts(seconds=492)


def test_the_facts_hold_at_most_fifty_files_the_largest_first_and_sum_the_rest_under_other() -> (
    None
):
    names = [f"t/f{index:02d}.py" for index in range(60)]
    cases = [case(name) for name in names] + [case(names[59])]  # f59 has two cases
    found = tally(junit(*cases), frozenset(names))

    facts = run_facts(1, [found])

    assert len(facts.files) == MAX_FILES == 50
    assert facts.files[0] == ("t/f59.py", Counts(passed=2))
    assert [name for name, _ in facts.files[1:]] == names[:49]
    assert facts.other == Counts(passed=10)
    assert facts.tests == Counts(passed=61)


def test_the_cases_under_other_are_added_to_the_cases_of_the_files_over_the_limit() -> (
    None
):
    names = [f"t/f{index:02d}.py" for index in range(51)]
    found = tally(junit(*[case(name) for name in names], case(None)), frozenset(names))

    facts = run_facts(1, [found])

    assert facts.other == Counts(passed=2)


@pytest.mark.parametrize("text", ["94.5", "100", "0", "7", "99.99", "0.0"])
def test_a_coverage_written_as_digits_is_kept_as_the_file_wrote_it(text: str) -> None:
    document = json.dumps({"totals": {"percent_covered_display": text}})

    assert coverage_of(document, "cov.json") == text


@pytest.mark.parametrize(
    "text",
    [
        "nan",
        "inf",
        "1e3",
        "-5",
        "101",
        "100.5",
        "9 4",
        ".",
        ".5",
        "100.",
        "١٠٠",
        "٩٤.٥",
        "see https://example.com",
        "",
    ],
)
def test_forms_that_are_not_coverage_give_no_fact(text: str) -> None:
    document = json.dumps({"totals": {"percent_covered_display": text}})

    with pytest.raises(FactError) as caught:
        coverage_of(document, "cov.json")

    assert text not in str(caught.value) or text == ""


def test_a_coverage_file_that_is_not_coverage_json_gives_no_fact() -> None:
    with pytest.raises(FactError) as caught:
        coverage_of("TOKEN=abc123", "cov.json")

    assert "abc123" not in str(caught.value)


def test_a_ruff_file_is_counted_by_the_entries_of_its_array() -> None:
    assert ruff_errors("[]") == 0
    assert ruff_errors('[{"code": "E1"}, {"code": "E2"}]') == 2


@pytest.mark.parametrize("text", ["TOKEN=abc123", '{"code": "E1"}', ""])
def test_a_ruff_file_that_is_not_an_array_gives_no_fact(text: str) -> None:
    with pytest.raises(FactError) as caught:
        ruff_errors(text)

    assert "abc123" not in str(caught.value)


def test_a_mypy_file_is_counted_by_its_found_line_or_success() -> None:
    assert mypy_errors("Success: no issues found in 12 source files\n") == 0
    assert mypy_errors("a.py:1: error: x\nFound 3 errors in 1 file (checked 4)") == 3
    assert mypy_errors("Found 1 error in 1 file") == 1


@pytest.mark.parametrize(
    "text",
    [
        "TOKEN=abc123",
        "Found many errors",
        "Found ٣ errors",
        "Found " + "9" * 12 + " errors",
    ],
)
def test_a_mypy_file_without_a_summary_gives_no_fact(text: str) -> None:
    with pytest.raises(FactError) as caught:
        mypy_errors(text)

    assert "abc123" not in str(caught.value)


FULL = RunFacts(
    seconds=492,
    tests=Counts(passed=812, failed=0, skipped=3),
    files=(("tests/a_spec.py", Counts(passed=3, skipped=1)),),
    other=Counts(passed=2),
    coverage="94.5",
    ruff=2,
    mypy=0,
)


def test_the_facts_are_written_as_one_ascii_line_and_read_back() -> None:
    line = to_line(FULL)

    assert "\n" not in line
    assert line.isascii()
    assert from_line(line) == FULL


def test_the_facts_of_a_name_with_other_characters_stay_one_ascii_line() -> None:
    facts = RunFacts(seconds=1, files=(("tests/é\n.py", Counts(passed=1)),))

    line = to_line(facts)

    assert "\n" not in line
    assert line.isascii()
    assert from_line(line) == facts


def test_the_facts_with_only_a_duration_are_read_back() -> None:
    assert from_line(to_line(RunFacts(seconds=7))) == RunFacts(seconds=7)


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        "{}",
        '{"v":2,"seconds":1}',
        '{"v":1}',
        '{"v":1,"seconds":-1}',
        '{"v":1,"seconds":true}',
        '{"v":1,"seconds":"1"}',
        '{"v":1,"seconds":1,"tests":[1,2]}',
        '{"v":1,"seconds":1,"tests":[1,2,"3"]}',
        '{"v":1,"seconds":1,"tests":[1,2,-3]}',
        '{"v":1,"seconds":1,"other":[1,2]}',
        '{"v":1,"seconds":1,"files":"a"}',
        '{"v":1,"seconds":1,"files":[["a",1,2]]}',
        '{"v":1,"seconds":1,"files":[[1,1,2,3]]}',
        '{"v":1,"seconds":1,"coverage":94.5}',
        '{"v":1,"seconds":1,"coverage":"see https://example.com"}',
        '{"v":1,"seconds":1,"coverage":"101"}',
        '{"v":1,"seconds":1,"ruff":"2"}',
        '{"v":1,"seconds":1,"ruff":-2}',
        '{"v":1,"seconds":1,"mypy":false}',
    ],
)
def test_facts_that_cannot_be_read_are_none(text: str) -> None:
    assert from_line(text) is None


def test_more_than_fifty_files_in_the_facts_cannot_be_read() -> None:
    files = [[f"f{index}.py", 1, 0, 0] for index in range(MAX_FILES + 1)]

    assert from_line(json.dumps({"v": 1, "seconds": 1, "files": files})) is None


def test_a_path_left_alone_is_named_by_its_key_and_its_entry_and_the_reason() -> None:
    line = message_left_alone(
        "results.coverage", "docs/cov.json", "the file is tracked"
    )

    assert line == (
        "prepush-ci: `results.coverage` ('docs/cov.json') is left alone: "
        "the file is tracked"
    )


def test_a_file_that_gives_no_fact_is_named_by_its_key_and_its_entry_and_the_reason() -> (
    None
):
    line = message_no_fact("results.junit", "out/a.xml", "the check did not write it")

    assert line == (
        "prepush-ci: `results.junit` ('out/a.xml') gives no fact: "
        "the check did not write it"
    )
