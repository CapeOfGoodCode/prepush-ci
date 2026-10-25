"""`prepush-ci app setup` in real temporary git repositories, started as the module, against a local
double of GitHub's API and a stub in place of the user's browser."""

import base64
import html
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

needs_openssl = pytest.mark.skipif(
    sys.platform == "win32" and shutil.which("openssl") is None,
    reason="the app's token is signed by `openssl`, which is not on this PATH",
)
POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="file modes and the stub need a POSIX system"
)
# What a pipe carries: on Windows the process writes the ANSI code page unless it runs in UTF-8 mode.
PIPE_ENCODING = "mbcs" if sys.platform == "win32" else "utf-8"
# Variables the developer's or Actions' own environment may set and a spec must decide itself.
CLEARED = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_REPOSITORY",
    "GITHUB_API_URL",
    "GITHUB_SERVER_URL",
    "XDG_CONFIG_HOME",
    "BROWSER",
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
ORIGIN = "https://github.com/acme/widgets.git"
APP_ID = "5401187"
SLUG = "prepush-ci-acme"
KEY = "-----BEGIN RSA PRIVATE KEY-----\nnot-a-real-key\n-----END RSA PRIVATE KEY-----\n"
CLIENT_SECRET = "client-secret-0123456789"
WEBHOOK_SECRET = "webhook-secret-0123456789"
WAIT = 30
ADDRESS = re.compile(r"http://127\.0\.0\.1:\d+/")


def conversion(**changes: object) -> str:
    body: dict[str, object] = {
        "id": int(APP_ID),
        "slug": SLUG,
        "pem": KEY,
        "client_secret": CLIENT_SECRET,
        "webhook_secret": WEBHOOK_SECRET,
    }
    return json.dumps({**body, **changes})


# --- A server that answers as GitHub's API does ------------------------------------------------


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: str


@dataclass
class Api:
    url: str
    requests: list[Request] = field(default_factory=list)
    answers: list[tuple[str, int, str]] = field(default_factory=list)

    def answer(self, where: str, status: int, body: str) -> None:
        """Answer a request whose `METHOD path` holds `where` with `status` and `body`."""
        self.answers.append((where, status, body))

    def respond(self, request: Request) -> tuple[int, str]:
        line = f"{request.method} {request.path}"
        for where, status, body in self.answers:
            if where in line:
                return status, body
        if line.startswith("POST /app-manifests/"):
            return 201, conversion()
        if line.endswith("/installation"):
            return 200, json.dumps({"id": 42})
        if line.endswith("/access_tokens"):
            return 201, json.dumps({"token": "ghs_installation_token"})
        if request.method == "GET" and "/commits/" in request.path:
            return 200, json.dumps({"check_runs": []})
        return 201, "{}"

    def conversions(self) -> list[Request]:
        return [r for r in self.requests if r.path.startswith("/app-manifests/")]


@pytest.fixture
def api() -> Iterator[Api]:
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


# --- The user's browser, and the user clicking in it ---------------------------------------------


@dataclass
class Reply:
    status: int
    body: str


NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch(address: str) -> Reply:
    """GET `address` (the answer of an error status as well), never through a proxy."""
    try:
        with NO_PROXY.open(address, timeout=WAIT) as response:
            return Reply(response.status, response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return Reply(error.code, error.read().decode("utf-8"))


@dataclass
class Form:
    action: str
    method: str
    manifest: dict[str, object]

    @property
    def state(self) -> str:
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.action).query)["state"][
            0
        ]


def read_form(page: str) -> Form:
    """What a browser would post: the form's method and action, and its `manifest` field unescaped
    from the HTML attribute, then read as JSON."""
    form = re.search(r"<form\b([^>]*)>", page)
    assert form is not None, page
    attributes = dict(re.findall(r'(\w+)="([^"]*)"', form.group(1)))
    value = re.search(r'name="manifest"\s+value="([^"]*)"', page)
    assert value is not None, page
    loaded = json.loads(html.unescape(value.group(1)))
    assert isinstance(loaded, dict)
    return Form(
        html.unescape(attributes["action"]), attributes["method"].lower(), loaded
    )


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


