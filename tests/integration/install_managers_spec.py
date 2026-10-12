"""`prepush-ci install` for hook managers: the manager's own files, run by the real manager and git."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "Prepush-CI: full"
PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"


@pytest.fixture
def shim(tmp_path: Path) -> Path:
    """A directory with a `prepush-ci` command that starts this interpreter's module, so that the
    files the manager runs find the tool on `PATH` and coverage measures it."""
    directory = tmp_path / "shim"
    directory.mkdir()
    python = Path(sys.executable).as_posix()
    script = directory / "prepush-ci"
    script.write_text(f'#!/bin/sh\nexec "{python}" -m prepush_ci "$@"\n')
    script.chmod(0o755)
    (directory / "prepush-ci.cmd").write_text(
        f'@"{sys.executable}" -m prepush_ci %*\r\n'
    )  # pre-commit on Windows looks for an executable extension
    return directory


@pytest.fixture
def env(shim: Path, tmp_path: Path) -> dict[str, str]:
    """The environment of every command: the shim first on `PATH`, pre-commit's cache away from
    the developer's home, no inherited opt-in or pre-commit variables."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return {
        **inherited,
        "PATH": os.pathsep.join([str(shim), os.environ["PATH"]]),
        "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home"),
    }


@pytest.fixture
def ran(tmp_path: Path) -> Path:
    """The file the config's check appends to."""
    return tmp_path / "ran.log"


@pytest.fixture
def pushing(repo: Path, tmp_path: Path, git: Git, ran: Path) -> Path:
    """`repo` on `main` with one commit, a config whose check logs to `ran` and a bare `origin`."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()}"\nrequire_up_to_date = false\n'
    )
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return repo


def install(
    repo: Path, env: dict[str, str], *args: str
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci install` in `repo`."""
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "install", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def pre_commit_install(repo: Path, env: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def log_hook(directory: Path, log: Path) -> str:
    """The text of a `local` pre-commit hook `lint` without `stages` that appends to `log`."""
    script = directory / "lint.sh"
    script.write_text(f"#!/bin/sh\necho lint >> {log.as_posix()}\n")
    return (
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: lint\n"
        "        name: lint\n"
        f"        entry: sh {script.as_posix()}\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
    )


def commit(
    repo: Path, git: Git, env: dict[str, str], message: str = "add x"
) -> "subprocess.CompletedProcess[str]":
    (repo / "x.txt").write_text(message)
    git(repo, "add", "x.txt")
    return git(
        repo,
        "commit",
        "-q",
        "-m",
        message,
        env={**env, "PREPUSH_CI": "full"},
        check=False,
    )


def body(repo: Path, git: Git, rev: str = "HEAD") -> str:
    return git(repo, "log", "-1", "--format=%B", rev).stdout.strip()


def remote_has(repo: Path, git: Git, sha: str) -> bool:
    return git(repo, "ls-remote", "origin", "refs/heads/main").stdout.startswith(sha)


def lines(path: Path) -> list[str]:
    return path.read_text().split() if path.exists() else []


# pre-commit


def test_a_commit_through_pre_commit_gets_the_trailer_and_the_other_hook_runs(
    pushing: Path, tmp_path: Path, git: Git, env: dict[str, str]
) -> None:
    log = tmp_path / "lint.log"
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n" + log_hook(tmp_path, log))

    result = install(pushing, env)
    pre_commit_install(pushing, env)
    committed = commit(pushing, git, env)

    assert result.returncode == 0, result.stderr
    assert committed.returncode == 0, committed.stderr
    assert body(pushing, git).endswith(TRAILER)
    assert lines(log) == ["lint"]


def test_a_push_through_pre_commit_runs_the_check_and_reaches_the_remote(
    pushing: Path, git: Git, env: dict[str, str], ran: Path
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG)
    commit(pushing, git, env)
    sha = git(pushing, "rev-parse", "HEAD").stdout.strip()

    pushed = git(pushing, "push", "origin", "main", env=env, check=False)

    assert pushed.returncode == 0, pushed.stderr
    assert lines(ran) == ["ran"]
    assert remote_has(pushing, git, sha)


def test_a_failing_check_refuses_a_push_through_pre_commit(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    (pushing / ".prepush-ci.toml").write_text(
        'check = "exit 1"\nrequire_up_to_date = false\n'
    )
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG, ".prepush-ci.toml")
    commit(pushing, git, env)

    pushed = git(pushing, "push", "origin", "main", env=env, check=False)

    assert pushed.returncode != 0
    assert git(pushing, "ls-remote", "origin").stdout == ""


def test_an_existing_pre_commit_hook_runs_on_commit_and_never_on_push(
    pushing: Path, tmp_path: Path, git: Git, env: dict[str, str]
) -> None:
    log = tmp_path / "lint.log"
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n" + log_hook(tmp_path, log))
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG)
    commit(pushing, git, env)
    after_commit = lines(log)

    git(pushing, "push", "origin", "main", env=env)

    assert after_commit == ["lint"]
    assert lines(log) == ["lint"]


