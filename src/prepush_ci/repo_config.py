"""Find the repository's config on disk and load it (the I/O around `core.config_source`)."""

from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.config_source import PREPUSH_CI_FILE, PYPROJECT_FILE, load_config
from prepush_ci.git import git


def repository_root(cwd: Path) -> Path:
    """The root of the working tree that contains `cwd`."""
    result = git(cwd, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise ConfigError(["not inside a git working tree: no config to read"])
    return text_io.to_path(result.stdout.strip())


def load_repository_config(cwd: Path) -> Config:
    """Load the config of the working tree containing `cwd`, wherever `cwd` is inside it.

    A file that is not UTF-8 is a problem of that file; `pyproject.toml` is read only when the
    dedicated file is missing, as it is the only one parsed then."""
    root = repository_root(cwd)
    dedicated = _read(root, PREPUSH_CI_FILE)
    pyproject = None if dedicated is not None else _read(root, PYPROJECT_FILE)
    return load_config(dedicated, pyproject)


def _read(root: Path, name: str) -> str | None:
    try:
        return text_io.read_utf8(root / name, name)
    except FileNotFoundError:
        return None
    except text_io.NotUtf8 as error:
        raise ConfigError([str(error)]) from error
