"""The few requests `prepush-ci report` makes to the GitHub API, over `urllib`."""

import http.client
import json
import urllib.error
import urllib.request
from urllib.parse import quote

from prepush_ci import text_io
from prepush_ci.core.report import ReportError, Repository

TIMEOUT_SECONDS = 30


class ApiError(ReportError):
    """The API answered with an error status (`status`), or could not be reached (None)."""

    def __init__(self, message: str, status: int | None) -> None:
        super().__init__(message)
        self.status = status


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


def send(
    method: str, api_url: str, path: str, token: str, payload: object = None
) -> bytes:
    """One request; the answer's body, or an `ApiError` naming the status and GitHub's message."""
    try:
        request = urllib.request.Request(
            text_io.to_os(api_url + path),
            data=None if payload is None else text_io.encode(json.dumps(payload)),
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "prepush-ci",
                "Content-Type": "application/json",
            },
        )
        with _send_request(request, timeout=TIMEOUT_SECONDS) as response:
            return bytes(response.read())
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
        raise ApiError(
            f"{method} {path}: the request could not be sent ({error})", None
        ) from error


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
