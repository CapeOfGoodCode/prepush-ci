"""When a passing check may be remembered: the key of a result and the commit its ref points at."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from prepush_ci.core.config import REMOTE, Config

SHORT = 12
# 128 bits of the hash keep a ref file name short: Windows limits a path to 260 characters
LENGTH = 32
RESULTS = "refs/prepush-ci/results"
IDENTITY = ("prepush-ci", "prepush-ci@localhost")
SUBJECT = "prepush-ci: the check passed"
NAMES = "commit "
EXPIRES_AFTER = 30 * 24 * 60 * 60  # seconds
BATCH = 100  # refs per `git push` that deletes them, so the command line stays short on Windows


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


def pushes_to_origin(args: Sequence[str], env: Mapping[str, str]) -> bool:
    """Whether the push the hook checks goes to the remote named `origin`: git passes the name
    (or the url, for `git push <url>`) as the first argument, pre-commit passes none and sets
    `PRE_COMMIT_REMOTE_NAME`. A hook that is told neither (lefthook) does not know, which is no."""
    name = args[0] if args else env.get("PRE_COMMIT_REMOTE_NAME")
    return name == REMOTE


def expired_refs(listing: str, now: int) -> list[str]:
    """The refs older than 30 days at `now` (a Unix time), from the output of
    `git for-each-ref --format='%(refname) %(committerdate:unix)'`. A ref dated in the future or
    without a readable date is kept: the tool removes only what it can age."""
    expired: list[str] = []
    for line in listing.splitlines():
        ref, _, stamp = line.rpartition(" ")
        if ref and stamp.isdigit() and now - int(stamp) > EXPIRES_AFTER:
            expired.append(ref)
    return expired


def batches(refs: Sequence[str]) -> list[list[str]]:
    return [list(refs[start : start + BATCH]) for start in range(0, len(refs), BATCH)]


def message_skipped(tree: str, sha: str) -> str:
    return (
        f"prepush-ci: the check passed earlier on tree {tree[:SHORT]} "
        f"(commit {sha[:SHORT]}) with the same config, so it is not run again; the preflight ran"
    )


def message_skipped_from_origin(tree: str, sha: str) -> str:
    return (
        f"prepush-ci: {REMOTE} holds a result: the check passed earlier on tree {tree[:SHORT]} "
        f"(commit {sha[:SHORT]}) with the same config, so it is not run again; the preflight ran"
    )


def lists_ref(listing: str, ref: str) -> bool:
    """Whether `git ls-remote <remote> <ref>` printed `ref` itself: it also matches a longer ref
    that ends with the name."""
    return any(line.partition("\t")[2] == ref for line in listing.splitlines())


def message_not_asked(reason: str) -> str:
    return f"prepush-ci: {REMOTE} could not be asked for a result, so the check runs: {reason}"


def message_not_cached(reason: str) -> str:
    return f"prepush-ci: the pass could not be cached, so a retry runs the check again: {reason}"


def message_not_shared(reason: str) -> str:
    return (
        f"prepush-ci: the result was not shared through {REMOTE}, so another clone "
        f"runs the check again: {reason}"
    )


def message_not_cleaned(reason: str) -> str:
    return f"prepush-ci: old results could not be removed: {reason}"


def message_not_cleaned_from_origin(reason: str) -> str:
    return f"prepush-ci: old results could not be removed from {REMOTE}, so they stay until a later push: {reason}"
