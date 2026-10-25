import json
from typing import Any

import pytest

from prepush_ci.core.report import Malformed, ReportError
from prepush_ci.core.ruleset import (
    ADMIN,
    ADMIN_ACTOR,
    NAME,
    Actor,
    app_actor,
    body,
    created,
    describe,
    listed_id,
    parse_app_id,
)

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


# --- The request -------------------------------------------------------------------------------


def test_the_body_names_the_ruleset_activates_it_and_targets_the_default_branch() -> (
    None
):
    made = body(Actor(5, "RepositoryRole"))

    assert made["name"] == "prepush-ci landing"
    assert made["target"] == "branch"
    assert made["enforcement"] == "active"
    assert made["conditions"] == {
        "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
    }


def test_the_body_has_exactly_the_three_rules_and_none_has_parameters() -> None:
    rules = body(Actor(5, "RepositoryRole"))["rules"]

    assert rules == [
        {"type": "update"},
        {"type": "non_fast_forward"},
        {"type": "deletion"},
    ]


def test_the_body_of_the_admin_role_has_one_bypass_actor_that_can_always_bypass() -> (
    None
):
    made = body(Actor(5, "RepositoryRole"))

    assert made["bypass_actors"] == [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
    ]


def test_the_body_of_an_app_has_the_integration_as_its_only_bypass_actor() -> None:
    made = body(app_actor(5401187))

    assert made["bypass_actors"] == [
        {"actor_id": 5401187, "actor_type": "Integration", "bypass_mode": "always"}
    ]


def test_the_admin_role_and_an_app_are_described_for_a_person() -> None:
    assert describe(ADMIN_ACTOR) == ADMIN == "the repository-admin role"
    assert describe(app_actor(5401187)) == "the app 5401187"


def test_an_app_id_is_a_whole_number_of_one_or_more() -> None:
    assert parse_app_id("5401187") == 5401187
    assert parse_app_id("1") == 1


@pytest.mark.parametrize("text", ["0", "slug", "", "-3", "1.5", "²", "4 2"])
def test_an_app_id_that_is_not_a_whole_number_of_one_or_more_is_malformed(
    text: str,
) -> None:
    with pytest.raises(Malformed):
        parse_app_id(text)


# --- The listing and the answer ------------------------------------------------------------------


def test_the_listing_gives_the_id_of_the_ruleset_with_the_landing_name() -> None:
    listing = json.dumps([{"id": 7, "name": "main"}, {"id": 8, "name": NAME}])

    assert listed_id(listing) == "8"


def test_a_listing_without_the_landing_ruleset_gives_none() -> None:
    assert listed_id(json.dumps([{"id": 7, "name": "main"}])) is None
    assert listed_id("[]") is None


@pytest.mark.parametrize(
    "text",
    ["not json", "{}", '["x"]', '[{"name": "prepush-ci landing"}]'],
)
def test_a_listing_that_is_not_what_the_api_documents_is_refused(text: str) -> None:
    with pytest.raises(ReportError):
        listed_id(text)


def test_the_created_ruleset_gives_its_id_and_the_address_of_its_page() -> None:
    made = created(json.dumps(LANDING))

    assert made.ruleset_id == "24893178"
    assert made.address == "https://github.com/acme/widgets/rules/24893178"


def test_an_answer_without_a_page_link_gives_no_address() -> None:
    assert created('{"id": 3}').address is None
    assert created('{"id": 3, "_links": {}}').address is None


@pytest.mark.parametrize(
    "text", ["not json", "[]", "{}", '{"id": true}', '{"id": "x"}']
)
def test_an_answer_without_a_numeric_id_is_refused(text: str) -> None:
    with pytest.raises(ReportError):
        created(text)
