"""Decisions of `prepush-ci report`: where a result goes, what the summary says, what is refused.

No I/O: the command reads the files, the environment and the remote, and sends the requests.
"""

import base64
import json
import posixpath
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_API = "https://api.github.com"
# GitHub's own hosts: ssh.github.com is its ssh endpoint over the HTTPS port.
GITHUB_HOSTS = frozenset({"github.com", "ssh.github.com"})
CHECK_RUN_NAME = "prepush-ci / full"
STATUS_CONTEXT = "prepush-ci/full"
FROM_A_SESSION = "reported from a session"

_TREE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_REMOTE_URL = re.compile(
    r"(?:https|ssh)://(?:[^@/]*@)?(?P<host>[^/@:]+)(?::\d+)?/(?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?"
)
# A one-letter "host" is a Windows drive (`C:/work/remote`), not a server.
_SCP_URL = re.compile(
    r"(?:[^@/:\s]+@)?(?P<host>[^@/:\s]{2,}):(?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?"
)
_REPOSITORY_NAME = re.compile(r"(?P<owner>[^/\s]+)/(?P<name>[^/\s]+)")


class ReportError(Exception):
    """`report` refuses or fails; the message says why and holds no secret."""


class Malformed(ValueError):
    """A value of the command line that the parser must reject; argparse puts the flag before it."""


# --- The command line -------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    version: str


def parse_tool(text: str) -> Tool:
    name, _, version = text.partition("=")
    if not name or not version:
        raise Malformed(f"expects NAME=VERSION, got {text!r}")
    return Tool(name, version)


def parse_duration(text: str) -> int:
    if not (text.isascii() and text.isdigit()):
        raise Malformed(f"expects a whole number of seconds of 0 or more, got {text!r}")
    return int(text)


def parse_name(text: str) -> str:
    if not text:
        raise Malformed("must not be empty")
    return text


def format_duration(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [f"{hours}h"] if hours else []
    if hours or minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def tree_problem(given: str, actual: str) -> str | None:
    """Why `given` is not the tree of the commit, or None when it is. An abbreviation is not."""
    if given == actual:
        return None
    if _TREE.fullmatch(given) is None:
        return (
            f"--tree must be the full tree hash ({len(actual)} hex digits), "
            f"got {given!r}; the commit's tree is {actual}"
        )
    return f"the tree {given} was checked, but the commit's tree is {actual}"


# --- Where the result goes --------------------------------------------------------------------


def value(env: Mapping[str, str], name: str) -> str | None:
    """A variable of the environment; an empty one counts as unset (a missing secret on Actions
    arrives set but empty)."""
    return env.get(name) or None


@dataclass(frozen=True)
class Repository:
    owner: str
    name: str


@dataclass(frozen=True)
class Target:
    api_url: str
    repository: Repository


def _remote(url: str) -> tuple[str, Repository] | None:
    found = _REMOTE_URL.fullmatch(url) or _SCP_URL.fullmatch(url)
    if found is None:
        return None
    return found["host"].lower(), Repository(found["owner"], found["name"])


def target(origin_url: str | None, env: Mapping[str, str]) -> Target:
    """The API and the repository to post to: `origin` names the repository when it can (a host
    other than GitHub's only when `GITHUB_API_URL` says where its API is), `GITHUB_REPOSITORY`
    when it cannot. The refusal never quotes the URL: it may carry a token."""
    api = value(env, "GITHUB_API_URL")
    remote = None if origin_url is None else _remote(origin_url)
    if remote is not None and (remote[0] in GITHUB_HOSTS or api is not None):
        return Target((api or DEFAULT_API).rstrip("/"), remote[1])
    named = value(env, "GITHUB_REPOSITORY")
    if named is None:
        raise ReportError(
            "no repository could be read from `origin`; "
            "set GITHUB_REPOSITORY to <owner>/<repo> to name it"
        )
    found = _REPOSITORY_NAME.fullmatch(named)
    if found is None:
        raise ReportError(
            f"GITHUB_REPOSITORY is {named!r}, which is not of the form <owner>/<repo>"
        )
    return Target(
        (api or DEFAULT_API).rstrip("/"), Repository(found["owner"], found["name"])
    )


@dataclass(frozen=True)
class AppCredentials:
    app_id: str
    key: str


@dataclass(frozen=True)
class TokenCredentials:
    token: str


def credentials(env: Mapping[str, str]) -> AppCredentials | TokenCredentials:
    """The app when it is configured, else a token; half an app is an error, never a fallback."""
    app_id = value(env, "PREPUSH_CI_APP_ID")
    key = value(env, "PREPUSH_CI_APP_KEY")
    if app_id is not None and key is not None:
        return AppCredentials(app_id, key)
    if app_id is None and key is None:
        token = value(env, "GITHUB_TOKEN") or value(env, "GH_TOKEN")
        if token is not None:
            return TokenCredentials(token)
        raise ReportError(
            "no credentials: set PREPUSH_CI_APP_ID and PREPUSH_CI_APP_KEY "
            "to post a check run, or GITHUB_TOKEN or GH_TOKEN to post a commit status"
        )
    missing = "PREPUSH_CI_APP_KEY" if key is None else "PREPUSH_CI_APP_ID"
    raise ReportError(
        f"the app is half configured: {missing} is not set "
        "(PREPUSH_CI_APP_ID and PREPUSH_CI_APP_KEY go together)"
    )


def redact(text: str, secrets: tuple[str, ...]) -> str:
    """`text` without any of the secrets (the longest first, so a part never survives a whole).
    An answer quoted with its white space folded to single spaces is cleaned as well."""
    forms = {
        form
        for secret in secrets
        for form in (secret, " ".join(secret.split()))
        if form.strip()
    }
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, "***")
    return text


