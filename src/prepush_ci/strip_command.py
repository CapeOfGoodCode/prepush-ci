"""`prepush-ci strip [<base>]`: rewrite the commits since `<base>` without the demanding trailer."""

import sys
from collections.abc import Sequence
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.config import REMOTE, Config, ConfigError
from prepush_ci.core.pre_push import demand_keys
from prepush_ci.core.strip import (
    MARKERS,
    commit_message,
    in_progress,
    message_detached,
    message_dirty,
    message_hidden,
    message_needs_base,
    message_not_ancestor,
    message_unknown_base,
    parent_shas,
    rebuild_commit,
    report,
    strip_message,
)
from prepush_ci.git import GitError, dirty, git, git_bytes, hidden, trailers
from prepush_ci.repo_config import load_repository_config


class Refused(Exception):
    """strip would not be safe or well-defined here; the message says why. Nothing was changed."""


def run(args: Sequence[str], cwd: Path) -> int:
    """Rewrite the branch and print the report; any refusal exits 1 before a ref moves."""
    try:
        for line in _strip(args, cwd):
            print(line)
        return 0
    except ConfigError as error:
        for problem in error.problems:
            print(f"prepush-ci: {problem}", file=sys.stderr)
    except (Refused, GitError) as error:
        print(f"prepush-ci: {error}", file=sys.stderr)
    return 1


def _strip(args: Sequence[str], cwd: Path) -> list[str]:
    if len(args) > 1:
        raise Refused(
            f"expected at most one <base>, got {len(args)} arguments: run `prepush-ci strip [<base>]`"
        )
    root = _worktree_root(cwd)
    _check_state(root)
    config = load_repository_config(root)
    old_tip = _head(root)
    base = _base(args[0] if args else None, config, root)
    mapping = _rewrite(base, old_tip, config, root)
    new_tip = mapping.get(old_tip, old_tip)
    total = len(_range(base, old_tip, root))
    if mapping:
        branch = _git(root, "symbolic-ref", "-q", "HEAD")
        _git(root, "update-ref", "-m", "prepush-ci strip", branch, new_tip, old_tip)
    return report(len(mapping), total, old_tip, new_tip)


def _worktree_root(cwd: Path) -> Path:
    result = git(cwd, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise Refused("not inside a git worktree, so there is nothing to strip")
    return text_io.to_path(result.stdout.strip())


def _check_state(root: Path) -> None:
    """Refuse every state in which moving the branch could lose work."""
    paths = _git(root, "rev-parse", *[a for m in MARKERS for a in ("--git-path", m)])
    existing = {
        marker
        for marker, path in zip(MARKERS, paths.splitlines(), strict=True)
        if (root / text_io.to_os(path)).exists()
    }
    problem = in_progress(existing)
    if problem is not None:
        raise Refused(problem)
    if git(root, "symbolic-ref", "-q", "HEAD").returncode != 0:
        raise Refused(message_detached())
    _head(root)
    dirty_files = dirty(root)
    if dirty_files:
        raise Refused(message_dirty(dirty_files))
    hidden_files = hidden(root)
    if hidden_files:
        raise Refused(message_hidden(hidden_files))


def _head(root: Path) -> str:
    sha = _commit("HEAD", root)
    if sha is None:
        raise Refused("HEAD points to no commit, so there is nothing to strip")
    return sha


def _commit(rev: str, root: Path) -> str | None:
    if rev.startswith(
        "-"
    ):  # no revision starts with a dash; never hand an option to git
        return None
    result = git(root, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def _base(argument: str | None, config: Config, root: Path) -> str:
    """The commit before the first one to rewrite; it is never rewritten itself."""
    if argument is not None:
        base = _commit(argument, root)
        if base is None:
            raise Refused(message_unknown_base(argument))
        ancestor = git(root, "merge-base", "--is-ancestor", base, "HEAD")
        if ancestor.returncode != 0:
            raise Refused(message_not_ancestor(argument))
        return base
    branch = config.default_branch
    for ref, shown in (
        (f"refs/remotes/{REMOTE}/{branch}", f"{REMOTE}/{branch}"),
        (f"refs/heads/{branch}", branch),
    ):
        default = _commit(ref, root)
        if default is None:
            continue
        merge_base = git(root, "merge-base", "HEAD", default)
        if (
            merge_base.returncode != 0
        ):  # no shared history: never fall back to all of it
            raise Refused(message_needs_base(shown))
        return merge_base.stdout.strip()
    raise Refused(message_needs_base(f"{REMOTE}/{branch}"))


def _range(base: str, tip: str, root: Path) -> list[str]:
    """The commits of `<base>..<tip>`, parents before children."""
    listing = _git(root, "rev-list", "--topo-order", "--reverse", f"{base}..{tip}")
    return listing.split()


def _rewrite(base: str, tip: str, config: Config, root: Path) -> dict[str, str]:
    """Write the changed commits as new objects; return old sha -> new sha for each of them."""
    keys = demand_keys(config)
    mapping: dict[str, str] = {}
    for sha in _range(base, tip, root):
        raw = text_io.decode(git_bytes(root, "cat-file", "commit", sha))
        old_message = commit_message(raw)
        message = strip_message(old_message, trailers(sha, root), keys)
        if message == old_message and all(
            mapping.get(parent, parent) == parent for parent in parent_shas(raw)
        ):
            continue
        rebuilt = text_io.encode(rebuild_commit(raw, mapping, message))
        written = git_bytes(
            root, "hash-object", "-t", "commit", "-w", "--stdin", stdin=rebuilt
        )
        mapping[sha] = text_io.decode(written).strip()
    return mapping


def _git(root: Path, *args: str) -> str:
    return text_io.decode(git_bytes(root, *args)).strip()
