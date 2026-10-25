"""`prepush-ci land`: a comment of the pull request as the second source of a pass (the I/O around
`core.land`, which decides what a comment says)."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from prepush_ci import github_api
from prepush_ci.core import land, report
from prepush_ci.core.config import REMOTE, Config
from prepush_ci.core.report import ReportError
from prepush_ci.git import answer, git

BUDGET_SECONDS = 60.0


@dataclass(frozen=True)
class Search:
    """Whether a comment is a pass; when not, why GitHub could not be asked (None: it was asked)."""

    found: bool
    why_not_asked: str | None = None


def search(
    number: int, config: Config, tree: str, env: Mapping[str, str], cwd: Path
) -> Search:
    """Look through the comments of pull request `number` for one that states a pass for `tree` and
    the check and preflight of `config`, written by someone with write access."""
    token = report.value(env, "GITHUB_TOKEN") or report.value(env, "GH_TOKEN")
    if token is None:
        return Search(
            False,
            "no token: set GITHUB_TOKEN (or GH_TOKEN) to read the comments of the pull request",
        )
    problems: list[str] = []
    try:
        origin = git(cwd, "remote", "get-url", REMOTE)
        target = report.target(answer(origin) if origin.returncode == 0 else None, env)
        client = github_api.PullRequestClient(
            target.api_url, target.repository, token, BUDGET_SECONDS
        )
        found = _has_written_pass(client, number, tree, config, problems)
    except ReportError as error:  # no repository, or the comments could not be read
        problems.append(str(error))
        found = False
    if found:
        return Search(True)
    # the token is never printed, whatever the API echoes back
    return Search(False, _said(problems[0], token) if problems else None)


def _said(problem: str, token: str) -> str:
    return report.redact(" ".join(problem.split()), (token,))


def _has_written_pass(
    client: github_api.PullRequestClient,
    number: int,
    tree: str,
    config: Config,
    problems: list[str],
) -> bool:
    """The first comment, over all pages, that states a pass for the tree and is by a writer. The
    permission of an author is asked for once, and only for a comment that matches already; an App
    is never asked about."""
    writers: dict[str, bool] = {}
    page = 1
    while True:
        comments = client.authored_comments(number, page)
        for comment in comments:
            if comment.bot or comment.login is None:
                continue
            if not (
                land.states_a_pass(comment.body)
                and land.names_this(comment.body, tree, config.check, config.preflight)
            ):
                continue
            if comment.login not in writers:
                writers[comment.login] = _writes(client, comment.login, problems)
            if writers[comment.login]:
                return True
        if len(comments) < github_api.PER_PAGE:
            return False
        page += 1


def _writes(
    client: github_api.PullRequestClient, login: str, problems: list[str]
) -> bool:
    """Whether the author has write access; a permission that cannot be read is no."""
    try:
        return land.may_write(client.permission(login))
    except github_api.ApiError as error:
        problems.append(str(error))
        return False
