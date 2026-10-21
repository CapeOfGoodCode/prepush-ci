"""What `prepush-ci install` writes into the files of a hook manager: one marked block per place,
edited as lines so that every other line of the file stays as it was."""

import re
from collections.abc import Sequence

BEGIN = "# prepush-ci: begin"
END = "# prepush-ci: end"


class Refusal(Exception):
    """A file this tool cannot edit safely; the message says what to fix, nothing was changed."""


def split_lines(text: str) -> tuple[list[str], str]:
    """The lines of `text` without their line ends, and the line end the file uses."""
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    if lines[-1] == "":  # the final line end is not a line
        lines.pop()
    return lines, eol


def join_lines(lines: Sequence[str], eol: str) -> str:
    """The text of `lines`, every line ended."""
    return "".join(line + eol for line in lines)


def find_block(lines: Sequence[str], needle: str = "") -> tuple[int, int] | None:
    """The indexes of the begin and end lines of the first block whose body contains `needle`."""
    start = 0
    while start < len(lines):
        if lines[start].strip() != BEGIN:
            start += 1
            continue
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].strip() == END), None
        )
        if end is None:
            raise Refusal(f"it has `{BEGIN}` without a matching `{END}`")
        if needle in "\n".join(lines[start + 1 : end]):
            return start, end
        start = end + 1
    return None


def place_block(
    lines: Sequence[str], block: Sequence[str], at: int, needle: str = ""
) -> list[str]:
    """`lines` with `block` (begin and end lines included) replacing the block that holds
    `needle`, or inserted before line `at` when there is none."""
    span = find_block(lines, needle)
    if span is None:
        span = (at, at - 1)
    return [*lines[: span[0]], *block, *lines[span[1] + 1 :]]


# What an entry does when the tool is not on PATH (spec `install`): `commit-msg` warns and lets
# the commit go on, `pre-push` refuses, as the native hooks do. The entries are the only code
# that runs then, so the guard is written into each of them (`command -v` is POSIX sh).
_NOT_FOUND = "prepush-ci is not on PATH, so"
_WARNING = f"{_NOT_FOUND} no trailer is written - install it"
_REFUSAL = f"{_NOT_FOUND} this push cannot be checked - install it"
_FOUND = "if command -v prepush-ci >/dev/null 2>&1; then"

PRE_COMMIT_FILE = ".pre-commit-config.yaml"
_TYPES_KEY = "default_install_hook_types"
_STAGES_KEY = "default_stages"
_WANTED_TYPES = ("commit-msg", "pre-push")
_BLOCK_ITEM = re.compile(r"\s*-\s+(\S+)\s*(#.*)?")
_FLOW_TYPES = re.compile(rf"{_TYPES_KEY}:\s*\[([^\]]*)\]\s*(#.*)?")


def _find(lines: Sequence[str], key: str) -> int | None:
    """The index of the line of a top-level `key`, if any."""
    return next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)


def _blank_or_comment(text: str) -> bool:
    stripped = text.strip()
    return not stripped or stripped.startswith("#")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _bare(items: Sequence[str]) -> list[str]:
    return [item.strip("'\"") for item in items]


def _pre_commit_entry(hook: str) -> str:
    """The `entry:` of `hook`: `sh -c` with the guard; pre-commit appends the message file, which
    `sh` hands to the script as `$1`."""
    if hook == "commit-msg":
        script = f'{_FOUND} exec prepush-ci hook commit-msg "$1"; else echo "{_WARNING}" >&2; fi'
    else:
        script = f'{_FOUND} exec prepush-ci hook pre-push; else echo "{_REFUSAL}" >&2; exit 1; fi'
    return f"sh -c '{script}' prepush-ci"


def pre_commit_block(indent: str) -> list[str]:
    """The `local` repo with the two hooks, its list item at `indent`."""
    lines = [BEGIN, "- repo: local", "  hooks:"]
    for hook, extra in (
        # pre-commit hides the output of a hook that passes, and with it what the hook says
        ("commit-msg", ["stages: [commit-msg]", "verbose: true"]),
        (
            "pre-push",
            [
                "stages: [pre-push]",
                "pass_filenames: false",
                "always_run: true",
                "verbose: true",
            ],
        ),
    ):
        lines += [
            f"    - id: prepush-ci-{hook}",
            f"      name: prepush-ci {hook}",
            f"      entry: {_pre_commit_entry(hook)}",
            "      language: system",
            *(f"      {line}" for line in extra),
        ]
    return [f"{indent}{line}" for line in [*lines, END]]


_EMPTY_REPOS = re.compile(r"repos:\s*\[\s*\]\s*(?:(#.*))?")
_EMPTY_REPOS_INDENT = 2


