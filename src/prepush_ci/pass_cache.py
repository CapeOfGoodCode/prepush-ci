"""The result cache in git: a passing check is remembered as a ref under `refs/prepush-ci/results/`."""

import os
import sys
import time
from pathlib import Path

from prepush_ci.core.config import REMOTE, Config
from prepush_ci.core.run_cache import (
    IDENTITY,
    Head,
    Key,
    lists_ref,
    message_not_asked,
    message_not_cached,
    message_not_shared,
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


def record_pass(config: Config, root: Path, key: Key, sha: str) -> bool:
    """Remember that the check passed on commit `sha`, whose tree is the key's; the key was read
    before the check ran. A cache that cannot be written is a warning, never a reason to fail a
    run that passed. True when the result is there to publish."""
    if not config.cache:
        return False
    try:
        commit = _commit_of(root, key.tree, sha)
        updated = git(root, "update-ref", result_ref(key), commit)
        if updated.returncode != 0:
            raise GitError(updated.stderr.strip())
    except GitError as error:
        print(message_not_cached(str(error)), file=sys.stderr)
        return False
    return True


def publish_pass(root: Path, key: Key) -> None:
    """Push the result ref of `key` to `origin`, without the repository's hooks: the push is the
    tool's own. Only the pre-push hook calls it, for a push to `origin`, so the tree the ref holds
    goes where the user is sending it anyway. A repository without `origin` shares nothing, and a
    remote that refuses is a warning, never a reason to refuse the push."""
    if not _has_origin(root):
        return
    ref = result_ref(key)
    # `+`: a pass made again is a new parentless commit, which never fast-forwards the old one
    pushed = git(root, "push", "--no-verify", REMOTE, f"+{ref}:{ref}")
    if pushed.returncode != 0:
        print(message_not_shared(pushed.stderr.strip()), file=sys.stderr)


def fetch_pass(config: Config, root: Path, key: Key) -> str | None:
    """The commit that passed the check for `key` according to `origin`, or None. Called after a
    local miss: the ref is asked for first (`git fetch` exits 128 for a missing ref and for an
    unreachable remote alike), fetched into the same name, and `has_pass` decides whether it is a
    result of the tree. A remote that fails is a warning and a miss."""
    if not config.cache or not _has_origin(root):
        return None
    ref = result_ref(key)
    asked = git(root, "ls-remote", REMOTE, ref)
    if asked.returncode != 0:
        print(message_not_asked(asked.stderr.strip()), file=sys.stderr)
        return None
    if not lists_ref(asked.stdout, ref):
        return None
    # A fetch that fails now (the ref went away since) leaves no ref: a miss, as it should.
    git(root, "fetch", "--quiet", REMOTE, f"+{ref}:{ref}")
    return has_pass(config, root, key)


def _has_origin(root: Path) -> bool:
    return git(root, "remote", "get-url", REMOTE).returncode == 0


def current_head(root: Path) -> Head:
    result = git(root, "log", "-1", "--format=%H%n%T", "HEAD", "--")
    shas = result.stdout.split()
    if result.returncode != 0 or len(shas) != 2:
        raise GitError("HEAD points to no commit")
    return Head(shas[0], shas[1])


def _commit_of(root: Path, tree: str, sha: str) -> str:
    """A parentless commit of `tree` that names `sha`, made with a fixed identity so it needs no
    `user.name` and no signing, and dated now: the environment cannot date it, for the date is
    what a cleanup ages the result by."""
    name, email = IDENTITY
    now = f"{int(time.time())} +0000"
    identity = {
        "GIT_AUTHOR_DATE": now,
        "GIT_COMMITTER_DATE": now,
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
