"""Decisions of `prepush-ci land`: where a head stands, how git's answers are read, what the line says."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from prepush_ci.core.report import Malformed
from prepush_ci.core.run_cache import SHORT
from prepush_ci.core.verify import one_line

_OBJECT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_SYMREF = "ref: refs/heads/"
_REFUSED = re.compile(r"!\t[^\t]*\t\[[^\]]*\] \((?P<reason>.*)\)\s*")


@dataclass(frozen=True)
class Answer:
    """The one line `land` prints: it landed (exit 0) or it did not (exit 1)."""

    landed: bool
    detail: str

    @property
    def line(self) -> str:
        """The line, kept one line: a character that does not print is escaped, so text from the
        remote or the commit can never make a second line, least of all one that starts `landed:`."""
        prefix = "landed:" if self.landed else "not landed:"
        return one_line(f"{prefix} {self.detail}")


class Position(Enum):
    """Where the head stands against the tip of the branch."""

    ON_BRANCH = "on the branch"  # the head is the tip or behind it: nothing to push
    ON_TOP = "on top of the tip"  # the tip is an ancestor of the head: a fast-forward
    MOVED = "the branch moved"  # the tip has commits the head lacks


def position(head_is_behind_tip: bool, tip_is_behind_head: bool) -> Position:
    """Where a head stands, from two ancestry questions: is the head the tip or an ancestor of it,
    is the tip an ancestor of the head. The first answer wins: a head that is already on the branch
    needs nothing, whatever the config says about being up to date."""
    if head_is_behind_tip:
        return Position.ON_BRANCH
    return Position.ON_TOP if tip_is_behind_head else Position.MOVED


def parse_number(text: str) -> int:
    """The number of a pull request: a positive integer."""
    try:
        number = int(text)
    except ValueError:
        raise Malformed(f"must be the number of a pull request, not {text!r}") from None
    if number < 1:
        raise Malformed(f"must be a positive number, not {text!r}")
    return number


def pull_ref(number: int) -> str:
    return f"refs/pull/{number}/head"


def default_branch(listing: str) -> str | None:
    """The branch `HEAD` points to, from `git ls-remote --symref <remote> HEAD`; None when the
    remote printed none (git prints nothing for a `HEAD` that names a branch the remote lacks)."""
    for line in listing.split("\n"):
        symref, _, name = line.partition("\t")
        if name == "HEAD" and symref.startswith(_SYMREF):
            return symref.removeprefix(_SYMREF)
    return None


def listed_commit(listing: str, ref: str) -> str | None:
    """The object `git ls-remote` lists for exactly `ref`; a longer ref that ends with the name is
    not it."""
    for line in listing.split("\n"):
        sha, _, name = line.partition("\t")
        if name == ref and _OBJECT.fullmatch(sha):
            return sha
    return None


def refusal_reason(push_output: str) -> str | None:
    """The text git shows in parentheses at the end of the `!` line of a refused ref in the output
    of `git push --porcelain` (`pre-receive hook declined`, `non-fast-forward`), which git does not
    translate; None when the output has no such line. A `remote:` line is the remote author's text
    and starts with `remote:`, so it is never read."""
    found: str | None = None
    for line in push_output.split("\n"):
        refused = _REFUSED.fullmatch(line)
        if refused:
            found = refused["reason"]
    return found


def landed(sha: str, branch: str) -> Answer:
    return Answer(True, f"{sha} on {branch}")


def already_on(sha: str, branch: str) -> Answer:
    return Answer(True, f"{sha} already on {branch}")


def refused(detail: str) -> Answer:
    return Answer(False, detail)


def not_in_repository(reason: str) -> Answer:
    return refused(f"not inside a git repository: {reason}")


def no_origin() -> Answer:
    return refused("the repository has no remote named origin to land on")


def origin_unreachable(reason: str) -> Answer:
    return refused(f"origin could not be asked: {reason}")


def no_pull_request(number: int) -> Answer:
    return refused(f"origin holds no pull request {number} ({pull_ref(number)})")


def no_default_branch() -> Answer:
    return refused(
        "origin names no default branch: its HEAD points to no branch it holds"
    )


def not_fetched(reason: str) -> Answer:
    return refused(
        f"the head and the branch could not be fetched from origin: {reason}"
    )


def branch_moved(branch: str) -> Answer:
    return refused(
        f"{branch} of origin has commits that the head does not contain: "
        f"rebase onto {branch} and push again"
    )


def cache_off() -> Answer:
    return refused(
        "the cache is off (cache = false in the config of the head), so no pass is recorded"
    )


def missing_variables(names: Sequence[str]) -> Answer:
    return refused(
        "the check needs these environment variables, which are unset or empty: "
        + ", ".join(names)
    )


def no_pass(tree: str) -> Answer:
    return refused(
        f"no pass was found for tree {tree[:SHORT]} in this clone or on origin"
    )


def preflight_failed(command: str, status: int) -> Answer:
    return refused(f"the preflight failed (exit {status}): {command}")


def push_refused(branch: str, reason: str | None) -> Answer:
    return refused(
        f"origin refused the push to {branch} ({reason or 'git gave no reason'}); "
        "a branch that a ruleset protects is moved by its bypass actors only"
    )
