"""The result cache in git: a passing check is remembered as a ref under `refs/prepush-ci/results/`."""

import os
import sys
import time
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.config import REMOTE, Config
from prepush_ci.core.run_cache import (
    IDENTITY,
    RESULTS,
    Head,
    Key,
    batches,
    config_digest,
    expired_refs,
    lists_ref,
    message_not_asked,
    message_not_cached,
    message_not_cleaned,
    message_not_cleaned_from_origin,
    message_not_shared,
    passed_commit,
    passed_facts,
    result_message,
    result_ref,
)
from prepush_ci.core.run_facts import RunFacts, to_line
from prepush_ci.git import GitError, git


def has_pass(config: Config, root: Path, key: Key) -> str | None:
    """The commit that passed the check for `key`, or None: a ref that is missing, unreadable or
    points at a commit of another tree is a miss."""
    if not config.cache:
        return None
    result = git(root, "log", "-1", "--format=%T%n%b", result_ref(key), "--")
    return passed_commit(result.stdout, key)  # unreadable: git says nothing, a miss


def record_pass(
    config: Config, root: Path, key: Key, sha: str, facts: RunFacts | None = None
) -> bool:
    """Remember that the check passed on commit `sha`, whose tree is the key's, with the facts of
    the run when there are any; the key was read before the check ran. A cache that cannot be
    written is a warning, never a reason to fail a run that passed. True when the result is there
    to publish."""
    if not config.cache:
        return False
    try:
        commit = _commit_of(root, key.tree, sha, facts, config_digest(config))
        updated = git(root, "update-ref", result_ref(key), commit)
        if updated.returncode != 0:
            raise GitError(updated.stderr.strip())
    except GitError as error:
        print(message_not_cached(str(error)), file=sys.stderr)
        return False
    return True


def pass_facts(root: Path, ref: str, tree: str) -> tuple[str, RunFacts] | None:
    """The commit a result ref names and the facts it holds, or None when it holds no facts that
    can be read (or is not a result of `tree`)."""
    key = Key(tree, ref.rpartition("-")[2])
    log = git(root, "log", "-1", "--format=%T%n%b", ref, "--").stdout
    sha, facts = passed_commit(log, key), passed_facts(log, key)
    return None if sha is None or facts is None else (sha, facts)


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
        print(message_not_shared(pushed.stderr), file=sys.stderr)
        if os.environ.get("PREPUSH_CI_DEBUG"):
            print(pushed.stderr.strip(), file=sys.stderr)


def expire_passes(root: Path, to_origin: bool) -> None:
    """Delete the result refs older than 30 days, after a pass was recorded; `to_origin` is
    whether the push the hook checks goes to `origin`. A repository without `origin` shares
    nothing and cleans its clone. One with `origin` cleans only in a push to `origin`, from
    `origin` first and then from the clone, for a clone that deleted what `origin` keeps would
    leave no name to drop it by. A failure is a warning, for the pass it follows is recorded."""
    has_origin = _has_origin(root)
    if has_origin and not to_origin:
        return
    expired = expired_refs(dated_passes(root, RESULTS), int(time.time()))
    if has_origin:
        expired = _delete_from_origin(root, expired)
    if expired:
        _delete_local(root, expired)


def dated_passes(root: Path, pattern: str) -> str:
    """Each result ref that matches `pattern` and its commit date, one per line. One ref git cannot
    date (its object is missing) makes git refuse the whole listing, so the refs are asked for in
    batches, and a batch that fails is halved until the ref that fails is alone; that one is left
    out, so it stays."""
    listing = _dated(root, [pattern])
    if listing is not None:
        return listing
    names = git(root, "for-each-ref", "--format=%(refname)", pattern).stdout.split()
    return "".join(_dated_among(root, batch) for batch in batches(names))


def _dated_among(root: Path, refs: list[str]) -> str:
    listing = _dated(root, refs)
    if listing is not None:
        return listing
    if len(refs) == 1:
        return ""
    middle = len(refs) // 2
    return _dated_among(root, refs[:middle]) + _dated_among(root, refs[middle:])


def _dated(root: Path, patterns: list[str]) -> str | None:
    listing = git(
        root, "for-each-ref", "--format=%(refname) %(committerdate:unix)", *patterns
    )
    return listing.stdout if listing.returncode == 0 else None


def _delete_from_origin(root: Path, refs: list[str]) -> list[str]:
    """Delete `refs` from `origin` and return the ones it dropped. A delete of a ref `origin` does
    not hold succeeds, so none needs asking for first. The push is the tool's own, without the
    repository's hooks; a batch that fails keeps its refs and the first reason is the one warning."""
    dropped: list[str] = []
    reason: str | None = None
    for batch in batches(refs):
        pushed = git(root, "push", "--no-verify", REMOTE, *(f":{ref}" for ref in batch))
        if pushed.returncode == 0:
            dropped += batch
        elif reason is None:
            reason = pushed.stderr.strip()
    if reason is not None:
        print(message_not_cleaned_from_origin(reason), file=sys.stderr)
    return dropped


def _delete_local(root: Path, refs: list[str]) -> None:
    """One `git update-ref --stdin` for all of them, however many there are."""
    commands = "".join(f"delete {ref}\n" for ref in refs)
    deleted = text_io.run_bytes(
        ["git", "update-ref", "--stdin"], cwd=root, stdin=text_io.encode(commands)
    )
    if deleted.returncode != 0:
        reason = text_io.decode(deleted.stderr).strip()
        print(message_not_cleaned(reason), file=sys.stderr)


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
    # A fetch that fails now (the ref went away since, or the clone's ref of this very name is
    # damaged) leaves no ref: a miss, as it should. A damaged ref of another name must not fail it:
    # git dies on one unless told to look away, and while it looks away its housekeeping would
    # prune what only that ref holds.
    git(
        root,
        "fetch",
        "--quiet",
        "--no-auto-maintenance",
        REMOTE,
        f"+{ref}:{ref}",
        env={**os.environ, "GIT_REF_PARANOIA": "0"},
    )
    return has_pass(config, root, key)


def _has_origin(root: Path) -> bool:
    return git(root, "remote", "get-url", REMOTE).returncode == 0


def current_head(root: Path) -> Head:
    result = git(root, "log", "-1", "--format=%H%n%T", "HEAD", "--")
    shas = result.stdout.split()
    if result.returncode != 0 or len(shas) != 2:
        raise GitError("HEAD points to no commit")
    return Head(shas[0], shas[1])


def _commit_of(
    root: Path, tree: str, sha: str, facts: RunFacts | None, digest: str
) -> str:
    """A parentless commit of `tree` that names `sha` and the digest of the config, made with a fixed identity so it needs no
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
    line = None if facts is None else to_line(facts)
    message = [
        part for text in result_message(sha, line, digest) for part in ("-m", text)
    ]
    made = git(root, "commit-tree", tree, *message, env={**os.environ, **identity})
    if made.returncode != 0:
        raise GitError(made.stderr.strip())
    return made.stdout.strip()
