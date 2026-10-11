"""The PreToolUse guard in .claude/hooks/guard.py: which agent shell commands it refuses."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "guard.py"


def guard_exit_code(command: str) -> int:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    ).returncode


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 3 --rebase",
        "gh api -X PUT repos/o/r/pulls/3/merge",
        "git push origin main",
        "git push -u origin HEAD:main",
        "git push origin +main",
        "git push --force",
        "git push -f origin feat/2-cli",
        "git commit --no-verify -m 'x'",
        "git push --no-verify",
        "git push origin v0.1.0",
        "git push --tags",
        "gh release create v0.1.0",
    ],
)
def test_guard_blocks_merging_pushing_to_main_force_pushing_and_skipping_hooks(
    command: str,
) -> None:
    assert guard_exit_code(command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "git push --force-with-lease origin feat/2-cli",
        "git push -u origin feat/2-main-thing",
        "git commit -m 'fix -n handling'",
        "gh pr create --draft --fill",
        "grep -r -- --no-verify AGENTS.md",
    ],
)
def test_guard_allows_ordinary_branch_work(command: str) -> None:
    assert guard_exit_code(command) == 0
