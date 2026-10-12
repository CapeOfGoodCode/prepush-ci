"""The CI files cannot run in a hosted CI from here, so these specs parse the YAML and assert on
the parsed structure: a comment or a stray line elsewhere cannot satisfy them. That the files work
in a real CI is for terminator to try."""

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "action.yml"
GITHUB = ROOT / "docs" / "ci" / "github-actions.yml"
GITLAB = ROOT / "docs" / "ci" / "gitlab-ci.yml"
GATE = ROOT / "docs" / "ci" / "gate.sh"


def load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    return data


def gate_step() -> dict[str, Any]:
    steps = load(ACTION)["runs"]["steps"]
    assert len(steps) == 1
    return steps[0]


def triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # YAML 1.1 reads the key `on` as the boolean True
    return workflow.get("on", workflow.get(True))


def jobs_other_than_the_gate(workflow: dict[str, Any]) -> dict[str, Any]:
    return {name: job for name, job in workflow["jobs"].items() if name != "gate"}


def comments(path: Path) -> str:
    return "\n".join(
        line for line in path.read_text().splitlines() if line.lstrip().startswith("#")
    )


# The action


def test_action_is_a_composite_whose_verified_output_is_the_gate_steps_output() -> None:
    action = load(ACTION)
    step = gate_step()

    assert action["runs"]["using"] == "composite"
    assert step["id"] == "gate"
    assert (
        action["outputs"]["verified"]["value"] == "${{ steps.gate.outputs.verified }}"
    )


def test_action_runs_the_gate_script_from_its_own_path_into_the_output_file() -> None:
    run = gate_step()["run"]

    assert "$GITHUB_ACTION_PATH/docs/ci/gate.sh" in run
    assert ">> " in run
    assert "$GITHUB_OUTPUT" in run


def test_action_command_input_defaults_to_pipx_run_and_reaches_the_gate_as_the_command() -> (
    None
):
    action = load(ACTION)

    assert action["inputs"]["command"]["default"] == "pipx run prepush-ci"
    assert gate_step()["env"]["PREPUSH_CI_CMD"] == "${{ inputs.command }}"


def test_action_maps_the_pull_request_event_to_the_gate_variables() -> None:
    env = gate_step()["env"]

    assert env["GATE_PULL_REQUEST"] == "${{ github.event_name == 'pull_request' }}"
    assert env["GATE_HEAD_SHA"] == "${{ github.event.pull_request.head.sha }}"
    assert (
        env["GATE_HEAD_REPO"] == "${{ github.event.pull_request.head.repo.full_name }}"
    )
    assert env["GATE_BASE_REPO"] == "${{ github.repository }}"
    assert env["GATE_HEAD_BRANCH"] == "${{ github.head_ref }}"
    assert env["GATE_DEFAULT_BRANCH"] == "${{ github.event.repository.default_branch }}"


def test_action_passes_event_values_through_the_environment_never_into_the_script() -> (
    None
):
    step = gate_step()
    expressions = [
        k
        for k, v in step["env"].items()
        if "github.head_ref" in v or "inputs.command" in v
    ]

    assert "${{" not in step["run"]
    assert sorted(expressions) == ["GATE_HEAD_BRANCH", "PREPUSH_CI_CMD"]
    assert "github.head_ref" not in str({k: v for k, v in step.items() if k != "env"})
    assert "inputs.command" not in str({k: v for k, v in step.items() if k != "env"})


def test_action_does_not_mention_the_pull_request_target_event() -> None:
    assert "pull_request_target" not in ACTION.read_text()


# The GitHub Actions example


