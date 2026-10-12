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


SESSION_HOOK_FILE = ".claude/hooks/session-start.sh"
_SESSION_HOOK = r"""#!/bin/sh
# Written by `prepush-ci init`; yours to edit, `init` never overwrites it.
# Claude Code runs it when a session starts. It works only in Claude Code on the web
# (CLAUDE_CODE_REMOTE=true): it installs prepush-ci for good, installs the hooks and turns the
# trailer on for the whole session. Add what the repository needs to run its check (services,
# dependencies) at the end; activating a hook manager (pre-commit install, lefthook install,
# husky's prepare) belongs there too.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
if [ -z "${CLAUDE_ENV_FILE:-}" ]; then
  echo "prepush-ci: CLAUDE_ENV_FILE is not set, so the session would not see prepush-ci;" \
    "nothing done" >&2
  exit 0
fi
set -eu
uv tool install prepush-ci
bin=$(uv tool dir --bin)
PATH="$bin:$PATH"
export PATH
prepush-ci install@HOOKS@
add_once() {
  grep -qxF -- "$1" "$CLAUDE_ENV_FILE" 2>/dev/null && return 0
  # another hook may have left the file without a final newline
  [ -z "$(tail -c 1 "$CLAUDE_ENV_FILE" 2>/dev/null)" ] || echo >> "$CLAUDE_ENV_FILE"
  printf '%s\n' "$1" >> "$CLAUDE_ENV_FILE"
}
add_once "export PATH=\"$bin:\$PATH\""
add_once 'export PREPUSH_CI=full'
"""


def session_start_script(hooks: str | None) -> str:
    """The SessionStart hook skeleton; `install` gets `--hooks <hooks>` unless there is none."""
    flag = "" if hooks in (None, "none") else f" --hooks {hooks}"
    return _SESSION_HOOK.replace("@HOOKS@", flag)


SETTINGS_FILE = ".claude/settings.json"
SESSION_COMMAND = '"$CLAUDE_PROJECT_DIR"/.claude/hooks/session-start.sh'
_SCRIPT_NAME = "session-start.sh"


class SettingsError(Exception):
    """`.claude/settings.json` cannot be edited safely; the message names the file."""


def _names_the_script(group: object) -> bool:
    if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
        return False
    return any(
        isinstance(hook, dict)
        and isinstance(hook.get("command"), str)
        and _SCRIPT_NAME in hook["command"]
        for hook in group["hooks"]
    )


def register_session_hook(text: str | None) -> str:
    """The text of `.claude/settings.json` with the script registered as a SessionStart hook:
    `text` itself when a command already names it, else the JSON with one group added (every
    other setting kept, two-space indent). `text` is None when the file does not exist."""
    try:
        data = {} if text is None else json.loads(text)
    except json.JSONDecodeError as error:
        raise SettingsError(f"{SETTINGS_FILE} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise SettingsError(f"{SETTINGS_FILE} must hold a JSON object")
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SettingsError(f"{SETTINGS_FILE}: `hooks` must be an object")
    groups = hooks.setdefault("SessionStart", [])
    if not isinstance(groups, list):
        raise SettingsError(f"{SETTINGS_FILE}: `hooks.SessionStart` must be a list")
    if text is not None and any(_names_the_script(group) for group in groups):
        return text
    groups.append({"hooks": [{"type": "command", "command": SESSION_COMMAND}]})
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


CI_CHOICES = ("github", "gitlab", "generic", "none")
CI_FILES = {
    "github": "github-actions.yml",
    "gitlab": "gitlab-ci.yml",
    "generic": "gate.sh",
}  # the files of docs/ci/, packaged beside the code as ci_gates/


def detect_ci(*, workflows: bool, gitlab: bool) -> str:
    """The CI system whose gate to show: GitHub Actions when `.github/workflows/` holds a
    workflow, else GitLab CI when `.gitlab-ci.yml` exists, else the generic shell gate."""
    if workflows:
        return "github"
    return "gitlab" if gitlab else "generic"
