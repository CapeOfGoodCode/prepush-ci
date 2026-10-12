"""What `prepush-ci init` decides: the config text, the flags that disagree with a config, and
the closing words. Everything here is text in, text out; the command does the I/O."""

import json
import tomllib
from dataclasses import dataclass

from prepush_ci.core.config import REMOTE, Config, ConfigError, parse_config

NO_REPOSITORY = "prepush-ci init: there is no git repository with a working tree here"
NEED_CHECK = (
    "prepush-ci init: --check is required while there is no config: "
    "the command that runs your full CI check"
)


@dataclass(frozen=True)
class ConfigFlags:
    """The config values the user gave; None means the flag was not given."""

    check: str | None = None
    preflight: str | None = None
    require_env: tuple[str, ...] | None = None
    require_up_to_date: str | None = None
    default_branch: str | None = None


_SHORT_ESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def toml_string(value: str) -> str:
    """A TOML basic string: quote, backslash and control characters escaped, the rest as it is.

    JSON's `\\uXXXX` escape would write a character outside the basic plane as a surrogate
    pair, which TOML forbids, so the text is written out. A lone surrogate (an argument that
    was not valid UTF-8) has no TOML form: it raises `ValueError`.
    """
    parts = ['"']
    for char in value:
        code = ord(char)
        if char in _SHORT_ESCAPES:
            parts.append(_SHORT_ESCAPES[char])
        elif code < 0x20 or code == 0x7F:
            parts.append(f"\\u{code:04x}")
        elif 0xD800 <= code <= 0xDFFF:
            raise ValueError(f"{value!r} is not valid text (not UTF-8)")
        else:
            parts.append(char)
    parts.append('"')
    return "".join(parts)


def _up_to_date_value(text: str) -> str:
    return text if text in ("true", "false") else toml_string(text)


def config_text(flags: ConfigFlags) -> str:
    """The text of `.prepush-ci.toml` holding the keys that were given, `check` first."""
    lines: list[str] = []
    if flags.check is not None:
        lines.append(f"check = {toml_string(flags.check)}")
    if flags.preflight is not None:
        lines.append(f"preflight = {toml_string(flags.preflight)}")
    if flags.require_env is not None:
        names = ", ".join(toml_string(name) for name in flags.require_env)
        lines.append(f"require_env = [{names}]")
    if flags.require_up_to_date is not None:
        lines.append(
            f"require_up_to_date = {_up_to_date_value(flags.require_up_to_date)}"
        )
    if flags.default_branch is not None:
        lines.append(f"default_branch = {toml_string(flags.default_branch)}")
    return "".join(f"{line}\n" for line in lines)


def validate(text: str) -> Config:
    """The config the text loads as; a `ConfigError` names every key the config rejects."""
    return parse_config(tomllib.loads(text))


def resolved_up_to_date(value: str, default_branch: str) -> str | None:
    """The ref a `--require-up-to-date` value stands for; None when it is switched off."""
    if value == "false":
        return None
    if value == "true":
        return f"{REMOTE}/{default_branch}"
    return value


def disagreements(config: Config, flags: ConfigFlags) -> list[str]:
    """The keys of `config` whose value differs from the flag given for them."""
    wrong: list[str] = []
    if flags.check is not None and flags.check != config.check:
        wrong.append("check")
    if flags.preflight is not None and flags.preflight != config.preflight:
        wrong.append("preflight")
    if flags.require_env is not None and flags.require_env != config.require_env:
        wrong.append("require_env")
    if (
        flags.require_up_to_date is not None
        and resolved_up_to_date(flags.require_up_to_date, config.default_branch)
        != config.require_up_to_date
    ):
        wrong.append("require_up_to_date")
    if (
        flags.default_branch is not None
        and flags.default_branch != config.default_branch
    ):
        wrong.append("default_branch")
    return wrong


def disagreement_message(keys: list[str], source: str) -> str:
    names = ", ".join(f"`{key}`" for key in keys)
    return f"prepush-ci init: the flags differ from the config in {source} for {names}"


def problems_message(error: ConfigError) -> str:
    return "\n".join(f"prepush-ci init: {problem}" for problem in error.problems)


ALREADY_INSTALLED = "already installed"


def closing(changed: bool) -> str:
    """The last line of the output: `already set up` exactly when no file changed."""
    return "set up" if changed else "already set up"
