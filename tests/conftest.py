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
