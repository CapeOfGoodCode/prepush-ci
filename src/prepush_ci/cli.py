"""Command-line entry point."""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from prepush_ci import (
    app_ruleset_command,
    app_setup_command,
    commit_msg_hook,
    doctor_command,
    init_command,
    install_command,
    land_command,
    post_push_hook,
    pre_push_hook,
    report_command,
    run_command,
    skill_command,
    strip_command,
    text_io,
    verify_command,
)
from prepush_ci.core.app_setup import (
    DEFAULT_TIMEOUT,
    parse_app_name,
    parse_timeout,
)
from prepush_ci.core.doctor import MODES
from prepush_ci.core.hook_managers import CHOICES
from prepush_ci.core.init import CI_CHOICES, ConfigFlags
from prepush_ci.core.land import parse_number
from prepush_ci.core.report import (
    STARTED,
    Malformed,
    markdown_name_problem,
    parse_duration,
    parse_name,
    parse_tool,
)
from prepush_ci.core.ruleset import ADMIN_ACTOR, app_actor, parse_app_id
from prepush_ci.version_line import PrintVersionLine

T = TypeVar("T")


def _parsed(parse: Callable[[str], T]) -> Callable[[str], T]:
    """`parse` as an argparse type: a `Malformed` value is a usage error that names its flag."""

    def convert(text: str) -> T:
        try:
            return parse(text)
        except Malformed as error:
            raise argparse.ArgumentTypeError(str(error)) from error

    return convert


# The flags that belong to a result, with the attribute each fills: `--start` takes none of them.
_RESULT_FLAGS = (
    ("--result", "result"),
    ("--junit", "junit"),
    ("--coverage", "coverage"),
    ("--ruff", "ruff"),
    ("--mypy", "mypy"),
    ("--duration", "duration"),
    ("--tool", "tool"),
)


def _report_problem(args: argparse.Namespace) -> str | None:
    """Why the flags of `report` do not go together, or None."""
    if args.markdown:
        if args.start:
            return "--markdown cannot be combined with --start"
        if args.name is not None and (problem := markdown_name_problem(args.name)):
            return problem
    given = [flag for flag, name in _RESULT_FLAGS if getattr(args, name) is not None]
    if not args.start:
        return (
            None if args.result is not None else "--result is required without --start"
        )
    if given:
        return f"--start cannot be combined with {', '.join(given)}"
    return None


