"""The wheel and the source distribution carry the skill file of the repository."""

import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "prepush-ci-setup" / "SKILL.md"
PROJECT_SKILL = Path(".claude") / "skills" / "prepush-ci-setup" / "SKILL.md"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`uv build` of the repository as the release does it: the sdist, then the wheel from it."""
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        ["uv", "build", "--quiet", "--out-dir", str(out), str(ROOT)],
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="module")
def installed(built: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The `prepush-ci` command of a new virtual environment holding only that wheel."""
    venv = tmp_path_factory.mktemp("env") / "venv"
    subprocess.run(["uv", "venv", "--quiet", str(venv)], check=True)
    wheel = next(built.glob("*.whl"))
    subprocess.run(
        ["uv", "pip", "install", "--quiet", "--python", str(venv), str(wheel)],
        check=True,
    )
    scripts = venv / ("Scripts" if (venv / "Scripts").is_dir() else "bin")
    return scripts / "prepush-ci"


def test_the_installed_wheel_prints_the_skill_of_the_repository(
    installed: Path, tmp_path: Path
) -> None:
    result = subprocess.run(
        [str(installed), "skill"], cwd=tmp_path, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == SKILL.read_bytes()


def test_the_source_distribution_carries_the_skill(built: Path) -> None:
    sdist = next(built.glob("*.tar.gz"))
    with tarfile.open(sdist) as archive:
        names = archive.getnames()

    assert any(name.endswith("/skills/prepush-ci-setup/SKILL.md") for name in names)


def test_the_installed_wheel_writes_the_skill_of_the_repository(
    installed: Path, repo: Path
) -> None:
    result = subprocess.run(
        [str(installed), "skill", "--write"],
        cwd=repo,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (repo / PROJECT_SKILL).read_bytes() == SKILL.read_bytes()
