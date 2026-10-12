"""Find the repository's config on disk and load it (the I/O around `core.config_source`)."""

import subprocess
from pathlib import Path

from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.config_source import PREPUSH_CI_FILE, PYPROJECT_FILE, load_config


def repository_root(cwd: Path) -> Path:
    """The root of the working tree that contains `cwd`."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ConfigError(["not inside a git working tree: no config to read"])
    return Path(result.stdout.strip())


def load_repository_config(cwd: Path) -> Config:
    """Load the config of the working tree containing `cwd`, wherever `cwd` is inside it."""
    root = repository_root(cwd)
    return load_config(_read(root / PREPUSH_CI_FILE), _read(root / PYPROJECT_FILE))


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