class Running:
    """An `app setup` that is waiting for GitHub: its output is read as it comes."""

    def __init__(self, process: "subprocess.Popen[bytes]") -> None:
        self.process = process
        self._out: list[bytes] = []
        self._err: list[bytes] = []
        self._readers = [
            threading.Thread(target=self._drain, args=(stream, into), daemon=True)
            for stream, into in (
                (process.stdout, self._out),
                (process.stderr, self._err),
            )
        ]
        for reader in self._readers:
            reader.start()

    @staticmethod
    def _drain(stream: object, into: list[bytes]) -> None:
        assert hasattr(stream, "read1")
        while chunk := stream.read1(4096):
            into.append(chunk)

    def stdout(self) -> str:
        return b"".join(self._out).decode(PIPE_ENCODING, "replace")

    def address(self) -> str:
        """The address the command printed for its page."""
        deadline = time.monotonic() + WAIT
        while time.monotonic() < deadline:
            found = ADDRESS.search(self.stdout())
            if found is not None:
                return found.group(0)
            time.sleep(0.02)
        raise AssertionError(f"no address was printed: {self.stdout()!r}")

    def form(self) -> Form:
        reply = fetch(self.address())
        assert reply.status == 200
        return read_form(reply.body)

    def callback(self, *, state: str | None = None, code: str | None = "c0de") -> Reply:
        """What GitHub's redirect makes the browser fetch; the right state unless given."""
        query = {
            "state": self.form().state if state is None else state,
            **({} if code is None else {"code": code}),
        }
        return fetch(f"{self.address()}callback?{urllib.parse.urlencode(query)}")

    def finish(self) -> Result:
        try:
            self.process.wait(timeout=WAIT)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
        for reader in self._readers:
            reader.join()
        return Result(
            self.process.returncode,
            self.stdout(),
            b"".join(self._err).decode(PIPE_ENCODING, "replace"),
        )

    def close(self) -> None:
        """Let the setup end the way it does: coverage is written by a process that exits by itself."""
        assert self.callback().status == 200
        assert self.finish().returncode == 0

    def accepts_connections(self) -> bool:
        port = int(urllib.parse.urlsplit(self.address()).port or 0)
        with socket.socket() as probe:
            probe.settimeout(WAIT)
            return probe.connect_ex(("127.0.0.1", port)) == 0


