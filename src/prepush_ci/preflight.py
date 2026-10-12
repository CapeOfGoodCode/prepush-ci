"""The preflight of the pre-push hook: variables, the default branch, the `preflight` command."""

import subprocess
from collections.abc import Mapping
from pathlib import Path

from prepush_ci.core.config import Config
from prepush_ci.core.preflight import (
    fetch_refspec,
    message_bad_ref,
    message_fetch_failed,
    message_merge_base_failed,
    message_missing_env,
    message_no_remote,
    message_not_up_to_date,
    message_preflight_failed,
    missing_env,
    split_ref,
)
from prepush_ci.git import git


class PreflightRefused(Exception):
    """A requirement does not hold; the message says what and how to fix it."""


def run(config: Config, env: Mapping[str, str], root: Path) -> None:
    """Verify, in this order, the variables, the up-to-date ref and the `preflight` command.

    Cheapest and most certain first; a rebase the up-to-date step asks for would invalidate
    the work of a later step. Each refusal stops every later step.
    """
    missing = missing_env(config.require_env, env)
    if missing:
        raise PreflightRefused(message_missing_env(missing))
    if config.require_up_to_date is not None:
        _up_to_date(config.require_up_to_date, root)
    if config.preflight is not None:
        outcome = subprocess.run(
            config.preflight,
            shell=True,
            cwd=root,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if outcome.returncode != 0:
            raise PreflightRefused(
                message_preflight_failed(config.preflight, outcome.returncode)
            )


def _up_to_date(ref: str, root: Path) -> None:
    """Fetch the ref into its tracking ref and require it to be an ancestor of `HEAD`."""
    parts = split_ref(ref)
    if parts is None:
        raise PreflightRefused(message_bad_ref(ref))
    remote, branch = parts
    if remote not in git(root, "remote").stdout.split():
        raise PreflightRefused(message_no_remote(remote, ref))
    fetched = git(root, "fetch", "--quiet", "--", remote, fetch_refspec(remote, branch))
    if fetched.returncode != 0:
        raise PreflightRefused(message_fetch_failed(ref, fetched.stderr.strip()))
    compared = git(
        root,
        "merge-base",
        "--is-ancestor",
        f"refs/remotes/{remote}/{branch}",
        "HEAD",
    )
    if compared.returncode == 1:
        raise PreflightRefused(message_not_up_to_date(ref))
    if compared.returncode != 0:
        raise PreflightRefused(message_merge_base_failed(ref, compared.stderr.strip()))
