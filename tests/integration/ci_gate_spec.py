import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

GATE = Path(__file__).resolve().parents[2] / "docs" / "ci" / "gate.sh"
TRAILER = "\n\nPrepush-CI: full"

ELIGIBLE = {
    "GATE_PULL_REQUEST": "true",
    "GATE_HEAD_REPO": "owner/repo",
    "GATE_BASE_REPO": "owner/repo",
    "GATE_HEAD_BRANCH": "feature",
    "GATE_DEFAULT_BRANCH": "main",
}


def commit(repo: Path, git: Git, message: str, *, committer: str | None = None) -> str:
    """Make an empty commit; return its full sha."""
    env = {}
    if committer:
        env["GIT_COMMITTER_NAME"] = "Server"
        env["GIT_COMMITTER_EMAIL"] = committer
    git(repo, "commit", "--allow-empty", "-q", "-m", message, env=env)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def configured(repo: Path, git: Git) -> Path:
    (repo / ".prepush-ci.toml").write_text('check = "true"\n')
    git(repo, "add", ".prepush-ci.toml")
    commit(repo, git, "init")
    return repo


@pytest.fixture
def shim(tmp_path: Path) -> str:
    """A `PREPUSH_CI_CMD` that starts the CLI as `sys.executable -m prepush_ci`, so coverage
    measures it; `sh <script>` survives the gate's word splitting."""
    script = tmp_path / "prepush-ci-shim.sh"
    script.write_text(f'exec "{Path(sys.executable).as_posix()}" -m prepush_ci "$@"\n')
    return f"sh {script.as_posix()}"


def gate(
    cwd: Path, env: dict[str, str], drop: tuple[str, ...] = ()
) -> "subprocess.CompletedProcess[str]":
    """Run the gate with `sh` the way a CI step would, in a clean environment."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GATE_", "PRE_COMMIT_"))
        and k not in ("PREPUSH_CI", "PREPUSH_CI_CMD")
    }
    merged = {**inherited, **env}
    for name in drop:
        merged.pop(name, None)
    return subprocess.run(
        ["sh", GATE.as_posix()],
        cwd=cwd,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


def eligible(sha: str, shim: str, **overrides: str) -> dict[str, str]:
    return {**ELIGIBLE, "GATE_HEAD_SHA": sha, "PREPUSH_CI_CMD": shim, **overrides}


def test_gate_prints_exactly_one_line_when_the_head_commit_carries_the_trailer(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, shim))

    assert result.stdout == "verified=true\n"
    assert result.returncode == 0, result.stderr


def test_gate_gives_the_reason_on_standard_error_when_the_head_commit_has_no_trailer(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work")

    result = gate(configured, eligible(sha, shim))

    assert result.stdout == "verified=false\n"
    assert "not verified: " in result.stderr
    assert result.returncode == 0


def test_gate_verifies_a_pull_request_from_the_same_repository(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    assert gate(configured, eligible(sha, shim)).stdout == "verified=true\n"


def test_gate_runs_uvx_prepush_ci_verify_when_no_command_is_set(
    configured: Path, git: Git, tmp_path: Path
) -> None:
    sha = commit(configured, git, "work" + TRAILER)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    recorded = tmp_path / "args.log"
    uvx = bin_dir / "uvx"
    uvx.write_text(f'#!/bin/sh\necho "$@" > {recorded.as_posix()}\n')
    uvx.chmod(0o755)
    env = {
        **ELIGIBLE,
        "GATE_HEAD_SHA": sha,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
    }

    result = gate(configured, env)

    assert result.stdout == "verified=true\n", result.stderr
    assert recorded.read_text().split() == ["prepush-ci", "verify", sha]


def test_gate_does_not_skip_when_the_run_is_not_a_pull_request(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, shim, GATE_PULL_REQUEST="false"))

    assert result.stdout == "verified=false\n"


def test_gate_does_not_skip_a_pull_request_from_a_fork(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, shim, GATE_HEAD_REPO="fork/repo"))

    assert result.stdout == "verified=false\n"


def test_gate_does_not_skip_when_the_source_branch_is_the_default_branch(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, shim, GATE_HEAD_BRANCH="main"))

    assert result.stdout == "verified=false\n"


def test_gate_does_not_skip_when_the_head_commit_does_not_verify(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work")

    assert gate(configured, eligible(sha, shim)).stdout == "verified=false\n"


def test_gate_does_not_skip_a_server_made_head_commit_that_carries_the_trailer(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER, committer="noreply@github.com")

    assert gate(configured, eligible(sha, shim)).stdout == "verified=false\n"


def test_gate_does_not_skip_when_the_head_repository_is_empty(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, shim, GATE_HEAD_REPO=""))

    assert result.stdout == "verified=false\n"


def test_gate_does_not_skip_and_exits_0_when_the_head_sha_is_unset(
    configured: Path, git: Git, shim: str
) -> None:
    commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible("", shim), drop=("GATE_HEAD_SHA",))

    assert result.stdout == "verified=false\n"
    assert result.returncode == 0


def test_gate_does_not_skip_when_the_default_branch_is_empty(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, shim, GATE_DEFAULT_BRANCH=""))

    assert result.stdout == "verified=false\n"


def test_gate_does_not_skip_when_both_repositories_are_empty(
    configured: Path, git: Git, shim: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, shim, GATE_HEAD_REPO="", GATE_BASE_REPO=""))

    assert result.stdout == "verified=false\n"


def test_gate_does_not_skip_and_exits_0_when_the_command_does_not_exist(
    configured: Path, git: Git
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    result = gate(configured, eligible(sha, "no-such-program-prepush-ci"))

    assert result.stdout == "verified=false\n"
    assert result.returncode == 0


@pytest.mark.parametrize("name", sorted({*ELIGIBLE, "GATE_HEAD_SHA"}))
def test_gate_does_not_skip_when_any_one_input_is_empty_or_unset(
    configured: Path, git: Git, shim: str, name: str
) -> None:
    sha = commit(configured, git, "work" + TRAILER)

    empty = gate(configured, eligible(sha, shim, **{name: ""}))
    unset = gate(configured, eligible(sha, shim), drop=(name,))

    assert empty.stdout == "verified=false\n"
    assert unset.stdout == "verified=false\n"
    assert empty.returncode == unset.returncode == 0


def test_gate_is_written_in_posix_sh() -> None:
    text = GATE.read_text()

    assert text.splitlines()[0] == "#!/bin/sh"
    assert "[[" not in text


def test_gate_header_names_every_variable_it_reads() -> None:
    header = "\n".join(
        line for line in GATE.read_text().splitlines() if line.startswith("#")
    )

    for name in (
        "GATE_PULL_REQUEST",
        "GATE_HEAD_SHA",
        "GATE_HEAD_REPO",
        "GATE_BASE_REPO",
        "GATE_HEAD_BRANCH",
        "GATE_DEFAULT_BRANCH",
        "PREPUSH_CI_CMD",
    ):
        assert name in header


def test_gate_runs_verify_only_through_the_command_variable() -> None:
    code = [
        line
        for line in GATE.read_text().splitlines()
        if not line.lstrip().startswith("#")
    ]
    calls = [line for line in code if "verify " in line and "$GATE_HEAD_SHA" in line]

    assert calls
    assert all("$PREPUSH_CI_CMD verify" in line for line in calls)
