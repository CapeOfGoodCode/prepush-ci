import os
import re
import shlex
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]


@pytest.fixture
def git() -> Git:
    """Run real git in a directory; a failing command fails the test unless `check=False`.

    `PREPUSH_CI` and `PRE_COMMIT_*` are dropped from the inherited environment so a developer's
    own opt-in, or the pre-commit run that started the suite as a pre-push hook, never leaks
    into a spec; pass them through `env` when a spec needs them.
    """

    def run(
        repo: Path,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> "subprocess.CompletedProcess[str]":
        inherited = {
            k: v
            for k, v in os.environ.items()
            if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
        }
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=check,
            env={**inherited, **(env or {})},
        )

    return run


@pytest.fixture
def repo(tmp_path: Path, git: Git) -> Path:
    """An empty git repository with an identity, in a temporary directory."""
    path = tmp_path / "work"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "commit.gpgsign", "false")
    return path


@pytest.fixture
def hooked_repo(repo: Path) -> Path:
    """`repo` with a valid config and the commit-msg hook installed the way git runs it."""
    (repo / ".prepush-ci.toml").write_text('check = "true"\n')
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook commit-msg "$1"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    return repo


@pytest.fixture
def pushing_repo(repo: Path, tmp_path: Path, git: Git) -> Path:
    """`repo` on `main` with one commit, a config whose check logs to `ran.log`, a bare `origin`
    and the pre-push hook installed the way git runs it."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    ran = tmp_path / "ran.log"
    (repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()}"\nrequire_up_to_date = false\n'
    )
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return repo


# --- The invocation checker the skill and the README specs share ---------------------------
# It holds every `prepush-ci` invocation of a text against the `--help` of the real CLI (started as
# the module, so coverage measures it). pytest imports specs by file (importlib mode), so the
# specs get it as a fixture.

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


@dataclass(frozen=True)
class Invocations:
    problems: Callable[[str], list[str]]
    code_lines: Callable[[str], list[str]]
    words_after_the_name: Callable[[str], list[list[str]]]
    help_of: Callable[[tuple[str, ...]], tuple[int, str]]
    choices: Callable[[str], set[str]]
    top_level_lists_verify: Callable[[], bool]


@pytest.fixture(scope="session")
def invocations() -> Invocations:
    """The check that every `prepush-ci` invocation of a text names a command and options the CLI has."""
    return Invocations(
        problems=problems,
        code_lines=code_lines,
        words_after_the_name=words_after_the_name,
        help_of=help_of,
        choices=choices,
        top_level_lists_verify=top_level_lists_verify,
    )
