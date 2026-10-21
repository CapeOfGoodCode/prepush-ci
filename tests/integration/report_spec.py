"""`prepush-ci report`: the result of a run posted to a local server that answers as GitHub's API
is documented to, for real temporary git repositories."""

import base64
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

# The signer is the program `openssl`, which Git for Windows ships but a runner may not put on the
# PATH; everything else in this module runs everywhere.
needs_openssl = pytest.mark.skipif(
    sys.platform == "win32" and shutil.which("openssl") is None,
    reason="the app's token is signed by `openssl`, which is not on this PATH",
)
# Variables the developer's or Actions' own environment may set and a spec must decide itself.
CLEARED = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_REPOSITORY",
    "GITHUB_API_URL",
    "PREPUSH_CI",
    "PREPUSH_CI_APP_ID",
    "PREPUSH_CI_APP_KEY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
APP_ID = "123456"
INSTALLATION_TOKEN = "ghs_installation_token"
ORIGIN = "https://github.com/acme/widgets.git"


# --- A server that answers as the API does ----------------------------------------------------


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: str

    def json(self) -> dict[str, object]:
        loaded = json.loads(self.body)
        assert isinstance(loaded, dict)
        return loaded

    @property
    def bearer(self) -> str:
        header = self.headers["authorization"]
        assert header.startswith("Bearer "), header
        return header.removeprefix("Bearer ")


@dataclass
class Api:
    url: str
    requests: list[Request] = field(default_factory=list)
    answers: list[tuple[str, int, Callable[[Request], str], int]] = field(
        default_factory=list
    )
    redirect_to: str | None = None
    runs: list[dict[str, object]] = field(default_factory=list)
    """The check runs of the commit, as GitHub keeps them: a lookup filters them by its query,
    a creation adds one, an update changes one. An answer given by `answer` comes first."""

    def answer(self, where: str, status: int, body: str = "{}", after: int = 0) -> None:
        """Answer a request whose `METHOD path` holds `where` with `status` and `body`, once
        `after` such requests came before it."""
        self.answers.append((where, status, lambda _request: body, after))

    def echo_the_bearer(self, where: str, status: int) -> None:
        """Answer with an error that quotes the credential of the request, as a careless API would."""
        self.answers.append(
            (
                where,
                status,
                lambda request: json.dumps({"message": f"bad {request.bearer} here"}),
                0,
            )
        )

    def respond(self, request: Request) -> tuple[int, str]:
        line = f"{request.method} {request.path}"
        for where, status, body, after in self.answers:
            if where in line:
                before = sum(
                    1 for r in self.requests[:-1] if where in f"{r.method} {r.path}"
                )
                if before >= after:
                    return status, body(request)
        if request.method == "GET" and "/commits/" in request.path:
            return 200, json.dumps(self._lookup(request))
        if request.method == "POST" and request.path.endswith("/check-runs"):
            self.runs.append(
                {**request.json(), "id": 100 + len(self.runs), "app_id": APP_ID}
            )
            return 201, json.dumps({"id": self.runs[-1]["id"]})
        if request.method == "PATCH" and "/check-runs/" in request.path:
            run_id = request.path.rsplit("/", 1)[1]
            (run,) = [r for r in self.runs if str(r["id"]) == run_id]
            run.update(request.json())
            return 200, json.dumps(run)
        if line.endswith("/installation"):
            return 200, json.dumps({"id": 42})
        if line.endswith("/access_tokens"):
            return 201, json.dumps({"token": INSTALLATION_TOKEN})
        return 201, "{}"

    def _lookup(self, request: Request) -> dict[str, object]:
        query = parse_qs(urlsplit(request.path).query)
        keys = {"check_name": "name", "status": "status", "app_id": "app_id"}
        found = [
            run
            for run in self.runs
            if all(
                str(run.get(keys[key])) == values[0] for key, values in query.items()
            )
        ]
        return {"total_count": len(found), "check_runs": found}

    def results(self) -> list[Request]:
        """The requests that create a check run or a status."""
        return [
            request
            for request in self.requests
            if request.path.endswith("/check-runs") or "/statuses/" in request.path
        ]

    def check_run(self) -> dict[str, object]:
        (request,) = [r for r in self.requests if r.path.endswith("/check-runs")]
        return request.json()

    def status(self) -> dict[str, object]:
        (request,) = [r for r in self.requests if "/statuses/" in r.path]
        return request.json()


