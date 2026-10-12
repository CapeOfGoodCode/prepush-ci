"""Decisions of the commit-msg hook: what `PREPUSH_CI` asks for, and whether a message is empty."""

from enum import Enum


class Mode(Enum):
    OFF = "off"
    FULL = "full"


class InvalidMode(Exception):
    """`PREPUSH_CI` holds a value other than `full`, `off` or the empty string."""


def parse_mode(value: str | None) -> Mode:
    """Unset and empty mean `off`; values are compared exactly, so `FULL` is refused."""
    if value is None or value == "":
        return Mode.OFF
    try:
        return Mode(value)
    except ValueError:
        raise InvalidMode(
            f"PREPUSH_CI={value!r} is not valid: use `full` to demand the full check "
            "on this commit, or `off` (or leave it unset) to commit as usual"
        ) from None


SIGN_OFF = (
    "Signed-off-by: "  # `git commit -s`; git does not count these lines as a message
)


class UnsupportedCommentChar(Exception):
    """`core.commentChar` holds a value the hook cannot interpret."""


def require_known_comment_setting(setting: str | None) -> None:
    """Refuse `auto` and empty: git picks the comment prefix per commit, so it cannot be known here."""
    if setting in ("", "auto"):
        raise UnsupportedCommentChar(
            f"core.commentChar={setting!r} is not supported with PREPUSH_CI=full: "
            "git picks the comment character per commit, so the hook cannot tell an "
            "empty message from one that holds only the trailer; set core.commentChar "
            "to a fixed character such as `#`, or commit with PREPUSH_CI=off"
        )


class Cleanup(Enum):
    """How git cleans the message up after the `commit-msg` hook (`commit.cleanup`)."""

    STRIP = "strip"
    WHITESPACE = "whitespace"
    VERBATIM = "verbatim"
    SCISSORS = "scissors"


def editor_was_used(git_editor: str | None, text: str) -> bool:
    """Whether git launched an editor, which hooks cannot be told directly.

    Git sets `GIT_EDITOR=:` for its hooks when it launches none. A user who chose the no-op
    editor `:` still leaves git's template in the message, which starts with an empty line.
    """
    return git_editor != ":" or text.startswith("\n")


def resolve_cleanup(configured: str | None, editor_used: bool) -> Cleanup:
    """The cleanup git applies: `commit.cleanup`, else `strip` with an editor, `whitespace` without.

    An explicit `git commit --cleanup=<mode>` is invisible to hooks and not accounted for.
    """
    try:
        return Cleanup(configured)
    except ValueError:  # unset or "default"
        return Cleanup.STRIP if editor_used else Cleanup.WHITESPACE


def is_blank_message(
    text: str, cleanup: Cleanup = Cleanup.STRIP, comment: str = "#"
) -> bool:
    """True when git will find nothing in the message after its cleanup and abort the commit.

    Like git, ignore everything from the scissors line on (the diff of `git commit -v`) and
    sign-off lines (`git commit -s` adds one to an empty message).
    Only `strip` drops comment lines; in the other modes they are the message.
    """
    scissors = f"{comment} ------------------------ >8 ------------------------"
    kept: list[str] = []
    for line in text.splitlines():
        if line.startswith(scissors):
            break
        kept.append(line)
    if cleanup is Cleanup.VERBATIM:
        return not kept
    drops_comments = cleanup is Cleanup.STRIP
    return not any(
        line.strip()
        and not line.startswith(SIGN_OFF)
        and not (drops_comments and line.startswith(comment))
        for line in kept
    )


def clean_up(text: str, cleanup: Cleanup, comment: str = "#") -> str:
    """The message the way git's cleanup leaves it (`git stripspace`), for comparing messages.

    Like git, cut at the scissors line, trim trailing whitespace, collapse runs of empty lines
    and drop leading and trailing ones; `strip` also drops comment lines. `verbatim` keeps the text.
    """
    scissors = f"{comment} ------------------------ >8 ------------------------"
    if cleanup is Cleanup.VERBATIM:
        return text
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith(scissors):
            break
        if cleanup is Cleanup.STRIP and line.startswith(comment):
            continue
        line = line.rstrip()
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return "".join(f"{line}\n" for line in lines)


def is_template_untouched(
    text: str, template: str, cleanup: Cleanup, comment: str = "#"
) -> bool:
    """True when git will find the message unchanged from `commit.template` and abort the commit.

    Git compares the cleaned message with the cleaned template, so a trailer added by the hook
    would make an unedited template look edited. Sign-off lines after the template do not count
    as an edit, and a verbatim message is never untouched.
    """
    if cleanup is Cleanup.VERBATIM or not template:
        return False
    cleaned_template = clean_up(template, cleanup, comment)
    cleaned = clean_up(text, cleanup, comment)
    if not cleaned.startswith(cleaned_template):
        return False
    rest = cleaned.removeprefix(cleaned_template)
    return all(
        not line.strip() or line.startswith(SIGN_OFF) for line in rest.splitlines()
    )
