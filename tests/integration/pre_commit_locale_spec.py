"""In the ascii variant pre-commit's own processes keep the outer locale; every other process stays hostile.

pre-commit 4.6 cannot run under `LC_ALL=C` in a directory whose name is not ASCII, so the specs that
drive it (`pre-commit install`, and the commits and pushes whose hooks it runs) give those processes
the locale the variant replaced, through the one `pre_commit_locale` helper of `conftest.py`. This
spec drives pre-commit and the CLI side by side and records the environment each process really gets.
"""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]
Locale = Callable[..., dict[str, str]]

KEYS = ("LC_ALL", "PYTHONUTF8", "PYTHONCOERCECLOCALE")
HOSTILE = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}


def recorder(directory: Path, name: str) -> tuple[str, Path]:
    """A command that appends the three variables it gets to a log, and that log."""
    script = directory / f"{name}.py"
    log = directory / f"{name}.log"
    script.write_text(
        "import json, os, sys\n"
        f"keys = {KEYS!r}\n"
        "with open(sys.argv[1], 'a') as log:\n"
        "    log.write(json.dumps({k: os.environ.get(k, '') for k in keys}) + '\\n')\n"
    )
    command = (
        f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}" "{log.as_posix()}"'
    )
    return command, log


def recorded(log: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in log.read_text().splitlines()]


class Scene:
    """What pre-commit's hooks and the CLI's preflight recorded in one repository."""

    def __init__(
        self,
        repo: Path,
        hooks: Path,
        preflight: Path,
        cli: "subprocess.CompletedProcess[str]",
    ) -> None:
        self.repo = repo
        self.hooks = recorded(hooks)
        self.preflight = recorded(preflight)
        self.doctor = cli


@pytest.fixture
def scene(repo: Path, tmp_path: Path, git: Git, pre_commit_locale: Locale) -> Scene:
    """The processes of pre-commit and of the CLI, each started the way its specs start it:
    `install --hooks pre-commit` and `pre-commit install`, a commit and a push through pre-commit's
    hooks, then `doctor`."""
    shim = tmp_path / "shim"
    shim.mkdir()
    python = Path(sys.executable).as_posix()
    (shim / "prepush-ci").write_text(f'#!/bin/sh\nexec "{python}" -m prepush_ci "$@"\n')
    (shim / "prepush-ci").chmod(0o755)
    (shim / "prepush-ci.cmd").write_text(f'@"{sys.executable}" -m prepush_ci %*\r\n')
    hook, hooks = recorder(tmp_path, "hook")
    preflight, preflights = recorder(tmp_path, "preflight")
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".prepush-ci.toml").write_text(
        f"check = \"true\"\npreflight = '{preflight}'\nrequire_up_to_date = false\n"
    )
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: record\n"
        "        name: record\n"
        f"        entry: '{hook}'\n"
        "        language: system\n"
        "        always_run: true\n"
        "        pass_filenames: false\n"
        "        stages: [pre-commit, pre-push]\n"
    )
    cli_env = {**os.environ, "PATH": os.pathsep.join([str(shim), os.environ["PATH"]])}
    pre_commit_env = pre_commit_locale(
        {**cli_env, "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home")}
    )

    subprocess.run(
        [sys.executable, "-m", "prepush_ci", "install", "--hooks", "pre-commit"],
        cwd=repo,
        env=cli_env,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-commit"]
        + ["--hook-type", "pre-push", "--hook-type", "commit-msg"],
        cwd=repo,
        env=pre_commit_env,
        capture_output=True,
        check=True,
    )
    git(repo, "add", ".pre-commit-config.yaml", ".prepush-ci.toml")
    committed = git(
        repo, "commit", "-q", "-m", "add the hook", env=pre_commit_env, check=False
    )
    assert committed.returncode == 0, committed.stdout + committed.stderr
    git(repo, "push", "-q", "origin", "main", env=pre_commit_env)
    doctor = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "doctor"],
        cwd=repo,
        env=cli_env,
        capture_output=True,
        text=True,
        check=False,
    )
    return Scene(repo, hooks, preflights, doctor)


def test_pre_commits_processes_keep_the_outer_locale(
    scene: Scene, pre_commit_locale: Locale, variant: str
) -> None:
    outer = {key: pre_commit_locale({})[key] for key in KEYS}
    assert len(scene.hooks) == 2  # once for the commit, once for the push
    for seen in scene.hooks:
        assert seen == outer
        if variant == "ascii":
            assert seen != HOSTILE
    if variant == "ascii":
        assert not scene.repo.as_posix().isascii()


def test_every_other_process_stays_hostile(scene: Scene, variant: str) -> None:
    assert "ok preflight" in scene.doctor.stdout, scene.doctor.stdout
    (seen,) = scene.preflight
    if variant == "ascii":
        assert seen == HOSTILE
    else:
        assert seen == {key: os.environ.get(key, "") for key in KEYS}


def test_a_spec_cannot_hand_the_exception_to_the_cli(
    repo: Path, pre_commit_locale: Locale, variant: str
) -> None:
    if variant != "ascii":
        return  # the variant has no exception to hand out
    with pytest.raises(AssertionError, match="CLI must keep the hostile locale"):
        subprocess.run(
            [sys.executable, "-m", "prepush_ci", "doctor", "--hooks", "none"],
            cwd=repo,
            env=pre_commit_locale(),
            capture_output=True,
            check=False,
        )
    with pytest.raises(AssertionError, match="pre-commit must get the outer locale"):
        subprocess.run(
            [sys.executable, "-m", "pre_commit", "--version"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
