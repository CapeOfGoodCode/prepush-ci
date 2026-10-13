"""`skills/prepush-ci-setup/SKILL.md` tells the truth about the CLI and keeps its promises in order.

The checks read the file as an agent would: every `prepush-ci` invocation is held against the
`--help` of the real CLI (started as the module, so coverage measures it), and the `init`
invocation is run in a scratch repository.
"""

import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "prepush-ci-setup" / "SKILL.md"

Git = Callable[..., "subprocess.CompletedProcess[str]"]

NAME = re.compile(r"(?<![\w/.@-])prepush-ci(?![\w/.@:-])")
OPERATORS = {"|", "||", "&&", ";", "&", ">", ">>", "<", ")"}


def cli(*args: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", *args],
        capture_output=True,
        text=True,
        check=False,
    )


@cache
def help_of(words: tuple[str, ...]) -> tuple[int, str]:
    """Exit status and text of `prepush-ci <words> --help`."""
    result = cli(*words, "--help")
    return result.returncode, result.stdout


def choices(help_text: str) -> set[str]:
    """The sub-command names an argparse help lists as `{a,b}`."""
    found = re.search(r"\{([\w,-]+)\}", help_text)
    return set(found.group(1).split(",")) if found else set()


def top_level_lists_verify() -> bool:
    return re.search(r"^also: verify\b", help_of(())[1], re.MULTILINE) is not None


def code_lines(text: str) -> list[str]:
    """The lines of fenced code blocks (continuations joined) and the inline code spans."""
    lines: list[str] = []
    fenced = False
    pending = ""
    for raw in text.splitlines():
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            pending += raw.strip()
            if pending.endswith("\\"):
                pending = pending[:-1] + " "
                continue
            lines.append(pending)
            pending = ""
        else:
            lines.extend(re.findall(r"`([^`\n]+)`", raw))
    return lines


def words_after_the_name(line: str) -> list[list[str]]:
    """For each `prepush-ci` in `line`, the words that follow up to a shell operator."""
    found: list[list[str]] = []
    for match in NAME.finditer(line):
        rest = line[match.end() :]
        try:
            words = shlex.split(rest)
        except ValueError:
            words = rest.split()
        taken: list[str] = []
        for word in words:
            if word in OPERATORS:
                break
            taken.append(word)
        found.append(taken)
    return found


def problems(text: str) -> list[str]:
    """What is wrong with the `prepush-ci` invocations of `text`, in order; empty when none."""
    found: list[str] = []
    for line in code_lines(text):
        for words in words_after_the_name(line):
            found.extend(check_invocation(words))
    return found


def check_invocation(words: list[str]) -> list[str]:
    command: list[str] = []
    rest = list(words)
    while rest and not rest[0].startswith("-"):
        listed = choices(help_of(tuple(command))[1])
        if not command and rest[0] == "verify" and top_level_lists_verify():
            return check_verify(rest[1:])
        if rest[0] not in listed:
            break
        command.append(rest.pop(0))
    if not command and rest and not rest[0].startswith("-"):
        return [f"unknown command {rest[0]}"]
    status, text = help_of(tuple(command))
    if status != 0:
        return [f"unknown command {' '.join(command)}"]
    if choices(text) and not rest:
        return []
    unknown: list[str] = []
    for word in rest:
        option = word.split("=", 1)[0]
        if option.startswith("-") and not re.search(
            rf"(?<![\w-]){re.escape(option)}(?![\w-])", text
        ):
            unknown.append(
                f"unknown option {option} for {' '.join(command) or 'prepush-ci'}"
            )
    return unknown


def check_verify(rest: list[str]) -> list[str]:
    options = [
        f"unknown option {word} for verify" for word in rest if word.startswith("-")
    ]
    arguments = [word for word in rest if not word.startswith("-")]
    if len(arguments) != 1:
        options.append("verify takes exactly one sha")
    return options


def shipped() -> str:
    return SKILL.read_text(encoding="utf-8")


# --- Every command in the skill exists -------------------------------------------------------


