"""Read a commit through git: the shared I/O of the commands that decide about a commit."""

import subprocess
from pathlib import Path

from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.config_source import (
    PREPUSH_CI_FILE,
    PYPROJECT_FILE,
    ConfigMissing,
    load_config,
)
from prepush_ci.core.pre_push import dirty_paths, hidden_paths


class GitError(Exception):
    """git cannot tell what a command needs to know; the message says what and why."""


def git(cwd: Path, *args: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )


def git_bytes(cwd: Path, *args: str, stdin: bytes | None = None) -> bytes:
    """Run git and return its standard output as bytes; a failure raises `GitError`."""
    result = subprocess.run(
        ["git", *args], cwd=cwd, input=stdin, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise GitError(f"`git {args[0]}` failed: {detail}")
    return result.stdout


def dirty(cwd: Path) -> list[str]:
    """Staged, unstaged and untracked paths (not the ignored ones) of the worktree."""
    return dirty_paths(
        _listing(
            cwd,
            "the worktree status",
            "status",
            "--porcelain",
            "-z",
            "--untracked-files=all",
        )
    )


def hidden(cwd: Path) -> list[str]:
    """Paths whose changes `git status` cannot see (assume-unchanged, skip-worktree)."""
    return hidden_paths(_listing(cwd, "the index flags", "ls-files", "-v", "-z"))


def _listing(cwd: Path, what: str, *args: str) -> str:
    result = git(cwd, *args)
    if result.returncode != 0:
        raise GitError(f"{what} could not be read: {result.stderr.strip()}")
    return result.stdout


def trailers(sha: str, cwd: Path) -> str:
    """`git log --format=%(trailers:only,unfold)` of the commit: one `Key: value` per line."""
    result = git(cwd, "log", "-1", "--format=%(trailers:only,unfold)", sha, "--")
    if result.returncode != 0:
        raise GitError(f"cannot read the message of {sha}: {result.stderr.strip()}")
    return result.stdout


def committed_config(sha: str, cwd: Path) -> Config | None:
    """The config committed in `sha`; None when the commit has none."""
    try:
        return load_config(
            _file(sha, PREPUSH_CI_FILE, cwd), _file(sha, PYPROJECT_FILE, cwd)
        )
    except ConfigMissing:
        return None
    except ConfigError as error:
        raise ConfigError(
            [f"config of {sha[:12]}: {problem}" for problem in error.problems]
        ) from error


def _file(sha: str, name: str, cwd: Path) -> str | None:
    listing = git(cwd, "ls-tree", "--full-tree", "--name-only", sha, "--", name)
    if listing.returncode != 0:
        raise GitError(f"cannot read {name} of {sha}: {listing.stderr.strip()}")
    if not listing.stdout.strip():
        return None
    blob = git(cwd, "cat-file", "blob", f"{sha}:{name}")
    if blob.returncode != 0:
        raise GitError(f"cannot read {name} of {sha}: {blob.stderr.strip()}")
    return blob.stdout