@dataclass
class Studio:
    """The directories and the way `app setup` is started in them."""

    repo: Path
    home: Path
    api: Api
    browser_log: Path
    started: list[Running] = field(default_factory=list)

    @property
    def keys(self) -> Path:
        return self.home / ".config" / "prepush-ci" / "apps"

    def environment(self, env: dict[str, str | None] | None = None) -> dict[str, str]:
        merged: dict[str, str | None] = {
            "GITHUB_API_URL": self.api.url,
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "BROWSER": str(self._browser()),
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
        merged.update(env or {})
        inherited = {k: v for k, v in os.environ.items() if k not in CLEARED}
        return {**inherited, **{k: v for k, v in merged.items() if v is not None}}

    def _browser(self) -> Path:
        """A program that records the address it is given in place of opening it."""
        windows = sys.platform == "win32"
        stub = self.home.parent / ("browser.cmd" if windows else "browser")
        if windows:
            stub.write_text(f'@echo %1>>"{self.browser_log}"\r\n')
        else:
            stub.write_text(f'#!/bin/sh\necho "$1" >> "{self.browser_log}"\n')
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        return stub

    def command(self, *args: str) -> list[str]:
        return [sys.executable, "-m", "prepush_ci", "app", "setup", *args]

    def start(
        self,
        *args: str,
        env: dict[str, str | None] | None = None,
        cwd: Path | None = None,
    ) -> Running:
        process = subprocess.Popen(
            self.command(*args),
            cwd=cwd or self.repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.environment(env),
        )
        running = Running(process)
        self.started.append(running)
        return running

    def run(
        self,
        *args: str,
        env: dict[str, str | None] | None = None,
        cwd: Path | None = None,
    ) -> Result:
        """Start `app setup` and let it finish by itself (a refusal, a timeout)."""
        return self.start(*args, env=env, cwd=cwd).finish()

    def complete(self, *args: str, env: dict[str, str | None] | None = None) -> Result:
        """Start `app setup`, let the user click, and let GitHub redirect the browser back."""
        running = self.start(*args, env=env)
        assert running.callback().status == 200
        return running.finish()

    def wait_for_the_browser(self) -> list[str]:
        deadline = time.monotonic() + WAIT
        while time.monotonic() < deadline:
            if self.browser_log.exists() and self.browser_log.read_text().strip():
                return self.browser_log.read_text().split()
            time.sleep(0.02)
        raise AssertionError("the browser was never started")


@pytest.fixture
def studio(repo: Path, git: Git, api: Api, tmp_path: Path) -> Iterator[Studio]:
    """`repo` with `origin` on github.com (never contacted), an empty home and the API double."""
    git(repo, "remote", "add", "origin", ORIGIN)
    home = tmp_path / "home"
    home.mkdir()
    made = Studio(repo, home, api, tmp_path / "browser.log")
    yield made
    for running in made.started:
        if running.process.poll() is None:
            running.process.kill()
            running.process.wait()


def no_page(result: Result) -> bool:
    return ADDRESS.search(result.stdout) is None


# --- Setup serves one page on the loopback address -----------------------------------------------


def test_the_address_is_printed_and_the_browser_receives_it(studio: Studio) -> None:
    running = studio.start()

    address = running.address()
    assert address.startswith("http://127.0.0.1:")
    assert studio.wait_for_the_browser() == [address]
    running.close()


def test_the_page_posts_the_manifest_and_the_state_to_the_server(
    studio: Studio,
) -> None:
    running = studio.start(env={"GITHUB_SERVER_URL": studio.api.url})

    form = running.form()

    assert form.method == "post"
    assert form.action.startswith(f"{studio.api.url}/settings/apps/new?state=")
    assert len(form.state) >= 16
    running.close()


def test_the_page_posts_to_github_when_no_server_is_named(studio: Studio) -> None:
    running = studio.start()

    assert running.form().action.startswith("https://github.com/settings/apps/new?")
    running.close()


def test_with_an_organization_the_form_posts_to_the_organizations_settings(
    studio: Studio,
) -> None:
    running = studio.start("--org", "acme")

    path = urllib.parse.urlsplit(running.form().action).path
    assert path == "/organizations/acme/settings/apps/new"
    running.close()


def test_an_organization_that_is_empty_exits_2_and_names_the_flag(
    studio: Studio,
) -> None:
    result = studio.run("--org", "")

    assert result.returncode == 2
    assert "--org" in result.stderr
    assert no_page(result)


def test_an_organization_with_special_characters_stays_one_path_segment(
    studio: Studio,
) -> None:
    running = studio.start("--org", "a/b?c")

    path = urllib.parse.urlsplit(running.form().action).path
    assert path == "/organizations/a%2Fb%3Fc/settings/apps/new"
    running.close()


def test_only_this_machine_can_reach_the_listener() -> None:
    from prepush_ci.app_setup_command import _Listener

    with _Listener("state") as listener:
        assert listener._server.socket.getsockname()[0] == "127.0.0.1"
        assert listener.address.startswith("http://127.0.0.1:")


def test_a_path_other_than_the_page_and_the_callback_is_answered_404(
    studio: Studio,
) -> None:
    running = studio.start()

    assert fetch(f"{running.address()}elsewhere").status == 404
    assert running.callback().status == 200
    assert running.finish().returncode == 0


# --- The app asks for its permissions -------------------------------------------------------------


def test_the_manifest_asks_for_checks_write_and_nothing_else(studio: Studio) -> None:
    running = studio.start()

    assert running.form().manifest["default_permissions"] == {"checks": "write"}
    running.close()


def test_the_manifest_of_a_landing_app_asks_for_four_permissions(
    studio: Studio,
) -> None:
    running = studio.start("--land")

    manifest = running.form().manifest
    assert manifest["default_permissions"] == {
        "checks": "write",
        "contents": "write",
        "pull_requests": "read",
        "workflows": "write",
    }
    assert manifest["public"] is False
    running.close()


def test_the_manifest_names_the_homepage_of_prepush_ci(studio: Studio) -> None:
    running = studio.start()

    homepage = running.form().manifest["url"]
    assert homepage == "https://github.com/CapeOfGoodCode/prepush-ci"
    running.close()


def test_the_manifest_has_no_webhook_no_events_and_is_not_public(
    studio: Studio,
) -> None:
    running = studio.start()

    manifest = running.form().manifest
    assert "hook_attributes" not in manifest
    assert manifest["default_events"] == []
    assert manifest["public"] is False
    running.close()


def test_the_manifest_redirects_to_the_port_the_command_printed(
    studio: Studio,
) -> None:
    running = studio.start()

    redirect = running.form().manifest["redirect_url"]
    assert isinstance(redirect, str)
    assert redirect.startswith(running.address().rstrip("/"))
    assert redirect.startswith("http://127.0.0.1:")
    running.close()


# --- The app's name -------------------------------------------------------------------------------


def test_the_default_name_is_the_owner_of_an_https_origin(studio: Studio) -> None:
    running = studio.start()

    assert running.form().manifest["name"] == "prepush-ci (acme)"
    running.close()


def test_the_default_name_is_the_owner_of_an_ssh_origin(
    studio: Studio, git: Git
) -> None:
    git(studio.repo, "remote", "set-url", "origin", "git@github.com:acme/widgets.git")
    running = studio.start()

    assert running.form().manifest["name"] == "prepush-ci (acme)"
    running.close()


def test_a_name_with_html_characters_reaches_github_unchanged(studio: Studio) -> None:
    running = studio.start("--name", 'A "b" <c> & d')

    reply = fetch(running.address())
    assert 'A "b" <c>' not in reply.body
    assert read_form(reply.body).manifest["name"] == 'A "b" <c> & d'
    running.close()


def test_a_chosen_name_replaces_the_default(studio: Studio) -> None:
    running = studio.start("--name", "Acme checks")

    assert running.form().manifest["name"] == "Acme checks"
    running.close()


def test_a_chosen_name_needs_no_origin(studio: Studio, git: Git) -> None:
    git(studio.repo, "remote", "remove", "origin")
    running = studio.start("--name", "Acme checks")

    assert running.form().manifest["name"] == "Acme checks"
    running.close()


def test_a_chosen_name_needs_no_repository(studio: Studio, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    running = studio.start("--name", "Acme checks", cwd=elsewhere)

    assert running.form().manifest["name"] == "Acme checks"
    running.close()


def test_without_an_owner_to_name_the_app_after_it_exits_1_naming_the_flag(
    studio: Studio, git: Git
) -> None:
    git(studio.repo, "remote", "remove", "origin")

    result = studio.run()

    assert result.returncode == 1
    assert "--name" in result.stderr
    assert no_page(result)


def test_an_origin_that_names_no_owner_exits_1_naming_the_flag(
    studio: Studio, git: Git, tmp_path: Path
) -> None:
    git(studio.repo, "remote", "set-url", "origin", str(tmp_path / "remote.git"))

    result = studio.run()

    assert result.returncode == 1
    assert "--name" in result.stderr
    assert no_page(result)


def test_the_environment_does_not_name_the_owner_when_there_is_no_origin(
    studio: Studio, git: Git
) -> None:
    git(studio.repo, "remote", "remove", "origin")

    result = studio.run(env={"GITHUB_REPOSITORY": "other/repo"})

    assert result.returncode == 1
    assert "--name" in result.stderr
    assert no_page(result)


def test_the_environment_does_not_name_the_owner_when_origin_names_none(
    studio: Studio, git: Git, tmp_path: Path
) -> None:
    git(studio.repo, "remote", "set-url", "origin", str(tmp_path / "remote.git"))

    result = studio.run(env={"GITHUB_REPOSITORY": "other/repo"})

    assert result.returncode == 1
    assert "--name" in result.stderr
    assert no_page(result)


# --- Names GitHub would refuse are refused first -------------------------------------------------


def test_an_empty_name_exits_2_names_the_flag_and_serves_no_page(
    studio: Studio,
) -> None:
    result = studio.run("--name", "")

    assert result.returncode == 2
    assert "--name" in result.stderr
    assert no_page(result)


def test_a_name_of_35_characters_exits_2_and_names_the_flag(studio: Studio) -> None:
    result = studio.run("--name", "n" * 35)

    assert result.returncode == 2
    assert "--name" in result.stderr
    assert no_page(result)


def test_a_name_of_34_characters_is_accepted(studio: Studio) -> None:
    running = studio.start("--name", "n" * 34)

    assert running.form().manifest["name"] == "n" * 34
    running.close()


def test_an_owner_that_makes_the_default_name_35_characters_exits_1_naming_the_flag(
    studio: Studio, git: Git
) -> None:
    owner = "o" * (35 - len("prepush-ci ()"))
    git(studio.repo, "remote", "set-url", "origin", f"https://github.com/{owner}/w.git")

    result = studio.run()

    assert result.returncode == 1
    assert "--name" in result.stderr
    assert no_page(result)


# --- GitHub's answer completes the setup ---------------------------------------------------------


def test_the_code_is_exchanged_without_a_credential_and_the_browser_gets_a_page(
    studio: Studio,
) -> None:
    running = studio.start()

    reply = running.callback(code="c0de")

    assert reply.status == 200
    assert "terminal" in reply.body
    assert running.finish().returncode == 0
    (conversion_request,) = studio.api.conversions()
    assert conversion_request.method == "POST"
    assert conversion_request.path == "/app-manifests/c0de/conversions"
    assert "authorization" not in conversion_request.headers


def test_a_code_with_special_characters_stays_one_path_segment(studio: Studio) -> None:
    running = studio.start()

    running.callback(code="a/../b?c")

    assert running.finish().returncode == 0
    (conversion_request,) = studio.api.conversions()
    assert conversion_request.path == "/app-manifests/a%2F..%2Fb%3Fc/conversions"


def test_a_callback_with_another_state_is_refused_and_the_right_one_completes(
    studio: Studio,
) -> None:
    running = studio.start()

    assert running.callback(state="not-the-state", code="stolen").status == 400
    assert running.callback(code="c0de").status == 200

    assert running.finish().returncode == 0
    (conversion_request,) = studio.api.conversions()
    assert conversion_request.path == "/app-manifests/c0de/conversions"


def test_a_callback_without_a_state_is_refused(studio: Studio) -> None:
    running = studio.start()

    assert fetch(f"{running.address()}callback?code=c0de").status == 400
    assert studio.api.conversions() == []
    running.close()


def test_a_callback_without_a_code_is_refused_and_starts_no_exchange(
    studio: Studio,
) -> None:
    running = studio.start()

    assert running.callback(code=None).status == 400
    assert studio.api.conversions() == []
    running.close()


def test_a_second_valid_callback_after_the_first_is_refused() -> None:
    from prepush_ci.app_setup_command import _Listener

    with _Listener("state") as listener:
        first = fetch(f"{listener.address}/callback?state=state&code=first")
        second = fetch(f"{listener.address}/callback?state=state&code=second")

    assert (first.status, second.status) == (200, 400)


def test_the_port_accepts_no_connection_once_the_setup_has_completed(
    studio: Studio,
) -> None:
    running = studio.start()
    assert running.callback().status == 200
    assert running.finish().returncode == 0

    assert not running.accepts_connections()


def test_a_code_github_refuses_exits_1_names_the_status_and_the_message(
    studio: Studio,
) -> None:
    studio.api.answer("POST /app-manifests/", 404, json.dumps({"message": "Not Found"}))

    result = studio.complete()

    assert result.returncode == 1
    assert "404" in result.stderr
    assert "Not Found" in result.stderr
    assert not studio.keys.exists() or list(studio.keys.iterdir()) == []


@pytest.mark.parametrize("missing", ["id", "slug", "pem"])
def test_an_answer_that_is_not_an_app_exits_1_and_writes_no_key(
    studio: Studio, missing: str
) -> None:
    body = json.loads(conversion())
    del body[missing]
    studio.api.answer("POST /app-manifests/", 201, json.dumps(body))

    result = studio.complete()

    assert result.returncode == 1
    assert "incomplete" in result.stderr
    assert not studio.keys.exists() or list(studio.keys.iterdir()) == []


# --- The wait ends -------------------------------------------------------------------------------


def test_without_a_callback_it_exits_1_after_the_timeout_and_stops_listening(
    studio: Studio,
) -> None:
    started = time.monotonic()
    running = studio.start("--timeout", "1")
    address = running.address()

    result = running.finish()

    assert result.returncode == 1
    assert "no answer came from GitHub" in result.stderr
    assert time.monotonic() - started < WAIT
    assert not studio.keys.exists() or list(studio.keys.iterdir()) == []
    with pytest.raises(urllib.error.URLError):
        NO_PROXY.open(address, timeout=WAIT)


@pytest.mark.parametrize("value", ["9223372037", "99999999999999999999"])
def test_a_timeout_longer_than_the_system_can_wait_is_accepted_and_the_setup_completes(
    studio: Studio, value: str
) -> None:
    result = studio.complete("--timeout", value)

    assert result.returncode == 0, result.stderr
    assert (studio.keys / f"{APP_ID}.pem").read_text() == KEY


@pytest.mark.parametrize("value", ["0", "soon", "-3", "1.5"])
def test_a_timeout_that_is_not_a_whole_number_of_1_or_more_exits_2_and_serves_no_page(
    studio: Studio, value: str
) -> None:
    result = studio.run("--timeout", value)

    assert result.returncode == 2
    assert "--timeout" in result.stderr
    assert no_page(result)


# --- The key is saved outside the repository -----------------------------------------------------


def test_the_key_is_saved_under_the_config_directory(
    studio: Studio, tmp_path: Path
) -> None:
    config = tmp_path / "config"

    result = studio.complete(env={"XDG_CONFIG_HOME": str(config)})

    assert result.returncode == 0
    assert (config / "prepush-ci" / "apps" / f"{APP_ID}.pem").read_text() == KEY


@POSIX_ONLY
def test_the_key_file_has_mode_0600_and_its_directory_0700(
    studio: Studio, tmp_path: Path
) -> None:
    config = tmp_path / "config"

    assert studio.complete(env={"XDG_CONFIG_HOME": str(config)}).returncode == 0

    apps = config / "prepush-ci" / "apps"
    assert stat.S_IMODE((apps / f"{APP_ID}.pem").stat().st_mode) == 0o600
    assert stat.S_IMODE(apps.stat().st_mode) == 0o700


def test_without_a_config_variable_the_key_goes_under_the_home_directory(
    studio: Studio,
) -> None:
    result = studio.complete()

    assert result.returncode == 0
    assert (studio.keys / f"{APP_ID}.pem").read_text() == KEY


def test_an_empty_config_variable_counts_as_unset(studio: Studio) -> None:
    result = studio.complete(env={"XDG_CONFIG_HOME": ""})

    assert result.returncode == 0
    assert (studio.keys / f"{APP_ID}.pem").read_text() == KEY


def test_no_file_of_the_repository_holds_the_key(studio: Studio) -> None:
    assert studio.complete().returncode == 0

    found = [
        path
        for path in studio.repo.rglob("*")
        if path.is_file() and "not-a-real-key" in path.read_text(errors="replace")
    ]
    assert found == []


def test_a_config_directory_inside_the_worktree_exits_1_before_a_page_is_served(
    studio: Studio,
) -> None:
    inside = studio.repo / "cfg"

    result = studio.run(env={"XDG_CONFIG_HOME": str(inside)})

    assert result.returncode == 1
    assert "repository" in result.stderr
    assert no_page(result)
    assert not inside.exists()


def test_a_config_directory_in_a_subdirectory_of_the_worktree_is_refused_too(
    studio: Studio,
) -> None:
    subdirectory = studio.repo / "docs"
    subdirectory.mkdir()

    result = studio.run(
        env={"XDG_CONFIG_HOME": str(studio.repo / "a" / "b")}, cwd=subdirectory
    )

    assert result.returncode == 1
    assert "repository" in result.stderr


def test_a_directory_that_cannot_be_made_exits_1_before_a_page_is_served(
    studio: Studio, tmp_path: Path
) -> None:
    in_the_way = tmp_path / "a-file"
    in_the_way.write_text("not a directory")

    result = studio.run(env={"XDG_CONFIG_HOME": str(in_the_way)})

    assert result.returncode == 1
    assert "cannot create" in result.stderr
    assert no_page(result)


def test_a_config_directory_in_a_git_directory_outside_the_worktree_is_refused(
    studio: Studio, git: Git, tmp_path: Path
) -> None:
    worktree = tmp_path / "separate-worktree"
    worktree.mkdir()
    git(worktree, "init", "-q", "--separate-git-dir", str(tmp_path / "sep.git"))
    git(worktree, "remote", "add", "origin", ORIGIN)
    inside = tmp_path / "sep.git" / "cfg"

    result = studio.run(env={"XDG_CONFIG_HOME": str(inside)}, cwd=worktree)

    assert result.returncode == 1
    assert "repository" in result.stderr
    assert no_page(result)
    assert not inside.exists()


def test_a_config_directory_in_the_git_directory_of_the_main_worktree_is_refused_from_a_linked_one(
    studio: Studio, git: Git, tmp_path: Path
) -> None:
    git(studio.repo, "commit", "-q", "--allow-empty", "-m", "start")
    linked = tmp_path / "linked"
    git(studio.repo, "worktree", "add", "-q", str(linked))
    inside = studio.repo / ".git" / "cfg"

    result = studio.run(env={"XDG_CONFIG_HOME": str(inside)}, cwd=linked)

    assert result.returncode == 1
    assert "repository" in result.stderr
    assert no_page(result)
    assert not inside.exists()


@POSIX_ONLY
def test_a_key_directory_that_exists_with_another_mode_is_set_to_0700(
    studio: Studio,
) -> None:
    studio.keys.mkdir(parents=True, mode=0o755)
    studio.keys.chmod(0o755)

    assert studio.complete().returncode == 0

    assert stat.S_IMODE(studio.keys.stat().st_mode) == 0o700


@pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="a directory is made read-only with chmod, which Windows and root ignore",
)
def test_a_key_directory_that_cannot_be_written_exits_1_before_a_page_is_served(
    studio: Studio,
) -> None:
    studio.keys.mkdir(parents=True)
    studio.keys.chmod(0o500)
    try:
        result = studio.run()
    finally:
        studio.keys.chmod(0o700)

    assert result.returncode == 1
    assert "cannot write" in result.stderr
    assert no_page(result)


def test_an_existing_key_file_is_kept_and_the_reason_says_the_app_was_created(
    studio: Studio,
) -> None:
    studio.keys.mkdir(parents=True)
    existing = studio.keys / f"{APP_ID}.pem"
    existing.write_text("the old key")

    result = studio.complete()

    assert result.returncode == 1
    assert existing.read_text() == "the old key"
    assert "created" in result.stderr
    assert "not saved" in result.stderr


# --- Secrets stay out of the output --------------------------------------------------------------


def test_neither_the_key_nor_the_secrets_are_printed_on_success(
    studio: Studio,
) -> None:
    result = studio.complete()

    assert result.returncode == 0
    for secret in ("not-a-real-key", CLIENT_SECRET, WEBHOOK_SECRET):
        assert secret not in result.output


def test_neither_the_key_nor_the_secrets_are_printed_when_the_setup_fails_after_the_answer(
    studio: Studio,
) -> None:
    studio.keys.mkdir(parents=True)
    (studio.keys / f"{APP_ID}.pem").write_text("the old key")

    result = studio.complete()

    assert result.returncode == 1
    for secret in ("not-a-real-key", CLIENT_SECRET, WEBHOOK_SECRET):
        assert secret not in result.output


def test_the_secrets_are_stored_nowhere(studio: Studio, tmp_path: Path) -> None:
    assert studio.complete().returncode == 0

    holders = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file()
        and any(
            secret in path.read_bytes().decode("utf-8", "replace")
            for secret in (CLIENT_SECRET, WEBHOOK_SECRET)
        )
    ]
    assert holders == []


