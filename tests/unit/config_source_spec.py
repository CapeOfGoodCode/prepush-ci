import pytest

from prepush_ci.core.config import ConfigError
from prepush_ci.core.config_source import ConfigMissing, load_config


def problems_of(prepush_ci_toml: str | None, pyproject_toml: str | None) -> list[str]:
    with pytest.raises(ConfigError) as error_info:
        load_config(prepush_ci_toml, pyproject_toml)
    return error_info.value.problems


def test_config_file_at_the_repository_root_is_used() -> None:
    assert load_config('check = "scripts/ci"', None).check == "scripts/ci"


def test_config_in_the_pyproject_table_is_used_without_a_dedicated_file() -> None:
    pyproject = '[project]\nname = "x"\n\n[tool.prepush-ci]\ncheck = "make ci"\n'

    assert load_config(None, pyproject).check == "make ci"


def test_dedicated_file_wins_over_pyproject_toml() -> None:
    pyproject = '[tool.prepush-ci]\ncheck = "make ci"\n'

    assert load_config('check = "scripts/ci"', pyproject).check == "scripts/ci"


def test_no_config_anywhere_names_both_places() -> None:
    problems = problems_of(None, None)

    assert len(problems) == 1
    assert ".prepush-ci.toml" in problems[0]
    assert "[tool.prepush-ci]" in problems[0]


def test_pyproject_without_the_table_names_both_places() -> None:
    problems = problems_of(None, '[project]\nname = "x"\n')

    assert len(problems) == 1
    assert ".prepush-ci.toml" in problems[0]
    assert "[tool.prepush-ci]" in problems[0]


def test_pyproject_with_a_tool_table_but_without_ours_names_both_places() -> None:
    problems = problems_of(None, "[tool.ruff]\nline-length = 88\n")

    assert len(problems) == 1
    assert "[tool.prepush-ci]" in problems[0]


def test_pyproject_where_our_table_is_not_a_table_is_reported() -> None:
    problems = problems_of(None, '[tool]\nprepush-ci = "make ci"\n')

    assert len(problems) == 1
    assert "[tool.prepush-ci]" in problems[0]
    assert "must be a table" in problems[0]


def test_pyproject_where_tool_is_not_a_table_names_both_places() -> None:
    problems = problems_of(None, 'tool = "x"\n')

    assert len(problems) == 1
    assert ".prepush-ci.toml" in problems[0]


def test_malformed_toml_in_the_config_file_names_the_file_and_the_parse_error() -> None:
    problems = problems_of("check = ", None)

    assert len(problems) == 1
    assert ".prepush-ci.toml" in problems[0]
    assert "not valid TOML" in problems[0]


def test_malformed_pyproject_as_the_source_names_the_file_and_the_parse_error() -> None:
    problems = problems_of(None, "[tool.prepush-ci\n")

    assert len(problems) == 1
    assert "pyproject.toml" in problems[0]
    assert "not valid TOML" in problems[0]


def test_malformed_pyproject_is_ignored_when_the_dedicated_file_exists() -> None:
    assert load_config('check = "scripts/ci"', "[[[").check == "scripts/ci"


def test_problems_of_the_config_file_are_prefixed_with_the_file_name() -> None:
    problems = problems_of('chekc = "x"', None)

    assert len(problems) == 2
    assert all(problem.startswith(".prepush-ci.toml: ") for problem in problems)


def test_problems_of_the_pyproject_table_are_prefixed_with_the_table_name() -> None:
    problems = problems_of(None, "[tool.prepush-ci]\ncache = false\n")

    assert len(problems) == 1
    assert problems[0].startswith("pyproject.toml [tool.prepush-ci]: ")
    assert "`check` is required" in problems[0]


def test_a_missing_config_is_told_apart_from_an_invalid_one() -> None:
    with pytest.raises(ConfigMissing):
        load_config(None, '[project]\nname = "x"\n')
    with pytest.raises(ConfigError) as error_info:
        load_config("nonsense = 1", None)
    assert not isinstance(error_info.value, ConfigMissing)
