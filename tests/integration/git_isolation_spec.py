"""The suite's own git: nothing a spec starts may outlive it."""

import subprocess
from pathlib import Path


def test_git_in_a_spec_repository_starts_no_fsmonitor_daemon(repo: Path) -> None:
    """Git for Windows enables core.fsmonitor in its system config; every temporary repository
    would then keep a `git fsmonitor--daemon` running after its test (#61). Any git a spec or
    the tool starts inherits the environment, so it is read the way they would see it."""
    enabled = subprocess.run(
        ["git", "config", "--get", "core.fsmonitor"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert enabled.stdout.strip() == "false"
