"""When a passing check may be remembered: the key of a result and the commit its ref points at."""

import hashlib
import json
from dataclasses import dataclass

from prepush_ci.core.config import Config

SHORT = 12
# 128 bits of the hash keep a ref file name short: Windows limits a path to 260 characters
LENGTH = 32
RESULTS = "refs/prepush-ci/results"
IDENTITY = ("prepush-ci", "prepush-ci@localhost")
SUBJECT = "prepush-ci: the check passed"
NAMES = "commit "


@dataclass(frozen=True)
class Head:
    """The commit a check runs on and its tree, read before the check can move `HEAD`."""

    sha: str
    tree: str


@dataclass(frozen=True)
class Key:
    """What a result is true of: a tree and everything else that decides the result."""

    tree: str
    config: str


def fingerprint(config: Config, preflight_output: str) -> str:
    """A hash of `check`, `preflight`, `require_env`, `require_up_to_date` and the standard output
    of the preflight command (the tool versions it reports); the other keys do not change what a
    pass means. JSON keeps values that run together in a join apart."""
    values = [
        config.check,
        config.preflight,
        list(config.require_env),
        config.require_up_to_date,
        preflight_output,
    ]
    return hashlib.sha256(json.dumps(values).encode("utf-8")).hexdigest()[:LENGTH]


def result_ref(key: Key) -> str:
    """The ref of the result of `key`: both parts are hex, so the name is safe on any system."""
    return f"{RESULTS}/{key.tree}-{key.config}"


def result_message(sha: str) -> list[str]:
    """The paragraphs of the message of the commit a result ref points at: they name the commit
    that was checked."""
    return [SUBJECT, f"{NAMES}{sha}"]


def passed_commit(log: str, key: Key) -> str | None:
    """The commit a result ref names, read from `git log -1 --format=%T%n%b` of the ref; None
    when the ref points at a commit of another tree or its message names no commit."""
    tree, _, body = log.partition("\n")
    body = body.strip()
    if tree != key.tree or not body.startswith(NAMES):
        return None
    return body.removeprefix(NAMES)


def message_skipped(tree: str, sha: str) -> str:
    return (
        f"prepush-ci: the check passed earlier on tree {tree[:SHORT]} "
        f"(commit {sha[:SHORT]}) with the same config, so it is not run again; the preflight ran"
    )


def message_not_cached(reason: str) -> str:
    return f"prepush-ci: the pass could not be cached, so a retry runs the check again: {reason}"
