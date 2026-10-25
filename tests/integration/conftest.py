import json
import os
import re
import shlex
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

# --- The two variants every integration spec runs in ----------------------------------------------
# `utf8` is the environment the specs always ran in. `ascii` is hostile: the temporary directory has
# a non-ASCII name and every process the spec starts has an ASCII locale, with no UTF-8 mode and no
# locale coercion, on every platform (on Windows the variables change nothing, the path still does).

VARIANTS = ("utf8", "ascii")
ASCII_ENVIRONMENT = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
NON_ASCII_DIRECTORY = "dé"
# What the three variables were before the variant set them; empty is as good as unset. pre-commit
# 4.6 cannot run under `LC_ALL=C` in a directory whose name is not ASCII, so its own processes (and
# only they) get these back; `pre_commit_locale` is the one way to hand them out.
OUTER_LOCALE = {key: os.environ.get(key, "") for key in ASCII_ENVIRONMENT}
# A spec starts the CLI as `python -m prepush_ci` (found in its source) or another way it declares
# with the marker `starts_the_cli` (the installed `prepush-ci` script, the demo's recording script);
# `variants_spec.py` fails on a module that does the second without the marker.
STARTS_THE_CLI = re.compile(r'"-m",\s*"prepush_ci"|-m prepush_ci')


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "starts_the_cli: the spec starts the CLI; it runs in both variants"
    )


@pytest.fixture(autouse=True, scope="session")
def text_files_are_utf8() -> Iterator[None]:
    """The specs write and read their files as UTF-8, as the tool does: the default encoding of a
    platform (cp1252 on Windows) must not decide what a path with a non-ASCII character becomes."""
    write, read = Path.write_text, Path.read_text

    def write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        return write(self, data, encoding or "utf-8", errors, newline)

    def read_text(
        self: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        return read(self, encoding or "utf-8", errors)

    patch = pytest.MonkeyPatch()
    patch.setattr(Path, "write_text", write_text)
    patch.setattr(Path, "read_text", read_text)
    yield
    patch.undo()


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Run each spec that uses a repository or starts the CLI once per variant."""
    source = Path(str(metafunc.module.__file__)).read_text(encoding="utf-8")
    marked = metafunc.definition.get_closest_marker("starts_the_cli") is not None
    if "repo" in metafunc.fixturenames or marked or STARTS_THE_CLI.search(source):
        if "variant" not in metafunc.fixturenames:
            metafunc.fixturenames.append("variant")
        metafunc.parametrize("variant", VARIANTS, indirect=True)


def keep_the_locales_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    """In `ascii` a process of the spec that runs the CLI must get the three hostile variables and
    one that runs pre-commit the outer ones: whatever the spec, a process started the other way
    round fails the spec, so the exception cannot reach the tool."""
    started = subprocess.Popen.__init__

    def guarded(
        self: "subprocess.Popen[Any]", args: Any, *rest: Any, **kwargs: Any
    ) -> None:
        words = [str(word) for word in args] if isinstance(args, (list, tuple)) else []
        module = words[words.index("-m") + 1 :][:1] if "-m" in words else []
        environment = kwargs.get("env")
        seen = {
            key: (os.environ if environment is None else environment).get(key, "")
            for key in ASCII_ENVIRONMENT
        }
        if module == ["prepush_ci"]:
            assert seen == ASCII_ENVIRONMENT, (
                f"the CLI must keep the hostile locale in the ascii variant, got {seen}"
            )
        if module == ["pre_commit"]:
            assert seen == OUTER_LOCALE, (
                f"pre-commit must get the outer locale in the ascii variant, got {seen}"
            )
        started(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", guarded)


@pytest.fixture
def variant(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """`utf8` or `ascii`; in `ascii` every process the spec starts gets an ASCII locale."""
    name = str(getattr(request, "param", "utf8"))
    if name == "ascii":
        for key, value in ASCII_ENVIRONMENT.items():
            monkeypatch.setenv(key, value)
        keep_the_locales_apart(monkeypatch)
    return name


@pytest.fixture
def pre_commit_locale() -> Callable[[Mapping[str, str] | None], dict[str, str]]:
    """The one helper that gives pre-commit's processes the locale the variant replaced: the
    environment of a pre-commit command, or of a commit or push that runs its hooks. Never the CLI's."""

    def environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
        base = (
            {k: v for k, v in os.environ.items() if not k.startswith("PRE_COMMIT_")}
            if env is None
            else env
        )
        return {**base, **OUTER_LOCALE}

    return environment


@pytest.fixture
def tmp_path(tmp_path: Path, variant: str) -> Path:
    """The temporary directory of the spec; in `ascii` its name has a non-ASCII character."""
    if variant != "ascii":
        return tmp_path
    hostile = tmp_path / NON_ASCII_DIRECTORY
    hostile.mkdir()
    return hostile


@pytest.fixture
def printed(variant: str) -> Callable[[str], str]:
    """What the CLI prints of a text: in `ascii` a character its output cannot encode is `?`."""

    def show(text: str) -> str:
        if variant == "ascii" and sys.platform != "win32":
            return text.encode("ascii", "replace").decode("ascii")
        return text

    return show


@pytest.fixture
def git() -> Git:
    """Run real git in a directory; a failing command fails the test unless `check=False`.

    `PREPUSH_CI`, `PREPUSH_CI_DEBUG` and `PRE_COMMIT_*` are dropped from the inherited environment so a developer's
    own opt-in, or the pre-commit run that started the suite as a pre-push hook, never leaks
    into a spec; pass them through `env` when a spec needs them.
    """

    def run(
        repo: Path,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> "subprocess.CompletedProcess[str]":
        inherited = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PREPUSH_CI", "PREPUSH_CI_DEBUG")
            and not k.startswith("PRE_COMMIT_")
        }
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            encoding="utf-8",  # git writes UTF-8 on every platform, whatever the locale
            errors="replace",
            check=check,
            env={**inherited, **(env or {})},
        )

    return run


