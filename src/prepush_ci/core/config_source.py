"""Pick the config source in use and parse only that one."""

import tomllib
from typing import Any

from prepush_ci.core.config import Config, ConfigError, parse_config

PREPUSH_CI_FILE = ".prepush-ci.toml"
PYPROJECT_FILE = "pyproject.toml"
PYPROJECT_TABLE = "[tool.prepush-ci]"

_MISSING = (
    f"no config found: create `{PREPUSH_CI_FILE}` at the repository root "
    f"or add a `{PYPROJECT_TABLE}` table to `{PYPROJECT_FILE}`"
)


class ConfigMissing(ConfigError):
    """There is no config at all (as opposed to an invalid one)."""


def load_config(prepush_ci_toml: str | None, pyproject_toml: str | None) -> Config:
    """Parse the config from the text of `.prepush-ci.toml`, else of `pyproject.toml`.

    Each argument is the text of the file, or None when the file does not exist. The
    dedicated file wins and the other one is not even parsed.
    """
    if prepush_ci_toml is not None:
        return _parse(_parse_toml(prepush_ci_toml, PREPUSH_CI_FILE), PREPUSH_CI_FILE)
    if pyproject_toml is None:
        raise ConfigMissing([_MISSING])
    data = _parse_toml(pyproject_toml, PYPROJECT_FILE)
    tool = data.get("tool")
    ours = tool.get("prepush-ci") if isinstance(tool, dict) else None
    if ours is None:
        raise ConfigMissing([_MISSING])
    if not isinstance(ours, dict):
        raise ConfigError(
            [
                f"{PYPROJECT_FILE}: `{PYPROJECT_TABLE}` must be a table, not a single value"
            ]
        )
    return _parse(ours, f"{PYPROJECT_FILE} {PYPROJECT_TABLE}")


def _parse_toml(text: str, name: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError([f"{name} is not valid TOML: {error}"]) from error


def _parse(table: dict[str, Any], source: str) -> Config:
    try:
        return parse_config(table)
    except ConfigError as error:
        raise ConfigError(
            [f"{source}: {problem}" for problem in error.problems]
        ) from error
