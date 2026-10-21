"""`prepush-ci --version` from a source checkout and from an installed wheel with the record each
installer leaves (or none)."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.starts_the_cli  # it runs the installed script

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "7a42451df0fd6a1b2c3d4e5f60718293a4b5c6d7"
VERSION = r"\d+\.\d+\.\d+\S*"


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The `prepush-ci` command of a new virtual environment holding only the wheel of this
    repository; the record of its distribution is the one `uv pip install` of a wheel file wrote."""
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        ["uv", "build", "--wheel", "--quiet", "--out-dir", str(out), str(ROOT)],
        check=True,
        capture_output=True,
    )
    venv = tmp_path_factory.mktemp("env") / "venv"
    subprocess.run(["uv", "venv", "--quiet", str(venv)], check=True)
    wheel = next(out.glob("*.whl"))
    subprocess.run(
        ["uv", "pip", "install", "--quiet", "--python", str(venv), str(wheel)],
        check=True,
    )
    scripts = venv / ("Scripts" if (venv / "Scripts").is_dir() else "bin")
    return scripts / "prepush-ci"


def record_of(command: Path) -> Path:
    """The installation record of the distribution `command` belongs to (may not exist)."""
    venv = command.parent.parent
    (info,) = venv.glob("**/site-packages/prepush_ci-*.dist-info")
    return info / "direct_url.json"


def version_with(
    command: Path, record: bytes | None, columns: int | None = None
) -> "subprocess.CompletedProcess[bytes]":
    path = record_of(command)
    if record is None:
        path.unlink(missing_ok=True)
    else:
        path.write_bytes(record)
    env = os.environ if columns is None else {**os.environ, "COLUMNS": str(columns)}
    return subprocess.run(
        [str(command), "--version"], capture_output=True, check=False, env=env
    )


def test_a_source_checkout_prints_its_version_and_that_it_is_a_direct_install() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(rf"prepush-ci {VERSION} \(direct install\)\n", result.stdout)


def test_a_wheel_file_install_is_a_direct_install(installed: Path) -> None:
    path = record_of(installed)
    assert path.exists()  # written by uv for the wheel file
    result = subprocess.run(
        [str(installed), "--version"], capture_output=True, text=True, check=False
    )

    assert re.fullmatch(rf"prepush-ci {VERSION} \(direct install\)\n", result.stdout)


def test_an_install_from_git_names_the_commit(installed: Path) -> None:
    record = json.dumps(
        {
            "url": "https://github.com/CapeOfGoodCode/prepush-ci",
            "vcs_info": {"vcs": "git", "commit_id": COMMIT},
        }
    ).encode()

    result = version_with(installed, record)

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(
        rf"prepush-ci {VERSION} \(git 7a42451df0fd\)\r?\n", result.stdout.decode()
    )
    assert result.stderr == b""


def test_the_line_stays_one_line_in_a_narrow_terminal(installed: Path) -> None:
    record = json.dumps({"vcs_info": {"vcs": "git", "commit_id": COMMIT}}).encode()

    result = version_with(installed, record, columns=20)

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(
        rf"prepush-ci {VERSION} \(git 7a42451df0fd\)\r?\n", result.stdout.decode()
    )


def test_a_source_checkout_stays_one_line_in_a_narrow_terminal() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "--version"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "COLUMNS": "20"},
    )

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(rf"prepush-ci {VERSION} \(direct install\)\n", result.stdout)


def test_an_install_from_an_index_prints_the_bare_version(installed: Path) -> None:
    result = version_with(installed, None)

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(rf"prepush-ci {VERSION}\r?\n", result.stdout.decode())
    assert result.stderr == b""


@pytest.mark.parametrize(
    "record",
    [b"{not json", b"[]", b"\xff\xfe\x00\x80", b'{"vcs_info": null, "dir_info": {}}'],
    ids=["invalid_json", "not_an_object", "not_utf_8", "two_keys"],
)
def test_an_unreadable_record_prints_the_bare_version_and_nothing_on_stderr(
    installed: Path, record: bytes
) -> None:
    result = version_with(installed, record)

    assert result.returncode == 0, result.stderr
    assert re.fullmatch(rf"prepush-ci {VERSION}\r?\n", result.stdout.decode())
    assert result.stderr == b""
