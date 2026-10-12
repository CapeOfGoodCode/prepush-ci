"""The suite's own `tests/conftest.py`: what it shields the suite from."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PROBE = """
import os
import subprocess
from pathlib import Path

REPOSITORY_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def test_the_probe_sees_no_repository_variable() -> None:
    assert [k for k in REPOSITORY_VARIABLES if k in os.environ] == []


def test_the_probe_configures_its_own_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for key, value in (("core.bare", "true"), ("user.name", "Test")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def test_the_suite_leaves_the_repository_of_the_git_that_started_it_alone(
    tmp_path: Path,
) -> None:
    """A pre-push hook run from a linked worktree gets `GIT_DIR` and friends (#77)."""
    main = tmp_path / "main"
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    git(
        main,
        "-c",
        "user.name=a",
        "-c",
        "user.email=a@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "init",
    )
    git(main, "worktree", "add", "-q", str(tmp_path / "linked"), "-b", "other")
    hook_env = {
        **os.environ,
        "GIT_DIR": git(main, "rev-parse", "--absolute-git-dir") + "/worktrees/linked",
        "GIT_COMMON_DIR": git(main, "rev-parse", "--absolute-git-dir"),
        "GIT_WORK_TREE": str(tmp_path / "linked"),
        "GIT_INDEX_FILE": str(tmp_path / "linked" / "index"),
    }
    suite = tmp_path / "suite"
    suite.mkdir()
    shutil.copy(ROOT / "tests" / "conftest.py", suite / "conftest.py")
    (suite / "probe_spec.py").write_text(PROBE, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "python_files=*_spec.py",
            str(suite),
        ],
        cwd=suite,
        env=hook_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert git(main, "config", "--local", "--get", "core.bare") != "true"
    assert git(main, "config", "--local", "--get", "user.name") == ""
