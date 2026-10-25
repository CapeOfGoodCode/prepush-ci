from collections.abc import Mapping
from typing import Any

import pytest

from prepush_ci.core.config import (
    Config,
    ConfigError,
    Results,
    Trailer,
    is_env_name,
    parse_config,
)


def problems_of(table: Mapping[str, Any]) -> list[str]:
    with pytest.raises(ConfigError) as error_info:
        parse_config(table)
    return error_info.value.problems


def test_only_the_check_is_given_and_every_other_key_takes_its_default() -> None:
    assert parse_config({"check": "scripts/ci"}) == Config(
        check="scripts/ci",
        preflight=None,
        require_env=(),
        require_up_to_date="origin/main",
        default_branch="main",
        trailer=Trailer(key="Prepush-CI", value="full"),
        legacy_keys=(),
        cache=True,
    )


def test_every_key_is_given_and_the_parsed_config_holds_exactly_those_values() -> None:
    table = {
        "check": "make ci",
        "preflight": "make lint",
        "require_env": ["DATABASE_URL"],
        "require_up_to_date": "upstream/develop",
        "default_branch": "trunk",
        "trailer": {"key": "Full-Check", "value": "yes"},
        "legacy_keys": ["Full-Pre-Push"],
        "cache": False,
        "results": {"coverage": "out/cov.json"},
    }

    assert parse_config(table) == Config(
        check="make ci",
        preflight="make lint",
        require_env=("DATABASE_URL",),
        require_up_to_date="upstream/develop",
        default_branch="trunk",
        trailer=Trailer(key="Full-Check", value="yes"),
        legacy_keys=("Full-Pre-Push",),
        cache=False,
        results=Results(coverage="out/cov.json"),
    )


def test_up_to_date_ref_follows_the_default_branch() -> None:
    config = parse_config({"check": "x", "default_branch": "trunk"})

    assert config.require_up_to_date == "origin/trunk"


def test_up_to_date_set_to_true_means_origin_and_the_default_branch() -> None:
    config = parse_config(
        {"check": "x", "default_branch": "trunk", "require_up_to_date": True}
    )

    assert config.require_up_to_date == "origin/trunk"


def test_up_to_date_check_disabled_leaves_no_up_to_date_ref() -> None:
    config = parse_config({"check": "x", "require_up_to_date": False})

    assert config.require_up_to_date is None


def test_trailer_table_with_only_a_key_takes_the_default_value() -> None:
    config = parse_config({"check": "x", "trailer": {"key": "Full-Check"}})

    assert config.trailer == Trailer(key="Full-Check", value="full")


def test_trailer_table_with_only_a_value_takes_the_default_key() -> None:
    config = parse_config({"check": "x", "trailer": {"value": "yes"}})

    assert config.trailer == Trailer(key="Prepush-CI", value="yes")


def test_missing_check_is_reported_as_required() -> None:
    problems = problems_of({"cache": False})

    assert len(problems) == 1
    assert "`check` is required" in problems[0]


def test_unknown_key_is_reported_by_name() -> None:
    problems = problems_of({"check": "x", "chekc": "scripts/ci"})

    assert len(problems) == 1
    assert "unknown key `chekc`" in problems[0]


def test_unknown_key_in_the_trailer_table_is_reported_by_its_full_path() -> None:
    problems = problems_of({"check": "x", "trailer": {"key": "X", "valeu": "y"}})

    assert len(problems) == 1
    assert "unknown key `trailer.valeu`" in problems[0]


def test_wrong_type_is_reported_with_the_key_and_the_expected_type() -> None:
    problems = problems_of({"check": "x", "cache": "yes"})

    assert len(problems) == 1
    assert "`cache` must be a boolean" in problems[0]


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("check", 3, "`check` must be a string"),
        ("preflight", ["a"], "`preflight` must be a string"),
        ("require_env", "HOME", "`require_env` must be a list of strings"),
        ("require_env", ["HOME", 3], "`require_env` must be a list of strings"),
        (
            "require_up_to_date",
            3,
            "`require_up_to_date` must be a string or a boolean",
        ),
        ("default_branch", 3, "`default_branch` must be a string"),
        ("trailer", "Prepush-CI: full", "`trailer` must be a table"),
        ("trailer", {"key": 3}, "`trailer.key` must be a string"),
        ("trailer", {"value": 3}, "`trailer.value` must be a string"),
        ("legacy_keys", "Full", "`legacy_keys` must be a list of strings"),
    ],
)
def test_every_key_with_a_value_of_the_wrong_type_is_reported(
    key: str, value: Any, expected: str
) -> None:
    table = {"check": "x"}
    table[key] = value

    problems = problems_of(table)

    assert len(problems) == 1
    assert expected in problems[0]


@pytest.mark.parametrize(
    "key", ["check", "preflight", "default_branch", "require_up_to_date"]
)
def test_an_empty_string_where_a_command_branch_or_ref_is_expected_is_reported(
    key: str,
) -> None:
    table = {"check": "x"}
    table[key] = ""

    problems = problems_of(table)

    assert len(problems) == 1
    assert f"`{key}` must not be empty" in problems[0]


def test_several_problems_are_reported_at_once() -> None:
    problems = problems_of({"check": "x", "foo": 1, "default_branch": 3})

    assert len(problems) == 2
    assert any("`foo`" in problem for problem in problems)
    assert any("`default_branch`" in problem for problem in problems)


def test_a_wrong_default_branch_does_not_hide_the_other_problems() -> None:
    problems = problems_of({"default_branch": 3, "require_up_to_date": True})

    assert any("`check` is required" in problem for problem in problems)
    assert any("`default_branch` must be a string" in problem for problem in problems)


