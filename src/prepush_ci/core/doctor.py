"""What `prepush-ci doctor` says: one line per check, a fix after every failure, a closing line."""

from collections.abc import Callable, Sequence
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
_WAY_OUT = "set `require_up_to_date = false` in the config"
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


def preflight_check(
    command: str | None,
    required: Sequence[str],
    missing: Sequence[str],
    run_command: Callable[[], tuple[int, str]],
) -> Check:
    """`missing` are the required variables that are unset or empty; `run_command` runs the
    preflight command and gives its exit status and output, and is called only when no variable
    is missing."""
    if missing:
        names = ", ".join(missing)
        return fail(
            PREFLIGHT,
            f"these environment variables are unset or empty: {names}",
            f"set {names} (`require_env` in the config); the command was not run",
        )
    if command is None:
        if required:
            return ok(PREFLIGHT, f"{', '.join(required)} set; no `preflight` command")
        return ok(PREFLIGHT, "nothing to verify: no `preflight` and no `require_env`")
    status, output = run_command()
    if status != 0:
        return fail(
            PREFLIGHT,
            f"`{command}` exited {status}",
            f"make `{command}` pass; its output follows",
            output.splitlines(),
        )
    return ok(PREFLIGHT, "the `preflight` command exited 0")


def up_to_date_check(
    ref: str | None,
    remotes: Sequence[str],
    ls_remote: Callable[[str, str], tuple[int, str]],
) -> Check:
    """`ref` is `require_up_to_date` (None when disabled); `ls_remote(remote, branch)` gives the
    exit status of `git ls-remote --exit-code` and its error output, and is called only for a
    ref of a configured remote."""
    if ref is None:
        return ok(UP_TO_DATE, "disabled: `require_up_to_date = false`")
    remote, separator, branch = ref.partition("/")
    if not separator or not remote or not branch:
        return fail(
            UP_TO_DATE,
            f'`require_up_to_date = "{ref}"` must be `<remote>/<branch>`, such as `origin/main`',
            f"write the ref as `<remote>/<branch>`, or {_WAY_OUT}",
        )
    if remote not in remotes:
        return fail(
            UP_TO_DATE,
            f"{ref}: the repository has no remote named `{remote}`",
            f"add it with `git remote add {remote} <url>`, or {_WAY_OUT}",
        )
    status, error = ls_remote(remote, branch)
    if status == 2:
        return fail(
            UP_TO_DATE,
            f"{ref}: the remote `{remote}` has no branch `{branch}`",
            f"push `{branch}` to `{remote}`, or {_WAY_OUT}",
        )
    if status != 0:
        reason = f": {error}" if error else ""
        return fail(
            UP_TO_DATE,
            f"{ref}: the remote `{remote}` cannot be reached{reason}",
            f"check the URL (`git remote get-url {remote}`) and the network, or {_WAY_OUT}",
        )
    return ok(UP_TO_DATE, f"{ref} is on the remote `{remote}`")
