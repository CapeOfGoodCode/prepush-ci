"""The `results` table of the config: which files the check writes, and which paths are refused."""

from collections.abc import Mapping
from typing import Any

import pytest

from prepush_ci.core.config import ConfigError, Results, parse_config


def parsed(results: Any) -> Results | None:
    return parse_config({"check": "x", "results": results}).results


def problems_of(results: Any, **more: Mapping[str, Any]) -> list[str]:
    with pytest.raises(ConfigError) as error_info:
        parse_config({"check": "x", "results": results, **more})
    return error_info.value.problems


def test_all_four_given_the_parsed_config_holds_those_two_junit_paths_and_those_three_paths() -> (
    None
):
    results = parsed(
        {
            "junit": ["out/a.xml", "out/b.xml"],
            "coverage": "out/cov.json",
            "ruff": "out/ruff.json",
            "mypy": "out/mypy.txt",
        }
    )

    assert results == Results(
        junit=("out/a.xml", "out/b.xml"),
        coverage="out/cov.json",
        ruff="out/ruff.json",
        mypy="out/mypy.txt",
    )


def test_only_one_given_the_parsed_config_has_that_junit_path_and_no_other() -> None:
    assert parsed({"junit": ["out/a.xml"]}) == Results(junit=("out/a.xml",))


def test_without_results_the_parsed_config_has_no_result_files() -> None:
    assert parse_config({"check": "x"}).results is None


def test_an_unknown_key_in_results_is_reported_by_its_full_path() -> None:
    problems = problems_of({"junt": ["out/a.xml"]})

    assert len(problems) == 1
    assert "`results.junt`" in problems[0]
    assert "junit" in problems[0]


def test_a_junit_entry_that_is_not_a_string_is_reported_with_the_key() -> None:
    problems = problems_of({"junit": [1]})

    assert len(problems) == 1
    assert "`results.junit`" in problems[0]


def test_a_junit_value_that_is_not_a_list_is_reported_with_the_key() -> None:
    problems = problems_of({"junit": "out/a.xml"})

    assert len(problems) == 1
    assert "`results.junit`" in problems[0]


def test_a_coverage_path_that_is_not_a_string_is_reported_with_the_key() -> None:
    problems = problems_of({"coverage": 3})

    assert len(problems) == 1
    assert "`results.coverage`" in problems[0]


def test_results_that_is_not_a_table_is_reported_with_the_key() -> None:
    problems = problems_of("out/a.xml")

    assert len(problems) == 1
    assert "`results`" in problems[0]
    assert "`results." not in problems[0]


def test_an_empty_path_is_reported_with_the_key() -> None:
    problems = problems_of({"coverage": ""})

    assert len(problems) == 1
    assert "`results.coverage`" in problems[0]


def test_an_empty_junit_entry_is_reported_with_the_key() -> None:
    problems = problems_of({"junit": ["out/a.xml", ""]})

    assert len(problems) == 1
    assert "`results.junit`" in problems[0]


def test_a_problem_in_results_does_not_hide_the_other_problems() -> None:
    problems = problems_of({"mypy": 1}, cache="yes")

    assert any("`results.mypy`" in problem for problem in problems)
    assert any("`cache`" in problem for problem in problems)


def test_a_path_above_the_worktree_is_reported_with_the_key_and_the_entry() -> None:
    problems = problems_of({"coverage": "../cov.json"})

    assert len(problems) == 1
    assert "`results.coverage`" in problems[0]
    assert "../cov.json" in problems[0]


def test_a_path_that_climbs_from_inside_a_directory_is_refused() -> None:
    problems = problems_of({"coverage": "out/../../cov.json"})

    assert "`results.coverage`" in problems[0]


def test_an_absolute_path_is_reported_with_the_key_and_the_entry() -> None:
    problems = problems_of({"mypy": "/tmp/mypy.txt"})

    assert len(problems) == 1
    assert "`results.mypy`" in problems[0]
    assert "/tmp/mypy.txt" in problems[0]


def test_a_path_with_a_drive_letter_is_reported_with_the_key() -> None:
    problems = problems_of({"ruff": "C:\\out\\ruff.json"})

    assert "`results.ruff`" in problems[0]


def test_a_path_inside_a_directory_is_fine() -> None:
    assert parsed({"coverage": "build/out/cov.json"}) == Results(
        coverage="build/out/cov.json"
    )


def test_a_drive_relative_path_is_reported_with_the_key() -> None:
    problems = problems_of({"ruff": "C:ruff.json"})

    assert "`results.ruff`" in problems[0]


def test_a_backslash_that_climbs_is_reported_with_the_key_and_the_entry() -> None:
    problems = problems_of({"coverage": "..\\cov.json"})

    assert "`results.coverage`" in problems[0]
    assert repr("..\\cov.json") in problems[0]


def test_a_leading_backslash_is_reported_with_the_key() -> None:
    problems = problems_of({"coverage": "\\out\\cov.json"})

    assert "`results.coverage`" in problems[0]


def test_a_network_path_is_reported_with_the_key() -> None:
    problems = problems_of({"junit": ["\\\\server\\share\\a.xml"]})

    assert "`results.junit`" in problems[0]


def test_the_git_config_is_reported_with_the_key_and_the_entry() -> None:
    problems = problems_of({"coverage": ".git/config"})

    assert len(problems) == 1
    assert "`results.coverage`" in problems[0]
    assert ".git/config" in problems[0]


def test_another_spelling_of_the_git_directory_is_reported_for_each_entry() -> None:
    entries = [".GIT/hooks/pre-push", "out/.git./a.xml", "GIT~1/index"]

    problems = problems_of({"junit": entries})

    assert len(problems) == 3
    for entry, problem in zip(entries, problems, strict=True):
        assert entry in problem


def test_a_trailing_space_does_not_hide_the_git_directory() -> None:
    problems = problems_of({"coverage": "out/.git /cov.json"})

    assert "`results.coverage`" in problems[0]


def test_a_name_that_only_holds_the_letters_of_the_git_directory_is_fine() -> None:
    assert parsed({"coverage": "out/.github/cov.json"}) == Results(
        coverage="out/.github/cov.json"
    )
