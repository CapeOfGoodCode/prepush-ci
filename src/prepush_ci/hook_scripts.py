"""Where git takes its hooks from and what the hook files there look like, for `doctor` and
`install`."""

import os
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.doctor_hooks import Script
from prepush_ci.git import answer, git


def hooks_path(cwd: Path, root: Path) -> tuple[str, Path] | None:
    """The effective `core.hooksPath` as configured and made absolute against the worktree root."""
    configured = git(cwd, "config", "--type=path", "--get", "core.hooksPath")
    value = answer(configured)
    if configured.returncode != 0 or not value:
        return None
    return value, (root / text_io.to_path(value)).resolve()


def git_hooks_directory(cwd: Path) -> Path:
    """The directory git takes hooks from; git applies `core.hooksPath` itself, from any directory
    of the worktree."""
    git_path = git(cwd, "rev-parse", "--git-path", "hooks").stdout.strip()
    return (cwd / text_io.to_path(git_path)).resolve()


def script(path: Path) -> Script:
    if not path.is_file():
        return Script(exists=False)
    try:
        text = text_io.read_text(path)
    except OSError:  # a hook that cannot be read is still a hook git runs
        text = ""
    return Script(exists=True, executable=os.access(path, os.X_OK), content=text)
