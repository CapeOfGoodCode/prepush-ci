"""`scripts/lint-workflows`: the workflows, the action and the shell scripts users copy are linted
by `scripts/ci`, so a template injection or a broad permission fails before a push."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "lint-workflows"

CLEAN_WORKFLOW = """name: ok
on: workflow_dispatch
permissions: {}
jobs:
  say:
    runs-on: ubuntu-latest
    permissions: {}
    steps:
      - run: echo hi
"""
INJECTION = """name: bad
on: issues
permissions: {}
jobs:
  say:
    runs-on: ubuntu-latest
    permissions: {}
    steps:
      - run: echo "${{ github.event.issue.title }}"
"""
CLEAN_SCRIPT = '#!/bin/sh\nset -eu\necho "$1"\n'


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A clean repository layout: one workflow, `docs/ci/gate.sh` and `scripts/ci`."""
    for name, text in (
        (".github/workflows/ok.yml", CLEAN_WORKFLOW),
        ("docs/ci/github-actions.yml", CLEAN_WORKFLOW),
        ("docs/ci/gate.sh", CLEAN_SCRIPT),
        ("scripts/ci", CLEAN_SCRIPT),
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, newline="\n")
    return tmp_path


def lint(root: Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        ["sh", SCRIPT.as_posix(), root.as_posix()],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_clean_tree_passes_the_workflow_lint(tree: Path) -> None:
    result = lint(tree)

    assert result.returncode == 0, result.stdout + result.stderr


def test_a_workflow_with_a_template_injection_fails_the_workflow_lint(
    tree: Path,
) -> None:
    (tree / ".github" / "workflows" / "bad.yml").write_text(INJECTION, newline="\n")

    result = lint(tree)

    assert result.returncode != 0
    assert "template-injection" in result.stdout + result.stderr


def test_an_injection_in_the_github_actions_example_fails_the_workflow_lint(
    tree: Path,
) -> None:
    (tree / "docs" / "ci" / "github-actions.yml").write_text(INJECTION, newline="\n")

    result = lint(tree)

    assert result.returncode != 0
    assert "template-injection" in result.stdout + result.stderr


def test_a_broken_expression_that_zizmor_does_not_read_fails_the_workflow_lint(
    tree: Path,
) -> None:
    broken = CLEAN_WORKFLOW.replace(
        "    steps:", "    if: ${{ github.nope.x }}\n    steps:"
    )
    (tree / ".github" / "workflows" / "broken.yml").write_text(broken, newline="\n")

    result = lint(tree)

    assert result.returncode != 0
    assert 'property "nope" is not defined' in result.stdout + result.stderr


@pytest.mark.parametrize("name", ["docs/ci/gate.sh", "scripts/ci"])
def test_a_shell_script_with_an_unquoted_expansion_fails_the_workflow_lint(
    tree: Path, name: str
) -> None:
    (tree / name).write_text("#!/bin/sh\nrm -rf $1\n", newline="\n")

    result = lint(tree)

    assert result.returncode != 0
    assert "SC2086" in result.stdout + result.stderr


def test_the_check_runs_the_workflow_lint_before_the_fast_exit() -> None:
    text = (ROOT / "scripts" / "ci").read_text(encoding="utf-8")

    assert "scripts/lint-workflows" in text
    assert text.index("scripts/lint-workflows") < text.index('"--fast"')


def test_a_python_script_and_a_directory_in_scripts_are_not_read_as_shell(
    tree: Path,
) -> None:
    (tree / "scripts" / "tool.py").write_text(
        '"""A `quoted` docstring."""\nprint("hi")\n', newline="\n"
    )
    (tree / "scripts" / "__pycache__").mkdir()

    result = lint(tree)

    assert result.returncode == 0, result.stdout + result.stderr
