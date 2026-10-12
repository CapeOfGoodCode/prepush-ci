"""`prepush-ci hook pre-push`: a pushed commit that carries the trailer was checked before it goes."""

import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

from prepush_ci.core.commit_msg import InvalidMode, parse_mode
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.pre_push import (
    MalformedRefLine,
    PushedRef,
    branch_tips,
    demand_keys,
    demands_check,
    dirty_paths,
    hidden_paths,
    message_dirty,
    message_hidden,
    message_not_head,
    message_off,
    parse_ref_lines,
    pre_commit_push,
)
from prepush_ci.git import GitError, committed_config, git, trailers
from prepush_ci.preflight import PreflightRefused
from prepush_ci.preflight import run as run_preflight
from prepush_ci.repo_config import load_repository_config

ENV_VAR = "PREPUSH_CI"
HINT = (
    "prepush-ci: this commit has no trailer, so CI will run the full check for this push; "
    "run `git commit --amend --no-edit` with PREPUSH_CI=full to add the trailer "
    "and check it here first"
)


class HookError(Exception):
    """The hook cannot let the push go; the message says why."""


def run(stdin: TextIO, env: Mapping[str, str], cwd: Path) -> int:
    """Run the hook; return the exit code (non-zero makes git abort the push)."""
    try:
        parse_mode(env.get(ENV_VAR))  # refuse unknown values before any ref is read
        return _decide(stdin.read(), env, cwd)
    except ConfigError as error:
        for problem in error.problems:
            print(f"prepush-ci: {problem}", file=sys.stderr)
        return 1
    except (
        InvalidMode,
        MalformedRefLine,
        HookError,
        GitError,
        PreflightRefused,
    ) as error:
        print(f"prepush-ci: {error}", file=sys.stderr)
        return 1


def _decide(stdin_text: str, env: Mapping[str, str], cwd: Path) -> int:
    tips = branch_tips(_pushed_refs(stdin_text, env, cwd))
    if not tips:
        return 0
    root = _worktree_root(cwd)
    config = load_repository_config(root)
    demanding = [sha for sha in tips if _demands_check(sha, config, root)]
    if not demanding:
        if env.get(ENV_VAR) == "full":  # a user who did not opt in is not nagged
            print(HINT, file=sys.stderr)
        return 0
    return _enforce(demanding, env, config, root)


def _enforce(
    demanding: list[str], env: Mapping[str, str], config: Config, root: Path
) -> int:
    """Refuse for the cheap, certain reasons first; run the check only on a state that is the commit."""
    if (
        env.get(ENV_VAR) == "off"
    ):  # unset, empty and `full` behave alike: the trailer demands the check, not the variable
        raise HookError(message_off(demanding))
    head = _head(root)
    others = [sha for sha in demanding if sha != head]
    if others:
        raise HookError(message_not_head(others, head))
    dirty = dirty_paths(_status(root))
    if dirty:
        raise HookError(message_dirty(dirty))
    hidden = hidden_paths(_listing(root, "the index flags", "ls-files", "-v", "-z"))
    if hidden:
        raise HookError(message_hidden(hidden))
    run_preflight(config, env, root)
    return _run_check(config, root)


def _head(cwd: Path) -> str:
    result = git(cwd, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if result.returncode != 0:
        raise HookError("HEAD points to no commit, so there is nothing to check")
    return result.stdout.strip()


def _status(cwd: Path) -> str:
    """`git status --porcelain -z`: staged, unstaged and untracked paths, not the ignored ones."""
    return _listing(
        cwd,
        "the worktree status",
        "status",
        "--porcelain",
        "-z",
        "--untracked-files=all",
    )


def _listing(cwd: Path, what: str, *args: str) -> str:
    result = git(cwd, *args)
    if result.returncode != 0:
        raise HookError(f"{what} could not be read: {result.stderr.strip()}")
    return result.stdout


def _pushed_refs(stdin_text: str, env: Mapping[str, str], cwd: Path) -> list[PushedRef]:
    refs = parse_ref_lines(stdin_text)
    if refs:
        return refs
    pushed = pre_commit_push(env)
    if pushed is None:
        return []
    sha = pushed.sha
    if sha is None:
        assert pushed.local_branch is not None  # pre_commit_push returns None otherwise
        sha = _resolve(pushed.local_branch, cwd)
    return [PushedRef(pushed.local_branch or sha, sha, pushed.remote_ref)]


def _resolve(ref: str, cwd: Path) -> str:
    result = git(cwd, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if result.returncode != 0:
        raise HookError(f"{ref} (PRE_COMMIT_LOCAL_BRANCH) does not name a commit")
    return result.stdout.strip()


def _demands_check(sha: str, config: Config, cwd: Path) -> bool:
    tip_config = committed_config(sha, cwd)
    configs = [config] if tip_config is None else [config, tip_config]
    return demands_check(trailers(sha, cwd), demand_keys(*configs))


def _worktree_root(cwd: Path) -> Path:
    result = git(cwd, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise HookError(
            "the repository has no worktree, so the hook cannot check a commit here"
        )
    return Path(result.stdout.strip())


def _run_check(config: Config, root: Path) -> int:
    outcome = subprocess.run(
        config.check, shell=True, cwd=root, stdin=subprocess.DEVNULL, check=False
    )
    if outcome.returncode != 0:
        print(
            f"prepush-ci: the check failed (exit {outcome.returncode}): {config.check}",
            file=sys.stderr,
        )
        return 1
    return 0
