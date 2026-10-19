"""`prepush-ci hook pre-push`: a pushed commit that carries the trailer was checked before it goes."""

import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from prepush_ci.checking import Refused, head, require_clean, run_check, worktree_root
from prepush_ci.core.commit_msg import InvalidMode, parse_mode
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.pre_push import (
    MalformedRefLine,
    PushedRef,
    branch_tips,
    demand_keys,
    demands_check,
    message_not_head,
    message_off,
    parse_ref_lines,
    pre_commit_push,
)
from prepush_ci.core.run_cache import (
    Key,
    fingerprint,
    message_skipped,
    pushes_to_origin,
)
from prepush_ci.git import GitError, committed_config, git, trailers
from prepush_ci.pass_cache import current_head, has_pass, publish_pass, record_pass
from prepush_ci.preflight import PreflightRefused
from prepush_ci.preflight import run as run_preflight
from prepush_ci.repo_config import load_repository_config

ENV_VAR = "PREPUSH_CI"
HINT = (
    "prepush-ci: this commit has no trailer, so CI will run the full check for this push; "
    "run `git commit --amend --no-edit` with PREPUSH_CI=full to add the trailer "
    "and check it here first"
)


def run(
    read_stdin: Callable[[], str],
    env: Mapping[str, str],
    cwd: Path,
    git_args: Sequence[str] = (),
) -> int:
    """Run the hook; return the exit code (non-zero makes git abort the push). `read_stdin`
    reads the ref lines git writes, after the mode is checked; `git_args` are the remote name and
    url git passes."""
    try:
        parse_mode(env.get(ENV_VAR))  # refuse unknown values before any ref is read
        return _decide(read_stdin(), env, cwd, git_args)
    except ConfigError as error:
        for problem in error.problems:
            print(f"prepush-ci: {problem}", file=sys.stderr)
        return 1
    except (
        InvalidMode,
        MalformedRefLine,
        Refused,
        GitError,
        PreflightRefused,
    ) as error:
        print(f"prepush-ci: {error}", file=sys.stderr)
        return 1


def _decide(
    stdin_text: str, env: Mapping[str, str], cwd: Path, git_args: Sequence[str]
) -> int:
    tips = branch_tips(_pushed_refs(stdin_text, env, cwd))
    if not tips:
        return 0
    root = worktree_root(cwd)
    config = load_repository_config(root)
    demanding = [sha for sha in tips if _demands_check(sha, config, root)]
    if not demanding:
        if env.get(ENV_VAR) == "full":  # a user who did not opt in is not nagged
            print(HINT, file=sys.stderr)
        return 0
    return _enforce(demanding, env, config, root, pushes_to_origin(git_args, env))


def _enforce(
    demanding: list[str],
    env: Mapping[str, str],
    config: Config,
    root: Path,
    to_origin: bool,
) -> int:
    """Refuse for the cheap, certain reasons first; run the check only on a state that is the commit."""
    if (
        env.get(ENV_VAR) == "off"
    ):  # unset, empty and `full` behave alike: the trailer demands the check, not the variable
        raise Refused(message_off(demanding))
    tip = head(root)
    checked = current_head(root)  # before the check: HEAD may move while it runs
    others = [sha for sha in demanding if sha != tip]
    if others:
        raise Refused(message_not_head(others, tip))
    require_clean(root)
    output = run_preflight(config, env, root)
    key = Key(checked.tree, fingerprint(config, output))
    passed = has_pass(config, root, key)
    if passed is not None:  # only the check is skipped: the preflight is never cached
        print(message_skipped(key.tree, passed), file=sys.stderr)
        if to_origin:  # a publish that failed once is retried by the next push
            publish_pass(config, root, key)
        return 0
    code = run_check(config, root)
    if code == 0 and record_pass(config, root, key, checked.sha) and to_origin:
        publish_pass(config, root, key)
    return code


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
        raise Refused(f"{ref} (PRE_COMMIT_LOCAL_BRANCH) does not name a commit")
    return result.stdout.strip()


def _demands_check(sha: str, config: Config, cwd: Path) -> bool:
    tip_config = committed_config(sha, cwd)
    configs = [config] if tip_config is None else [config, tip_config]
    return demands_check(trailers(sha, cwd), demand_keys(*configs))
