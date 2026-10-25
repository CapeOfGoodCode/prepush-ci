"""The result files a check writes: deleted before it runs, so that none from an earlier run is
read, and read after it passes, into the facts of the run."""

import os
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TypeVar

from prepush_ci import text_io
from prepush_ci.core import run_facts
from prepush_ci.core.config import Config, Results
from prepush_ci.core.result_paths import (
    ANOTHER_REPOSITORY,
    components,
    listed,
    tracked_reason,
)
from prepush_ci.core.run_facts import (
    FactError,
    RunFacts,
    message_left_alone,
    message_no_fact,
)
from prepush_ci.git import tracked_listings, tree_files

T = TypeVar("T")
# What `clear` leaves alone, as the key of the config and the entry that names it
Named = tuple[str, str]

IS_A_LINK = "it is a link"
LINK_ON_THE_WAY = "a link is on the way"
IS_A_DIRECTORY = "it is a directory"
NOT_REGULAR = "it is not a regular file"
NOT_DELETED = "the deletion failed"
NOT_WRITTEN = "the check did not write it"
NOT_READ = "it could not be read"
NOT_UTF8 = "it is not UTF-8 text"


def named(results: Results) -> list[Named]:
    """Every file `results` names, with the key it is named by."""
    files = [("results.junit", entry) for entry in results.junit]
    for key in ("coverage", "ruff", "mypy"):
        if (entry := getattr(results, key)) is not None:
            files.append((f"results.{key}", entry))
    return files


def clear(config: Config, root: Path) -> frozenset[Named]:
    """Delete each file the config names that the tool may delete, before the check starts, and
    return the ones it left alone (a line on standard error says why). Nothing is deleted when the
    cache is off: no pass is recorded, so there are no facts to keep clean."""
    if not config.cache or config.results is None:
        return frozenset()
    files = named(config.results)
    if not files:
        return frozenset()
    paths, gitlinks = listed(*tracked_listings(root))
    left: set[Named] = set()
    for key, entry in files:
        target = root.joinpath(*components(entry))
        if not os.path.lexists(target):
            continue
        why = _why_not_deleted(root, entry, paths, gitlinks) or _delete(target)
        if why is not None:
            print(message_left_alone(key, entry, why), file=sys.stderr)
            left.add((key, entry))
    return frozenset(left)


def _why_not_deleted(
    root: Path, entry: str, paths: frozenset[str], gitlinks: frozenset[str]
) -> str | None:
    """Why the file that exists at `entry` is not the tool's to delete, or None."""
    parts = components(entry)
    target = root.joinpath(*parts)
    for end in range(1, len(parts)):
        if os.path.lexists(root.joinpath(*parts[:end], ".git")):
            return ANOTHER_REPOSITORY
    if target.is_symlink():
        return IS_A_LINK
    if target.is_dir():
        return IS_A_DIRECTORY
    if not target.is_file():
        return NOT_REGULAR
    if (why := tracked_reason("/".join(parts), paths, gitlinks)) is not None:
        return why
    # A symbolic link or a junction on the way: the real path is not the one the entry spells.
    expected = os.path.join(os.path.realpath(root), *parts)
    if os.path.normcase(os.path.realpath(target)) != os.path.normcase(expected):
        return LINK_ON_THE_WAY
    return None


def _delete(target: Path) -> str | None:
    try:
        target.unlink()
    except OSError:
        return NOT_DELETED
    return None


def gather(
    config: Config, root: Path, tree: str, seconds: int, left: frozenset[Named]
) -> RunFacts:
    """The facts of a run that passed: its duration, and what each named file says that the check
    wrote and the tool did not leave alone. A file that gives no fact costs one line and nothing
    else."""
    results = config.results
    if results is None:
        return run_facts.run_facts(seconds, [])
    reader = _Reader(root, left)
    tree_paths = tree_files(root, tree) if results.junit else frozenset[str]()
    tallies = [
        tally
        for entry in results.junit
        if (
            tally := reader.read(
                "results.junit",
                entry,
                partial(
                    run_facts.junit_tally,
                    name=entry,
                    top=str(root),
                    in_tree=tree_paths.__contains__,
                ),
            )
        )
        is not None
    ]
    coverage = results.coverage
    return run_facts.run_facts(
        seconds,
        tallies,
        coverage=None
        if coverage is None
        else reader.read_decoded(
            "results.coverage", coverage, partial(run_facts.coverage_of, name=coverage)
        ),
        ruff=None
        if results.ruff is None
        else reader.read_decoded("results.ruff", results.ruff, run_facts.ruff_errors),
        mypy=None
        if results.mypy is None
        else reader.read_decoded("results.mypy", results.mypy, run_facts.mypy_errors),
    )


class _Reader:
    """Reads the files a run wrote; a file that cannot give a fact is one line on standard error."""

    def __init__(self, root: Path, left: frozenset[Named]) -> None:
        self.root = root
        self.left = left

    def read(self, key: str, entry: str, parse: Callable[[bytes], T]) -> T | None:
        if (
            key,
            entry,
        ) in self.left:  # already reported, and not the tool's file to read
            return None
        try:
            data = self.root.joinpath(*components(entry)).read_bytes()
        except FileNotFoundError:
            return self._skip(key, entry, NOT_WRITTEN)
        except OSError:
            return self._skip(key, entry, NOT_READ)
        try:
            return parse(data)
        except FactError as error:
            return self._skip(key, entry, str(error))

    def read_decoded(self, key: str, entry: str, parse: Callable[[str], T]) -> T | None:
        def parse_bytes(data: bytes) -> T:
            try:
                text = text_io.decode_utf8(data, entry)
            except text_io.NotUtf8 as error:
                raise FactError(NOT_UTF8) from error
            return parse(text.removeprefix("\ufeff"))

        return self.read(key, entry, parse_bytes)

    @staticmethod
    def _skip(key: str, entry: str, why: str) -> None:
        print(message_no_fact(key, entry, why), file=sys.stderr)
