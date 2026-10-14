"""`scripts/check-wheel`: the built package is installed in an empty environment, started and made to
read its data files, so a module, an entry point or a data file that the wheel lacks fails
`scripts/ci` and not the user of `uvx`."""

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-wheel"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A copy of what the wheel is built from: the project file, the readme, the package and the skill."""
    copy = tmp_path / "source"
    copy.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy(ROOT / name, copy / name)
    shutil.copytree(
        ROOT / "src", copy / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(ROOT / "skills", copy / "skills")
    return copy


def check(source: Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        ["sh", SCRIPT.as_posix(), source.as_posix()],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_built_wheel_starts_in_an_empty_environment(source: Path) -> None:
    result = check(source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"prepush-ci {VERSION}" in result.stdout


def test_a_module_missing_from_the_package_fails_the_wheel_check(source: Path) -> None:
    (source / "src" / "prepush_ci" / "install_command.py").unlink()

    result = check(source)

    assert result.returncode != 0
    assert "install_command" in result.stdout + result.stderr


def test_a_missing_entry_point_fails_the_wheel_check(source: Path) -> None:
    project = source / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8").replace(
            'prepush-ci = "prepush_ci.cli:main"', 'other = "prepush_ci.cli:main"'
        ),
        encoding="utf-8",
        newline="\n",
    )

    result = check(source)

    assert result.returncode != 0
    assert "prepush-ci" in result.stdout + result.stderr


@pytest.mark.parametrize("name", ["gate.sh", "github-actions.yml", "gitlab-ci.yml"])
def test_a_data_file_missing_from_the_package_fails_the_wheel_check(
    source: Path, name: str
) -> None:
    (source / "src" / "prepush_ci" / "ci_gates" / name).unlink()

    result = check(source)

    assert result.returncode != 0
    assert name in result.stdout + result.stderr


def test_the_check_builds_and_starts_the_wheel_after_the_tests() -> None:
    text = (ROOT / "scripts" / "ci").read_text(encoding="utf-8")

    assert "scripts/check-wheel" in text
    assert text.index("scripts/check-wheel") > text.index(
        "coverage report --fail-under=95"
    )
    assert text.index("scripts/check-wheel") < text.index("==> full check passed")
