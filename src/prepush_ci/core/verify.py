"""Decisions of `prepush-ci verify`: may CI skip a commit because the full check provably ran on it."""

from collections.abc import Sequence
from dataclasses import dataclass

from prepush_ci.core.config import Config
from prepush_ci.core.pre_push import demand_keys, matching_trailer

# Identities that servers record as committer of the commits they write (GitHub's merge, squash,
# rebase and web-edit commits; GitLab's web commits when it signs). Whole address, lower-cased.
SERVER_EMAILS = frozenset({"noreply@github.com", "noreply@gitlab.com"})


@dataclass(frozen=True)
class Verdict:
    verified: bool
    reason: str


def usage_problem(args: Sequence[str]) -> str | None:
    """What is wrong with the command line, or None when it is exactly one non-empty sha."""
    if not args:
        return "the sha is missing: run `prepush-ci verify <sha>`"
    if len(args) > 1:
        return f"expected one sha, got {len(args)} arguments: run `prepush-ci verify <sha>`"
    if not args[0]:
        return "the sha is empty: is the variable that holds it unset?"
    return None


def render(verdict: Verdict, sha: str | None) -> str:
    """The one line `verify` prints; `sha` is None when the command line named none.

    The reason can hold text from the commit (a config key) or from git, and the sha is the
    argument as given, so both are escaped when they hold a control character: a newline
    must not make a second line, least of all one that starts with `verified:`.
    """
    prefix = "verified:" if verdict.verified else "not verified:"
    reason = one_line(verdict.reason)
    if sha is None:
        return f"{prefix} {reason}"
    return f"{prefix} {one_line(sha)} {reason}"


def one_line(text: str) -> str:
    return text if text.isprintable() else text.encode("unicode_escape").decode("ascii")


def server_made(committer_email: str) -> Verdict | None:
    """A refusal when a server wrote the commit, so no hook ran on it; None for any other committer.

    `committer_email` is the address as recorded in the commit (`%ce`), never `.mailmap`-mapped.
    """
    if committer_email.lower() in SERVER_EMAILS:
        return Verdict(
            False,
            f"made by a server (committer {committer_email}), so the check did not run on it",
        )
    return None


def trailer_verdict(trailers: str, config: Config) -> Verdict:
    """Verified when a trailer has the configured key or a legacy key (the rule of the pre-push hook)."""
    keys = demand_keys(config)
    found = matching_trailer(trailers, keys)
    if found is None:
        return Verdict(False, f"no trailer (looked for: {', '.join(sorted(keys))})")
    return Verdict(True, f"carries the trailer `{found}`")


def no_config() -> Verdict:
    return Verdict(
        False, "the commit has no config (.prepush-ci.toml or [tool.prepush-ci])"
    )


def invalid_config(problems: Sequence[str]) -> Verdict:
    return Verdict(
        False, "the config committed in it is invalid: " + "; ".join(problems)
    )


def unreadable(message: str) -> Verdict:
    return Verdict(False, message)


def unresolved(argument: str, shallow: bool) -> Verdict:
    """The refusal for an argument that is no commit here, saying what to fetch."""
    if argument.startswith("-"):
        return Verdict(
            False,
            f"{argument} is an option, not a sha: run `prepush-ci verify <sha>`",
        )
    if shallow:
        return Verdict(
            False,
            f"{argument} is not a commit of this shallow clone: run `git fetch --unshallow` "
            "(with GitHub Actions' checkout, set `fetch-depth: 0`)",
        )
    return Verdict(
        False,
        f"{argument} is not a commit of this repository: fetch it with "
        f"`git fetch origin {argument}`, or check the sha",
    )
