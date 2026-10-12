import json
import tomllib

import pytest

from prepush_ci.core.config import Config, ConfigError, parse_config
from prepush_ci.core.init import (
    SESSION_COMMAND,
    ConfigFlags,
    SettingsError,
    closing,
    config_text,
    disagreement_message,
    disagreements,
    problems_message,
    register_session_hook,
    resolved_up_to_date,
    session_start_script,
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


def test_the_closing_line_says_already_set_up_only_when_nothing_changed() -> None:
    assert closing(False) == "already set up"
    assert closing(True) == "set up"


def test_the_session_script_installs_the_chosen_hooks() -> None:
    assert "prepush-ci install --hooks husky\n" in session_start_script("husky")


def test_the_session_script_lets_install_detect_when_no_hooks_were_chosen() -> None:
    assert "prepush-ci install\n" in session_start_script(None)
    assert "prepush-ci install\n" in session_start_script("none")


def test_the_session_script_never_runs_uvx_or_a_manager_activation() -> None:
    script = session_start_script("pre-commit")
    commands = [line for line in script.splitlines() if not line.startswith("#")]

    assert not [
        line for line in commands if "uvx" in line or "pre-commit install" in line
    ]


def command_of(text: str) -> str:
    group = json.loads(text)["hooks"]["SessionStart"][-1]
    return str(group["hooks"][0]["command"])


def test_a_missing_settings_file_becomes_one_with_the_hook() -> None:
    text = register_session_hook(None)

    assert json.loads(text)["hooks"]["SessionStart"] == [
        {"hooks": [{"type": "command", "command": SESSION_COMMAND}]}
    ]
    assert text.endswith("}\n")


def test_the_command_runs_the_script_from_the_project_directory() -> None:
    assert SESSION_COMMAND == '"$CLAUDE_PROJECT_DIR"/.claude/hooks/session-start.sh'


def test_every_other_setting_and_hook_stays() -> None:
    before = {
        "permissions": {"allow": ["x"]},
        "hooks": {
            "PreToolUse": [1],
            "SessionStart": [{"hooks": [{"type": "command", "command": "other.sh"}]}],
        },
    }

    after = json.loads(register_session_hook(json.dumps(before)))

    assert after["permissions"] == before["permissions"]
    assert after["hooks"]["PreToolUse"] == [1]
    assert after["hooks"]["SessionStart"][0] == before["hooks"]["SessionStart"][0]
    assert command_of(json.dumps(after)) == SESSION_COMMAND


def test_a_registered_hook_leaves_the_text_exactly_as_it_was() -> None:
    text = '{"hooks":{"SessionStart":[{"hooks":[{"command":"sh .claude/hooks/session-start.sh"}]}]}}'

    assert register_session_hook(text) == text


def test_odd_entries_are_skipped_when_looking_for_the_registration() -> None:
    odd = [1, {"hooks": "x"}, {"hooks": [2, {"command": 3}, {}]}]
    text = json.dumps({"hooks": {"SessionStart": odd}})

    after = json.loads(register_session_hook(text))

    assert after["hooks"]["SessionStart"][:3] == odd
    assert len(after["hooks"]["SessionStart"]) == 4


def test_settings_that_are_not_json_are_refused_naming_the_file() -> None:
    with pytest.raises(
        SettingsError, match=r"\.claude/settings\.json is not valid JSON"
    ):
        register_session_hook("{nope")


@pytest.mark.parametrize(
    "text",
    ["[]", '{"hooks": []}', '{"hooks": {"SessionStart": {}}}'],
)
def test_settings_of_an_unexpected_shape_are_refused_naming_the_file(text: str) -> None:
    with pytest.raises(SettingsError, match=r"\.claude/settings\.json"):
        register_session_hook(text)
