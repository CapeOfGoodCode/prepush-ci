import json
from typing import Any

import pytest

from prepush_ci.core.report import ReportError
from prepush_ci.core.ruleset import ADMIN, NAME
from prepush_ci.core.ruleset_audit import ActorsHidden, audit

LANDING: dict[str, Any] = {
    "id": 24893178,
    "name": NAME,
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [{"type": "update"}, {"type": "non_fast_forward"}, {"type": "deletion"}],
    "bypass_actors": [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
    ],
    "_links": {"html": {"href": "https://github.com/acme/widgets/rules/24893178"}},
}


def changed(**changes: Any) -> str:
    return json.dumps({**LANDING, **changes})


def problems_of(text: str, app_id: str | None = None) -> tuple[str, ...]:
    return audit(text, app_id).problems


def test_the_ruleset_the_command_creates_has_no_problem_and_names_the_admin_role() -> (
    None
):
    found = audit(changed(), None)

    assert found.problems == ()
    assert found.actor == ADMIN


def test_the_answer_of_the_command_with_an_app_names_the_app() -> None:
    actors = [
        {"actor_id": 5401187, "actor_type": "Integration", "bypass_mode": "always"}
    ]

    found = audit(changed(bypass_actors=actors), "5401187")

    assert found.problems == ()
    assert "5401187" in found.actor


def test_an_app_passes_with_the_variable_unset_or_empty() -> None:
    actors = [
        {"actor_id": 5401187, "actor_type": "Integration", "bypass_mode": "always"}
    ]

    assert problems_of(changed(bypass_actors=actors), None) == ()
    assert problems_of(changed(bypass_actors=actors), "") == ()


def test_the_page_link_of_the_ruleset_is_part_of_the_audit() -> None:
    assert (
        audit(changed(), None).address
        == "https://github.com/acme/widgets/rules/24893178"
    )
    assert audit(json.dumps({**LANDING, "_links": {}}), None).address is None


@pytest.mark.parametrize("enforcement", ["evaluate", "disabled"])
def test_a_ruleset_that_is_not_active_is_named_by_its_enforcement(
    enforcement: str,
) -> None:
    assert any(enforcement in p for p in problems_of(changed(enforcement=enforcement)))


def test_a_ruleset_that_targets_tags_is_named_by_its_target() -> None:
    assert any("tag" in p for p in problems_of(changed(target="tag")))


def test_a_ruleset_that_does_not_include_the_default_branch_names_it() -> None:
    conditions = {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}}

    found = problems_of(changed(conditions=conditions))

    assert any("~DEFAULT_BRANCH" in p and "refs/heads/dev" in p for p in found)