# --- The result names what report needs ----------------------------------------------------------


def test_the_result_names_the_id_the_install_address_the_key_file_and_the_variables(
    studio: Studio, printed: Callable[[str], str]
) -> None:
    result = studio.complete()

    assert result.returncode == 0
    assert APP_ID in result.stdout
    assert f"/apps/{SLUG}/installations/new" in result.stdout
    assert printed((studio.keys / f"{APP_ID}.pem").as_posix()) in result.stdout
    assert "PREPUSH_CI_APP_ID" in result.stdout
    assert "PREPUSH_CI_APP_KEY" in result.stdout


def test_the_result_of_a_landing_app_names_the_ruleset_command_and_the_word_installed(
    studio: Studio,
) -> None:
    result = studio.complete("--land")

    assert result.returncode == 0
    assert f"prepush-ci app ruleset --app {APP_ID}" in result.stdout
    assert "installed" in result.stdout


def test_the_result_of_an_app_without_the_flag_holds_no_ruleset_command(
    studio: Studio,
) -> None:
    result = studio.complete()

    assert "app ruleset" not in result.stdout


def test_the_install_address_is_on_the_server_the_setup_used(studio: Studio) -> None:
    result = studio.complete(env={"GITHUB_SERVER_URL": "https://ghe.example/"})

    assert f"https://ghe.example/apps/{SLUG}/installations/new" in result.stdout


