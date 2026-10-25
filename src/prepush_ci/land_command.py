"""`prepush-ci land <number>`: push the head of a checked pull request to the default branch of `origin`."""

import contextlib
import shutil
import sys
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path

from prepush_ci import land_comments, text_io
from prepush_ci.core import land
from prepush_ci.core.config import REMOTE, Config, ConfigError
from prepush_ci.core.land import Answer, Position
from prepush_ci.core.preflight import missing_env
from prepush_ci.core.run_cache import Key, fingerprint
from prepush_ci.core.verify import invalid_config
from prepush_ci.git import GitError, committed_config, git
from prepush_ci.pass_cache import fetch_pass, has_pass
from prepush_ci.verify_command import verdict_of


def run(number: int, env: Mapping[str, str], cwd: Path) -> int:
    """Print one line and return 0 for a head that landed or is already on the branch, 1 for every
    other outcome."""
    try:
        answer = _land(number, env, cwd)
    except ConfigError as error:
        answer = land.refused(invalid_config(error.problems).reason)
    except GitError as error:
        answer = land.refused(str(error))
    except OSError as error:  # git cannot even start
        answer = land.refused(f"cannot run git: {error}")
    print(answer.line)
    return 0 if answer.landed else 1


def _land(number: int, env: Mapping[str, str], cwd: Path) -> Answer:
    """Every refusal that needs no command of the head comes first: the `preflight` committed in
    the head is code of the pull request and runs with the rights of whoever runs `land`."""
    inside = git(cwd, "rev-parse", "--git-dir")
    if inside.returncode != 0:
        return land.not_in_repository(_first_line(inside.stderr))
    if git(cwd, "remote", "get-url", REMOTE).returncode != 0:
        return land.no_origin()
    ref = land.pull_ref(number)
    asked = git(cwd, "ls-remote", "--symref", REMOTE, "HEAD", ref)
    if asked.returncode != 0:
        return land.origin_unreachable(_first_line(asked.stderr))
    branch = land.default_branch(asked.stdout)
    tip = land.listed_commit(asked.stdout, "HEAD")
    if branch is None or tip is None:
        return land.no_default_branch()
    head = land.listed_commit(asked.stdout, ref)
    if head is None:
        return land.no_pull_request(number)
    problem = _fetch((f"refs/heads/{branch}", ref), (tip, head), env, cwd)
    if problem is not None:
        return problem
    where = _position(tip, head, cwd)
    if where is Position.ON_BRANCH:
        return land.already_on(head, branch)
    if where is Position.MOVED:
        return land.branch_moved(branch)
    verdict = verdict_of(head, cwd)
    if not verdict.verified:
        return land.refused(f"{head} {verdict.reason}")
    config = committed_config(head, cwd)
    assert config is not None  # a verified commit has a config
    if not config.cache:
        return land.cache_off()
    missing = missing_env(config.require_env, env)
    if missing:
        return land.missing_variables(missing)
    output = _preflight(config, head, cwd)
    if isinstance(output, Answer):
        return output
    tree = _tree(head, cwd)
    key = Key(tree, fingerprint(config, output))
    if has_pass(config, cwd, key) is None and fetch_pass(config, cwd, key) is None:
        searched = land_comments.search(number, config, tree, env, cwd)
        if not searched.found:
            return land.no_pass(tree, searched.why_not_asked)
    return _push(head, tip, branch, env, cwd)


