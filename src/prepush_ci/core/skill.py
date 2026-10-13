"""Where `prepush-ci skill` reads the setup skill from, and the words it says."""

from collections.abc import Sequence
from dataclasses import dataclass

SKILL_FILE = "skills/prepush-ci-setup/SKILL.md"  # in the repository, and in the sdist
INSTALLED_FILE = "prepush-ci-setup/SKILL.md"  # in the wheel, below the data directory
PROJECT_SKILL = ".claude/skills/prepush-ci-setup/SKILL.md"
NOT_INSTALLED = "prepush-ci skill: the skill is not part of this installation"
NO_REPOSITORY = "prepush-ci skill: --write needs a git repository with a working tree"


@dataclass(frozen=True)
class Source:
    """The skill file to read: the source checkout's, or the entry of the installed distribution."""

    checkout: bool
    entry: str | None = None


def choose(checkout_has_file: bool, listed: Sequence[str]) -> Source | None:
    """The source checkout when it has the file, else the first listed file of the distribution
    that is the installed skill; None when there is neither."""
    if checkout_has_file:
        return Source(True)
    for entry in listed:
        if entry == INSTALLED_FILE or entry.endswith(f"/{INSTALLED_FILE}"):
            return Source(False, entry)
    return None
