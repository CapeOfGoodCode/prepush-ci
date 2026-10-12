import tomllib

import pytest

from prepush_ci.core.config import Config, ConfigError, parse_config
from prepush_ci.core.init import (
    ConfigFlags,
    config_text,
    disagreement_message,
    disagreements,
    problems_message,
    resolved_up_to_date,
    toml_string,
    validate,
)


def loaded(**flags: object) -> Config:
    return validate(config_text(ConfigFlags(**flags)))  # type: ignore[arg-type]


def test_the_config_holds_only_the_check_when_only_the_check_is_given() -> None:
    assert config_text(ConfigFlags(check="scripts/ci")) == 'check = "scripts/ci"\n'


def test_every_flag_given_is_written_and_loads_back() -> None:
    config = loaded(
        check="make ci",
        preflight="make up",
        require_env=("A", "B"),
        require_up_to_date="upstream/trunk",
        default_branch="trunk",
    )

    assert config.check == "make ci"
    assert config.preflight == "make up"
    assert config.require_env == ("A", "B")
    assert config.require_up_to_date == "upstream/trunk"
    assert config.default_branch == "trunk"


def test_a_value_equal_to_the_default_is_still_written() -> None:
    text = config_text(ConfigFlags(check="x", default_branch="main"))

    assert tomllib.loads(text) == {"check": "x", "default_branch": "main"}


def test_false_and_true_are_written_as_booleans() -> None:
    assert tomllib.loads(config_text(ConfigFlags(require_up_to_date="false"))) == {
        "require_up_to_date": False
    }
    assert tomllib.loads(config_text(ConfigFlags(require_up_to_date="true"))) == {
        "require_up_to_date": True
    }


def test_switching_the_up_to_date_check_off_loads_as_no_ref() -> None:
    assert loaded(check="x", require_up_to_date="false").require_up_to_date is None


def test_quotes_and_backslashes_in_a_check_survive() -> None:
    check = 'sh -c "make ci" \\ done\ttab'

    assert loaded(check=check).check == check


def test_a_string_is_written_as_a_toml_basic_string() -> None:
    assert toml_string('a"b') == '"a\\"b"'
    assert toml_string("a\\b") == '"a\\\\b"'
    assert toml_string("a\tb\nc\r") == '"a\\tb\\nc\\r"'


def test_a_control_character_is_escaped_as_toml_wants_it() -> None:
    assert toml_string("a\x00b\x7fc") == '"a\\u0000b\\u007fc"'
    assert loaded(check="a\x01b\x7f").check == "a\x01b\x7f"


def test_a_character_outside_the_basic_plane_is_written_as_it_is() -> None:
    assert toml_string("echo \N{GRINNING FACE}") == '"echo \N{GRINNING FACE}"'
    assert loaded(check="echo \N{GRINNING FACE}").check == "echo \N{GRINNING FACE}"


def test_a_lone_surrogate_has_no_toml_string() -> None:
    with pytest.raises(ValueError, match="not valid text"):
        toml_string("echo \udcff")


def test_a_value_the_config_rejects_names_its_key() -> None:
    try:
        validate(config_text(ConfigFlags(check="")))
    except ConfigError as error:
        assert "`check` must not be empty" in problems_message(error)
    else:
        raise AssertionError("an empty check was accepted")


def config() -> Config:
    return parse_config(
        {
            "check": "scripts/ci",
            "preflight": "make up",
            "require_env": ["A"],
            "default_branch": "trunk",
        }
    )


def test_flags_that_agree_with_the_config_disagree_on_nothing() -> None:
    flags = ConfigFlags(
        check="scripts/ci",
        preflight="make up",
        require_env=("A",),
        require_up_to_date="true",
        default_branch="trunk",
    )

    assert disagreements(config(), flags) == []


def test_no_flag_disagrees_on_nothing() -> None:
    assert disagreements(config(), ConfigFlags()) == []


def test_every_key_that_differs_is_named() -> None:
    flags = ConfigFlags(
        check="make ci",
        preflight="x",
        require_env=("B",),
        require_up_to_date="other/ref",
        default_branch="main",
    )

    assert disagreements(config(), flags) == [
        "check",
        "preflight",
        "require_env",
        "require_up_to_date",
        "default_branch",
    ]


def test_true_stands_for_the_origin_ref_of_the_config_default_branch() -> None:
    assert resolved_up_to_date("true", "trunk") == "origin/trunk"
    assert resolved_up_to_date("false", "trunk") is None
    assert resolved_up_to_date("up/x", "trunk") == "up/x"


def test_the_message_names_each_key_and_the_source() -> None:
    message = disagreement_message(["check", "preflight"], ".prepush-ci.toml")

    assert "`check`, `preflight`" in message
    assert ".prepush-ci.toml" in message
