"""`prepush-ci app ruleset`: make one actor the only one that may move the default branch, by
creating the ruleset `doctor --ruleset` checks. The token is the user's own; `app setup` never
sees one."""

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from prepush_ci import github_api
from prepush_ci.core import report, ruleset
from prepush_ci.core.report import ReportError, Repository
from prepush_ci.core.ruleset import Actor
from prepush_ci.git import GitError, answer, git

# What a 403 means for rulesets: the plan does not have them, or the token may not make them.
FORBIDDEN = (
    "a private repository needs a paid plan for rulesets, and the token needs "
    "administration rights on the repository"
)


@dataclass(frozen=True)
class Access:
    """Where the requests go and the token that is sent with them."""

    api_url: str
    repository: Repository
    token: str


def access(cwd: Path, env: Mapping[str, str]) -> Access:
    """The repository as `report` names it (`origin`, then `GITHUB_REPOSITORY`) and the token
    (`GITHUB_TOKEN`, then `GH_TOKEN`); a refusal when either is missing, before any request."""
    result = git(cwd, "remote", "get-url", "origin")
    where = report.target(answer(result) if result.returncode == 0 else None, env)
    token = report.value(env, "GITHUB_TOKEN") or report.value(env, "GH_TOKEN")
    if token is None:
        raise ReportError(
            "no token: set GITHUB_TOKEN or GH_TOKEN to a token with administration rights "
            "on the repository (`GH_TOKEN=$(gh auth token)` gives the GitHub CLI's)"
        )
    return Access(where.api_url, where.repository, token)


def run(actor: Actor, env: Mapping[str, str], cwd: Path) -> int:
    """Return 0 when the ruleset was created, 1 when the command refused or failed; the result
    goes to standard output, the reason to standard error."""
    secrets: tuple[str, ...] = ()
    try:
        found = access(cwd, env)
        secrets = (found.token,)
        print(_create(actor, found))
        return 0
    except (ReportError, GitError, OSError) as error:
        reason = str(error)
        if getattr(error, "status", None) == 403:
            reason += f"; {FORBIDDEN}"
        print(f"prepush-ci: {report.redact(reason, secrets)}", file=sys.stderr)
        return 1


def _create(actor: Actor, found: Access) -> str:
    listing = github_api.list_rulesets(found.api_url, found.repository, found.token)
    if ruleset.listed_id(listing) is not None:
        raise ReportError(
            f"the ruleset `{ruleset.NAME}` exists already and is left as it is; delete it in "
            "the settings of the repository (Rules) and run the command again"
        )
    made = github_api.create_ruleset(
        found.api_url, found.repository, found.token, ruleset.body(actor)
    )
    try:
        new = ruleset.created(made)
    except ReportError as error:
        raise ReportError(
            "GitHub answered, but its answer is not what the API documents; check the "
            f"settings of the repository to see whether the ruleset `{ruleset.NAME}` exists"
        ) from error
    lines = [f"created the ruleset {ruleset.NAME} (id {new.ruleset_id})"]
    if new.address is not None:
        lines.append(f"its page: {new.address}")
    lines.append(f"bypass actor: {ruleset.describe(actor)}")
    lines.append("check it later with: prepush-ci doctor --ruleset")
    return "\n".join(lines)