def test_the_shipped_skill_passes() -> None:
    assert problems(shipped()) == []


def test_an_option_the_cli_lacks_is_reported_as_unknown_to_its_command() -> None:
    assert problems("Run `prepush-ci strip --force` now.") == [
        "unknown option --force for strip"
    ]


def test_a_command_the_cli_lacks_is_reported_as_unknown() -> None:
    assert problems("Run `prepush-ci sync` now.") == ["unknown command sync"]


def test_a_nested_command_is_accepted() -> None:
    assert problems("Run `prepush-ci hook pre-push`.") == []


def test_a_command_with_its_options_in_a_fenced_block_is_accepted() -> None:
    block = "```sh\nprepush-ci init --non-interactive \\\n  --check true --hooks none\n```\n"
    assert problems(block) == []


def test_text_outside_code_is_not_an_invocation() -> None:
    assert problems("prepush-ci sync is mentioned in prose.") == []


# --- The verify command is checked by its shape ----------------------------------------------


def test_verify_with_a_sha_is_accepted() -> None:
    assert problems('Run `prepush-ci verify "$SHA"`.') == []


def test_verify_with_an_option_reports_the_option_as_unknown() -> None:
    assert problems('Run `prepush-ci verify --strict "$SHA"`.') == [
        "unknown option --strict for verify"
    ]


def test_verify_without_a_sha_is_reported() -> None:
    assert problems("Run `prepush-ci verify`.") == ["verify takes exactly one sha"]


# --- The init invocation runs -----------------------------------------------------------------

PLACEHOLDER_VALUES = {
    "check command": "true",
    "default branch": "main",
    "hooks": "none",
}


def init_invocation() -> list[str]:
    for line in code_lines(shipped()):
        for words in words_after_the_name(line):
            if words[:2] == ["init", "--non-interactive"]:
                return words
    raise AssertionError(
        "SKILL.md has no `prepush-ci init --non-interactive` invocation"
    )


def filled(words: list[str]) -> list[str]:
    def fill(word: str) -> str:
        return re.sub(
            r"<([^<>]+)>",
            lambda m: PLACEHOLDER_VALUES[m.group(1)],
            word,
        )

    return [fill(word) for word in words]


def test_the_init_invocation_works_with_its_placeholders_filled(
    tmp_path: Path, git: Git
) -> None:
    git(tmp_path, "init", "-q")
    words = filled(init_invocation())
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", *words],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".prepush-ci.toml").is_file()


# --- What the skill says, in order ------------------------------------------------------------


def sections() -> dict[str, str]:
    """The `## ` sections of the skill, by heading."""
    parts = re.split(r"^## ", shipped(), flags=re.MULTILINE)[1:]
    return {part.split("\n", 1)[0]: part.split("\n", 1)[1] for part in parts}


def section(keyword: str) -> str:
    """The text of the one section whose heading contains `keyword`."""
    found = [text for heading, text in sections().items() if keyword in heading]
    assert len(found) == 1, f"{keyword!r} matches {len(found)} sections"
    return found[0]


def position(keyword: str) -> int:
    return [i for i, heading in enumerate(sections()) if keyword in heading][0]


def answer(label: str) -> str:
    """The bullet of the question step that starts with the bold `label`, nested bullets included."""
    lines = section("Ask").splitlines()
    start = next(i for i, text in enumerate(lines) if text.startswith(f"- **{label}"))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("- **")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_session_script_step_says_init_wrote_the_script_and_names_what_to_add() -> (
    None
):
    step = flat(section("SessionStart"))
    assert "`init` wrote `.claude/hooks/session-start.sh`" in step
    assert all(word in step for word in ("dependencies", "services"))
    assert "settings.json" not in step
    assert "create" not in step.lower()


def test_the_session_script_step_names_the_activation_of_a_manager() -> None:
    step = section("SessionStart")
    assert "`pre-commit install`" in step
    assert "`lefthook install`" in step


def test_the_session_script_step_has_no_uvx_and_no_pipx_run() -> None:
    step = section("SessionStart")
    assert "uvx" not in step
    assert "pipx run" not in step


