"""`prepush-ci skill [--write]`: print the setup skill of this version, or write it as the project skill."""

import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, PackagePath, distribution
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.skill import (
    NO_REPOSITORY,
    NOT_INSTALLED,
    PROJECT_SKILL,
    SKILL_FILE,
    choose,
)
from prepush_ci.git import git

# Two directories above the package: the root of a source checkout, where the skill is edited.
CHECKOUT_FILE = Path(__file__).resolve().parents[2] / SKILL_FILE


def run(
    write: bool,
    cwd: Path,
    *,
    checkout: Path = CHECKOUT_FILE,
    files: Sequence[PackagePath] | None = None,
) -> int:
    """Print the skill, or with `write` put it into the working tree; the exit code."""
    content = _read(checkout, _installed_files() if files is None else files)
    if content is None:
        print(NOT_INSTALLED, file=sys.stderr)
        return 1
    if not write:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
        return 0
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print(NO_REPOSITORY, file=sys.stderr)
        return 1
    # Only the newline git ends its answer with goes: a root that ends in a space is a root.
    target = text_io.to_path(top.stdout.removesuffix("\n")) / PROJECT_SKILL
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # bytes: no newline translation may change the skill
        target.write_bytes(content)
    except OSError as error:
        # a file in the way, a directory at the target, no permission
        reason = error.strerror or str(error)
        print(
            f"prepush-ci skill: cannot write {text_io.text_of(target)}: {reason}",
            file=sys.stderr,
        )
        return 1
    print(f"wrote {PROJECT_SKILL}")
    return 0


def _installed_files() -> Sequence[PackagePath]:
    try:
        return distribution("prepush-ci").files or []
    except PackageNotFoundError:  # run from a source tree that was never installed
        return []


def _read(checkout: Path, files: Sequence[PackagePath]) -> bytes | None:
    """The bytes of the skill file `choose` picks; None when there is none or it is gone."""
    source = choose(checkout.is_file(), [str(entry) for entry in files])
    if source is None:
        return None
    if source.checkout:
        return checkout.read_bytes()
    entry = next(entry for entry in files if str(entry) == source.entry)
    try:
        return Path(str(entry.locate())).read_bytes()
    except OSError:  # listed in the record, removed from the environment since
        return None
