"""`prepush-ci install`: point git at hook scripts that run this tool."""

import os
import sys
from pathlib import Path

from prepush_ci.core.hook_managers import (
    HUSKY_DIRECTORY,
    MANAGERS,
    MARKERS,
    Refusal,
    choose,
    edit_file,
    holds_block,
    manager_files,
    manager_report,
    missing_message,
)
from prepush_ci.core.install import (
    HOOKS,
    HOOKS_DIRECTORY,
    NO_REPOSITORY,
    PREVIOUS_FILE,
    Existing,
    changes,
    desired_files,
    forwardable,
    outcome,
    report,
)
from prepush_ci.core.uv_cache import TEMPORARY_WARNING, is_temporary
from prepush_ci.git import git


def run(cwd: Path, hooks: str | None = None) -> int:
    try:
        common_dir = git(cwd, "rev-parse", "--git-common-dir")
    except OSError as error:  # git cannot even start
        print(f"prepush-ci install: cannot run git: {error}", file=sys.stderr)
        return 1
    if common_dir.returncode != 0:
        print(NO_REPOSITORY, file=sys.stderr)
        return 1
    root = _worktree_root(cwd)
    try:
        chosen = choose(hooks, _found(root))
    except Refusal as refusal:
        print(f"prepush-ci install: {refusal}", file=sys.stderr)
        return 1
    if chosen in MANAGERS:
        return _install_manager(root, chosen)
    common = _resolve(cwd, common_dir.stdout.strip())
    directory = common.joinpath(*HOOKS_DIRECTORY)
    ours = _hooks_path(cwd) == directory
    previous = _previous(cwd, common, directory)
    entries = sorted(e for e in _files(previous))
    forwarded = [name for name in entries if forwardable(name)]
    interpreter = Path(sys.executable).as_posix()
    desired = desired_files(interpreter, previous.as_posix(), forwarded)
    existing = {
        name: Existing(
            (directory / name).read_text(encoding="utf-8"),
            _executable(directory / name),
        )
        for name in _files(directory)
    }
    difference = changes(existing, desired)
    directory.mkdir(parents=True, exist_ok=True)
    for name in difference.write:
        path = directory / name
        path.write_text(desired[name], encoding="utf-8", newline="\n")
        path.chmod(0o755)
    for name in difference.remove:
        (directory / name).unlink()
    if not ours:
        git(cwd, "config", "--local", "core.hooksPath", directory.as_posix())
    word = outcome(
        was_installed=ours or bool(existing), changed=difference.any or not ours
    )
    chained = forwarded or [hook for hook in HOOKS if hook in entries]
    print(report(word, directory.as_posix(), previous.as_posix() if chained else None))
    if is_temporary(interpreter, os.environ, os.getcwd(), sys.platform == "win32"):
        print(TEMPORARY_WARNING, file=sys.stderr)
    return 0


def _worktree_root(cwd: Path) -> Path | None:
    """The top of the worktree; None in a bare repository."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    return _resolve(cwd, top.stdout.strip()) if top.returncode == 0 else None


def _found(root: Path | None) -> list[str]:
    """The managers whose files the worktree root holds."""
    if root is None:
        return []
    return [m for m in MANAGERS if any(_marker(root, name) for name in MARKERS[m])]


def _marker(root: Path, name: str) -> bool:
    """Whether the worktree root holds `name`: a directory for husky, a file for the others."""
    path = root / name
    return path.is_dir() if name == HUSKY_DIRECTORY else path.is_file()


def _install_manager(root: Path | None, manager: str) -> int:
    """Edit the files of `manager`; every file is read and edited before the first is written, so
    a refusal leaves them all as they were."""
    if root is None:
        print("prepush-ci install: there is no worktree here", file=sys.stderr)
        return 1
    present = [name for name in MARKERS[manager] if _marker(root, name)]
    if not present:
        print(f"prepush-ci install: {missing_message(manager)}", file=sys.stderr)
        return 1
    names = manager_files(manager, present)
    plan: dict[str, tuple[str | None, str]] = {}
    for name in names:
        path = root / name
        try:
            old = _read(path)
            plan[name] = (old, edit_file(manager, name, old))
        except (Refusal, OSError, UnicodeDecodeError) as problem:
            print(f"prepush-ci install: {name}: {problem}", file=sys.stderr)
            return 1
    for name, (old, new) in plan.items():
        if old != new:
            path = root / name
            path.write_text(new, encoding="utf-8", newline="")
            if old is None:
                path.chmod(0o755)  # a hook file git runs
    was_installed = any(
        old is not None and holds_block(old) for old, _ in plan.values()
    )
    changed = any(old != new for old, new in plan.values())
    print(
        manager_report(
            outcome(was_installed=was_installed, changed=changed), manager, names
        )
    )
    return 0


def _read(path: Path) -> str | None:
    """The contents of the file, None when it does not exist; a directory is an error."""
    if not path.exists():
        return None
    with path.open(
        encoding="utf-8", newline=""
    ) as file:  # newline="": keep the line ends
        return file.read()


def _resolve(base: Path, text: str) -> Path:
    return (base / text).resolve()


def _files(directory: Path) -> list[str]:
    """The names of the regular files of `directory`; none when it does not exist."""
    if not directory.is_dir():
        return []
    return [entry.name for entry in directory.iterdir() if entry.is_file()]


def _executable(path: Path) -> bool:
    return os.access(
        path, os.X_OK
    )  # Windows has no bit: true for every file, so stable


def _hooks_path(cwd: Path) -> Path | None:
    """The effective `core.hooksPath` (any scope, `~` expanded, relative to the worktree root)."""
    configured = git(cwd, "config", "--type=path", "--get", "core.hooksPath")
    value = configured.stdout.strip()
    if configured.returncode != 0 or not value:
        return None
    root = git(cwd, "rev-parse", "--show-toplevel").stdout.strip()
    return _resolve(_resolve(cwd, root), value)


def _previous(cwd: Path, common: Path, ours: Path) -> Path:
    """The directory git would take hooks from without `install`; never `ours`: a rerun keeps
    the one recorded the first time."""
    path = _hooks_path(cwd)
    if path is None:
        return _resolve(
            cwd, git(cwd, "rev-parse", "--git-path", "hooks").stdout.strip()
        )
    if path != ours:
        return path
    recorded = ours / PREVIOUS_FILE
    if recorded.is_file():
        return Path(recorded.read_text(encoding="utf-8").strip())
    return common / "hooks"