@pytest.mark.parametrize("ref", ["refs/heads/main", "~DEFAULT_BRANCH"])
def test_a_ruleset_that_excludes_a_branch_names_the_excluded_ref(ref: str) -> None:
    conditions = {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": [ref]}}

    assert any(ref in p for p in problems_of(changed(conditions=conditions)))


def test_a_ruleset_without_conditions_does_not_include_the_default_branch() -> None:
    text = json.dumps({k: v for k, v in LANDING.items() if k != "conditions"})

    assert any("~DEFAULT_BRANCH" in p for p in problems_of(text))


def test_a_rule_too_many_is_named() -> None:
    rules = [*LANDING["rules"], {"type": "pull_request"}]

    assert any("pull_request" in p for p in problems_of(changed(rules=rules)))


def test_a_rule_too_few_is_named() -> None:
    rules = LANDING["rules"][:2]

    assert any("deletion" in p for p in problems_of(changed(rules=rules)))


def test_a_rule_listed_twice_is_named() -> None:
    rules = [*LANDING["rules"], {"type": "update"}]

    assert any("update" in p for p in problems_of(changed(rules=rules)))


def test_the_rule_update_with_the_fetch_and_merge_parameter_set_is_named() -> None:
    rules = [
        {"type": "update", "parameters": {"update_allows_fetch_and_merge": True}},
        {"type": "non_fast_forward"},
        {"type": "deletion"},
    ]

    assert any("update" in p for p in problems_of(changed(rules=rules)))


@pytest.mark.parametrize(
    "parameters", [{"update_allows_fetch_and_merge": False}, {}, None]
)
def test_the_rule_update_with_a_parameter_that_changes_nothing_passes(
    parameters: Any,
) -> None:
    rules = [
        {"type": "update", "parameters": parameters},
        {"type": "non_fast_forward"},
        {"type": "deletion"},
    ]

    assert problems_of(changed(rules=rules)) == ()


def test_another_rule_with_parameters_is_named() -> None:
    rules = [
        {"type": "update"},
        {"type": "non_fast_forward", "parameters": {"x": 1}},
        {"type": "deletion"},
    ]

    assert any("non_fast_forward" in p for p in problems_of(changed(rules=rules)))


def test_the_rule_update_with_another_parameter_is_named() -> None:
    rules = [
        {"type": "update", "parameters": {"x": False}},
        {"type": "non_fast_forward"},
        {"type": "deletion"},
    ]

    assert any("update" in p for p in problems_of(changed(rules=rules)))


def test_a_ruleset_without_a_bypass_actor_is_named() -> None:
    assert any("no bypass actor" in p for p in problems_of(changed(bypass_actors=[])))


def test_two_bypass_actors_are_both_named() -> None:
    actors = [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
        {"actor_id": 77, "actor_type": "Team", "bypass_mode": "always"},
    ]

    found = problems_of(changed(bypass_actors=actors))

    assert any("Team" in p and "77" in p for p in found)


@pytest.mark.parametrize(
    "actor",
    [
        {"actor_id": 77, "actor_type": "Team", "bypass_mode": "always"},
        {"actor_id": 1, "actor_type": "RepositoryRole", "bypass_mode": "always"},
        {"actor_id": None, "actor_type": "OrganizationAdmin", "bypass_mode": "always"},
        {"actor_id": None, "actor_type": "Integration", "bypass_mode": "always"},
    ],
)
def test_one_bypass_actor_that_is_neither_the_admin_role_nor_an_app_is_named(
    actor: dict[str, Any],
) -> None:
    found = problems_of(changed(bypass_actors=[actor]))

    assert any(str(actor["actor_type"]) in p for p in found)


def test_an_app_other_than_the_one_the_variable_names_is_named_with_both() -> None:
    actors = [{"actor_id": 99, "actor_type": "Integration", "bypass_mode": "always"}]

    found = problems_of(changed(bypass_actors=actors), "5401187")

    assert any("99" in p and "5401187" in p for p in found)


def test_the_admin_role_passes_whatever_the_variable_names() -> None:
    assert problems_of(changed(), "5401187") == ()


def test_an_actor_without_a_bypass_mode_counts_as_always() -> None:
    actors = [{"actor_id": 5, "actor_type": "RepositoryRole"}]

    assert problems_of(changed(bypass_actors=actors)) == ()


@pytest.mark.parametrize("mode", ["pull_request", "exempt"])
def test_an_actor_whose_mode_is_not_always_is_named_with_always(mode: str) -> None:
    actors = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": mode}]

    found = problems_of(changed(bypass_actors=actors))

    assert any(mode in p and "always" in p for p in found)


def test_every_problem_is_reported_not_only_the_first() -> None:
    found = problems_of(changed(enforcement="disabled", target="tag", rules=[]))

    assert len(found) >= 3


def test_an_answer_without_the_bypass_actors_field_is_the_token_of_a_non_administrator() -> (
    None
):
    text = json.dumps({k: v for k, v in LANDING.items() if k != "bypass_actors"})

    with pytest.raises(ActorsHidden):
        audit(text, None)


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"bypass_actors": 3}',
        '{"bypass_actors": [3]}',
        '{"bypass_actors": [], "rules": 3}',
        '{"bypass_actors": [], "rules": [3]}',
        '{"bypass_actors": [], "conditions": 3}',
        '{"bypass_actors": [], "conditions": {"ref_name": 3}}',
        '{"bypass_actors": [], "conditions": {"ref_name": {"include": 3}}}',
        '{"bypass_actors": [], "rules": [{"type": "update", "parameters": 3}]}',
    ],
)
def test_an_answer_that_is_not_what_the_api_documents_is_refused(text: str) -> None:
    with pytest.raises(ReportError):
        audit(text, None)
