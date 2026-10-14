"""Every command in a repository whose directory name ends in a space: git prints the worktree root
with that space, and the tool must read it back as the same directory."""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows does not keep a trailing space in a name"
)

TRAILER = "Prepush-CI: full"
TOUCH = "touch ran.log"


def prepush(
    cwd: Path, *args: str, env: dict[str, str] | None = None, stdin: str | None = None
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci <args>` in `cwd` without any `PREPUSH_CI` the developer has set."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", *args],
        cwd=cwd,
        env={**inherited, **(env or {})},
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def spaced(tmp_path: Path, git: Git) -> Path:
    """A repository on `main` whose directory name ends in a space, with a bare `origin`."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    where = tmp_path / "work "
    where.mkdir()
    git(where, "init", "-q")
    git(where, "symbolic-ref", "HEAD", "refs/heads/main")
    git(where, "config", "user.name", "Test")
    git(where, "config", "user.email", "test@example.com")
    git(where, "config", "commit.gpgsign", "false")
    git(where, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return where


def initialized(where: Path, git: Git) -> None:
    """Set the repository up the way a user would and commit that; the check leaves `ran.log` in
    the worktree."""
    result = prepush(
        where,
        "init",
        "--non-interactive",
        "--check",
        TOUCH,
        "--default-branch",
        "main",
        "--hooks",
        "native",
        "--require-up-to-date",
        "false",
    )
    assert result.returncode == 0, result.stderr
    git(where, "add", ".")
    git(where, "commit", "-q", "-m", "setup")


def no_directory_beside(where: Path) -> None:
    """The directory the strip of a trailing space would name must not have come into being."""
    assert not (where.parent / where.name.strip()).exists()


def test_init_in_a_directory_whose_name_ends_with_a_space_sets_up_that_directory(
    spaced: Path,
) -> None:
    result = prepush(
        spaced,
        "init",
        "--non-interactive",
        "--check",
        TOUCH,
        "--default-branch",
        "main",
        "--hooks",
        "native",
    )

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert (spaced / ".prepush-ci.toml").is_file()
    assert (spaced / ".git" / "prepush-ci" / "hooks" / "pre-push").is_file()
    no_directory_beside(spaced)


def test_install_in_a_directory_whose_name_ends_with_a_space_installs_there(
    spaced: Path,
    printed: Callable[[str], str],
) -> None:
    result = prepush(spaced, "install", "--hooks", "native")

    assert result.returncode == 0, result.stderr
    assert (spaced / ".git" / "prepush-ci" / "hooks" / "commit-msg").is_file()
    assert printed(str(spaced)) + "/.git" in result.stdout
    no_directory_beside(spaced)


def test_doctor_in_a_directory_whose_name_ends_with_a_space_finds_the_valid_config(
    spaced: Path, git: Git
) -> None:
    initialized(spaced, git)

    result = prepush(spaced, "doctor")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "not valid" not in result.stdout + result.stderr


def test_the_commit_msg_hook_in_a_directory_whose_name_ends_with_a_space_writes_the_trailer(
    spaced: Path, git: Git
) -> None:
    initialized(spaced, git)

    git(
        spaced,
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "work",
        env={"PREPUSH_CI": "full"},
    )

    message = git(spaced, "log", "-1", "--format=%B").stdout
    assert TRAILER in message


def test_the_pre_push_hook_in_a_directory_whose_name_ends_with_a_space_runs_the_check_there(
    spaced: Path, git: Git
) -> None:
    initialized(spaced, git)
    git(
        spaced,
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "work",
        env={"PREPUSH_CI": "full"},
    )

    pushed = git(spaced, "push", "origin", "main", check=False)

    assert pushed.returncode == 0, pushed.stderr
    assert (spaced / "ran.log").is_file()
    no_directory_beside(spaced)


def test_run_in_a_directory_whose_name_ends_with_a_space_runs_the_check_there(
    spaced: Path, git: Git
) -> None:
    initialized(spaced, git)

    result = prepush(spaced, "run")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (spaced / "ran.log").is_file()


def test_strip_in_a_directory_whose_name_ends_with_a_space_removes_the_trailer(
    spaced: Path, git: Git
) -> None:
    initialized(spaced, git)
    base = git(spaced, "rev-parse", "HEAD").stdout.strip()
    git(
        spaced,
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "work",
        env={"PREPUSH_CI": "full"},
    )

    result = prepush(spaced, "strip", base)

    assert result.returncode == 0, result.stderr
    assert TRAILER not in git(spaced, "log", "-1", "--format=%B").stdout


def test_install_in_a_directory_whose_name_ends_with_a_space_finds_the_hook_manager_there(
    spaced: Path,
) -> None:
    (spaced / "lefthook.yml").write_text(
        "pre-push:\n  commands:\n    lint:\n      run: true\n"
    )

    result = prepush(spaced, "install")

    assert result.returncode == 0, result.stderr
    assert "prepush-ci" in (spaced / "lefthook.yml").read_text()


def test_install_in_a_directory_whose_name_ends_with_a_space_keeps_the_hooks_core_hooks_path_names(
    spaced: Path, git: Git, printed: Callable[[str], str]
) -> None:
    kept = spaced / ".githooks"
    kept.mkdir()
    (kept / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    (kept / "pre-push").chmod(0o755)
    git(spaced, "config", "core.hooksPath", ".githooks")

    result = prepush(spaced, "install", "--hooks", "native")

    assert result.returncode == 0, result.stderr
    assert f"hooks kept from: {printed(str(kept))}" in result.stdout


# --- Paths git prints that end in a space, though the worktree root does not -------------------


def submodule(tmp_path: Path, git: Git) -> Path:
    """A submodule at the path `sub `, whose git directory `.git/modules/sub ` ends in a space as
    well; returns its worktree."""
    library = tmp_path / "library"
    library.mkdir()
    git(library, "init", "-q")
    git(library, "symbolic-ref", "HEAD", "refs/heads/main")
    git(library, "config", "user.name", "Test")
    git(library, "config", "user.email", "test@example.com")
    git(library, "commit", "--allow-empty", "-q", "-m", "library")
    outer = tmp_path / "super"
    outer.mkdir()
    git(outer, "init", "-q")
    git(
        outer,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(library),
        "sub ",
    )
    return outer / "sub "


def no_modules_directory_beside(modules: Path) -> None:
    assert not (modules / "sub").exists()


def test_install_in_a_submodule_whose_path_ends_with_a_space_installs_into_its_git_directory(
    tmp_path: Path, git: Git
) -> None:
    where = submodule(tmp_path, git)
    modules = tmp_path / "super" / ".git" / "modules"

    result = prepush(where, "install", "--hooks", "native")

    assert result.returncode == 0, result.stderr
    assert (modules / "sub " / "prepush-ci" / "hooks" / "commit-msg").is_file()
    no_modules_directory_beside(modules)


def test_doctor_in_a_submodule_whose_path_ends_with_a_space_finds_the_installed_hooks(
    tmp_path: Path, git: Git
) -> None:
    where = submodule(tmp_path, git)
    prepush(where, "install", "--hooks", "native")

    result = prepush(where, "doctor")

    assert "ok commit-msg" in result.stdout, result.stdout + result.stderr
    assert "ok pre-push" in result.stdout, result.stdout + result.stderr


def test_install_in_a_repository_whose_git_directory_ends_with_a_space_installs_into_it(
    spaced: Path, tmp_path: Path, git: Git
) -> None:
    store = tmp_path / "store "
    shutil.move(spaced / ".git", store)
    (spaced / ".git").write_text(f"gitdir: {store}\n")

    result = prepush(spaced, "install", "--hooks", "native")

    assert result.returncode == 0, result.stderr
    assert (store / "prepush-ci" / "hooks" / "commit-msg").is_file()
    assert not (tmp_path / "store").exists()


def test_install_keeps_the_hooks_of_a_core_hooks_path_that_ends_with_a_space(
    spaced: Path, git: Git, printed: Callable[[str], str]
) -> None:
    kept = spaced / "hooks "
    kept.mkdir()
    (kept / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    (kept / "pre-push").chmod(0o755)
    git(spaced, "config", "core.hooksPath", "hooks ")

    result = prepush(spaced, "install", "--hooks", "native")

    assert result.returncode == 0, result.stderr
    assert f"hooks kept from: {printed(str(kept))}" in result.stdout


def test_install_again_keeps_the_hooks_of_a_core_hooks_path_that_ends_with_a_space(
    spaced: Path, git: Git, printed: Callable[[str], str]
) -> None:
    kept = spaced / "hooks "
    kept.mkdir()
    (kept / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    (kept / "pre-push").chmod(0o755)
    git(spaced, "config", "core.hooksPath", "hooks ")
    prepush(spaced, "install", "--hooks", "native")

    result = prepush(spaced, "install", "--hooks", "native")

    assert result.returncode == 0, result.stderr
    assert f"hooks kept from: {printed(str(kept))}" in result.stdout


def test_doctor_reads_a_core_hooks_path_that_ends_with_a_space_as_it_is_configured(
    spaced: Path, git: Git
) -> None:
    (spaced / "hooks ").mkdir()
    git(spaced, "config", "core.hooksPath", "hooks ")

    result = prepush(spaced, "doctor")

    assert "core.hooksPath is hooks ," in result.stdout, result.stdout + result.stderr


def test_install_refusing_a_hook_manager_in_a_git_directory_that_ends_with_a_space_loses_no_hooks(
    spaced: Path, tmp_path: Path, git: Git
) -> None:
    store = tmp_path / "store "
    shutil.move(spaced / ".git", store)
    (spaced / ".git").write_text(f"gitdir: {store}\n")
    (store / "hooks").mkdir(exist_ok=True)
    (store / "hooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    (store / "hooks" / "pre-push").chmod(0o755)
    prepush(spaced, "install", "--hooks", "native")
    (spaced / "lefthook.yml").write_text(
        "pre-push:\n  commands:\n    lint:\n      run: true\n"
    )

    result = prepush(spaced, "install", "--hooks", "lefthook")

    assert result.returncode != 0
    assert "core.hooksPath still points" in result.stderr
    assert "will no longer run" not in result.stderr


def test_init_after_install_names_the_pre_push_hook_it_kept_in_a_git_directory_that_ends_with_a_space(
    spaced: Path, tmp_path: Path, printed: Callable[[str], str]
) -> None:
    store = tmp_path / "store "
    shutil.move(spaced / ".git", store)
    (spaced / ".git").write_text(f"gitdir: {store}\n")
    (store / "hooks").mkdir(exist_ok=True)
    (store / "hooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    (store / "hooks" / "pre-push").chmod(0o755)
    prepush(spaced, "install", "--hooks", "native")

    result = prepush(
        spaced,
        "init",
        "--check",
        TOUCH,
        "--default-branch",
        "main",
        "--require-up-to-date",
        "false",
        stdin="\n\nnative\n\n",
    )

    assert result.returncode == 0, result.stderr
    assert (
        f"the pre-push hook {printed(str(store / 'hooks' / 'pre-push'))}"
        in result.stdout
    )
