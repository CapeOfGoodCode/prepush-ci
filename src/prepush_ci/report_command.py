"""`prepush-ci report`: post the result of a run of the check as a check run or a commit status."""

import platform
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from prepush_ci import github_api, signing, text_io
from prepush_ci.core import report
from prepush_ci.core.config import ConfigError
from prepush_ci.core.report import (
    AppCredentials,
    Counts,
    Facts,
    Failure,
    ReportError,
    Target,
    Tool,
)
from prepush_ci.git import (
    GitError,
    answer,
    committed_config,
    git,
    git_bytes,
    resolve_commit,
)


@dataclass(frozen=True)
class Options:
    result: str
    tree: str
    commit: str
    name: str | None
    duration: int | None
    tools: tuple[Tool, ...]
    junit: tuple[str, ...]
    coverage: str | None
    ruff: tuple[str, ...] = ()
    mypy: tuple[str, ...] = ()


MAX_MESSAGE = 500


def run(options: Options, env: Mapping[str, str], cwd: Path) -> int:
    """Return 0 when the result was posted, 1 when `report` refused or failed; it prints one line
    on standard output, or the reason on standard error."""
    secrets = [
        secret
        for name in ("GITHUB_TOKEN", "GH_TOKEN", "PREPUSH_CI_APP_KEY")
        if (secret := report.value(env, name)) is not None
    ]
    try:
        print(_report(options, env, cwd, secrets))
        return 0
    except ConfigError as error:
        problems = error.problems
    except (ReportError, GitError, OSError) as error:
        problems = [str(error)]
    for problem in problems:
        # Cut after the secrets are gone: a cut secret is no longer one the redaction can find.
        shown = report.redact(problem, tuple(secrets))[:MAX_MESSAGE]
        print(f"prepush-ci: {shown}", file=sys.stderr)
    return 1


def _report(
    options: Options, env: Mapping[str, str], cwd: Path, secrets: list[str]
) -> str:
    toplevel = git(cwd, "rev-parse", "--show-toplevel")
    if toplevel.returncode != 0:
        raise ReportError(
            "not inside a git worktree, so there is no commit to report on"
        )
    top = answer(toplevel)
    sha = resolve_commit(options.commit, cwd)
    if sha is None:
        raise ReportError(f"--commit {options.commit!r} names no commit")
    config = committed_config(sha, cwd)
    if config is None:
        raise ReportError(
            f"the commit {sha} has no config (.prepush-ci.toml or [tool.prepush-ci])"
        )
    tree = _tree_of(sha, cwd)
    problem = report.tree_problem(options.tree, tree)
    if problem is not None:
        raise ReportError(problem)
    facts = Facts(
        sha=sha,
        tree=tree,
        check=config.check,
        preflight=config.preflight,
        tools=options.tools,
        system=platform.system() or sys.platform,
        duration=options.duration,
        counts=None,
        coverage=None,
    )
    if options.result == report.STARTED:
        return _started(options, env, cwd, secrets, facts)
    counts, failures = _junit(options.junit, cwd, top)
    contradiction = report.contradiction(options.result, counts)
    if contradiction is not None:
        raise ReportError(contradiction)
    failures += _tool_failures(options, cwd, top)
    coverage = None if options.coverage is None else _coverage(options.coverage, cwd)
    facts = replace(facts, counts=counts, coverage=coverage, failures=tuple(failures))
    where = report.target(_origin(cwd), env)
    credentials = report.credentials(env)
    if isinstance(credentials, AppCredentials):
        name = options.name or report.CHECK_RUN_NAME
        _post_check_run(where, credentials, name, facts, options.result, secrets)
        how = "check run"
    else:
        name = options.name or report.STATUS_CONTEXT
        github_api.post_status(
            where.api_url,
            where.repository,
            sha,
            credentials.token,
            report.status_body(name, facts, options.result),
        )
        how = "commit status"
    return f"reported {sha} {options.result} as a {how}"


