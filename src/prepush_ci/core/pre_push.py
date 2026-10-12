"""Decisions of the pre-push hook: which pushed refs count, and whether a tip demands the check."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from prepush_ci.core.config import Config

BRANCH_PREFIX = "refs/heads/"
SHORT = 12  # characters of a sha shown in messages


class MalformedRefLine(Exception):
    """A line on standard input is not `<local ref> <local sha> <remote ref> <remote sha>`."""


@dataclass(frozen=True)
class PushedRef:
    """One ref of a push; `remote_ref` is None when pre-commit does not say."""

    local_ref: str
    sha: str
    remote_ref: str | None


@dataclass(frozen=True)
class PreCommitPush:
    """What pre-commit tells a pre-push hook; `sha` is None when only the local branch is known."""

    sha: str | None
    local_branch: str | None
    remote_ref: str | None


def parse_ref_lines(text: str) -> list[PushedRef]:
    """Read git's pre-push protocol: one `<local ref> <local sha> <remote ref> <remote sha>` per line."""
    refs: list[PushedRef] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split(" ")
        if len(fields) != 4:
            raise MalformedRefLine(
                f"git sent a ref line the hook cannot read: {line!r} "
                "(expected `<local ref> <local sha> <remote ref> <remote sha>`)"
            )
        local_ref, local_sha, remote_ref, _remote_sha = fields
        refs.append(PushedRef(local_ref, local_sha, remote_ref))
    return refs


def pre_commit_push(env: Mapping[str, str]) -> PreCommitPush | None:
    """The push as pre-commit describes it, or None when it sets neither the sha nor the local branch.

    pre-commit consumes git's standard input and exposes one ref in `PRE_COMMIT_*` variables.
    """
    sha = env.get("PRE_COMMIT_TO_REF") or None
    local_branch = env.get("PRE_COMMIT_LOCAL_BRANCH") or None
    if sha is None and local_branch is None:
        return None
    return PreCommitPush(
        sha=sha,
        local_branch=local_branch,
        remote_ref=env.get("PRE_COMMIT_REMOTE_BRANCH") or None,
    )


def is_deletion(sha: str) -> bool:
    return set(sha) == {"0"}


def is_branch_update(ref: PushedRef) -> bool:
    """A branch is decided by the remote ref; an unknown one counts as a branch (fail closed)."""
    if is_deletion(ref.sha):
        return False
    return ref.remote_ref is None or ref.remote_ref.startswith(BRANCH_PREFIX)


def branch_tips(refs: Iterable[PushedRef]) -> list[str]:
    """The distinct shas that branches are updated to, in push order."""
    tips: list[str] = []
    for ref in refs:
        if is_branch_update(ref) and ref.sha not in tips:
            tips.append(ref.sha)
    return tips


def demand_keys(*configs: Config) -> frozenset[str]:
    """Lower-cased trailer keys that demand the check: the configured key and the legacy keys."""
    keys: set[str] = set()
    for config in configs:
        keys.add(config.trailer.key.lower())
        keys.update(key.lower() for key in config.legacy_keys)
    return frozenset(keys)


def demands_check(trailers: str, keys: Iterable[str]) -> bool:
    """Whether a trailer of the tip has a demanding key, whatever its value.

    `trailers` is `git log --format=%(trailers:only,unfold)` of the tip: one `Key: value` per
    line, so git decides what a trailer is. `keys` are lower-cased.
    """
    wanted = set(keys)
    for line in trailers.splitlines():
        key, separator, _value = line.partition(":")
        if separator and key.strip().lower() in wanted:
            return True
    return False


def dirty_paths(porcelain_z: str) -> list[str]:
    """Paths in `git status --porcelain -z` output (a rename lists its old path as a second entry)."""
    entries = porcelain_z.split("\0")
    paths: list[str] = []
    skip_next = False
    for entry in entries:
        if skip_next:
            skip_next = False
            continue
        if not entry:
            continue
        paths.append(entry[3:])
        skip_next = entry[0] in "RC" or entry[1] in "RC"
    return paths


def hidden_paths(ls_files_v_z: str) -> list[str]:
    """Paths `git status` cannot see changes to, from `git ls-files -v -z` output.

    A lowercase tag marks an assume-unchanged entry and `S` a skip-worktree one
    (sparse checkout sets it); git reports no change to either.
    """
    paths: list[str] = []
    for entry in ls_files_v_z.split("\0"):
        if entry and (entry[0].islower() or entry[0] == "S"):
            paths.append(entry[2:])
    return paths


def _shorts(shas: Sequence[str]) -> str:
    return ", ".join(sha[:SHORT] for sha in shas)


def message_off(tips: Sequence[str]) -> str:
    return (
        f"{_shorts(tips)} demands the full check but PREPUSH_CI=off: "
        "unset PREPUSH_CI (or set it to `full`) to run the check, "
        "or push a commit without the trailer"
    )


def message_not_head(tips: Sequence[str], head: str) -> str:
    return (
        f"{_shorts(tips)} demands the full check, but only the checked-out commit "
        f"can be checked and HEAD is {head[:SHORT]}: check out the commit you push "
        "(or push HEAD)"
    )


def message_dirty(paths: Sequence[str]) -> str:
    listed = "\n".join(f"  {path}" for path in paths)
    return (
        "the worktree is not clean, so the check would not run on the commit you push; "
        f"commit, stash, or ignore these paths:\n{listed}"
    )


def message_hidden(paths: Sequence[str]) -> str:
    listed = "\n".join(f"  {path}" for path in paths)
    return (
        "git does not report changes to these paths (assume-unchanged or skip-worktree, "
        "which a sparse checkout sets), so the check would not run on the commit you push; "
        "clear the flag with `git update-index --no-assume-unchanged` or "
        f"`--no-skip-worktree`, or check out the whole tree:\n{listed}"
    )
