"""Decisions of `prepush-ci app setup`: the manifest, the page, the callback, the answer, the output.

No I/O: the command serves the page, sends the request and writes the key.
"""

import html
import json
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass

from prepush_ci.core.report import Malformed, ReportError

HOMEPAGE = "https://github.com/CapeOfGoodCode/prepush-ci"
DEFAULT_SERVER = "https://github.com"
# GitHub allows 34 characters at most in the name of an app.
MAX_NAME = 34
DEFAULT_TIMEOUT = 300
_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_INCOMPLETE = "GitHub's answer is incomplete: it needs a numeric id, a slug and a key"


def parse_app_name(text: str) -> str:
    if not text:
        raise Malformed("must not be empty")
    if len(text) > MAX_NAME:
        raise Malformed(
            f"is {len(text)} characters long; GitHub allows {MAX_NAME} at most"
        )
    return text


def default_name(owner: str) -> str:
    name = f"prepush-ci ({owner})"
    if len(name) > MAX_NAME:
        raise ReportError(
            f"the default name {name!r} is {len(name)} characters long; "
            f"GitHub allows {MAX_NAME} at most, so choose one with --name"
        )
    return name


def parse_timeout(text: str) -> int:
    if not (text.isascii() and text.isdigit() and int(text) >= 1):
        raise Malformed(f"expects a whole number of seconds of 1 or more, got {text!r}")
    return int(text)


# What an app that moves the default branch asks for (`--land`): `contents` to push it,
# `pull_requests` to read the pull request, `workflows` because GitHub refuses a push that changes
# a workflow file without it.
LAND_PERMISSIONS = {
    "checks": "write",
    "contents": "write",
    "pull_requests": "read",
    "workflows": "write",
}


def manifest(name: str, redirect_url: str, land: bool = False) -> dict[str, object]:
    """What GitHub's manifest flow needs to create the app: `checks: write` and nothing else, or
    with `land` the permissions of `LAND_PERMISSIONS`; no webhook (it would need a server to point
    at), no events, private."""
    return {
        "name": name,
        "url": HOMEPAGE,
        "redirect_url": redirect_url,
        "public": False,
        "default_events": [],
        "default_permissions": dict(LAND_PERMISSIONS) if land else {"checks": "write"},
    }


def page(action: str, manifest_data: Mapping[str, object]) -> str:
    """The page that posts the manifest to GitHub; the browser unescapes the field's value."""
    field = html.escape(json.dumps(manifest_data), quote=True)
    return (
        "<!doctype html>\n<html><body>\n"
        f'<form id="setup" method="post" action="{html.escape(action, quote=True)}">\n'
        f'<input type="hidden" name="manifest" value="{field}">\n'
        '<noscript><button type="submit">Create the GitHub App</button></noscript>\n'
        "</form>\n"
        '<script>document.getElementById("setup").submit()</script>\n'
        "</body></html>\n"
    )


def new_state() -> str:
    return secrets.token_urlsafe(24)


def callback_code(query: Mapping[str, list[str]], state: str) -> str | None:
    """The code of GitHub's redirect, or None when the callback is not the answer to this run."""
    given = query.get("state", [""])[0]
    if not secrets.compare_digest(given.encode(), state.encode()):
        return None
    return query.get("code", [""])[0] or None


@dataclass(frozen=True)
class App:
    app_id: str
    slug: str
    key: str


def parse_app(body: str) -> App:
    """The app GitHub's conversion answers with; the id and the slug end up in a path and an
    address, so they must look like what GitHub gives."""
    try:
        found = json.loads(body)
        app_id, slug, key = found["id"], found["slug"], found["pem"]
    except (ValueError, KeyError, TypeError, RecursionError) as error:
        raise ReportError(_INCOMPLETE) from error
    if isinstance(app_id, int) and not isinstance(app_id, bool):
        app_id = str(app_id)
    usable = (
        isinstance(app_id, str)
        and app_id.isascii()
        and app_id.isdigit()
        and isinstance(slug, str)
        and _SLUG.fullmatch(slug) is not None
        and isinstance(key, str)
        and key != ""
    )
    if not usable:
        raise ReportError(_INCOMPLETE)
    return App(app_id, slug, key)


def install_address(server: str, slug: str) -> str:
    return f"{server}/apps/{slug}/installations/new"


def result_text(app: App, server: str, key_path: str, land: bool = False) -> str:
    """What `report` needs, without the key itself; with `land` also the command that makes the
    app the one actor that may move the default branch."""
    text = (
        f"created the app {app.slug} (id {app.app_id})\n"
        f"key saved to {key_path}\n"
        f"install it on your repositories: {install_address(server, app.slug)}\n"
        "then give report these two variables:\n"
        f"  PREPUSH_CI_APP_ID={app.app_id}\n"
        "  PREPUSH_CI_APP_KEY=<the text of the key file>"
    )
    if not land:
        return text
    return (
        f"{text}\n"
        "once the app is installed on the repository, let it alone move the default branch:\n"
        f"  prepush-ci app ruleset --app {app.app_id}"
    )