def test_a_trailer_key_with_a_space_is_not_a_valid_trailer_key() -> None:
    problems = problems_of(
        {"check": "x", "trailer": {"key": "Prepush CI", "value": "full"}}
    )

    assert len(problems) == 1
    assert "`trailer.key` is not a valid trailer key" in problems[0]


def test_an_empty_trailer_key_is_not_a_valid_trailer_key() -> None:
    problems = problems_of({"check": "x", "trailer": {"key": "", "value": "full"}})

    assert len(problems) == 1
    assert "`trailer.key` is not a valid trailer key" in problems[0]


def test_a_legacy_key_with_a_space_is_not_a_valid_trailer_key() -> None:
    problems = problems_of({"check": "x", "legacy_keys": ["Full Pre-Push"]})

    assert len(problems) == 1
    assert "`legacy_keys`" in problems[0]
    assert "Full Pre-Push" in problems[0]


def test_an_empty_legacy_key_is_not_a_valid_trailer_key() -> None:
    problems = problems_of({"check": "x", "legacy_keys": ["Full-Pre-Push", ""]})

    assert len(problems) == 1
    assert "`legacy_keys`" in problems[0]


@pytest.mark.parametrize(
    "value", ["", "full\nSigned-off-by: x", "full\r", "  full  ", "full "]
)
def test_a_trailer_value_that_is_empty_multi_line_or_padded_is_reported(
    value: str,
) -> None:
    problems = problems_of({"check": "x", "trailer": {"value": value}})

    assert len(problems) == 1
    assert "`trailer.value`" in problems[0]


def reported(name: str) -> str:
    """The one problem that a config with `require_env = [name]` has."""
    problems = problems_of({"check": "true", "require_env": [name]})

    assert len(problems) == 1
    assert "`require_env`" in problems[0]
    assert repr(name) in problems[0]
    return problems[0]


def test_an_empty_name_in_require_env_is_reported_with_the_key_and_the_entry() -> None:
    reported("")


def test_a_name_with_whitespace_in_require_env_is_reported_with_the_key_and_the_entry() -> (
    None
):
    reported("DATABASE URL")


def test_names_with_a_hyphen_or_a_dot_in_require_env_are_reported_with_the_key_and_both() -> (
    None
):
    problems = problems_of({"check": "true", "require_env": ["MY-VAR", "A.B"]})

    assert len(problems) == 2
    assert all("`require_env`" in problem for problem in problems)
    assert "'MY-VAR'" in problems[0] and "'A.B'" in problems[1]


def test_a_name_starting_with_a_digit_in_require_env_is_reported_with_the_entry() -> (
    None
):
    reported("1A")


def test_a_name_with_an_equals_sign_in_require_env_is_reported_with_the_entry() -> None:
    reported("DATABASE_URL=x")


def test_one_bad_name_among_good_ones_is_reported_with_an_unknown_key() -> None:
    problems = problems_of(
        {"check": "true", "require_env": ["DATABASE_URL", "", "_TOKEN1"], "foo": 1}
    )

    assert len(problems) == 2
    assert any("`foo`" in problem for problem in problems)
    assert sum("`require_env`" in problem for problem in problems) == 1


def test_valid_names_in_require_env_load_exactly_as_given() -> None:
    config = parse_config(
        {"check": "true", "require_env": ["DATABASE_URL", "_TOKEN1", "a"]}
    )

    assert config.require_env == ("DATABASE_URL", "_TOKEN1", "a")


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("DATABASE_URL", True),
        ("_X1", True),
        ("a", True),
        ("", False),
        ("A=1", False),
        ("=A", False),
        ("A B", False),
        ("MY-VAR", False),
        ("A.B", False),
        ("1A", False),
        ("A\n", False),
        ("ÄB", False),
    ],
)
def test_a_variable_name_is_valid_only_in_the_portable_form(
    name: str, valid: bool
) -> None:
    assert is_env_name(name) is valid


def default_branch_problems(value: str, **more: Any) -> list[str]:
    return problems_of({"check": "x", "default_branch": value, **more})


def test_a_default_branch_name_with_a_slash_loads_with_its_up_to_date_ref() -> None:
    config = parse_config({"check": "x", "default_branch": "release/1"})

    assert config.default_branch == "release/1"
    assert config.require_up_to_date == "origin/release/1"


def test_a_default_branch_that_is_a_ref_is_reported_together_with_the_other_problems() -> (
    None
):
    problems = default_branch_problems("refs/heads/main", foo=1)

    assert len(problems) == 2
    assert any("`foo`" in problem for problem in problems)
    assert any("`default_branch`" in problem for problem in problems)


@pytest.mark.parametrize(
    ("value", "branch"),
    [
        ("refs/remotes/origin/trunk", "trunk"),
        ("refs/heads/release/1", "release/1"),
        ("origin/trunk", "trunk"),
    ],
)
def test_a_default_branch_that_is_not_a_branch_name_is_reported_with_the_name_to_write(
    value: str, branch: str
) -> None:
    problems = default_branch_problems(value)

    assert len(problems) == 1
    assert "`default_branch`" in problems[0]
    assert f'use "{branch}"' in problems[0]


@pytest.mark.parametrize(
    "value", ["refs/tags/v1", "refs/remotes/upstream/x", "origin/"]
)
def test_a_default_branch_that_is_not_a_branch_name_gets_no_name_to_write_when_none_fits(
    value: str,
) -> None:
    problems = default_branch_problems(value)

    assert len(problems) == 1
    assert "`default_branch`" in problems[0]
    assert "branch name is expected" in problems[0]
    assert 'use "' not in problems[0]
