"""The facts of a run of the check: what the files it wrote say, kept as numbers, and the one line
they are recorded as.

No I/O: the command reads the files and the tree, and hands their text over. Nothing the check
printed is kept: only numbers, and the paths of test files that are files of the checked tree.
"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from prepush_ci.core import report
from prepush_ci.core.report import Counts, ReportError

MAX_FILES = 50
VERSION = 1
# ASCII digits with at most one `.` and a digit on each side of it
_COVERAGE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
# the bound keeps `int` away from a number nobody printed
_MYPY_FOUND = re.compile(r"^Found ([0-9]{1,9}) errors?", re.MULTILINE)


class FactError(Exception):
    """A file gives no fact; the message says why in a few words and holds none of its content."""


@dataclass(frozen=True)
class Tally:
    """The cases of JUnit files: per test file of the tree, and the rest."""

    files: dict[str, Counts] = field(default_factory=dict)
    other: Counts = Counts()

    def __add__(self, more: "Tally") -> "Tally":
        files = dict(self.files)
        for name, counts in more.files.items():
            files[name] = files.get(name, Counts()) + counts
        return Tally(files, self.other + more.other)


@dataclass(frozen=True)
class RunFacts:
    """What a run says: the seconds of the check, and what the named files add to it. `files` has
    at most `MAX_FILES` test files, the largest first; `other` holds every case that is not in
    one of them."""

    seconds: int
    tests: Counts | None = None
    files: tuple[tuple[str, Counts], ...] = ()
    other: Counts | None = None
    coverage: str | None = None
    ruff: int | None = None
    mypy: int | None = None


def junit_tally(
    data: bytes, name: str, top: str, in_tree: Callable[[str], bool]
) -> Tally:
    """The cases of a JUnit file by the `file` they name, taken from `top` as `report` takes
    paths: a case whose file is not a path of the tree (`in_tree`), or names none, goes under
    `other`, for a name that came out of a result file is output of the check."""
    files: dict[str, Counts] = {}
    other = Counts()
    try:
        cases = report.junit_cases(data, name)
    except ReportError as error:
        raise FactError("it is not JUnit XML") from error
    for case in cases:
        counts = report.case_counts(case)
        path = _tree_path(case.get("file"), top, in_tree)
        if path is None:
            other += counts
        else:
            files[path] = files.get(path, Counts()) + counts
    return Tally(files, other)


def _tree_path(
    file: str | None, top: str, in_tree: Callable[[str], bool]
) -> str | None:
    if file is None:
        return None
    try:
        path = report.relative_path(file, top)
    except ReportError:
        return None
    return path if in_tree(path) else None


def run_facts(
    seconds: int,
    junit: Sequence[Tally],
    coverage: str | None = None,
    ruff: int | None = None,
    mypy: int | None = None,
) -> RunFacts:
    """The facts of a run from what was read; `junit` has one tally per JUnit file that could be
    read, none when nothing was."""
    if not junit:
        return RunFacts(seconds, coverage=coverage, ruff=ruff, mypy=mypy)
    total = sum(junit[1:], junit[0])
    ranked = sorted(total.files.items(), key=lambda item: (-_cases(item[1]), item[0]))
    kept, rest = ranked[:MAX_FILES], ranked[MAX_FILES:]
    other = sum((counts for _, counts in rest), total.other)
    tests = sum((counts for _, counts in ranked), total.other)
    return RunFacts(
        seconds,
        tests=tests,
        files=tuple(kept),
        other=other if _cases(other) else None,
        coverage=coverage,
        ruff=ruff,
        mypy=mypy,
    )


def _cases(counts: Counts) -> int:
    return counts.passed + counts.failed + counts.skipped


def coverage_of(text: str, name: str) -> str:
    """The coverage of a coverage.py `coverage.json`, as the file wrote it, when it is digits with
    at most one `.` and a number from 0 to 100; `float()` would take `nan`, `1e3` and `-5`."""
    try:
        shown = report.coverage_display(text, name)
    except ReportError as error:
        raise FactError("it is not the coverage.json of coverage.py") from error
    if not is_coverage(shown):
        raise FactError("its coverage is not a number from 0 to 100")
    return shown


def is_coverage(text: str) -> bool:
    return _COVERAGE.fullmatch(text) is not None and float(text) <= 100


def ruff_errors(text: str) -> int:
    """The number of entries of the array of `ruff check --output-format json`."""
    try:
        entries = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise FactError(
            "it is not the output of `ruff check --output-format json`"
        ) from error
    if not isinstance(entries, list):
        raise FactError("it is not the output of `ruff check --output-format json`")
    return len(entries)


def mypy_errors(text: str) -> int:
    """The number in the `Found <n> errors` line of mypy, or 0 for `Success`."""
    found = _MYPY_FOUND.search(text)
    if found is not None:
        return int(found[1])
    if "Success: no issues found" in text:
        return 0
    raise FactError("it is not the output of mypy")


def message_left_alone(key: str, entry: str, why: str) -> str:
    return f"prepush-ci: `{key}` ({entry!r}) is left alone: {why}"


def message_no_fact(key: str, entry: str, why: str) -> str:
    return f"prepush-ci: `{key}` ({entry!r}) gives no fact: {why}"


# --- The line in the result commit ------------------------------------------------------------


def _counts_json(counts: Counts) -> list[int]:
    return [counts.passed, counts.failed, counts.skipped]


def to_line(facts: RunFacts) -> str:
    """The facts as one line of JSON that is plain ASCII, so no name can end it or fail to encode."""
    data: dict[str, Any] = {"v": VERSION, "seconds": facts.seconds}
    if facts.tests is not None:
        data["tests"] = _counts_json(facts.tests)
    if facts.files:
        data["files"] = [[name, *_counts_json(c)] for name, c in facts.files]
    if facts.other is not None:
        data["other"] = _counts_json(facts.other)
    for key in ("coverage", "ruff", "mypy"):
        if (value := getattr(facts, key)) is not None:
            data[key] = value
    return json.dumps(data, separators=(",", ":"))


def from_line(line: str) -> RunFacts | None:
    """The facts a line holds, or None for anything that is not exactly what `to_line` writes: a
    result ref can come from `origin`, so its line is as untrusted as any input."""
    try:
        data = json.loads(line)
        if not isinstance(data, dict) or data.get("v") != VERSION:
            return None
        return _facts_of(data)
    except (ValueError, RecursionError):
        return None


def _count(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("not a count")
    return value


def _counts(value: Any) -> Counts:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("not three counts")
    return Counts(*(_count(item) for item in value))


def _file(value: Any) -> tuple[str, Counts]:
    if not isinstance(value, list) or len(value) != 4 or not isinstance(value[0], str):
        raise ValueError("not a file")
    return value[0], _counts(value[1:])


def _facts_of(data: dict[str, Any]) -> RunFacts:
    files = data.get("files", [])
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise ValueError("not a list of files")
    coverage = data.get("coverage")
    if coverage is not None and not (
        isinstance(coverage, str) and is_coverage(coverage)
    ):
        raise ValueError("not a coverage")
    return RunFacts(
        seconds=_count(data.get("seconds")),
        tests=_counts(data["tests"]) if "tests" in data else None,
        files=tuple(_file(item) for item in files),
        other=_counts(data["other"]) if "other" in data else None,
        coverage=coverage,
        ruff=_count(data["ruff"]) if "ruff" in data else None,
        mypy=_count(data["mypy"]) if "mypy" in data else None,
    )
