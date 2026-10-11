"""PostToolUse hook: fix, format and lint a Python file right after it is edited.

The pre-commit hooks catch the same findings, but only at commit time — by then
an agent may have built several edits on top of a lint error. This hook runs
`ruff check --fix` and `ruff format` on the one file just written and, when a
finding is left that ruff cannot fix, reports it back to the agent (exit code 2,
findings on stderr) so it is answered in the same step.

Reads the hook payload on stdin; does nothing for non-Python files or files
outside the project.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_PYTHON_SUFFIXES = {".py", ".pyi"}


def _ruff(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--quiet", "ruff", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    raw = str(payload.get("tool_input", {}).get("file_path", ""))
    if not raw:
        return 0
    path = Path(raw)
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())).resolve()
    if path.suffix not in _PYTHON_SUFFIXES or not path.is_file():
        return 0
    if not path.resolve().is_relative_to(project):
        return 0

    _ruff("check", "--fix", "--force-exclude", "--quiet", str(path))
    _ruff("format", "--force-exclude", "--quiet", str(path))
    remaining = _ruff("check", "--force-exclude", "--output-format=concise", str(path))
    if remaining.returncode != 0:
        print(
            "ruff findings left after --fix (answer them now, see AGENTS.md):\n"
            + remaining.stdout
            + remaining.stderr,
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
