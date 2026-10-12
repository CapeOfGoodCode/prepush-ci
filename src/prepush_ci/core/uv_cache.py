"""Whether an interpreter lives in uv's cache, where `uv cache prune` deletes it."""

import ntpath
import posixpath
from collections.abc import Mapping
from types import ModuleType

TEMPORARY_WARNING = (
    "prepush-ci install: warning: this interpreter is temporary, it lies in uv's cache; "
    "the hooks stop working when uv cleans its cache. "
    "Run `uv tool install prepush-ci`, then `prepush-ci install`."
)


def _flavor(windows: bool) -> ModuleType:
    return ntpath if windows else posixpath


def _components(path: str, windows: bool) -> tuple[bool, ...] | tuple[object, ...]:
    """Whether the path is rooted, then its components, compared as written: normalized by
    text alone (never resolved), and case-insensitive on Windows."""
    flavor = _flavor(windows)
    text = flavor.normcase(flavor.normpath(path))
    separator = flavor.sep
    return (text.startswith(separator), *[p for p in text.split(separator) if p])


def inside(path: str, directory: str, windows: bool = False) -> bool:
    """Whether the components of `directory` are a prefix of those of `path`; a directory that
    merely shares a name prefix with a parent of `path` does not count."""
    wanted = _components(directory, windows)
    return _components(path, windows)[: len(wanted)] == wanted


def cache_directory(
    environ: Mapping[str, str], cwd: str, windows: bool = False
) -> str | None:
    """Where uv keeps its cache, found as uv does: `UV_CACHE_DIR` (relative to `cwd`), else
    `%LOCALAPPDATA%\\uv\\cache` on Windows, else `$XDG_CACHE_HOME/uv`, else `$HOME/.cache/uv`;
    None when none of the variables is set."""
    join = _flavor(windows).join
    if environ.get("UV_CACHE_DIR"):
        return str(join(cwd, environ["UV_CACHE_DIR"]))
    if windows:
        local = environ.get("LOCALAPPDATA")
        return str(join(cwd, local, "uv", "cache")) if local else None
    if environ.get("XDG_CACHE_HOME"):
        return str(join(cwd, environ["XDG_CACHE_HOME"], "uv"))
    if environ.get("HOME"):
        return str(join(cwd, environ["HOME"], ".cache", "uv"))
    return None


def is_temporary(
    interpreter: str, environ: Mapping[str, str], cwd: str, windows: bool = False
) -> bool:
    """Whether `interpreter` lies inside uv's cache directory."""
    directory = cache_directory(environ, cwd, windows)
    return directory is not None and inside(interpreter, directory, windows)
