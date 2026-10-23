"""`skills/prepush-ci-setup/SKILL.md` tells the truth about the CLI and keeps its promises in order.

The checks read the file as an agent would: every `prepush-ci` invocation is held against the
`--help` of the real CLI (started as the module, so coverage measures it), and the `init`
invocation is run in a scratch repository.
"""

import json
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills" / "prepush-ci-setup" / "SKILL.md"

Git = Callable[..., "subprocess.CompletedProcess[str]"]


def shipped() -> str:
    return SKILL.read_text(encoding="utf-8")


# --- Every command in the skill exists -------------------------------------------------------


def test_the_shipped_skill_passes(invocations: Any) -> None:
    assert invocations.problems(shipped()) == []


def test_an_option_the_cli_lacks_is_reported_as_unknown_to_its_command(
    invocations: Any,
) -> None:
    assert invocations.problems("Run `prepush-ci strip --force` now.") == [
        "unknown option --force for strip"
    ]


def test_a_command_the_cli_lacks_is_reported_as_unknown(invocations: Any) -> None:
    assert invocations.problems("Run `prepush-ci sync` now.") == [
        "unknown command sync"
    ]


def test_a_nested_command_is_accepted(invocations: Any) -> None:
    assert invocations.problems("Run `prepush-ci hook pre-push`.") == []


def test_a_redirection_after_the_name_is_not_a_command(invocations: Any) -> None:
    assert invocations.problems("Run `command -v prepush-ci >/dev/null 2>&1`.") == []


def test_a_command_with_its_options_in_a_fenced_block_is_accepted(
    invocations: Any,
) -> None:
    block = "```sh\nprepush-ci init --non-interactive \\\n  --check true --hooks none\n```\n"
    assert invocations.problems(block) == []


def test_text_outside_code_is_not_an_invocation(invocations: Any) -> None:
    assert invocations.problems("prepush-ci sync is mentioned in prose.") == []


# --- The verify command is checked by its shape ----------------------------------------------


def test_verify_with_a_sha_is_accepted(invocations: Any) -> None:
    assert invocations.problems('Run `prepush-ci verify "$SHA"`.') == []


def test_verify_with_an_option_reports_the_option_as_unknown(invocations: Any) -> None:
    assert invocations.problems('Run `prepush-ci verify --strict "$SHA"`.') == [
        "unknown option --strict for verify"
    ]


def test_verify_without_a_sha_is_reported(invocations: Any) -> None:
    assert invocations.problems("Run `prepush-ci verify`.") == [
        "verify takes exactly one sha"
    ]


# --- The init invocation runs -----------------------------------------------------------------

PLACEHOLDER_VALUES = {
    "check command": "true",
    "default branch": "main",
    "hooks": "none",
}


def init_invocation(invocations: Any) -> list[str]:
    for line in invocations.code_lines(shipped()):
        for words in invocations.words_after_the_name(line):
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
    tmp_path: Path, git: Git, invocations: Any
) -> None:
    git(tmp_path, "init", "-q")
    words = filled(init_invocation(invocations))
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


# --- The default branch hint yields a branch name ---------------------------------------------

ORIGIN_PREFIX = "refs/remotes/origin/"


def default_branch_step() -> str:
    """The bullet of the init step that tells where `<default branch>` comes from."""
    for line in section("Run init").splitlines():
        if line.startswith("- `<default branch>`"):
            return flat(line)
    raise AssertionError("SKILL.md has no `<default branch>` bullet in the init step")


def hint_commands() -> list[list[str]]:
    """The git commands the `<default branch>` step gives, in order, as the words git is run with."""
    found = [
        shlex.split(span)[1:]
        for span in re.findall(r"`([^`]+)`", default_branch_step())
        if span.startswith("git ")
    ]
    assert found, "the `<default branch>` step names no git command"
    return found


