"""`prepush-ci land`: a comment of the pull request as the second source of a pass (the I/O around
`core.land`, which decides what a comment says)."""

import contextlib
import sys
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
    """The first comment, over all pages, that states a pass for the tree and is by a writer; the
    walk ends there. Each author who does not count is named once on standard error."""
    walk = _Walk(client, problems)
    page = 1
    while True:
        comments = client.authored_comments(number, page)
        for comment in comments:
            if not (
                land.states_a_pass(comment.body)
                and land.names_this(comment.body, tree, config.check, config.preflight)
            ):
                continue
            if walk.counts(comment):
                return True
        if len(comments) < github_api.PER_PAGE:
            return False
        page += 1


class _Walk:
    """What the walk over the matching comments has asked and said so far: the token's user and
    whether it may push once per run, the permission once per author, a line once per author."""

    def __init__(
        self, client: github_api.PullRequestClient, problems: list[str]
    ) -> None:
        self._client = client
        self._problems = problems
        self._named: set[str] = set()  # authors whose ignored pass is already said
        self._unknown_named = False
        self._me_asked = False
        self._me: str | None = None

    def counts(self, comment: github_api.Comment) -> bool:
        """Whether the matching comment is by a writer; when not, name its author once."""
        login = comment.login
        if login is None or not land.is_plain_login(login):
            if not self._unknown_named:
                self._unknown_named = True
                _say(land.IGNORED_UNKNOWN)
            return False
        if login in self._named:
            return False  # not a writer, as asked before
        if comment.bot:
            self._named.add(login)
            _say(land.ignored_app(login))
            return False
        if login == self._token_user() and self._token_can_push():
            return True
        permission = self._permission(login)
        if permission is not None and land.may_write(permission):
            return True
        self._named.add(login)
        _say(land.ignored_for_permission(login, permission))
        return False

    def _token_user(self) -> str | None:
        """The login of the token's user, asked once; None when it cannot be read."""
        if not self._me_asked:
            self._me_asked = True
            # a shortcut only: an error leaves the permission request to decide, with no reason added
            with contextlib.suppress(github_api.ApiError):
                self._me = self._client.user()
        return self._me

    def _token_can_push(self) -> bool:
        """Whether the repository lets the token push; an error is no. Asked once: an author who
        does not count is named and skipped from then on, so this runs once for the token's user."""
        try:
            return self._client.can_push()
        except github_api.ApiError:
            return False

    def _permission(self, login: str) -> str | None:
        """The permission of the author; None when it cannot be read, with the reason noted."""
        try:
            return self._client.permission(login)
        except github_api.ApiError as error:
            self._problems.append(str(error))
            return None


def _say(line: str) -> None:
    print(line, file=sys.stderr)
