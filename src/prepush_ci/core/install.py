"""What `prepush-ci install` writes: the hook scripts and the files that configure them."""

import re
from collections.abc import Sequence

HOOKS = ("commit-msg", "pre-push")
HOOKS_DIRECTORY = ("prepush-ci", "hooks")
PYTHON_FILE = "python"
PREVIOUS_FILE = "previous"

_FORWARDABLE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*"
)  # a name safe to write into a script
_PRELUDE = (
    "#!/bin/sh\n"
    "# Written by `prepush-ci install`; run it again to update.\n"
    'dir=$(dirname "$0")\n'
    f'prev=$(cat "$dir/{PREVIOUS_FILE}")\n'
)
_RUN_PREVIOUS = (
    # Git runs a hook only if it exists and is executable, and so do we, each time.
    'if [ -x "$prev/{hook}" ]; then\n  "$prev/{hook}" "$@"{stdin} || exit $?\nfi\n'
)


def hook_script(hook: str) -> str:
    """The script git runs for `hook`: the hook of the same name in the previous directory first,
    then this tool, started with the interpreter in the file `python` beside the script so that
    `PATH` plays no part. `pre-push` reads its standard input once and feeds it to both."""
    interpreter = f'py=$(cat "$dir/{PYTHON_FILE}")\n'
    if hook == "pre-push":
        return (
            _PRELUDE
            + 'input=$(mktemp) || exit 1\ntrap \'rm -f "$input"\' EXIT\ncat > "$input"\n'
            + _RUN_PREVIOUS.format(hook=hook, stdin=' < "$input"')
            + interpreter
            + f'"$py" -m prepush_ci hook {hook} "$@" < "$input"\n'
        )
    return (
        _PRELUDE
        + _RUN_PREVIOUS.format(hook=hook, stdin="")
        + interpreter
        + f'exec "$py" -m prepush_ci hook {hook} "$@"\n'
    )


def forwarder_script(hook: str) -> str:
    """A script that does what git would have done with the previous directory for `hook`."""
    return (
        _PRELUDE
        + f'if [ -x "$prev/{hook}" ]; then\n  exec "$prev/{hook}" "$@"\nfi\nexit 0\n'
    )


def forwardable(name: str) -> bool:
    """Whether a file of the previous directory is a hook to forward: not a sample, not ours."""
    return (
        name not in HOOKS
        and not name.endswith(".sample")
        and _FORWARDABLE.fullmatch(name) is not None
    )


def desired_files(
    python: str, previous: str, forwarded: Sequence[str]
) -> dict[str, str]:
    """Every file of the hooks directory, by name, with its contents."""
    files = {hook: hook_script(hook) for hook in HOOKS}
    files.update({name: forwarder_script(name) for name in forwarded})
    files[PYTHON_FILE] = python + "\n"
    files[PREVIOUS_FILE] = previous + "\n"
    return files
