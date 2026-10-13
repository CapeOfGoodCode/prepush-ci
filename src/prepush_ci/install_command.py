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
    native_hooks_refusal,
    outcome,
    report,
)
from prepush_ci.core.uv_cache import TEMPORARY_WARNING, is_temporary
from prepush_ci.git import git


class Unreadable(Exception):
    """A file or directory `install` has to read cannot be read; the message names it and why."""

    def __init__(self, path: Path, error: Exception) -> None:
        reason = str(error)
        if isinstance(error, UnicodeDecodeError):
            reason = "it is not valid UTF-8"
        elif isinstance(error, OSError) and error.strerror:
            reason = error.strerror
        super().__init__(f"cannot read {path.as_posix()}: {reason}")


HOOKS_PATH_REFUSERS = ("pre-commit", "lefthook")  # husky sets core.hooksPath itself


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
        return _install_manager(cwd, root, chosen)
    common = _resolve(cwd, common_dir.stdout.strip())
    directory = common.joinpath(*HOOKS_DIRECTORY)
    ours = _hooks_path(cwd) == directory
    try:
        previous = _previous(cwd, common, directory)
        entries = _listing(previous)
    except Unreadable as unreadable:
        print(f"prepush-ci install: {unreadable}", file=sys.stderr)
        return 1
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
    windows = sys.platform == "win32"
    if is_temporary(interpreter, os.environ, os.getcwd(), windows, os.path.realpath):
        print(TEMPORARY_WARNING, file=sys.stderr)
    return 0


def _worktree_root(cwd: Path) -> Path | None:
    """The top of the worktree; None in a bare repository."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    return _resolve(cwd, top.stdout.strip()) if top.returncode == 0 else None


def _found(root: Path | None) -> list[str]:
    """The managers whose files the worktree root holds."""
    return list(found_files(root))


def found_files(root: Path | None) -> dict[str, str]:
    """For each manager whose files the worktree root holds, the first of them that exists."""
    if root is None:
        return {}
    found: dict[str, str] = {}
    for manager in MANAGERS:
        present = [name for name in MARKERS[manager] if _marker(root, name)]
        if present:
            found[manager] = present[0]
    return found


def previous_pre_push(cwd: Path) -> Path | None:
    """The `pre-push` hook `install` would chain to, if one is there to run."""
    common = _resolve(cwd, git(cwd, "rev-parse", "--git-common-dir").stdout.strip())
    directory = common.joinpath(*HOOKS_DIRECTORY)
    hook = _previous(cwd, common, directory) / "pre-push"
    return hook if hook.is_file() else None


def _marker(root: Path, name: str) -> bool:
    """Whether the worktree root holds `name`: a directory for husky, a file for the others."""
    path = root / name
    return path.is_dir() if name == HUSKY_DIRECTORY else path.is_file()


def _install_manager(cwd: Path, root: Path | None, manager: str) -> int:
    """Edit the files of `manager`; every file is read and edited before the first is written, so
    a refusal leaves them all as they were."""
    if root is None:
        print("prepush-ci install: there is no worktree here", file=sys.stderr)
        return 1
    if manager in HOOKS_PATH_REFUSERS and _holds_hooks_path(cwd, root):
        print(
            f"prepush-ci install: {native_hooks_refusal(manager, _lost_hooks(cwd, root))}",
            file=sys.stderr,
        )
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
    attempted: list[tuple[str, str | None]] = []
    for name, (old, new) in plan.items():
        if old != new:
            path = root / name
            attempted.append(
                (name, old)
            )  # a refused write may still have cut the file short
            try:
                path.write_text(new, encoding="utf-8", newline="")
                if old is None:
                    path.chmod(0o755)  # a hook file git runs
            except OSError as problem:
                stuck = _put_back(root, attempted)
                reason = problem.strerror or str(problem)
                print(f"prepush-ci install: {name}: {reason}", file=sys.stderr)
                for left in stuck:  # pragma: no cover (no scenario: see design.md)
                    print(
                        f"prepush-ci install: could not put back {left}",
                        file=sys.stderr,
                    )
                return 1
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


def _put_back(root: Path, attempted: list[tuple[str, str | None]]) -> list[str]:
    """Undo the writes tried so far: restore the previous contents, remove a file the run created.
    A file that already holds what it held before is left alone (a refused write changes
    nothing). Best effort; returns the names of the files that could not be put back."""
    stuck: list[str] = []
    for name, old in reversed(attempted):
        path = root / name
        try:
            if _read(path) == old:
                continue
            if old is None:
                path.unlink()
            else:
                path.write_text(old, encoding="utf-8", newline="")
        except (
            OSError,
            UnicodeDecodeError,
        ):  # pragma: no cover (no scenario: see design.md)
            stuck.append(name)
    return stuck


def _native_directory(cwd: Path) -> Path:
    common = _resolve(cwd, git(cwd, "rev-parse", "--git-common-dir").stdout.strip())
    return common.joinpath(*HOOKS_DIRECTORY)


def _holds_hooks_path(cwd: Path, root: Path) -> bool:
    """Whether the local `core.hooksPath` is the native hooks directory: the only value the
    command the refusal names removes."""
    local = git(cwd, "config", "--local", "--type=path", "--get", "core.hooksPath")
    value = local.stdout.strip()
    return (
        local.returncode == 0
        and bool(value)
        and _resolve(root, value) == _native_directory(cwd)
    )


def _lost_hooks(cwd: Path, root: Path) -> str | None:
    """The previous hooks directory, when it holds a hook and git stops using it once the local
    `core.hooksPath` is gone; None when that cannot be known (the record or the directory cannot
    be read), so that the refusal still says how to unblock the install."""
    recorded = _native_directory(cwd) / PREVIOUS_FILE
    try:
        if not recorded.is_file():
            return None
        previous = Path(recorded.read_text(encoding="utf-8").strip()).resolve()
        if not any(not name.endswith(".sample") for name in _files(previous)):
            return None
    except (OSError, ValueError):  # UnicodeDecodeError is a ValueError
        return None
    return None if previous == _hooks_without_local(cwd, root) else previous.as_posix()


def _hooks_without_local(cwd: Path, root: Path) -> Path:
    """The directory git takes hooks from when the local `core.hooksPath` is gone."""
    scoped = git(
        cwd, "config", "--show-scope", "--type=path", "--get-all", "core.hooksPath"
    )
    others = [
        line.split("\t", 1)[1]
        for line in scoped.stdout.splitlines()
        if not line.startswith("local\t")
    ]
    if others:
        return _resolve(root, others[-1])
    return (
        _resolve(cwd, git(cwd, "rev-parse", "--git-common-dir").stdout.strip())
        / "hooks"
    )


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


def _listing(directory: Path) -> list[str]:
    """The sorted names of the regular files of `directory`; unreadable is an error."""
    try:
        return sorted(_files(directory))
    except OSError as error:
        raise Unreadable(directory, error) from error


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
    try:
        if recorded.exists():  # a directory fails to be read: the record is unreadable
            return Path(recorded.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as error:  # UnicodeDecodeError is a ValueError
        raise Unreadable(recorded, error) from error
    return common / "hooks"
