"""The result cache in git: a passing check is remembered as a ref under `refs/prepush-ci/results/`."""

import os
import sys
from pathlib import Path

from prepush_ci.core.config import Config
from prepush_ci.core.run_cache import (
    IDENTITY,
    Head,
    Key,
    message_not_cached,
    passed_commit,
    result_message,
    result_ref,
)
from prepush_ci.git import GitError, git


def has_pass(config: Config, root: Path, key: Key) -> str | None:
    """The commit that passed the check for `key`, or None: a ref that is missing, unreadable or
    points at a commit of another tree is a miss."""
    if not config.cache:
        return None
    result = git(root, "log", "-1", "--format=%T%n%b", result_ref(key), "--")
    return passed_commit(result.stdout, key)  # unreadable: git says nothing, a miss


def record_pass(config: Config, root: Path, key: Key, sha: str) -> None:
    """Remember that the check passed on commit `sha`, whose tree is the key's; the key was read
    before the check ran. A cache that cannot be written is a warning, never a reason to fail a
    run that passed."""
    if not config.cache:
        return
    try:
        commit = _commit_of(root, key.tree, sha)
        updated = git(root, "update-ref", result_ref(key), commit)
        if updated.returncode != 0:
            raise GitError(updated.stderr.strip())
    except GitError as error:
        print(message_not_cached(str(error)), file=sys.stderr)


def current_head(root: Path) -> Head:
    result = git(root, "log", "-1", "--format=%H%n%T", "HEAD", "--")
    shas = result.stdout.split()
    if result.returncode != 0 or len(shas) != 2:
        raise GitError("HEAD points to no commit")
    return Head(shas[0], shas[1])


def _commit_of(root: Path, tree: str, sha: str) -> str:
    """A parentless commit of `tree` that names `sha`, made with a fixed identity so it needs no
    `user.name` and no signing."""
    name, email = IDENTITY
    identity = {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }
    message = [part for text in result_message(sha) for part in ("-m", text)]
    made = git(root, "commit-tree", tree, *message, env={**os.environ, **identity})
    if made.returncode != 0:
        raise GitError(made.stderr.strip())
    return made.stdout.strip()
