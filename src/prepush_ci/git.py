"""Read a commit through git: the shared I/O of the commands that decide about a commit."""

from collections.abc import Mapping
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.config_source import (
    PREPUSH_CI_FILE,
    PYPROJECT_FILE,
    ConfigMissing,
    load_config,
)
from prepush_ci.core.pre_push import dirty_paths, hidden_paths
from prepush_ci.text_io import Completed


class GitError(Exception):
    """git cannot tell what a command needs to know; the message says what and why."""


def git(cwd: Path, *args: str, env: Mapping[str, str] | None = None) -> Completed:
    """Run git; `env` replaces the environment (None: inherit it). Arguments and output are the
    tool's text, so a path git prints is one `text_io.to_path` turns into a path the process can
    open again, whatever the locale is."""
    return text_io.run(["git", *args], cwd=cwd, env=env)


def answer(result: Completed) -> str:
    """The one-line answer of git: only its final newline goes, for a path may end in a space
    (`--show-toplevel` of a directory called `work `, `--git-common-dir` of a submodule at
    `sub `, a `core.hooksPath` of `hooks `), which `strip()` would take with it."""
    return result.stdout.removesuffix("\n")


def git_bytes(cwd: Path, *args: str, stdin: bytes | None = None) -> bytes:
    """Run git and return its standard output as bytes; a failure raises `GitError`."""
    result = text_io.run_bytes(["git", *args], cwd=cwd, stdin=stdin)
    if result.returncode != 0:
        detail = text_io.decode(result.stderr).strip()
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


def tracked_listings(cwd: Path) -> tuple[str, str]:
    """What `HEAD` and the index list, as `git ls-tree -r -z HEAD` and `git ls-files -s -z` print
    it; a listing that cannot be read is an error, for a path missing from it would look free."""
    return (
        _listing(cwd, "the files of HEAD", "ls-tree", "-r", "-z", "HEAD"),
        _listing(cwd, "the files of the index", "ls-files", "-s", "-z"),
    )


def tree_files(cwd: Path, tree: str) -> frozenset[str]:
    """The paths of the files in a tree; empty when git cannot list it."""
    result = git(cwd, "ls-tree", "-r", "-z", "--name-only", tree)
    return frozenset(result.stdout.split("\0")) - {""}


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
        dedicated = _file(sha, PREPUSH_CI_FILE, cwd)
        pyproject = None if dedicated is not None else _file(sha, PYPROJECT_FILE, cwd)
        return load_config(dedicated, pyproject)
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
    blob = text_io.run_bytes(["git", "cat-file", "blob", f"{sha}:{name}"], cwd=cwd)
    if blob.returncode != 0:
        detail = text_io.decode(blob.stderr).strip()
        raise GitError(f"cannot read {name} of {sha}: {detail}")
    try:
        return text_io.decode_utf8(blob.stdout, name)
    except text_io.NotUtf8 as error:
        raise ConfigError([str(error)]) from error


def resolve_commit(argument: str, cwd: Path) -> str | None:
    """The full sha of the commit `argument` names, or None when it names none."""
    if argument.startswith(
        "-"
    ):  # no revision starts with a dash; never hand an option to git
        return None
    result = git(cwd, "rev-parse", "--verify", "--quiet", f"{argument}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None
