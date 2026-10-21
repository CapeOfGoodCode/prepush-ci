"""The `commit-msg` and `pre-push` checks of `prepush-ci doctor`: would git run our hooks?"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from prepush_ci.core.doctor import Check, fail, ok
from prepush_ci.core.hook_managers import Refusal, find_block, split_lines

HUSKY_PATHS = (".husky", ".husky/_")
_ACTIVATION = {
    "pre-commit": "pre-commit install",
    "lefthook": "lefthook install",
    "husky": "npx husky",
}
_NAMED_IN_SCRIPT = {"pre-commit": "pre-commit", "lefthook": "lefthook"}
_REINSTALL = "run `prepush-ci install`"
_NATIVE_HINT = "if you chose native hooks, run `prepush-ci doctor --hooks native`"


@dataclass(frozen=True)
class Script:
    """A file git may run as a hook, as it is on disk."""

    exists: bool
    executable: bool = False
    content: str = ""


@dataclass(frozen=True)
class NativeFacts:
    """What the native hooks look like on disk."""

    configured: str | None  # `core.hooksPath` as configured; None when unset
    ours: bool  # whether the effective `core.hooksPath` is `directory`
    directory: str  # where `install` writes the scripts
    scripts: Mapping[str, Script]  # by hook name, in `directory`
    interpreter: (
        str | None
    )  # the contents of the file `python`; None when it is missing
    interpreter_exists: bool


@dataclass(frozen=True)
class ManagerFacts:
    """What a hook manager's files look like on disk, for one hook."""

    manager: str
    detected: bool  # found from its files, not named with `--hooks`
    file: str  # the file `install` edits for this hook, relative to the worktree root
    content: str | None  # its contents; None when it does not exist
    hooks_path: (
        str | None
    )  # the effective `core.hooksPath`, relative to the root when inside it
    hooks_directory: str  # the directory git takes hooks from
    installed: Script  # the hook of this name in `hooks_directory`


@dataclass(frozen=True)
class Binary:
    """The `prepush-ci` a manager's hooks find on `PATH`, and what it answered to `--version`."""

    path: str | None  # where it is; None when `PATH` holds none
    line: str | None = (
        None  # the first line it printed; None when its version was not read
    )
    why: str = ""  # why the version was not read: "it printed nothing", "it exited with status 1"


def none_check(hook: str) -> Check:
    return ok(hook, "no local hooks wanted (`--hooks none`)")


def refusal_check(hook: str, message: str) -> Check:
    return fail(hook, message, "say which with `prepush-ci doctor --hooks <hooks>`")


def native_check(hook: str, facts: NativeFacts) -> Check:
    """Whether git would run our script for `hook`: right directory, executable, a live interpreter."""
    if not facts.ours:
        if facts.configured is None:
            text = f"core.hooksPath is not set, so git does not run {facts.directory}"
        else:
            text = (
                f"core.hooksPath is {facts.configured}, not {facts.directory}: "
                "another tool took over the hooks"
            )
        return fail(hook, text, _REINSTALL)
    script = facts.scripts[hook]
    if not script.exists:
        return fail(hook, f"{facts.directory}/{hook} does not exist", _REINSTALL)
    if not script.executable:
        text = f"{facts.directory}/{hook} is not executable, so git skips it"
        return fail(hook, text, _REINSTALL)
    if facts.interpreter is None:
        text = f"the file python is missing from {facts.directory}"
        return fail(hook, text, _REINSTALL)
    if not facts.interpreter_exists:
        text = f"the interpreter {facts.interpreter} no longer exists"
        return fail(hook, text, _REINSTALL)
    return ok(hook, f"{facts.directory}/{hook} runs {facts.interpreter}")


def manager_check(
    hook: str, facts: ManagerFacts, own: str | None, binary: Callable[[], Binary]
) -> Check:
    """Whether the manager's file has our block for `hook`, git would run the manager, and the
    manager finds the `prepush-ci` whose `--version` line is `own` (None when doctor cannot read
    its own). `binary` looks it up and runs it; it is called only for a check that has passed
    everything else."""
    problem = _manager_problem(hook, facts)
    if problem is None:
        if own is None:
            set_up = f"{facts.file} has the block and {facts.manager} is activated"
            text = f"{set_up}, but this prepush-ci cannot read its own version, so the hook's cannot be compared"
            return fail(
                hook,
                text,
                "run doctor from an installed prepush-ci (`uv tool install prepush-ci`)",
            )
        return _binary_check(hook, facts, own, binary())
    text, fix = problem
    if facts.detected:
        fix = f"{fix}; {_NATIVE_HINT}"
    return fail(hook, text, fix)


def _binary_check(hook: str, facts: ManagerFacts, own: str, found: Binary) -> Check:
    set_up = f"{facts.file} has the block and {facts.manager} is activated"
    if found.path is None:
        text = f"{set_up}, but no prepush-ci is on PATH"
        return fail(hook, text, f"put the prepush-ci that prints `{own}` on PATH")
    if found.line is None:
        text = (
            f"{set_up}, but the version of {found.path} could not be read: {found.why}"
        )
        return fail(hook, text, f"put the prepush-ci that prints `{own}` first on PATH")
    if found.line != own:
        text = f"{set_up}, but the hook runs {found.path}: {found.line}, not {own}"
        return fail(hook, text, f"put the prepush-ci that prints `{own}` first on PATH")
    return ok(hook, f"{set_up}; the hook runs {found.path}: {found.line}")


def _manager_problem(hook: str, facts: ManagerFacts) -> tuple[str, str] | None:
    """What is wrong and how to fix it; None when nothing is."""
    manager = facts.manager
    install = (
        "run `prepush-ci install`"
        if facts.detected
        else f"run `prepush-ci install --hooks {manager}`"
    )
    if facts.content is None:
        return f"{facts.file} does not exist", install
    try:
        block = find_block(split_lines(facts.content)[0], f"prepush-ci hook {hook}")
    except Refusal as refusal:
        return f"{facts.file}: {refusal}", install
    if block is None:
        return f"{facts.file} has no prepush-ci block for {hook}", install
    if manager == "husky":
        return _husky_problem(hook, facts)
    return _activation_problem(hook, facts)


def _husky_problem(hook: str, facts: ManagerFacts) -> tuple[str, str] | None:
    fix = f"run `{_ACTIVATION['husky']}`"
    if facts.hooks_path not in HUSKY_PATHS:
        shown = facts.hooks_path or "unset"
        text = f"husky is not set up on this clone: core.hooksPath is {shown}, not .husky/_"
        return text, fix
    where = f"{facts.hooks_path}/{hook}"
    if not facts.installed.exists:
        return f"husky: {where} does not exist, so git runs no hook", fix
    if not facts.installed.executable:
        return f"husky: {where} is not executable, so git skips it", fix
    return None


def _activation_problem(hook: str, facts: ManagerFacts) -> tuple[str, str] | None:
    manager = facts.manager
    where = f"{facts.hooks_directory}/{hook}"
    script = facts.installed
    if not script.exists:
        reason = "does not exist"
    elif not script.executable:
        reason = "is not executable"
    elif _NAMED_IN_SCRIPT[manager] not in script.content:
        reason = f"does not run {manager}"
    else:
        return None
    return (
        f"{manager} is not activated: {where} {reason}",
        f"run `{_ACTIVATION[manager]}`",
    )