def test_the_existing_hooks_are_looked_at_before_init_and_each_place_is_named() -> None:
    assert position("existing hooks") < position("Run init")
    step = section("existing hooks")
    for place in (
        "core.hooksPath",
        "`commit-msg`",
        "`pre-push`",
        ".pre-commit-config.yaml",
        ".husky/",
        "lefthook.yml",
    ):
        assert place in step, place


def test_two_managers_make_the_skill_ask_which_to_use_and_pass_it_as_hooks() -> None:
    step = flat(section("existing hooks"))
    assert "more than one" in step
    assert "ask the user which" in step
    assert "`--hooks`" in step


def test_the_question_comes_before_init_and_lists_the_three_answers() -> None:
    assert position("Ask") < position("Run init")
    step = flat(section("Ask"))
    assert "keep the existing hooks" in step
    assert "only in cloud sessions" in step
    assert "fold the existing pre-push steps into the full check" in step


def test_the_question_step_says_to_wait_for_the_answer_before_installing_hooks() -> (
    None
):
    step = flat(section("Ask")).lower()
    assert "wait for the answer before" in step
    assert "installs hooks" in step


def test_the_first_answer_for_native_hooks_leaves_the_hook_files_alone() -> None:
    first = flat(answer("Keep"))
    assert "run `init`" in first
    assert "leave the existing hook files as they are" in first


def test_the_first_answer_for_pre_commit_names_the_block_and_both_keys_and_commits_them() -> (
    None
):
    first = flat(answer("Keep"))
    assert ".pre-commit-config.yaml" in first
    assert "`default_install_hook_types`" in first
    assert "`default_stages`" in first
    assert "committed" in first


def test_the_first_answer_for_husky_or_lefthook_names_the_block_and_commits_it() -> (
    None
):
    # Only this sub-bullet: the pre-commit one next to it also says "committed" and "the block".
    bullet = next(
        flat(line)
        for line in answer("Keep").splitlines()
        if line.lstrip().startswith("- husky or lefthook")
    )
    assert "`.husky/`" in bullet
    assert "`lefthook.yml`" in bullet
    assert "the block `init` writes" in bullet
    assert "#!/usr/bin/env sh" in bullet
    assert "Commit the block together with `.prepush-ci.toml`" in bullet


def test_the_second_answer_is_init_with_hooks_none_when_no_manager_is_in_use() -> None:
    second = flat(answer("Cloud"))
    assert "`--hooks none`" in second
    assert "no hook manager" in second


def test_with_a_manager_only_the_first_and_the_third_answer_are_offered_and_why() -> (
    None
):
    step = flat(section("Ask"))
    assert "only the first and the third answer" in step
    assert "modify the tracked config" in step
    assert "dirty" in step
    assert "every developer" in step


def test_removing_a_hook_needs_the_file_shown_its_steps_moved_and_a_yes_by_name() -> (
    None
):
    third = flat(answer("Fold"))
    assert "show the user the hook file" in third.lower()
    assert "move its steps into the check command first" in third
    assert "confirms it by name" in third


def test_the_skill_never_names_a_gate_action_that_does_not_exist() -> None:
    assert "prepush-ci/gate" not in shipped()


def test_every_action_reference_has_the_owner_that_ships_it() -> None:
    owners = re.findall(r"([\w.-]+)/prepush-ci@", shipped())
    assert owners
    assert set(owners) == {"CapeOfGoodCode"}


def test_the_gate_step_names_where_its_snippet_comes_from() -> None:
    step = section("CI gate")
    assert "docs/ci/" in step or "init --ci" in step


def test_the_gate_step_says_forks_and_the_default_branch_never_skip() -> None:
    step = flat(section("CI gate")).lower()
    assert "pull requests from forks never skip" in step
    assert "the default branch never skips" in step


def test_the_proof_step_runs_doctor_with_the_mode_after_sourcing_the_variables() -> (
    None
):
    step = section("Prove")
    assert "doctor --mode full" in step
    assert step.index("source") < step.index("doctor --mode full")