def _serve_api() -> Iterator[Api]:
    served: Api

    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            request = Request(
                self.command,
                self.path,
                {key.lower(): value for key, value in self.headers.items()},
                self.rfile.read(length).decode("utf-8"),
            )
            served.requests.append(request)
            status, body = served.respond(request)
            data = body.encode("utf-8")
            self.send_response(status)
            if served.redirect_to is not None and 300 <= status < 400:
                self.send_header("Location", served.redirect_to + self.path)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PATCH = _serve  # noqa: N815

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    served = Api(f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield served
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def api() -> Iterator[Api]:
    yield from _serve_api()


@pytest.fixture
def other_api() -> Iterator[Api]:
    """A second server, the one a redirect names: it must never be asked for anything."""
    yield from _serve_api()


@pytest.fixture
def unused_address() -> str:
    """The address of a port nobody listens on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{probe.getsockname()[1]}"


# --- A key the app signs with ------------------------------------------------------------------


@dataclass(frozen=True)
class AppKey:
    pem: str
    public: Path


@pytest.fixture(scope="session")
def app_key(tmp_path_factory: pytest.TempPathFactory) -> AppKey:
    directory = tmp_path_factory.mktemp("app-key")
    private, public = directory / "private.pem", directory / "public.pem"
    subprocess.run(
        ["openssl", "genrsa", "-out", str(private), "2048"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["openssl", "rsa", "-in", str(private), "-pubout", "-out", str(public)],
        check=True,
        capture_output=True,
    )
    return AppKey(private.read_text(), public)


# --- A repository to report on -----------------------------------------------------------------


@dataclass
class World:
    repo: Path
    git: Git
    api: Api
    app_key: Callable[[], AppKey]

    @property
    def sha(self) -> str:
        return self.rev("HEAD")

    @property
    def tree(self) -> str:
        return self.rev("HEAD^{tree}")

    def rev(self, name: str) -> str:
        return self.git(self.repo, "rev-parse", name).stdout.strip()

    def commit(self, name: str, text: str, message: str) -> None:
        (self.repo / name).write_text(text)
        self.git(self.repo, "add", name)
        self.git(self.repo, "commit", "-q", "-m", message)

    def app_env(self) -> dict[str, str | None]:
        return {"PREPUSH_CI_APP_ID": APP_ID, "PREPUSH_CI_APP_KEY": self.app_key().pem}

    def run(
        self,
        *args: str,
        env: dict[str, str | None] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        """Run `report`. Without `env` a token is set; the API is the local server unless `env`
        names `GITHUB_API_URL` (None unsets a variable)."""
        merged: dict[str, str | None] = {"GITHUB_API_URL": self.api.url}
        merged.update({"GITHUB_TOKEN": "tok"} if env is None else env)
        inherited = {k: v for k, v in os.environ.items() if k not in CLEARED}
        inherited["NO_PROXY"] = inherited["no_proxy"] = "127.0.0.1,localhost"
        wanted = {k: v for k, v in merged.items() if v is not None}
        return subprocess.run(
            [sys.executable, "-m", "prepush_ci", "report", *args],
            cwd=cwd or self.repo,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env={**inherited, **wanted},
        )

    def passed(
        self, *args: str, env: dict[str, str | None] | None = None
    ) -> "subprocess.CompletedProcess[str]":
        return self.run("--result", "passed", "--tree", self.tree, *args, env=env)

    def failed(
        self, *args: str, env: dict[str, str | None] | None = None
    ) -> "subprocess.CompletedProcess[str]":
        return self.run("--result", "failed", "--tree", self.tree, *args, env=env)


@pytest.fixture
def world(repo: Path, git: Git, api: Api, request: pytest.FixtureRequest) -> World:
    """`repo` with a committed config and `origin` on github.com (never contacted)."""
    (repo / ".prepush-ci.toml").write_text(
        'check = "sh scripts/ci"\nrequire_up_to_date = false\n'
    )
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", ORIGIN)
    return World(repo, git, api, lambda: request.getfixturevalue("app_key"))


def set_origin(world: World, url: str) -> None:
    world.git(world.repo, "remote", "set-url", "origin", url)


def write_junit(path: Path, *cases: str, wrap: str = "testsuite") -> Path:
    path.write_text(f"<{wrap}>{''.join(cases)}</{wrap}>")
    return path


PASSING = "<testcase classname='a' name='{}'/>"
FAILING = "<testcase classname='a' name='bad'><failure message='x'/></testcase>"
SKIPPED = "<testcase classname='a' name='later'><skipped/></testcase>"


def passing(count: int) -> list[str]:
    return [PASSING.format(f"t{n}") for n in range(count)]


def write_coverage(path: Path, shown: str = "94.5") -> Path:
    path.write_text(json.dumps({"totals": {"percent_covered_display": shown}}))
    return path


def located_case(file: str, line: int, message: str = "assert 1 == 2") -> str:
    return (
        f"<testcase classname='a' name='test_a' file='{file}' line='{line}'>"
        f"<failure message='{message}'/></testcase>"
    )


def write_ruff(path: Path, *entries: tuple[str, int, str, str]) -> Path:
    path.write_text(
        json.dumps(
            [
                {
                    "filename": filename,
                    "location": {"row": row, "column": 1},
                    "code": code,
                    "message": message,
                }
                for filename, row, code, message in entries
            ]
        )
    )
    return path


def write_mypy(path: Path, *errors: str) -> Path:
    found = f"Found {len(errors)} errors in 1 file (checked 1 source file)"
    path.write_text(
        "\n".join([*errors, found if errors else "Success: no issues found"])
    )
    return path


def mypy_error(number: int, path: str = "src/a.py") -> str:
    return f'{path}:{number}: error: Name "x{number}" is not defined  [name-defined]'


def in_the_output(result: "subprocess.CompletedProcess[str]") -> str:
    return result.stdout + result.stderr


# --- Report posts the result of a run ----------------------------------------------------------


def test_the_result_is_posted_and_one_line_names_the_sha_the_result_and_the_way(
    world: World,
) -> None:
    result = world.passed()

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    assert world.sha in lines[0]
    assert "passed" in lines[0]
    assert "commit status" in lines[0]


def test_a_commit_other_than_head_is_reported_by_its_own_sha(world: World) -> None:
    earlier = world.sha
    earlier_tree = world.tree
    world.commit("later.txt", "x", "second")

    result = world.run(
        "--result", "passed", "--tree", earlier_tree, "--commit", earlier
    )

    assert result.returncode == 0
    assert world.api.requests[-1].path.endswith(f"/statuses/{earlier}")


def test_a_report_from_a_subdirectory_posts_as_it_does_from_the_root(
    world: World,
) -> None:
    deeper = world.repo / "src" / "deeper"
    deeper.mkdir(parents=True)

    result = world.run("--result", "passed", "--tree", world.tree, cwd=deeper)

    assert result.returncode == 0
    assert world.api.requests[-1].path.endswith(f"/statuses/{world.sha}")


def test_a_report_outside_a_worktree_exits_1_and_sends_no_request(
    world: World, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "plain"
    elsewhere.mkdir()

    result = world.run("--result", "passed", "--tree", world.tree, cwd=elsewhere)

    assert result.returncode == 1
    assert "worktree" in result.stderr
    assert world.api.requests == []


def test_a_commit_that_does_not_exist_exits_1_names_the_argument_and_sends_nothing(
    world: World,
) -> None:
    result = world.passed("--commit", "no-such-commit")

    assert result.returncode == 1
    assert "--commit" in result.stderr
    assert world.api.requests == []


# --- The exit status says whether the result was posted ----------------------------------------


def test_a_result_that_is_missing_exits_2_and_names_the_flag(world: World) -> None:
    result = world.run("--tree", world.tree)

    assert result.returncode == 2
    assert "--result" in result.stderr
    assert world.api.requests == []


def test_a_result_that_is_unknown_exits_2_and_names_the_flag(world: World) -> None:
    result = world.run("--result", "maybe", "--tree", world.tree)

    assert result.returncode == 2
    assert "--result" in result.stderr
    assert world.api.requests == []


def test_a_tree_that_is_missing_exits_2_and_names_the_flag(world: World) -> None:
    result = world.run("--result", "passed")

    assert result.returncode == 2
    assert "--tree" in result.stderr
    assert world.api.requests == []


def test_a_flag_report_does_not_have_exits_2_and_names_it(world: World) -> None:
    result = world.passed("--no-such-flag")

    assert result.returncode == 2
    assert "--no-such-flag" in result.stderr
    assert world.api.requests == []


def test_help_exits_0_and_lists_every_flag(world: World) -> None:
    result = world.run("--help")

    assert result.returncode == 0
    for flag in (
        "--result",
        "--tree",
        "--commit",
        "--name",
        "--duration",
        "--tool",
        "--junit",
        "--coverage",
        "--ruff",
        "--mypy",
        "--start",
        "--markdown",
    ):
        assert flag in result.stdout
    assert world.api.requests == []


# --- Malformed values are refused ---------------------------------------------------------------


def test_a_tool_without_a_version_exits_2_and_names_the_flag(world: World) -> None:
    result = world.passed("--tool", "ruff")

    assert result.returncode == 2
    assert "--tool" in result.stderr
    assert world.api.requests == []


def test_a_tool_without_a_name_exits_2_and_names_the_flag(world: World) -> None:
    result = world.passed("--tool", "=1.0")

    assert result.returncode == 2
    assert "--tool" in result.stderr


def test_a_duration_that_is_not_a_number_exits_2_and_names_the_flag(
    world: World,
) -> None:
    result = world.passed("--duration", "abc")

    assert result.returncode == 2
    assert "--duration" in result.stderr
    assert world.api.requests == []


def test_a_negative_duration_exits_2_and_names_the_flag(world: World) -> None:
    result = world.passed("--duration", "-5")

    assert result.returncode == 2
    assert "--duration" in result.stderr


def test_an_empty_name_exits_2_and_names_the_flag(world: World) -> None:
    result = world.passed("--name", "")

    assert result.returncode == 2
    assert "--name" in result.stderr
    assert world.api.requests == []


# --- Report runs nothing and reads the commit's config -----------------------------------------


def test_the_check_and_the_preflight_do_not_run(world: World) -> None:
    marks = world.repo.parent / "marks"
    marks.mkdir()
    check, preflight = (marks / "check").as_posix(), (marks / "preflight").as_posix()
    (world.repo / ".prepush-ci.toml").write_text(
        f'check = "touch {check}"\npreflight = "touch {preflight}"\n'
        "require_up_to_date = false\n"
    )
    world.git(world.repo, "commit", "-q", "-a", "-m", "touching config")

    result = world.passed()

    assert result.returncode == 0
    assert list(marks.iterdir()) == []


def test_a_commit_without_a_config_exits_1_and_sends_no_request(
    repo: Path, git: Git, api: Api, request: pytest.FixtureRequest
) -> None:
    (repo / "readme.txt").write_text("x")
    git(repo, "add", "readme.txt")
    git(repo, "commit", "-q", "-m", "no config")
    git(repo, "remote", "add", "origin", ORIGIN)
    bare = World(repo, git, api, lambda: request.getfixturevalue("app_key"))

    result = bare.passed()

    assert result.returncode == 1
    assert "no config" in result.stderr
    assert api.requests == []


def test_an_invalid_config_in_the_commit_exits_1_and_names_the_key(
    world: World,
) -> None:
    (world.repo / ".prepush-ci.toml").write_text('check = "true"\nbogus_key = 1\n')
    world.git(world.repo, "commit", "-q", "-a", "-m", "bad config")

    result = world.passed()

    assert result.returncode == 1
    assert "bogus_key" in result.stderr
    assert world.api.requests == []


@needs_openssl
def test_the_config_committed_in_the_commit_decides_not_the_one_in_the_worktree(
    world: World,
) -> None:
    (world.repo / ".prepush-ci.toml").write_text('check = "sh other.sh"\n')

    result = world.passed(env=world.app_env())

    assert result.returncode == 0, result.stderr
    summary = str(world.api.check_run()["output"])
    assert "sh scripts/ci" in summary
    assert "sh other.sh" not in summary


# --- A result never shows on a state it did not check ------------------------------------------


def test_a_tree_of_another_commit_exits_1_and_names_both_hashes(world: World) -> None:
    other = world.tree
    world.commit("later.txt", "more\n", "a later commit")

    result = world.run("--result", "passed", "--tree", other)

    assert result.returncode == 1
    assert other in result.stderr
    assert world.tree in result.stderr
    assert world.api.requests == []


def test_a_tree_checked_before_an_amend_that_changed_only_the_message_is_posted(
    world: World,
) -> None:
    checked = world.tree
    before = world.sha
    world.git(world.repo, "commit", "-q", "--amend", "-m", "a new message")

    result = world.run("--result", "passed", "--tree", checked)

    assert result.returncode == 0
    assert world.sha != before
    assert world.api.requests[-1].path.endswith(f"/statuses/{world.sha}")


def test_a_tree_checked_before_a_later_commit_that_changed_a_file_is_refused(
    world: World,
) -> None:
    checked = world.tree
    world.commit("changed.txt", "x", "later")

    result = world.run("--result", "passed", "--tree", checked)

    assert result.returncode == 1
    assert world.api.requests == []


def test_an_abbreviated_tree_exits_1_and_sends_no_request(world: World) -> None:
    result = world.run("--result", "passed", "--tree", world.tree[:7])

    assert result.returncode == 1
    assert world.api.requests == []


# --- Where the result is posted ----------------------------------------------------------------


def test_an_https_remote_names_the_repository(world: World) -> None:
    set_origin(world, "https://github.com/acme/widgets.git")

    assert world.passed().returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_an_ssh_remote_without_the_suffix_names_the_repository(world: World) -> None:
    set_origin(world, "git@github.com:acme/widgets")

    assert world.passed().returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_a_remote_with_credentials_names_the_repository(world: World) -> None:
    set_origin(world, "https://x-access-token:s3cret@github.com/acme/widgets.git")

    assert world.passed().returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_an_ssh_url_names_the_repository(world: World) -> None:
    set_origin(world, "ssh://git@github.com/acme/widgets.git")

    assert world.passed().returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_the_repository_comes_from_the_environment_when_origin_is_a_local_path(
    world: World, tmp_path: Path
) -> None:
    set_origin(world, str(tmp_path / "remote.git"))

    result = world.passed(
        env={"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "acme/widgets"}
    )

    assert result.returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_origin_wins_over_github_repository(world: World) -> None:
    set_origin(world, "https://github.com/acme/widgets.git")

    result = world.passed(
        env={"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "other/repo"}
    )

    assert result.returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_a_short_alias_of_origin_names_the_repository(world: World) -> None:
    world.git(world.repo, "config", "url.https://github.com/acme/.insteadOf", "gh:")
    set_origin(world, "gh:widgets")

    result = world.passed()

    assert result.returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_a_push_only_rewrite_is_ignored(world: World) -> None:
    world.git(
        world.repo,
        "config",
        "url.https://github.com/fork/.pushInsteadOf",
        "https://github.com/acme/",
    )
    set_origin(world, "https://github.com/acme/widgets.git")

    result = world.passed()

    assert result.returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path
    assert "/repos/fork/" not in world.api.requests[-1].path


def test_an_ssh_host_alias_exits_1_and_sends_no_request(world: World) -> None:
    set_origin(world, "git@github.com-work:acme/widgets.git")

    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_API_URL": None})

    assert result.returncode == 1
    assert "no repository could be read from `origin`" in result.stderr
    assert world.api.requests == []


def test_a_host_that_only_starts_like_githubs_exits_1_and_sends_no_request(
    world: World,
) -> None:
    set_origin(world, "https://ssh.github.com.example.test/acme/widgets.git")

    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_API_URL": None})

    assert result.returncode == 1
    assert world.api.requests == []


def test_no_origin_and_no_repository_name_exits_1_and_sends_no_request(
    world: World,
) -> None:
    world.git(world.repo, "remote", "remove", "origin")

    result = world.passed()

    assert result.returncode == 1
    assert "no repository could be read from `origin`" in result.stderr
    assert world.api.requests == []


def test_a_malformed_repository_name_exits_1_names_the_variable_and_sends_nothing(
    world: World, tmp_path: Path
) -> None:
    set_origin(world, str(tmp_path / "remote.git"))

    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "acme"})

    assert result.returncode == 1
    assert "GITHUB_REPOSITORY" in result.stderr
    assert world.api.requests == []


def test_an_empty_repository_name_exits_1_and_sends_no_request(world: World) -> None:
    world.git(world.repo, "remote", "remove", "origin")

    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": ""})

    assert result.returncode == 1
    assert "no repository could be read from `origin`" in result.stderr
    assert world.api.requests == []


def test_another_api_address_receives_the_request_for_a_host_it_names(
    world: World,
) -> None:
    set_origin(world, "https://git.example.test/acme/widgets.git")

    result = world.passed()

    assert result.returncode == 0
    assert "/repos/acme/widgets/" in world.api.requests[-1].path


def test_a_host_without_an_api_address_exits_1_and_sends_no_request(
    world: World,
) -> None:
    set_origin(world, "https://git.example.test/acme/widgets.git")

    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_API_URL": None})

    assert result.returncode == 1
    assert "no repository could be read from `origin`" in result.stderr
    assert world.api.requests == []


def test_an_empty_api_address_exits_1_and_sends_no_request(world: World) -> None:
    set_origin(world, "https://git.example.test/acme/widgets.git")

    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_API_URL": ""})

    assert result.returncode == 1
    assert "no repository could be read from `origin`" in result.stderr
    assert world.api.requests == []


# --- The credentials decide check run or commit status -----------------------------------------


@needs_openssl
def test_the_app_posts_a_check_run_and_nothing_else_creates_a_result(
    world: World,
) -> None:
    result = world.passed(env={**world.app_env(), "GITHUB_TOKEN": "tok"})

    assert result.returncode == 0, result.stderr
    assert "check run" in result.stdout
    assert [r.path for r in world.api.results()] == ["/repos/acme/widgets/check-runs"]


def test_a_token_alone_posts_a_commit_status_with_that_token(world: World) -> None:
    result = world.passed(env={"GITHUB_TOKEN": "tok-1"})

    assert result.returncode == 0
    (posted,) = world.api.results()
    assert "/statuses/" in posted.path
    assert posted.bearer == "tok-1"


def test_gh_token_serves_when_github_token_is_unset(world: World) -> None:
    result = world.passed(env={"GH_TOKEN": "tok-2"})

    assert result.returncode == 0
    (posted,) = world.api.results()
    assert "/statuses/" in posted.path
    assert posted.bearer == "tok-2"


def test_an_empty_github_token_falls_to_gh_token(world: World) -> None:
    result = world.passed(env={"GITHUB_TOKEN": "", "GH_TOKEN": "tok-2"})

    assert result.returncode == 0
    (posted,) = world.api.results()
    assert "/statuses/" in posted.path
    assert posted.bearer == "tok-2"


def test_an_empty_app_id_counts_as_unset_and_a_status_is_posted(world: World) -> None:
    result = world.passed(env={"PREPUSH_CI_APP_ID": "", "GITHUB_TOKEN": "tok"})

    assert result.returncode == 0
    (posted,) = world.api.results()
    assert "/statuses/" in posted.path


def test_an_empty_app_id_with_a_key_exits_1_and_names_the_app_id(world: World) -> None:
    result = world.passed(
        env={"PREPUSH_CI_APP_ID": "", "PREPUSH_CI_APP_KEY": "pem", "GITHUB_TOKEN": "t"}
    )

    assert result.returncode == 1
    assert "PREPUSH_CI_APP_ID" in result.stderr
    assert world.api.requests == []


def test_an_app_without_a_key_exits_1_and_names_the_key(world: World) -> None:
    result = world.passed(env={"PREPUSH_CI_APP_ID": APP_ID, "GITHUB_TOKEN": "tok"})

    assert result.returncode == 1
    assert "PREPUSH_CI_APP_KEY" in result.stderr
    assert world.api.requests == []


def test_an_app_without_an_id_exits_1_and_names_the_id(world: World) -> None:
    result = world.passed(env={"PREPUSH_CI_APP_KEY": "pem"})

    assert result.returncode == 1
    assert "PREPUSH_CI_APP_ID" in result.stderr
    assert world.api.requests == []


def test_no_credentials_exit_1_and_name_the_app_and_token_variables(
    world: World,
) -> None:
    result = world.passed(env={})

    assert result.returncode == 1
    for name in ("PREPUSH_CI_APP_ID", "PREPUSH_CI_APP_KEY", "GITHUB_TOKEN", "GH_TOKEN"):
        assert name in result.stderr
    assert world.api.requests == []


# --- A failing app does not become a status ----------------------------------------------------


@needs_openssl
def test_an_app_that_is_not_installed_exits_1_and_posts_no_status(world: World) -> None:
    world.api.answer("/installation", 404, '{"message": "Not Found"}')

    result = world.passed(env={**world.app_env(), "GITHUB_TOKEN": "tok"})

    assert result.returncode == 1
    assert "not installed" in result.stderr
    assert "acme/widgets" in result.stderr
    assert world.api.results() == []


@needs_openssl
def test_a_check_run_that_is_rejected_exits_1_and_posts_no_status(
    world: World,
) -> None:
    world.api.answer("/check-runs", 403, '{"message": "Resource not accessible"}')

    result = world.passed(env={**world.app_env(), "GITHUB_TOKEN": "tok"})

    assert result.returncode == 1
    assert "403" in result.stderr
    assert not [r for r in world.api.requests if "/statuses/" in r.path]


@needs_openssl
def test_an_installation_answer_without_an_id_exits_1(world: World) -> None:
    world.api.answer("/installation", 200, "{}")

    result = world.passed(env=world.app_env())

    assert result.returncode == 1
    assert "no id" in result.stderr
    assert world.api.results() == []


@needs_openssl
def test_an_installation_lookup_that_fails_for_another_reason_names_the_status(
    world: World,
) -> None:
    world.api.answer("/installation", 500, '{"message": "boom"}')

    result = world.passed(env=world.app_env())

    assert result.returncode == 1
    assert "500" in result.stderr


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_of_the_status_request_exits_1_and_nothing_follows_it(
    world: World, other_api: Api, status: int
) -> None:
    world.api.redirect_to = other_api.url
    world.api.answer("/statuses/", status)

    result = world.passed()

    assert result.returncode == 1
    assert str(status) in result.stderr
    assert "reported" not in result.stdout
    assert [r.method for r in world.api.requests] == ["POST"]
    assert other_api.requests == []


@needs_openssl
def test_a_redirect_of_the_installation_lookup_exits_1_and_sends_no_token_on(
    world: World, other_api: Api
) -> None:
    world.api.redirect_to = other_api.url
    world.api.answer("/installation", 301)

    result = world.passed(env=world.app_env())

    assert result.returncode == 1
    assert "301" in result.stderr
    assert other_api.requests == []
    assert world.api.results() == []


# --- Authenticating as the app -----------------------------------------------------------------


def decode_part(part: str) -> dict[str, object]:
    loaded = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    assert isinstance(loaded, dict)
    return loaded


def lookup_token(world: World) -> str:
    (lookup,) = [r for r in world.api.requests if r.path.endswith("/installation")]
    return lookup.bearer


@needs_openssl
def test_the_token_is_signed_with_the_key_and_its_header_says_rs256(
    world: World, app_key: AppKey, tmp_path: Path
) -> None:
    assert world.passed(env=world.app_env()).returncode == 0

    header, payload, signature = lookup_token(world).split(".")
    assert decode_part(header)["alg"] == "RS256"
    message, proof = tmp_path / "message", tmp_path / "signature"
    message.write_bytes(f"{header}.{payload}".encode("ascii"))
    proof.write_bytes(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)))
    verified = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            str(app_key.public),
            "-signature",
            str(proof),
            str(message),
        ],
        capture_output=True,
        check=False,
    )
    assert verified.returncode == 0


@needs_openssl
def test_the_claims_of_the_token_name_the_app_and_expire_within_ten_minutes(
    world: World,
) -> None:
    assert world.passed(env=world.app_env()).returncode == 0

    claims = decode_part(lookup_token(world).split(".")[1])
    issued, expires = claims["iat"], claims["exp"]
    assert isinstance(issued, int)
    assert isinstance(expires, int)
    assert claims["iss"] == APP_ID
    assert expires - issued <= 600 + 60
    assert issued < expires


@needs_openssl
def test_the_check_run_is_created_with_the_installation_token_only(
    world: World,
) -> None:
    env = world.app_env()

    assert world.passed(env=env).returncode == 0

    (created,) = [r for r in world.api.requests if r.path.endswith("/check-runs")]
    assert created.bearer == INSTALLATION_TOKEN
    assert lookup_token(world) not in created.body
    pem = str(env["PREPUSH_CI_APP_KEY"])
    key_line = [line for line in pem.splitlines() if len(line) > 40][0]
    assert key_line not in created.body
    assert key_line not in str(created.headers)
    (granting,) = [r for r in world.api.requests if r.path.endswith("/access_tokens")]
    assert granting.path == "/app/installations/42/access_tokens"
    assert granting.bearer == lookup_token(world)


# --- The key stays private and the signer must exist -------------------------------------------


@needs_openssl
def test_the_key_is_not_left_behind_in_the_repository_or_the_temporary_directory(
    world: World, app_key: AppKey, tmp_path: Path
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = {
        **world.app_env(),
        "TMPDIR": str(scratch),
        "TEMP": str(scratch),
        "TMP": str(scratch),
    }

    assert world.passed(env=env).returncode == 0

    body = [line for line in app_key.pem.splitlines() if len(line) > 40][0]
    assert list(scratch.iterdir()) == []
    for path in world.repo.rglob("*"):
        if path.is_file():
            assert body.encode("ascii") not in path.read_bytes()


@needs_openssl
def test_a_key_that_is_not_a_key_exits_1_and_sends_no_request(world: World) -> None:
    result = world.passed(env={**world.app_env(), "PREPUSH_CI_APP_KEY": "not a key"})

    assert result.returncode == 1
    assert "cannot be used" in result.stderr
    assert world.api.requests == []


@pytest.mark.skipif(
    sys.platform == "win32", reason="the stub that stands in for git is a shell script"
)
def test_openssl_missing_from_the_path_exits_1_names_it_and_sends_no_request(
    world: World, app_key: AppKey, tmp_path: Path
) -> None:
    only_git = tmp_path / "only-git"
    only_git.mkdir()
    stub = only_git / "git"
    stub.write_text(f'#!/bin/sh\nexec "{shutil.which("git")}" "$@"\n')
    stub.chmod(0o755)

    result = world.passed(env={**world.app_env(), "PATH": str(only_git)})

    assert result.returncode == 1
    assert "openssl" in result.stderr
    assert world.api.requests == []


# --- The check run names what ran --------------------------------------------------------------


@needs_openssl
def test_a_green_run_is_a_success_with_the_counts_in_the_title_and_the_coverage(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", *passing(3), SKIPPED)
    coverage = write_coverage(tmp_path / "coverage.json", "94.5")

    result = world.passed(
        "--junit", str(junit), "--coverage", str(coverage), env=world.app_env()
    )

    assert result.returncode == 0, result.stderr
    body = world.api.check_run()
    output = body["output"]
    assert isinstance(output, dict)
    assert body["conclusion"] == "success"
    assert body["status"] == "completed"
    assert body["head_sha"] == world.sha
    for part in ("3 passed", "0 failed", "1 skipped"):
        assert part in output["title"]
    assert "94.5%" in output["summary"]


@needs_openssl
def test_a_red_run_is_a_failure_with_the_failing_count_in_the_title(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", FAILING, FAILING, *passing(1))

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    body = world.api.check_run()
    assert body["conclusion"] == "failure"
    assert "2 failed" in body["output"]["title"]  # type: ignore[index]


@needs_openssl
def test_the_check_run_is_called_prepush_ci_slash_full_by_default(
    world: World,
) -> None:
    assert world.passed(env=world.app_env()).returncode == 0

    assert world.api.check_run()["name"] == "prepush-ci / full"


@needs_openssl
def test_the_check_run_takes_the_name_it_is_given(world: World) -> None:
    result = world.passed("--name", "prepush-ci / unit", env=world.app_env())

    assert result.returncode == 0
    assert world.api.check_run()["name"] == "prepush-ci / unit"


@needs_openssl
def test_a_run_without_files_is_titled_passed_and_the_summary_has_no_coverage(
    world: World,
) -> None:
    assert world.passed(env=world.app_env()).returncode == 0

    output = world.api.check_run()["output"]
    assert isinstance(output, dict)
    assert output["title"] == "Passed"
    assert "overage" not in output["summary"]


# --- The summary names what ran ----------------------------------------------------------------


def summary_of(world: World) -> str:
    output = world.api.check_run()["output"]
    assert isinstance(output, dict)
    return str(output["summary"])


@needs_openssl
def test_the_summary_names_the_commit_the_tree_the_check_and_the_preflight(
    world: World,
) -> None:
    (world.repo / ".prepush-ci.toml").write_text(
        'check = "sh scripts/ci"\npreflight = "test -f ready"\n'
        "require_up_to_date = false\n"
    )
    world.git(world.repo, "commit", "-q", "-a", "-m", "preflight")

    assert world.passed(env=world.app_env()).returncode == 0

    summary = summary_of(world)
    for part in (world.sha, world.tree, "sh scripts/ci", "test -f ready"):
        assert part in summary


@needs_openssl
def test_a_summary_without_a_preflight_says_none(world: World) -> None:
    assert world.passed(env=world.app_env()).returncode == 0

    assert "| Preflight | none |" in summary_of(world)


@needs_openssl
def test_the_summary_names_the_tools_the_duration_and_the_system(
    world: World,
) -> None:
    result = world.passed(
        "--tool",
        "ruff=0.14.2",
        "--tool",
        "mypy=1.18.2",
        "--duration",
        "492",
        env=world.app_env(),
    )

    assert result.returncode == 0, result.stderr
    summary = summary_of(world)
    for part in ("ruff 0.14.2", "mypy 1.18.2", "8m 12s", platform.system()):
        assert part in summary


def row_of(world: World, label: str) -> str:
    rows = [line for line in summary_of(world).splitlines() if line.startswith("|")]
    (row,) = [line for line in rows if line.startswith(f"| {label} |")]
    return row


def configure(world: World, config: str) -> None:
    (world.repo / ".prepush-ci.toml").write_text(
        config + "require_up_to_date = false\n"
    )
    world.git(world.repo, "commit", "-q", "-a", "-m", "config")


@needs_openssl
def test_a_pipe_in_the_check_is_written_with_a_backslash_in_the_summary(
    world: World,
) -> None:
    configure(world, 'check = "sh scripts/ci | tee ci.log"\n')

    assert world.passed(env=world.app_env()).returncode == 0

    row = row_of(world, "Check")
    assert row == r"| Check | ` sh scripts/ci \| tee ci.log ` |"
    cell = row.removeprefix("| Check | ").removesuffix(" |")
    assert not re.search(r"(?<!\\)\|", cell)


@needs_openssl
def test_a_pipe_in_the_preflight_is_written_with_a_backslash_in_the_summary(
    world: World,
) -> None:
    configure(world, 'check = "sh scripts/ci"\npreflight = "make lint | cat"\n')

    assert world.passed(env=world.app_env()).returncode == 0

    assert row_of(world, "Preflight") == r"| Preflight | ` make lint \| cat ` |"


@needs_openssl
def test_a_pipe_in_a_tool_name_is_written_with_a_backslash_in_the_summary(
    world: World,
) -> None:
    result = world.passed("--tool", "a|b=1.0", env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert row_of(world, "Tools") == r"| Tools | a\|b 1.0 |"


@needs_openssl
def test_a_backslash_before_a_pipe_in_the_check_is_kept_and_the_pipe_escaped(
    world: World,
) -> None:
    configure(world, "check = 'echo \\| cat'\n")

    assert world.passed(env=world.app_env()).returncode == 0

    assert row_of(world, "Check") == r"| Check | ` echo \\| cat ` |"


@needs_openssl
def test_a_check_without_a_pipe_is_written_as_typed_in_the_summary(
    world: World,
) -> None:
    assert world.passed(env=world.app_env()).returncode == 0

    assert row_of(world, "Check") == "| Check | ` sh scripts/ci ` |"


@needs_openssl
def test_the_summary_says_the_result_was_reported_from_a_session(
    world: World,
) -> None:
    assert world.passed(env=world.app_env()).returncode == 0

    assert "reported from a session" in summary_of(world)


# --- Results are read from standard formats ----------------------------------------------------


def test_several_junit_files_are_added_up(world: World, tmp_path: Path) -> None:
    first = write_junit(tmp_path / "a.xml", *passing(2))
    second = write_junit(tmp_path / "b.xml", *passing(3), wrap="testsuites")

    result = world.passed("--junit", str(first), "--junit", str(second))

    assert result.returncode == 0
    assert "5 passed" in str(world.api.status()["description"])


def test_a_junit_file_of_pytest_counts_a_setup_error_as_failed(
    world: World, tmp_path: Path
) -> None:
    setup_error = "<testcase name='s'><error message='x'/></testcase>"
    junit = write_junit(
        tmp_path / "r.xml", PASSING.format("a"), FAILING, SKIPPED, setup_error
    )

    result = world.failed("--junit", str(junit))

    assert result.returncode == 0
    assert "1 passed, 2 failed, 1 skipped" in str(world.api.status()["description"])


def test_a_junit_file_of_node_counts_nested_suites_once(
    world: World, tmp_path: Path
) -> None:
    node = tmp_path / "node.xml"
    node.write_text(
        "<?xml version='1.0'?><!-- node --><testsuites><testsuite name='root'>"
        "<testsuite name='inner'><testcase name='a'/><testcase name='b'><failure/></testcase>"
        "</testsuite><testcase name='c'><skipped/></testcase></testsuite></testsuites>"
    )

    result = world.failed("--junit", str(node))

    assert result.returncode == 0
    assert "1 passed, 1 failed, 1 skipped" in str(world.api.status()["description"])


# --- Input that cannot be trusted is refused ---------------------------------------------------


def test_a_junit_file_that_does_not_exist_exits_1_and_names_it(
    world: World, tmp_path: Path
) -> None:
    result = world.passed("--junit", str(tmp_path / "missing.xml"))

    assert result.returncode == 1
    assert "missing.xml" in result.stderr
    assert world.api.requests == []


def test_a_junit_file_of_plain_text_exits_1_and_names_it(
    world: World, tmp_path: Path
) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("plain text")

    result = world.passed("--junit", str(notes))

    assert result.returncode == 1
    assert "notes.txt" in result.stderr
    assert world.api.requests == []


def test_a_coverage_file_without_totals_exits_1_and_names_it(
    world: World, tmp_path: Path
) -> None:
    other = tmp_path / "other.json"
    other.write_text("{}")

    result = world.passed("--coverage", str(other))

    assert result.returncode == 1
    assert "other.json" in result.stderr
    assert world.api.requests == []


def test_a_coverage_file_that_is_not_utf8_exits_1_and_names_it(
    world: World, tmp_path: Path
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_bytes(b'{"totals": \xff}')

    result = world.passed("--coverage", str(broken))

    assert result.returncode == 1
    assert "broken.json" in result.stderr
    assert world.api.requests == []


def test_a_passed_result_with_a_failing_test_exits_1_and_sends_no_request(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", FAILING)

    result = world.passed("--junit", str(junit))

    assert result.returncode == 1
    assert "contradicts" in result.stderr
    assert world.api.requests == []


@needs_openssl
def test_a_failed_result_without_a_failing_test_is_a_failure_check_run(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", *passing(2))

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert world.api.check_run()["conclusion"] == "failure"


# --- Without an app the result is a commit status ----------------------------------------------


def test_a_green_status_has_the_counts_the_coverage_the_tree_and_the_session(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", *passing(3))
    coverage = write_coverage(tmp_path / "coverage.json", "94.5")

    result = world.passed("--junit", str(junit), "--coverage", str(coverage))

    assert result.returncode == 0
    status = world.api.status()
    description = str(status["description"])
    assert status["state"] == "success"
    assert status["context"] == "prepush-ci/full"
    for part in ("3 passed", "94.5%", world.tree[:7], "reported from a session"):
        assert part in description


def test_a_red_status_is_a_failure(world: World) -> None:
    result = world.failed()

    assert result.returncode == 0
    assert world.api.status()["state"] == "failure"


def test_a_status_takes_the_context_it_is_given(world: World) -> None:
    result = world.passed("--name", "unit")

    assert result.returncode == 0
    assert world.api.status()["context"] == "unit"


def test_a_status_description_without_files_has_the_tree_and_no_counts(
    world: World,
) -> None:
    assert world.passed().returncode == 0

    description = str(world.api.status()["description"])
    assert world.tree[:7] in description
    assert "reported from a session" in description
    assert "passed" not in description


# --- An answer of the API that is not success fails the command --------------------------------


def test_a_rejected_request_exits_1_and_names_the_status_and_the_message(
    world: World,
) -> None:
    world.api.answer("/statuses/", 422, '{"message": "Validation Failed"}')

    result = world.passed()

    assert result.returncode == 1
    assert "422" in result.stderr
    assert "Validation Failed" in result.stderr


def test_an_answer_without_a_json_message_is_reported_as_it_came(
    world: World,
) -> None:
    world.api.answer("/statuses/", 502, "bad gateway")

    result = world.passed()

    assert result.returncode == 1
    assert "502" in result.stderr
    assert "bad gateway" in result.stderr


def test_an_answer_without_any_body_is_reported_as_having_no_message(
    world: World,
) -> None:
    world.api.answer("/statuses/", 500, "")

    result = world.passed()

    assert result.returncode == 1
    assert "no message" in result.stderr


def test_a_server_nobody_listens_on_exits_1_and_says_the_request_was_not_sent(
    world: World, unused_address: str
) -> None:
    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_API_URL": unused_address})

    assert result.returncode == 1
    assert "could not be sent" in result.stderr


def test_an_api_address_that_is_no_url_exits_1_and_says_the_request_was_not_sent(
    world: World,
) -> None:
    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_API_URL": "not a url"})

    assert result.returncode == 1
    assert "could not be sent" in result.stderr


def test_the_token_stays_out_of_the_output_of_a_status_run(world: World) -> None:
    world.api.echo_the_bearer("/statuses/", 401)

    result = world.passed(env={"GITHUB_TOKEN": "ghp_secret_token"})

    assert result.returncode == 1
    assert "401" in result.stderr
    assert "ghp_secret_token" not in in_the_output(result)


@needs_openssl
def test_the_json_web_token_and_the_key_stay_out_of_the_output_of_an_app_run(
    world: World, app_key: AppKey
) -> None:
    world.api.echo_the_bearer("/installation", 401)

    result = world.passed(env=world.app_env())

    assert result.returncode == 1
    assert "401" in result.stderr
    for line in app_key.pem.splitlines():
        assert line not in in_the_output(result)
    (lookup,) = world.api.requests
    for part in lookup.bearer.split("."):
        assert part not in in_the_output(result)


@needs_openssl
def test_the_installation_token_stays_out_of_the_output_of_an_app_run(
    world: World,
) -> None:
    world.api.echo_the_bearer("/check-runs", 401)

    result = world.passed(env=world.app_env())

    assert result.returncode == 1
    assert INSTALLATION_TOKEN not in in_the_output(result)


def test_the_userinfo_of_the_remote_stays_out_of_the_output(world: World) -> None:
    set_origin(world, "https://x-access-token:s3cret@git.example.test/acme/widgets.git")

    result = world.passed(env={"GITHUB_TOKEN": "tok", "GITHUB_API_URL": None})

    assert result.returncode == 1
    assert "s3cret" not in in_the_output(result)


@needs_openssl
def test_the_key_stays_out_of_the_output_when_the_api_quotes_it(
    world: World, app_key: AppKey
) -> None:
    quoted = json.dumps({"message": f"unusable key {app_key.pem}"})
    world.api.answer("/installation", 401, quoted)

    result = world.passed(env=world.app_env())

    assert result.returncode == 1
    assert "unusable key" in result.stderr
    for line in app_key.pem.splitlines():
        assert line not in in_the_output(result)


def test_a_long_answer_is_cut_to_a_reasonable_length_after_the_secrets_are_removed(
    world: World,
) -> None:
    secret = "ghp_" + "s" * 400
    long_message = json.dumps({"message": "x" * 1000 + secret})
    world.api.answer("/statuses/", 500, long_message)

    result = world.passed(env={"GITHUB_TOKEN": secret})

    assert result.returncode == 1
    assert len(result.stderr) < 700
    assert "sssss" not in result.stderr


def test_a_secret_cut_by_the_length_limit_would_still_be_found_whole(
    world: World,
) -> None:
    secret = "ghp_" + "s" * 400
    world.api.answer("/statuses/", 500, json.dumps({"message": "x" * 450 + secret}))

    result = world.passed(env={"GITHUB_TOKEN": secret})

    assert "ssss" not in result.stderr


# --- Failures become annotations ---------------------------------------------------------------


def annotations_of(world: World) -> list[dict[str, object]]:
    output = world.api.check_run()["output"]
    assert isinstance(output, dict)
    found = output.get("annotations", [])
    assert isinstance(found, list)
    return found


def top_of(world: World) -> str:
    """The top of the worktree as the command sees it (a path the tools would write)."""
    return world.git(world.repo, "rev-parse", "--show-toplevel").stdout.strip()


@needs_openssl
def test_a_failing_test_sits_on_its_line_plus_one_with_the_title_pytest(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", located_case("tests/a_spec.py", 117))

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert annotations_of(world) == [
        {
            "path": "tests/a_spec.py",
            "start_line": 118,
            "end_line": 118,
            "annotation_level": "failure",
            "title": "pytest",
            "message": "assert 1 == 2",
        }
    ]


@needs_openssl
def test_a_failing_test_without_a_location_has_no_annotation_and_still_counts_as_failed(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", FAILING)

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert annotations_of(world) == []
    assert "output" in world.api.check_run()
    assert "1 failed" in world.api.check_run()["output"]["title"]  # type: ignore[index]


@needs_openssl
def test_a_ruff_error_is_an_annotation_with_its_code_and_message(
    world: World, tmp_path: Path
) -> None:
    ruff = write_ruff(
        tmp_path / "ruff.json",
        (f"{top_of(world)}/src/a.py", 3, "F401", "`os` imported but unused"),
    )

    result = world.failed("--ruff", str(ruff), env=world.app_env())

    assert result.returncode == 0, result.stderr
    (found,) = annotations_of(world)
    assert found["path"] == "src/a.py"
    assert found["start_line"] == found["end_line"] == 3
    assert found["title"] == "ruff"
    assert "F401" in str(found["message"])
    assert "`os` imported but unused" in str(found["message"])


@needs_openssl
def test_a_mypy_error_is_an_annotation_and_a_note_is_none(
    world: World, tmp_path: Path
) -> None:
    mypy = tmp_path / "mypy.txt"
    mypy.write_text(
        'src/a.py:42: error: Returning Any from function declared to return "Mode"  [no-any-return]\n'
        'src/a.py:42: note: Use "-> None" if function does not return a value\n'
        "Found 1 error in 1 file (checked 1 source file)\n"
    )

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    (found,) = annotations_of(world)
    assert (found["path"], found["start_line"], found["title"]) == (
        "src/a.py",
        42,
        "mypy",
    )


@needs_openssl
def test_a_wrapped_mypy_message_is_cut_at_the_end_of_its_first_line(
    world: World, tmp_path: Path
) -> None:
    mypy = tmp_path / "mypy.txt"
    mypy.write_text(
        "src/m.py:1:10: error: Incompatible types in assignment (expression has type\n"
        '"str", variable has type "int")  [assignment]\n'
        '    x: int = "a"\n'
        "             ^~~\n"
        "Found 1 error in 1 file (checked 1 source file)\n"
    )

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    (found,) = annotations_of(world)
    assert (found["path"], found["start_line"]) == ("src/m.py", 1)
    assert found["message"] == "Incompatible types in assignment (expression has type"


@needs_openssl
@pytest.mark.parametrize("flag", ["--ruff", "--mypy"])
def test_a_file_that_starts_with_a_byte_order_mark_is_read_as_without_one(
    world: World, tmp_path: Path, flag: str
) -> None:
    text = (
        write_ruff(
            tmp_path / "found.txt", (f"{top_of(world)}/src/a.py", 3, "F401", "x")
        )
        if flag == "--ruff"
        else write_mypy(tmp_path / "found.txt", mypy_error(42))
    )
    text.write_bytes(b"\xef\xbb\xbf" + text.read_bytes())

    result = world.failed(flag, str(text), env=world.app_env())

    assert result.returncode == 0, result.stderr
    (found,) = annotations_of(world)
    assert found["path"] == "src/a.py"


@needs_openssl
def test_a_mypy_error_with_a_column_is_on_its_line(
    world: World, tmp_path: Path
) -> None:
    mypy = tmp_path / "mypy.txt"
    mypy.write_text(
        'src/a.py:42:9: error: Name "x" is not defined  [name-defined]\n'
        "Found 1 error in 1 file (checked 1 source file)\n"
    )

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    (found,) = annotations_of(world)
    assert (found["path"], found["start_line"]) == ("src/a.py", 42)


@needs_openssl
def test_the_annotations_of_several_files_are_all_on_the_check_run(
    world: World, tmp_path: Path
) -> None:
    first = write_ruff(tmp_path / "r1.json", (f"{top_of(world)}/a.py", 1, "F401", "x"))
    second = write_ruff(tmp_path / "r2.json", (f"{top_of(world)}/b.py", 2, "E501", "y"))

    result = world.failed(
        "--ruff", str(first), "--ruff", str(second), env=world.app_env()
    )

    assert result.returncode == 0, result.stderr
    assert [a["path"] for a in annotations_of(world)] == ["a.py", "b.py"]


@needs_openssl
def test_a_relative_path_is_taken_from_the_top_of_the_worktree_whatever_the_directory(
    world: World, tmp_path: Path
) -> None:
    deeper = world.repo / "src" / "deeper"
    deeper.mkdir(parents=True)
    mypy = write_mypy(tmp_path / "mypy.txt", mypy_error(42))

    result = world.run(
        "--result",
        "failed",
        "--tree",
        world.tree,
        "--mypy",
        str(mypy),
        env=world.app_env(),
        cwd=deeper,
    )

    assert result.returncode == 0, result.stderr
    assert [a["path"] for a in annotations_of(world)] == ["src/a.py"]


@needs_openssl
def test_a_path_outside_the_worktree_exits_1_names_it_and_sends_no_request(
    world: World, tmp_path: Path
) -> None:
    outside = (tmp_path / "elsewhere" / "a.py").as_posix()
    ruff = write_ruff(tmp_path / "ruff.json", (outside, 1, "F401", "x"))

    result = world.failed("--ruff", str(ruff), env=world.app_env())

    assert result.returncode == 1
    assert "elsewhere" in result.stderr
    assert world.api.requests == []


@needs_openssl
def test_a_path_with_backslashes_is_taken_with_slashes(
    world: World, tmp_path: Path
) -> None:
    mypy = tmp_path / "mypy.txt"
    mypy.write_text(
        'src\\a.py:42: error: Name "x" is not defined  [name-defined]\n'
        "Found 1 error in 1 file (checked 1 source file)\n"
    )

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert [a["path"] for a in annotations_of(world)] == ["src/a.py"]


def test_without_an_app_the_failure_files_are_read_and_not_posted(
    world: World, tmp_path: Path
) -> None:
    ruff = write_ruff(
        tmp_path / "ruff.json", (f"{top_of(world)}/src/a.py", 3, "F401", "x")
    )

    result = world.failed("--ruff", str(ruff))

    assert result.returncode == 0, result.stderr
    assert [r.path for r in world.api.requests] == [
        f"/repos/acme/widgets/statuses/{world.sha}"
    ]
    assert "annotations" not in world.api.requests[0].body


# --- Failure files that cannot be trusted are refused --------------------------------------------


@pytest.mark.parametrize("flag", ["--ruff", "--mypy"])
def test_a_failure_file_that_does_not_exist_exits_1_and_names_it(
    world: World, tmp_path: Path, flag: str
) -> None:
    result = world.failed(flag, str(tmp_path / "missing.out"))

    assert result.returncode == 1
    assert "missing.out" in result.stderr
    assert world.api.requests == []


def test_a_ruff_file_of_plain_text_exits_1_and_names_it(
    world: World, tmp_path: Path
) -> None:
    text = tmp_path / "ruff.txt"
    text.write_text("All checks passed!")

    result = world.failed("--ruff", str(text))

    assert result.returncode == 1
    assert "ruff.txt" in result.stderr
    assert world.api.requests == []


def test_a_mypy_file_without_a_summary_line_exits_1_and_names_it(
    world: World, tmp_path: Path
) -> None:
    text = tmp_path / "mypy.txt"
    text.write_text("hello")

    result = world.failed("--mypy", str(text))

    assert result.returncode == 1
    assert "mypy.txt" in result.stderr
    assert world.api.requests == []


@pytest.mark.parametrize("flag", ["--ruff", "--mypy"])
def test_a_failure_file_that_is_not_utf8_exits_1_and_names_it(
    world: World, tmp_path: Path, flag: str
) -> None:
    text = tmp_path / "bytes.out"
    text.write_bytes(b"\xff\xfe")

    result = world.failed(flag, str(text))

    assert result.returncode == 1
    assert "bytes.out" in result.stderr
    assert world.api.requests == []


@needs_openssl
def test_clean_mypy_output_with_a_passed_result_is_a_success_without_annotations(
    world: World, tmp_path: Path
) -> None:
    mypy = write_mypy(tmp_path / "mypy.txt")

    result = world.passed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert world.api.check_run()["conclusion"] == "success"
    assert annotations_of(world) == []


def test_a_passed_result_with_a_lint_error_exits_1_and_sends_no_request(
    world: World, tmp_path: Path
) -> None:
    ruff = write_ruff(
        tmp_path / "ruff.json", (f"{top_of(world)}/src/a.py", 3, "F401", "x")
    )

    result = world.passed("--ruff", str(ruff))

    assert result.returncode == 1
    assert "contradicts" in result.stderr
    assert world.api.requests == []


def test_a_passed_result_with_a_type_error_exits_1_and_sends_no_request(
    world: World, tmp_path: Path
) -> None:
    mypy = write_mypy(tmp_path / "mypy.txt", mypy_error(42))

    result = world.passed("--mypy", str(mypy))

    assert result.returncode == 1
    assert "contradicts" in result.stderr
    assert world.api.requests == []


@pytest.mark.parametrize(
    "error",
    [
        "src/b.py:1:10:1:12: error: Incompatible types  [assignment]",
        'b/x.py: error: Duplicate module named "x" (also at "a/x.py")',
        'src/a:b.py:3: error: Name "x" is not defined  [name-defined]',
    ],
    ids=["with an end position", "without a line", "with a colon in the path"],
)
def test_a_passed_result_with_any_form_of_mypy_error_exits_1(
    world: World, tmp_path: Path, error: str
) -> None:
    mypy = write_mypy(tmp_path / "mypy.txt", error)

    result = world.passed("--mypy", str(mypy))

    assert result.returncode == 1
    assert "contradicts" in result.stderr
    assert world.api.requests == []


# --- Annotations are sent in batches of 50 -------------------------------------------------------

RUN = "/repos/acme/widgets/check-runs"


def run_requests(world: World) -> list[Request]:
    """The requests that create the check run or update one, in order."""
    return [
        r for r in world.api.requests if "/check-runs" in r.path and r.method != "GET"
    ]


def batch_sizes(world: World) -> list[int]:
    return [
        len(r.json()["output"].get("annotations", []))  # type: ignore[attr-defined]
        for r in run_requests(world)
    ]


@needs_openssl
def test_exactly_50_annotations_go_in_one_request(world: World, tmp_path: Path) -> None:
    mypy = write_mypy(tmp_path / "mypy.txt", *(mypy_error(n) for n in range(1, 51)))

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert [(r.method, r.path) for r in run_requests(world)] == [("POST", RUN)]
    assert batch_sizes(world) == [50]


@needs_openssl
def test_120_annotations_go_in_requests_of_50_50_and_20_to_the_same_run(
    world: World, tmp_path: Path
) -> None:
    mypy = write_mypy(tmp_path / "mypy.txt", *(mypy_error(n) for n in range(1, 121)))

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert [(r.method, r.path) for r in run_requests(world)] == [
        ("POST", RUN),
        ("PATCH", f"{RUN}/{world.api.runs[0]['id']}"),
        ("PATCH", f"{RUN}/{world.api.runs[0]['id']}"),
    ]
    assert batch_sizes(world) == [50, 50, 20]
    lines = [
        a["start_line"]
        for r in run_requests(world)
        for a in r.json()["output"]["annotations"]  # type: ignore[attr-defined]
    ]
    assert lines == list(range(1, 121))
    first, second = run_requests(world)[0].json(), run_requests(world)[1].json()
    assert second["output"]["title"] == first["output"]["title"]  # type: ignore[index]
    assert second["output"]["summary"] == first["output"]["summary"]  # type: ignore[index]


@needs_openssl
def test_a_failed_result_without_a_located_failure_is_sent_without_annotations(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", FAILING)

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert batch_sizes(world) == [0]
    assert "annotations" not in world.api.check_run()["output"]  # type: ignore[operator]


@needs_openssl
def test_a_rejected_second_batch_exits_1_names_the_status_and_sends_no_third(
    world: World, tmp_path: Path
) -> None:
    world.api.answer(f"PATCH {RUN}/", 422, '{"message": "Invalid"}', after=1)
    mypy = write_mypy(tmp_path / "mypy.txt", *(mypy_error(n) for n in range(1, 131)))

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 1
    assert "422" in result.stderr
    assert [r.method for r in run_requests(world)] == ["POST", "PATCH", "PATCH"]


@needs_openssl
def test_an_answer_without_a_run_id_exits_1_when_later_batches_need_it(
    world: World, tmp_path: Path
) -> None:
    world.api.answer(f"POST {RUN}", 201)
    mypy = write_mypy(tmp_path / "mypy.txt", *(mypy_error(n) for n in range(1, 52)))

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 1
    assert "no id" in result.stderr
    assert [r.method for r in run_requests(world)] == ["POST"]


# --- The summary of a red run lists the failures first -------------------------------------------


@needs_openssl
def test_the_failures_come_before_the_table_of_what_ran(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", located_case("tests/a_spec.py", 117))
    mypy = write_mypy(tmp_path / "mypy.txt", mypy_error(42))

    result = world.failed(
        "--junit", str(junit), "--mypy", str(mypy), env=world.app_env()
    )

    assert result.returncode == 0, result.stderr
    text = summary_of(world)
    assert text.startswith("### Failures")
    for failure in ("tests/a_spec.py:118", "assert 1 == 2", "src/a.py:42", "x42"):
        assert text.index(failure) < text.index(world.sha)
        assert text.index(failure) < text.index("sh scripts/ci")


@needs_openssl
def test_25_errors_list_20_and_the_number_of_the_others_and_all_25_are_annotated(
    world: World, tmp_path: Path
) -> None:
    mypy = write_mypy(tmp_path / "mypy.txt", *(mypy_error(n) for n in range(1, 26)))

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    text = summary_of(world)
    assert len([line for line in text.splitlines() if line.startswith("- mypy")]) == 20
    assert "- and 5 more" in text
    assert batch_sizes(world) == [25]


@needs_openssl
def test_a_failed_case_without_a_location_is_listed_with_its_name(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", FAILING)

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert "- pytest ` bad `" in summary_of(world)


@needs_openssl
def test_a_green_run_has_no_section_of_failures(world: World, tmp_path: Path) -> None:
    junit = write_junit(tmp_path / "r.xml", *passing(2))
    mypy = write_mypy(tmp_path / "mypy.txt")

    result = world.passed(
        "--junit", str(junit), "--mypy", str(mypy), env=world.app_env()
    )

    assert result.returncode == 0, result.stderr
    assert "Failures" not in summary_of(world)


@needs_openssl
def test_a_message_of_several_lines_is_listed_by_its_first_line(
    world: World, tmp_path: Path
) -> None:
    message = "AssertionError: assert a == b&#10;- a&#10;+ b"
    junit = write_junit(tmp_path / "r.xml", located_case("a_spec.py", 3, message))

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    text = summary_of(world)
    assert "` AssertionError: assert a == b `" in text
    assert "+ b" not in text
    assert "+ b" in str(annotations_of(world)[0]["message"])


@needs_openssl
def test_a_message_of_5000_characters_is_cut_to_200_in_the_summary(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "r.xml", located_case("a_spec.py", 3, "m" * 5000))

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert f"` {'m' * 199}… `" in summary_of(world)
    assert "m" * 200 not in summary_of(world)


@needs_openssl
def test_a_pipe_and_markdown_characters_of_a_message_reach_the_summary_as_typed(
    world: World, tmp_path: Path
) -> None:
    message = "assert 2*3 == 7*1 | &lt;built-in function len&gt; `tick`"
    junit = write_junit(tmp_path / "r.xml", located_case("a_spec.py", 3, message))

    result = world.failed("--junit", str(junit), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert (
        "- pytest ` a_spec.py:4 ` `` assert 2*3 == 7*1 | <built-in function len> `tick` ``"
        in summary_of(world)
    )


# --- A run can be shown as in progress -----------------------------------------------------------


def start(
    world: World, *args: str, env: dict[str, str | None] | None = None
) -> "subprocess.CompletedProcess[str]":
    return world.run("--start", "--tree", world.tree, *args, env=env)


def creations(world: World) -> list[Request]:
    return [r for r in world.api.requests if r.method == "POST" and r.path == RUN]


def updates(world: World) -> list[Request]:
    return [r for r in world.api.requests if r.method == "PATCH"]


@needs_openssl
def test_a_start_creates_one_check_run_in_progress_that_names_the_commit_and_the_check(
    world: World,
) -> None:
    result = start(world, env=world.app_env())

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    assert world.sha in lines[0]
    assert "started" in lines[0]
    assert "check run" in lines[0]
    (created,) = creations(world)
    body = created.json()
    assert body["status"] == "in_progress"
    assert body["name"] == "prepush-ci / full"
    assert body["head_sha"] == world.sha
    assert body["output"]["title"] == "Running"  # type: ignore[index]
    for part in (world.sha, world.tree, "sh scripts/ci", "reported from a session"):
        assert part in body["output"]["summary"]  # type: ignore[index]
    assert "conclusion" not in body


@needs_openssl
def test_a_start_takes_the_name_it_is_given(world: World) -> None:
    result = start(world, "--name", "prepush-ci / unit", env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert creations(world)[0].json()["name"] == "prepush-ci / unit"


@needs_openssl
def test_a_second_start_updates_the_started_at_of_the_run_and_creates_none(
    world: World,
) -> None:
    assert start(world, env=world.app_env()).returncode == 0

    result = start(world, env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert len(creations(world)) == 1
    (update,) = updates(world)
    assert update.path == f"{RUN}/{world.api.runs[0]['id']}"
    assert "started_at" in update.json()
    assert world.api.runs[0]["status"] == "in_progress"


@needs_openssl
def test_a_start_leaves_a_completed_run_of_the_app_alone(world: World) -> None:
    world.api.runs.append(
        {"id": 7, "name": "prepush-ci / full", "status": "completed", "app_id": APP_ID}
    )

    result = start(world, env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert len(creations(world)) == 1
    assert updates(world) == []
    assert world.api.runs[0]["status"] == "completed"


@needs_openssl
def test_a_start_looks_for_a_run_in_progress_of_its_name_and_app(world: World) -> None:
    assert start(world, env=world.app_env()).returncode == 0

    (lookup,) = [
        r for r in world.api.requests if r.method == "GET" and "/commits/" in r.path
    ]

    assert (
        urlsplit(lookup.path).path
        == f"/repos/acme/widgets/commits/{world.sha}/check-runs"
    )
    assert parse_qs(urlsplit(lookup.path).query) == {
        "check_name": ["prepush-ci / full"],
        "status": ["in_progress"],
        "app_id": [APP_ID],
    }


@needs_openssl
def test_a_start_whose_lookup_is_refused_exits_1_and_creates_nothing(
    world: World,
) -> None:
    world.api.answer("GET /repos/acme/widgets/commits/", 403, '{"message": "no"}')

    result = start(world, env=world.app_env())

    assert result.returncode == 1
    assert "403" in result.stderr
    assert world.api.results() == []


@pytest.mark.parametrize(
    "answer", ["{}", '{"check_runs": [{"name": "x"}]}', "[]", "text"]
)
@needs_openssl
def test_a_lookup_answered_without_runs_or_ids_exits_1_and_creates_nothing(
    world: World, answer: str
) -> None:
    world.api.answer("GET /repos/acme/widgets/commits/", 200, answer)

    result = start(world, env=world.app_env())

    assert result.returncode == 1
    assert "lookup" in result.stderr
    assert world.api.results() == []


def test_a_start_with_a_tree_that_is_not_the_commits_exits_1_and_sends_no_request(
    world: World,
) -> None:
    other = "0" * 40

    result = world.run("--start", "--tree", other)

    assert result.returncode == 1
    assert other in result.stderr
    assert world.tree in result.stderr
    assert world.api.requests == []


def test_a_start_without_an_app_posts_a_pending_status_and_nothing_else(
    world: World,
) -> None:
    result = start(world)

    assert result.returncode == 0, result.stderr
    assert world.sha in result.stdout
    assert "started" in result.stdout
    assert "commit status" in result.stdout
    assert [r.path for r in world.api.requests] == [
        f"/repos/acme/widgets/statuses/{world.sha}"
    ]
    body = world.api.status()
    assert body["state"] == "pending"
    assert body["context"] == "prepush-ci/full"
    assert world.tree[:7] in str(body["description"])
    assert "reported from a session" in str(body["description"])


@pytest.mark.parametrize(
    "flag",
    [
        ("--junit", "r.xml"),
        ("--coverage", "c.json"),
        ("--ruff", "r.json"),
        ("--mypy", "m.txt"),
        ("--duration", "5"),
        ("--tool", "ruff=1.0"),
    ],
)
def test_a_start_with_a_flag_of_a_result_exits_2_and_names_it(
    world: World, flag: tuple[str, str]
) -> None:
    result = start(world, *flag)

    assert result.returncode == 2
    assert flag[0] in result.stderr
    assert world.api.requests == []


def test_a_start_together_with_a_result_exits_2_and_names_both_flags(
    world: World,
) -> None:
    result = start(world, "--result", "passed")

    assert result.returncode == 2
    assert "--start" in result.stderr
    assert "--result" in result.stderr
    assert world.api.requests == []


# --- The final report completes the run in progress ----------------------------------------------


def run_in_progress(run_id: int, name: str = "prepush-ci / full") -> dict[str, object]:
    return {"id": run_id, "name": name, "status": "in_progress", "app_id": APP_ID}


@needs_openssl
def test_the_final_report_completes_the_run_the_start_created_and_creates_none(
    world: World,
) -> None:
    assert start(world, env=world.app_env()).returncode == 0
    started = world.api.runs[0]["id"]

    result = world.passed(env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert "check run" in result.stdout
    assert len(creations(world)) == 1
    (update,) = updates(world)
    assert update.path == f"{RUN}/{started}"
    assert update.json()["status"] == "completed"
    assert update.json()["conclusion"] == "success"
    assert world.api.runs[0]["status"] == "completed"
    assert world.api.runs[0]["conclusion"] == "success"


@needs_openssl
def test_a_final_report_without_a_run_in_progress_creates_one_completed_and_updates_none(
    world: World,
) -> None:
    result = world.passed(env=world.app_env())

    assert result.returncode == 0, result.stderr
    (created,) = creations(world)
    assert created.json()["status"] == "completed"
    assert created.json()["conclusion"] == "success"
    assert updates(world) == []


@needs_openssl
def test_the_final_report_looks_up_the_runs_in_progress_of_the_commit_name_and_app(
    world: World,
) -> None:
    result = world.passed("--name", "prepush-ci / unit", env=world.app_env())

    assert result.returncode == 0, result.stderr
    (lookup,) = [
        r for r in world.api.requests if r.method == "GET" and "/commits/" in r.path
    ]
    assert (
        urlsplit(lookup.path).path
        == f"/repos/acme/widgets/commits/{world.sha}/check-runs"
    )
    assert parse_qs(urlsplit(lookup.path).query) == {
        "check_name": ["prepush-ci / unit"],
        "status": ["in_progress"],
        "app_id": [APP_ID],
    }


@needs_openssl
def test_a_run_in_progress_of_another_name_is_left_alone(world: World) -> None:
    world.api.runs.append(run_in_progress(7))

    result = world.passed("--name", "prepush-ci / unit", env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert updates(world) == []
    assert creations(world)[0].json()["name"] == "prepush-ci / unit"
    assert world.api.runs[0]["status"] == "in_progress"


@needs_openssl
def test_with_several_runs_in_progress_the_one_with_the_highest_id_is_completed(
    world: World,
) -> None:
    world.api.runs.extend([run_in_progress(7), run_in_progress(9)])

    result = world.passed(env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert [u.path for u in updates(world)] == [f"{RUN}/9"]
    assert creations(world) == []
    assert [r["status"] for r in world.api.runs] == ["in_progress", "completed"]


@needs_openssl
def test_a_lookup_that_is_refused_exits_1_names_the_status_and_creates_no_run(
    world: World,
) -> None:
    world.api.answer("GET /repos/acme/widgets/commits/", 403, '{"message": "no"}')

    result = world.passed(env=world.app_env())

    assert result.returncode == 1
    assert "403" in result.stderr
    assert world.api.results() == []
    assert updates(world) == []


@needs_openssl
def test_the_annotations_of_a_completed_run_go_to_the_run_in_batches_of_50(
    world: World, tmp_path: Path
) -> None:
    world.api.runs.append(run_in_progress(7))
    mypy = write_mypy(tmp_path / "mypy.txt", *(mypy_error(n) for n in range(1, 121)))

    result = world.failed("--mypy", str(mypy), env=world.app_env())

    assert result.returncode == 0, result.stderr
    assert creations(world) == []
    assert [u.path for u in updates(world)] == [f"{RUN}/7"] * 3
    assert [len(u.json()["output"]["annotations"]) for u in updates(world)] == [  # type: ignore[index]
        50,
        50,
        20,
    ]
    assert "head_sha" not in updates(world)[0].json()


def test_without_an_app_the_final_status_replaces_the_pending_one_with_its_context(
    world: World,
) -> None:
    assert start(world).returncode == 0

    result = world.passed()

    assert result.returncode == 0, result.stderr
    pending, final = [r.json() for r in world.api.requests]
    assert pending["state"] == "pending"
    assert final["state"] == "success"
    assert final["context"] == pending["context"]


# --- Report prints the result as Markdown ------------------------------------------------------


def markdown(
    world: World, *args: str, env: dict[str, str | None] | None = None
) -> "subprocess.CompletedProcess[str]":
    return world.passed("--markdown", *args, env={} if env is None else env)


def test_the_markdown_is_printed_without_a_remote_and_without_credentials(
    world: World,
) -> None:
    world.git(world.repo, "remote", "remove", "origin")

    result = markdown(world)

    assert result.returncode == 0, result.stderr
    assert world.sha in result.stdout
    assert "sh scripts/ci" in result.stdout
    assert result.stderr == ""
    assert world.api.requests == []


def test_the_markdown_sends_no_request_whatever_the_environment_holds(
    world: World,
) -> None:
    result = markdown(world, env={"GITHUB_TOKEN": "tok"})

    assert result.returncode == 0, result.stderr
    assert world.api.requests == []


@needs_openssl
def test_the_markdown_sends_no_request_even_with_an_app_whose_key_is_bad(
    world: World,
) -> None:
    result = markdown(
        world, env={"PREPUSH_CI_APP_ID": APP_ID, "PREPUSH_CI_APP_KEY": "not a key"}
    )

    assert result.returncode == 0, result.stderr
    assert world.api.requests == []


def test_the_markdown_of_a_tree_that_is_not_the_commits_exits_1_with_nothing_printed(
    world: World,
) -> None:
    other = world.tree
    world.commit("later.txt", "more\n", "a later commit")

    result = world.run("--markdown", "--result", "passed", "--tree", other, env={})

    assert result.returncode == 1
    assert other in result.stderr and world.tree in result.stderr
    assert result.stdout == ""


def test_the_markdown_reads_the_inputs_of_a_failed_result(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(
        tmp_path / "junit.xml",
        "<testcase classname='a' name='first'><failure message='x'/></testcase>",
        "<testcase classname='a' name='second'><failure message='y'/></testcase>",
    )

    result = world.failed("--markdown", "--junit", str(junit), env={})

    assert result.returncode == 0, result.stderr
    assert "2 failed" in result.stdout
    assert "first" in result.stdout and "second" in result.stdout


def test_the_markdown_refuses_a_missing_input_as_a_post_does(world: World) -> None:
    result = markdown(world, "--junit", "nowhere.xml")

    assert result.returncode == 1
    assert "nowhere.xml" in result.stderr
    assert result.stdout == ""


def test_the_markdown_with_a_name_still_needs_a_result(world: World) -> None:
    result = world.run("--markdown", "--name", "foo", "--tree", world.tree, env={})

    assert result.returncode == 2
    assert "--result is required" in result.stderr
    assert result.stdout == ""


def test_the_first_line_of_the_markdown_is_the_marker_of_the_default_name(
    world: World,
) -> None:
    result = markdown(world)

    assert result.stdout.splitlines()[0] == "<!-- prepush-ci:prepush-ci / full -->"


def test_the_marker_and_the_title_line_hold_a_chosen_name(world: World) -> None:
    lines = markdown(world, "--name", "prepush-ci / unit").stdout.splitlines()

    assert lines[0] == "<!-- prepush-ci:prepush-ci / unit -->"
    assert "prepush-ci / unit" in lines[1]


def test_the_third_line_of_the_markdown_names_the_commit_it_reports(
    world: World,
) -> None:
    earlier_sha, earlier_tree = world.sha, world.tree
    world.commit("later.txt", "more\n", "a later commit")

    result = world.run(
        "--markdown",
        "--result",
        "passed",
        "--tree",
        earlier_tree,
        "--commit",
        earlier_sha,
        env={},
    )

    third = result.stdout.splitlines()[2]
    assert re.search(r"\b[0-9a-f]{40}\b", third)
    assert earlier_sha in third and world.sha not in third


@needs_openssl
def test_the_markdown_holds_the_summary_that_the_check_run_holds(
    world: World, tmp_path: Path
) -> None:
    junit = write_junit(tmp_path / "junit.xml", *passing(3))
    coverage = write_coverage(tmp_path / "coverage.json", "94.5")
    inputs = ("--junit", str(junit), "--coverage", str(coverage), "--duration", "5")
    posted = world.passed(*inputs, env=world.app_env())
    assert posted.returncode == 0, posted.stderr
    output = world.api.check_run()["output"]
    assert isinstance(output, dict)

    result = markdown(world, *inputs)

    lines = result.stdout.splitlines()
    assert "3 passed" in lines[1] and "94.5%" in result.stdout
    assert "\n".join(lines[4:]) == str(output["summary"]).rstrip("\n")


def test_the_failures_of_a_red_markdown_come_before_the_table(
    world: World, tmp_path: Path
) -> None:
    mypy = write_mypy(tmp_path / "mypy.txt", mypy_error(7))

    result = world.failed("--markdown", "--mypy", str(mypy), env={})

    assert result.returncode == 0, result.stderr
    assert result.stdout.index("x7") < result.stdout.index("| Check |")


def test_the_markdown_does_not_combine_with_start(world: World) -> None:
    result = world.run("--markdown", "--start", "--tree", world.tree, env={})

    assert result.returncode == 2
    assert "--markdown" in result.stderr and "--start" in result.stderr
    assert result.stdout == ""


def test_a_name_that_closes_the_marker_is_refused_with_the_markdown(
    world: World,
) -> None:
    result = markdown(world, "--name", "a-->b")

    assert result.returncode == 2
    assert "--name" in result.stderr
    assert result.stdout == ""


def test_a_name_with_a_line_break_is_refused_with_the_markdown(world: World) -> None:
    result = markdown(world, "--name", "a\nb")

    assert result.returncode == 2
    assert "--name" in result.stderr
    assert result.stdout == ""


def test_a_name_that_closes_the_marker_is_still_posted_without_the_markdown(
    world: World,
) -> None:
    result = world.passed("--name", "a-->b")

    assert result.returncode == 0, result.stderr
    assert world.api.status()["context"] == "a-->b"