@pytest.fixture
def repo(tmp_path: Path, git: Git) -> Path:
    """An empty git repository with an identity, in a temporary directory."""
    path = tmp_path / "work"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "commit.gpgsign", "false")
    return path


@pytest.fixture
def lose_the_parent_of_head(git: Git) -> Callable[[Path], None]:
    """Delete the loose object of `HEAD^` from a repository: `HEAD` still names a commit, but git
    cannot walk its history, so `git log HEAD` fails with a status other than 1."""

    def lose(repo: Path) -> None:
        parent = git(repo, "rev-parse", "HEAD^").stdout.strip()
        stored = repo / ".git" / "objects" / parent[:2] / parent[2:]
        stored.chmod(
            0o644
        )  # git stores objects read-only; Windows refuses to delete them
        stored.unlink()

    return lose


@pytest.fixture
def hooked_repo(repo: Path) -> Path:
    """`repo` with a valid config and the commit-msg hook installed the way git runs it."""
    (repo / ".prepush-ci.toml").write_text('check = "true"\n')
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook commit-msg "$1"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    return repo


@pytest.fixture
def pushing_repo(repo: Path, tmp_path: Path, git: Git) -> Path:
    """`repo` on `main` with one commit, a config whose check logs to `ran.log`, a bare `origin`
    and the pre-push hook installed the way git runs it."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    ran = tmp_path / "ran.log"
    (repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()}"\nrequire_up_to_date = false\n'
    )
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return repo


# --- The invocation checker the skill and the README specs share ---------------------------
# It holds every `prepush-ci` invocation of a text against the `--help` of the real CLI (started as
# the module, so coverage measures it). pytest imports specs by file (importlib mode), so the
# specs get it as a fixture.

NAME = re.compile(r"(?<![\w/.@-])prepush-ci(?![\w/.@:-])")
OPERATORS = {"|", "||", "&&", ";", "&", ">", ">>", "<", ")"}
REDIRECTION = re.compile(r"\d*>")


def cli(*args: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", *args],
        capture_output=True,
        text=True,
        check=False,
    )


@cache
def help_of(words: tuple[str, ...]) -> tuple[int, str]:
    """Exit status and text of `prepush-ci <words> --help`."""
    result = cli(*words, "--help")
    return result.returncode, result.stdout


def choices(help_text: str) -> set[str]:
    """The sub-command names an argparse help lists as `{a,b}`."""
    found = re.search(r"\{([\w,-]+)\}", help_text)
    return set(found.group(1).split(",")) if found else set()


def top_level_lists_verify() -> bool:
    return re.search(r"^also: verify\b", help_of(())[1], re.MULTILINE) is not None


def code_lines(text: str) -> list[str]:
    """The lines of fenced code blocks (continuations joined) and the inline code spans."""
    lines: list[str] = []
    fenced = False
    pending = ""
    for raw in text.splitlines():
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            pending += raw.strip()
            if pending.endswith("\\"):
                pending = pending[:-1] + " "
                continue
            lines.append(pending)
            pending = ""
        else:
            lines.extend(re.findall(r"`([^`\n]+)`", raw))
    return lines


def words_after_the_name(line: str) -> list[list[str]]:
    """For each `prepush-ci` in `line`, the words that follow up to a shell operator."""
    found: list[list[str]] = []
    for match in NAME.finditer(line):
        rest = line[match.end() :]
        try:
            words = shlex.split(rest)
        except ValueError:
            words = rest.split()
        taken: list[str] = []
        for word in words:
            if word in OPERATORS or REDIRECTION.match(word):
                break
            taken.append(word)
        found.append(taken)
    return found


def problems(text: str) -> list[str]:
    """What is wrong with the `prepush-ci` invocations of `text`, in order; empty when none."""
    found: list[str] = []
    for line in code_lines(text):
        for words in words_after_the_name(line):
            found.extend(check_invocation(words))
    return found


def check_invocation(words: list[str]) -> list[str]:
    command: list[str] = []
    rest = list(words)
    while rest and not rest[0].startswith("-"):
        listed = choices(help_of(tuple(command))[1])
        if not command and rest[0] == "verify" and top_level_lists_verify():
            return check_verify(rest[1:])
        if rest[0] not in listed:
            break
        command.append(rest.pop(0))
    if not command and rest and not rest[0].startswith("-"):
        return [f"unknown command {rest[0]}"]
    status, text = help_of(tuple(command))
    if status != 0:
        return [f"unknown command {' '.join(command)}"]
    if choices(text) and not rest:
        return []
    unknown: list[str] = []
    for word in rest:
        option = word.split("=", 1)[0]
        if option.startswith("-") and not re.search(
            rf"(?<![\w-]){re.escape(option)}(?![\w-])", text
        ):
            unknown.append(
                f"unknown option {option} for {' '.join(command) or 'prepush-ci'}"
            )
    return unknown


def check_verify(rest: list[str]) -> list[str]:
    options = [
        f"unknown option {word} for verify" for word in rest if word.startswith("-")
    ]
    arguments = [word for word in rest if not word.startswith("-")]
    if len(arguments) != 1:
        options.append("verify takes exactly one sha")
    return options


@dataclass(frozen=True)
class Invocations:
    problems: Callable[[str], list[str]]
    code_lines: Callable[[str], list[str]]
    words_after_the_name: Callable[[str], list[list[str]]]
    help_of: Callable[[tuple[str, ...]], tuple[int, str]]
    choices: Callable[[str], set[str]]
    top_level_lists_verify: Callable[[], bool]


@pytest.fixture(scope="session")
def invocations() -> Invocations:
    """The check that every `prepush-ci` invocation of a text names a command and options the CLI has."""
    return Invocations(
        problems=problems,
        code_lines=code_lines,
        words_after_the_name=words_after_the_name,
        help_of=help_of,
        choices=choices,
        top_level_lists_verify=top_level_lists_verify,
    )


@pytest.fixture(
    params=[
        pytest.param("dé", id="utf8"),
        pytest.param(
            "d\udce9",  # the byte 0xE9 on its own: a Latin-1 name, not UTF-8
            id="not-utf8",
            marks=pytest.mark.skipif(
                sys.platform == "win32", reason="Windows names are Unicode"
            ),
        ),
    ]
)
def non_ascii_name(request: pytest.FixtureRequest) -> str:
    """The name of a directory with a non-ASCII character in it."""
    return str(request.param)


# --- A double of GitHub's rulesets API ------------------------------------------------------------
# `app ruleset` and `doctor --ruleset` talk to it through `GITHUB_API_URL`; every request is kept.

RULESET_ID = 24893178
LANDING_NAME = "prepush-ci landing"


@dataclass
class ApiRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: str


@dataclass
class RulesetApi:
    """Answers the three requests about rulesets as GitHub does. `listing` is what the listing
    holds, `ruleset` what the request for one ruleset answers (None: 404), `answer` replaces the
    answer of the first request whose `METHOD path` holds its text."""

    url: str
    requests: list[ApiRequest] = field(default_factory=list)
    listing: list[dict[str, Any]] = field(default_factory=list)
    ruleset: dict[str, Any] | None = None
    answers: list[tuple[str, int, str]] = field(default_factory=list)

    def answer(self, where: str, status: int, body: str) -> None:
        self.answers.append((where, status, body))

    def respond(self, request: ApiRequest) -> tuple[int, str]:
        line = f"{request.method} {request.path}"
        for where, status, body in self.answers:
            if where in line:
                return status, body
        path = request.path.split("?")[0]
        if request.method == "GET" and path.endswith("/rulesets"):
            return 200, json.dumps(self.listing)
        if request.method == "GET" and "/rulesets/" in path:
            if self.ruleset is None:
                return 404, json.dumps({"message": "Not Found"})
            return 200, json.dumps(self.ruleset)
        if request.method == "POST" and path.endswith("/rulesets"):
            made = {
                "id": RULESET_ID,
                "name": LANDING_NAME,
                "_links": {
                    "html": {"href": f"{self.url}/acme/widgets/rules/{RULESET_ID}"}
                },
            }
            return 201, json.dumps(made)
        return 404, json.dumps({"message": "Not Found"})

    def posts(self) -> list[ApiRequest]:
        return [r for r in self.requests if r.method == "POST"]

    def changes(self) -> list[ApiRequest]:
        """The requests that would change something on GitHub."""
        return [r for r in self.requests if r.method != "GET"]


@pytest.fixture
def ruleset_api() -> Iterator[RulesetApi]:
    served: RulesetApi

    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            request = ApiRequest(
                self.command,
                self.path,
                {key.lower(): value for key, value in self.headers.items()},
                self.rfile.read(length).decode("utf-8"),
            )
            served.requests.append(request)
            status, body = served.respond(request)
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _serve  # noqa: N815

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    served = RulesetApi(f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield served
    server.shutdown()
    server.server_close()
    thread.join()
