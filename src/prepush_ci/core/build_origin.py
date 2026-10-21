"""What `prepush-ci --version` says about where the installed build came from."""

import json
import re

# The installation record (`direct_url.json`, PEP 610) holds exactly one of these keys.
_KEYS = ("vcs_info", "dir_info", "archive_info")
_HEX = re.compile(
    r"[0-9a-fA-F]+"
)  # not `\d` or `str.isalnum`: Unicode digits are no hex
_SHOWN = 12


def origin_suffix(record: str | None) -> str:
    """The text that follows the version: ` (git <commit>)`, ` (direct install)` or nothing.

    `record` is the text of the installation record, None when there is none. A record that is
    no JSON, is no object, names none of the keys or holds a key that is no object counts as none:
    the version line never fails. It never carries a path or a URL of the record.
    """
    try:
        data = json.loads(record) if record is not None else None
    except (ValueError, RecursionError):
        # Invalid JSON, a number of more than 4300 digits, or nesting too deep to decode.
        return ""
    if not isinstance(data, dict):
        return ""
    named = [data[key] for key in _KEYS if key in data]
    if not named or not all(isinstance(value, dict) for value in named):
        return ""
    vcs_info = data.get("vcs_info")
    if vcs_info is not None and vcs_info.get("vcs") == "git":
        commit = vcs_info.get("commit_id")
        if isinstance(commit, str) and _HEX.fullmatch(commit):
            return f" (git {commit[:_SHOWN]})"
    return " (direct install)"
