"""Command-line entry point."""

import argparse
import os
import sys
from importlib.metadata import version
from pathlib import Path

from prepush_ci import commit_msg_hook, pre_push_hook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prepush-ci")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('prepush-ci')}"
    )
    commands = parser.add_subparsers(dest="command")
    hook = commands.add_parser("hook", help="entry points that git hooks call")
    hooks = hook.add_subparsers(dest="hook", required=True)
    commit_msg = hooks.add_parser(
        "commit-msg", help="write the trailer when PREPUSH_CI=full"
    )
    commit_msg.add_argument(
        "file", type=Path, help="the commit message file git passes"
    )
    pre_push = hooks.add_parser(
        "pre-push",
        help="refuse to push a commit with the trailer unless the check passes",
    )
    pre_push.add_argument(
        "git_args", nargs="*", help="the remote name and url git passes (unused)"
    )
    args = parser.parse_args(argv)
    if args.command == "hook" and args.hook == "pre-push":
        return pre_push_hook.run(sys.stdin, os.environ, Path.cwd())
    if args.command == "hook":
        return commit_msg_hook.run(args.file, os.environ, Path.cwd())
    parser.print_help()
    return 0
