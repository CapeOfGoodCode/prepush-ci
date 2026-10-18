"""`prepush-ci report`: post the result of a run of the check as a check run or a commit status."""

import platform
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from prepush_ci import github_api, signing, text_io
from prepush_ci.core import report
from prepush_ci.core.config import ConfigError
from prepush_ci.core.report import (
    AppCredentials,
    Counts,
    Facts,
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
    if git(cwd, "rev-parse", "--show-toplevel").returncode != 0:
        raise ReportError(
            "not inside a git worktree, so there is no commit to report on"
        )
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
    counts = _counts(options.junit, cwd)
    contradiction = report.contradiction(options.result, counts)
    if contradiction is not None:
        raise ReportError(contradiction)
    coverage = None if options.coverage is None else _coverage(options.coverage, cwd)
    where = report.target(_origin(cwd), env)
    credentials = report.credentials(env)
    facts = Facts(
        sha=sha,
        tree=tree,
        check=config.check,
        preflight=config.preflight,
        tools=options.tools,
        system=platform.system() or sys.platform,
        duration=options.duration,
        counts=counts,
        coverage=coverage,
    )
    if isinstance(credentials, AppCredentials):
        name = options.name or report.CHECK_RUN_NAME
        _post_check_run(
            where,
            credentials,
            report.check_run_body(name, facts, options.result, counts),
            secrets,
        )
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


def _tree_of(sha: str, cwd: Path) -> str:
    return text_io.decode(git_bytes(cwd, "rev-parse", f"{sha}^{{tree}}")).strip()


def _origin(cwd: Path) -> str | None:
    result = git(cwd, "config", "--get", "remote.origin.url")
    return answer(result) if result.returncode == 0 else None


def _read(path_text: str, cwd: Path) -> tuple[str, bytes]:
    try:
        return path_text, (cwd / text_io.to_path(path_text)).read_bytes()
    except OSError as error:
        raise ReportError(f"cannot read {path_text}: {error.strerror}") from error


def _counts(paths: tuple[str, ...], cwd: Path) -> Counts | None:
    if not paths:
        return None
    total = Counts()
    for path_text in paths:
        name, data = _read(path_text, cwd)
        total += report.count_junit(data, name)
    return total


def _coverage(path_text: str, cwd: Path) -> str:
    name, data = _read(path_text, cwd)
    try:
        text = text_io.decode_utf8(data, name)
    except text_io.NotUtf8 as error:
        raise ReportError(str(error)) from error
    return report.coverage_display(text, name)


def _post_check_run(
    where: Target, app: AppCredentials, body: object, secrets: list[str]
) -> None:
    signing_input = report.jwt_signing_input(app.app_id, int(time.time()))
    app_jwt = report.jwt(signing_input, signing.sign(signing_input, app.key))
    secrets.append(app_jwt)
    token = github_api.installation_token(where.api_url, where.repository, app_jwt)
    secrets.append(token)
    github_api.post_check_run(where.api_url, where.repository, token, body)
