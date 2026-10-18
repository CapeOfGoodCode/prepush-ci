"""`prepush-ci report`: the result of a run posted to a local server that answers as GitHub's API
is documented to, for real temporary git repositories."""

import base64
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
    answers: list[tuple[str, int, Callable[[Request], str]]] = field(
        default_factory=list
    )
    redirect_to: str | None = None

    def answer(self, where: str, status: int, body: str = "{}") -> None:
        """Answer a request whose `METHOD path` holds `where` with `status` and `body`."""
        self.answers.append((where, status, lambda _request: body))

    def echo_the_bearer(self, where: str, status: int) -> None:
        """Answer with an error that quotes the credential of the request, as a careless API would."""
        self.answers.append(
            (
                where,
                status,
                lambda request: json.dumps({"message": f"bad {request.bearer} here"}),
            )
        )

    def respond(self, request: Request) -> tuple[int, str]:
        for where, status, body in self.answers:
            if where in f"{request.method} {request.path}":
                return status, body(request)
        line = f"{request.method} {request.path}"
        if line.endswith("/installation"):
            return 200, json.dumps({"id": 42})
        if line.endswith("/access_tokens"):
            return 201, json.dumps({"token": INSTALLATION_TOKEN})
        return 201, "{}"

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

        do_GET = do_POST = _serve  # noqa: N815

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
