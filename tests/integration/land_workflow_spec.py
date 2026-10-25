"""`docs/ci/land.yml` cannot run on GitHub from here, so these specs parse the YAML and assert on
the parsed structure, and run the `run:` of its steps under `sh` with a stub `gh` and a stub
`prepush-ci`. That the file works in a real repository is for the first landing to show."""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

LAND = Path(__file__).resolve().parents[2] / "docs" / "ci" / "land.yml"

POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="the steps run under sh with stubs"
)
APP_TOKEN = "ghs_app_token"
JOB_TOKEN = "ghs_job_token"


def load() -> dict[str, Any]:
    data = yaml.safe_load(LAND.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # YAML 1.1 reads the key `on` as the boolean True
    return workflow.get("on", workflow.get(True))


def job() -> dict[str, Any]:
    return load()["jobs"]["land"]


def step(id_: str) -> dict[str, Any]:
    found = [s for s in job()["steps"] if s.get("id") == id_]
    assert len(found) == 1, f"{len(found)} steps have the id {id_}"
    return found[0]


def leading_comment() -> str:
    lines = []
    for line in LAND.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line.lstrip("# "))
    return " ".join(" ".join(lines).split())


# --- The workflow runs when a review is submitted ---------------------------------------


def test_one_event() -> None:
    workflow = load()

    assert triggers(workflow) == {"pull_request_review": {"types": ["submitted"]}}
    assert list(workflow["jobs"]) == ["land"]


def test_approved_from_this_repository() -> None:
    condition = job()["if"]

    assert "github.event.review.state == 'approved'" in condition
    assert (
        "github.event.pull_request.head.repo.full_name == github.repository"
        in condition
    )


def test_the_job_condition_leaves_the_draft_to_decide() -> None:
    assert "draft" not in job()["if"]


def test_no_default_permissions() -> None:
    assert load()["permissions"] == {}
    assert job()["permissions"] == {"contents": "read", "pull-requests": "write"}


# --- A step decides whether to land -----------------------------------------------------


def test_later_steps_wait_for_the_decision() -> None:
    steps = job()["steps"]
    position = [s.get("id") for s in steps].index("decide")

    assert position == 0
    for later in steps[position + 1 :]:
        assert "steps.decide.outputs.land == 'true'" in later["if"]


APPROVED = {
    "REPOSITORY": "acme/widgets",
    "REVIEWER": "alice",
    "REVIEW_ID": "42",
    "REVIEW_COMMIT": "a" * 40,
    "NUMBER": "7",
    "DEFAULT_BRANCH": "main",
}
# What the event's copy still holds in a re-run, though `decide` must not read it
EVENT_COPY = {
    "HEAD_SHA": "a" * 40,
    "BASE_REF": "main",
    "DRAFT": "false",
    "PR_STATE": "open",
    "REVIEW_STATE": "approved",
}


