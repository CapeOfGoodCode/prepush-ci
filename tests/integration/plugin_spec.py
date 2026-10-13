"""The repository is a Claude Code plugin marketplace whose one plugin is the setup skill."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "prepush-ci-setup" / "SKILL.md"


def manifest(name: str) -> dict[str, Any]:
    loaded = json.loads((ROOT / ".claude-plugin" / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def front_matter(path: Path) -> dict[str, str]:
    """The `key: value` lines between the first two `---` lines of the file."""
    match = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match, f"{path} has no front matter"
    return dict(
        line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line
    )


def test_the_marketplace_names_one_plugin_whose_source_is_the_repository_root() -> None:
    marketplace = manifest("marketplace.json")

    assert marketplace["name"] == "prepush-ci"
    assert marketplace["owner"]["name"].strip() != ""
    assert [(p["name"], p["source"]) for p in marketplace["plugins"]] == [
        ("prepush-ci", "./")
    ]


def test_the_plugin_manifest_has_a_name_and_a_description_and_no_version() -> None:
    plugin = manifest("plugin.json")

    assert plugin["name"] == "prepush-ci"
    assert plugin["description"].strip() != ""
    assert "version" not in plugin


def test_the_skill_is_a_component_named_like_its_directory_with_a_description() -> None:
    meta = front_matter(SKILL)

    assert meta["name"] == SKILL.parent.name == "prepush-ci-setup"
    assert meta["description"].strip() != ""


def test_the_plugin_has_no_component_other_than_the_skill() -> None:
    others = ["agents", "commands", "hooks", ".mcp.json", ".lsp.json"]

    assert [name for name in others if (ROOT / name).exists()] == []


def test_the_skill_is_the_only_tracked_skill_file_outside_the_agent_directories() -> (
    None
):
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*SKILL.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")

    outside = [
        name
        for name in tracked
        if name
        and Path(name).name == "SKILL.md"
        and not name.startswith((".claude/", "openspec/"))
    ]
    assert outside == ["skills/prepush-ci-setup/SKILL.md"]