def _repo_entries(lines: Sequence[str], repos: int) -> tuple[int, int]:
    """The indent of the entries under the `repos:` line and the index of the last line of them."""
    indent, last = None, repos
    for i in range(repos + 1, len(lines)):
        line = lines[i]
        if _blank_or_comment(line):
            continue
        if _indent(line) == 0 and not line.startswith("-"):
            break  # the next top-level key
        if indent is None:
            if not line.lstrip().startswith("-"):
                raise Refusal("`repos` must be a block list of `- repo:` entries")
            indent = _indent(line)
        last = i
    if indent is None:
        raise Refusal("`repos` has no entries: add a `- repo:` or remove the key")
    return indent, last


def edit_pre_commit(text: str) -> str:
    """The `.pre-commit-config.yaml` with the block at the end of `repos:` and both hook types
    installed, the hooks it already had kept at the stages they ran at."""
    lines, eol = split_lines(text)
    repos = _find(lines, "repos")
    empty = None if repos is None else _EMPTY_REPOS.fullmatch(lines[repos])
    if repos is not None and empty is not None:
        # An empty flow list has no entries to move: it becomes a block list for the block.
        lines[repos] = f"repos: {empty[1]}" if empty[1] else "repos:"
        indent, last = _EMPTY_REPOS_INDENT, repos
    elif repos is None or not _blank_or_comment(lines[repos][len("repos:") :]):
        raise Refusal("`repos` must be a block list: `repos:` and `- repo:` entries")
    else:
        indent, last = _repo_entries(lines, repos)
    lines = place_block(lines, pre_commit_block(" " * indent), last + 1)
    before = _with_hook_types(lines)
    if before is not None and _find(lines, _STAGES_KEY) is None:
        repos = _find(lines, "repos")
        assert repos is not None  # still there: only lines above and below it changed
        lines.insert(repos, f"{_STAGES_KEY}: [{', '.join(before)}]")
    return join_lines(lines, eol)


def _with_hook_types(lines: list[str]) -> list[str] | None:
    """Make `default_install_hook_types` in `lines` hold `commit-msg` and `pre-push`. The types
    it held before when any was added, else None."""
    key = _find(lines, _TYPES_KEY)
    if key is None:
        repos = _find(lines, "repos")
        assert repos is not None  # the caller found it
        lines.insert(repos, f"{_TYPES_KEY}: [pre-commit, commit-msg, pre-push]")
        return ["pre-commit"]  # what pre-commit installs when the key is absent
    flow = _FLOW_TYPES.fullmatch(lines[key])
    if flow is not None:
        items = [item.strip() for item in flow[1].split(",") if item.strip()]
        missing = _missing_types(items)
        if missing:
            comment = f" {flow[2]}" if flow[2] else ""
            lines[key] = f"{_TYPES_KEY}: [{', '.join([*items, *missing])}]{comment}"
            return _bare(items)
        return None
    if not _blank_or_comment(lines[key][len(_TYPES_KEY) + 1 :]):
        raise Refusal(
            f"`{_TYPES_KEY}` must be a list on one line or a block list of hook types"
        )
    last, items = _block_items(lines, key)
    missing = _missing_types(items)
    if not missing:
        return None
    pad = " " * _indent(lines[last])
    lines[last + 1 : last + 1] = [f"{pad}- {t}" for t in missing]
    return _bare(items)


def _missing_types(items: Sequence[str]) -> list[str]:
    present = _bare(items)
    return [t for t in _WANTED_TYPES if t not in present]


def _block_items(lines: Sequence[str], key: int) -> tuple[int, list[str]]:
    """The index of the last item and the items of the block list under line `key`."""
    last, items = key, []
    for i in range(key + 1, len(lines)):
        if _blank_or_comment(lines[i]):
            continue
        item = _BLOCK_ITEM.fullmatch(lines[i])
        if item is None:
            break
        last = i
        items.append(item[1])
    if not items:
        raise Refusal(f"`{_TYPES_KEY}` has no items: list the hook types")
    return last, items


HUSKY_DIRECTORY = ".husky"
_HOOKS = ("commit-msg", "pre-push")
_HUSKY_SHEBANG = "#!/usr/bin/env sh"
# The pre-push block reads git's standard input once, hands it to the tool, ends the hook with
# its status when it fails, and gives the same input to the lines after it.
_HUSKY_BLOCKS = {
    "commit-msg": [
        BEGIN,
        _FOUND,
        '  prepush-ci hook commit-msg "$1" || exit $?',
        "else",
        f'  echo "{_WARNING}" >&2',
        "fi",
        END,
    ],
    "pre-push": [
        BEGIN,
        "refs=$(cat)",
        _FOUND,
        '  printf \'%s\\n\' "$refs" | prepush-ci hook pre-push "$@" || exit $?',
        "else",
        f'  echo "{_REFUSAL}" >&2',
        "  exit 1",
        "fi",
        "exec <<PREPUSH_CI_REFS",
        "$refs",
        "PREPUSH_CI_REFS",
        END,
    ],
}

