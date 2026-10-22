"""`README.md` tells the truth about the CLI and the config, and says what a user acts on.

The README is the PyPI long description. Its prose cannot be tested for its sense; what is tested is
that it names no command or option that does not exist, leaves none out, gives the config's keys and
defaults as the config has them, and gives the agent prompt and plugin commands as the CLI and the
manifests have them. The commands and flags come from the `--help` of the real CLI, the keys from the
config's own `unknown key` message, the defaults from what the config loads: no second list in the
tests to drift.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from prepush_ci.core.config import ConfigError, parse_config

README = Path(__file__).resolve().parents[2] / "README.md"

Entries = dict[str, str]


def shipped() -> str:
    return README.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return " ".join(text.split())


def section(text: str, heading: str, level: int = 2) -> str:
    """The text under the `level` heading that contains `heading`, up to the next one of that level."""
    marks = "#" * level
    parts = re.split(rf"^{marks} ", text, flags=re.MULTILINE)[1:]
    found = [p.split("\n", 1)[1] for p in parts if heading in p.split("\n", 1)[0]]
    assert len(found) == 1, f"{heading!r} matches {len(found)} sections"
    return found[0]


# --- Every command in the README exists -----------------------------------------------------


def test_the_shipped_readme_uses_only_commands_and_options_the_cli_has(
    invocations: Any,
) -> None:
    assert invocations.problems(shipped()) == []


def test_an_option_the_cli_lacks_is_reported_as_unknown_to_its_command_in_a_readme(
    invocations: Any,
) -> None:
    assert invocations.problems("Run ``prepush-ci run --fast``.") == [
        "unknown option --fast for run"
    ]


def test_a_command_the_cli_lacks_is_reported_as_unknown_in_a_readme(
    invocations: Any,
) -> None:
    assert invocations.problems("Run ``prepush-ci sync``.") == ["unknown command sync"]


# --- The reference lists every command and flag ---------------------------------------------


def command_names(invocations: Any) -> list[str]:
    """Every command of the CLI as the reference names it: `hook` by its two hooks, `app` by
    its one command."""
    groups = ("hook", "app")
    top = invocations.choices(invocations.help_of(())[1])
    names = sorted(top - set(groups))
    if invocations.top_level_lists_verify():
        names.append("verify")
    names += [
        f"{group} {command}"
        for group in groups
        for command in sorted(invocations.choices(invocations.help_of((group,))[1]))
    ]
    return names


def flags_of(invocations: Any, command: str) -> list[str]:
    """The options the `--help` of `command` lists, `-h` and `--help` apart."""
    if command == "verify":  # `verify` is not an argparse command: it takes one sha
        return []
    text = invocations.help_of(tuple(command.split()))[1]
    found = dict.fromkeys(re.findall(r"(?<![\w-])--[\w-]+", text))
    return [flag for flag in found if flag != "--help"]


def entries(text: str) -> Entries:
    """The entries of the command reference by command: the `### ` headings of the section whose
    heading says `reference`, without its backticks."""
    reference = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    body = next(
        (
            p.split("\n", 1)[1]
            for p in reference
            if "reference" in p.split("\n", 1)[0].lower()
        ),
        "",
    )
    result: Entries = {}
    for part in re.split(r"^### ", body, flags=re.MULTILINE)[1:]:
        heading, rest = part.split("\n", 1)
        name = heading.replace("`", "").strip()
        result[name] = rest
    return result


def invocation_words(invocations: Any, entry: str, command: str) -> list[list[str]]:
    """The words after `prepush-ci <command>` of each invocation of that command in `entry`."""
    words = command.split()
    found = []
    for line in invocations.code_lines(entry):
        for after in invocations.words_after_the_name(line):
            if after[: len(words)] == words:
                found.append(after[len(words) :])
    return found


def reference_problems(text: str, invocations: Any) -> list[str]:
    found: list[str] = []
    listed = entries(text)
    for command in command_names(invocations):
        entry = listed.get(command)
        if entry is None:
            found.append(f"{command} has no entry")
            continue
        if not invocation_words(invocations, entry, command):
            found.append(f"{command} has no synopsis")
            continue
        code = "\n".join(invocations.code_lines(entry))
        found.extend(
            f"{flag} is missing from {command}"
            for flag in flags_of(invocations, command)
            if not re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", code)
        )
    return found


def reference(invocations: Any, *, without: str = "", leaving_out: str = "") -> str:
    """A README text with an entry per command, each naming every flag; `without` drops the entry
    of that command, `leaving_out` drops that flag from the entries that have it."""
    parts = ["## Command reference\n"]
    for command in command_names(invocations):
        if command == without:
            continue
        flags = [f for f in flags_of(invocations, command) if f != leaving_out]
        synopsis = " ".join([f"prepush-ci {command}", *(f"[{f}]" for f in flags)])
        parts.append(f"### `{command}`\n\n```\n{synopsis}\n```\n")
    return "\n".join(parts)


def test_the_shipped_reference_is_complete(invocations: Any) -> None:
    assert reference_problems(shipped(), invocations) == []


@pytest.mark.parametrize("command", ["doctor", "skill"])
def test_a_command_left_out_of_the_reference_is_reported(
    invocations: Any, command: str
) -> None:
    text = reference(invocations, without=command)

    assert reference_problems(text, invocations) == [f"{command} has no entry"]


def test_a_flag_left_out_of_its_entry_is_reported_as_missing_from_the_command(
    invocations: Any,
) -> None:
    text = reference(invocations, leaving_out="--no-session-hook")

    assert reference_problems(text, invocations) == [
        "--no-session-hook is missing from init"
    ]


def test_a_readme_without_an_entry_for_report_is_reported(invocations: Any) -> None:
    text = reference(invocations, without="report")

    assert reference_problems(text, invocations) == ["report has no entry"]


def test_an_entry_without_a_synopsis_is_reported(invocations: Any) -> None:
    text = reference(invocations).replace("prepush-ci strip", "strip")

    assert reference_problems(text, invocations) == ["strip has no synopsis"]


def test_a_readme_without_an_entry_for_app_setup_is_reported(invocations: Any) -> None:
    text = reference(invocations, without="app setup")

    assert reference_problems(text, invocations) == ["app setup has no entry"]


def test_the_reference_lists_the_twelve_commands(invocations: Any) -> None:
    assert command_names(invocations) == [
        "doctor",
        "init",
        "install",
        "report",
        "run",
        "skill",
        "strip",
        "verify",
        "hook commit-msg",
        "hook post-push",
        "hook pre-push",
        "app setup",
    ]


# --- The exit statuses are stated ------------------------------------------------------------


def test_the_entry_of_verify_says_zero_means_verified_and_one_means_not() -> None:
    entry = flat(entries(shipped())["verify"])

    assert "0 means the commit is verified" in entry
    assert "1 means it is not" in entry


def test_the_entry_of_doctor_says_zero_means_every_check_passed() -> None:
    entry = flat(entries(shipped())["doctor"])

    assert "0 means every check passed" in entry
    assert "1 means at least one did not" in entry


def test_the_readme_of_hook_post_push_names_the_forms_recognized_and_those_not() -> (
    None
):
    entry = flat(entries(shipped())["hook post-push"])
    recognized, _, not_recognized = entry.partition("It is not recognized")

    assert not_recognized
    for form in ("`time`", "`env`", "`bash -c`", "subshell"):
        assert form in recognized
    for form in ("`eval`", "`xargs`", "`sudo`", "alias or a function defined outside"):
        assert form in not_recognized


def test_the_entry_of_init_says_it_exits_two_when_the_check_is_missing() -> None:
    entry = flat(entries(shipped())["init"])

    assert "2 means `--check` is missing and no config exists" in entry


@pytest.mark.parametrize("command", ["run", "strip"])
def test_the_entries_of_run_and_strip_say_zero_means_done_and_one_means_refused(
    command: str,
) -> None:
    entry = flat(entries(shipped())[command])

    assert "0 means it did its work" in entry
    assert "1 means it refused or failed" in entry


def test_the_entry_of_report_says_zero_means_posted_one_refused_and_two_rejected() -> (
    None
):
    entry = flat(entries(shipped())["report"])

    assert "0 means the result was posted" in entry
    assert "1 means it refused or failed" in entry
    assert "2 means the parser rejected the command line" in entry


def test_the_entry_of_app_setup_says_zero_means_created_one_refused_and_two_rejected() -> (
    None
):
    entry = flat(entries(shipped())["app setup"])

    assert "0 means the app was created and its key saved" in entry
    assert "1 means it refused or failed" in entry
    assert "2 means the parser rejected the command line" in entry


def test_the_entry_of_report_advises_running_mypy_without_pretty() -> None:
    entry = flat(entries(shipped())["report"])

    assert "without `--pretty`" in entry


def test_the_entry_of_report_says_a_failed_case_sits_on_the_line_its_failure_names() -> (
    None
):
    entry = flat(entries(shipped())["report"])

    assert "on the line its failure text names" in entry
    assert "is titled `pytest:` and the label of the case" in entry


# --- PREPUSH_CI ------------------------------------------------------------------------------


def values_of_prepush_ci() -> dict[str, str]:
    """The bullets of the `PREPUSH_CI` section by the value they open with."""
    body = section(shipped(), "PREPUSH_CI")
    bullets: dict[str, str] = {}
    for item in re.split(r"^- ", body, flags=re.MULTILINE)[1:]:
        label = re.match(r"\*\*(.+?)\*\*", item)
        assert label, item
        bullets[label.group(1)] = flat(item)
    return bullets


def test_the_readme_says_what_each_value_of_prepush_ci_does() -> None:
    values = values_of_prepush_ci()

    assert set(values) == {"`PREPUSH_CI=full`", "unset or empty", "`PREPUSH_CI=off`"}
    assert "get the trailer" in values["`PREPUSH_CI=full`"]
    unset = values["unset or empty"]
    assert "writes no trailer" in unset
    assert "still checked" in unset
    off = values["`PREPUSH_CI=off`"]
    assert "writes no trailer" in off
    assert "refused" in off


def test_the_sentence_on_off_says_a_tip_with_the_trailer_is_refused_and_names_strip() -> (
    None
):
    off = values_of_prepush_ci()["`PREPUSH_CI=off`"]

    assert "refused" in off
    assert "`prepush-ci strip`" in off


# --- The config keys and their defaults ------------------------------------------------------

ROW = re.compile(r"^\|\s*`([a-z_.]+)`\s*\|\s*(.+?)\s*\|", re.MULTILINE)


def known_keys() -> tuple[set[str], set[str]]:
    """The keys the config accepts at the top level and under `trailer`, read from its own
    `unknown key` message."""
    with pytest.raises(ConfigError) as caught:
        parse_config({"check": "true", "zz-top": 1, "trailer": {"zz-sub": 1}})
    top, sub = (
        set(re.search(r"\(known keys: ([^)]+)\)", line).group(1).split(", "))  # type: ignore[union-attr]
        for line in caught.value.problems
    )
    return top, sub


def documented(text: str) -> dict[str, str]:
    """The rows `key | default` of the key table, backticks stripped from the default."""
    return {key: default.replace("`", "") for key, default in ROW.findall(text)}


def key_problems(text: str) -> list[str]:
    top, sub = known_keys()
    keys = documented(text)
    found: list[str] = []
    for known in sorted(top - {"trailer"}) + [f"trailer.{s}" for s in sorted(sub)]:
        if known not in keys:
            found.append(f"`{known}` is missing")
    found.extend(
        f"`{key}` is unknown to the config"
        for key in keys
        if (key.split(".")[0] not in top)
        or (key.startswith("trailer.") and key.split(".", 1)[1] not in sub)
    )
    return found


def loaded_defaults() -> dict[str, str]:
    """What the config loads when only `check` is set, in the forms the README writes."""
    config = parse_config({"check": "true"})

    def canonical(value: object) -> str:
        if value is None:
            return "none"
        if value == ():
            return "[]"
        if isinstance(value, bool):
            return str(value).lower()
        if value == f"origin/{config.default_branch}":
            return "origin/<default_branch>"
        return str(value)

    return {
        "preflight": canonical(config.preflight),
        "require_env": canonical(config.require_env),
        "require_up_to_date": canonical(config.require_up_to_date),
        "default_branch": canonical(config.default_branch),
        "trailer.key": canonical(config.trailer.key),
        "trailer.value": canonical(config.trailer.value),
        "legacy_keys": canonical(config.legacy_keys),
        "cache": canonical(config.cache),
    }


def default_problems(text: str) -> list[str]:
    keys = documented(text)
    return [
        f"the default of `{key}` is `{default}`"
        for key, default in loaded_defaults().items()
        if key in keys and keys[key] != default
    ]


def key_table(*, without: str = "", extra: str = "", cache: str = "true") -> str:
    rows = {**loaded_defaults(), "check": "required", "cache": cache}
    lines = ["| key | default |", "| --- | --- |"]
    lines += [f"| `{k}` | `{v}` |" for k, v in rows.items() if k != without]
    if extra:
        lines.append(f"| `{extra}` | `5` |")
    return "\n".join(lines)


def test_the_shipped_keys_are_the_keys_the_config_accepts() -> None:
    assert key_problems(shipped()) == []


def test_a_key_left_out_of_the_table_is_reported_as_missing() -> None:
    assert key_problems(key_table(without="cache")) == ["`cache` is missing"]


def test_a_key_the_config_does_not_have_is_reported_as_unknown() -> None:
    assert key_problems(key_table(extra="timeout")) == [
        "`timeout` is unknown to the config"
    ]


def test_a_trailer_sub_key_left_out_is_reported_as_missing() -> None:
    assert key_problems(key_table(without="trailer.value")) == [
        "`trailer.value` is missing"
    ]


def test_the_shipped_defaults_are_what_the_config_loads() -> None:
    assert default_problems(shipped()) == []


def test_the_shipped_table_gives_every_default_of_the_config() -> None:
    assert set(loaded_defaults()) <= set(documented(shipped()))


def test_a_wrong_default_is_reported_with_the_one_the_config_loads() -> None:
    assert default_problems(key_table(cache="false")) == [
        "the default of `cache` is `true`"
    ]


# --- The usage steps ---------------------------------------------------------------------


def steps(text: str) -> dict[str, str]:
    """The `### ` steps of the usage section by heading."""
    body = section(text, "Usage")
    return {
        part.split("\n", 1)[0]: part.split("\n", 1)[1]
        for part in re.split(r"^### ", body, flags=re.MULTILINE)[1:]
    }


# --- The agent step ------------------------------------------------------------------------

SKILL_FILE = "skills/prepush-ci-setup/SKILL.md"


def agent_step(text: str | None = None) -> str:
    """The one `### ` step of the usage section whose heading names the agent."""
    found = [
        body
        for heading, body in steps(shipped() if text is None else text).items()
        if "agent" in heading
    ]
    assert len(found) == 1, f"{len(found)} usage steps name the agent"
    return found[0]


def agent_prompt() -> str:
    blocks = re.findall(
        r"^```[^\n]*\n(.*?)^```", agent_step(), re.MULTILINE | re.DOTALL
    )
    assert len(blocks) == 1
    return flat(blocks[0])


def test_the_agent_step_is_found_once_and_reported_not_raised_when_none_names_the_agent() -> (
    None
):
    assert agent_step()

    with pytest.raises(AssertionError, match="0 usage steps name the agent"):
        agent_step("## Usage\n\n### 1. Install\n\ntext\n")
    with pytest.raises(AssertionError, match="2 usage steps name the agent"):
        agent_step("## Usage\n\n### An agent\n\nx\n\n### Another agent\n\ny\n")


def test_the_agent_step_has_no_link_to_the_skill_on_github() -> None:
    links = re.findall(r"https://\S+", agent_step())

    assert not [link for link in links if SKILL_FILE in link]
    assert (README.parent / SKILL_FILE).is_file()


def test_the_prompts_command_exists(invocations: Any) -> None:
    prompt = agent_prompt()

    assert (
        invocations.problems(f"```\n{prompt}\n```") == []
    )  # the prompt as the code it is
    assert ["skill"] in [
        words[:1] for words in invocations.words_after_the_name(prompt)
    ]


def spans(text: str) -> list[str]:
    return re.findall(r"`([^`\n]+)`", text)


def test_the_agent_step_names_the_claude_code_plugin() -> None:
    found = spans(agent_step())

    assert "/plugin marketplace add CapeOfGoodCode/prepush-ci" in found
    assert "/plugin install prepush-ci@prepush-ci" in found


def test_the_plugin_commands_match_the_manifests() -> None:
    install = next(
        span for span in spans(agent_step()) if span.startswith("/plugin install ")
    )
    plugin, marketplace = install.removeprefix("/plugin install ").split("@")
    manifest = json.loads(
        (README.parent / ".claude-plugin" / "marketplace.json").read_text("utf-8")
    )

    assert marketplace == manifest["name"]
    assert plugin in [entry["name"] for entry in manifest["plugins"]]
