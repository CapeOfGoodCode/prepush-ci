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
# The pre-push hook runs under `sh`, and dash drops a variable whose name is not a shell identifier.
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_KEYS = (
    "check",
    "preflight",
    "require_env",
    "require_up_to_date",
    "default_branch",
    "trailer",
    "legacy_keys",
    "cache",
    "results",
)
_TRAILER_KEYS = ("key", "value")
_RESULTS_KEYS = ("junit", "coverage", "ruff", "mypy")
# a drive (`C:\x`) or a drive-relative path (`C:x`), which means something only on Windows
_DRIVE = re.compile(r"[A-Za-z]:")
# the git directory in every spelling a file system folds to it: another case, trailing dots and
# spaces (Windows), and its 8.3 short name
_GIT_DIRECTORY = ("git~1", ".git")


@dataclass(frozen=True)
class Trailer:
    key: str
    value: str

    def line(self) -> str:
        return f"{self.key}: {self.value}"


@dataclass(frozen=True)
class Results:
    """The files the check writes, as paths from the top of the worktree written with `/`."""

    junit: tuple[str, ...] = ()
    coverage: str | None = None
    ruff: str | None = None
    mypy: str | None = None


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
    results: Results | None = None


class ConfigError(Exception):
    """The config is missing or invalid; `problems` has one line per problem, each naming its key."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


def is_trailer_token(text: str) -> bool:
    return _TRAILER_TOKEN.fullmatch(text) is not None


def is_env_name(text: str) -> bool:
    """A name that the hook, `doctor` and `run` all see the same way: a shell identifier."""
    return _ENV_NAME.fullmatch(text) is not None


_BRANCH_PREFIXES = ("refs/remotes/origin/", "refs/heads/", "origin/")


def default_branch_problem(value: str) -> str | None:
    """Why `value` is not the name of a branch of `origin`, with the name to write when the rest of
    the value is one; None when it may be a branch name."""
    if not value.startswith(("refs/", "origin/")):
        return None
    problem = f"`default_branch` is {value!r}, which is not a branch name"
    for prefix in _BRANCH_PREFIXES:
        if value.startswith(prefix) and len(value) > len(prefix):
            return f'{problem}; use "{value[len(prefix) :]}"'
    return f"{problem} (a branch name is expected, such as `main`)"


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
    if default_branch is not None and (why := default_branch_problem(default_branch)):
        problems.append(why)
    require_env = strings("require_env", table.get("require_env"))
    problems.extend(
        f"`require_env` contains {name!r}, which is not a valid environment variable "
        "name (it must start with a letter or `_` and hold only letters, digits and `_`)"
        for name in require_env
        if not is_env_name(name)
    )
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

    results = _parse_results(table["results"], problems) if "results" in table else None

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
        results=results,
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


def _parse_results(table: Any, problems: list[str]) -> Results:
    if not isinstance(table, dict):
        problems.append("`results` must be a table of result files")
        return Results()
    problems.extend(
        f"unknown key `results.{key}` (known keys: {', '.join(_RESULTS_KEYS)})"
        for key in table
        if key not in _RESULTS_KEYS
    )
    junit = table.get("junit")
    if junit is not None and (
        not isinstance(junit, list) or not all(isinstance(v, str) for v in junit)
    ):
        problems.append("`results.junit` must be a list of strings")
        junit = None
    entries = [("junit", path) for path in junit or []]
    single: dict[str, str | None] = {}
    for key in ("coverage", "ruff", "mypy"):
        value = table.get(key)
        if value is not None and not isinstance(value, str):
            problems.append(f"`results.{key}` must be a string")
            value = None
        single[key] = value
        if value is not None:
            entries.append((key, value))
    for key, path in entries:
        if why := result_path_problem(path):
            problems.append(f"`results.{key}` is {path!r}, which {why}")
    return Results(junit=tuple(junit or ()), **single)


def result_path_problem(path: str) -> str | None:
    """Why `path` cannot name a result file (the tool deletes it before the check and reads it
    after), or None. The same on every operating system, so one config reads the same everywhere."""
    if not path:
        return "is empty"
    if "\\" in path or path.startswith("/") or _DRIVE.match(path):
        return (
            "is not a path from the top of the worktree written with `/` only "
            "(no backslash, no leading `/`, no drive)"
        )
    components = path.split("/")
    if ".." in components:
        return "leaves the worktree (a `..` component)"
    if any(c.rstrip(". ").lower() in _GIT_DIRECTORY for c in components):
        return "names the git directory"
    return None
