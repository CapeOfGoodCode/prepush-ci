"""Decisions of `prepush-ci strip`: which trailer lines go, how a commit object is rebuilt, what to say."""

from collections.abc import Collection, Iterable, Mapping, Sequence

from prepush_ci.core.pre_push import demands_check, is_demanding

# Headers that sign the commit; a rewritten commit cannot keep them.
_SIGNATURE_HEADERS = ("gpgsig", "gpgsig-sha256")

# Marker paths inside the git directory, most specific first, with what each means.
_IN_PROGRESS = (
    ("rebase-apply/applying", "git am is in progress"),
    ("rebase-merge", "a rebase is in progress"),
    ("rebase-apply", "a rebase is in progress"),
    ("MERGE_HEAD", "a merge is in progress"),
    ("CHERRY_PICK_HEAD", "a cherry-pick is in progress"),
    ("REVERT_HEAD", "a revert is in progress"),
    ("BISECT_LOG", "a bisect is in progress"),
)
MARKERS = tuple(marker for marker, _meaning in _IN_PROGRESS)


def strip_message(message: str, trailers: str, keys: Iterable[str]) -> str:
    """The message without the demanding trailer lines of its trailer block.

    `trailers` is what `git log --format=%(trailers:only,unfold)` shows for the message, so
    git decides whether the last paragraph is a trailer block; `keys` are lower-cased. A
    removed trailer takes the indented lines that continue it. Everything else stays byte for
    byte, except that a block that ends up empty takes the blank lines around it.
    """
    wanted = set(keys)
    if not demands_check(trailers, wanted):
        return message
    lines = message.splitlines(keepends=True)
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    start = end
    while start and lines[start - 1].strip():
        start -= 1
    entries = _entries(lines[start:end])
    kept = [entry for entry in entries if not is_demanding(entry[0], wanted)]
    if len(kept) == len(entries):
        return message
    if kept:
        block = [line for entry in kept for line in entry]
        return "".join(lines[:start] + block + lines[end:])
    while start and not lines[start - 1].strip():
        start -= 1
    return "".join(lines[:start])


def _entries(block: list[str]) -> list[list[str]]:
    """A trailer and the indented lines that continue it, per entry."""
    entries: list[list[str]] = []
    for line in block:
        if entries and line[:1] in (" ", "\t"):
            entries[-1].append(line)
        else:
            entries.append([line])
    return entries


def parent_shas(raw: str) -> list[str]:
    """The parents named by the headers of a commit object (`git cat-file commit`)."""
    return [
        line.split(" ", 1)[1]
        for line in _split(raw)[0].splitlines()
        if line.startswith("parent ")
    ]


def commit_message(raw: str) -> str:
    return _split(raw)[1]


def rebuild_commit(raw: str, parents: Mapping[str, str], message: str) -> str:
    """The commit object with the parents mapped, the signature dropped and a new message.

    Tree, author, committer, encoding and any other header stay exactly as they were.
    """
    headers: list[str] = []
    signature = False
    for line in _split(raw)[0].splitlines(keepends=True):
        if line[:1] == " ":  # continues the header above it
            if not signature:
                headers.append(line)
            continue
        name, _, value = line.partition(" ")
        signature = name in _SIGNATURE_HEADERS
        if signature:
            continue
        if name == "parent":
            sha = value.strip()
            line = f"parent {parents.get(sha, sha)}\n"
        headers.append(line)
    return "".join(headers) + "\n" + message


def _split(raw: str) -> tuple[str, str]:
    """Headers (with their final newline) and message of a commit object."""
    head, _, message = raw.partition("\n\n")
    return head + "\n", message


def in_progress(existing: Collection[str]) -> str | None:
    """The refusal for an operation that is still open, from the `MARKERS` that exist."""
    for marker, meaning in _IN_PROGRESS:
        if marker in existing:
            return f"{meaning}: finish or abort it first, then run strip again"
    return None


def message_detached() -> str:
    return "HEAD is detached, so there is no branch to move: check out a branch first"


def message_needs_base(default_ref: str) -> str:
    return (
        f"cannot tell which commits are yours: `{default_ref}` is missing or shares no "
        "history with HEAD; name the commit before them as `prepush-ci strip <base>`"
    )


def message_unknown_base(base: str) -> str:
    return f"`{base}` is not a commit of this repository"


def message_not_ancestor(base: str) -> str:
    return f"`{base}` is not an ancestor of HEAD, so `{base}..HEAD` holds commits that are not yours"


def report(rewritten: int, total: int, old_tip: str, new_tip: str) -> list[str]:
    """The lines `strip` prints on success."""
    first = f"strip: rewrote {rewritten} of {total} commits, old tip {old_tip}, new tip {new_tip}"
    if rewritten:
        return [first, "the next push needs `git push --force-with-lease`"]
    return [first, "nothing changed, so nothing needs pushing again"]


def message_dirty(paths: Sequence[str]) -> str:
    listed = "\n".join(f"  {path}" for path in paths)
    return (
        "the worktree is not clean, so strip could overwrite your changes; "
        f"commit, stash, or ignore these paths first:\n{listed}"
    )


def message_hidden(paths: Sequence[str]) -> str:
    listed = "\n".join(f"  {path}" for path in paths)
    return (
        "git does not report changes to these paths (assume-unchanged or skip-worktree), "
        "so strip could overwrite them; clear the flag with "
        f"`git update-index --no-assume-unchanged` or `--no-skip-worktree`:\n{listed}"
    )