def main(argv: list[str] | None = None) -> int:
    text_io.configure_streams()
    args_in = text_io.arguments(sys.argv[1:]) if argv is None else argv
    env = text_io.environment()
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
        "--version",
        action=PrintVersionLine,
        help="show program's version number and exit",
    )
    commands = parser.add_subparsers(dest="command")
    hook = commands.add_parser("hook", help="entry points that git hooks call")
    hooks = hook.add_subparsers(dest="hook", required=True)
    commands.add_parser(
        "run",
        help="run the preflight and the check on HEAD, as the pre-push hook would",
    )
    install = commands.add_parser(
        "install", help="point git at hooks that run this tool"
    )
    install.add_argument(
        "--hooks",
        choices=CHOICES,
        help="whose hooks to install (default: the hook manager found, else native)",
    )
    init = commands.add_parser(
        "init", help="set a repository up: config, hooks, SessionStart hook, CI gate"
    )
    init.add_argument(
        "--non-interactive", action="store_true", help="ask nothing; take the flags"
    )
    init.add_argument("--check", help="the command that runs your full CI check")
    init.add_argument("--preflight", help="a command to run before the check")
    init.add_argument(
        "--require-env",
        action="append",
        help="an environment variable the check needs (repeatable)",
    )
    init.add_argument(
        "--require-up-to-date",
        help="a ref the branch must contain, or true or false",
    )
    init.add_argument("--default-branch", help="the repository's default branch")
    init.add_argument(
        "--hooks",
        choices=(*CHOICES, "none"),
        help="whose hooks to install, or none (default: the hook manager found, else native)",
    )
    init.add_argument(
        "--no-session-hook",
        action="store_true",
        help="do not write the Claude Code SessionStart hook",
    )
    init.add_argument(
        "--ci",
        choices=CI_CHOICES,
        help="whose CI gate snippet to show (default: detected from the repository)",
    )
    init.add_argument(
        "--ci-gate-file",
        help="write the CI gate snippet to this file instead of printing it",
    )
    diagnose = commands.add_parser(
        "doctor", help="check that the hooks and the config will do their job"
    )
    diagnose.add_argument(
        "--hooks",
        choices=(*CHOICES, "none"),
        help="whose hooks to check, or none (default: the hook manager found, else native)",
    )
    diagnose.add_argument(
        "--mode",
        choices=MODES,
        help="also require PREPUSH_CI to have this value (unset: not set or empty)",
    )
    commit_msg = hooks.add_parser(
        "commit-msg", help="write the trailer when PREPUSH_CI=full"
    )
    commit_msg.add_argument(
        "file", type=text_io.to_path, help="the commit message file git passes"
    )
    pre_push = hooks.add_parser(
        "pre-push",
        help="refuse to push a commit with the trailer unless the check passes",
    )
    pre_push.add_argument(
        "git_args", nargs="*", help="the remote name and url git passes"
    )
    hooks.add_parser(
        "post-push",
        help="after a push of a checked commit, put the result on its pull request "
        "(reads a Claude Code PostToolUse payload on standard input)",
    )
    land = commands.add_parser(
        "land",
        help="push the head of a checked pull request to the default branch of origin",
    )
    land.add_argument(
        "number",
        type=_parsed(parse_number),
        help="the number of the pull request, read as refs/pull/<number>/head of origin",
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
    skill = commands.add_parser(
        "skill", help="print the setup skill of this version for an agent to follow"
    )
    skill.add_argument(
        "--write",
        action="store_true",
        help="write it to .claude/skills/prepush-ci-setup/SKILL.md of the repository",
    )
    report = commands.add_parser(
        "report",
        help="post the result of a run of the check for a commit, as a check run or a status",
    )
    report.add_argument(
        "--result",
        choices=("passed", "failed"),
        help="how the run ended (or --start)",
    )
    report.add_argument(
        "--start",
        action="store_true",
        help="show the check as in progress instead; --result completes it later",
    )
    report.add_argument(
        "--markdown",
        action="store_true",
        help="print the summary as Markdown instead of posting it; needs no token, app or network",
    )
    report.add_argument(
        "--tree",
        required=True,
        help="the full hash of the tree the check ran on; refused when it is not the commit's",
    )
    report.add_argument(
        "--commit", default="HEAD", help="the commit to report on (default: HEAD)"
    )
    report.add_argument(
        "--name",
        type=_parsed(parse_name),
        help="the name of the check run, or the context of the status",
    )
    report.add_argument(
        "--duration",
        type=_parsed(parse_duration),
        help="how long the run took, in whole seconds",
    )
    report.add_argument(
        "--tool",
        action="append",
        type=_parsed(parse_tool),
        help="a tool the run used, as NAME=VERSION (repeatable)",
    )
    report.add_argument(
        "--junit",
        action="append",
        help="a JUnit XML file of the run (repeatable); its test cases are counted",
    )
    report.add_argument(
        "--coverage", help="the coverage.json of coverage.py; its total is shown"
    )
    report.add_argument(
        "--ruff",
        action="append",
        help="the output of `ruff check --output-format json` (repeatable); its errors are annotated",
    )
    report.add_argument(
        "--mypy",
        action="append",
        help="the output of mypy (repeatable); its errors are annotated",
    )
    app = commands.add_parser(
        "app", help="the GitHub App that report posts check runs as"
    )
    apps = app.add_subparsers(dest="app_command", required=True)
    setup = apps.add_parser(
        "setup",
        help="create the app with one click in the browser and save its key outside the repository",
    )
    setup.add_argument(
        "--org",
        type=_parsed(parse_name),
        help="the organization that owns the app (default: your account)",
    )
    setup.add_argument(
        "--name",
        type=_parsed(parse_app_name),
        help="the name of the app (default: prepush-ci (<owner of origin>)); 34 characters at most",
    )
    setup.add_argument(
        "--timeout",
        type=_parsed(parse_timeout),
        default=DEFAULT_TIMEOUT,
        help="seconds to wait for GitHub's answer (default: %(default)s)",
    )
    ruleset = apps.add_parser(
        "ruleset",
        help="create the ruleset that lets only one actor move the default branch",
        description="Create the ruleset `prepush-ci landing` on the default branch: only the "
        "actor you name may update it (no pull request is required), and it cannot be deleted "
        "or rewritten. It uses the token of GITHUB_TOKEN or GH_TOKEN, which needs "
        "administration rights on the repository. A private repository needs a paid plan for "
        "rulesets.",
    )
    # Not `required`: argparse would then report the missing flag before an unknown one.
    who = ruleset.add_mutually_exclusive_group()
    who.add_argument(
        "--admin",
        action="store_true",
        help="the repository-admin role may bypass the ruleset (for landing by hand)",
    )
    who.add_argument(
        "--app",
        type=_parsed(parse_app_id),
        metavar="ID",
        help="the app with this id may bypass the ruleset (for the landing workflow); "
        "it must be installed on the repository",
    )
    args = parser.parse_args(args_in)
    if args.command == "app" and args.app_command == "ruleset":
        if not args.admin and args.app is None:
            ruleset.error("one of the arguments --admin --app is required")
        return app_ruleset_command.run(
            ADMIN_ACTOR if args.admin else app_actor(args.app), env, Path.cwd()
        )
    if args.command == "app":
        return app_setup_command.run(
            app_setup_command.Options(args.org, args.name, args.timeout),
            env,
            Path.cwd(),
        )
    if args.command == "report":
        problem = _report_problem(args)
        if problem is not None:
            report.error(problem)
        return report_command.run(
            report_command.Options(
                STARTED if args.start else args.result,
                args.tree,
                args.commit,
                args.name,
                args.duration,
                tuple(args.tool or ()),
                tuple(args.junit or ()),
                args.coverage,
                tuple(args.ruff or ()),
                tuple(args.mypy or ()),
                args.markdown,
            ),
            env,
            Path.cwd(),
        )
    if args.command == "skill":
        return skill_command.run(args.write, Path.cwd())
    if args.command == "land":
        return land_command.run(args.number, env, Path.cwd())
    if args.command == "strip":
        return strip_command.run(args.base, Path.cwd())
    if args.command == "run":
        return run_command.run(env, Path.cwd())
    if args.command == "init":
        flags = ConfigFlags(
            check=args.check,
            preflight=args.preflight,
            require_env=None if args.require_env is None else tuple(args.require_env),
            require_up_to_date=args.require_up_to_date,
            default_branch=args.default_branch,
        )
        return init_command.run(
            init_command.Options(
                flags,
                args.non_interactive,
                args.hooks,
                not args.no_session_hook,
                args.ci,
                args.ci_gate_file,
            ),
            Path.cwd(),
        )
    if args.command == "doctor":
        return doctor_command.run(Path.cwd(), env, args.hooks, args.mode)
    if args.command == "install":
        return install_command.run(Path.cwd(), args.hooks)
    if args.command == "hook" and args.hook == "pre-push":
        return pre_push_hook.run(text_io.stdin_text, env, Path.cwd(), args.git_args)
    if args.command == "hook" and args.hook == "post-push":
        return post_push_hook.run(text_io.stdin_text, env, Path.cwd())
    if args.command == "hook":
        return commit_msg_hook.run(args.file, env, Path.cwd())
    parser.print_help()
    return 0
