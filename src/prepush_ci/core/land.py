"""Decisions of `prepush-ci land`: where a head stands, how git's answers are read, what the line says."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from prepush_ci.core.report import CHECK_RUN_NAME, Malformed, code_span, row_line
from prepush_ci.core.run_cache import SHORT
from prepush_ci.core.verify import one_line

_OBJECT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_SYMREF = "ref: refs/heads/"
_REFUSED = re.compile(r"!\t[^\t]*\t\[[^\]]*\] \((?P<reason>.*)\)\s*")
MARKER = f"<!-- prepush-ci:{CHECK_RUN_NAME} -->"
_PASS_TITLE = re.compile(
    rf"### {re.escape(CHECK_RUN_NAME)}: (?:Passed|\d+ passed, 0 failed, \d+ skipped)"
)
FAILURES = "### Failures"
WRITERS = ("admin", "write")
READERS = ("read", "none")
PERMISSIONS = WRITERS + READERS  # the four values the API documents
_PLAIN_LOGIN = re.compile(r"[A-Za-z0-9_\[\]-]+")
IGNORED_UNKNOWN = "ignored a pass by an unknown author"


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
    CANNOT_TELL = (
        "a shallow clone cannot tell"  # the history that would answer is not here
    )


def position(
    head_is_behind_tip: bool, tip_is_behind_head: bool, shallow: bool = False
) -> Position:
    """Where a head stands, from two ancestry questions: is the head the tip or an ancestor of it,
    is the tip an ancestor of the head. The first answer wins: a head that is already on the branch
    needs nothing, whatever the config says about being up to date. Two noes in a shallow clone
    may only mean that the history which would say yes is missing: a yes is true in any clone."""
    if head_is_behind_tip:
        return Position.ON_BRANCH
    if tip_is_behind_head:
        return Position.ON_TOP
    return Position.CANNOT_TELL if shallow else Position.MOVED


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


def after_refusal(
    head: str,
    tip: str,
    now: str | None,
    branch: str,
    reason: str | None,
    head_is_behind_now: bool,
) -> Answer:
    """The answer once `origin` refused the push of `head`, which sat on top of `tip`: `now` is the
    tip it lists then (None for a branch it no longer lists), `head_is_behind_now` whether the head
    is that tip or an ancestor of it. A head on the branch by then is landed, whoever pushed it;
    otherwise a tip that changed is a moved branch and one that did not is the refusal."""
    if now is not None and head_is_behind_now:
        return already_on(head, branch)
    if now not in (None, tip):
        return branch_moved(branch)
    return push_refused(branch, reason)


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


def shallow_cannot_tell(branch: str) -> Answer:
    return refused(
        f"this clone is shallow, so it cannot tell whether {branch} of origin moved: "
        "run `git fetch --unshallow` (with GitHub Actions' checkout, set `fetch-depth: 0`)"
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


def no_pass(tree: str, why_not_asked: str | None = None) -> Answer:
    """No pass in the clone, on origin or in a comment; `why_not_asked` says why GitHub could not
    be asked for the comments, when that is so."""
    if why_not_asked is None:
        return refused(
            f"no pass was found for tree {tree[:SHORT]} in this clone, on origin "
            "or in a comment of the pull request"
        )
    return refused(
        f"no pass was found for tree {tree[:SHORT]} in this clone or on origin, "
        f"and GitHub could not be asked: {why_not_asked}"
    )


def preflight_failed(command: str, status: int) -> Answer:
    return refused(f"the preflight failed (exit {status}): {command}")


def push_refused(branch: str, reason: str | None) -> Answer:
    return refused(
        f"origin refused the push to {branch} ({reason or 'git gave no reason'}); "
        "a branch that a ruleset protects is moved by its bypass actors only"
    )


# --- A comment of the pull request as a pass ------------------------------------------------------


def _lines(body: str) -> list[str]:
    """The lines of a comment, line feed or carriage return and line feed alike."""
    return body.replace("\r\n", "\n").split("\n")


def states_a_pass(body: str) -> bool:
    """Whether a comment is the Markdown of `report` for the default check and says it passed: the
    marker is its first line, the title line its second, and it has no `### Failures` section."""
    lines = _lines(body)
    return (
        lines[0] == MARKER
        and len(lines) > 1
        and _PASS_TITLE.fullmatch(lines[1]) is not None
        and FAILURES not in lines
    )


def names_this(body: str, tree: str, check: str, preflight: str | None) -> bool:
    """Whether the table of a comment holds, cell for cell as `report` writes them, this tree and
    the `check` and `preflight` committed in the head. It names the preflight command, not what it
    printed."""
    rows = {
        row_line("Tree", code_span(tree)),
        row_line("Check", code_span(check)),
        row_line("Preflight", "none" if preflight is None else code_span(preflight)),
    }
    return rows <= set(_lines(body))


def may_write(permission: str) -> bool:
    """Whether the `permission` of a collaborator is one that can push."""
    return permission in WRITERS


def is_plain_login(login: str) -> bool:
    """Whether a login is one that can be printed and sent in a request path: a non-empty string of
    ASCII letters, digits, `-`, `_`, `[` and `]`. Any other is no login at all."""
    return _PLAIN_LOGIN.fullmatch(login) is not None


def ignored_app(login: str) -> str:
    """The line on standard error for a pass by a GitHub App."""
    return f"ignored a pass by {login}: a GitHub App"


def ignored_for_permission(login: str, permission: str | None) -> str:
    """The line on standard error for a pass by an author who is not a writer: `permission` is what
    GitHub said (`read` or `none`), None when it could not be read. A value the API does not document
    is never printed."""
    if permission in READERS:
        return (
            f"ignored a pass by {login}: permission {permission} is not admin or write"
        )
    return f"ignored a pass by {login}: its permission cannot be read"
