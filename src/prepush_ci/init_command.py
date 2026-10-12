"""`prepush-ci init`: config, hooks, SessionStart hook and CI gate in one command."""

import contextlib
import io
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from prepush_ci import install_command
from prepush_ci.core.config import ConfigError
from prepush_ci.core.config_source import (
    PREPUSH_CI_FILE,
    PYPROJECT_FILE,
    PYPROJECT_TABLE,
    ConfigMissing,
    load_config,
)
from prepush_ci.core.init import (
    ALREADY_INSTALLED,
    CI_FILES,
    NEED_CHECK,
    NO_REPOSITORY,
    SESSION_HOOK_FILE,
    SETTINGS_FILE,
    ConfigFlags,
    SettingsError,
    closing,
    config_text,
    detect_ci,
    disagreement_message,
    disagreements,
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


def run(options: Options, cwd: Path) -> int:
    root = _worktree_root(cwd)
    if root is None:
        print(NO_REPOSITORY, file=sys.stderr)
        return 1
    try:
        config = load_config(
            _read(root / PREPUSH_CI_FILE), _read(root / PYPROJECT_FILE)
        )
    except ConfigMissing:
        config = None
    except ConfigError as error:
        print(problems_message(error), file=sys.stderr)
        return 1
    if config is not None:
        wrong = disagreements(config, options.flags)
        if wrong:
            print(disagreement_message(wrong, _source(root)), file=sys.stderr)
            return 1
        text = None
    else:
        if options.flags.check is None:
            print(NEED_CHECK, file=sys.stderr)
            return 2
        try:
            text = config_text(options.flags)
        except ValueError as error:  # a value that was not valid UTF-8
            print(f"prepush-ci init: {error}", file=sys.stderr)
            return 1
        try:
            validate(text)
        except ConfigError as error:
            print(problems_message(error), file=sys.stderr)
            return 1
    settings_old: str | None = None
    settings_new: str | None = None
    if options.session_hook:
        settings_old = _read(root / SETTINGS_FILE)
        try:
            settings_new = register_session_hook(settings_old)
        except SettingsError as error:
            print(f"prepush-ci init: {error}", file=sys.stderr)
            return 1
    gate = _gate(options.ci, root)
    target = None if options.ci_gate_file is None else cwd / options.ci_gate_file
    if gate is not None and target is not None:
        other = _read(target)
        if other is not None and other != gate[1]:
            print(
                f"prepush-ci init: {options.ci_gate_file} exists with other contents; "
                "not overwriting it",
                file=sys.stderr,
            )
            return 1
    changed = False
    if text is not None:
        (root / PREPUSH_CI_FILE).write_text(text, encoding="utf-8", newline="\n")
        print(f"written: {PREPUSH_CI_FILE}")
        changed = True
    else:
        print(f"kept: {_source(root)}")
    code, installed = _install(options.hooks, cwd)
    if code != 0:
        return code
    if options.session_hook:
        changed = _session_hook(root, options.hooks) or changed
        changed = _settings(root, settings_old, settings_new) or changed
    if gate is not None:
        if target is None:
            print(f"CI gate ({gate[0]}): add this to your CI")
            print(gate[1], end="")
        else:
            changed = _gate_file(options.ci_gate_file or "", target, gate[1]) or changed
    print(closing(changed or installed))
    return 0


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
