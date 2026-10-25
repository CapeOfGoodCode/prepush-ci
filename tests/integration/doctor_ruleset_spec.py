"""`prepush-ci doctor --ruleset` in real temporary git repositories, started as the module, against
a local double of GitHub's rulesets API."""

import copy
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

DEEP = pytest.param("[" * 100_000, id="nested-too-deep")

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
LANDING = "prepush-ci landing"
RULESETS = "/repos/acme/widgets/rulesets"
RULESET_ID = 24893178
APP_ID = "5401187"
ADMIN_ACTOR = {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
APP_ACTOR = {
    "actor_id": int(APP_ID),
    "actor_type": "Integration",
    "bypass_mode": "always",
}
CHECKS = ("config", "commit-msg", "pre-push", "preflight", "PREPUSH_CI", "up-to-date")


def landing(api: Any, **changes: Any) -> dict[str, Any]:
    """The ruleset `app ruleset --admin` creates, as GitHub answers for an administrator."""
    made: dict[str, Any] = {
        "id": RULESET_ID,
        "name": LANDING,
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "update"},
            {"type": "non_fast_forward"},
            {"type": "deletion"},
        ],
        "bypass_actors": [copy.deepcopy(ADMIN_ACTOR)],
        "_links": {"html": {"href": page(api)}},
    }
    return {**made, **changes}


def page(api: Any) -> str:
    return f"{api.url}/acme/widgets/rules/{RULESET_ID}"


@pytest.fixture
def work(repo: Path, git: Git, ruleset_api: Any) -> Path:
    """`repo` with `origin` on github.com, which is never contacted, and the API double holding
    the landing ruleset."""
    git(repo, "remote", "add", "origin", ORIGIN)
    ruleset_api.listing = [{"id": RULESET_ID, "name": LANDING}]
    ruleset_api.ruleset = landing(ruleset_api)
    return repo


