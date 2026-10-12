"""`prepush-ci install`: point git at hook scripts that run this tool."""

import sys
from pathlib import Path

from prepush_ci.core.install import HOOKS_DIRECTORY, desired_files
from prepush_ci.git import git


def run(cwd: Path) -> int:
    common = git(cwd, "rev-parse", "--git-common-dir").stdout.strip()
    directory = (cwd / common).resolve().joinpath(*HOOKS_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in desired_files(Path(sys.executable).as_posix()).items():
        path = directory / name
        path.write_text(content, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    git(cwd, "config", "--local", "core.hooksPath", directory.as_posix())
    print(f"installed: {directory.as_posix()}")
    return 0