# --- What the files say -----------------------------------------------------------------------


@dataclass(frozen=True)
class Counts:
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(
            self.passed + other.passed,
            self.failed + other.failed,
            self.skipped + other.skipped,
        )

    def line(self) -> str:
        return f"{self.passed} passed, {self.failed} failed, {self.skipped} skipped"


def count_junit(data: bytes, name: str) -> Counts:
    """The test cases of a JUnit file, by what each case holds, whatever the nesting of suites:
    pytest and `node --test` give the same numbers for the same tests."""
    counts = Counts()
    for case in junit_cases(data, name):
        counts += case_counts(case)
    return counts


def junit_cases(data: bytes, name: str) -> list[ET.Element]:
    """The `testcase` elements of a JUnit file, whatever the nesting of suites."""
    return list(_junit_root(data, name).iter("testcase"))


def case_counts(case: ET.Element) -> Counts:
    """One case as a count: failed when it holds a failure or an error, else skipped, else passed."""
    if case.find("failure") is not None or case.find("error") is not None:
        return Counts(failed=1)
    if case.find("skipped") is not None:
        return Counts(skipped=1)
    return Counts(passed=1)


@dataclass(frozen=True)
class Failure:
    """One failure the files report: a failed test case, a ruff error or a mypy error. `path` and
    `line` (1-based, relative to the top of the worktree) are None for a case with no location.
    `case` is the label of the test case (see `case_label`), which titles its annotation."""

    tool: str
    text: str
    path: str | None = None
    line: int | None = None
    case: str = ""


def _junit_root(data: bytes, name: str) -> ET.Element:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ReportError(f"{name} is not JUnit XML: {error}") from error
    if root.tag not in ("testsuites", "testsuite"):
        raise ReportError(
            f"{name} is not JUnit XML: it holds <{root.tag}>, not <testsuites>"
        )
    return root


_MAX_LINE_DIGITS = 9


def _zero_based_line(line: str | None) -> int | None:
    """The number in a case's `line` attribute, or None when it is no line: not whole digits, or
    more than 9 of them (the bound of a frame number, #235). A longer value is garbled, and one
    near Python's limit on the digits of an integer (4300) cannot even be printed after the +1."""
    if line is None or not (line.isascii() and line.isdigit()):
        return None
    if len(line) > _MAX_LINE_DIGITS:
        return None
    return int(line)


