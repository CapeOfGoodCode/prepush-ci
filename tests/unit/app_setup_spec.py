import html as html_module
import json
import re

import pytest

from prepush_ci.core.app_setup import (
    HOMEPAGE,
    App,
    callback_code,
    default_name,
    install_address,
    manifest,
    new_state,
    page,
    parse_app,
    parse_app_name,
    parse_timeout,
    result_text,
)
from prepush_ci.core.report import Malformed, ReportError

REDIRECT = "http://127.0.0.1:5000/callback"


def test_the_manifest_asks_for_checks_write_and_nothing_else() -> None:
    assert manifest("n", REDIRECT)["default_permissions"] == {"checks": "write"}


def test_the_manifest_of_a_landing_app_asks_for_four_permissions_and_is_not_public() -> (
    None
):
    made = manifest("n", REDIRECT, land=True)

    assert made["default_permissions"] == {
        "checks": "write",
        "contents": "write",
        "pull_requests": "read",
        "workflows": "write",
    }
    assert made["public"] is False


def test_the_manifest_names_the_homepage_and_the_redirect() -> None:
    made = manifest("Acme checks", REDIRECT)

    assert made["url"] == HOMEPAGE == "https://github.com/CapeOfGoodCode/prepush-ci"
    assert made["redirect_url"] == REDIRECT
    assert made["name"] == "Acme checks"


def test_the_manifest_has_no_webhook_no_events_and_is_not_public() -> None:
    made = manifest("n", REDIRECT)

    assert "hook_attributes" not in made
    assert made["default_events"] == []
    assert made["public"] is False


def test_the_default_name_is_the_tool_and_the_owner() -> None:
    assert default_name("acme") == "prepush-ci (acme)"


def test_a_default_name_of_34_characters_is_kept() -> None:
    owner = "a" * (34 - len("prepush-ci ()"))

    assert len(default_name(owner)) == 34


def test_a_default_name_of_35_characters_is_refused_naming_the_flag() -> None:
    owner = "a" * (35 - len("prepush-ci ()"))

    with pytest.raises(ReportError, match="--name"):
        default_name(owner)


def test_a_name_of_34_characters_is_a_name() -> None:
    assert parse_app_name("n" * 34) == "n" * 34


def test_a_name_of_35_characters_is_malformed() -> None:
    with pytest.raises(Malformed, match="34"):
        parse_app_name("n" * 35)


def test_an_empty_name_is_malformed() -> None:
    with pytest.raises(Malformed, match="empty"):
        parse_app_name("")


@pytest.mark.parametrize("text", ["0", "soon", "-1", "1.5", "", "٣"])
def test_a_timeout_that_is_not_a_whole_number_of_1_or_more_is_malformed(
    text: str,
) -> None:
    with pytest.raises(Malformed, match="1 or more"):
        parse_timeout(text)


def test_a_timeout_is_a_whole_number_of_seconds() -> None:
    assert parse_timeout("1") == 1
    assert parse_timeout("300") == 300


def test_the_page_posts_the_manifest_as_a_json_field_to_the_action() -> None:
    html = page("https://github.com/settings/apps/new?state=s", {"name": "n"})

    assert 'method="post"' in html
    assert 'action="https://github.com/settings/apps/new?state=s"' in html
    assert 'name="manifest"' in html


def test_the_page_escapes_the_manifest_so_special_characters_reach_github_unchanged() -> (
    None
):
    shown = page("https://x/y", {"name": 'A "b" <c> & d'})

    assert 'A "b" <c>' not in shown
    value = re.search(r'name="manifest" value="([^"]*)"', shown)
    assert value is not None
    assert json.loads(html_module.unescape(value.group(1))) == {"name": 'A "b" <c> & d'}


def test_a_callback_with_the_right_state_and_a_code_gives_the_code() -> None:
    assert callback_code({"state": ["s"], "code": ["c0de"]}, "s") == "c0de"


def test_a_callback_with_another_state_gives_nothing() -> None:
    assert callback_code({"state": ["other"], "code": ["c0de"]}, "s") is None


def test_a_callback_without_a_state_gives_nothing() -> None:
    assert callback_code({"code": ["c0de"]}, "s") is None


def test_a_callback_without_a_code_gives_nothing() -> None:
    assert callback_code({"state": ["s"]}, "s") is None


def test_a_callback_with_an_empty_code_gives_nothing() -> None:
    assert callback_code({"state": ["s"], "code": [""]}, "s") is None


def answer(**changes: object) -> str:
    base: dict[str, object] = {
        "id": 5401187,
        "slug": "prepush-ci-acme",
        "pem": "KEY",
        "client_secret": "cs",
        "webhook_secret": "ws",
    }
    return json.dumps({**base, **changes})


def test_an_answer_with_an_id_a_slug_and_a_key_is_an_app() -> None:
    assert parse_app(answer()) == App("5401187", "prepush-ci-acme", "KEY")


@pytest.mark.parametrize("missing", ["id", "slug", "pem"])
def test_an_answer_without_one_of_the_three_is_incomplete(missing: str) -> None:
    body = json.loads(answer())
    del body[missing]

    with pytest.raises(ReportError, match="incomplete"):
        parse_app(json.dumps(body))


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        "[]",
        "null",
        answer(id="../x"),
        answer(id=True),
        answer(id=""),
        answer(slug="a b"),
        answer(slug=""),
        answer(slug="../x"),
        answer(pem=""),
        answer(pem=7),
    ],
)
def test_an_answer_that_does_not_hold_a_usable_app_is_incomplete(body: str) -> None:
    with pytest.raises(ReportError, match="incomplete"):
        parse_app(body)


def test_an_id_given_as_text_of_digits_is_accepted() -> None:
    assert parse_app(answer(id="42")).app_id == "42"


def test_the_install_address_is_on_the_server() -> None:
    assert (
        install_address("https://github.com", "prepush-ci-acme")
        == "https://github.com/apps/prepush-ci-acme/installations/new"
    )


def test_the_result_names_the_id_the_address_the_path_and_the_two_variables() -> None:
    text = result_text(
        App("5401187", "prepush-ci-acme", "KEY"),
        "https://github.com",
        "/home/me/.config/prepush-ci/apps/5401187.pem",
    )

    assert "5401187" in text
    assert "https://github.com/apps/prepush-ci-acme/installations/new" in text
    assert "/home/me/.config/prepush-ci/apps/5401187.pem" in text
    assert "PREPUSH_CI_APP_ID" in text
    assert "PREPUSH_CI_APP_KEY" in text
    assert "KEY" not in text.replace("PREPUSH_CI_APP_KEY", "")


def test_the_result_of_a_landing_app_names_the_ruleset_command_with_its_id() -> None:
    text = result_text(
        App("5401187", "prepush-ci-acme", "KEY"), "https://github.com", "key.pem", True
    )

    assert "prepush-ci app ruleset --app 5401187" in text
    assert "installed" in text


def test_the_result_of_an_app_without_the_flag_holds_no_ruleset_command() -> None:
    text = result_text(
        App("5401187", "prepush-ci-acme", "KEY"), "https://github.com", "key.pem"
    )

    assert "app ruleset" not in text


def test_each_run_gets_its_own_state_that_is_safe_in_an_address() -> None:
    first, second = new_state(), new_state()

    assert first != second
    assert re.fullmatch(r"[A-Za-z0-9_-]{32,}", first)
