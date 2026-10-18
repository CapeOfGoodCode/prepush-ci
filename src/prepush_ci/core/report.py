"""Decisions of `prepush-ci report`: where a result goes, what the summary says, what is refused.

No I/O: the command reads the files, the environment and the remote, and sends the requests.
"""

import base64
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_API = "https://api.github.com"
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
    other than github.com only when `GITHUB_API_URL` says where its API is), `GITHUB_REPOSITORY`
    when it cannot. The refusal never quotes the URL: it may carry a token."""
    api = value(env, "GITHUB_API_URL")
    remote = None if origin_url is None else _remote(origin_url)
    if remote is not None and (remote[0] == "github.com" or api is not None):
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
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ReportError(f"{name} is not JUnit XML: {error}") from error
    if root.tag not in ("testsuites", "testsuite"):
        raise ReportError(
            f"{name} is not JUnit XML: it holds <{root.tag}>, not <testsuites>"
        )
    counts = Counts()
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            counts += Counts(failed=1)
        elif case.find("skipped") is not None:
            counts += Counts(skipped=1)
        else:
            counts += Counts(passed=1)
    return counts


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


def code_span(text: str) -> str:
    """`text` as one Markdown code span, whatever backticks and line ends it holds."""
    one_line = " ".join(text.split())
    longest = max((len(run) for run in re.findall(r"`+", one_line)), default=0)
    fence = "`" * (longest + 1)
    return f"{fence} {one_line} {fence}"


def title(result: str, counts: Counts | None) -> str:
    if counts is not None:
        return counts.line()
    return "Passed" if result == "passed" else "Failed"


def summary(facts: Facts) -> str:
    rows = [
        ("Commit", code_span(facts.sha)),
        ("Tree", code_span(facts.tree)),
        ("Check", code_span(facts.check)),
        (
            "Preflight",
            "none" if facts.preflight is None else code_span(facts.preflight),
        ),
    ]
    if facts.tools:
        rows.append(("Tools", ", ".join(f"{t.name} {t.version}" for t in facts.tools)))
    rows.append(("System", facts.system))
    if facts.duration is not None:
        rows.append(("Duration", format_duration(facts.duration)))
    if facts.counts is not None:
        rows.append(("Tests", facts.counts.line()))
    if facts.coverage is not None:
        rows.append(("Coverage", f"{facts.coverage}%"))
    table = "\n".join(f"| {label} | {text} |" for label, text in rows)
    return (
        f"Result {FROM_A_SESSION}: `prepush-ci report` posted it for the tree below, "
        "which the session says it checked. GitHub did not run the check.\n\n"
        f"| | |\n| --- | --- |\n{table}\n"
    )


def status_description(facts: Facts) -> str:
    parts = [] if facts.counts is None else [facts.counts.line()]
    if facts.coverage is not None:
        parts.append(f"{facts.coverage}%")
    parts.append(f"tree {facts.tree[:7]}")
    return f"{', '.join(parts)} ({FROM_A_SESSION})"


def check_run_body(
    name: str, facts: Facts, result: str, counts: Counts | None
) -> dict[str, object]:
    return {
        "name": name,
        "head_sha": facts.sha,
        "status": "completed",
        "conclusion": "success" if result == "passed" else "failure",
        "output": {"title": title(result, counts), "summary": summary(facts)},
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
