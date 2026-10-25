"""The few requests `prepush-ci report` makes to the GitHub API, over `urllib`."""

import contextlib
import http.client
import json
import queue
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from urllib.parse import quote

from prepush_ci import text_io
from prepush_ci.core.report import ReportError, Repository

TIMEOUT_SECONDS = 30
PER_PAGE = 100
SHORTEST_WAIT = 0.001  # a request is never given no time at all


class ApiError(ReportError):
    """The API answered with an error status (`status`), or could not be reached (None);
    `timed_out` when it did not answer in time."""

    def __init__(
        self, message: str, status: int | None, timed_out: bool = False
    ) -> None:
        super().__init__(message)
        self.status = status
        self.timed_out = timed_out


class _Refuse3xx(urllib.request.HTTPRedirectHandler):
    """A redirect is an error: urllib would repeat a POST as a GET (nothing posted, exit 0) and carry
    the `Authorization` header to whatever host `Location` names."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


_send_request = urllib.request.build_opener(_Refuse3xx).open


def _repo_path(repository: Repository) -> str:
    return (
        f"/repos/{quote(repository.owner, safe='')}/{quote(repository.name, safe='')}"
    )


def _message(body: bytes) -> str:
    text = text_io.decode(body).strip()
    try:
        message = json.loads(text)["message"]
    except (ValueError, KeyError, TypeError):
        message = text
    return " ".join(str(message).split()) or "(no message)"


def _request(
    method: str, api_url: str, path: str, token: str | None, payload: object
) -> urllib.request.Request:
    return urllib.request.Request(
        text_io.to_os(api_url + path),
        data=None if payload is None else text_io.encode(json.dumps(payload)),
        method=method,
        headers={
            **({} if token is None else {"Authorization": f"Bearer {token}"}),
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "prepush-ci",
            "Content-Type": "application/json",
        },
    )


@contextlib.contextmanager
def _api_errors(method: str, path: str) -> Iterator[None]:
    """Turn what a request can raise into an `ApiError` naming the status and GitHub's message."""
    try:
        yield
    except urllib.error.HTTPError as error:
        raise ApiError(
            f"{method} {path} answered {error.code}: {_message(error.read())}",
            error.code,
        ) from error
    except ValueError as error:
        # An address or a header value urllib refuses; either may hold a secret, so none is quoted.
        raise ApiError(
            f"{method} {path}: the request could not be sent "
            "(the API address or a credential is not usable)",
            None,
        ) from error
    except (OSError, http.client.HTTPException) as error:
        timed_out = isinstance(getattr(error, "reason", error), TimeoutError)
        raise ApiError(
            f"{method} {path}: the request could not be sent ({error})", None, timed_out
        ) from error


def _read(request: urllib.request.Request, timeout: float) -> bytes:
    with _send_request(request, timeout=timeout) as response:
        return bytes(response.read())


def send(
    method: str,
    api_url: str,
    path: str,
    token: str | None,
    payload: object = None,
) -> bytes:
    """One request, with no credential when `token` is None, that waits `TIMEOUT_SECONDS` for each
    step; the answer's body, or an `ApiError` naming the status and GitHub's message."""
    with _api_errors(method, path):
        return _read(_request(method, api_url, path, token, payload), TIMEOUT_SECONDS)


def _field(body: bytes, name: str, what: str) -> str:
    try:
        return str(json.loads(text_io.decode(body))[name])
    except (ValueError, KeyError, TypeError) as error:
        raise ReportError(f"the answer to {what} has no {name}") from error


def post_status(
    api_url: str, repository: Repository, sha: str, token: str, body: object
) -> None:
    send("POST", api_url, f"{_repo_path(repository)}/statuses/{sha}", token, body)


def post_check_run(
    api_url: str, repository: Repository, token: str, body: object
) -> bytes:
    """Create a check run; GitHub's answer, which names its id (see `check_run_id`)."""
    return send("POST", api_url, f"{_repo_path(repository)}/check-runs", token, body)


def check_run_id(created: bytes) -> str:
    return _field(created, "id", "the check run request")


def update_check_run(
    api_url: str, repository: Repository, token: str, run_id: str, body: object
) -> None:
    path = f"{_repo_path(repository)}/check-runs/{quote(run_id, safe='')}"
    send("PATCH", api_url, path, token, body)


def in_progress_run(
    api_url: str, repository: Repository, token: str, sha: str, name: str, app_id: str
) -> str | None:
    """The id of the check run of that name and app that is in progress on the commit, the highest
    when there are several; None when there is none."""
    query = f"check_name={quote(name, safe='')}&status=in_progress&app_id={quote(app_id, safe='')}"
    found = send(
        "GET",
        api_url,
        f"{_repo_path(repository)}/commits/{sha}/check-runs?{query}",
        token,
    )
    try:
        ids = [
            int(run["id"]) for run in json.loads(text_io.decode(found))["check_runs"]
        ]
    except (ValueError, KeyError, TypeError) as error:
        raise ReportError(
            "the answer to the check run lookup has no check_runs with an id each"
        ) from error
    return str(max(ids)) if ids else None


