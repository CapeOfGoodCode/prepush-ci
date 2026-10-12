"""What the pre-push hook verifies before it runs the check: variables, the default branch, a preflight."""

from collections.abc import Mapping, Sequence

WAYS_OUT = (
    "set `require_up_to_date = false` in the config to skip this step, "
    "or push a tip without the trailer, which runs no check"
)


def missing_env(required: Sequence[str], env: Mapping[str, str]) -> list[str]:
    """The required variables that are unset or empty, in the configured order."""
    return [name for name in required if not env.get(name)]


def split_ref(ref: str) -> tuple[str, str] | None:
    """`<remote>/<branch>` split at the first slash (`origin/release/1` is `origin`, `release/1`)."""
    remote, separator, branch = ref.partition("/")
    if not separator or not remote or not branch:
        return None
    return remote, branch


def fetch_refspec(remote: str, branch: str) -> str:
    """Fetch the branch into the tracking ref the user's own `git rebase <remote>/<branch>` reads."""
    return f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}"


def message_missing_env(names: Sequence[str]) -> str:
    return (
        "the check needs these environment variables, which are unset or empty: "
        f"{', '.join(names)}; set them (`require_env` in the config) or push a tip "
        "without the trailer, which runs no check"
    )


def message_preflight_failed(command: str, status: int) -> str:
    return f"the preflight failed (exit {status}): {command}"


def message_not_up_to_date(ref: str) -> str:
    return (
        f"{ref} has commits that this branch does not contain: "
        f"rebase onto it (`git rebase {ref}`) or merge it (`git merge {ref}`), then push again"
    )


def message_fetch_failed(ref: str, reason: str) -> str:
    return f"could not fetch {ref} to see whether the branch is up to date: {reason}; {WAYS_OUT}"


def message_bad_ref(ref: str) -> str:
    return (
        f'`require_up_to_date = "{ref}"` must be `<remote>/<branch>`, '
        f"such as `origin/main`; {WAYS_OUT}"
    )


def message_no_remote(remote: str, ref: str) -> str:
    return f"{ref}: the repository has no remote named `{remote}`; {WAYS_OUT}"


def message_merge_base_failed(ref: str, reason: str) -> str:
    return f"could not compare this branch with {ref}: {reason}; {WAYS_OUT}"
