"""Decisions about the landing ruleset: the request that creates it and the reading of GitHub's
answers.

No I/O: `app ruleset` and `doctor` send the requests.
"""

import json
from dataclasses import dataclass
from typing import Any

from prepush_ci.core.report import Malformed, ReportError

NAME = "prepush-ci landing"
DEFAULT_BRANCH = "~DEFAULT_BRANCH"
RULES = ("update", "non_fast_forward", "deletion")
ALWAYS = "always"
ADMIN_ROLE = "RepositoryRole"
ADMIN_ROLE_ID = 5  # GitHub's id of the repository-admin role
APP = "Integration"
ADMIN = "the repository-admin role"
_UNDOCUMENTED = "the answer is not what the API documents for rulesets"


@dataclass(frozen=True)
class Actor:
    actor_id: int
    actor_type: str


ADMIN_ACTOR = Actor(ADMIN_ROLE_ID, ADMIN_ROLE)


def app_actor(app_id: int) -> Actor:
    return Actor(app_id, APP)


def describe(actor: Actor) -> str:
    return ADMIN if actor == ADMIN_ACTOR else f"the app {actor.actor_id}"


def parse_app_id(text: str) -> int:
    if not (text.isascii() and text.isdigit() and int(text) >= 1):
        raise Malformed(f"expects a whole number of 1 or more, got {text!r}")
    return int(text)


def body(actor: Actor) -> dict[str, object]:
    """The ruleset `app ruleset` creates: the three rules, no pull request rule, and the actor
    as the only one that may bypass them."""
    return {
        "name": NAME,
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": [DEFAULT_BRANCH], "exclude": []}},
        "rules": [{"type": kind} for kind in RULES],
        "bypass_actors": [
            {
                "actor_id": actor.actor_id,
                "actor_type": actor.actor_type,
                "bypass_mode": ALWAYS,
            }
        ],
    }


# --- GitHub's answers ------------------------------------------------------------------------------


def load_object(text: str) -> dict[str, Any]:
    try:
        found = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise ReportError(_UNDOCUMENTED) from error
    return as_dict(found, strict=True)


def as_dict(value: object, *, strict: bool = False) -> dict[str, Any]:
    """`value` as an object; an absent one (None) is empty unless `strict`."""
    if isinstance(value, dict):
        return value
    if value is None and not strict:
        return {}
    raise ReportError(_UNDOCUMENTED)


def as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    raise ReportError(_UNDOCUMENTED)


def _id(entry: dict[str, Any]) -> str:
    found = entry.get("id")
    if isinstance(found, int) and not isinstance(found, bool):
        return str(found)
    raise ReportError(_UNDOCUMENTED)


def listed_id(text: str) -> str | None:
    """The id of the ruleset named `NAME` in the listing of a repository's rulesets, else None."""
    try:
        listing = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise ReportError(_UNDOCUMENTED) from error
    if not isinstance(listing, list):
        raise ReportError(_UNDOCUMENTED)
    for entry in map(as_dict, listing):
        if entry.get("name") == NAME:
            return _id(entry)
    return None


@dataclass(frozen=True)
class Created:
    ruleset_id: str
    address: str | None


def page_address(found: dict[str, Any]) -> str | None:
    href = as_dict(as_dict(found.get("_links")).get("html")).get("href")
    return href if isinstance(href, str) else None


def created(text: str) -> Created:
    """The id of the ruleset GitHub made, and the address of its page when it names one."""
    found = load_object(text)
    return Created(_id(found), page_address(found))
