"""`prepush-ci hook commit-msg <file>`: write the trailer that demands the full check."""

import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from prepush_ci.core.commit_msg import (
    InvalidMode,
    Mode,
    UnsupportedCommentChar,
    editor_was_used,
    is_blank_message,
    is_template_untouched,
    parse_mode,
    require_known_comment_setting,
    resolve_cleanup,
)
from prepush_ci.core.config import ConfigError
from prepush_ci.repo_config import load_repository_config

ENV_VAR = "PREPUSH_CI"


def run(message_file: Path, env: Mapping[str, str], cwd: Path) -> int:
    """Run the hook; return the exit code (non-zero makes git abort the commit)."""
    try:
        mode = parse_mode(env.get(ENV_VAR))
    except InvalidMode as error:
        print(f"prepush-ci: {error}", file=sys.stderr)
        return 1
    if mode is Mode.OFF:
        return 0
    try:
        config = load_repository_config(cwd)
    except ConfigError as error:
        for problem in error.problems:
            print(f"prepush-ci: {problem}", file=sys.stderr)
        return 1
    try:
        require_known_comment_setting(_comment_setting(cwd))
    except UnsupportedCommentChar as error:
        print(f"prepush-ci: {error}", file=sys.stderr)
        return 1
    # Only classified here, never written back: git rewrites the file with its bytes as they are.
    # `surrogateescape` keeps every byte distinct, so a text compares equal to what git prints.
    text = message_file.read_text(encoding="utf-8", errors="surrogateescape")
    editor_used = editor_was_used(env.get("GIT_EDITOR"), text)
    cleanup = resolve_cleanup(_git_config(cwd, "commit.cleanup"), editor_used)
    comment = _comment_prefix(cwd)
    if is_blank_message(text, cleanup, comment):
        return 0
    template = (
        _commit_template(cwd) if editor_used else None
    )  # git checks only after an editor
    if template is not None and is_template_untouched(text, template, cleanup, comment):
        return 0
    subprocess.run(
        [
            "git",
            "interpret-trailers",
            "--in-place",
            "--no-divider",
            "--where",
            "start",
            "--if-exists",
            "doNothing",
            "--trailer",
            config.trailer.line(),
            str(message_file),
        ],
        check=True,
    )
    return 0


def _comment_setting(cwd: Path) -> str | None:
    """What the repository configures as comment prefix (`commentString` is newer git)."""
    for name in ("core.commentString", "core.commentChar"):
        value = _git_config(cwd, name)
        if value is not None:
            return value
    return None


def _git_config(cwd: Path, name: str, *, as_path: bool = False) -> str | None:
    result = subprocess.run(
        ["git", "config", "--get", *(["--type=path"] if as_path else []), name],
        cwd=cwd,
        capture_output=True,
        text=True,
        errors="surrogateescape",
        check=False,
    )
    return result.stdout.removesuffix("\n") if result.returncode == 0 else None


def _comment_prefix(cwd: Path) -> str:
    """The comment prefix of the git that runs the hook, whichever settings it honours."""
    result = subprocess.run(
        ["git", "stripspace", "--comment-lines"],
        cwd=cwd,
        input="x\n",
        capture_output=True,
        encoding="utf-8",
        errors="surrogateescape",
        check=True,
    )
    return result.stdout.removesuffix(" x\n")


def _commit_template(cwd: Path) -> str | None:
    """The text of `commit.template`, or None when unset or unreadable (git reports that itself)."""
    path = _git_config(cwd, "commit.template", as_path=True)
    if path is None:
        return None
    try:
        return (cwd / path).read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return None
