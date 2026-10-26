"""`prepush-ci verify <sha>`: exit 0 only when the commit provably went through the full check."""

from collections.abc import Sequence
from pathlib import Path

from prepush_ci.core.config import ConfigError
from prepush_ci.core.verify import (
    Verdict,
    invalid_config,
    no_config,
    render,
    server_made,
    trailer_verdict,
    unreadable,
    unresolved,
    usage_problem,
)
from prepush_ci.git import (
    GitError,
    committed_config,
    git,
    is_shallow,
    resolve_commit,
    trailers,
)


def run(args: Sequence[str], cwd: Path) -> int:
    """Print one line and return 0 for a verified commit, 1 for every other outcome."""
    sha: str | None = None
    try:
        problem = usage_problem(args)
        if problem is not None:
            verdict = Verdict(False, problem)
        else:
            sha, verdict = _decide(args[0], cwd)
    except OSError as error:  # git cannot even start
        verdict = unreadable(f"cannot run git: {error}")
    print(render(verdict, sha))
    return 0 if verdict.verified else 1


def _decide(argument: str, cwd: Path) -> tuple[str | None, Verdict]:
    """The full sha (or the argument when it names no commit) and the verdict about it."""
    inside = git(cwd, "rev-parse", "--git-dir")
    if inside.returncode != 0:
        return argument, unreadable(
            f"not inside a git repository: {inside.stderr.strip()}"
        )
    sha = resolve_commit(argument, cwd)
    if sha is None:
        return argument, unresolved(argument, is_shallow(cwd))
    try:
        return sha, verdict_of(sha, cwd)
    except ConfigError as error:
        return sha, invalid_config(error.problems)
    except GitError as error:
        return sha, unreadable(str(error))


def verdict_of(sha: str, cwd: Path) -> Verdict:
    refusal = server_made(_committer_email(sha, cwd))
    if refusal is not None:
        return refusal
    config = committed_config(sha, cwd)
    if config is None:
        return no_config()
    return trailer_verdict(trailers(sha, cwd), config)


def _committer_email(sha: str, cwd: Path) -> str:
    """The address recorded in the commit (`%ce`), never the `.mailmap`-mapped `%cE`."""
    result = git(cwd, "log", "-1", "--format=%ce", sha, "--")
    if result.returncode != 0:
        raise GitError(f"cannot read the committer of {sha}: {result.stderr.strip()}")
    return result.stdout.strip()
