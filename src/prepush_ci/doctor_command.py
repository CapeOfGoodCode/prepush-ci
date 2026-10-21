"""`prepush-ci doctor`: look at what git would run and say what is missing, changing nothing."""

import os
import sys
from collections.abc import Callable, Mapping
from functools import cache
from importlib import metadata
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core import doctor, doctor_hooks
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.config_source import PREPUSH_CI_FILE, PYPROJECT_FILE, ConfigMissing
from prepush_ci.core.doctor_hooks import Binary, ManagerFacts, NativeFacts, Script
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
from prepush_ci.core.preflight import missing_env
from prepush_ci.git import answer, git
from prepush_ci.repo_config import load_repository_config
from prepush_ci.version_line import own_version_line

PROBE = "prepush-ci-doctor-probe"  # the alias that runs a command in git's shell
VERSION_SECONDS = (
    10  # what `prepush-ci --version` of a healthy install needs is far less
)


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
    root = (cwd / text_io.to_path(answer(top))).resolve()
    common = (cwd / text_io.to_path(answer(common_dir))).resolve()
    commit_msg, pre_push = _hook_checks(cwd, root, common, hooks, env)
    config, config_check = _config(root)
    found = {
        doctor.CONFIG: config_check,
        doctor.COMMIT_MSG: commit_msg,
        doctor.PRE_PUSH: pre_push,
        doctor.PREFLIGHT: _preflight(config, root, env),
        doctor.PREPUSH_CI: doctor.prepush_ci_check(env.get("PREPUSH_CI"), mode),
        doctor.UP_TO_DATE: _up_to_date(config, root, env),
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
    except OSError as error:
        problem = f"cannot read {source}: {error}"
        return None, doctor.config_check(source, [problem], missing=False)
    return config, doctor.config_check(source, [], missing=False)


def _preflight(
    config: Config | None, root: Path, env: Mapping[str, str]
) -> doctor.Check:
    """The `preflight` verdict: the variables, then the command run as the hook runs it."""
    if config is None:
        return doctor.config_skip(doctor.PREFLIGHT)
    return doctor.preflight_check(
        config.preflight,
        config.require_env,
        missing_env(config.require_env, env),
        lambda: _run_preflight(config.preflight or "", root, env),
    )


def _run_preflight(command: str, root: Path, env: Mapping[str, str]) -> tuple[int, str]:
    """The exit status and the output of `command`, from the repository root, asking nothing.

    The output goes to an unnamed temporary file, not a pipe: a process the command leaves
    running keeps a pipe open and would hold `doctor`, while the hook returns at once.
    """
    return text_io.run_shell_captured(command, cwd=root, env=env)


def _up_to_date(
    config: Config | None, root: Path, env: Mapping[str, str]
) -> doctor.Check:
    """The `up-to-date` verdict: the remote answers and has the branch; nothing is fetched."""
    if config is None:
        return doctor.config_skip(doctor.UP_TO_DATE)
    quiet = {**env, "GIT_TERMINAL_PROMPT": "0"}  # a credential prompt is no diagnosis

    def ls_remote(remote: str, branch: str) -> tuple[int, str]:
        result = git(
            root,
            "ls-remote",
            "--exit-code",
            "--",
            remote,
            f"refs/heads/{branch}",
            env=quiet,
        )
        return result.returncode, next(iter(result.stderr.strip().splitlines()), "")

    return doctor.up_to_date_check(
        config.require_up_to_date, git(root, "remote").stdout.split(), ls_remote
    )


def _hook_checks(
    cwd: Path, root: Path, common: Path, hooks: str | None, env: Mapping[str, str]
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
    try:
        own: str | None = own_version_line()
    except (
        metadata.PackageNotFoundError
    ):  # run from source that is no installed distribution
        own = None
    binary = _binary_on_path(root, env)
    return (
        doctor_hooks.manager_check(
            HOOKS[0], _manager_facts(cwd, root, chosen, HOOKS[0], detected), own, binary
        ),
        doctor_hooks.manager_check(
            HOOKS[1], _manager_facts(cwd, root, chosen, HOOKS[1], detected), own, binary
        ),
    )


def _through_git_shell(
    root: Path, env: Mapping[str, str], command: str
) -> tuple[int, str] | None:
    """Run `command` as the hooks of a manager would: in the shell git runs a hook with (on
    Windows the sh of Git for Windows, not one on `PATH`), from the repository root, which is
    where that shell finds an empty or a relative `PATH` entry. Git runs the command of an alias
    that starts with `!` in exactly that shell, from the top of the worktree."""
    return text_io.run_limited(
        ["git", "-c", f"alias.{PROBE}=!{command}", PROBE],
        cwd=root,
        env=env,
        seconds=VERSION_SECONDS,
    )


def _binary_on_path(root: Path, env: Mapping[str, str]) -> Callable[[], Binary]:
    """The look-up of the `prepush-ci` the hooks find on `PATH`, done once and only when asked:
    a failure that is already there needs no executable run."""

    @cache
    def look() -> Binary:
        found = _through_git_shell(root, env, "command -v prepush-ci")
        if found is None or found[0] != 0 or not found[1].strip():
            return Binary(None)
        shown = found[1].splitlines()[0].strip()
        done = _through_git_shell(root, env, "prepush-ci --version")
        if done is None:
            return Binary(
                shown, None, f"it did not finish in {VERSION_SECONDS} seconds"
            )
        status, output = done
        if status != 0:
            return Binary(shown, None, f"it exited with status {status}")
        line = next(iter(output.splitlines()), "").strip()
        if not line:
            return Binary(shown, None, "it printed no line")
        return Binary(shown, line)

    return look


def _marker(root: Path, name: str) -> bool:
    """Whether the worktree root holds `name`: a directory for husky, a file for the others."""
    path = root / name
    return path.is_dir() if name == HUSKY_DIRECTORY else path.is_file()


def _hooks_path(cwd: Path, root: Path) -> tuple[str, Path] | None:
    """The effective `core.hooksPath` as configured and made absolute against the worktree root."""
    configured = git(cwd, "config", "--type=path", "--get", "core.hooksPath")
    value = answer(configured)
    if configured.returncode != 0 or not value:
        return None
    return value, (root / text_io.to_path(value)).resolve()


def _script(path: Path) -> Script:
    if not path.is_file():
        return Script(exists=False)
    try:
        text = text_io.read_text(path)
    except OSError:  # a hook that cannot be read is still a hook git runs
        text = ""
    return Script(exists=True, executable=os.access(path, os.X_OK), content=text)


def _native_facts(cwd: Path, root: Path, common: Path) -> NativeFacts:
    directory = common.joinpath(*HOOKS_DIRECTORY)
    configured = _hooks_path(cwd, root)
    interpreter = _script(directory / PYTHON_FILE)
    recorded = interpreter.content.strip() if interpreter.exists else None
    return NativeFacts(
        configured=configured[0] if configured else None,
        ours=configured is not None and configured[1] == directory,
        directory=text_io.text_of(directory),
        scripts={hook: _script(directory / hook) for hook in HOOKS},
        interpreter=recorded,
        interpreter_exists=recorded is not None
        and os.access(text_io.to_os(recorded), os.X_OK),
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
        text: str | None = text_io.read_text(root / name)
    except FileNotFoundError:
        text = None
    except OSError:  # unreadable: it holds no block we could find
        text = ""
    configured = _hooks_path(cwd, root)
    if configured is not None:
        directory = configured[1]
        inside = (
            text_io.text_of(directory.relative_to(root))
            if directory.is_relative_to(root)
            else None
        )
        shown = inside or text_io.text_of(configured[1])
    else:
        git_path = git(cwd, "rev-parse", "--git-path", "hooks").stdout.strip()
        directory = (cwd / text_io.to_path(git_path)).resolve()
        shown = None
    return ManagerFacts(
        manager=manager,
        detected=detected,
        file=name,
        content=text,
        hooks_path=shown,
        hooks_directory=text_io.text_of(directory),
        installed=_script(directory / hook),
    )