def _started(
    options: Options,
    env: Mapping[str, str],
    cwd: Path,
    secrets: list[str],
    facts: Facts,
) -> str:
    """Show the check as in progress: a check run, or a `pending` status without an app."""
    where = report.target(_origin(cwd), env)
    credentials = report.credentials(env)
    if isinstance(credentials, AppCredentials):
        name = options.name or report.CHECK_RUN_NAME
        token = _installation_token(where, credentials, secrets)
        running = github_api.in_progress_run(
            where.api_url, where.repository, token, facts.sha, name, credentials.app_id
        )
        now = int(time.time())
        if running is None:
            github_api.post_check_run(
                where.api_url,
                where.repository,
                token,
                report.started_body(name, facts, now),
            )
        else:
            github_api.update_check_run(
                where.api_url,
                where.repository,
                token,
                running,
                report.started_update_body(now),
            )
        how = "check run"
    else:
        github_api.post_status(
            where.api_url,
            where.repository,
            facts.sha,
            credentials.token,
            report.started_status_body(options.name or report.STATUS_CONTEXT, facts),
        )
        how = "commit status"
    return f"reported {facts.sha} {report.STARTED} as a {how}"


def _tree_of(sha: str, cwd: Path) -> str:
    return text_io.decode(git_bytes(cwd, "rev-parse", f"{sha}^{{tree}}")).strip()


def _origin(cwd: Path) -> str | None:
    result = git(cwd, "remote", "get-url", "origin")
    return answer(result) if result.returncode == 0 else None


def _read(path_text: str, cwd: Path) -> tuple[str, bytes]:
    try:
        return path_text, (cwd / text_io.to_path(path_text)).read_bytes()
    except OSError as error:
        raise ReportError(f"cannot read {path_text}: {error.strerror}") from error


def _junit(
    paths: tuple[str, ...], cwd: Path, top: str
) -> tuple[Counts | None, list[Failure]]:
    if not paths:
        return None, []
    total = Counts()
    failures: list[Failure] = []
    for path_text in paths:
        name, data = _read(path_text, cwd)
        total += report.count_junit(data, name)
        failures += report.junit_failures(data, name, top)
    return total, failures


def _text(path_text: str, cwd: Path) -> tuple[str, str]:
    name, data = _read(path_text, cwd)
    try:
        return name, text_io.decode_utf8(data, name).removeprefix("\ufeff")
    except text_io.NotUtf8 as error:
        raise ReportError(str(error)) from error


def _tool_failures(options: Options, cwd: Path, top: str) -> list[Failure]:
    """The errors of the ruff and mypy files; a `passed` result they contradict is refused."""
    failures: list[Failure] = []
    for paths, parse in (
        (options.ruff, report.ruff_failures),
        (options.mypy, report.mypy_failures),
    ):
        for path_text in paths:
            name, text = _text(path_text, cwd)
            found = parse(text, name, top)
            contradiction = report.file_contradiction(options.result, name, found)
            if contradiction is not None:
                raise ReportError(contradiction)
            failures += found
    return failures


def _coverage(path_text: str, cwd: Path) -> str:
    name, text = _text(path_text, cwd)
    return report.coverage_display(text, name)


def _installation_token(where: Target, app: AppCredentials, secrets: list[str]) -> str:
    signing_input = report.jwt_signing_input(app.app_id, int(time.time()))
    app_jwt = report.jwt(signing_input, signing.sign(signing_input, app.key))
    secrets.append(app_jwt)
    token = github_api.installation_token(where.api_url, where.repository, app_jwt)
    secrets.append(token)
    return token


def _post_check_run(
    where: Target,
    app: AppCredentials,
    name: str,
    facts: Facts,
    result: str,
    secrets: list[str],
) -> None:
    """Complete the run in progress of that name, or create the completed run; later batches of
    annotations update the same run."""
    token = _installation_token(where, app, secrets)
    run_id = github_api.in_progress_run(
        where.api_url, where.repository, token, facts.sha, name, app.app_id
    )
    created = (
        b""  # GitHub's answer to a creation; read only when a later batch needs the id
    )
    if run_id is None:
        created = github_api.post_check_run(
            where.api_url,
            where.repository,
            token,
            report.check_run_body(name, facts, result, facts.counts),
        )
    else:
        github_api.update_check_run(
            where.api_url,
            where.repository,
            token,
            run_id,
            report.completion_body(name, facts, result, facts.counts),
        )
    for body in report.later_batches_bodies(facts, result, facts.counts):
        github_api.update_check_run(
            where.api_url,
            where.repository,
            token,
            run_id or github_api.check_run_id(created),
            body,
        )
