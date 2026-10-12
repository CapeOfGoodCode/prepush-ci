"""What `prepush-ci install` writes: the hook scripts and the files that configure them."""

HOOKS = ("commit-msg", "pre-push")
HOOKS_DIRECTORY = ("prepush-ci", "hooks")
PYTHON_FILE = "python"


def hook_script(hook: str) -> str:
    """The script git runs for `hook`; it starts the tool with the interpreter in the file `python`
    that sits beside it, so `PATH` plays no part."""
    return (
        "#!/bin/sh\n"
        "# Written by `prepush-ci install`; run it again to update.\n"
        'dir=$(dirname "$0")\n'
        f'py=$(cat "$dir/{PYTHON_FILE}")\n'
        f'exec "$py" -m prepush_ci hook {hook} "$@"\n'
    )


def desired_files(python: str) -> dict[str, str]:
    """Every file of the hooks directory, by name, with its contents."""
    files = {hook: hook_script(hook) for hook in HOOKS}
    files[PYTHON_FILE] = python + "\n"
    return files
