"""`prepush-ci init`: config, hooks, SessionStart hook and CI gate in one command."""

import contextlib
import io
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TextIO

from prepush_ci import install_command
from prepush_ci.core.config import ConfigError
from prepush_ci.core.config_source import (
    PREPUSH_CI_FILE,
    PYPROJECT_FILE,
    PYPROJECT_TABLE,
    ConfigMissing,
    load_config,
)
from prepush_ci.core.hook_managers import Refusal
from prepush_ci.core.init import (
    ALREADY_INSTALLED,
    CI_FILES,
    NEED_CHECK,
    NO_INPUT,
    NO_REPOSITORY,
    QUESTIONS,
    SESSION_HOOK_FILE,
    SESSION_QUESTION,
    SETTINGS_FILE,
    ConfigFlags,
    SettingsError,
    closing,
    config_text,
    default_branch_of,
    default_check,
    default_for,
    detect_ci,
    disagreement_message,
    disagreements,
    flags_from_answers,
    hooks_default,
    hooks_prompt,
    parse_hooks,
    parse_yes_no,
    pending,
    problems_message,
    register_session_hook,
    session_start_script,
    validate,
)
from prepush_ci.git import git


@dataclass(frozen=True)
class Options:
    flags: ConfigFlags
    non_interactive: bool = False
    hooks: str | None = None
    session_hook: bool = True
    ci: str | None = None
    ci_gate_file: str | None = None