def test_hook_types_the_team_already_used_keep_their_stages(
    pushing: Path, tmp_path: Path, git: Git, env: dict[str, str]
) -> None:
    log = tmp_path / "lint.log"
    (pushing / PRE_COMMIT_CONFIG).write_text(
        "default_install_hook_types: [pre-commit, pre-push]\n"
        "repos:\n" + log_hook(tmp_path, log)
    )
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG)
    commit(pushing, git, env)
    git(pushing, "push", "origin", "main", env=env)

    text = (pushing / PRE_COMMIT_CONFIG).read_text()
    assert "default_stages: [pre-commit, pre-push]\n" in text
    assert lines(log) == ["lint", "lint"]  # once on the commit, once on the push


def test_a_pre_commit_config_without_hook_types_gets_all_three_installed(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    install(pushing, env)
    pre_commit_install(pushing, env)

    text = (pushing / PRE_COMMIT_CONFIG).read_text()
    assert "default_install_hook_types: [pre-commit, commit-msg, pre-push]\n" in text
    hooks = {path.name for path in (pushing / ".git" / "hooks").iterdir()}
    assert {"pre-commit", "commit-msg", "pre-push"} <= hooks


def test_a_pre_commit_config_that_is_not_a_block_list_is_refused_and_unchanged(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos: []\n")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "repos" in result.stderr
    assert (pushing / PRE_COMMIT_CONFIG).read_text() == "repos: []\n"


def test_a_pre_commit_install_leaves_git_alone(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    before = sorted(p.name for p in (pushing / ".git" / "hooks").iterdir())

    result = install(pushing, env, "--hooks", "pre-commit")

    assert result.returncode == 0, result.stderr
    assert git(pushing, "config", "core.hooksPath", check=False).stdout == ""
    assert sorted(p.name for p in (pushing / ".git" / "hooks").iterdir()) == before
    assert not (pushing / ".git" / "prepush-ci").exists()


def test_the_pre_commit_block_holds_no_local_path_and_no_check_command(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    (pushing / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')

    install(pushing, env, "--hooks", "pre-commit")

    written = (pushing / PRE_COMMIT_CONFIG).read_text()
    assert "prepush-ci hook" in written
    assert str(pushing) not in written
    assert Path(sys.executable).as_posix() not in written
    assert "scripts/ci" not in written
    assert "args:" not in written


def test_a_second_pre_commit_install_writes_nothing_and_says_so(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / PRE_COMMIT_CONFIG
    path.write_text("repos:\n  - repo: local\n    hooks: []\n")
    first = install(pushing, env, "--hooks", "pre-commit")
    stamp = path.stat().st_mtime_ns
    contents = path.read_text()

    second = install(pushing, env, "--hooks", "pre-commit")

    assert "installed" in first.stdout and "already installed" not in first.stdout
    assert second.returncode == 0
    assert "already installed" in second.stdout
    assert (path.read_text(), path.stat().st_mtime_ns) == (contents, stamp)


def test_a_hand_edited_pre_commit_block_is_restored_and_reported_updated(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / PRE_COMMIT_CONFIG
    path.write_text("repos:\n  - repo: local\n    hooks: []\n")
    install(pushing, env, "--hooks", "pre-commit")
    installed = path.read_text()
    path.write_text(installed.replace("language: system", "language: fail", 1))

    result = install(pushing, env, "--hooks", "pre-commit")

    assert "updated" in result.stdout
    assert path.read_text() == installed


def test_the_pre_commit_report_names_the_file_and_the_activation_step(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    result = install(pushing, env, "--hooks", "pre-commit")

    assert PRE_COMMIT_CONFIG in result.stdout
    assert "pre-commit install" in result.stdout
