"""Command-line entry point."""

import argparse
import os
import sys
from importlib.metadata import version
from pathlib import Path

from prepush_ci import (
    commit_msg_hook,
    install_command,
    pre_push_hook,
    run_command,
    strip_command,
    verify_command,
)


def main(argv: list[str] | None = None) -> int:
    args_in = sys.argv[1:] if argv is None else argv
    if args_in[:1] == ["--"]:
        args_in = args_in[
            1:
        ]  # `prepush-ci -- verify "$SHA"` must reach the route below
    if args_in[:1] == ["verify"]:
        # Before argparse: its usage errors exit 2 and `--help` exits 0, but a CI gate must only
        # ever see 0 (verified) or 1.
        return verify_command.run(args_in[1:], Path.cwd())
    parser = argparse.ArgumentParser(
        prog="prepush-ci",
        epilog="also: verify <sha>  exit 0 when a commit carries the trailer and was not "
        "made by a server",  # not a subparser: argparse could never be allowed to answer for it
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('prepush-ci')}"
    )
    commands = parser.add_subparsers(dest="command")
    hook = commands.add_parser("hook", help="entry points that git hooks call")
    hooks = hook.add_subparsers(dest="hook", required=True)
    commands.add_parser(
        "run",
        help="run the preflight and the check on HEAD, as the pre-push hook would",
    )
    commands.add_parser("install", help="point git at hooks that run this tool")
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
    strip = commands.add_parser(
        "strip",
        help="remove the trailer from the commits since <base>, so a push needs no check",
    )
    strip.add_argument(
        "base",
        nargs="*",
        help="the commit before yours (default: the merge base with the default branch)",
    )
    args = parser.parse_args(args_in)
    if args.command == "strip":
        return strip_command.run(args.base, Path.cwd())
    if args.command == "run":
        return run_command.run(os.environ, Path.cwd())
    if args.command == "install":
        return install_command.run(Path.cwd())
    if args.command == "hook" and args.hook == "pre-push":
        return pre_push_hook.run(sys.stdin, os.environ, Path.cwd())
    if args.command == "hook":
        return commit_msg_hook.run(args.file, os.environ, Path.cwd())
    parser.print_help()
    return 0
