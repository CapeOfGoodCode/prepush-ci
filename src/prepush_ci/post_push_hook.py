"""`prepush-ci hook post-push`: after a push of a checked commit, put the result on its pull
request. Claude Code runs it after each command of the agent; it never fails the command."""

import contextlib
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from prepush_ci import github_api, report_command, text_io
from prepush_ci.core import report
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.post_push import (
    facts_block,
    find_comment,
    is_push,
    latest_ref,
    marker_of,
    parse_payload,
    results_pattern,
)
from prepush_ci.core.pre_push import demand_keys, demands_check
from prepush_ci.core.report import ReportError
from prepush_ci.git import GitError, answer, committed_config, git, trailers
from prepush_ci.pass_cache import current_head, dated_passes, pass_facts
from prepush_ci.repo_config import load_repository_config

BUDGET_SECONDS = 15.0


def run(read_stdin: Callable[[], str], env: Mapping[str, str], cwd: Path) -> int:
    """Return 0, whatever happens. A failure to post is one line on standard error; every other
    reason not to act is silent."""
    token = report.value(env, "GITHUB_TOKEN") or report.value(env, "GH_TOKEN")
    try:
        _show(read_stdin(), env, cwd, token)
    except github_api.ApiError as error:
        reason = (
            f"gave up after {BUDGET_SECONDS:g} seconds without an answer from GitHub"
            if error.timed_out
            else str(error)
        )
        secrets = () if token is None else (token,)
        shown = report.redact(" ".join(reason.split()), secrets)
        print(
            f"prepush-ci: the result was not put on the pull request: {shown}",
            file=sys.stderr,
        )
    except (ReportError, ConfigError, GitError, OSError, ValueError):
        pass  # nothing to show, or no way to find out: the agent's command is never blocked
    return 0


def _show(
    stdin_text: str,
    env: Mapping[str, str],
    cwd: Path,
    token: str | None,
) -> None:
    payload = parse_payload(stdin_text)
    if payload is None or not is_push(payload.command):
        return
    where = cwd if payload.cwd is None else text_io.to_path(payload.cwd)
    toplevel = git(where, "rev-parse", "--show-toplevel")
    if toplevel.returncode != 0:
        return
    root = text_io.to_path(answer(toplevel))
    branch = _branch(root)
    head = current_head(root)
    if (
        branch is None
        or _pushed(root, branch) != head.sha
        or not _demands(root, head.sha)
    ):
        return
    recorded = _latest_pass(root, head.tree)
    if recorded is None:
        return
    origin = git(root, "remote", "get-url", "origin")
    target = report.target(answer(origin) if origin.returncode == 0 else None, env)
    client = github_api.PullRequestClient(
        target.api_url, target.repository, token, BUDGET_SECONDS
    )
    pulls = client.open_pulls(branch)
    if not pulls:
        return
    body = report_command.passed_markdown(head.sha, head.tree, root)
    facts = pass_facts(root, recorded, head.tree)
    if facts is not None:
        body += "\n\n" + facts_block(facts[1], facts[0], head.sha)
    found = _comment_of(client, pulls[0], marker_of(body))
    if found is None:
        client.create_comment(pulls[0], body)
    elif found[1] != body:
        client.update_comment(found[0], body)


def _comment_of(
    client: github_api.PullRequestClient, number: int, marker: str
) -> tuple[int, str] | None:
    """The comment of the pull request that starts with the marker, over all its pages."""
    page = 1
    while True:
        comments = client.issue_comments(number, page)
        found = find_comment(comments, marker)
        if found is not None or len(comments) < github_api.PER_PAGE:
            return found
        page += 1


def _branch(root: Path) -> str | None:
    """The branch checked out, or None when `HEAD` is detached."""
    named = git(root, "symbolic-ref", "--quiet", "HEAD")
    prefix = "refs/heads/"
    return answer(named).removeprefix(prefix) if named.returncode == 0 else None


def _pushed(root: Path, branch: str) -> str | None:
    """What `origin` last got under the name of the branch, as git remembers it."""
    found = git(
        root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"
    )
    return found.stdout.strip() if found.returncode == 0 else None


def _demands(root: Path, sha: str) -> bool:
    """Whether the commit carries the trailer the pre-push hook demands the check for: the keys of
    the config committed in it and of the worktree's, when that can be read."""
    committed = committed_config(sha, root)
    if committed is None:
        return False
    configs: list[Config] = [committed]
    # When the worktree's config cannot be read, the commit's keys decide.
    with contextlib.suppress(ConfigError):
        configs.append(load_repository_config(root))
    return demands_check(trailers(sha, root), demand_keys(*configs))


def _latest_pass(root: Path, tree: str) -> str | None:
    """The result ref of the latest pass the run cache holds for the tree, or None."""
    return latest_ref(dated_passes(root, results_pattern(tree)))