def _failing_line(file: str, text: str) -> int | None:
    """The line number of the last line of `text` that begins, at its first column, with
    `<file>:<n>:`: the deepest frame of the traceback in the file of the case. A number of more
    than nine digits (`int` refuses it past 4300) or a number of 0 is no line of a traceback."""
    numbers = re.findall(
        rf"^{re.escape(file)}:([0-9]{{1,9}}):", text, flags=re.MULTILINE
    )
    frames = [int(number) for number in numbers if int(number) > 0]
    return frames[-1] if frames else None


def _module(file: str | None, top: str) -> str | None:
    """The module of a test file: its path in the worktree without the extension, a dot for each
    `/`; None for a case without a file, or with one outside the worktree."""
    if not file:
        return None
    try:
        path = relative_path(file, top)
    except ReportError:
        return None
    return posixpath.splitext(path)[0].replace("/", ".")


def case_label(case: ET.Element, top: str) -> str:
    """The name of a test case, joined with a `.` to what its `classname` adds to the module of
    its `file` (the class of a method). A `classname` that is not under that module is kept whole
    in front of the name: nothing it says is lost."""
    name, classname = case.get("name", ""), case.get("classname")
    if not classname:
        return name
    module = _module(case.get("file"), top)
    if classname == module:
        return name
    if module is not None and classname.startswith(module + "."):
        classname = classname[len(module) + 1 :]
    return f"{classname}.{name}"


def junit_failures(data: bytes, name: str, top: str) -> list[Failure]:
    """The failed cases of a JUnit file. A case with a `file` and a `line` sits on that file, on
    the last line its failure text names in that file (see `_failing_line`), else at `line` + 1:
    pytest writes the line 0-based. Any other case has the text of its name only."""
    failures = []
    for case in _junit_root(data, name).iter("testcase"):
        found = case.find("failure")
        if found is None:
            found = case.find("error")
        if found is None:
            continue
        file, line = case.get("file"), _zero_based_line(case.get("line"))
        label = case_label(case, top)
        if file and line is not None:
            message, detail = found.get("message") or "", found.text or ""
            failures.append(
                Failure(
                    "pytest",
                    message or detail.strip() or label,
                    relative_path(file, top),
                    _failing_line(file, f"{message}\n{detail}") or line + 1,
                    label,
                )
            )
        else:
            failures.append(Failure("pytest", label, case=label))
    return failures


_DRIVE = re.compile(r"[A-Za-z]:/")


def _drive_lowered(path: str) -> str:
    return path[0].lower() + path[1:] if _DRIVE.match(path) else path


def relative_path(path: str, top: str) -> str:
    """`path` as GitHub knows it: relative to `top`, the top of the worktree, with `/` for every
    separator (a tool on Windows writes `\\` and `C:\\`). A path that leaves the worktree, or
    names no file in it, is refused."""
    slashed = path.replace("\\", "/")
    if slashed.startswith("/") or _DRIVE.match(slashed):
        prefix = _drive_lowered(top.replace("\\", "/").rstrip("/") + "/")
        if not _drive_lowered(slashed).startswith(prefix):
            raise ReportError(f"{path!r} is not a file inside the worktree")
        slashed = slashed[len(prefix) :]
    parts: list[str] = []
    for part in slashed.split("/"):
        if part == "..":
            if not parts:
                raise ReportError(f"{path!r} is not a file inside the worktree")
            parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    if not parts:
        raise ReportError(f"{path!r} is not a file inside the worktree")
    return "/".join(parts)


def _ruff_failure(entry: object, top: str) -> Failure:
    if not isinstance(entry, dict):
        raise ValueError("not an object")
    row = entry["location"]["row"]
    code, message, filename = entry["code"], entry["message"], entry["filename"]
    if not all(isinstance(text, str) for text in (code, message, filename)):
        raise ValueError("not text")
    if not isinstance(row, int) or isinstance(row, bool):
        raise ValueError("not a row")
    return Failure(
        "ruff", f"{code} {message}", relative_path(filename, top), max(row, 1)
    )