def clone_of_remote(repo: Path, git: Git, branch: str) -> Path:
    """`repo` with one commit, fetched from a bare remote `origin` whose default branch is
    `branch`; `origin/HEAD` is not set, as in a repository that was not made by `git clone`."""
    (repo / "f").write_text("x")
    git(repo, "add", "f")
    git(repo, "commit", "-q", "-m", "init")
    remote = repo.parent / "remote.git"
    git(repo.parent, "init", "-q", "--bare", f"--initial-branch={branch}", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    git(repo, "fetch", "-q", "origin")
    return repo


def rename_remote_default_branch(repo: Path, git: Git, old: str, new: str) -> None:
    """The remote renames its default branch from `old` to `new`; `repo` fetches and prunes."""
    remote = repo.parent / "remote.git"
    git(repo, "push", "-q", "origin", f"HEAD:refs/heads/{new}")
    git(remote, "symbolic-ref", "HEAD", f"refs/heads/{new}")
    git(remote, "branch", "-q", "-D", old)
    git(repo, "fetch", "-q", "--prune", "origin")


def init_default_branch(
    repo: Path, branch: str, invocations: Any
) -> "subprocess.CompletedProcess[str]":
    """Run the skill's `init` invocation in `repo` with `branch` as the default branch."""
    words = [
        word.replace("<default branch>", branch)
        for word in init_invocation(invocations)
    ]
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", *filled(words)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def loaded_default_branch(repo: Path) -> str:
    import tomllib

    from prepush_ci.core.config import parse_config

    table = tomllib.loads((repo / ".prepush-ci.toml").read_text(encoding="utf-8"))
    return parse_config(table).default_branch


def follow_the_hint(repo: Path, git: Git) -> str:
    """What an agent does with the step: run its commands in order, remove the leading prefix
    from the last output."""
    output = ""
    for command in hint_commands():
        output = git(repo, *command).stdout.strip()
    assert output.startswith(ORIGIN_PREFIX), output
    return output[len(ORIGIN_PREFIX) :]


def hint_gives_the_name_init_accepts(
    repo: Path,
    git: Git,
    invocations: Any,
    origin_head: str,
    local_branch: str | None = None,
) -> None:
    clone_of_remote(repo, git, origin_head)
    if local_branch:
        git(repo, "branch", local_branch)

    result = init_default_branch(repo, follow_the_hint(repo, git), invocations)

    assert result.returncode == 0, result.stderr
    assert loaded_default_branch(repo) == origin_head


def test_a_repository_with_origin_head_gets_its_default_branch_from_the_hint(
    repo: Path, git: Git, invocations: Any
) -> None:
    hint_gives_the_name_init_accepts(repo, git, invocations, "trunk")


def test_a_default_branch_name_with_a_slash_survives_the_hint(
    repo: Path, git: Git, invocations: Any
) -> None:
    hint_gives_the_name_init_accepts(repo, git, invocations, "release/1")


def test_a_local_branch_named_like_the_remote_branch_does_not_change_the_hint(
    repo: Path, git: Git, invocations: Any
) -> None:
    hint_gives_the_name_init_accepts(
        repo, git, invocations, "trunk", local_branch="origin/trunk"
    )


def test_a_record_older_than_a_rename_is_refreshed_by_the_hint(
    repo: Path, git: Git, invocations: Any
) -> None:
    clone_of_remote(repo, git, "master")
    git(repo, "remote", "set-head", "origin", "--auto")
    rename_remote_default_branch(repo, git, "master", "main")
    stale = git(repo, "symbolic-ref", "refs/remotes/origin/HEAD").stdout.strip()

    result = init_default_branch(repo, follow_the_hint(repo, git), invocations)

    assert stale == f"{ORIGIN_PREFIX}master"
    assert result.returncode == 0, result.stderr
    assert loaded_default_branch(repo) == "main"


def test_the_default_branch_step_names_both_commands_in_order_and_says_to_remove_the_prefix() -> (
    None
):
    step = default_branch_step()
    refresh = step.index("`git remote set-head origin --auto`")
    read = step.index("`git symbolic-ref refs/remotes/origin/HEAD`")
    assert refresh < read
    assert "refreshes the local record from the remote" in step
    assert "remove the leading `refs/remotes/origin/`" in step


def test_without_a_remote_the_first_hint_command_fails(repo: Path, git: Git) -> None:
    (repo / "f").write_text("x")
    git(repo, "add", "f")
    git(repo, "commit", "-q", "-m", "init")

    first = git(repo, *hint_commands()[0], check=False)

    assert first.returncode != 0


def test_with_a_remote_that_cannot_be_reached_the_first_hint_command_fails(
    repo: Path, git: Git
) -> None:
    clone_of_remote(repo, git, "master")
    git(repo, "remote", "set-head", "origin", "--auto")
    git(repo, "remote", "set-url", "origin", str(repo.parent / "nothing"))

    first = git(repo, *hint_commands()[0], check=False)
    stale = git(repo, "symbolic-ref", "refs/remotes/origin/HEAD").stdout.strip()

    assert first.returncode != 0
    assert stale == f"{ORIGIN_PREFIX}master"


def test_in_a_single_branch_clone_the_first_hint_command_fails(
    repo: Path, git: Git
) -> None:
    clone_of_remote(repo, git, "main")
    git(repo, "push", "-q", "origin", "HEAD:refs/heads/feature")
    clone = repo.parent / "single-branch-clone"
    git(
        repo.parent,
        "clone",
        "-q",
        "--single-branch",
        "-b",
        "feature",
        str(repo.parent / "remote.git"),
        str(clone),
    )

    first = git(clone, *hint_commands()[0], check=False)

    assert first.returncode != 0


def test_the_default_branch_step_says_the_commands_fail_without_a_reachable_origin_and_to_ask() -> (
    None
):
    step = default_branch_step()
    assert "fail when `origin` does not exist, cannot be reached" in step
    assert "has no default branch" in step
    assert "(a single-branch clone of another branch)" in step
    assert "ask the user for the default branch" in step
    assert "do not guess" in step
    assert "do not use the output of the second when the first failed" in step


# --- What the README promises about the setup --------------------------------------------------


def test_the_check_is_confirmed_before_init_and_the_skill_does_not_go_on_without_it() -> (
    None
):
    assert position("Find the full check") < position("Run init")
    step = flat(section("Find the full check"))
    assert "Ask the user** to confirm the command and the list of steps" in step
    assert "Do not continue without a confirmed check" in step


def test_the_skill_works_on_a_branch_and_opens_a_pull_request() -> None:
    opening = flat(shipped().split("## 0.")[0])
    assert "Work on a branch and open a pull request with the result" in opening
    assert "do not push to the default branch" in opening


def test_the_first_step_reads_the_ci_definitions_and_finds_or_writes_one_command() -> (
    None
):
    step = flat(section("Find the full check"))
    assert "Read every CI definition" in step
    assert "write `scripts/ci`" in step
    assert "runs the steps in CI's order" in step


def test_a_missing_service_fails_the_check_and_the_tests_are_never_skipped_for_it() -> (
    None
):
    step = flat(section("Services and preflight"))
    assert "A missing service must fail the full check, never skip tests" in step
    assert "--require-env" in step and "--preflight" in step


# --- The skill has the check write its result files ----------------------------------------------

ITEM = "6. **Have the check write its result files.**"


def result_files_item() -> str:
    """Item 6 of the first step, whitespace folded: the item that has the check write the files."""
    step = section("Find the full check")
    assert ITEM in step, "the first step has no item that has the check write its files"
    return flat(step[step.index(ITEM) :])


def test_the_result_files_item_comes_after_the_confirmation_and_before_init() -> None:
    step = section("Find the full check")
    assert step.index("4. **Ask the user**") < step.index(ITEM)
    assert position("Find the full check") < position("Run init")


def test_the_result_files_item_names_the_fixed_paths_at_the_top_of_the_worktree() -> (
    None
):
    item = result_files_item()
    assert "`.prepush-ci/junit.xml`" in item
    assert "`.prepush-ci/coverage.json`" in item
    assert "at the top of the worktree" in item


def test_the_coverage_file_is_the_json_of_coverage_py_and_other_runners_get_none() -> (
    None
):
    item = result_files_item()
    assert "the JSON of coverage.py" in item
    assert (
        "a runner that cannot write it gets a JUnit file and no coverage file" in item
    )


def test_the_result_files_are_ignored_by_git_unless_they_are_already() -> None:
    item = result_files_item()
    assert "add `.prepush-ci/` to `.gitignore` unless it is ignored already" in item
    assert (
        "the pre-push hook refuses a worktree with untracked files that are not ignored"
        in item
    )


def test_no_file_written_means_gitignore_stays_as_it_is() -> None:
    item = result_files_item()
    assert "only when at least one of the files is written" in item
    assert "leave `.gitignore` as it is" in item
    assert (
        '(a "no", several test commands, an entry point, a test command that is not '
        "a runner call, a test command that runs in another directory)" in item
    )


def test_the_files_use_an_option_the_runner_has_and_never_a_new_package() -> None:
    item = result_files_item()
    assert "use an option the runner has built in" in item
    assert "never add a package or plugin to the project" in item


def test_the_console_output_loses_nothing_to_the_junit_option() -> None:
    item = result_files_item()
    assert "adds the file and takes nothing from the console output" in item
    assert "leaves the console output as it is" not in item


def test_the_junit_example_names_the_file_it_writes() -> None:
    item = result_files_item()
    assert "pytest --junitxml=.prepush-ci/junit.xml -o junit_family=xunit1" in item


def test_a_runner_that_chooses_its_reporters_from_the_environment_gets_no_junit_file() -> (
    None
):
    item = result_files_item()
    assert (
        "A `vitest`, `jest` or `node --test` check gets no JUnit file, and you tell the user "
        "that the comment will show no counts for that check" in item
    )
    assert (
        "replaces the reporters that the runner chooses itself from the environment"
        in item
    )
    assert (
        "an agent reporter under an agent, `github-actions` in GitHub Actions" in item
    )
    assert (
        "the console output of the check would change in the pre-push hook and in CI"
        in item
    )
    assert "--reporter=default" not in item
    assert "--reporters=default" not in item
    assert "--test-reporter=junit" not in item
    assert "does not create `.prepush-ci/`" in item
    assert "the run fails with exit 7 and the check turns red" in item


def test_coverage_is_written_only_where_the_check_already_measures_it() -> None:
    item = result_files_item()
    assert "only when the check already measures coverage with coverage.py" in item
    assert "never add measurement" in item
    assert (
        "a coverage threshold in the project's configuration would then start to fail the check"
        in item
    )


def test_the_coverage_table_stays_when_the_check_names_no_cov_report() -> None:
    item = result_files_item()
    assert "names `--cov` and no `--cov-report`" in item
    assert "on its command line or in the runner's configuration" in item
    assert "add `--cov-report=term` beside the JSON report" in item
    assert (
        "the JSON report alone replaces the table of uncovered lines that pytest-cov prints by default"
        in item
    )


def test_a_file_the_check_already_writes_is_left_alone() -> None:
    item = result_files_item()
    assert "already writes a JUnit file" in item
    assert "(`--junitxml` in `addopts`) or a coverage JSON file" in item
    assert "or a coverage JSON file (`--cov-report=json`)" in item
    assert "do not add yours, because the later option wins" in item
    assert (
        "tell the user that the check already writes its own file and the comment will show no counts for it"
        in item
    )


def test_several_test_commands_get_no_file_and_the_user_is_told() -> None:
    item = result_files_item()
    assert (
        "when the check runs tests with more than one command, neither file is written"
        in item
    )
    assert "the comment will show no counts for that reason" in item


def test_a_file_left_out_is_explained_and_dropped_from_the_report_call() -> None:
    item = result_files_item()
    assert "tell the user which file is left out and why" in item
    assert "leave `--junit` or `--coverage` out of the step 8 call for it" in item


def test_the_options_go_to_the_test_command_of_a_command_line_check() -> None:
    item = result_files_item()
    assert "a command line, such as a runner call or a chain of commands" in item
    assert "add the options to the test command in that line" in item


def test_the_options_go_to_the_test_line_of_a_script_written_in_this_run() -> None:
    item = result_files_item()
    assert "a `scripts/ci` you wrote in this run (item 3)" in item
    assert "add the options to the line of the script that runs the tests" in item


def test_an_entry_point_of_the_project_gets_no_file_and_no_change() -> None:
    item = result_files_item()
    assert (
        "`make ci`, `npm run ci`, `just ci`, a `tox` or `nox` session, "
        "or a script that existed before this run" in item
    )
    assert (
        "write neither file, change no file of the project, and tell the user "
        "that the entry point is the project's and the comment will show no counts"
        in item
    )


def test_a_direct_call_of_the_runner_gets_the_options() -> None:
    item = result_files_item()
    assert "a call of `pytest`: `pytest` or `uv run pytest`" in item


def test_a_test_command_that_is_an_entry_point_gets_no_file_and_no_change() -> None:
    item = result_files_item()
    for command in (
        "`ruff check . && make test`",
        "`npm run lint && npm test`",
        "`tox -e py`",
    ):
        assert command in item, command
    assert (
        "the test command is not a call of the runner and the comment will show no counts"
        in item
    )


def test_no_option_is_appended_to_an_entry_point() -> None:
    item = result_files_item()
    assert (
        "never append `--junitxml`, `--reporter`, `--outputFile`, "
        "`--test-reporter-destination`, `JEST_JUNIT_OUTPUT_FILE` or `--cov-report` "
        "to a Makefile target, a package script or a tox session" in item
    )


def test_a_cd_before_the_test_command_gets_no_file_and_no_change() -> None:
    item = result_files_item()
    assert "Only where the test command starts at the top of the worktree" in item
    assert (
        "a `cd` or `pushd` in the chain or the script, `uv run --directory`, `make -C`"
        in item
    )
    assert "`cd backend && pytest -q`" in item
    assert "a `scripts/ci` whose test line follows a `cd`" in item
    assert (
        "write neither file, change no file of the project, and tell the user "
        "that the test command runs in another directory and the comment will show no counts"
        in item
    )


def test_a_cd_that_ended_before_the_test_command_does_not_count() -> None:
    item = result_files_item()
    assert "`(cd web && npm run build) && pytest -q`" in item
    assert "the directory in which the test command starts" in item
    assert "the options go to `pytest` here" in item


def test_the_user_is_shown_the_change_and_asked_before_it_is_made() -> None:
    item = result_files_item()
    assert "show the user the change" in item
    assert "ask for a yes before you make it" in item
    assert "leave the check as it is without the yes" in item


def test_the_change_never_touches_what_the_check_checks() -> None:
    item = result_files_item()
    assert (
        "the change only adds the files and never changes the steps, the selection of tests "
        "or the thresholds of the check" in item
    )


def test_init_gets_the_changed_command_line_after_a_yes() -> None:
    step = flat(section("Run init"))
    assert (
        "after a yes, `<check command>` is the confirmed command line with the added options"
        in step
    )


def test_init_gets_the_script_unchanged_when_the_script_holds_the_options() -> None:
    step = flat(section("Run init"))
    assert "`scripts/ci`, unchanged, when the options are in the script" in step


def test_a_no_leaves_the_check_and_the_report_call_as_they_are() -> None:
    step = flat(section("Run init"))
    assert "without a yes `<check command>` is the confirmed check unchanged" in step
    item = result_files_item()
    assert "Without the yes the files count as not written" in item
    assert "the step 8 call has neither `--junit` nor `--coverage`" in item


# --- The documentation section has every session show its result on the pull request ----------

TOP = '"$(git rev-parse --show-toplevel)/'
JUNIT_PATH = TOP + '.prepush-ci/junit.xml"'
COVERAGE_PATH = TOP + '.prepush-ci/coverage.json"'
REPORT_COMMAND = (
    "`prepush-ci report --markdown --result passed "
    "--tree \"$(git rev-parse 'HEAD^{tree}')\"`"
)


def test_the_documentation_section_has_the_command_that_prints_the_result_after_a_push() -> (
    None
):
    step = flat(section("Documentation"))
    assert "after a push" in step.lower()
    assert "trailer" in step
    assert REPORT_COMMAND in step


def test_the_documentation_section_says_to_post_nothing_without_a_pull_request() -> (
    None
):
    step = flat(section("Documentation"))
    assert "has no pull request" in step
    assert "post nothing" in step


def test_the_markdown_invocation_of_the_documentation_section_exists(
    invocations: Any,
) -> None:
    assert invocations.problems(REPORT_COMMAND) == []
    assert REPORT_COMMAND in section("Documentation")


def test_the_documentation_section_updates_the_comment_that_holds_the_marker() -> None:
    step = flat(section("Documentation"))
    assert "`<!-- prepush-ci:`" in step
    assert "update it" in step
    assert "create a comment only when none holds the marker" in step


def test_the_documentation_section_bans_edit_last_and_says_why() -> None:
    step = flat(section("Documentation"))
    assert "`--edit-last`" in step
    assert "whatever it says" in step


def test_the_documentation_section_passes_the_result_files_each_only_if_written() -> (
    None
):
    step = flat(section("Documentation"))
    assert f"`--junit {JUNIT_PATH}`" in step
    assert f"`--coverage {COVERAGE_PATH}`" in step
    assert "for each of those files the check writes" in step


def test_the_paths_of_the_documentation_section_do_not_depend_on_the_directory_of_the_call() -> (
    None
):
    step = flat(section("Documentation"))
    assert JUNIT_PATH.startswith(TOP) and COVERAGE_PATH.startswith(TOP)
    assert step.count(TOP) == 2
    assert "`--junit .prepush-ci" not in step
    assert "`--coverage .prepush-ci" not in step
    assert "from a subdirectory" in step


def test_the_documentation_section_leaves_the_files_out_after_a_cached_pass() -> None:
    step = flat(section("Documentation"))
    assert (
        "Leave out the result files when the push said the check passed earlier, "
        "because the files on disk may belong to another tree" in step
    )


def test_the_documentation_section_says_the_hook_and_the_call_share_the_comment() -> (
    None
):
    step = flat(section("Documentation"))
    assert (
        "The post-push hook, where the repository has it, writes the short comment "
        "right after the push and your call then updates that comment" in step
    )


# --- The hook that shows the result after every push is proposed, never imposed -----------------

HOOK_COMMAND = (
    'd=$(uv tool dir --bin 2>/dev/null) && [ -n "$d" ] && PATH="$d:$PATH"; '
    "command -v prepush-ci >/dev/null 2>&1 && prepush-ci hook post-push || true"
)


def hook_group() -> dict[str, Any]:
    """The group the step shows for `hooks.PostToolUse`, from its JSON block."""
    block = re.search(r"```json\n(.*?)```", section("Show the result"), re.DOTALL)
    assert block is not None
    settings = json.loads(block.group(1))
    (group,) = settings["hooks"]["PostToolUse"]
    assert isinstance(group, dict)
    return group


def test_the_hook_step_follows_the_documentation_step() -> None:
    assert position("Show the result") == position("Documentation") + 1


def test_the_hook_step_says_what_the_hook_does_and_asks_for_a_yes() -> None:
    step = flat(section("Show the result"))
    assert "after every successful `git push`" in step
    assert "ask the user for a yes" in step
    assert "`.claude/settings.json`" in step


def test_the_hook_step_changes_no_file_without_the_yes() -> None:
    step = flat(section("Show the result"))
    assert "Without a yes, change no file" in step


def test_the_rule_of_the_documentation_step_stays_as_the_fallback() -> None:
    assert REPORT_COMMAND in section("Documentation")
    step = flat(section("Show the result"))
    assert "stays for agents without hooks" in step


def test_the_hook_step_shows_the_group_for_post_tool_use() -> None:
    group = hook_group()
    assert group["matcher"] == "Bash"
    assert group["hooks"] == [
        {"type": "command", "command": HOOK_COMMAND, "timeout": 30}
    ]


def test_the_hook_step_keeps_every_other_setting_and_adds_nothing_twice() -> None:
    step = flat(section("Show the result"))
    assert "keep every other setting" in step
    assert "add nothing when a command there already runs `hook post-push`" in step


def test_the_invocation_of_the_hook_step_exists(invocations: Any) -> None:
    step = section("Show the result")
    assert f"`{HOOK_COMMAND}`" in step
    assert invocations.problems(step) == []


def test_the_hook_step_says_that_uv_tool_install_turns_the_hook_on() -> None:
    step = flat(section("Show the result"))
    assert "`uv tool install prepush-ci`" in step
    assert "does nothing until" in step


# --- The command of the hook is silent where the tool is not installed ------------------------

POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the command of the hook is run by /bin/sh, and its stubs are sh scripts",
)
PUSH_PAYLOAD = '{"tool_input": {"command": "git push"}}'


