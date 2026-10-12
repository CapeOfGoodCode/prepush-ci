"""What `prepush-ci doctor` says: one line per check, a fix after every failure, a closing line."""

from collections.abc import Sequence
from dataclasses import dataclass

from prepush_ci.core.config_source import PREPUSH_CI_FILE

CONFIG = "config"
COMMIT_MSG = "commit-msg"
PRE_PUSH = "pre-push"
PREFLIGHT = "preflight"
PREPUSH_CI = "PREPUSH_CI"
UP_TO_DATE = "up-to-date"
NAMES = (CONFIG, COMMIT_MSG, PRE_PUSH, PREFLIGHT, PREPUSH_CI, UP_TO_DATE)

OK = "ok"
FAIL = "fail"
SKIP = "skip"

MODES = ("full", "off", "unset")
_VALID_VALUES = ("full", "off", "")
_MEANING = {
    "full": "commits get the trailer",
    "off": "a push of a commit with the trailer is refused",
    "": "no trailer is written",
}
NO_REPOSITORY = "prepush-ci doctor: there is no git repository here"
NO_WORKTREE = "prepush-ci doctor: this repository has no working tree to check"


@dataclass(frozen=True)
class Check:
    """The verdict of one check: `ok`, `fail` or `skip`, what it found, and the way out of a
    failure. `detail` is printed indented after the fix, for output of the user's own."""

    status: str
    name: str
    text: str
    fix: str | None = None
    detail: tuple[str, ...] = ()


def ok(name: str, text: str) -> Check:
    return Check(OK, name, text)


def fail(name: str, text: str, fix: str, detail: Sequence[str] = ()) -> Check:
    return Check(FAIL, name, text, fix, tuple(detail))


def skip(name: str, text: str) -> Check:
    return Check(SKIP, name, text)


def exit_status(checks: Sequence[Check]) -> int:
    """0 only when every check passed; a skip is not a pass."""
    return 0 if all(check.status == OK for check in checks) else 1


def closing(checks: Sequence[Check]) -> str:
    """The last line: all passed, or how many of the checks did not."""
    failed = sum(check.status != OK for check in checks)
    if not failed:
        return "all checks passed"
    return f"{failed} of {len(checks)} checks did not pass"


def render(checks: Sequence[Check]) -> list[str]:
    """Every output line: each check, its fix and detail lines, then the closing line."""
    lines: list[str] = []
    for check in checks:
        lines.append(f"{check.status} {check.name}: {check.text}")
        if check.fix is not None:
            lines.append(f"  fix: {check.fix}")
        lines.extend(f"    {line}" for line in check.detail)
    lines.append(closing(checks))
    return lines


def config_check(
    source: str | None, problems: Sequence[str], *, missing: bool
) -> Check:
    """`source` is the file the config was read from; `problems` is empty when it loaded."""
    if not problems:
        return ok(CONFIG, f"loaded from {source}")
    if missing:
        fix = f"run `prepush-ci init`, or create `{PREPUSH_CI_FILE}` with a `check` key"
    else:
        fix = f"correct {source}: every problem above names its key"
    return fail(CONFIG, "; ".join(problems), fix)


def config_skip(name: str) -> Check:
    return skip(name, "the config is not valid")


def prepush_ci_check(value: str | None, mode: str | None) -> Check:
    """`value` is `PREPUSH_CI` (None when unset); `mode` is the value `--mode` expects."""
    found = value or ""
    if found not in _VALID_VALUES:
        return fail(
            PREPUSH_CI,
            f"PREPUSH_CI={found!r} is not valid: use `full` or `off`, or leave it unset",
            "run `export PREPUSH_CI=full` (or `off`), or `unset PREPUSH_CI`",
        )
    shown = found or "unset"
    if mode is not None and shown != mode:
        fix = "unset PREPUSH_CI" if mode == "unset" else f"export PREPUSH_CI={mode}"
        return fail(
            PREPUSH_CI,
            f"PREPUSH_CI is {shown}, expected {mode}",
            f"run `{fix}`",
        )
    if found:
        return ok(PREPUSH_CI, f"PREPUSH_CI={found}: {_MEANING[found]}")
    return ok(PREPUSH_CI, f"PREPUSH_CI is unset: {_MEANING['']}")
