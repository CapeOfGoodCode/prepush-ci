"""PreToolUse hook: refuse the few shell commands that would break this repository's invariants.

Agents here may run with every permission granted, so this is the last line before the server-side
rules (branch ruleset, token scope). It stops slips, not a determined actor. Blocked:

- merging a pull request (`gh pr merge`, the merge API): only a human merges, after reading the proof;
- pushing to `main` or force-pushing without a lease: `main` changes only through merged pull requests;
- pushing a tag or creating a release: a tag publishes to PyPI, and only a human releases;
- bypassing git hooks (`--no-verify`): the hooks are the quality gate.

Reads the hook payload on stdin; exit code 2 with the reason on stderr blocks the call.
"""

import json
import re
import sys

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgh\s+pr\s+merge\b"), "only a human merges pull requests (LOOP.md)"),
    (
        re.compile(r"\bgh\s+api\b.*\bpulls/\d+/merge\b"),
        "only a human merges pull requests (LOOP.md)",
    ),
    (
        re.compile(r"\bgit\s+(commit|push)\b[^|;&\n]*--no-verify\b"),
        "never bypass git hooks (AGENTS.md)",
    ),
    (
        re.compile(
            r"\bgit\s+push\b[^|;&\n]*(\s--tags\b|\sv\d|refs/tags/)|\bgh\s+release\s+create\b"
        ),
        "only a human releases (AGENTS.md, Versioning)",
    ),
    (
        re.compile(r"\bgit\s+push\b[^|;&]*(\s|:|\+)(refs/heads/)?(main|master)\b"),
        "main changes only through merged pull requests (AGENTS.md)",
    ),
    (
        re.compile(r"\bgit\s+push\b[^|;&]*\s(--force|-f)(\s|$)"),
        "use --force-with-lease on your own branch, never --force (AGENTS.md)",
    ),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = str(payload.get("tool_input", {}).get("command", ""))
    for pattern, reason in _RULES:
        if pattern.search(command):
            print(f"Blocked by .claude/hooks/guard.py: {reason}.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
