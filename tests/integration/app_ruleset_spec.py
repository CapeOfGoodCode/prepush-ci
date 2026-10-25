"""`prepush-ci app ruleset` in real temporary git repositories, started as the module, against a
local double of GitHub's rulesets API."""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

# Variables the developer's or Actions' own environment may set and a spec must decide itself.
CLEARED = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_REPOSITORY",
    "GITHUB_API_URL",
    "GITHUB_SERVER_URL",
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
TOKEN = "t0k-0123456789"
RULESETS = "/repos/acme/widgets/rulesets"
LANDING = "prepush-ci landing"
APP_ID = "5401187"
THREE_RULES = [{"type": "update"}, {"type": "non_fast_forward"}, {"type": "deletion"}]


@pytest.fixture
def work(repo: Path, git: Git) -> Path:
    """`repo` with `origin` on github.com, which is never contacted."""
    git(repo, "remote", "add", "origin", ORIGIN)
    return repo


def ruleset(
    repo: Path,
    api: Any,
    *args: str,
    env: dict[str, str | None] | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci app ruleset` in `repo` against the API double, with a token unless `env`
    says otherwise (a `None` removes the variable)."""
    merged: dict[str, str | None] = {
        "GITHUB_API_URL": api.url,
        "GITHUB_TOKEN": TOKEN,
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    merged.update(env or {})
    inherited = {k: v for k, v in os.environ.items() if k not in CLEARED}
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "app", "ruleset", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**inherited, **{k: v for k, v in merged.items() if v is not None}},
        timeout=60,
    )


def posted(api: Any) -> dict[str, Any]:
    """The body of the one `POST` the API received."""
    assert len(api.posts()) == 1, api.requests
    body = json.loads(api.posts()[0].body)
    assert isinstance(body, dict)
    return body


# --- One bypass actor ---------------------------------------------------------------------------


def test_without_a_flag_it_exits_2_names_both_flags_and_sends_no_request(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api)

    assert result.returncode == 2
    assert "--admin" in result.stderr
    assert "--app" in result.stderr
    assert ruleset_api.requests == []


def test_with_both_flags_it_exits_2_and_sends_no_request(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--admin", "--app", APP_ID)

    assert result.returncode == 2
    assert ruleset_api.requests == []


@pytest.mark.parametrize("given", ["0", "slug"])
def test_a_malformed_app_id_exits_2_names_the_flag_and_sends_no_request(
    work: Path, ruleset_api: Any, given: str
) -> None:
    result = ruleset(work, ruleset_api, "--app", given)

    assert result.returncode == 2
    assert "--app" in result.stderr
    assert ruleset_api.requests == []


def test_the_help_lists_both_flags_and_mentions_a_paid_plan_for_a_private_repository(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--help")

    assert result.returncode == 0
    assert "--admin" in result.stdout
    assert "--app" in result.stdout
    assert "paid plan" in " ".join(result.stdout.split())
    assert "private repository" in " ".join(result.stdout.split())
    assert ruleset_api.requests == []


def test_an_unknown_flag_exits_2_names_the_flag_and_sends_no_request(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--frob")

    assert result.returncode == 2
    assert "--frob" in result.stderr
    assert ruleset_api.requests == []


# --- The token and the repository ---------------------------------------------------------------


def test_the_token_of_the_environment_is_sent_as_a_bearer_token_for_the_repository_of_origin(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--admin", env={"GITHUB_TOKEN": "t0k"})

    assert result.returncode == 0
    assert ruleset_api.requests
    for request in ruleset_api.requests:
        assert request.path.split("?")[0] == RULESETS
        assert request.headers["authorization"] == "Bearer t0k"


def test_gh_token_is_the_token_when_github_token_is_unset(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(
        work,
        ruleset_api,
        "--admin",
        env={"GITHUB_TOKEN": None, "GH_TOKEN": "t0k"},
    )

    assert result.returncode == 0
    assert {r.headers["authorization"] for r in ruleset_api.requests} == {"Bearer t0k"}


def test_gh_token_is_the_token_when_github_token_is_empty(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(
        work, ruleset_api, "--admin", env={"GITHUB_TOKEN": "", "GH_TOKEN": "t0k"}
    )

    assert result.returncode == 0
    assert {r.headers["authorization"] for r in ruleset_api.requests} == {"Bearer t0k"}


def test_without_a_token_it_exits_1_names_both_variables_and_sends_no_request(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--admin", env={"GITHUB_TOKEN": None})

    assert result.returncode == 1
    assert "GITHUB_TOKEN" in result.stderr
    assert "GH_TOKEN" in result.stderr
    assert ruleset_api.requests == []


def test_without_a_repository_it_exits_1_and_sends_no_request(
    repo: Path, ruleset_api: Any
) -> None:
    result = ruleset(repo, ruleset_api, "--admin")

    assert result.returncode == 1
    assert "origin" in result.stderr
    assert ruleset_api.requests == []


def test_the_repository_comes_from_the_environment_when_origin_names_none(
    repo: Path, git: Git, ruleset_api: Any
) -> None:
    git(repo, "remote", "add", "origin", str(repo.parent / "elsewhere.git"))

    result = ruleset(
        repo, ruleset_api, "--admin", env={"GITHUB_REPOSITORY": "acme/widgets"}
    )

    assert result.returncode == 0
    assert {r.path.split("?")[0] for r in ruleset_api.requests} == {RULESETS}


def test_origin_wins_over_the_repository_of_the_environment(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(
        work, ruleset_api, "--admin", env={"GITHUB_REPOSITORY": "other/thing"}
    )

    assert result.returncode == 0
    assert {r.path.split("?")[0] for r in ruleset_api.requests} == {RULESETS}


# --- The ruleset and its bypass actor -------------------------------------------------------------


def test_the_request_names_the_landing_ruleset_with_three_rules_and_no_pull_request_rule(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 0
    body = posted(ruleset_api)
    assert body["name"] == LANDING
    assert body["target"] == "branch"
    assert body["enforcement"] == "active"
    assert body["conditions"] == {
        "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
    }
    assert body["rules"] == THREE_RULES
    types = {rule["type"] for rule in body["rules"]}
    assert not types & {"pull_request", "required_status_checks", "creation"}


def test_the_admin_role_is_the_only_bypass_actor_with_admin(
    work: Path, ruleset_api: Any
) -> None:
    ruleset(work, ruleset_api, "--admin")

    body = posted(ruleset_api)
    assert body["bypass_actors"] == [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
    ]
    assert ruleset_api.posts()[0].path == RULESETS


def test_the_app_is_the_only_bypass_actor_with_app(
    work: Path, ruleset_api: Any
) -> None:
    ruleset(work, ruleset_api, "--app", APP_ID)

    body = posted(ruleset_api)
    assert body["bypass_actors"] == [
        {"actor_id": int(APP_ID), "actor_type": "Integration", "bypass_mode": "always"}
    ]
    assert body["rules"] == THREE_RULES


def test_the_listing_is_read_before_the_ruleset_is_created(
    work: Path, ruleset_api: Any
) -> None:
    ruleset(work, ruleset_api, "--admin")

    assert [r.method for r in ruleset_api.requests] == ["GET", "POST"]


# --- A ruleset that exists is kept ------------------------------------------------------------------


def test_an_existing_landing_ruleset_exits_1_and_nothing_is_created_or_changed(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.listing = [{"id": 7, "name": LANDING}]

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 1
    assert ruleset_api.changes() == []
    assert LANDING in result.stderr
    assert "delete" in result.stderr
    assert "settings" in result.stderr


def test_a_ruleset_with_another_name_is_no_obstacle(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.listing = [{"id": 7, "name": "main"}]

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 0
    assert posted(ruleset_api)["name"] == LANDING


# --- What the command prints -------------------------------------------------------------------------


def test_the_id_the_page_the_actor_and_the_doctor_command_are_printed(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 0
    assert "(id 24893178)" in result.stdout
    assert f"{ruleset_api.url}/acme/widgets/rules/24893178" in result.stdout
    assert "admin" in result.stdout
    assert "doctor --ruleset" in result.stdout


def test_an_answer_that_names_no_page_still_prints_the_id_and_no_page_line(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.answer("POST", 201, json.dumps({"id": 24893178, "name": "landing"}))

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 0
    assert "(id 24893178)" in result.stdout
    assert "its page:" not in result.stdout
    assert "doctor --ruleset" in result.stdout


def test_the_app_is_named_when_it_is_the_bypass_actor(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--app", APP_ID)

    assert APP_ID in result.stdout


def test_the_token_stays_out_of_the_output_of_a_success(
    work: Path, ruleset_api: Any
) -> None:
    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 0
    assert TOKEN not in result.stdout + result.stderr


def test_the_token_stays_out_of_the_output_of_a_failure_that_quotes_it(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.answer("POST", 422, json.dumps({"message": f"bad token {TOKEN}"}))

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 1
    assert "422" in result.stderr
    assert TOKEN not in result.stdout + result.stderr


def test_an_answer_that_is_not_what_the_api_documents_exits_1_and_says_to_look(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.answer("POST", 201, "not json")

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 1
    assert "check the settings" in result.stderr


# --- GitHub's refusal is reported ----------------------------------------------------------------------


def test_a_403_exits_1_with_the_status_the_message_a_paid_plan_and_administration_rights(
    work: Path, ruleset_api: Any
) -> None:
    message = (
        "Upgrade to GitHub Pro or make this repository public to enable this feature."
    )
    ruleset_api.answer("POST", 403, json.dumps({"message": message}))

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 1
    assert "403" in result.stderr
    assert message in result.stderr
    assert "paid plan" in result.stderr
    assert "administration" in result.stderr


def test_a_403_of_the_listing_says_the_same(work: Path, ruleset_api: Any) -> None:
    ruleset_api.answer("GET", 403, json.dumps({"message": "Forbidden"}))

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 1
    assert "paid plan" in result.stderr
    assert ruleset_api.posts() == []


def test_a_404_of_the_listing_exits_1_with_the_status_and_posts_nothing(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.answer("GET", 404, json.dumps({"message": "Not Found"}))

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 1
    assert "404" in result.stderr
    assert ruleset_api.posts() == []
    assert "paid plan" not in result.stderr


def test_a_refusal_is_not_retried(work: Path, ruleset_api: Any) -> None:
    ruleset_api.answer("POST", 403, json.dumps({"message": "no"}))

    ruleset(work, ruleset_api, "--admin")

    assert len(ruleset_api.posts()) == 1


def test_an_api_that_cannot_be_reached_exits_1(work: Path, ruleset_api: Any) -> None:
    result = ruleset(
        work, ruleset_api, "--admin", env={"GITHUB_API_URL": "http://127.0.0.1:1"}
    )

    assert result.returncode == 1
    assert "could not be sent" in result.stderr


def test_a_listing_that_is_not_what_the_api_documents_exits_1_and_posts_nothing(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.answer("GET", 200, "not json")

    result = ruleset(work, ruleset_api, "--admin")

    assert result.returncode == 1
    assert ruleset_api.posts() == []


# --- The exit status -----------------------------------------------------------------------------------


def test_it_exits_0_when_the_ruleset_was_created(work: Path, ruleset_api: Any) -> None:
    assert ruleset(work, ruleset_api, "--admin").returncode == 0