def decode_part(part: str) -> dict[str, object]:
    loaded = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    assert isinstance(loaded, dict)
    return loaded


@needs_openssl
def test_report_run_with_the_printed_values_posts_a_check_run(
    studio: Studio, git: Git, tmp_path: Path
) -> None:
    private, public = tmp_path / "private.pem", tmp_path / "public.pem"
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
    studio.api.answer("POST /app-manifests/", 201, conversion(pem=private.read_text()))
    (studio.repo / ".prepush-ci.toml").write_text(
        'check = "sh scripts/ci"\nrequire_up_to_date = false\n'
    )
    git(studio.repo, "add", ".prepush-ci.toml")
    git(studio.repo, "commit", "-q", "-m", "init")
    tree = git(studio.repo, "rev-parse", "HEAD^{tree}").stdout.strip()

    assert studio.complete().returncode == 0

    saved = studio.keys / f"{APP_ID}.pem"
    posted = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "report", "--result", "passed"]
        + ["--tree", tree],
        cwd=studio.repo,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=studio.environment(
            {"PREPUSH_CI_APP_ID": APP_ID, "PREPUSH_CI_APP_KEY": saved.read_text()}
        ),
    )
    assert posted.returncode == 0, posted.stderr
    (lookup,) = [r for r in studio.api.requests if r.path.endswith("/installation")]
    header, payload, signature = lookup.headers["authorization"].split()[1].split(".")
    assert decode_part(header)["alg"] == "RS256"
    assert decode_part(payload)["iss"] == APP_ID
    message, proof = tmp_path / "message", tmp_path / "signature"
    message.write_bytes(f"{header}.{payload}".encode("ascii"))
    proof.write_bytes(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)))
    verified = subprocess.run(
        ["openssl", "dgst", "-sha256", "-verify", str(public)]
        + ["-signature", str(proof), str(message)],
        capture_output=True,
        check=False,
    )
    assert verified.returncode == 0
    assert any(r.path.endswith("/check-runs") for r in studio.api.requests)


# --- The exit status says whether the app was created --------------------------------------------


def test_the_app_is_created_and_the_command_exits_0(studio: Studio) -> None:
    assert studio.complete().returncode == 0


def test_a_flag_the_command_does_not_have_exits_2_names_it_and_serves_no_page(
    studio: Studio,
) -> None:
    result = studio.run("--frob")

    assert result.returncode == 2
    assert "--frob" in result.stderr
    assert no_page(result)


def test_help_exits_0_and_lists_the_three_flags(studio: Studio) -> None:
    result = studio.run("--help")

    assert result.returncode == 0
    for flag in ("--org", "--name", "--timeout"):
        assert flag in result.stdout


def test_help_gives_300_seconds_as_the_default_timeout(studio: Studio) -> None:
    result = studio.run("--help")

    assert "(default: 300)" in " ".join(result.stdout.split())


def test_app_without_a_subcommand_exits_2_and_names_setup(studio: Studio) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "app"],
        cwd=studio.repo,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=studio.environment(),
    )

    assert result.returncode == 2
    assert "setup" in result.stderr
