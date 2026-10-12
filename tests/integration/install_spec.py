"""`prepush-ci install`: native hooks through core.hooksPath, run by real git."""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from prepush_ci import install_command

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "Prepush-CI: full"


def install(
    repo: Path, *, python: str | None = None, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci install` in `repo` with `python` (default: this interpreter)."""
    return subprocess.run(
        [python or sys.executable, "-m", "prepush_ci", "install"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


def hooks_dir(repo: Path) -> Path:
    return repo / ".git" / "prepush-ci" / "hooks"


@pytest.fixture
def ran(tmp_path: Path) -> Path:
    """The file the config's check appends to."""
    return tmp_path / "ran.log"


@pytest.fixture
def pushing(repo: Path, tmp_path: Path, git: Git, ran: Path) -> Path:
    """`repo` on `main` with one commit, a config whose check logs to `ran`, a bare `origin` and
    no hook installed: specs call `install` themselves."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()}"\nrequire_up_to_date = false\n'
    )
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return repo


def commit_with_trailer(repo: Path, git: Git, name: str = "x") -> str:
    (repo / f"{name}.txt").write_text(name)
    git(repo, "add", f"{name}.txt")
    git(repo, "commit", "-q", "-m", f"add {name}", env={"PREPUSH_CI": "full"})
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def remote_has(repo: Path, git: Git, sha: str) -> bool:
    return git(repo, "ls-remote", "origin", "refs/heads/main").stdout.startswith(sha)


def test_a_commit_after_install_gets_the_trailer(pushing: Path, git: Git) -> None:
    assert install(pushing).returncode == 0

    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")
    git(pushing, "commit", "-q", "-m", "add x", env={"PREPUSH_CI": "full"})

    message = git(pushing, "log", "-1", "--format=%B").stdout
    assert message.strip().endswith(TRAILER)


def test_a_push_after_install_runs_the_check_and_reaches_the_remote(
    pushing: Path, git: Git, ran: Path
) -> None:
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    git(pushing, "push", "-q", "origin", "main")

    assert ran.read_text().split() == ["ran"]  # cmd keeps the space before >>
    assert remote_has(pushing, git, sha)


def test_install_leaves_the_worktree_clean(pushing: Path, git: Git) -> None:
    install(pushing)

    assert git(pushing, "status", "--porcelain").stdout == ""


def test_install_points_core_hooks_path_at_its_own_directory(
    pushing: Path, git: Git
) -> None:
    install(pushing)

    configured = git(pushing, "config", "--local", "core.hooksPath").stdout.strip()
    assert Path(configured) == hooks_dir(pushing).resolve()
    assert os.access(hooks_dir(pushing) / "commit-msg", os.X_OK)
    assert os.access(hooks_dir(pushing) / "pre-push", os.X_OK)


def test_the_hooks_start_the_tool_without_prepush_ci_on_path(
    pushing: Path, git: Git
) -> None:
    scripts = str(Path(sys.executable).parent)
    path = os.pathsep.join(
        p for p in os.environ["PATH"].split(os.pathsep) if p != scripts
    )
    assert shutil.which("prepush-ci", path=path) is None
    install(pushing)

    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")
    git(
        pushing,
        "commit",
        "-q",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full", "PATH": path},
    )

    assert git(pushing, "log", "-1", "--format=%B").stdout.strip().endswith(TRAILER)


NO_EXECUTABLE_BIT = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no executable bit: git and sh run every hook file",
)


def write_hook(
    directory: Path, name: str, body: str, *, executable: bool = True
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755 if executable else 0o644)
    return path


def push_main(repo: Path, git: Git) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", "-q", "origin", "main", check=False)


def snapshot(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def test_an_existing_pre_push_hook_that_passes_runs_before_the_check(
    pushing: Path, git: Git, ran: Path, tmp_path: Path
) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-push", f"echo hook >> {ran.as_posix()}")
    install(pushing)
    commit_with_trailer(pushing, git)

    assert push_main(pushing, git).returncode == 0

    assert ran.read_text().split() == ["hook", "ran"]


def test_an_existing_pre_push_hook_that_fails_stops_the_push_before_the_check(
    pushing: Path, git: Git, ran: Path
) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-push", "exit 1")
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    result = push_main(pushing, git)

    assert result.returncode != 0
    assert not ran.exists()
    assert not remote_has(pushing, git, sha)


def test_an_existing_commit_msg_hook_runs_before_the_trailer_is_written(
    pushing: Path, git: Git
) -> None:
    write_hook(pushing / ".git" / "hooks", "commit-msg", 'echo Reviewed >> "$1"')
    install(pushing)

    commit_with_trailer(pushing, git)

    message = git(pushing, "log", "-1", "--format=%B").stdout
    assert "Reviewed" in message
    assert message.strip().endswith(TRAILER)


def test_an_existing_pre_push_hook_gets_the_arguments_and_the_ref_lines_of_the_push(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    seen = tmp_path / "seen.log"
    write_hook(
        pushing / ".git" / "hooks",
        "pre-push",
        f'echo "$1" > {seen.as_posix()}; cat >> {seen.as_posix()}',
    )
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    push_main(pushing, git)

    first, line = seen.read_text().splitlines()
    assert first == "origin"
    assert line.startswith(f"refs/heads/main {sha} refs/heads/main ")


@NO_EXECUTABLE_BIT
def test_an_existing_pre_push_hook_without_the_executable_bit_is_skipped_as_git_does(
    pushing: Path, git: Git, ran: Path
) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-push", "exit 1", executable=False)
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    assert push_main(pushing, git).returncode == 0

    assert ran.read_text().split() == ["ran"]  # cmd keeps the space before >>
    assert remote_has(pushing, git, sha)


def test_a_sample_hook_is_not_a_hook(pushing: Path, git: Git) -> None:
    hooks = pushing / ".git" / "hooks"
    write_hook(hooks, "pre-push.sample", "exit 1")
    write_hook(hooks, "commit-msg.sample", "exit 1")
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    assert push_main(pushing, git).returncode == 0

    assert remote_has(pushing, git, sha)
    assert sorted(p.name for p in hooks_dir(pushing).iterdir()) == [
        "commit-msg",
        "pre-push",
        "previous",
        "python",
    ]


def test_an_existing_pre_commit_hook_still_runs_after_install(
    pushing: Path, git: Git
) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-commit", "exit 1")
    install(pushing)
    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")

    result = git(pushing, "commit", "-q", "-m", "add x", check=False)

    assert result.returncode != 0


@NO_EXECUTABLE_BIT
def test_a_pre_commit_hook_without_the_executable_bit_does_not_fail_the_commit(
    pushing: Path, git: Git
) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-commit", "exit 1", executable=False)
    install(pushing)
    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")

    result = git(pushing, "commit", "-q", "-m", "add x", check=False)

    assert result.returncode == 0


def test_a_pre_commit_hook_deleted_after_install_does_not_fail_the_commit(
    pushing: Path, git: Git
) -> None:
    hook = write_hook(pushing / ".git" / "hooks", "pre-commit", "exit 1")
    install(pushing)
    hook.unlink()
    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")

    result = git(pushing, "commit", "-q", "-m", "add x", check=False)

    assert result.returncode == 0


def test_a_forwarded_hook_gets_the_arguments_git_passes(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    seen = tmp_path / "seen.log"
    write_hook(
        pushing / ".git" / "hooks", "post-checkout", f'echo "$#" > {seen.as_posix()}'
    )
    install(pushing)

    git(pushing, "checkout", "-q", "-b", "topic")

    assert seen.read_text().strip() == "3"


def test_an_existing_core_hooks_path_is_chained_and_left_untouched(
    pushing: Path, git: Git
) -> None:
    custom = pushing / "custom-hooks"
    write_hook(custom, "pre-push", "exit 1")
    git(pushing, "config", "core.hooksPath", "custom-hooks")
    before = snapshot(custom)
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    result = push_main(pushing, git)

    assert result.returncode != 0
    assert not remote_has(pushing, git, sha)
    assert snapshot(custom) == before


def test_the_hooks_of_the_common_directory_run_from_a_linked_worktree(
    pushing: Path, git: Git, tmp_path: Path, ran: Path
) -> None:
    refusals = tmp_path / "refusals.log"
    write_hook(
        pushing / ".git" / "hooks",
        "pre-push",
        f"echo refused >> {refusals.as_posix()}; exit 1",
    )
    linked = tmp_path / "linked"
    git(pushing, "worktree", "add", "-q", "-b", "other", str(linked))
    install(linked)
    from_main_sha = commit_with_trailer(pushing, git)
    from_linked_sha = commit_with_trailer(linked, git, "y")

    from_main = push_main(pushing, git)
    from_linked = git(linked, "push", "-q", "origin", "other", check=False)

    assert from_main.returncode != 0
    assert from_linked.returncode != 0
    assert refusals.read_text().split() == ["refused", "refused"]
    assert not ran.exists()
    remote = git(pushing, "ls-remote", "origin").stdout
    assert from_main_sha not in remote
    assert from_linked_sha not in remote


def test_an_existing_hook_survives_a_second_install(pushing: Path, git: Git) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-push", "exit 1")
    install(pushing)
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    result = push_main(pushing, git)

    assert result.returncode != 0
    assert not remote_has(pushing, git, sha)


def test_a_hooks_path_set_by_a_manager_after_install_becomes_the_previous_directory(
    pushing: Path, git: Git
) -> None:
    install(pushing)
    managed = pushing / "managed-hooks"
    write_hook(managed, "pre-push", "exit 1")
    git(pushing, "config", "core.hooksPath", "managed-hooks")
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    result = push_main(pushing, git)

    assert result.returncode != 0
    assert not remote_has(pushing, git, sha)
    configured = git(pushing, "config", "--local", "core.hooksPath").stdout.strip()
    assert Path(configured) == hooks_dir(pushing).resolve()


def test_install_works_when_the_previous_hooks_directory_does_not_exist(
    pushing: Path, git: Git
) -> None:
    shutil.rmtree(pushing / ".git" / "hooks")
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    assert push_main(pushing, git).returncode == 0

    assert remote_has(pushing, git, sha)


def mtimes(directory: Path) -> dict[str, int]:
    return {p.name: p.stat().st_mtime_ns for p in directory.iterdir()}


def test_the_first_install_says_installed(pushing: Path) -> None:
    result = install(pushing)

    assert result.returncode == 0
    assert result.stdout.startswith("installed")


def test_a_second_install_says_so_and_changes_nothing(pushing: Path, git: Git) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-commit", "exit 0")
    install(pushing)
    files = snapshot(hooks_dir(pushing))
    times = mtimes(hooks_dir(pushing))
    configured = git(pushing, "config", "--local", "core.hooksPath").stdout

    second = install(pushing)

    assert second.returncode == 0
    assert "already installed" in second.stdout
    assert snapshot(hooks_dir(pushing)) == files
    assert mtimes(hooks_dir(pushing)) == times
    assert git(pushing, "config", "--local", "core.hooksPath").stdout == configured


def test_a_hook_added_after_install_is_forwarded_by_the_next_install(
    pushing: Path, git: Git, tmp_path: Path
) -> None:
    seen = tmp_path / "merged.log"
    install(pushing)
    write_hook(
        pushing / ".git" / "hooks", "post-merge", f"echo merged > {seen.as_posix()}"
    )

    second = install(pushing)

    assert "updated" in second.stdout
    assert "already" not in second.stdout
    git(pushing, "checkout", "-q", "-b", "topic")
    (pushing / "y.txt").write_text("y")
    git(pushing, "add", "y.txt")
    git(pushing, "commit", "-q", "-m", "add y")
    git(pushing, "checkout", "-q", "main")
    git(pushing, "merge", "-q", "--no-ff", "-m", "merge topic", "topic")
    assert seen.read_text().strip() == "merged"


def test_a_hook_removed_after_install_leaves_no_forwarder_behind(
    pushing: Path,
) -> None:
    hook = write_hook(pushing / ".git" / "hooks", "post-merge", "exit 0")
    install(pushing)
    hook.unlink()

    second = install(pushing)

    assert "updated" in second.stdout
    assert not (hooks_dir(pushing) / "post-merge").exists()


def test_install_from_another_interpreter_updates_the_recorded_one(
    pushing: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    install(pushing)
    capsys.readouterr()
    other = pushing.parent / "other-python"
    monkeypatch.setattr(
        sys, "executable", str(other)
    )  # what a run by another interpreter sees

    assert install_command.run(pushing) == 0

    assert "updated" in capsys.readouterr().out
    assert (hooks_dir(pushing) / "python").read_text().strip() == other.as_posix()


def test_a_hooks_path_set_by_a_manager_is_reported_as_an_update(
    pushing: Path, git: Git
) -> None:
    install(pushing)
    write_hook(pushing / "managed-hooks", "pre-push", "exit 0")
    git(pushing, "config", "core.hooksPath", "managed-hooks")

    second = install(pushing)

    assert "updated" in second.stdout


def test_the_report_names_the_hooks_directory_and_the_previous_one(
    pushing: Path,
) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-push", "exit 0")

    result = install(pushing)

    assert hooks_dir(pushing).resolve().as_posix() in result.stdout
    assert (pushing / ".git" / "hooks").resolve().as_posix() in result.stdout


def test_the_report_names_no_previous_directory_when_there_is_nothing_to_chain(
    pushing: Path,
) -> None:
    result = install(pushing)

    assert "previous" not in result.stdout


def test_a_rerun_without_the_record_of_the_previous_directory_falls_back_to_git_hooks(
    pushing: Path, git: Git
) -> None:
    write_hook(pushing / ".git" / "hooks", "pre-push", "exit 1")
    install(pushing)
    (hooks_dir(pushing) / "previous").unlink()
    install(pushing)
    sha = commit_with_trailer(pushing, git)

    result = push_main(pushing, git)

    assert result.returncode != 0
    assert not remote_has(pushing, git, sha)


def test_install_says_so_when_git_cannot_be_started(
    pushing: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", "")

    assert install_command.run(pushing) == 1

    assert "cannot run git" in capsys.readouterr().err


def test_install_outside_a_git_repository_fails_and_says_so(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()

    result = install(outside, env={"GIT_CEILING_DIRECTORIES": str(tmp_path)})

    assert result.returncode == 1
    assert "no git repository" in result.stderr


def vanish_interpreter(repo: Path) -> None:
    (hooks_dir(repo) / "python").write_text("/nonexistent/venv/bin/python\n")


def test_a_push_is_refused_naming_install_when_the_interpreter_has_vanished(
    pushing: Path, git: Git, ran: Path
) -> None:
    install(pushing)
    sha = commit_with_trailer(pushing, git)
    vanish_interpreter(pushing)

    result = push_main(pushing, git)

    assert result.returncode != 0
    assert "prepush-ci install" in result.stderr
    assert not ran.exists()
    assert not remote_has(pushing, git, sha)


def test_a_commit_goes_through_without_the_trailer_when_the_interpreter_has_vanished(
    pushing: Path, git: Git
) -> None:
    install(pushing)
    vanish_interpreter(pushing)
    (pushing / "x.txt").write_text("x")
    git(pushing, "add", "x.txt")

    result = git(
        pushing, "commit", "-m", "add x", env={"PREPUSH_CI": "full"}, check=False
    )

    assert result.returncode == 0
    assert "prepush-ci install" in result.stderr
    assert TRAILER not in git(pushing, "log", "-1", "--format=%B").stdout
