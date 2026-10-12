"""`prepush-ci doctor`: look at what git would run and say what is missing, changing nothing."""

import sys
from collections.abc import Mapping
from pathlib import Path

from prepush_ci.core import doctor
from prepush_ci.core.config import Config, ConfigError
from prepush_ci.core.config_source import PREPUSH_CI_FILE, PYPROJECT_FILE, ConfigMissing
from prepush_ci.git import git
from prepush_ci.repo_config import load_repository_config


def run(cwd: Path, env: Mapping[str, str], mode: str | None = None) -> int:
    try:
        common_dir = git(cwd, "rev-parse", "--git-common-dir")
    except OSError as error:  # git cannot even start
        print(f"prepush-ci doctor: cannot run git: {error}", file=sys.stderr)
        return 1
    if common_dir.returncode != 0:
        print(doctor.NO_REPOSITORY, file=sys.stderr)
        return 1
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print(doctor.NO_WORKTREE, file=sys.stderr)
        return 1
    root = (cwd / top.stdout.strip()).resolve()
    config, config_check = _config(root)
    found = {
        doctor.CONFIG: config_check,
        doctor.COMMIT_MSG: doctor.skip(doctor.COMMIT_MSG, "not checked yet"),
        doctor.PRE_PUSH: doctor.skip(doctor.PRE_PUSH, "not checked yet"),
        doctor.PREFLIGHT: _needs_config(config, doctor.PREFLIGHT),
        doctor.PREPUSH_CI: doctor.prepush_ci_check(env.get("PREPUSH_CI"), mode),
        doctor.UP_TO_DATE: _needs_config(config, doctor.UP_TO_DATE),
    }
    checks = [found[name] for name in doctor.NAMES]
    print("\n".join(doctor.render(checks)))
    return doctor.exit_status(checks)


def _config(root: Path) -> tuple[Config | None, doctor.Check]:
    """The config of the worktree and the verdict of the `config` check."""
    source = PREPUSH_CI_FILE if (root / PREPUSH_CI_FILE).exists() else PYPROJECT_FILE
    try:
        config = load_repository_config(root)
    except ConfigMissing as error:
        return None, doctor.config_check(None, error.problems, missing=True)
    except ConfigError as error:
        return None, doctor.config_check(source, error.problems, missing=False)
    except (OSError, UnicodeDecodeError) as error:
        problem = f"cannot read {source}: {error}"
        return None, doctor.config_check(source, [problem], missing=False)
    return config, doctor.config_check(source, [], missing=False)


def _needs_config(config: Config | None, name: str) -> doctor.Check:
    if config is None:
        return doctor.config_skip(name)
    return doctor.skip(name, "not checked yet")
