"""What `prepush-ci install` writes into the files of a hook manager: one marked block per place,
edited as lines so that every other line of the file stays as it was."""

from collections.abc import Sequence

BEGIN = "# prepush-ci: begin"
END = "# prepush-ci: end"


class Refusal(Exception):
    """A file this tool cannot edit safely; the message says what to fix, nothing was changed."""


def split_lines(text: str) -> tuple[list[str], str]:
    """The lines of `text` without their line ends, and the line end the file uses."""
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(eol)
    if lines[-1] == "":  # the final line end is not a line
        lines.pop()
    return lines, eol


def join_lines(lines: Sequence[str], eol: str) -> str:
    """The text of `lines`, every line ended."""
    return "".join(line + eol for line in lines)


def find_block(lines: Sequence[str], needle: str = "") -> tuple[int, int] | None:
    """The indexes of the begin and end lines of the first block whose body contains `needle`."""
    start = 0
    while start < len(lines):
        if lines[start].strip() != BEGIN:
            start += 1
            continue
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].strip() == END), None
        )
        if end is None:
            raise Refusal(f"it has `{BEGIN}` without a matching `{END}`")
        if needle in "\n".join(lines[start + 1 : end]):
            return start, end
        start = end + 1
    return None


def place_block(
    lines: Sequence[str], block: Sequence[str], at: int, needle: str = ""
) -> list[str]:
    """`lines` with `block` (begin and end lines included) replacing the block that holds
    `needle`, or inserted before line `at` when there is none."""
    span = find_block(lines, needle)
    if span is None:
        span = (at, at - 1)
    return [*lines[: span[0]], *block, *lines[span[1] + 1 :]]