def convert_manifest(api_url: str, code: str) -> str:
    """The app GitHub made from a manifest (the answer's text): the one request that needs no
    credential, since the single-use code proves the person who clicked."""
    path = f"/app-manifests/{quote(code, safe='')}/conversions"
    return text_io.decode(send("POST", api_url, path, None))


def installation_token(api_url: str, repository: Repository, app_jwt: str) -> str:
    """The token of the app's installation on the repository; the JSON Web Token proves the app."""
    try:
        found = send("GET", api_url, f"{_repo_path(repository)}/installation", app_jwt)
    except ApiError as error:
        if error.status == 404:
            raise ReportError(
                f"the app is not installed on {repository.owner}/{repository.name}"
            ) from error
        raise
    installation = _field(found, "id", "the installation lookup")
    granted = send(
        "POST",
        api_url,
        f"/app/installations/{quote(installation, safe='')}/access_tokens",
        app_jwt,
    )
    return _field(granted, "token", "the access token request")


def _unexpected(method: str, path: str) -> ApiError:
    return ApiError(f"{method} {path}: the answer is not what the API documents", None)


class PullRequestClient:
    """The requests about the pull request of a pushed branch. All of them together end by one
    deadline: `timeout` bounds each step of a request, not the request, so a server that sends a
    byte a second would never be given up on."""

    def __init__(
        self, api_url: str, repository: Repository, token: str | None, seconds: float
    ) -> None:
        self._api_url = api_url
        self._repository = repository
        self._token = token
        self._ends = time.monotonic() + seconds

    def _left(self) -> float:
        return max(self._ends - time.monotonic(), SHORTEST_WAIT)

    def _call(self, method: str, path: str, payload: object = None) -> bytes:
        """The answer's body, or an `ApiError` (`timed_out`) when the deadline comes first. The
        request runs in a thread that is left behind when it is given up on."""
        answers: queue.SimpleQueue[bytes | ApiError] = queue.SimpleQueue()
        left = self._left()

        def work() -> None:
            try:
                with _api_errors(method, path):
                    request = _request(
                        method, self._api_url, path, self._token, payload
                    )
                    answers.put(_read(request, left))
            except ApiError as error:
                answers.put(error)

        threading.Thread(target=work, daemon=True).start()
        try:
            answer = answers.get(timeout=left)
        except queue.Empty:
            raise ApiError(
                f"{method} {path}: no answer in time", None, timed_out=True
            ) from None
        if isinstance(answer, ApiError):
            raise answer
        return answer

    def open_pulls(self, branch: str) -> list[int]:
        """The numbers of the open pull requests whose head is the branch in the repository itself."""
        head = quote(f"{self._repository.owner}:{branch}", safe="")
        path = f"{_repo_path(self._repository)}/pulls?state=open&head={head}&per_page={PER_PAGE}"
        found = self._call("GET", path)
        try:
            return [int(pull["number"]) for pull in json.loads(text_io.decode(found))]
        except (ValueError, KeyError, TypeError) as error:
            raise _unexpected("GET", path) from error

    def issue_comments(self, number: int, page: int) -> list[tuple[int, str]]:
        """One page of the comments of an issue or pull request, as (id, body)."""
        path = f"{_repo_path(self._repository)}/issues/{number}/comments?per_page={PER_PAGE}&page={page}"
        found = self._call("GET", path)
        try:
            return [
                (int(comment["id"]), str(comment["body"]))
                for comment in json.loads(text_io.decode(found))
            ]
        except (ValueError, KeyError, TypeError) as error:
            raise _unexpected("GET", path) from error

    def create_comment(self, number: int, body: str) -> None:
        path = f"{_repo_path(self._repository)}/issues/{number}/comments"
        self._call("POST", path, {"body": body})

    def update_comment(self, comment_id: int, body: str) -> None:
        path = f"{_repo_path(self._repository)}/issues/comments/{comment_id}"
        self._call("PATCH", path, {"body": body})


def list_rulesets(api_url: str, repository: Repository, token: str) -> str:
    """The answer to the listing of the repository's rulesets (GitHub allows 75 at most, so one
    page of 100 holds them all); the listing has no rules and no bypass actors."""
    path = f"{_repo_path(repository)}/rulesets?per_page={PER_PAGE}"
    return text_io.decode(send("GET", api_url, path, token))


def get_ruleset(
    api_url: str, repository: Repository, token: str, ruleset_id: str
) -> str:
    """One ruleset with its rules; its bypass actors only for an administrator's token."""
    path = f"{_repo_path(repository)}/rulesets/{quote(ruleset_id, safe='')}"
    return text_io.decode(send("GET", api_url, path, token))


def create_ruleset(
    api_url: str, repository: Repository, token: str, body: object
) -> str:
    """Create a ruleset; GitHub's answer for it."""
    path = f"{_repo_path(repository)}/rulesets"
    return text_io.decode(send("POST", api_url, path, token, body))