def test_github_example_checks_out_the_head_commit_for_the_gate_and_gates_only_pull_requests() -> (
    None
):
    workflow = load(GITHUB)
    gate = workflow["jobs"]["gate"]
    checkout = next(
        s for s in gate["steps"] if s.get("uses", "").startswith("actions/checkout")
    )
    on = triggers(workflow)

    assert checkout["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    assert gate["outputs"]["verified"] == "${{ steps.gate.outputs.verified }}"
    assert any(
        s.get("id") == "gate" and "prepush-ci" in s["uses"] for s in gate["steps"]
    )
    assert "pull_request" in on
    assert on["push"]["branches"] == ["main"]


def test_github_example_every_other_job_waits_for_the_gate_and_runs_unless_it_says_true() -> (
    None
):
    others = jobs_other_than_the_gate(load(GITHUB))

    assert others
    for job in others.values():
        assert job["needs"] in ("gate", ["gate"])
        condition = job["if"]
        assert "!cancelled()" in condition
        assert "needs.gate.outputs.verified != 'true'" in condition


def test_github_example_no_job_is_skipped_when_the_gate_fails() -> None:
    for job in jobs_other_than_the_gate(load(GITHUB)).values():
        assert any(
            f in job.get("if", "") for f in ("!cancelled()", "always()", "failure()")
        )


# The GitLab CI example


MERGE_REQUEST = {
    "CI_MERGE_REQUEST_SOURCE_PROJECT_PATH": "owner/repo",
    "CI_PROJECT_PATH": "owner/repo",
    "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "feature",
    "CI_DEFAULT_BRANCH": "main",
    "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": "1111111",
    "CI_COMMIT_SHA": "2222222",
}


def run_gitlab_gate(
    tmp_path: Path, verify_exit: int = 0, **overrides: str
) -> tuple[dict[str, Any], list[str]]:
    """Run the gate job's script (plain sh) with a `uvx` stub on PATH; return the generated
    child pipeline and the arguments the stub got."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    recorded = tmp_path / "uvx-args.log"
    uvx = bin_dir / "uvx"
    uvx.write_text(
        f'#!/bin/sh\necho "$@" > {recorded.as_posix()}\nexit {verify_exit}\n'
    )
    uvx.chmod(0o755)
    work = tmp_path / "job"
    work.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("CI_")}
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    env.update({**MERGE_REQUEST, **overrides})
    script = load(GITLAB)["gate"]["script"]
    assert len(script) == 1
    result = subprocess.run(
        ["sh", "-c", script[0]],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    child = yaml.safe_load((work / "child.yml").read_text())
    return child, recorded.read_text().split() if recorded.exists() else []


def test_gitlab_gate_skips_a_merge_request_from_the_same_project_whose_head_verifies(
    tmp_path: Path,
) -> None:
    child, args = run_gitlab_gate(tmp_path)

    assert "verified" in child
    assert "include" not in child
    assert args == ["prepush-ci", "verify", "1111111"]


def test_gitlab_gate_runs_the_full_pipeline_for_a_merge_request_from_a_fork(
    tmp_path: Path,
) -> None:
    child, _ = run_gitlab_gate(
        tmp_path, CI_MERGE_REQUEST_SOURCE_PROJECT_PATH="fork/repo"
    )

    assert "include" in child
    assert "verified" not in child


def test_gitlab_gate_runs_the_full_pipeline_when_the_source_branch_is_the_default_branch(
    tmp_path: Path,
) -> None:
    child, _ = run_gitlab_gate(tmp_path, CI_MERGE_REQUEST_SOURCE_BRANCH_NAME="main")

    assert "include" in child
    assert "verified" not in child


def test_gitlab_gate_runs_the_full_pipeline_when_the_head_does_not_verify(
    tmp_path: Path,
) -> None:
    child, args = run_gitlab_gate(tmp_path, verify_exit=1)

    assert "include" in child
    assert "verified" not in child
    assert args == ["prepush-ci", "verify", "1111111"]


def test_gitlab_gate_runs_the_full_pipeline_when_the_source_project_is_unknown(
    tmp_path: Path,
) -> None:
    child, _ = run_gitlab_gate(
        tmp_path, CI_MERGE_REQUEST_SOURCE_PROJECT_PATH="", CI_PROJECT_PATH=""
    )

    assert "include" in child
    assert "verified" not in child


def test_gitlab_gate_verifies_the_commit_sha_when_the_source_branch_sha_is_unset(
    tmp_path: Path,
) -> None:
    _, args = run_gitlab_gate(tmp_path, CI_MERGE_REQUEST_SOURCE_BRANCH_SHA="")

    assert args == ["prepush-ci", "verify", "2222222"]


def test_gitlab_example_gates_only_merge_request_pipelines() -> None:
    gate = load(GITLAB)["gate"]

    assert [r["if"] for r in gate["rules"]] == [
        '$CI_PIPELINE_SOURCE == "merge_request_event"'
    ]


def test_gitlab_example_runs_the_full_pipeline_on_the_default_branch() -> None:
    run = load(GITLAB)["run-default-branch"]

    assert [r["if"] for r in run["rules"]] == [
        "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH"
    ]
    assert run["trigger"]["include"] == "ci/pipeline.yml"


def test_gitlab_example_warns_against_the_rebase_button() -> None:
    text = comments(GITLAB)

    assert "Rebase" in text
    assert "skipping" in text


# The optional full run


@pytest.mark.parametrize("path", [GATE, GITHUB, GITLAB], ids=lambda p: p.name)
def test_every_example_names_the_optional_full_run_and_says_it_is_off(
    path: Path,
) -> None:
    text = comments(path)

    assert "one full run per pull request" in text
    assert "off" in text