def ruff_failures(text: str, name: str, top: str) -> list[Failure]:
    """The errors of the output of `ruff check --output-format json`."""
    try:
        entries = json.loads(text)
        if not isinstance(entries, list):
            raise ValueError("not an array")
        return [_ruff_failure(entry, top) for entry in entries]
    except (ValueError, KeyError, TypeError) as error:
        raise ReportError(
            f"{name} is not the output of `ruff check --output-format json`: "
            "expected an array of errors with filename, location.row, code and message"
        ) from error


_MYPY_ERROR = re.compile(
    r"(?P<path>(?:(?!: (?:note|error): ).)+?)(?::(?P<line>\d+)(?::\d+){0,3})?: error: (?P<message>.*)"
)
_MYPY_SUMMARY = re.compile(
    r"(?:Success: no issues found|Found \d+ errors?)", re.MULTILINE
)


def _mypy_line(line: str | None) -> int | None:
    """The line of an error, or None when it has none or `int` cannot take it: a value past
    Python's limit on the digits of an integer (4300) is garbled, not a place."""
    if line is None:
        return None
    try:
        return max(int(line), 1)
    except ValueError:
        return None


def mypy_failures(text: str, name: str, top: str) -> list[Failure]:
    """The `error:` lines of the output of mypy; its `note:` lines are context. An error with no
    line is a failure without a place."""
    if _MYPY_SUMMARY.search(text) is None:
        raise ReportError(
            f"{name} is not the output of mypy: "
            "it has neither `Success: no issues found` nor `Found <n> errors`"
        )
    failures = []
    for line in text.splitlines():
        found = _MYPY_ERROR.fullmatch(line)
        if found is None:
            continue
        place = _mypy_line(found["line"])
        if place is None:
            failures.append(Failure("mypy", f"{found['path']}: {found['message']}"))
        else:
            failures.append(
                Failure(
                    "mypy",
                    found["message"],
                    relative_path(found["path"], top),
                    place,
                )
            )
    return failures


def coverage_display(text: str, name: str) -> str:
    """`totals.percent_covered_display` of a coverage.py `coverage.json`, without the `%`."""
    try:
        shown = json.loads(text)["totals"]["percent_covered_display"]
    except (ValueError, KeyError, TypeError) as error:
        raise ReportError(
            f"{name} is not the coverage.json of coverage.py: "
            "it has no totals.percent_covered_display"
        ) from error
    if not isinstance(shown, str):
        raise ReportError(
            f"{name} is not the coverage.json of coverage.py: "
            "totals.percent_covered_display is not text"
        )
    return shown


def contradiction(result: str, counts: Counts | None) -> str | None:
    """Why the result cannot stand with the counts: a `passed` run with failing tests. A `failed`
    run with none is fine, for lint or types can fail alone."""
    if result == "passed" and counts is not None and counts.failed:
        return (
            f"--result passed contradicts the JUnit files, which hold {counts.failed} "
            "failing test cases"
        )
    return None


def file_contradiction(result: str, name: str, failures: list[Failure]) -> str | None:
    """Why a `passed` result cannot stand with the errors a ruff or mypy file holds."""
    if result == "passed" and failures:
        return (
            f"--result passed contradicts {name}, which holds {len(failures)} "
            f"{failures[0].tool} errors"
        )
    return None


# --- What is posted ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Facts:
    sha: str
    tree: str
    check: str
    preflight: str | None
    tools: tuple[Tool, ...]
    system: str
    duration: int | None
    counts: Counts | None
    coverage: str | None
    failures: tuple[Failure, ...] = ()


ESCAPED_PIPE = "\\|"


def code_span(text: str) -> str:
    """`text` as one Markdown code span, whatever backticks and line ends it holds."""
    one_line = " ".join(text.split())
    longest = max((len(run) for run in re.findall(r"`+", one_line)), default=0)
    fence = "`" * (longest + 1)
    return f"{fence} {one_line} {fence}"


MAX_ANNOTATION_MESSAGE = 32_000


