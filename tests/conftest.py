import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True, scope="session")
def no_fsmonitor_daemons() -> Iterator[None]:
    """Run every git of the suite, and of the tool under test, with `core.fsmonitor=false`.

    Git for Windows enables it in its system config, so each temporary repository would start a
    `git fsmonitor--daemon` that outlives its test: 700 of them after one run (#61). The
    variables append to any `GIT_CONFIG_COUNT` the developer already set.
    """
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    patch = pytest.MonkeyPatch()
    patch.setenv(f"GIT_CONFIG_KEY_{count}", "core.fsmonitor")
    patch.setenv(f"GIT_CONFIG_VALUE_{count}", "false")
    patch.setenv("GIT_CONFIG_COUNT", str(count + 1))
    yield
    patch.undo()


# Git's per-repository variables (`git rev-parse --local-env-vars` without the config ones).
REPOSITORY_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
    "GIT_GRAFT_FILE",
    "GIT_SHALLOW_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE",
)


@pytest.fixture(autouse=True, scope="session")
def no_repository_of_the_calling_git() -> Iterator[None]:
    """Run every git of the suite against the repository it names, never the one that started us.

    Git exports `GIT_DIR` and friends to a hook it runs, in a linked worktree too. Inherited,
    they would send each `git init`, `git config` and `git commit` of a test to the developer's
    repository: its config rewritten, its work tree moved to `main` (#77).
    """
    patch = pytest.MonkeyPatch()
    for name in REPOSITORY_VARIABLES:
        patch.delenv(name, raising=False)
    yield
    patch.undo()