def _fetch(
    refs: tuple[str, ...], commits: tuple[str, ...], env: Mapping[str, str], cwd: Path
) -> Answer | None:
    """Fetch the refs into `FETCH_HEAD`. Git may also move `refs/remotes/origin/<branch>`
    by itself; none of the repository's hooks (`reference-transaction`) runs for it. A damaged ref of
    another name must not fail it, as for the result cache."""
    with _no_hooks() as no_hooks:
        fetched = git(
            cwd,
            *no_hooks,
            "fetch",
            "--quiet",
            "--no-auto-maintenance",
            "--",
            REMOTE,
            *refs,
            env={**env, "GIT_REF_PARANOIA": "0"},
        )
    if fetched.returncode != 0:
        return land.not_fetched(_first_line(fetched.stderr))
    # a ref that moved since it was listed may have taken its commit away
    for sha in commits:
        if git(cwd, "cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
            return land.not_fetched(f"origin did not send {sha}")
    return None


def _position(tip: str, head: str, cwd: Path) -> Position:
    return land.position(_is_ancestor(head, tip, cwd), _is_ancestor(tip, head, cwd))


def _is_ancestor(ancestor: str, descendant: str, cwd: Path) -> bool:
    """Whether `ancestor` is `descendant` or one of its ancestors; unrelated histories are not. An
    answer git cannot give counts as no, which refuses the landing."""
    compared = git(cwd, "merge-base", "--is-ancestor", ancestor, descendant)
    return compared.returncode == 0


def _tree(head: str, cwd: Path) -> str:
    """The tree of a commit that was fetched; empty if git cannot read it, which finds no pass."""
    result = git(cwd, "rev-parse", "--verify", "--quiet", f"{head}^{{tree}}")
    return result.stdout.strip()


def _preflight(config: Config, head: str, cwd: Path) -> str | Answer:
    """The standard output of the `preflight` run in a checkout of the head (empty without one),
    shown on standard error because the answer is one line; or the refusal when it fails."""
    if config.preflight is None:
        return ""
    with _checkout(head, cwd) as worktree, contextlib.redirect_stdout(sys.stderr):
        status, output = text_io.run_shell_tee(config.preflight, cwd=worktree)
    if status != 0:
        return land.preflight_failed(config.preflight, status)
    return output


@contextlib.contextmanager
def _checkout(head: str, cwd: Path) -> Iterator[Path]:
    """A detached checkout of `head` in a scratch directory, gone afterwards whatever happens. It
    runs none of the repository's hooks (`post-checkout` is the lander's, written for checkouts
    the lander makes): `core.hooksPath` points at an empty directory for that one command."""
    scratch = Path(tempfile.mkdtemp(prefix="prepush-ci-land-"))
    worktree = scratch / "head"
    hooks = scratch / "hooks"
    hooks.mkdir()
    try:
        added = git(
            cwd,
            "-c",
            f"core.hooksPath={hooks.as_posix()}",
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(worktree),
            head,
        )
        if added.returncode != 0:
            raise GitError(f"cannot check out {head}: {_first_line(added.stderr)}")
        yield worktree
    finally:
        shutil.rmtree(scratch, ignore_errors=True)  # Windows may still hold a file
        git(cwd, "worktree", "prune")  # forget the checkout the directory held


@contextlib.contextmanager
def _no_hooks() -> Iterator[list[str]]:
    """The arguments that make one git command run none of the repository's hooks: an empty
    directory as `core.hooksPath`."""
    with tempfile.TemporaryDirectory(prefix="prepush-ci-land-hooks-") as empty:
        yield ["-c", f"core.hooksPath={Path(empty).as_posix()}"]


def _push(
    head: str, tip: str, branch: str, env: Mapping[str, str], cwd: Path
) -> Answer:
    """The tool's own push: a fast-forward, never forced, without the repository's hooks (`--no-verify`
    skips only `pre-push`; `reference-transaction` is silenced by an empty `core.hooksPath`) and
    without the tags it may be configured to follow. The push is the compare-and-swap: a branch
    that moved is never overwritten."""
    with _no_hooks() as no_hooks:
        pushed = git(
            cwd,
            *no_hooks,
            "-c",
            "push.followTags=false",
            "push",
            "--porcelain",
            "--no-verify",
            "--",
            REMOTE,
            f"{head}:refs/heads/{branch}",
        )
    if pushed.returncode == 0:
        return land.landed(head, branch)
    # the refusal may come from a run that landed the head meanwhile: ask the branch, not the refusal
    listed = git(cwd, "ls-remote", REMOTE, f"refs/heads/{branch}")
    now = land.listed_commit(listed.stdout, f"refs/heads/{branch}")
    return land.after_refusal(
        head,
        tip,
        now,
        branch,
        land.refusal_reason(pushed.stdout),
        now is not None
        and now != tip
        and _fetch((f"refs/heads/{branch}",), (now,), env, cwd) is None
        and _is_ancestor(head, now, cwd),
    )


def _first_line(text: str) -> str:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines[0] if lines else "git gave no reason"
