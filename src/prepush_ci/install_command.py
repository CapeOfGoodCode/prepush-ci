"""`prepush-ci install`: point git at hook scripts that run this tool."""

import os
import sys
from pathlib import Path

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
from prepush_ci.git import git


def run(cwd: Path) -> int:
    try:
        common_dir = git(cwd, "rev-parse", "--git-common-dir")
    except OSError as error:  # git cannot even start
        print(f"prepush-ci install: cannot run git: {error}", file=sys.stderr)
        return 1
    if common_dir.returncode != 0:
        print(NO_REPOSITORY, file=sys.stderr)
        return 1
    common = _resolve(cwd, common_dir.stdout.strip())
    directory = common.joinpath(*HOOKS_DIRECTORY)
    ours = _hooks_path(cwd) == directory
    previous = _previous(cwd, common, directory)
    entries = sorted(e for e in _files(previous))
    forwarded = [name for name in entries if forwardable(name)]
    desired = desired_files(
        Path(sys.executable).as_posix(), previous.as_posix(), forwarded
    )
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
    return 0


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
