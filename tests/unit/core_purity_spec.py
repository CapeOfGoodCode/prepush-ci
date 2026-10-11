import ast
from pathlib import Path

import prepush_ci.core

CORE = Path(prepush_ci.core.__file__).parent
IO_MODULES = {
    "os",
    "sys",
    "subprocess",
    "pathlib",
    "shutil",
    "socket",
    "urllib",
    "http",
    "io",
}


def imported_top_level_modules(source: str) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def test_core_modules_import_nothing_that_does_io() -> None:
    offenders = {
        path.name: sorted(
            imported_top_level_modules(path.read_text(encoding="utf-8")) & IO_MODULES
        )
        for path in CORE.rglob("*.py")
    }
    assert {name: mods for name, mods in offenders.items() if mods} == {}
