"""`prepush-ci app setup`: create the GitHub App `report` posts check runs as, through GitHub's
manifest flow, with a page on the loopback address instead of a server of ours."""

import os
import queue
import sys
import threading
import webbrowser
from collections.abc import Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from prepush_ci import github_api, text_io
from prepush_ci.core import app_setup, report
from prepush_ci.core.app_setup import App
from prepush_ci.core.report import ReportError
from prepush_ci.git import GitError, answer, git

LOOPBACK = "127.0.0.1"
CALLBACK = "/callback"


@dataclass(frozen=True)
class Options:
    org: str | None
    name: str | None
    timeout: int


def run(options: Options, env: Mapping[str, str], cwd: Path) -> int:
    """Return 0 when the app was created and its key saved, 1 when `app setup` refused or failed;
    the result goes to standard output, the reason to standard error."""
    try:
        print(_setup(options, env, cwd))
        return 0
    except (ReportError, GitError, OSError) as error:
        print(f"prepush-ci: {error}", file=sys.stderr)
        return 1


def _setup(options: Options, env: Mapping[str, str], cwd: Path) -> str:
    name = options.name or app_setup.default_name(_owner(cwd, env))
    server = (
        report.value(env, "GITHUB_SERVER_URL") or app_setup.DEFAULT_SERVER
    ).rstrip("/")
    api_url = (report.value(env, "GITHUB_API_URL") or report.DEFAULT_API).rstrip("/")
    directory = _key_directory(env)
    _refuse_inside_the_worktree(directory, cwd)
    _make(directory)
    state = app_setup.new_state()
    with _Listener(state) as listener:
        # The manifest and the form are made once the port is known: the redirect names it.
        listener.page = app_setup.page(
            _form_action(server, options.org, state),
            app_setup.manifest(name, f"{listener.address}{CALLBACK}"),
        )
        print(f"open this address to create the app: {listener.address}/", flush=True)
        # A thread: a browser that runs in the terminal blocks until it is closed, and cannot be
        # answered by a page this thread has not served yet.
        threading.Thread(
            target=webbrowser.open, args=(f"{listener.address}/",), daemon=True
        ).start()
        code = listener.wait_for_the_code(options.timeout)
    app = app_setup.parse_app(github_api.convert_manifest(api_url, code))
    path = _save_the_key(directory, app)
    return app_setup.result_text(app, server, text_io.text_of(path))


def _owner(cwd: Path, env: Mapping[str, str]) -> str:
    result = git(cwd, "remote", "get-url", "origin")
    origin = answer(result) if result.returncode == 0 else None
    # Only the API address of the environment: GITHUB_REPOSITORY names the repository a job runs
    # for, not the owner of the remote `origin` the name is made of.
    forms = {"GITHUB_API_URL": env.get("GITHUB_API_URL", "")}
    try:
        return report.target(origin, forms).repository.owner
    except ReportError as error:
        raise ReportError(
            "no owner could be read from `origin` to name the app after; "
            "choose a name with --name"
        ) from error


def _form_action(server: str, org: str | None, state: str) -> str:
    where = (
        "settings" if org is None else f"organizations/{quote(org, safe='')}/settings"
    )
    return f"{server}/{where}/apps/new?state={state}"


def _key_directory(env: Mapping[str, str]) -> Path:
    configured = report.value(env, "XDG_CONFIG_HOME")
    config = text_io.to_path(configured) if configured else Path.home() / ".config"
    return config / "prepush-ci" / "apps"


def _refuse_inside_the_worktree(directory: Path, cwd: Path) -> None:
    """The worktree and the git directory: the one may lie outside the other, and a linked worktree
    shares the git directory of the main one."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return
    roots = [text_io.to_path(answer(top)).resolve()]
    for option in ("--absolute-git-dir", "--git-common-dir"):
        found = answer(git(cwd, "rev-parse", option))
        roots.append((cwd / text_io.to_path(found)).resolve())
    here = directory.resolve()
    if any(here.is_relative_to(root) for root in roots):
        raise ReportError(
            f"the key would be saved in the repository ({text_io.text_of(directory)}); "
            "set XDG_CONFIG_HOME to a directory outside it"
        )


def _make(directory: Path) -> None:
    """Before the browser opens: a key that cannot be saved would be lost with the app made for it."""
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        raise ReportError(
            f"cannot create {text_io.text_of(directory)} for the key ({error.strerror})"
        ) from error
    if not os.access(directory, os.W_OK | os.X_OK):
        raise ReportError(
            f"cannot write to {text_io.text_of(directory)}, which would hold the key; "
            "make it writable or set XDG_CONFIG_HOME to another directory"
        )
    # `mkdir` leaves the mode of a directory that was there; the key's directory is for its owner.
    directory.chmod(0o700)


def _save_the_key(directory: Path, app: App) -> Path:
    path = directory / f"{app.app_id}.pem"
    try:
        text_io.create_private(path, app.key)
    except OSError as error:
        raise ReportError(
            f"the app {app.slug} was created but its key was not saved to "
            f"{text_io.text_of(path)} ({error.strerror}); delete the app in its settings "
            "and run `app setup` again"
        ) from error
    return path


class _Listener:
    """One page and one callback on the loopback address, for as long as the `with` lasts."""

    def __init__(self, state: str) -> None:
        self.page = ""
        self._codes: queue.Queue[str] = queue.Queue(maxsize=1)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                owner.handle(self)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

        self._state = state
        self._server = ThreadingHTTPServer((LOOPBACK, 0), Handler)
        self._server.daemon_threads = True
        self.address = f"http://{LOOPBACK}:{self._server.server_address[1]}"

    def __enter__(self) -> "_Listener":
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def handle(self, request: BaseHTTPRequestHandler) -> None:
        parts = urlsplit(request.path)
        if parts.path == "/":
            self._reply(request, 200, self.page)
        elif parts.path == CALLBACK:
            code = app_setup.callback_code(parse_qs(parts.query), self._state)
            if code is not None and self._offer(code):
                self._reply(request, 200, "The app is created. Return to the terminal.")
            else:
                self._reply(
                    request, 400, "This is not the answer this setup waits for."
                )
        else:
            self._reply(request, 404, "Not found.")

    def _offer(self, code: str) -> bool:
        try:
            self._codes.put_nowait(code)
        except queue.Full:
            return False
        return True

    @staticmethod
    def _reply(request: BaseHTTPRequestHandler, status: int, text: str) -> None:
        data = text_io.encode(text)
        request.send_response(status)
        request.send_header("Content-Type", "text/html; charset=utf-8")
        request.send_header("Content-Length", str(len(data)))
        request.end_headers()
        request.wfile.write(data)

    def wait_for_the_code(self, timeout: int) -> str:
        try:
            return self._codes.get(timeout=min(timeout, threading.TIMEOUT_MAX))
        except queue.Empty as error:
            raise ReportError(
                f"no answer came from GitHub within {timeout} seconds; nothing was created "
                "here (run `app setup` again, or raise --timeout)"
            ) from error