def annotation(failure: Failure) -> dict[str, object]:
    """The annotation of a failure that has a place; a failed case titles it with its label, and
    the message is cut far below GitHub's 64 KB."""
    return {
        "path": failure.path,
        "start_line": failure.line,
        "end_line": failure.line,
        "annotation_level": "failure",
        "title": f"{failure.tool}: {_cut(failure.case)}"
        if failure.case
        else failure.tool,
        "message": failure.text[:MAX_ANNOTATION_MESSAGE],
    }


def annotations(failures: list[Failure]) -> list[dict[str, object]]:
    """One annotation per failure that has a place, in order."""
    return [annotation(failure) for failure in failures if failure.path is not None]


ANNOTATIONS_PER_REQUEST = 50


def annotation_batches(failures: list[Failure]) -> list[list[dict[str, object]]]:
    """The annotations in requests of at most 50 each (GitHub's limit), in order."""
    placed = annotations(failures)
    return [
        placed[start : start + ANNOTATIONS_PER_REQUEST]
        for start in range(0, len(placed), ANNOTATIONS_PER_REQUEST)
    ]


def title(result: str, counts: Counts | None) -> str:
    if counts is not None:
        return counts.line()
    return "Passed" if result == "passed" else "Failed"


MAX_LISTED = 20
MAX_TEXT = 200


def _cut(text: str) -> str:
    """`text` with its white space merged, cut at 200 characters with `…` as the 200th."""
    merged = " ".join(text.split())
    return merged if len(merged) <= MAX_TEXT else merged[: MAX_TEXT - 1] + "…"


def _listed_text(text: str) -> str:
    """The first line of a message, cut as `_cut` does."""
    return _cut(next((line for line in text.splitlines() if line.strip()), ""))


def _failure_line(failure: Failure) -> str:
    where = (
        ""
        if failure.path is None
        else f" {code_span(f'{failure.path}:{failure.line}')}"
    )
    label = f" {code_span(_cut(failure.case))}" if failure.case else ""
    text = (
        ""
        if failure.case and failure.path is None
        else f" {code_span(_listed_text(failure.text))}"
    )
    return f"- {failure.tool}{where}{label}{text}"


def _failures_section(failures: tuple[Failure, ...]) -> str:
    """A list, not a table: a `|` in a message would split the cell of a table."""
    lines = [_failure_line(failure) for failure in failures[:MAX_LISTED]]
    if len(failures) > MAX_LISTED:
        lines.append(f"- and {len(failures) - MAX_LISTED} more")
    return "### Failures\n\n" + "\n".join(lines) + "\n\n"


def _table(rows: list[tuple[str, str]]) -> str:
    # A pipe ends a table cell, also inside a code span: GitHub reads `\|` as the pipe.
    table = "\n".join(
        f"| {label} | {text.replace('|', ESCAPED_PIPE)} |" for label, text in rows
    )
    return f"| Fact | Value |\n| --- | --- |\n{table}\n"


def _what_ran(facts: Facts) -> list[tuple[str, str]]:
    return [
        ("Commit", code_span(facts.sha)),
        ("Tree", code_span(facts.tree)),
        ("Check", code_span(facts.check)),
        (
            "Preflight",
            "none" if facts.preflight is None else code_span(facts.preflight),
        ),
    ]


def summary(facts: Facts) -> str:
    rows = _what_ran(facts)
    if facts.tools:
        rows.append(("Tools", ", ".join(f"{t.name} {t.version}" for t in facts.tools)))
    rows.append(("System", facts.system))
    if facts.duration is not None:
        rows.append(("Duration", format_duration(facts.duration)))
    if facts.counts is not None:
        rows.append(("Tests", facts.counts.line()))
    if facts.coverage is not None:
        rows.append(("Coverage", f"{facts.coverage}%"))
    failures = _failures_section(facts.failures) if facts.failures else ""
    return (
        f"{failures}"
        f"Result {FROM_A_SESSION}: `prepush-ci report` posted it for the tree below, "
        "which the session says it checked. GitHub did not run the check.\n\n"
        f"{_table(rows)}"
    )


def markdown_name_problem(name: str) -> str | None:
    """Why `name` cannot go into the hidden marker, or None: `--` or a line break would end the
    comment early."""
    if "--" in name or "\n" in name or "\r" in name:
        return "--name must not hold `--` or a line break with --markdown"
    return None


