"""Decisions of `hook post-push`: what a `PostToolUse` payload says, whether a command pushes, and
which comment is the check's."""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from prepush_ci.core.run_cache import RESULTS

TOOL = "Bash"
_NOT_A_PUSH = ("--dry-run", "-n", "--delete", "-d")
_SEPARATORS = ";&|()`\n\r"
_KEYWORDS = frozenset(("!", "{", "if", "elif", "while", "until", "then", "else", "do"))
_WRAPPERS = frozenset(("time", "command", "exec", "nohup", "env", "timeout"))
_VALUE_OPTIONS = {"env": ("-u", "-C"), "timeout": ("-k", "-s")}
_SHELLS = ("sh", "bash", "zsh")
_ESCAPED_IN_DOUBLE_QUOTES = '"\\$`\n'


@dataclass(frozen=True)
class Payload:
    """The command the agent ran and the directory it ran in (None: the hook's own)."""

    command: str
    cwd: str | None


def parse_payload(text: str) -> Payload | None:
    """The payload of a `Bash` tool call, or None for anything else: not JSON, not an object,
    another tool, or a command that is not a string."""
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("tool_name") != TOOL:
        return None
    tool_input = data.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return None
    cwd = data.get("cwd")
    return Payload(command, cwd if isinstance(cwd, str) and cwd else None)


def _commands(line: str) -> list[list[str]] | None:
    """The commands of a command line as lists of words, read like a shell reads them: a separator
    ends a command, a quoted word stays whole (a quote may span lines). None when a quote is never
    closed."""
    commands: list[list[str]] = []
    words: list[str] = []
    word: list[str] = []
    in_word = False
    quote = ""
    chars = iter(line)
    for char in chars:
        if quote == "'":
            if char == "'":
                quote = ""
            else:
                word.append(char)
        elif quote == '"':
            if char == '"':
                quote = ""
            elif char == "\\":
                following = next(chars, "")
                word.append(
                    following
                    if following in _ESCAPED_IN_DOUBLE_QUOTES
                    else char + following
                )
            else:
                word.append(char)
        elif char in "'\"":
            quote = char
            in_word = True
        elif char == "\\":
            word.append(next(chars, ""))
            in_word = True
        elif char in _SEPARATORS or char in " \t":
            if in_word:
                words.append("".join(word))
                word, in_word = [], False
            if char in _SEPARATORS and words:
                commands.append(words)
                words = []
        else:
            word.append(char)
            in_word = True
    if quote:
        return None
    if in_word:
        words.append("".join(word))
    if words:
        commands.append(words)
    return commands


def _is_assignment(word: str) -> bool:
    name, separator, _value = word.partition("=")
    return bool(separator) and name.isidentifier()


def _after_wrapper(name: str, words: list[str], start: int) -> int:
    """The index of what follows a wrapper once its options are skipped: the value of `env -u` and
    `timeout -k` with them, and the duration `timeout` takes."""
    values = _VALUE_OPTIONS.get(name, ())
    index = start
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in values else 1
    if name == "timeout":
        index += 1
    return min(index, len(words))


def _is_c_option(word: str) -> bool:
    """Whether `word` is a shell option word that holds `c`: `-c`, `-lc`, `-ec`."""
    letters = word[1:]
    return (
        word[:1] == "-" and "c" in letters and letters.isascii() and letters.isalpha()
    )


def _script_of(args: list[str]) -> str | None:
    """The script of `sh -c`: the word after the first option that holds `c`, when every option
    before it starts with `-`."""
    for index, word in enumerate(args):
        if _is_c_option(word):
            return args[index + 1] if index + 1 < len(args) else None
        if not word.startswith("-"):
            return None
    return None


def _is_git_push(words: list[str], start: int) -> bool:
    """Whether the command that starts at `start` is `git [options] push` that sends something."""
    if words[start : start + 1] != ["git"]:
        return False
    index = start + 1
    while index < len(words) and (
        words[index] in ("-C", "-c") or words[index].startswith("--")
    ):
        index += 2 if words[index] in ("-C", "-c") else 1
    if words[index : index + 1] != ["push"]:
        return False
    return not any(word in _NOT_A_PUSH for word in words[index + 1 :])


def _pushes(words: list[str]) -> bool:
    """Whether one command is a push, once the words that run another command are skipped."""
    start = 0
    while start < len(words) and (
        _is_assignment(words[start])
        or words[start] in _KEYWORDS
        or words[start] in _WRAPPERS
    ):
        name = words[start]
        start += 1
        if name in _WRAPPERS:
            start = _after_wrapper(name, words, start)
    if words[start : start + 1] and words[start] in _SHELLS:
        script = _script_of(words[start + 1 :])
        return script is not None and is_push(script)
    return _is_git_push(words, start)


def is_push(command: str) -> bool:
    """Whether some command of the line is a `git push` that sends commits: not a dry run, not a
    deletion, and not a line whose quotes cannot be read."""
    commands = _commands(command)
    return commands is not None and any(_pushes(words) for words in commands)


def marker_of(body: str) -> str:
    """The first line of a comment's body, which names the check."""
    return body.split("\n", 1)[0]


def find_comment(
    comments: Sequence[tuple[int, str]], marker: str
) -> tuple[int, str] | None:
    """The first comment (id, body) whose body starts with the marker."""
    for comment in comments:
        if comment[1].startswith(marker):
            return comment
    return None


def results_pattern(tree: str) -> str:
    """The pattern of the result refs of a tree, whatever the config part of the key is."""
    return f"{RESULTS}/{tree}-*"