LEFTHOOK_FILES = ("lefthook.yml", "lefthook.yaml", ".lefthook.yml", ".lefthook.yaml")
_LEFTHOOK_RUN = {
    "commit-msg": [
        f'run: {_FOUND} prepush-ci hook commit-msg {{1}}; else echo "{_WARNING}" >&2; fi'
    ],
    "pre-push": [
        f'run: {_FOUND} prepush-ci hook pre-push; else echo "{_REFUSAL}" >&2; exit 1; fi',
        "use_stdin: true",
    ],
}
_COMMANDS = re.compile(r"(\s*)commands:\s*(#.*)?")

MANAGERS = ("pre-commit", "husky", "lefthook")
CHOICES = ("native", *MANAGERS)
# What the worktree root holds for each manager.
MARKERS = {
    "pre-commit": (PRE_COMMIT_FILE,),
    "husky": (HUSKY_DIRECTORY,),
    "lefthook": LEFTHOOK_FILES,
}
# The team's own step, never run from here.
_ACTIVATION = {"pre-commit": "pre-commit install", "lefthook": "lefthook install"}


def choose(hooks: str | None, found: Sequence[str]) -> str:
    """The hooks to install: the one asked for, else the manager found, else native."""
    if hooks is not None:
        return hooks
    if len(found) > 1:
        raise Refusal(
            f"several hook managers found ({', '.join(found)}): "
            f"say which with --hooks {{{'|'.join(CHOICES)}}}"
        )
    return found[0] if found else "native"


def missing_message(manager: str) -> str:
    names = MARKERS[manager]
    return f"{manager} is not set up here: no {' or '.join(names)} at the worktree root"


def manager_files(manager: str, present: Sequence[str]) -> list[str]:
    """The files `install` edits for `manager`, relative to the worktree root; `present` are the
    names from `MARKERS` that exist."""
    if manager == "husky":
        return [f"{HUSKY_DIRECTORY}/{hook}" for hook in _HOOKS]
    if manager == "lefthook":
        return [present[0]]  # the first name wins, as it does for lefthook
    return [PRE_COMMIT_FILE]


def edit_file(manager: str, name: str, text: str | None) -> str:
    """The new contents of file `name` of `manager`, `text` being its contents or None."""
    if manager == "husky":
        return edit_husky(name.rsplit("/", 1)[-1], text)
    if manager == "lefthook":
        return edit_lefthook(text or "")
    return edit_pre_commit(text or "")


def lefthook_block(hook: str, indent: str) -> list[str]:
    """The command that runs the tool for `hook`, its key at `indent`."""
    body = [BEGIN, "prepush-ci:", *(f"  {line}" for line in _LEFTHOOK_RUN[hook]), END]
    return [f"{indent}{line}" for line in body]


def edit_lefthook(text: str) -> str:
    """The lefthook config with the command in `commit-msg` and `pre-push`, each added to the
    `commands:` it has or to a hook section added at the end."""
    lines, eol = split_lines(text)
    for hook in _HOOKS:
        lines = _lefthook_hook(lines, hook)
    return join_lines(lines, eol)


def _lefthook_hook(lines: list[str], hook: str) -> list[str]:
    key = _find(lines, hook)
    if key is None:
        return [*lines, f"{hook}:", "  commands:", *lefthook_block(hook, "    ")]
    where = f"`{hook}` must be a mapping with a block-style `commands:`"
    if not _blank_or_comment(lines[key][len(hook) + 1 :]):
        raise Refusal(where)
    end = next(
        (
            i
            for i in range(key + 1, len(lines))
            if not _blank_or_comment(lines[i]) and _indent(lines[i]) == 0
        ),
        len(lines),
    )
    commands = next(
        (i for i in range(key + 1, end) if _COMMANDS.fullmatch(lines[i])), None
    )
    if commands is None:
        raise Refusal(where)
    entries = next(
        (
            _indent(lines[i])
            for i in range(commands + 1, end)
            if not _blank_or_comment(lines[i])
        ),
        0,
    )
    inner = (
        entries if entries > _indent(lines[commands]) else _indent(lines[commands]) + 2
    )
    return place_block(
        lines, lefthook_block(hook, " " * inner), commands + 1, f"hook {hook}"
    )


def edit_husky(hook: str, text: str | None) -> str:
    """A husky hook file with the block before every other line (after a `#!` line): the whole
    file when `text` is None."""
    if text is None:
        return join_lines([_HUSKY_SHEBANG, *_HUSKY_BLOCKS[hook]], "\n")
    lines, eol = split_lines(text)
    after_shebang = 1 if lines and lines[0].startswith("#!") else 0
    return join_lines(place_block(lines, _HUSKY_BLOCKS[hook], after_shebang), eol)


def holds_block(text: str) -> bool:
    return find_block(split_lines(text)[0]) is not None


def manager_report(word: str, manager: str, files: Sequence[str]) -> str:
    lines = [f"{word}: {manager}", *(f"  {name}" for name in files)]
    if manager in _ACTIVATION:
        lines.append(f"next: run `{_ACTIVATION[manager]}` to activate the hooks")
    return "\n".join(lines)