def markdown(name: str, facts: Facts, result: str) -> str:
    """The summary of the check run under a hidden marker that names the check, a title and a
    line that names the commit, without a final newline."""
    head = (
        f"<!-- prepush-ci:{name} -->\n"
        f"### {name}: {title(result, facts.counts)}\n"
        f"Commit {facts.sha}\n\n"
    )
    return (head + summary(facts)).rstrip("\n")


def status_description(facts: Facts) -> str:
    parts = [] if facts.counts is None else [facts.counts.line()]
    if facts.coverage is not None:
        parts.append(f"{facts.coverage}%")
    parts.append(f"tree {facts.tree[:7]}")
    return f"{', '.join(parts)} ({FROM_A_SESSION})"


def _output(
    facts: Facts, result: str, counts: Counts | None, batch: list[dict[str, object]]
) -> dict[str, object]:
    output: dict[str, object] = {
        "title": title(result, counts),
        "summary": summary(facts),
    }
    if batch:
        output["annotations"] = batch
    return output


def check_run_body(
    name: str, facts: Facts, result: str, counts: Counts | None
) -> dict[str, object]:
    """The request that creates the completed check run, with the first 50 annotations."""
    batches = annotation_batches(list(facts.failures))
    return {
        "name": name,
        "head_sha": facts.sha,
        "status": "completed",
        "conclusion": "success" if result == "passed" else "failure",
        "output": _output(facts, result, counts, batches[0] if batches else []),
    }


def completion_body(
    name: str, facts: Facts, result: str, counts: Counts | None
) -> dict[str, object]:
    """The request that completes a run in progress: the body of a new run, without the commit
    the run already has."""
    body = check_run_body(name, facts, result, counts)
    del body["head_sha"]
    return body


def later_batches_bodies(
    facts: Facts, result: str, counts: Counts | None
) -> list[dict[str, object]]:
    """The updates of the same run that carry the annotations after the first 50, each with the
    same title and summary."""
    return [
        {"output": _output(facts, result, counts, batch)}
        for batch in annotation_batches(list(facts.failures))[1:]
    ]


STARTED = "started"


def started_at(now: int) -> str:
    """`now`, in seconds since the epoch, as the `started_at` GitHub reads."""
    return datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def started_body(name: str, facts: Facts, now: int) -> dict[str, object]:
    """The request that creates a check run in progress."""
    text = (
        f"The check is running; the result will be {FROM_A_SESSION} with "
        "`prepush-ci report` for the tree below. GitHub is not running the check.\n\n"
        f"{_table(_what_ran(facts))}"
    )
    return {
        "name": name,
        "head_sha": facts.sha,
        "status": "in_progress",
        "started_at": started_at(now),
        "output": {"title": "Running", "summary": text},
    }


def started_update_body(now: int) -> dict[str, object]:
    """The request that restarts a run already in progress."""
    return {"status": "in_progress", "started_at": started_at(now)}


def started_status_body(name: str, facts: Facts) -> dict[str, object]:
    return {
        "state": "pending",
        "context": name,
        "description": status_description(facts),
    }


def status_body(name: str, facts: Facts, result: str) -> dict[str, object]:
    return {
        "state": "success" if result == "passed" else "failure",
        "context": name,
        "description": status_description(facts),
    }


# --- Authenticating as the app ----------------------------------------------------------------


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def jwt_signing_input(app_id: str, now: int) -> bytes:
    """The header and the claims of the token the app signs: issued a minute ago, valid for nine
    minutes (GitHub accepts ten at most, and a clock that is a little off)."""
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {"iat": now - 60, "exp": now + 540, "iss": app_id}
    parts = (
        _base64url(json.dumps(part, separators=(",", ":")).encode("ascii"))
        for part in (header, claims)
    )
    return ".".join(parts).encode("ascii")


def jwt(signing_input: bytes, signature: bytes) -> str:
    return f"{signing_input.decode('ascii')}.{_base64url(signature)}"
