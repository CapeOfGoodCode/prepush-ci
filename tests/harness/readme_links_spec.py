"""README.md is the PyPI long description, so every link in it must work outside the repository."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOB = "https://github.com/CapeOfGoodCode/prepush-ci/blob/main/"
TREE = "https://github.com/CapeOfGoodCode/prepush-ci/tree/main/"


def link_targets() -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(
        r'(?:src|href)="([^"]+)"', text
    )


def test_readme_has_no_relative_link_target() -> None:
    relative = [t for t in link_targets() if not re.match(r"[a-z][a-z0-9+.-]*:|#", t)]
    assert relative == []


def test_readme_links_to_repository_files_resolve_in_the_checkout() -> None:
    paths = [
        (t.removeprefix(BLOB), False)
        if t.startswith(BLOB)
        else (t.removeprefix(TREE), True)
        for t in link_targets()
        if t.startswith((BLOB, TREE))
    ]
    assert paths
    for path, is_directory in paths:
        assert (ROOT / path).is_dir() if is_directory else (ROOT / path).is_file(), path
