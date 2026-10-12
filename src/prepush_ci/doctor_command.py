"""`prepush-ci doctor`: look at what git would run and say what is missing, changing nothing."""

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from prepush_ci.core import doctor, doctor_hooks
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.config_source import PREPUSH_CI_FILE, PYPROJECT_FILE, ConfigMissing
from prepush_ci.core.doctor_hooks import ManagerFacts, NativeFacts, Script
from prepush_ci.core.hook_managers import (
    HUSKY_DIRECTORY,
    LEFTHOOK_FILES,
    MANAGERS,
    MARKERS,
    PRE_COMMIT_FILE,
    Refusal,
    choose,
)
from prepush_ci.core.install import HOOKS, HOOKS_DIRECTORY, PYTHON_FILE
from prepush_ci.git import git
from prepush_ci.repo_config import load_repository_config


def run(
    cwd: Path,
    env: Mapping[str, str],
    hooks: str | None = None,
    mode: str | None = None,
) -> int:
    try:
        common_dir = git(cwd, "rev-parse", "--git-common-dir")
    except OSError as error:  # git cannot even start
        print(f"prepush-ci doctor: cannot run git: {error}", file=sys.stderr)
        return 1
    if common_dir.returncode != 0:
        print(doctor.NO_REPOSITORY, file=sys.stderr)
        return 1
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print(doctor.NO_WORKTREE, file=sys.stderr)
        return 1
    root = (cwd / top.stdout.strip()).resolve()
    common = (cwd / common_dir.stdout.strip()).resolve()
    commit_msg, pre_push = _hook_checks(cwd, root, common, hooks)
    config, config_check = _config(root)
    found = {
        doctor.CONFIG: config_check,
        doctor.COMMIT_MSG: commit_msg,
        doctor.PRE_PUSH: pre_push,
        doctor.PREFLIGHT: _needs_config(config, doctor.PREFLIGHT),
        doctor.PREPUSH_CI: doctor.prepush_ci_check(env.get("PREPUSH_CI"), mode),
        doctor.UP_TO_DATE: _needs_config(config, doctor.UP_TO_DATE),
    }
    checks = [found[name] for name in doctor.NAMES]
    print("\n".join(doctor.render(checks)))
    return doctor.exit_status(checks)


def _config(root: Path) -> tuple[Config | None, doctor.Check]:
    """The config of the worktree and the verdict of the `config` check."""
    source = PREPUSH_CI_FILE if (root / PREPUSH_CI_FILE).exists() else PYPROJECT_FILE
    try:
        config = load_repository_config(root)
    except ConfigMissing as error:
        return None, doctor.config_check(None, error.problems, missing=True)
    except ConfigError as error:
        return None, doctor.config_check(source, error.problems, missing=False)
    except (OSError, UnicodeDecodeError) as error:
        problem = f"cannot read {source}: {error}"
        return None, doctor.config_check(source, [problem], missing=False)
    return config, doctor.config_check(source, [], missing=False)


def _needs_config(config: Config | None, name: str) -> doctor.Check:
    if config is None:
        return doctor.config_skip(name)
    return doctor.skip(name, "not checked yet")


def _hook_checks(
    cwd: Path, root: Path, common: Path, hooks: str | None
) -> tuple[doctor.Check, doctor.Check]:
    """The `commit-msg` and `pre-push` verdicts for the hooks asked for, else the manager found,
    else the native ones."""
    if hooks == "none":
        return doctor_hooks.none_check(HOOKS[0]), doctor_hooks.none_check(HOOKS[1])
    found = [m for m in MANAGERS if any(_marker(root, n) for n in MARKERS[m])]
    try:
        chosen = choose(hooks, found)
    except Refusal as refusal:
        message = str(refusal)
        return (
            doctor_hooks.refusal_check(HOOKS[0], message),
            doctor_hooks.refusal_check(HOOKS[1], message),
        )
    if chosen == "native":
        native = _native_facts(cwd, root, common)
        return (
            doctor_hooks.native_check(HOOKS[0], native),
            doctor_hooks.native_check(HOOKS[1], native),
        )
    detected = hooks is None
    return (
        doctor_hooks.manager_check(
            HOOKS[0], _manager_facts(cwd, root, chosen, HOOKS[0], detected)
        ),
        doctor_hooks.manager_check(
            HOOKS[1], _manager_facts(cwd, root, chosen, HOOKS[1], detected)
        ),
    )


def _marker(root: Path, name: str) -> bool:
    """Whether the worktree root holds `name`: a directory for husky, a file for the others."""
    path = root / name
    return path.is_dir() if name == HUSKY_DIRECTORY else path.is_file()


def _hooks_path(cwd: Path, root: Path) -> tuple[str, Path] | None:
    """The effective `core.hooksPath` as configured and made absolute against the worktree root."""
    configured = git(cwd, "config", "--type=path", "--get", "core.hooksPath")
    value = configured.stdout.strip()
    if configured.returncode != 0 or not value:
        return None
    return value, (root / value).resolve()


def _script(path: Path) -> Script:
    if not path.is_file():
        return Script(exists=False)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):  # a binary hook is still a hook git runs
        text = ""
    return Script(exists=True, executable=os.access(path, os.X_OK), text=text)


def _native_facts(cwd: Path, root: Path, common: Path) -> NativeFacts:
    directory = common.joinpath(*HOOKS_DIRECTORY)
    configured = _hooks_path(cwd, root)
    interpreter = _script(directory / PYTHON_FILE)
    recorded = interpreter.text.strip() if interpreter.exists else None
    return NativeFacts(
        configured=configured[0] if configured else None,
        ours=configured is not None and configured[1] == directory,
        directory=directory.as_posix(),
        scripts={hook: _script(directory / hook) for hook in HOOKS},
        interpreter=recorded,
        interpreter_exists=recorded is not None and os.access(recorded, os.X_OK),
    )


def _manager_file(root: Path, manager: str, hook: str) -> str:
    """The file `install` edits for `hook`, relative to the worktree root."""
    if manager == "husky":
        return f"{HUSKY_DIRECTORY}/{hook}"
    if manager == "lefthook":
        return next(
            (n for n in LEFTHOOK_FILES if (root / n).is_file()), LEFTHOOK_FILES[0]
        )
    return PRE_COMMIT_FILE


def _manager_facts(
    cwd: Path, root: Path, manager: str, hook: str, detected: bool
) -> ManagerFacts:
    name = _manager_file(root, manager, hook)
    try:
        text: str | None = (root / name).read_text(encoding="utf-8")
    except FileNotFoundError:
        text = None
    except (OSError, UnicodeDecodeError):  # unreadable: it holds no block we could find
        text = ""
    configured = _hooks_path(cwd, root)
    if configured is not None:
        directory = configured[1]
        inside = (
            directory.relative_to(root).as_posix()
            if directory.is_relative_to(root)
            else None
        )
        shown = inside or configured[1].as_posix()
    else:
        git_path = git(cwd, "rev-parse", "--git-path", "hooks").stdout.strip()
        directory = (cwd / git_path).resolve()
        shown = None
    return ManagerFacts(
        manager=manager,
        detected=detected,
        file=name,
        text=text,
        hooks_path=shown,
        hooks_directory=directory.as_posix(),
        installed=_script(directory / hook),
    )
