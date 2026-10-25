"""The steps `run` and the pre-push hook share: what must hold before the check, and the check."""

import sys
import time
from pathlib import Path

from prepush_ci import result_files, text_io
from prepush_ci.core.config import Config
from prepush_ci.core.pre_push import message_dirty, message_hidden
from prepush_ci.core.run_facts import RunFacts
from prepush_ci.git import answer, dirty, git, hidden


class Refused(Exception):
    """The check cannot run on this state; the message says why."""


def head(cwd: Path) -> str:
    result = git(cwd, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if result.returncode != 0:
        raise Refused("HEAD points to no commit, so there is nothing to check")
    return result.stdout.strip()


def require_clean(root: Path) -> None:
    """Refuse a worktree whose state is not the commit: changes, or changes git hides."""
    dirty_files = dirty(root)
    if dirty_files:
        raise Refused(message_dirty(dirty_files))
    hidden_files = hidden(root)
    if hidden_files:
        raise Refused(message_hidden(hidden_files))


def worktree_root(cwd: Path) -> Path:
    result = git(cwd, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise Refused(
            "the repository has no worktree, so there is no commit to check here"
        )
    return text_io.to_path(answer(result))


def run_check(config: Config, root: Path) -> int:
    status = text_io.run_shell(config.check, cwd=root)
    if status != 0:
        print(
            f"prepush-ci: the check failed (exit {status}): {config.check}",
            file=sys.stderr,
        )
        return 1
    return 0


def run_recorded_check(
    config: Config, root: Path, tree: str
) -> tuple[int, RunFacts | None]:
    """`run_check` for a check whose pass is recorded: the named result files are deleted first
    and, when the check passes, read into the facts of the run together with its duration. With
    the cache off there is no pass to record, so nothing is deleted and no fact is made."""
    left = result_files.clear(config, root)
    started = time.monotonic()
    code = run_check(config, root)
    if code != 0 or not config.cache:
        return code, None
    seconds = round(time.monotonic() - started)
    return 0, result_files.gather(config, root, tree, seconds, left)
