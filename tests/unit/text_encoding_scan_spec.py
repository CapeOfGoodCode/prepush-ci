import ast
from pathlib import Path

import prepush_ci

PACKAGE = Path(prepush_ci.__file__).parent
CALLS = {
    "read_text",
    "write_text",
    "open",
    "decode",
    "encode",
    "fsdecode",
    "fsencode",
    "reconfigure",
    "input",
}
KEYWORDS = {"encoding", "errors", "text", "universal_newlines"}
OWNER = "text_io"


def decides_an_encoding(source: str) -> list[str]:
    """The calls, keywords and names of a module that cross a boundary on their own."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", "")
            )
            owned = (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == OWNER
            )
            if name in CALLS and not owned:
                found.append(f"line {node.lineno}: the call {name}()")
            found.extend(
                f"line {node.lineno}: the keyword {keyword.arg}"
                for keyword in node.keywords
                if keyword.arg in KEYWORDS
            )
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and (node.value.id, node.attr) == ("sys", "stdin")
        ):
            found.append(f"line {node.lineno}: sys.stdin")
        elif isinstance(node, ast.Name) and node.id == "subprocess":
            found.append(f"line {node.lineno}: subprocess")
        elif isinstance(node, ast.Import | ast.ImportFrom) and _imports_subprocess(
            node
        ):
            found.append(f"line {node.lineno}: an import of subprocess")
    return found


def _imports_subprocess(node: ast.Import | ast.ImportFrom) -> bool:
    if isinstance(node, ast.ImportFrom):
        return (node.module or "").split(".")[0] == "subprocess"
    return any(alias.name.split(".")[0] == "subprocess" for alias in node.names)


def commands() -> list[Path]:
    """The modules the policy covers: all but `text_io.py` and `core/`."""
    return [path for path in sorted(PACKAGE.glob("*.py")) if path.name != f"{OWNER}.py"]


def test_no_other_module_decides_an_encoding() -> None:
    offenders = {
        path.name: decides_an_encoding(path.read_text(encoding="utf-8"))
        for path in commands()
    }

    assert {name: found for name, found in offenders.items() if found} == {}


def test_the_scan_covers_the_commands() -> None:
    names = {path.name for path in commands()}

    assert {"cli.py", "git.py", "install_command.py", "init_command.py"} <= names
    assert "text_io.py" not in names


def test_the_scan_finds_a_violation() -> None:
    source = 'def f(path):\n    return path.read_text(encoding="utf-8")\n'

    assert decides_an_encoding(source) == [
        "line 2: the call read_text()",
        "line 2: the keyword encoding",
    ]


def test_the_scan_finds_an_implicit_crossing() -> None:
    stdin = "import sys\n\ndef f():\n    return sys.stdin.read()\n"
    process = (
        "import subprocess\n\ndef f(text):\n    return subprocess.run(['git', text])\n"
    )

    assert decides_an_encoding(stdin) == ["line 4: sys.stdin"]
    assert decides_an_encoding(process) == [
        "line 1: an import of subprocess",
        "line 4: subprocess",
    ]


def test_the_scan_finds_the_text_keyword_and_the_calls_of_the_scenario() -> None:
    source = (
        "import os\n"
        "run(['git'], text=True)\n"
        "os.fsdecode(b'')\n"
        "b''.decode()\n"
        "open('x')\n"
        "input()\n"
    )

    assert decides_an_encoding(source) == [
        "line 2: the keyword text",
        "line 3: the call fsdecode()",
        "line 4: the call decode()",
        "line 5: the call open()",
        "line 6: the call input()",
    ]


def test_a_call_of_the_owning_module_is_not_a_violation() -> None:
    source = (
        "from prepush_ci import text_io\n"
        "text_io.read_text(path)\ntext_io.decode(data)\ntext_io.write_text(path, x)\n"
    )

    assert decides_an_encoding(source) == []