def stub(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def run_hook_command(
    tmp_path: Path, *, uv: str | None, tool_dir: Path | None = None
) -> "subprocess.CompletedProcess[str]":
    """The command of the skill's group through `sh -c`, with a `PATH` of the stubs alone.

    `uv` is the body of a `uv` stub (none: there is no `uv`); `tool_dir` is the directory
    `uv tool dir --bin` prints. The working directory holds a `prepush-ci` that a clone could plant.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if uv is not None:
        stub(bin_dir / "uv", uv.replace("TOOL_DIR", str(tool_dir or "")))
    work = tmp_path / "work"
    stub(work / "prepush-ci", "echo PLANTED RAN; exit 9")
    return subprocess.run(
        ["/bin/sh", "-c", hook_group()["hooks"][0]["command"]],
        cwd=work,
        env={"PATH": str(bin_dir)},
        input=PUSH_PAYLOAD,
        capture_output=True,
        text=True,
        check=False,
    )


@POSIX_ONLY
def test_the_tool_is_not_installed_and_the_command_exits_0_and_prints_nothing(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "tools"
    empty.mkdir()
    result = run_hook_command(tmp_path, uv='echo "TOOL_DIR"', tool_dir=empty)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


@POSIX_ONLY
def test_the_tool_is_installed_and_the_command_runs_it_and_exits_0_whatever_its_status(
    tmp_path: Path,
) -> None:
    tools = tmp_path / "tools"
    stub(
        tools / "prepush-ci",
        'echo "TOOL RAN $*"; read -r payload; echo "$payload"; exit 5',
    )
    result = run_hook_command(tmp_path, uv='echo "TOOL_DIR"', tool_dir=tools)
    assert result.returncode == 0
    assert result.stdout == f"TOOL RAN hook post-push\n{PUSH_PAYLOAD}\n"


@POSIX_ONLY
def test_uv_is_not_installed_and_the_command_exits_0_and_does_not_run_the_planted_file(
    tmp_path: Path,
) -> None:
    result = run_hook_command(tmp_path, uv=None)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


@POSIX_ONLY
def test_uv_prints_no_directory_and_the_command_does_not_run_the_planted_file(
    tmp_path: Path,
) -> None:
    result = run_hook_command(tmp_path, uv="exit 0")
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


@POSIX_ONLY
def test_uv_fails_and_the_command_does_not_run_the_planted_file(
    tmp_path: Path,
) -> None:
    result = run_hook_command(tmp_path, uv='echo "an error" >&2; exit 1')
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
