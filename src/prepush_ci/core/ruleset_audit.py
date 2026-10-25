"""What `doctor --ruleset` makes of a ruleset that exists: whether it is the landing ruleset, with
one bypass actor that can push.

No I/O: `doctor` sends the requests.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Any

from prepush_ci.core.report import ReportError
from prepush_ci.core.ruleset import (
    ADMIN,
    ADMIN_ROLE,
    ADMIN_ROLE_ID,
    ALWAYS,
    APP,
    DEFAULT_BRANCH,
    RULES,
    as_dict,
    as_list,
    load_object,
    page_address,
)

# The one parameter `update` takes; set to false it means what its absence means.
_FETCH_AND_MERGE = "update_allows_fetch_and_merge"


class ActorsHidden(ReportError):
    """The answer has no `bypass_actors`: GitHub leaves them out for a token that is not an
    administrator's."""


@dataclass(frozen=True)
class Audit:
    """What is wrong with a ruleset (empty: nothing), who may bypass it when that is as it should
    be, and the address of its page when GitHub names one."""

    problems: tuple[str, ...]
    actor: str
    address: str | None


def _where(found: dict[str, Any]) -> list[str]:
    problems = []
    if found.get("enforcement") != "active":
        problems.append(f"enforcement is `{found.get('enforcement')}`, not `active`")
    if found.get("target") != "branch":
        problems.append(f"the target is `{found.get('target')}`, not `branch`")
    ref_name = as_dict(as_dict(found.get("conditions")).get("ref_name"))
    included = [str(ref) for ref in as_list(ref_name.get("include"))]
    if DEFAULT_BRANCH not in included:
        shown = ", ".join(f"`{ref}`" for ref in included) or "nothing"
        problems.append(f"`{DEFAULT_BRANCH}` is not included (it includes {shown})")
    problems.extend(
        f"it excludes `{ref}`" for ref in map(str, as_list(ref_name.get("exclude")))
    )
    return problems


def _rules(found: dict[str, Any]) -> list[str]:
    rules = [as_dict(rule, strict=True) for rule in as_list(found.get("rules"))]
    counts = Counter(str(rule.get("type")) for rule in rules)
    problems = [
        f"has the rule `{kind}`" for kind in sorted(counts) if kind not in RULES
    ]
    for kind in RULES:
        if counts[kind] == 0:
            problems.append(f"lacks the rule `{kind}`")
        elif counts[kind] > 1:
            problems.append(f"has the rule `{kind}` {counts[kind]} times")
    for rule in rules:
        kind = str(rule.get("type"))
        parameters = as_dict(rule.get("parameters"))
        harmless = {} if kind != "update" else {_FETCH_AND_MERGE: False}
        if kind in RULES and parameters not in ({}, harmless):
            problems.append(f"the rule `{kind}` carries parameters")
    return problems


def _name(actor: dict[str, Any]) -> str:
    kind, found = actor.get("actor_type"), actor.get("actor_id")
    return f"{kind}" if found is None else f"{kind} {found}"


def _actors(found: dict[str, Any], app_id: str | None) -> tuple[list[str], str]:
    """The problems with the bypass actors, and who the one actor is when it is as it should be."""
    actors = [as_dict(actor, strict=True) for actor in as_list(found["bypass_actors"])]
    if not actors:
        return ["lists no bypass actor"], ""
    if len(actors) > 1:
        named = ", ".join(map(_name, actors))
        return [f"lists {len(actors)} bypass actors ({named}), not one"], ""
    only = actors[0]
    problems = []
    who = ""
    kind, number = only.get("actor_type"), only.get("actor_id")
    if (kind, number) == (ADMIN_ROLE, ADMIN_ROLE_ID):
        who = ADMIN
    elif kind == APP and isinstance(number, int):
        if app_id and str(number) != app_id:
            problems.append(
                f"the bypass actor is the app {number}, but PREPUSH_CI_APP_ID names the app {app_id}"
            )
        else:
            who = f"the app {number}"
    else:
        problems.append(
            f"the bypass actor {_name(only)} is neither the repository-admin role nor an app"
        )
    mode = only.get("bypass_mode") or ALWAYS
    if mode != ALWAYS:
        problems.append(f"its bypass mode is `{mode}`, not `{ALWAYS}`")
    return problems, "" if problems else who


def audit(text: str, app_id: str | None) -> Audit:
    """Whether the ruleset in `text` (GitHub's answer for one ruleset) is the landing ruleset with
    one bypass actor that can push; `app_id` is the app `PREPUSH_CI_APP_ID` names, if any."""
    found = load_object(text)
    if "bypass_actors" not in found:
        raise ActorsHidden("the answer has no bypass_actors")
    actor_problems, actor = _actors(found, app_id)
    problems = (*_where(found), *_rules(found), *actor_problems)
    return Audit(problems, actor, page_address(found))
