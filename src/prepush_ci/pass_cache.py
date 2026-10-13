"""The result cache on disk: a passing check is remembered under `prepush-ci/` in the git directory."""

import sys
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.config import Config
from prepush_ci.core.run_cache import (
    Key,
    fingerprint,
    is_pass_for,
    message_not_cached,
    pass_record,
    record_name,
)
from prepush_ci.git import GitError, git

DIRECTORY = "prepush-ci"


def has_pass(config: Config, root: Path, key: Key) -> bool:
    """Whether a pass is recorded for `key`; anything else is a miss."""
    if not config.cache:
        return False
    try:
        record = text_io.read_text(_directory(root) / record_name(key))
    except (GitError, OSError):  # unreadable: run the check
        return False
    return is_pass_for(record, key)


def record_pass(config: Config, root: Path, key: Key) -> None:
    """Remember that the check passed on `key`, which was read before the check ran. A cache
    that cannot be written is a warning, never a reason to fail a run that passed."""
    if not config.cache:
        return
    try:
        directory = _directory(root)
        directory.mkdir(parents=True, exist_ok=True)
        text_io.write_text(directory / record_name(key), pass_record(key))
    except (GitError, OSError) as error:
        print(message_not_cached(str(error)), file=sys.stderr)


def current_key(config: Config, root: Path) -> Key:
    result = git(root, "log", "-1", "--format=%H%n%T", "HEAD", "--")
    shas = result.stdout.split()
    if result.returncode != 0 or len(shas) != 2:
        raise GitError("HEAD points to no commit")
    return Key(shas[0], shas[1], fingerprint(config))


def _directory(root: Path) -> Path:
    result = git(root, "rev-parse", "--git-path", DIRECTORY)
    if result.returncode != 0:
        raise GitError(f"cannot find the git directory: {result.stderr.strip()}")
    return (root / text_io.to_path(result.stdout.strip())).resolve()
