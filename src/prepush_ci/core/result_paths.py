"""Which named result files the tool may delete before the check: what git lists decides, never
the spelling of the path, so one rule holds on a case-folding file system and on a case-sensitive
one alike."""

GITLINK = "160000"
TRACKED = "the file is tracked"
ANOTHER_REPOSITORY = "the file is in another repository"


def components(path: str) -> list[str]:
    """The components of a path written with `/`, as the file system reads them: a `.` and an empty
    component (`a//b`, `a/b/`) name the directory they are in, so they are dropped. The one place
    that reads a spelling, so every comparison sees the same path."""
    return [part for part in path.split("/") if part not in ("", ".")]


def fold(path: str) -> str:
    """The path as a file system that folds case and drops trailing dots and spaces sees it."""
    return "/".join(part.rstrip(". ").lower() for part in path.split("/"))


def listed(*listings: str) -> tuple[frozenset[str], frozenset[str]]:
    """The folded paths and the folded gitlinks (submodules) of listings from `git ls-tree -r -z`
    and `git ls-files -s -z`: entries end at a NUL, and hold the mode, the rest, a tab and the path."""
    paths: set[str] = set()
    gitlinks: set[str] = set()
    for listing in listings:
        for entry in listing.split("\0"):
            meta, tab, path = entry.partition("\t")
            if not tab:
                continue
            paths.add(fold(path))
            if meta.split(" ", 1)[0] == GITLINK:
                gitlinks.add(fold(path))
    return frozenset(paths), frozenset(gitlinks)


def tracked_reason(
    path: str, paths: frozenset[str], gitlinks: frozenset[str]
) -> str | None:
    """Why git's own files forbid deleting `path` (written with `/`), or None: it is under a
    gitlink, so another repository holds it, or it is a path of `HEAD` or the index."""
    parts = components(path)
    if any(fold("/".join(parts[:end])) in gitlinks for end in range(1, len(parts))):
        return ANOTHER_REPOSITORY
    if fold("/".join(parts)) in paths:
        return TRACKED
    return None
