"""`prepush-ci hook post-push`: a Claude Code `PostToolUse` payload on standard input, a real
repository that pushed to a bare `origin`, and a local server that answers as GitHub's API is
documented to."""

import json
import os
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from prepush_ci.core.config import ConfigError
from prepush_ci.core.run_cache import config_digest
from prepush_ci.git import committed_config

DEEP = pytest.param("[" * 100_000, id="nested-too-deep")

Git = Callable[..., "subprocess.CompletedProcess[str]"]

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
ORIGIN = "https://github.com/acme/widgets.git"
COMMITTED = "the config committed in HEAD"
MARKER = "<!-- prepush-ci:prepush-ci / full -->"
TRAILER = "Prepush-CI: full"
BRANCH = "feat/x"
PUSH = f"git push origin {BRANCH}"
PULLS = "/repos/acme/widgets/pulls"
COMMENTS = "/repos/acme/widgets/issues/7/comments"


# --- A server that answers as the API does ----------------------------------------------------


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: str

    @property
    def route(self) -> str:
        return urlsplit(self.path).path

    @property
    def query(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}

    def json(self) -> dict[str, str]:
        loaded = json.loads(self.body)
        assert isinstance(loaded, dict)
        return loaded


@dataclass
class Api:
    url: str
    requests: list[Request] = field(default_factory=list)
    pulls: list[dict[str, object]] = field(default_factory=lambda: [{"number": 7}])
    comments: list[dict[str, object]] = field(default_factory=list)
    answers: list[tuple[str, int, str]] = field(default_factory=list)
    delay: float = 0.0
    hang_on: str | None = None
    trickle_on: str | None = None
    release: threading.Event = field(default_factory=threading.Event)
    redirect_to: str | None = None

    def answer(self, where: str, status: int, body: str = "{}") -> None:
        """Answer a request whose `METHOD path` holds `where` with `status` and `body`."""
        self.answers.append((where, status, body))

    def respond(self, request: Request) -> tuple[int, str]:
        line = f"{request.method} {request.path}"
        if self.hang_on is not None and self.hang_on in line:
            self.release.wait(60)
        time.sleep(self.delay)
        for where, status, body in self.answers:
            if where in line:
                return status, body
        if request.method == "GET" and request.route == PULLS:
            return 200, json.dumps(self.pulls)
        if request.method == "GET" and request.route == COMMENTS:
            page, size = int(request.query["page"]), int(request.query["per_page"])
            return 200, json.dumps(self.comments[(page - 1) * size : page * size])
        if request.method == "POST" and request.route == COMMENTS:
            created = {"id": 100 + len(self.comments), "body": request.json()["body"]}
            self.comments.append(created)
            return 201, json.dumps(created)
        if request.method == "PATCH" and "/issues/comments/" in request.route:
            number = int(request.route.rsplit("/", 1)[1])
            (found,) = [c for c in self.comments if c["id"] == number]
            found["body"] = request.json()["body"]
            return 200, json.dumps(found)
        return 404, json.dumps({"message": "Not Found"})

    def writes(self) -> list[Request]:
        return [r for r in self.requests if r.method != "GET"]

    def asked(self, route: str) -> list[Request]:
        return [r for r in self.requests if r.route == route]


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
            if served.trickle_on is not None and served.trickle_on in request.path:
                self._trickle()
                return
            status, body = served.respond(request)
            data = body.encode("utf-8")
            self.send_response(status)
            if served.redirect_to is not None and 300 <= status < 400:
                self.send_header("Location", served.redirect_to + self.path)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _trickle(self) -> None:
            """Answer the status line, then one header line a second, until released."""
            try:
                self.wfile.write(b"HTTP/1.1 200 OK\r\n")
                while not served.release.wait(1):
                    self.wfile.write(b"X-Slow: a\r\n")
                    self.wfile.flush()
            except OSError:
                pass  # the hook gave up and closed the connection

        do_GET = do_POST = do_PATCH = _serve  # noqa: N815

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    served = Api(f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield served
    served.release.set()
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def api() -> Iterator[Api]:
    yield from _serve_api()


@pytest.fixture
def other_api() -> Iterator[Api]:
    """The server a redirect names: it must never be asked for anything."""
    yield from _serve_api()


@pytest.fixture
def unused_address() -> str:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{probe.getsockname()[1]}"


# --- A repository that pushed a trailer commit ------------------------------------------------


@dataclass
class World:
    repo: Path
    git: Git
    api: Api
    tmp_path: Path

    @property
    def sha(self) -> str:
        return self.rev("HEAD")

    @property
    def tree(self) -> str:
        return self.rev("HEAD^{tree}")

    def rev(self, name: str) -> str:
        return self.git(self.repo, "rev-parse", name).stdout.strip()

    def commit(self, message: str = "work", trailer: str | None = TRAILER) -> None:
        paragraphs = [message] if trailer is None else [message, trailer]
        self.git(
            self.repo,
            "commit",
            "--allow-empty",
            "-q",
            *(arg for text in paragraphs for arg in ("-m", text)),
        )

    def config(self, *lines: str, check: str | None = None) -> None:
        """Commit a config whose check logs to `ran.log`, with the extra lines."""
        log = self.tmp_path / "ran.log"
        body = [
            f"check = '{check or f'echo ran >> {log.as_posix()}'}'",
            "require_up_to_date = false",
            *lines,
        ]
        (self.repo / ".prepush-ci.toml").write_text("\n".join(body) + "\n")
        self.git(self.repo, "add", ".prepush-ci.toml")

    def push(self, *args: str, options: tuple[str, ...] = ()) -> None:
        """Push through the real hooks, to the bare repository, then let `origin` name the
        repository on GitHub again."""
        self.git(
            self.repo, "remote", "set-url", "origin", str(self.tmp_path / "remote.git")
        )
        self.git(self.repo, *options, "push", *args)
        self.on_github()

    def landed(self) -> None:
        """Make it look as if `HEAD` was pushed to `origin` under the name of the branch."""
        self.git(self.repo, "update-ref", f"refs/remotes/origin/{BRANCH}", "HEAD")

    def digest(self) -> str:
        """The digest of the config committed in `HEAD` (zeros when there is none to read)."""
        try:
            committed = committed_config(self.sha, self.repo)
        except ConfigError:
            committed = None
        return "0" * 32 if committed is None else config_digest(committed)

    def recorded(self) -> None:
        """Record a pass for the tree of `HEAD`, as the pre-push hook does."""
        self.forge_pass("feed", None, 1_700_000_000)

    def passes(self) -> list[str]:
        listing = self.git(
            self.repo, "for-each-ref", "--format=%(refname)", "refs/prepush-ci/results"
        )
        return listing.stdout.split()

    def forge_pass(
        self,
        suffix: str,
        facts: dict[str, object] | str | None,
        date: int,
        *,
        commit: str | None = None,
        digest: str | None = COMMITTED,
    ) -> None:
        """Record a pass for the tree of `HEAD` as the run cache does, with the facts given (none:
        as an older version recorded it), made at `date`, and the digest of the config committed in
        `HEAD` unless another one (or none) is given."""
        sha = commit or self.sha
        message = ["-m", "prepush-ci: the check passed", "-m", f"commit {sha}"]
        if facts is not None:
            line = (
                facts
                if isinstance(facts, str)
                else json.dumps({"v": 1, **facts}, separators=(",", ":"))
            )
            message += ["-m", f"facts {line}"]
        if digest is not None:
            message += [
                "-m",
                f"config {self.digest() if digest == COMMITTED else digest}",
            ]
        stamp = f"{date} +0000"
        made = self.git(
            self.repo,
            "commit-tree",
            self.tree,
            *message,
            env={"GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp},
        ).stdout.strip()
        self.git(
            self.repo,
            "update-ref",
            f"refs/prepush-ci/results/{self.tree}-{suffix}",
            made,
        )

    def drop_passes(self) -> None:
        for ref in self.passes():
            self.git(self.repo, "update-ref", "-d", ref)

    def on_github(self) -> None:
        """Let `origin` name the repository on GitHub, after the pushes that need a real remote."""
        self.git(self.repo, "remote", "set-url", "origin", ORIGIN)

    def environment(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        base = {k: v for k, v in os.environ.items() if k not in CLEARED}
        return {**base, "GITHUB_API_URL": self.api.url, **(extra or {})}

    def payload(
        self, command: str = PUSH, cwd: Path | None = None, **fields: object
    ) -> str:
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(cwd or self.repo),
            **fields,
        }
        return json.dumps(data)

    def hook(
        self,
        stdin: str | None = None,
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            [sys.executable, "-m", "prepush_ci", "hook", "post-push"],
            input=self.payload() if stdin is None else stdin,
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=120,
            env=self.environment(env) if environment is None else environment,
        )

    def nothing(self, result: "subprocess.CompletedProcess[str]") -> None:
        """The hook exited 0, printed nothing and sent no request."""
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
        assert self.api.requests == []

    def comment_body(self) -> str:
        (created,) = self.api.comments
        return str(created["body"])


@pytest.fixture
def world(pushing_repo: Path, git: Git, tmp_path: Path, api: Api) -> World:
    """`pushing_repo` on branch `feat/x`, with a trailer commit pushed through the pre-push hook
    (so a pass is recorded) and `origin` named as a repository on GitHub afterwards."""
    git(pushing_repo, "switch", "-q", "-c", BRANCH)
    made = World(pushing_repo, git, api, tmp_path)
    made.commit()
    made.push("origin", BRANCH)
    return made


@pytest.fixture
def fresh(pushing_repo: Path, git: Git, tmp_path: Path, api: Api) -> World:
    """`pushing_repo` on branch `feat/x`: nothing pushed yet."""
    git(pushing_repo, "switch", "-q", "-c", BRANCH)
    return World(pushing_repo, git, api, tmp_path)


# --- The hook reads the payload and never fails ------------------------------------------------


@pytest.mark.parametrize("text", ["not json", ""])
def test_the_hook_does_nothing_for_input_that_is_not_json(
    world: World, text: str
) -> None:
    world.nothing(world.hook(text))


def test_the_hook_does_nothing_for_another_tool_whose_command_would_be_a_push(
    world: World,
) -> None:
    world.nothing(world.hook(world.payload(tool_name="Edit")))


def test_the_hook_does_nothing_when_the_command_is_not_a_string(world: World) -> None:
    text = json.dumps({"tool_name": "Bash", "tool_input": {"command": 7}})
    world.nothing(world.hook(text))


def test_the_help_of_the_hook_exits_0(world: World) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "hook", "post-push", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_the_hook_writes_nothing_to_the_repository(world: World) -> None:
    before = world.git(world.repo, "for-each-ref").stdout
    status = world.git(world.repo, "status", "--porcelain").stdout
    assert world.hook().returncode == 0
    assert world.git(world.repo, "for-each-ref").stdout == before
    assert world.git(world.repo, "status", "--porcelain").stdout == status


# --- The hook acts for a landed push -----------------------------------------------------------


def test_the_hook_looks_for_the_pull_request_of_a_pushed_trailer_commit(
    world: World,
) -> None:
    assert world.hook().returncode == 0
    assert [r.route for r in world.api.requests][:1] == [PULLS]


def test_the_hook_does_nothing_for_a_command_that_is_not_a_push(world: World) -> None:
    world.nothing(world.hook(world.payload("git status")))


def test_the_hook_does_nothing_on_a_detached_head(world: World) -> None:
    world.git(world.repo, "switch", "-q", "--detach")
    world.nothing(world.hook())


def test_the_hook_does_nothing_when_the_push_did_not_land(world: World) -> None:
    world.commit("more", trailer=None)  # the same tree, so a pass is recorded for it
    world.nothing(world.hook(world.payload(f"{PUSH} || true")))


def test_the_hook_does_nothing_for_a_push_under_another_name(fresh: World) -> None:
    fresh.commit()
    fresh.push("origin", "HEAD:other")
    fresh.nothing(fresh.hook(fresh.payload("git push origin HEAD:other")))


def test_the_hook_acts_on_the_worktree_that_contains_a_subdirectory(
    world: World,
) -> None:
    sub = world.repo / "sub" / "dir"
    sub.mkdir(parents=True)
    assert world.hook(world.payload(cwd=sub), cwd=world.tmp_path).returncode == 0
    assert world.api.asked(PULLS)[0].query["head"] == f"acme:{BRANCH}"


def test_the_hook_acts_on_a_linked_worktree_whose_branch_was_pushed(
    world: World,
) -> None:
    world.git(world.repo, "branch", "topic")
    world.push("origin", "topic")
    linked = world.tmp_path / "linked"
    world.git(world.repo, "worktree", "add", "-q", str(linked), "topic")
    world.hook(world.payload("git push origin topic", cwd=linked), cwd=world.tmp_path)
    assert world.api.asked(PULLS)[0].query["head"] == "acme:topic"


def test_the_hook_does_nothing_outside_a_worktree(world: World) -> None:
    outside = world.tmp_path / "outside"
    outside.mkdir()
    world.nothing(world.hook(world.payload(cwd=outside)))


def test_the_hook_does_nothing_for_a_directory_that_does_not_exist(
    world: World,
) -> None:
    gone = world.tmp_path / "gone"
    world.nothing(world.hook(world.payload(cwd=gone)))


@pytest.mark.parametrize(
    "cwd",
    [
        pytest.param("/tmp/a\0b", id="a NUL character"),
        pytest.param("\ud800", id="a lone surrogate"),
    ],
)
def test_the_hook_does_nothing_for_a_directory_the_system_cannot_take(
    world: World, cwd: str
) -> None:
    world.nothing(world.hook(world.payload(cwd=Path(cwd))))


# --- The hook acts for a commit that demands the check ------------------------------------------


def test_the_hook_does_nothing_for_a_commit_without_the_trailer(world: World) -> None:
    world.commit("plain", trailer=None)
    world.landed()
    world.nothing(world.hook())


def test_the_hook_acts_for_a_configured_trailer_key(fresh: World) -> None:
    fresh.config('trailer = { key = "Full-Check", value = "yes" }')
    fresh.commit(trailer="Full-Check: yes")
    fresh.push("origin", BRANCH)
    fresh.hook()
    assert [r.route for r in fresh.api.requests][:1] == [PULLS]


def test_the_hook_acts_for_a_legacy_trailer_key(fresh: World) -> None:
    fresh.config('legacy_keys = ["Full-Pre-Push"]')
    fresh.commit(trailer="Full-Pre-Push: required")
    fresh.push("origin", BRANCH)
    fresh.hook()
    assert [r.route for r in fresh.api.requests][:1] == [PULLS]


def test_the_hook_does_nothing_when_the_commit_holds_no_config(world: World) -> None:
    world.git(world.repo, "rm", "-q", "--cached", ".prepush-ci.toml")
    world.commit()
    world.landed()
    world.recorded()
    world.nothing(world.hook())


def test_the_hook_reads_a_config_in_pyproject_toml(world: World) -> None:
    world.git(world.repo, "rm", "-q", ".prepush-ci.toml")
    (world.repo / "pyproject.toml").write_text('[tool.prepush-ci]\ncheck = "true"\n')
    world.git(world.repo, "add", "pyproject.toml")
    world.commit()
    world.landed()
    world.recorded()
    world.hook()
    assert [r.route for r in world.api.requests][:1] == [PULLS]


def test_the_hook_does_nothing_when_the_committed_config_is_invalid(
    world: World,
) -> None:
    (world.repo / ".prepush-ci.toml").write_text('check = "true"\nbogus = 1\n')
    world.git(world.repo, "add", ".prepush-ci.toml")
    world.commit()
    world.landed()
    world.recorded()
    world.nothing(world.hook())


# --- Only a recorded pass is shown ---------------------------------------------------------------


def test_the_hook_goes_on_after_a_push_that_recorded_a_pass(world: World) -> None:
    refs = world.git(world.repo, "for-each-ref", "refs/prepush-ci/results").stdout
    assert world.tree in refs
    world.hook()
    assert world.api.asked(PULLS)


def test_the_hook_does_nothing_for_a_push_with_no_verify(fresh: World) -> None:
    fresh.commit()
    fresh.push("--no-verify", "origin", BRANCH)
    fresh.nothing(fresh.hook())


def test_the_hook_does_nothing_for_a_push_with_another_hooks_path(fresh: World) -> None:
    fresh.commit()
    nowhere = fresh.tmp_path / "nowhere"
    nowhere.mkdir()
    fresh.push("origin", BRANCH, options=("-c", f"core.hooksPath={nowhere}"))
    pushed = f"git -c core.hooksPath={nowhere} push origin {BRANCH}"
    fresh.nothing(fresh.hook(fresh.payload(pushed)))


def test_the_hook_does_nothing_when_the_cache_is_off(fresh: World) -> None:
    fresh.config("cache = false")
    fresh.commit()
    fresh.push("origin", BRANCH)
    fresh.nothing(fresh.hook())


def test_the_hook_does_nothing_for_a_pass_of_another_tree(world: World) -> None:
    (world.repo / "other.txt").write_text("other\n")
    world.git(world.repo, "add", "other.txt")
    world.commit("other tree")
    world.push("--no-verify", "origin", BRANCH)
    world.nothing(world.hook())


def test_the_hook_goes_on_for_an_amended_commit_of_a_tree_that_passed(
    world: World,
) -> None:
    world.git(
        world.repo,
        "commit",
        "--amend",
        "--allow-empty",
        "-q",
        "-m",
        "reworded",
        "-m",
        TRAILER,
    )
    world.push("--no-verify", "--force", "origin", BRANCH)
    world.hook()
    assert world.api.asked(PULLS)


# --- The pull request of the branch ---------------------------------------------------------------


def test_the_hook_asks_for_the_open_pull_request_of_the_branch(world: World) -> None:
    world.hook()
    pulls = world.api.asked(PULLS)
    assert [r.method for r in pulls] == ["GET"]
    assert pulls[0].query["state"] == "open"
    assert pulls[0].query["head"] == f"acme:{BRANCH}"
    assert pulls[0].query["per_page"] == "100"
    assert world.api.asked(COMMENTS)


def test_the_hook_sends_no_further_request_when_there_is_no_pull_request(
    world: World,
) -> None:
    world.api.pulls = []
    result = world.hook()
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    assert [r.route for r in world.api.requests] == [PULLS]


def test_the_hook_does_nothing_for_a_remote_that_is_not_on_github(world: World) -> None:
    world.git(
        world.repo, "remote", "set-url", "origin", str(world.tmp_path / "remote.git")
    )
    without = {k: v for k, v in world.environment().items() if k != "GITHUB_API_URL"}
    world.nothing(world.hook(environment=without))


def test_the_hook_takes_the_repository_from_the_environment(world: World) -> None:
    world.git(
        world.repo, "remote", "set-url", "origin", str(world.tmp_path / "remote.git")
    )
    world.hook(env={"GITHUB_REPOSITORY": "acme/widgets"})
    assert world.api.asked(PULLS)[0].query["head"] == f"acme:{BRANCH}"


# --- The comment is the Markdown of report ---------------------------------------------------------


def markdown_of_report(world: World) -> str:
    # On Windows the ascii variant changes nothing, so report writes its stdout in the ANSI code
    # page; ask for UTF-8 there so the spec reads it back whole.
    utf8_out = {"PYTHONIOENCODING": "utf-8"} if sys.platform == "win32" else {}
    shown = subprocess.run(
        [
            sys.executable,
            "-m",
            "prepush_ci",
            "report",
            "--markdown",
            "--result",
            "passed",
            "--tree",
            world.tree,
        ],
        cwd=world.repo,
        env={**os.environ, **utf8_out},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return shown.rstrip("\n")


def test_the_comment_is_what_report_prints_as_markdown(
    world: World, printed: Callable[[str], str]
) -> None:
    world.drop_passes()
    world.forge_pass("feed", None, 1_700_000_000)
    world.hook()
    assert printed(world.comment_body()) == markdown_of_report(world)


def test_the_comment_names_the_commit(world: World) -> None:
    world.hook()
    assert world.sha in world.comment_body()
    assert world.comment_body().startswith(MARKER + "\n")


# --- The facts of the run follow the markdown ---------------------------------------------------

FACTS = {
    "seconds": 492,
    "tests": [812, 0, 3],
    "files": [["tests/a_spec.py", 3, 0, 1], ["tests/b_spec.py", 2, 1, 0]],
    "other": [806, 0, 2],
    "coverage": "94.5",
    "ruff": 2,
}
VISIBLE = (
    "Facts of the run: 812 passed, 0 failed, 3 skipped; coverage 94.5%; duration 8m 12s"
)


def test_the_facts_follow_the_markdown_after_a_blank_line(
    world: World, printed: Callable[[str], str]
) -> None:
    world.drop_passes()
    world.forge_pass("feed", FACTS, 1_700_000_000)

    world.hook()

    body = printed(world.comment_body())
    assert body.startswith(markdown_of_report(world) + "\n\n" + VISIBLE + "\n")


def test_the_facts_are_those_of_the_latest_pass_for_the_tree(world: World) -> None:
    world.drop_passes()
    world.forge_pass("aaa", {"seconds": 5, "tests": [40, 0, 0]}, 1_700_000_000)
    world.forge_pass("bbb", {"seconds": 6, "tests": [812, 0, 0]}, 1_700_000_100)

    world.hook()

    assert "812 passed" in world.comment_body()
    assert "40 passed" not in world.comment_body()


def test_the_facts_of_an_older_pass_are_not_shown_when_the_latest_pass_has_none(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("aaa", FACTS, 1_700_000_000)
    world.forge_pass("bbb", None, 1_700_000_100)

    world.hook()

    assert "Facts of the run" not in world.comment_body()
    assert "<details>" not in world.comment_body()


def test_of_equal_dates_the_facts_are_those_of_the_ref_whose_name_sorts_last(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("ccc", {"seconds": 3, "tests": [3, 0, 0]}, 1_700_000_000)
    world.forge_pass("aaa", {"seconds": 1, "tests": [1, 0, 0]}, 1_700_000_000)

    world.hook()

    assert "3 passed" in world.comment_body()


def test_the_visible_line_holds_the_tests_the_coverage_and_the_duration(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("feed", FACTS, 1_700_000_000)

    world.hook()

    assert VISIBLE in world.comment_body().split("\n")


def test_the_visible_line_of_a_pass_with_only_a_duration_has_no_details(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("feed", {"seconds": 492}, 1_700_000_000)

    world.hook()

    assert "Facts of the run: duration 8m 12s" in world.comment_body().split("\n")
    assert "<details>" not in world.comment_body()


def test_a_pass_without_facts_adds_neither_the_line_nor_the_details(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("feed", None, 1_700_000_000)

    world.hook()

    assert "Facts of the run" not in world.comment_body()
    assert "<details>" not in world.comment_body()


def test_a_pass_whose_facts_cannot_be_read_adds_neither_the_line_nor_the_details(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("feed", "not json", 1_700_000_000)

    world.hook()

    assert "Facts of the run" not in world.comment_body()
    assert "<details>" not in world.comment_body()


def test_the_details_are_collapsed_and_hold_the_tools_and_the_test_files(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("feed", FACTS, 1_700_000_000)

    world.hook()

    body = world.comment_body()
    visible, details = body.split("<details>", 1)
    assert VISIBLE in visible
    assert "<summary>Details</summary>" in details
    assert VISIBLE not in details
    for row in (
        "| Tests |",
        "| Coverage |",
        "| Ruff |",
        "tests/a_spec.py",
        "tests/b_spec.py",
    ):
        assert row in details


def test_nothing_the_check_printed_reaches_the_comment(fresh: World) -> None:
    shout = fresh.tmp_path / "shout.py"
    shout.write_text(
        'print("TOKEN=" + "abc" + "123")\n'
    )  # the command never holds the text
    python = Path(sys.executable).as_posix()
    fresh.config(check=f'"{python}" "{shout.as_posix()}"')
    fresh.commit()
    fresh.push("origin", BRANCH)

    fresh.hook()

    assert "abc123" not in fresh.comment_body()
    assert "Facts of the run" in fresh.comment_body()


def test_a_pass_on_this_commit_says_so_on_the_second_line_of_the_facts(
    world: World,
) -> None:
    world.hook()

    lines = world.comment_body().split("\n")
    start = next(
        n for n, line in enumerate(lines) if line.startswith("Facts of the run")
    )
    assert lines[start + 1] == "Checked on this commit."


def test_a_pass_recorded_for_an_amended_commit_names_the_earlier_commit(
    world: World,
) -> None:
    earlier = world.sha
    world.git(
        world.repo,
        "commit",
        "--amend",
        "--allow-empty",
        "-q",
        "-m",
        "amended",
        "-m",
        TRAILER,
    )
    world.push("--force", "--no-verify", "origin", BRANCH)

    world.hook()

    lines = world.comment_body().split("\n")
    start = next(
        n for n, line in enumerate(lines) if line.startswith("Facts of the run")
    )
    assert lines[start + 1] == f"Reused from the run on {earlier[:12]}, same tree."


def test_a_commit_pushed_twice_keeps_the_facts_of_its_first_run(world: World) -> None:
    world.push("origin", "HEAD:other")

    world.hook()

    lines = world.comment_body().split("\n")
    start = next(
        n for n, line in enumerate(lines) if line.startswith("Facts of the run")
    )
    assert lines[start + 1] == "Checked on this commit."


def test_a_pass_fetched_from_origin_brings_its_facts(
    world: World, git: Git, tmp_path: Path, api: Api
) -> None:
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(clone))
    git(clone, "config", "user.name", "Test")
    git(clone, "config", "user.email", "test@example.com")
    git(clone, "config", "commit.gpgsign", "false")
    hook = clone / ".git" / "hooks" / "pre-push"
    hook.write_text(
        f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" -m prepush_ci hook pre-push "$@"\n'
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    git(clone, "switch", "-q", BRANCH)
    there = World(clone, git, api, tmp_path)
    assert there.passes() == []  # the clone has no pass of its own

    pushed = git(clone, "push", "origin", "HEAD:other")
    there.on_github()

    assert "origin holds a result" in pushed.stderr
    there.hook()
    assert "Facts of the run" in there.comment_body()
    assert "Checked on this commit." in there.comment_body()


# --- One comment per check, found by its marker ----------------------------------------------------


def test_the_comment_that_starts_with_the_marker_is_the_one_updated(
    world: World,
) -> None:
    world.api.comments = [
        {"id": 1, "body": f"I saw {MARKER} in the middle of this"},
        {"id": 2, "body": f"{MARKER}\nCommit {'0' * 40}"},
    ]
    world.hook()
    (patch,) = world.api.writes()
    assert (patch.method, patch.route) == (
        "PATCH",
        "/repos/acme/widgets/issues/comments/2",
    )
    assert world.sha in patch.json()["body"]
    assert world.api.comments[0]["body"] == f"I saw {MARKER} in the middle of this"


def test_the_comment_past_the_first_page_is_found(world: World) -> None:
    world.api.comments = [{"id": n, "body": f"chat {n}"} for n in range(1, 101)]
    world.api.comments.append({"id": 101, "body": f"{MARKER}\nold"})
    world.hook()
    pages = [r.query["page"] for r in world.api.asked(COMMENTS) if r.method == "GET"]
    assert pages == ["1", "2"]
    (patch,) = world.api.writes()
    assert patch.route.endswith("/issues/comments/101")


def test_the_comment_of_another_check_is_left_alone_and_a_new_one_is_created(
    world: World,
) -> None:
    other = "<!-- prepush-ci:prepush-ci / unit -->\nsomething"
    world.api.comments = [{"id": 1, "body": other}]
    world.hook()
    (post,) = world.api.writes()
    assert post.method == "POST"
    assert world.api.comments[0]["body"] == other
    assert str(world.api.comments[1]["body"]).startswith(MARKER)


# --- A wrapped push is a push -----------------------------------------------------------------

WRAPPED = "(time git push --force-with-lease) 2>&1 | tail -25"


def test_a_wrapped_push_updates_the_comment(world: World) -> None:
    world.api.comments = [{"id": 2, "body": f"{MARKER}\nCommit {'0' * 40}"}]
    world.git(
        world.repo,
        "commit",
        "--amend",
        "--allow-empty",
        "-q",
        "-m",
        "reworded",
        "-m",
        TRAILER,
    )
    world.push("--no-verify", "--force", "origin", BRANCH)
    world.hook(world.payload(WRAPPED))
    (patch,) = world.api.writes()
    assert (patch.method, patch.route) == (
        "PATCH",
        "/repos/acme/widgets/issues/comments/2",
    )
    assert world.sha in patch.json()["body"]


def test_a_wrapped_push_that_did_not_land_sends_no_request(world: World) -> None:
    world.commit("more", trailer=None)  # the same tree, so a pass is recorded for it
    world.nothing(world.hook(world.payload("(time git push origin main) 2>&1 | tail")))


# --- The comment is replaced, left alone or created ---------------------------------------------------


def test_a_comment_is_created_when_none_starts_with_the_marker(world: World) -> None:
    world.api.comments = [{"id": 1, "body": "hello"}, {"id": 2, "body": "world"}]
    world.hook()
    (post,) = world.api.writes()
    assert (post.method, post.route) == ("POST", COMMENTS)
    assert post.json()["body"].startswith(MARKER)


def test_the_same_text_is_not_written_again(world: World) -> None:
    world.hook()
    sent = len(world.api.requests)
    assert world.hook().returncode == 0
    assert [r.method for r in world.api.requests[sent:]] == ["GET", "GET"]


def test_a_new_commit_replaces_the_text_of_the_comment(world: World) -> None:
    world.hook()
    first = world.comment_body()
    world.commit("again")
    world.landed()
    world.recorded()
    world.hook()
    assert [r.method for r in world.api.writes()] == ["POST", "PATCH"]
    assert world.comment_body() != first
    assert world.sha in world.comment_body()


def test_the_hook_uses_only_the_rest_api_and_prints_nothing_on_standard_output(
    world: World,
) -> None:
    results = [world.hook()]
    world.commit("again")
    world.landed()
    world.recorded()
    results.append(world.hook())
    assert [r.stdout for r in results] == ["", ""]
    assert not [r for r in world.api.requests if "graphql" in r.route]
    assert [r.method for r in world.api.writes()] == ["POST", "PATCH"]


# --- The credentials are the token's, if there is one -----------------------------------------------------


def test_every_request_carries_the_token(world: World) -> None:
    world.hook(env={"GITHUB_TOKEN": "t0k"})
    assert world.api.requests
    assert {r.headers["authorization"] for r in world.api.requests} == {"Bearer t0k"}


def test_the_token_comes_from_gh_token_when_github_token_is_empty(world: World) -> None:
    world.hook(env={"GITHUB_TOKEN": "", "GH_TOKEN": "g0k"})
    assert {r.headers["authorization"] for r in world.api.requests} == {"Bearer g0k"}


def test_no_authorization_header_is_sent_without_a_token(world: World) -> None:
    world.hook()
    assert world.api.requests
    assert all("authorization" not in r.headers for r in world.api.requests)


# --- The whole run is bounded ----------------------------------------------------------------------------------


def test_a_server_that_never_answers_makes_the_hook_give_up_within_20_seconds(
    world: World,
) -> None:
    world.api.hang_on = PULLS
    started = time.monotonic()
    result = world.hook()
    assert time.monotonic() - started < 20
    assert result.returncode == 0
    assert result.stdout == ""
    lines = result.stderr.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("prepush-ci:")
    assert "gave up" in lines[0]


def test_a_server_that_trickles_its_answer_makes_the_hook_give_up_within_20_seconds(
    world: World,
) -> None:
    world.api.trickle_on = PULLS
    started = time.monotonic()
    result = world.hook()
    assert time.monotonic() - started < 20
    assert result.returncode == 0
    assert result.stdout == ""
    (line,) = result.stderr.splitlines()
    assert line.startswith("prepush-ci:")
    assert "gave up" in line


def test_a_slow_server_that_answers_in_time_gets_its_comment(world: World) -> None:
    world.api.delay = 1.0
    result = world.hook()
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    assert len(world.api.comments) == 1


# --- A failure to post is one line -------------------------------------------------------------------------------


def test_a_refused_write_is_one_line_with_the_status_and_the_message(
    world: World,
) -> None:
    world.api.answer(
        f"POST {COMMENTS}", 403, json.dumps({"message": "Resource not accessible"})
    )
    result = world.hook()
    assert result.returncode == 0
    (line,) = result.stderr.splitlines()
    assert line.startswith("prepush-ci:")
    assert "403" in line
    assert "Resource not accessible" in line


def test_a_refused_lookup_is_one_line_and_asks_for_no_comments(world: World) -> None:
    world.api.answer(PULLS, 401, json.dumps({"message": "Bad credentials"}))
    result = world.hook()
    assert result.returncode == 0
    (line,) = result.stderr.splitlines()
    assert "401" in line
    assert not world.api.asked(COMMENTS)


def test_an_unreachable_server_is_one_line_that_says_the_request_could_not_be_sent(
    world: World, unused_address: str
) -> None:
    result = world.hook(env={"GITHUB_API_URL": unused_address})
    assert result.returncode == 0
    (line,) = result.stderr.splitlines()
    assert line.startswith("prepush-ci:")
    assert "could not be sent" in line


def test_a_redirect_is_refused_and_not_followed(world: World, other_api: Api) -> None:
    world.api.redirect_to = other_api.url
    world.api.answer(PULLS, 301)
    result = world.hook(env={"GITHUB_TOKEN": "t0k"})
    assert result.returncode == 0
    (line,) = result.stderr.splitlines()
    assert "301" in line
    assert other_api.requests == []


def test_the_token_appears_on_neither_stream(world: World) -> None:
    world.api.answer(PULLS, 401, json.dumps({"message": "bad t0k-secret here"}))
    result = world.hook(env={"GITHUB_TOKEN": "t0k-secret"})
    assert "t0k-secret" not in result.stdout + result.stderr
    assert "401" in result.stderr


@pytest.mark.parametrize("answer", ['{"not": "a list"}', DEEP])
def test_an_answer_that_is_not_what_the_api_documents_is_one_line(
    world: World, answer: str
) -> None:
    world.api.answer(PULLS, 200, answer)
    result = world.hook()
    assert result.returncode == 0
    (line,) = result.stderr.splitlines()
    assert line.startswith("prepush-ci:")
    assert world.api.asked(COMMENTS) == []


@pytest.mark.parametrize("answer", ['[{"id": 1}]', DEEP])
def test_a_page_of_comments_that_is_not_what_the_api_documents_is_one_line(
    world: World, answer: str
) -> None:
    world.api.answer(f"GET {COMMENTS}", 200, answer)
    result = world.hook()
    assert result.returncode == 0
    (line,) = result.stderr.splitlines()
    assert line.startswith("prepush-ci:")
    assert world.api.writes() == []


def test_the_hook_decides_by_the_commit_when_the_worktree_config_cannot_be_read(
    world: World,
) -> None:
    (world.repo / ".prepush-ci.toml").write_text("bogus = [\n")
    world.hook()
    assert len(world.api.comments) == 1


# --- Only a pass of the committed config is shown -----------------------------------------------


def push_with_ignored_config(
    fresh: World, committed_check: str, *worktree_lines: str
) -> None:
    """Push a trailer commit whose committed config (in `pyproject.toml`) has `committed_check`,
    while the ignored `.prepush-ci.toml` that wins in the worktree has the check that logs to
    `ran.log`, with `worktree_lines` added."""
    (fresh.repo / "pyproject.toml").write_text(
        f"[tool.prepush-ci]\ncheck = '{committed_check}'\nrequire_up_to_date = false\n"
    )
    (fresh.repo / ".gitignore").write_text(".prepush-ci.toml\n")
    fresh.git(fresh.repo, "rm", "-q", "--cached", ".prepush-ci.toml")
    log = fresh.tmp_path / "ran.log"
    (fresh.repo / ".prepush-ci.toml").write_text(
        "\n".join(
            [
                f"check = 'echo ran >> {log.as_posix()}'",
                "require_up_to_date = false",
                *worktree_lines,
                "",
            ]
        )
    )
    fresh.git(fresh.repo, "add", "pyproject.toml", ".gitignore")
    fresh.commit()
    fresh.push("origin", BRANCH)
    fresh.landed()


def test_a_pass_of_a_check_that_is_not_the_committed_one_shows_nothing(
    fresh: World,
) -> None:
    push_with_ignored_config(fresh, "scripts/ci")

    assert len(fresh.passes()) == 1
    fresh.nothing(fresh.hook())


def test_a_pass_with_another_require_env_shows_nothing(fresh: World) -> None:
    push_with_ignored_config(
        fresh,
        f"echo ran >> {(fresh.tmp_path / 'ran.log').as_posix()}",
        'require_env = ["PATH"]',
    )

    assert len(fresh.passes()) == 1
    fresh.nothing(fresh.hook())


def test_a_pass_without_a_digest_shows_nothing(world: World) -> None:
    world.drop_passes()
    world.forge_pass("feed", FACTS, 1_700_000_000, digest=None)

    world.nothing(world.hook())


def test_the_facts_of_an_older_pass_of_the_committed_config_are_shown_beside_a_later_pass_of_another(
    world: World,
) -> None:
    world.drop_passes()
    world.forge_pass("aaa", {"seconds": 5, "tests": [40, 0, 0]}, 1_700_000_000)
    world.forge_pass(
        "bbb", {"seconds": 6, "tests": [812, 0, 0]}, 1_700_000_100, digest="f" * 32
    )

    world.hook()

    assert "40 passed" in world.comment_body()
    assert "812 passed" not in world.comment_body()