class _Stop(Exception):
    """`init` ends before it writes anything: the message for standard error and the exit code."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Plan:
    """Everything `init` will do, decided and checked before the first write."""

    config_text: str | None  # None: a config exists
    source: str  # the file the existing config lives in
    hooks: str | None
    session_hook: bool
    settings_old: str | None
    settings_new: str | None
    gate: tuple[str, str] | None
    gate_file: tuple[str, Path] | None


def run(options: Options, cwd: Path, stdin: TextIO | None = None) -> int:
    root = _worktree_root(cwd)
    if root is None:
        print(NO_REPOSITORY, file=sys.stderr)
        return 1
    try:
        plan = _plan(options, cwd, root, sys.stdin if stdin is None else stdin)
    except _Stop as stop:
        print(stop, file=sys.stderr)
        return stop.code
    changed = False
    if plan.config_text is not None:
        (root / PREPUSH_CI_FILE).write_text(
            plan.config_text, encoding="utf-8", newline="\n"
        )
        print(f"written: {PREPUSH_CI_FILE}")
        changed = True
    else:
        print(f"kept: {plan.source}")
    code, installed = _install(plan.hooks, cwd)
    if code != 0:
        return code
    if plan.session_hook:
        changed = _session_hook(root, plan.hooks) or changed
        changed = _settings(root, plan.settings_old, plan.settings_new) or changed
    if plan.gate is not None:
        if plan.gate_file is None:
            print(f"CI gate ({plan.gate[0]}): add this to your CI")
            print(plan.gate[1], end="")
        else:
            changed = _gate_file(*plan.gate_file, plan.gate[1]) or changed
    print(closing(changed or installed))
    return 0


def _plan(options: Options, cwd: Path, root: Path, stdin: TextIO) -> _Plan:
    """Read the repository, ask the questions, and refuse whatever cannot work; no write."""
    try:
        config = load_config(
            _read(root / PREPUSH_CI_FILE), _read(root / PYPROJECT_FILE)
        )
    except ConfigMissing:
        config = None
    except ConfigError as error:
        raise _Stop(problems_message(error)) from error
    flags, hooks, session_hook = options.flags, options.hooks, options.session_hook
    if config is not None:
        wrong = disagreements(config, flags)
        if wrong:
            raise _Stop(disagreement_message(wrong, _source(root)))
    if not options.non_interactive:
        try:
            if config is None:
                flags = _ask_config(flags, root, stdin)
            if hooks is None:
                hooks = _ask_hooks(root, cwd, stdin)
            if session_hook:
                session_hook = parse_yes_no(_ask(stdin, SESSION_QUESTION))
        except Refusal as refusal:
            raise _Stop(f"prepush-ci init: {refusal}") from refusal
    text = None
    if config is None:
        if flags.check is None:
            raise _Stop(NEED_CHECK, 2)
        try:
            text = config_text(flags)
        except ValueError as error:  # a value that was not valid UTF-8
            raise _Stop(f"prepush-ci init: {error}") from error
        try:
            validate(text)
        except ConfigError as error:
            raise _Stop(problems_message(error)) from error
    settings_old = settings_new = None
    if session_hook:
        settings_old = _read(root / SETTINGS_FILE)
        try:
            settings_new = register_session_hook(settings_old)
        except SettingsError as error:
            raise _Stop(f"prepush-ci init: {error}") from error
    gate = _gate(options.ci, root)
    gate_file = None
    if gate is not None and options.ci_gate_file is not None:
        gate_file = (options.ci_gate_file, cwd / options.ci_gate_file)
        other = _read(gate_file[1])
        if other is not None and other != gate[1]:
            raise _Stop(
                f"prepush-ci init: {options.ci_gate_file} exists with other contents; "
                "not overwriting it"
            )
    return _Plan(
        text,
        _source(root),
        hooks,
        session_hook,
        settings_old,
        settings_new,
        gate,
        gate_file,
    )


def _ask(stdin: TextIO, prompt: str) -> str:
    """Show the question and read one line; the end of the input ends `init`."""
    print(prompt, flush=True)
    line = stdin.readline()
    if not line:
        raise _Stop(NO_INPUT)
    return line.strip()


def _ask_config(flags: ConfigFlags, root: Path, stdin: TextIO) -> ConfigFlags:
    """Ask for each config value no flag gave, with the default the repository suggests."""
    check = default_check(
        scripts_ci=(root / "scripts" / "ci").is_file(),
        bin_ci=(root / "bin" / "ci").is_file(),
        makefile=_read(root / "Makefile"),
    )
    head = git(root, "symbolic-ref", "refs/remotes/origin/HEAD")
    branch = default_branch_of(head.stdout.strip() if head.returncode == 0 else None)
    labels = dict(QUESTIONS)
    answers: dict[str, str] = {}
    for key in pending(flags):
        default = default_for(key, flags, answers, check, branch)
        answers[key] = _ask(
            stdin, f"{labels[key]} [{default}]" if default else labels[key]
        )
    return flags_from_answers(flags, answers, check, branch)


def _ask_hooks(root: Path, cwd: Path, stdin: TextIO) -> str:
    """Ask what to do about hooks, naming what is there already."""
    managers = install_command.found_files(root)
    hook = install_command.previous_pre_push(cwd)
    previous = None
    if hook is not None:
        try:
            previous = hook.relative_to(root.resolve()).as_posix()
        except ValueError:  # a hooks directory outside the worktree
            previous = hook.as_posix()
    default = hooks_default(list(managers))
    prompt = hooks_prompt(list(managers.values()), previous, default)
    return parse_hooks(_ask(stdin, prompt), default)


def _gate(ci: str | None, root: Path) -> tuple[str, str] | None:
    """The system whose CI gate to show and the text of the snippet; None for `--ci none`."""
    system = ci or detect_ci(
        workflows=_has_workflows(root), gitlab=(root / ".gitlab-ci.yml").is_file()
    )
    if system == "none":
        return None
    text = (
        resources.files("prepush_ci")
        .joinpath("ci_gates", CI_FILES[system])
        .read_text(encoding="utf-8")
    )
    return system, text if text.endswith("\n") else text + "\n"


def _gate_file(name: str, target: Path, text: str) -> bool:
    """Write the snippet to `target` unless it holds it already; whether it was written."""
    if _read(target) == text:
        print(f"kept: {name}")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"written: {name}")
    return True


def _has_workflows(root: Path) -> bool:
    directory = root / ".github" / "workflows"
    return directory.is_dir() and any(
        entry.is_file() and entry.suffix in (".yml", ".yaml")
        for entry in directory.iterdir()
    )


def _settings(root: Path, old: str | None, new: str | None) -> bool:
    """Write the settings file with the hook registered; whether it changed."""
    if new is None or new == old:
        print(f"kept: {SETTINGS_FILE}")
        return False
    path = root / SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8", newline="\n")
    print(f"{'written' if old is None else 'updated'}: {SETTINGS_FILE}")
    return True


def _session_hook(root: Path, hooks: str | None) -> bool:
    """Write the SessionStart script unless there is one; whether it was written."""
    path = root / SESSION_HOOK_FILE
    if path.exists():
        print(f"kept: {SESSION_HOOK_FILE}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session_start_script(hooks), encoding="utf-8", newline="\n")
    path.chmod(0o755)
    print(f"written: {SESSION_HOOK_FILE}")
    return True


def _install(hooks: str | None, cwd: Path) -> tuple[int, bool]:
    """Run `install` and show what it printed: its exit code, and whether it changed anything.
    A refusal ends `init` with its message."""
    if hooks == "none":
        print("skipped: hooks (--hooks none)")
        return 0, False
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = install_command.run(cwd, hooks)
    print(printed.getvalue(), end="")
    return code, not printed.getvalue().startswith(ALREADY_INSTALLED)


def _source(root: Path) -> str:
    """The file the existing config lives in."""
    if (root / PREPUSH_CI_FILE).exists():
        return PREPUSH_CI_FILE
    return f"{PYPROJECT_FILE} {PYPROJECT_TABLE}"


def _worktree_root(cwd: Path) -> Path | None:
    top = git(cwd, "rev-parse", "--show-toplevel")
    return Path(top.stdout.strip()) if top.returncode == 0 else None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
