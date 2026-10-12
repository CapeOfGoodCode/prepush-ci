"""Turn the config table into a typed `Config`, or into every problem found in it."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_TRAILER_KEY = "Prepush-CI"
DEFAULT_TRAILER_VALUE = "full"
DEFAULT_BRANCH = "main"
REMOTE = "origin"

_TRAILER_TOKEN = re.compile(r"[A-Za-z0-9-]+")
_KEYS = (
    "check",
    "preflight",
    "require_env",
    "require_up_to_date",
    "default_branch",
    "trailer",
    "legacy_keys",
    "cache",
)
_TRAILER_KEYS = ("key", "value")


@dataclass(frozen=True)
class Trailer:
    key: str
    value: str

    def line(self) -> str:
        return f"{self.key}: {self.value}"


@dataclass(frozen=True)
class Config:
    check: str
    preflight: str | None
    require_env: tuple[str, ...]
    require_up_to_date: str | None
    default_branch: str
    trailer: Trailer
    legacy_keys: tuple[str, ...]
    cache: bool


class ConfigError(Exception):
    """The config is missing or invalid; `problems` has one line per problem, each naming its key."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


def is_trailer_token(text: str) -> bool:
    return _TRAILER_TOKEN.fullmatch(text) is not None


def is_trailer_value(text: str) -> bool:
    return bool(text) and text == text.strip() and "\n" not in text and "\r" not in text


def parse_config(table: Mapping[str, Any]) -> Config:
    problems: list[str] = []

    def string(key: str, value: Any, *, default: str | None = None) -> str | None:
        if value is None:
            return default
        if not isinstance(value, str):
            problems.append(f"`{key}` must be a string")
            return default
        if not value:
            problems.append(f"`{key}` must not be empty")
            return default
        return value

    def strings(key: str, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            problems.append(f"`{key}` must be a list of strings")
            return ()
        return tuple(value)

    problems.extend(
        f"unknown key `{key}` (known keys: {', '.join(_KEYS)})"
        for key in table
        if key not in _KEYS
    )

    check = string("check", table.get("check"))
    if "check" not in table:
        problems.append("`check` is required: the command that runs your full CI check")
    preflight = string("preflight", table.get("preflight"))
    default_branch = string(
        "default_branch", table.get("default_branch"), default=DEFAULT_BRANCH
    )
    require_env = strings("require_env", table.get("require_env"))
    legacy_keys = strings("legacy_keys", table.get("legacy_keys"))
    problems.extend(
        f"`legacy_keys` contains {key!r}, which is not a valid trailer key "
        "(letters, digits and hyphens only)"
        for key in legacy_keys
        if not is_trailer_token(key)
    )

    up_to_date = table.get("require_up_to_date")
    if up_to_date is None or up_to_date is True:
        require_up_to_date = f"{REMOTE}/{default_branch}"
    elif up_to_date is False:
        require_up_to_date = None
    elif isinstance(up_to_date, str):
        require_up_to_date = string("require_up_to_date", up_to_date)
    else:
        problems.append("`require_up_to_date` must be a string or a boolean")
        require_up_to_date = None

    trailer = _parse_trailer(table.get("trailer"), problems)

    cache = table.get("cache", True)
    if not isinstance(cache, bool):
        problems.append("`cache` must be a boolean")

    if problems or check is None or default_branch is None:
        raise ConfigError(problems)
    return Config(
        check=check,
        preflight=preflight,
        require_env=require_env,
        require_up_to_date=require_up_to_date,
        default_branch=default_branch,
        trailer=trailer,
        legacy_keys=legacy_keys,
        cache=bool(cache),
    )


def _parse_trailer(table: Any, problems: list[str]) -> Trailer:
    default = Trailer(DEFAULT_TRAILER_KEY, DEFAULT_TRAILER_VALUE)
    if table is None:
        return default
    if not isinstance(table, dict):
        problems.append("`trailer` must be a table with `key` and `value`")
        return default
    problems.extend(
        f"unknown key `trailer.{key}` (known keys: {', '.join(_TRAILER_KEYS)})"
        for key in table
        if key not in _TRAILER_KEYS
    )
    key = table.get("key", default.key)
    value = table.get("value", default.value)
    if not isinstance(key, str):
        problems.append("`trailer.key` must be a string")
    elif not is_trailer_token(key):
        problems.append(
            f"`trailer.key` is not a valid trailer key: {key!r} "
            "(letters, digits and hyphens only)"
        )
    if not isinstance(value, str):
        problems.append("`trailer.value` must be a string")
    elif not is_trailer_value(value):
        problems.append(
            f"`trailer.value` must be a non-empty single line without leading or trailing whitespace: {value!r}"
        )
    return Trailer(
        key if isinstance(key, str) else default.key,
        value if isinstance(value, str) else default.value,
    )
