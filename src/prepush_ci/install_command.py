"""`prepush-ci install`: point git at hook scripts that run this tool."""

import sys
from pathlib import Path

from prepush_ci.core.install import (
    HOOKS_DIRECTORY,
    PREVIOUS_FILE,
    desired_files,
    forwardable,
)
from prepush_ci.git import git


def run(cwd: Path) -> int:
    common = _resolve(cwd, git(cwd, "rev-parse", "--git-common-dir").stdout.strip())
    directory = common.joinpath(*HOOKS_DIRECTORY)
    previous = _previous(cwd, common, directory)
    forwarded = sorted(
        entry.name
        for entry in (previous.iterdir() if previous.is_dir() else ())
        if entry.is_file() and forwardable(entry.name)
    )
    directory.mkdir(parents=True, exist_ok=True)
    files = desired_files(
        Path(sys.executable).as_posix(), previous.as_posix(), forwarded
    )
    for name, content in files.items():
        path = directory / name
        path.write_text(content, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    git(cwd, "config", "--local", "core.hooksPath", directory.as_posix())
    print(f"installed: {directory.as_posix()}")
    return 0


def _resolve(base: Path, text: str) -> Path:
    return (base / text).resolve()


def _previous(cwd: Path, common: Path, ours: Path) -> Path:
    """The directory git would take hooks from without `install`; never `ours`: a rerun keeps
    the one recorded the first time."""
    configured = git(cwd, "config", "--type=path", "--get", "core.hooksPath")
    value = configured.stdout.strip()
    if configured.returncode == 0 and value:
        root = git(cwd, "rev-parse", "--show-toplevel").stdout.strip()
        path = _resolve(_resolve(cwd, root), value)
        if path != ours:
            return path
        recorded = ours / PREVIOUS_FILE
        if recorded.is_file():
            return Path(recorded.read_text(encoding="utf-8").strip())
        return common / "hooks"
    return _resolve(cwd, git(cwd, "rev-parse", "--git-path", "hooks").stdout.strip())
