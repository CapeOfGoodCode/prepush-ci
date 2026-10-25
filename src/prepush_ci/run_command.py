"""`prepush-ci run`: the sequence of the pre-push hook, started by hand on `HEAD`."""

import sys
from collections.abc import Mapping
from pathlib import Path

from prepush_ci.checking import (
    Refused,
    head,
    require_clean,
    run_recorded_check,
    worktree_root,
)
from prepush_ci.core.config import ConfigError
from prepush_ci.core.run_cache import Key, fingerprint
from prepush_ci.git import GitError
from prepush_ci.pass_cache import current_head, expire_passes, record_pass
from prepush_ci.preflight import PreflightRefused
from prepush_ci.preflight import run as run_preflight
from prepush_ci.repo_config import load_repository_config


def run(env: Mapping[str, str], cwd: Path) -> int:
    """Return 0 when the preflight and the check pass on `HEAD`, 1 otherwise.

    Not a hook: `PREPUSH_CI` and the trailer play no part, and the check always runs, so
    this is also how to run a flaky check again. A pass refreshes the cache.
    """
    try:
        root = worktree_root(cwd)
        config = load_repository_config(root)
        head(root)
        checked = current_head(root)
        require_clean(root)
        output = run_preflight(config, env, root)
        code, facts = run_recorded_check(config, root, checked.tree)
        if code == 0:
            key = Key(checked.tree, fingerprint(config, output))
            if record_pass(config, root, key, checked.sha, facts):
                expire_passes(root, to_origin=False)
        return code
    except ConfigError as error:
        for problem in error.problems:
            print(f"prepush-ci: {problem}", file=sys.stderr)
        return 1
    except (Refused, PreflightRefused, GitError) as error:
        print(f"prepush-ci: {error}", file=sys.stderr)
        return 1