def stubs(tmp_path: Path, *, gh: str, prepush: str = "exit 0") -> Path:
    """A directory for PATH with a `gh` and a `prepush-ci` that record their arguments."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in (("gh", gh), ("prepush-ci", prepush)):
        path = bin_dir / name
        log = (tmp_path / f"{name}.args").as_posix()
        path.write_text(
            f'#!/bin/sh\nprintf "%s\\0" "$@" > {log}\necho "$*" >> {log}.calls\n'
            f'printf "%s" "${{GITHUB_TOKEN:-}}" > {log}.token\n{body}\n',
            newline="\n",
        )
        path.chmod(0o755)
    return bin_dir


def recorded(tmp_path: Path, name: str) -> list[str]:
    """The arguments the stub `name` got."""
    return (tmp_path / f"{name}.args").read_text().split("\0")[:-1]


def run_step(
    tmp_path: Path, id_: str, env: dict[str, str], bin_dir: Path
) -> "tuple[subprocess.CompletedProcess[str], str]":
    """The `run:` of the step under `sh` with the step's `env:` replaced by `env`; the result and
    what the step wrote to `GITHUB_OUTPUT`."""
    output = tmp_path / "output"
    output.write_text("")
    result = subprocess.run(
        ["sh", "-e", "-c", step(id_)["run"]],
        cwd=tmp_path,
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_OUTPUT": output.as_posix(),
            **env,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, output.read_text()


PERMISSION_CALL = (
    "api repos/acme/widgets/collaborators/alice/permission --jq .permission"
)
PULL_CALL = "api repos/acme/widgets/pulls/7 --jq"
REVIEW_CALL = "api repos/acme/widgets/pulls/7/reviews/42 --jq .state"


def pull_answer(
    head: str = "a" * 40, base: str = "main", draft: str = "false", state: str = "open"
) -> str:
    """The line `decide` asks `--jq` for: the head sha, base branch, draft flag and state."""
    return f"{head} {base} {draft} {state}"


def gh_stub(permission: str, pull: str, review: str, failing: str = "") -> str:
    """A `gh` that answers each of the three calls of `decide`; the call named by `failing`
    answers and then fails, so that only its status can stop a landing."""

    def answer(kind: str, text: str) -> str:
        return f'echo "{text}"; exit {1 if failing == kind else 0}'

    return "\n".join(
        [
            "case $2 in",
            f"  */collaborators/*) {answer('permission', permission)};;",
            f"  */reviews/*) {answer('review', review)};;",
            f"  *) {answer('pull', pull)};;",
            "esac",
        ]
    )


def decide(
    tmp_path: Path,
    permission: str = "write",
    *,
    pull: str | None = None,
    review: str = "APPROVED",
    failing: str = "",
    **changes: str,
) -> str:
    """What `decide` wrote, given the answers of the three calls (`failing` names one that
    fails after answering)."""
    bin_dir = stubs(
        tmp_path,
        gh=gh_stub(
            permission, pull_answer() if pull is None else pull, review, failing
        ),
    )
    result, written = run_step(
        tmp_path,
        "decide",
        {**APPROVED, **EVENT_COPY, **changes, "GH_TOKEN": JOB_TOKEN},
        bin_dir,
    )
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "gh.args.calls").read_text().splitlines()
    assert PERMISSION_CALL in calls
    assert all(
        call.startswith((PERMISSION_CALL, PULL_CALL, REVIEW_CALL)) for call in calls
    )
    return written


def test_the_event_copy_of_the_pull_request_is_not_read() -> None:
    read = str(step("decide")["env"]) + step("decide")["run"]

    for name in ("head.sha", "base.ref", "draft", "state"):
        assert f"github.event.pull_request.{name}" not in read


def test_the_payload_gives_decide_only_what_cannot_change() -> None:
    env = step("decide")["env"]

    assert env["NUMBER"] == "${{ github.event.pull_request.number }}"
    assert env["REVIEWER"] == "${{ github.event.review.user.login }}"
    assert env["REVIEW_ID"] == "${{ github.event.review.id }}"
    assert env["REVIEW_COMMIT"] == "${{ github.event.review.commit_id }}"
    assert env["DEFAULT_BRANCH"] == "${{ github.event.repository.default_branch }}"


@POSIX_ONLY
@pytest.mark.parametrize("permission", ["write", "admin"])
def test_a_writer_approves_the_current_head(tmp_path: Path, permission: str) -> None:
    assert decide(tmp_path, permission) == "land=true\n"
    calls = (tmp_path / "gh.args.calls").read_text().splitlines()
    assert any(call.startswith(PULL_CALL) for call in calls)
    assert REVIEW_CALL in calls


@POSIX_ONLY
@pytest.mark.parametrize("permission", ["read", "none", "", "triage"])
def test_a_reader_approves(tmp_path: Path, permission: str) -> None:
    assert decide(tmp_path, permission) == "land=false\n"


@POSIX_ONLY
@pytest.mark.parametrize("failing", ["permission", "pull", "review"])
def test_a_call_cannot_be_read(tmp_path: Path, failing: str) -> None:
    assert decide(tmp_path, failing=failing) == "land=false\n"


@POSIX_ONLY
def test_an_empty_answer_for_the_pull_request_does_not_land(tmp_path: Path) -> None:
    assert decide(tmp_path, pull="") == "land=false\n"


@POSIX_ONLY
def test_the_head_moved_after_the_approval(tmp_path: Path) -> None:
    assert decide(tmp_path, "admin", REVIEW_COMMIT="b" * 40) == "land=false\n"


@POSIX_ONLY
def test_the_head_moved_after_the_event_in_a_re_run(tmp_path: Path) -> None:
    # the event's copy still says the approved head; the API gives another one
    assert decide(tmp_path, pull=pull_answer(head="b" * 40)) == "land=false\n"


@POSIX_ONLY
def test_based_on_another_branch(tmp_path: Path) -> None:
    assert decide(tmp_path, pull=pull_answer(base="feature")) == "land=false\n"


@POSIX_ONLY
def test_retargeted_after_the_event_in_a_re_run(tmp_path: Path) -> None:
    # BASE_REF of the event's copy is `main`; the API says `feature`
    answer = pull_answer(base="feature")

    assert decide(tmp_path, pull=answer, BASE_REF="main") == "land=false\n"


@POSIX_ONLY
def test_based_on_the_default_branch(tmp_path: Path) -> None:
    assert decide(tmp_path, pull=pull_answer(base="main")) == "land=true\n"


@POSIX_ONLY
def test_a_default_branch_renamed_since_the_event_does_not_land(
    tmp_path: Path,
) -> None:
    assert decide(tmp_path, DEFAULT_BRANCH="trunk") == "land=false\n"


@POSIX_ONLY
def test_closed_since_the_review(tmp_path: Path) -> None:
    assert decide(tmp_path, pull=pull_answer(state="closed")) == "land=false\n"


@POSIX_ONLY
def test_a_draft_since_the_review(tmp_path: Path) -> None:
    assert decide(tmp_path, pull=pull_answer(draft="true")) == "land=false\n"


@POSIX_ONLY
def test_dismissed_after_the_event(tmp_path: Path) -> None:
    # REVIEW_STATE of the event's copy is still `approved`
    assert decide(tmp_path, review="DISMISSED") == "land=false\n"


@POSIX_ONLY
def test_still_approved(tmp_path: Path) -> None:
    assert decide(tmp_path, review="APPROVED") == "land=true\n"


# --- Every approval is handled ----------------------------------------------------------


def test_no_concurrency_group() -> None:
    assert "concurrency" not in load()
    assert "concurrency" not in job()


def test_the_example_does_not_claim_an_order_it_does_not_keep() -> None:
    assert "one at a time" not in leading_comment()


@POSIX_ONLY
def test_the_second_of_two_landings_is_told(tmp_path: Path) -> None:
    moved = (
        "not landed: main of origin has commits that the head does not contain: "
        "rebase onto main and push again"
    )
    bin_dir = stubs(tmp_path, gh="exit 0", prepush=f"echo '{moved}'\nexit 1")
    result, written = run_step(
        tmp_path,
        "land",
        {"PREPUSH_CI_CMD": "prepush-ci", "NUMBER": "7", "GITHUB_TOKEN": APP_TOKEN},
        bin_dir,
    )
    assert result.returncode == 1
    assert written == f"line={moved}\n"

    body = comment(tmp_path, moved)[4]

    assert moved in body and "rebase" in body
    assert step("land")["continue-on-error"] is True


# --- Land runs with the token of the app ------------------------------------------------


def test_the_token_is_made_from_the_apps_variables() -> None:
    token = step("token")

    assert re.fullmatch(r"actions/create-github-app-token@[0-9a-f]{40}", token["uses"])
    assert token["with"]["app-id"] == "${{ vars.PREPUSH_CI_APP_ID }}"
    assert token["with"]["private-key"] == "${{ secrets.PREPUSH_CI_APP_KEY }}"


def test_checkout_of_the_default_branch() -> None:
    checkout = [
        s for s in job()["steps"] if s.get("uses", "").startswith("actions/checkout@")
    ]

    assert len(checkout) == 1
    assert re.fullmatch(r"actions/checkout@[0-9a-f]{40}", checkout[0]["uses"])
    assert checkout[0]["with"]["ref"] == "${{ github.event.repository.default_branch }}"
    assert checkout[0]["with"]["fetch-depth"] == 0
    assert checkout[0]["with"]["token"] == "${{ steps.token.outputs.token }}"


@POSIX_ONLY
def test_land_gets_the_number_and_the_token(tmp_path: Path) -> None:
    bin_dir = stubs(tmp_path, gh="exit 0", prepush="echo 'landed: abc on main'")

    result, written = run_step(
        tmp_path,
        "land",
        {"PREPUSH_CI_CMD": "prepush-ci", "NUMBER": "7", "GITHUB_TOKEN": APP_TOKEN},
        bin_dir,
    )

    assert result.returncode == 0, result.stderr
    assert recorded(tmp_path, "prepush-ci") == ["land", "7"]
    assert (tmp_path / "prepush-ci.args.token").read_text() == APP_TOKEN
    assert written == "line=landed: abc on main\n"


def test_nothing_is_interpolated_into_a_script() -> None:
    scripts = [s["run"] for s in job()["steps"] if "run" in s]

    assert scripts
    assert all("${{" not in script for script in scripts)


# --- The line of land is kept -----------------------------------------------------------


@POSIX_ONLY
def test_the_line_is_kept(tmp_path: Path) -> None:
    bin_dir = stubs(
        tmp_path,
        gh="exit 0",
        prepush="echo 'not landed: the branch moved'\necho 'a second line'\nexit 1",
    )

    result, written = run_step(
        tmp_path,
        "land",
        {"PREPUSH_CI_CMD": "prepush-ci", "NUMBER": "7", "GITHUB_TOKEN": APP_TOKEN},
        bin_dir,
    )

    assert written == "line=not landed: the branch moved\n"
    assert result.returncode == 1


def test_a_refusal_does_not_fail_the_job() -> None:
    assert step("land")["continue-on-error"] is True


# --- A refusal is told on the pull request ----------------------------------------------

COMMENT_ENV = {
    "NUMBER": "7",
    "DEFAULT_BRANCH": "main",
    "RUN_URL": "https://github.com/acme/widgets/actions/runs/9",
    "GH_TOKEN": JOB_TOKEN,
}


def comment(tmp_path: Path, line: str) -> list[str]:
    """The arguments `gh` got from the step `comment` for that line."""
    bin_dir = stubs(tmp_path, gh="exit 0")
    result, _ = run_step(tmp_path, "comment", {**COMMENT_ENV, "LINE": line}, bin_dir)
    assert result.returncode == 0, result.stderr
    return recorded(tmp_path, "gh")


@POSIX_ONLY
def test_a_refusal_is_commented(tmp_path: Path) -> None:
    args = comment(tmp_path, "not landed: the branch moved")

    assert args[:4] == ["pr", "comment", "7", "--body"]
    body = args[4]
    for text in (
        "not landed: the branch moved",
        "main",
        "rebase",
        "pre-push",
        "approval",
        COMMENT_ENV["RUN_URL"],
    ):
        assert text in body


@POSIX_ONLY
def test_a_refusal_a_rebase_cannot_fix(tmp_path: Path) -> None:
    body = comment(tmp_path, "not landed: missing A_URL")[4]

    assert "not landed: missing A_URL" in body
    assert "workflow" in body and "env" in body


@POSIX_ONLY
def test_a_backtick_cannot_break_out(tmp_path: Path) -> None:
    body = comment(tmp_path, "not landed: ```x``` please")[4]

    assert "not landed: " in body
    assert "``` " not in body and "```not" not in body
    assert body.count("```") == 2


@POSIX_ONLY
def test_a_crash_without_a_line_is_commented_with_the_link_of_the_run(
    tmp_path: Path,
) -> None:
    body = comment(tmp_path, "")[4]

    assert COMMENT_ENV["RUN_URL"] in body


def test_only_a_failed_landing_is_commented() -> None:
    commenting = step("comment")

    assert "steps.land.outcome == 'failure'" in commenting["if"]
    assert "steps.decide.outputs.land == 'true'" in commenting["if"]
    assert commenting["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "steps.token" not in str(commenting)


@POSIX_ONLY
def test_a_landing_is_not_commented(tmp_path: Path) -> None:
    bin_dir = stubs(tmp_path, gh="exit 0", prepush="echo 'landed: abc on main'")
    result, _ = run_step(
        tmp_path,
        "land",
        {"PREPUSH_CI_CMD": "prepush-ci", "NUMBER": "7", "GITHUB_TOKEN": APP_TOKEN},
        bin_dir,
    )

    assert result.returncode == 0
    assert "steps.land.outcome == 'failure'" in step("comment")["if"]
    assert not (tmp_path / "gh.args").exists()


# --- The example says what it needs and what it costs -----------------------------------


@pytest.mark.parametrize(
    "name",
    [
        ".github/workflows",
        "app setup --land",
        "app ruleset --app",
        "PREPUSH_CI_APP_ID",
        "PREPUSH_CI_APP_KEY",
        "require_env",
    ],
)
def test_the_example_names_what_it_needs(name: str) -> None:
    assert name in leading_comment()


@pytest.mark.parametrize("name", ["preflight", "anyone who can push"])
def test_the_example_warns_of_what_it_costs(name: str) -> None:
    assert name in leading_comment()