def doctor(
    repo: Path,
    api: Any,
    *args: str,
    env: dict[str, str | None] | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci doctor` in `repo` against the API double, with a token unless `env` says
    otherwise (a `None` removes the variable)."""
    merged: dict[str, str | None] = {
        "GITHUB_API_URL": api.url,
        "GITHUB_TOKEN": "t0k",
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    merged.update(env or {})
    inherited = {k: v for k, v in os.environ.items() if k not in CLEARED}
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "doctor", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**inherited, **{k: v for k, v in merged.items() if v is not None}},
        timeout=120,
    )


def check_lines(result: "subprocess.CompletedProcess[str]") -> list[str]:
    return [
        text
        for text in result.stdout.splitlines()
        if text.startswith(("ok ", "fail ", "skip "))
    ]


def ruleset_line(result: "subprocess.CompletedProcess[str]") -> str:
    """The `ruleset` line with the indented lines after it (its fix)."""
    lines = result.stdout.splitlines()
    prefixes = ("ok ruleset:", "fail ruleset:", "skip ruleset:")
    start = next(i for i, text in enumerate(lines) if text.startswith(prefixes))
    block = [lines[start]]
    for text in lines[start + 1 :]:
        if not text.startswith(" "):
            break
        block.append(text)
    return "\n".join(block)


def verdict(
    work: Path,
    api: Any,
    ruleset: dict[str, Any],
    env: dict[str, str | None] | None = None,
) -> str:
    api.ruleset = ruleset
    return ruleset_line(doctor(work, api, "--ruleset", env=env))


# --- The report ---------------------------------------------------------------------------------


def test_with_the_flag_the_output_holds_seven_check_lines_the_seventh_is_ruleset(
    work: Path, ruleset_api: Any
) -> None:
    lines = check_lines(doctor(work, ruleset_api, "--ruleset"))

    assert len(lines) == 7
    assert [text.split(":")[0].split(" ", 1)[1] for text in lines] == [
        *CHECKS,
        "ruleset",
    ]


def test_without_the_flag_the_output_holds_six_check_lines(
    work: Path, ruleset_api: Any
) -> None:
    lines = check_lines(doctor(work, ruleset_api))

    assert len(lines) == 6
    assert not any(" ruleset:" in text for text in lines)


def test_the_closing_line_counts_the_ruleset_check_of_seven(
    work: Path, ruleset_api: Any
) -> None:
    result = doctor(work, ruleset_api, "--ruleset")

    failed = sum(not text.startswith("ok ") for text in check_lines(result))
    assert result.stdout.splitlines()[-1] == f"{failed} of 7 checks did not pass"
    assert result.returncode == 1


def test_a_ruleset_that_passes_does_not_fail_the_run_on_its_own(
    work: Path, ruleset_api: Any
) -> None:
    result = doctor(work, ruleset_api, "--ruleset")

    assert ruleset_line(result).startswith("ok ruleset:")


def test_a_failed_ruleset_check_does_not_stop_the_others_and_exits_1(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.listing = []

    result = doctor(work, ruleset_api, "--ruleset")

    assert len(check_lines(result)) == 7
    assert result.returncode == 1


# --- The ruleset check reads the ruleset ------------------------------------------------------------


def test_a_missing_ruleset_fails_and_the_fix_is_the_ruleset_command(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.listing = [{"id": 7, "name": "main"}]

    line = ruleset_line(doctor(work, ruleset_api, "--ruleset"))

    assert line.startswith("fail ruleset:")
    assert "missing" in line
    assert "prepush-ci app ruleset" in line


def test_a_token_that_cannot_see_the_bypass_actors_fails_and_asks_for_administration_rights(
    work: Path, ruleset_api: Any
) -> None:
    hidden = landing(ruleset_api)
    del hidden["bypass_actors"]

    line = verdict(work, ruleset_api, hidden)

    assert line.startswith("fail ruleset:")
    assert "administration rights" in line
    assert "bypass actors" in line


def test_without_a_token_the_check_fails_naming_the_variable_and_sends_no_request(
    work: Path, ruleset_api: Any
) -> None:
    result = doctor(
        work, ruleset_api, "--ruleset", env={"GITHUB_TOKEN": None, "GH_TOKEN": None}
    )

    assert ruleset_line(result).startswith("fail ruleset:")
    assert "GITHUB_TOKEN" in ruleset_line(result)
    assert ruleset_api.requests == []


def test_gh_token_is_a_token_too(work: Path, ruleset_api: Any) -> None:
    result = doctor(
        work,
        ruleset_api,
        "--ruleset",
        env={"GITHUB_TOKEN": None, "GH_TOKEN": "gh-t0k"},
    )

    assert ruleset_line(result).startswith("ok ruleset:")
    assert {r.headers["authorization"] for r in ruleset_api.requests} == {
        "Bearer gh-t0k"
    }


def test_without_a_repository_the_check_fails_and_sends_no_request(
    repo: Path, ruleset_api: Any
) -> None:
    result = doctor(repo, ruleset_api, "--ruleset")

    assert ruleset_line(result).startswith("fail ruleset:")
    assert "no repository could be read from `origin`" in ruleset_line(result)
    assert ruleset_api.requests == []


def test_the_repository_comes_from_the_environment_when_origin_names_none(
    repo: Path, git: Git, ruleset_api: Any
) -> None:
    git(repo, "remote", "add", "origin", str(repo.parent / "elsewhere.git"))
    ruleset_api.listing = [{"id": RULESET_ID, "name": LANDING}]
    ruleset_api.ruleset = landing(ruleset_api)

    doctor(repo, ruleset_api, "--ruleset", env={"GITHUB_REPOSITORY": "acme/widgets"})

    assert ruleset_api.requests[0].path.split("?")[0] == RULESETS


@pytest.mark.parametrize("status", [403, 404])
def test_a_listing_that_github_refuses_fails_with_the_status(
    work: Path, ruleset_api: Any, status: int
) -> None:
    ruleset_api.answer("GET", status, json.dumps({"message": "refused"}))

    line = ruleset_line(doctor(work, ruleset_api, "--ruleset"))

    assert line.startswith("fail ruleset:")
    assert str(status) in line


def test_a_ruleset_that_github_does_not_answer_for_fails_with_the_status(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.ruleset = None

    line = ruleset_line(doctor(work, ruleset_api, "--ruleset"))

    assert line.startswith("fail ruleset:")
    assert "404" in line


def test_a_refusal_whose_body_is_nested_too_deep_still_fails_with_the_status(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.answer("GET", 500, "[" * 100_000)

    line = ruleset_line(doctor(work, ruleset_api, "--ruleset"))

    assert line.startswith("fail ruleset:") and "500" in line


def test_the_token_stays_out_of_a_failure_that_quotes_it(
    work: Path, ruleset_api: Any
) -> None:
    ruleset_api.answer("GET", 403, json.dumps({"message": "bad token t0k"}))

    result = doctor(work, ruleset_api, "--ruleset")

    assert ruleset_line(result).startswith("fail ruleset:")
    assert "403" in result.stdout
    assert "t0k" not in result.stdout + result.stderr


@pytest.mark.parametrize("answer", ["not json", DEEP])
def test_an_answer_that_is_not_what_the_api_documents_fails(
    work: Path, ruleset_api: Any, answer: str
) -> None:
    ruleset_api.answer("GET", 200, answer)

    assert ruleset_line(doctor(work, ruleset_api, "--ruleset")).startswith(
        "fail ruleset:"
    )


def test_the_check_sends_the_listing_then_the_ruleset_and_nothing_else(
    work: Path, ruleset_api: Any
) -> None:
    doctor(work, ruleset_api, "--ruleset")

    assert [(r.method, r.path.split("?")[0]) for r in ruleset_api.requests] == [
        ("GET", RULESETS),
        ("GET", f"{RULESETS}/{RULESET_ID}"),
    ]
    assert {r.headers["authorization"] for r in ruleset_api.requests} == {"Bearer t0k"}


def snapshot(repo: Path) -> dict[str, bytes]:
    return {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git/index" not in path.as_posix()
    }


def test_the_check_changes_no_file_of_the_repository_and_sends_only_get_requests(
    work: Path, ruleset_api: Any
) -> None:
    before = snapshot(work)

    doctor(work, ruleset_api, "--ruleset")

    assert snapshot(work) == before
    assert ruleset_api.changes() == []


# --- The ruleset check passes only for the landing ruleset ---------------------------------------------


@pytest.mark.parametrize("enforcement", ["evaluate", "disabled"])
def test_a_ruleset_that_is_not_active_fails_naming_the_enforcement(
    work: Path, ruleset_api: Any, enforcement: str
) -> None:
    line = verdict(work, ruleset_api, landing(ruleset_api, enforcement=enforcement))

    assert line.startswith("fail ruleset:")
    assert enforcement in line


def test_a_ruleset_for_tags_fails_naming_the_target(
    work: Path, ruleset_api: Any
) -> None:
    line = verdict(work, ruleset_api, landing(ruleset_api, target="tag"))

    assert line.startswith("fail ruleset:")
    assert "tag" in line


def test_a_ruleset_that_does_not_include_the_default_branch_fails_naming_it(
    work: Path, ruleset_api: Any
) -> None:
    conditions = {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}}

    line = verdict(work, ruleset_api, landing(ruleset_api, conditions=conditions))

    assert line.startswith("fail ruleset:")
    assert "~DEFAULT_BRANCH" in line


@pytest.mark.parametrize("ref", ["refs/heads/main", "~DEFAULT_BRANCH"])
def test_a_ruleset_that_excludes_a_branch_fails_naming_the_excluded_ref(
    work: Path, ruleset_api: Any, ref: str
) -> None:
    conditions = {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": [ref]}}

    line = verdict(work, ruleset_api, landing(ruleset_api, conditions=conditions))

    assert line.startswith("fail ruleset:")
    assert ref in line


def test_a_pull_request_rule_too_many_fails_naming_the_rule(
    work: Path, ruleset_api: Any
) -> None:
    rules = [
        {"type": "update"},
        {"type": "non_fast_forward"},
        {"type": "deletion"},
        {"type": "pull_request"},
    ]

    line = verdict(work, ruleset_api, landing(ruleset_api, rules=rules))

    assert line.startswith("fail ruleset:")
    assert "pull_request" in line


def test_a_rule_too_few_fails_naming_the_rule(work: Path, ruleset_api: Any) -> None:
    rules = [{"type": "update"}, {"type": "non_fast_forward"}]

    line = verdict(work, ruleset_api, landing(ruleset_api, rules=rules))

    assert line.startswith("fail ruleset:")
    assert "deletion" in line


def test_the_rule_update_with_the_fetch_and_merge_parameter_set_fails_naming_update(
    work: Path, ruleset_api: Any
) -> None:
    rules = [
        {"type": "update", "parameters": {"update_allows_fetch_and_merge": True}},
        {"type": "non_fast_forward"},
        {"type": "deletion"},
    ]

    line = verdict(work, ruleset_api, landing(ruleset_api, rules=rules))

    assert line.startswith("fail ruleset:")
    assert "update" in line


def test_a_parameter_that_changes_nothing_passes(work: Path, ruleset_api: Any) -> None:
    rules = [
        {"type": "update", "parameters": {"update_allows_fetch_and_merge": False}},
        {"type": "non_fast_forward"},
        {"type": "deletion"},
    ]

    line = verdict(work, ruleset_api, landing(ruleset_api, rules=rules))

    assert line.startswith("ok ruleset:")


def test_a_failure_names_the_address_of_the_ruleset_in_its_fix(
    work: Path, ruleset_api: Any
) -> None:
    line = verdict(work, ruleset_api, landing(ruleset_api, enforcement="disabled"))

    assert "fix:" in line
    assert page(ruleset_api) in line


def test_a_failure_of_a_ruleset_without_a_page_link_still_has_a_fix(
    work: Path, ruleset_api: Any
) -> None:
    line = verdict(
        work, ruleset_api, landing(ruleset_api, enforcement="disabled", _links={})
    )

    assert line.startswith("fail ruleset:")
    assert "fix:" in line
    assert "settings" in line


# --- The ruleset check passes only for one bypass actor that can push -------------------------------------


def test_the_admin_role_passes_and_is_named(work: Path, ruleset_api: Any) -> None:
    line = verdict(work, ruleset_api, landing(ruleset_api))

    assert line.startswith("ok ruleset:")
    assert "admin" in line


def test_the_app_the_variable_names_passes_and_is_named(
    work: Path, ruleset_api: Any
) -> None:
    actors = [copy.deepcopy(APP_ACTOR)]

    line = verdict(
        work,
        ruleset_api,
        landing(ruleset_api, bypass_actors=actors),
        env={"PREPUSH_CI_APP_ID": APP_ID},
    )

    assert line.startswith("ok ruleset:")
    assert APP_ID in line


def test_an_app_passes_when_the_variable_is_unset(work: Path, ruleset_api: Any) -> None:
    actors = [copy.deepcopy(APP_ACTOR)]

    line = verdict(work, ruleset_api, landing(ruleset_api, bypass_actors=actors))

    assert line.startswith("ok ruleset:")
    assert APP_ID in line


def test_an_app_passes_when_the_variable_is_empty(work: Path, ruleset_api: Any) -> None:
    actors = [copy.deepcopy(APP_ACTOR)]

    line = verdict(
        work,
        ruleset_api,
        landing(ruleset_api, bypass_actors=actors),
        env={"PREPUSH_CI_APP_ID": ""},
    )

    assert line.startswith("ok ruleset:")


def test_another_app_than_the_variable_names_fails_naming_both(
    work: Path, ruleset_api: Any
) -> None:
    actors = [{**APP_ACTOR, "actor_id": 99}]

    line = verdict(
        work,
        ruleset_api,
        landing(ruleset_api, bypass_actors=actors),
        env={"PREPUSH_CI_APP_ID": APP_ID},
    )

    assert line.startswith("fail ruleset:")
    assert "99" in line
    assert APP_ID in line


def test_the_admin_role_and_a_team_fail_naming_the_team_and_the_address(
    work: Path, ruleset_api: Any
) -> None:
    actors = [
        copy.deepcopy(ADMIN_ACTOR),
        {"actor_id": 77, "actor_type": "Team", "bypass_mode": "always"},
    ]

    line = verdict(work, ruleset_api, landing(ruleset_api, bypass_actors=actors))

    assert line.startswith("fail ruleset:")
    assert "Team" in line
    assert page(ruleset_api) in line


def test_an_actor_without_a_bypass_mode_passes(work: Path, ruleset_api: Any) -> None:
    actors = [{"actor_id": 5, "actor_type": "RepositoryRole"}]

    line = verdict(work, ruleset_api, landing(ruleset_api, bypass_actors=actors))

    assert line.startswith("ok ruleset:")


@pytest.mark.parametrize("mode", ["pull_request", "exempt"])
def test_an_actor_whose_mode_is_not_always_fails_naming_always(
    work: Path, ruleset_api: Any, mode: str
) -> None:
    actors = [{**ADMIN_ACTOR, "bypass_mode": mode}]

    line = verdict(work, ruleset_api, landing(ruleset_api, bypass_actors=actors))

    assert line.startswith("fail ruleset:")
    assert "always" in line


# --- The flag is the only way to the ruleset check ---------------------------------------------------------------


def test_without_the_flag_no_request_is_sent_and_there_is_no_ruleset_line(
    work: Path, ruleset_api: Any
) -> None:
    result = doctor(work, ruleset_api)

    assert ruleset_api.requests == []
    assert " ruleset:" not in result.stdout


def test_a_command_line_doctor_does_not_know_exits_2_as_before(
    work: Path, ruleset_api: Any
) -> None:
    result = doctor(work, ruleset_api, "--ruleset", "--frob")

    assert result.returncode == 2
    assert "--frob" in result.stderr
    assert ruleset_api.requests == []
