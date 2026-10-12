"""When a passing check may be remembered: the key of a pass and the record that proves it."""

import hashlib
import json
from dataclasses import dataclass

from prepush_ci.core.config import Config

SHORT = 12


@dataclass(frozen=True)
class Key:
    """What a pass is true of: a commit, its tree and the config values that decide the result."""

    sha: str
    tree: str
    fingerprint: str


def fingerprint(config: Config) -> str:
    """A hash of `check`, `preflight`, `require_env` and `require_up_to_date`; the other keys do
    not change what a pass means. JSON keeps values that run together in a join apart."""
    values = [
        config.check,
        config.preflight,
        list(config.require_env),
        config.require_up_to_date,
    ]
    return hashlib.sha256(json.dumps(values).encode("utf-8")).hexdigest()


def pass_record(key: Key) -> str:
    """The text stored for a pass; only this exact text counts as one."""
    return f"{key.sha}\n{key.tree}\n{key.fingerprint}\n"


def is_pass_for(record: str | None, key: Key) -> bool:
    """A record that is missing, empty, truncated or made for another key is not a pass."""
    return record == pass_record(key)


def record_name(key: Key) -> str:
    """The file name of the record of `key`: a hash, so every character is safe on any system."""
    return hashlib.sha256(pass_record(key).encode("utf-8")).hexdigest()


def message_skipped(sha: str) -> str:
    return (
        f"prepush-ci: the check passed earlier on {sha[:SHORT]} (same commit, tree and config), "
        "so it is not run again; the preflight ran"
    )


def message_not_cached(reason: str) -> str:
    return f"prepush-ci: the pass could not be cached, so a retry runs the check again: {reason}"
