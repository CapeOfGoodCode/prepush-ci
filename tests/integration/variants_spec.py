"""The two variants every integration spec runs in: `utf8` as always, and a hostile `ascii`."""

import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).parent
MODULE = (
    "prepush" + "_ci"
)  # not spelled out, or the regex of conftest.py would match this file


def collect(directory: Path, *files: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--import-mode=importlib",
            *files,
        ],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
        env={k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")},
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A directory with this directory's `conftest.py` and small specs of the three kinds."""
    where = tmp_path / "specs"
    where.mkdir()
    shutil.copy(HERE / "conftest.py", where / "conftest.py")
    (where / "repo_spec.py").write_text(
        "def test_uses_a_repository(repo): pass\n", encoding="utf-8"
    )
    (where / "cli_spec.py").write_text(
        "import subprocess, sys\n\n"
        "def test_starts_the_cli():\n"
        f'    subprocess.run([sys.executable, "-m", "{MODULE}"], check=False)\n',
        encoding="utf-8",
    )
    (where / "plain_spec.py").write_text("def test_plain(): pass\n", encoding="utf-8")
    return where


def ids(output: str) -> list[str]:
    return [line for line in output.splitlines() if "::" in line]


def test_both_variants_run(sandbox: Path) -> None:
    listing = collect(
        sandbox, "--collect-only", "repo_spec.py", "cli_spec.py", "plain_spec.py"
    )

    found = ids(listing.stdout)
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert sorted(found) == sorted(
        [
            "repo_spec.py::test_uses_a_repository[utf8]",
            "repo_spec.py::test_uses_a_repository[ascii]",
            "cli_spec.py::test_starts_the_cli[utf8]",
            "cli_spec.py::test_starts_the_cli[ascii]",
            "plain_spec.py::test_plain",
        ]
    )


def test_a_command_that_cannot_run_under_the_variant_fails_the_suite(
    sandbox: Path,
) -> None:
    (sandbox / "breaks_spec.py").write_text(
        textwrap.dedent(
            """
            import os

            def test_a_command_that_breaks_under_an_ascii_locale(repo):
                assert os.environ.get("LC_ALL") != "C", "Traceback (most recent call last)"
            """
        ),
        encoding="utf-8",
    )

    done = collect(sandbox, "-rs", "breaks_spec.py")

    assert "1 failed, 1 passed" in done.stdout, done.stdout
    assert "skipped" not in done.stdout


def test_the_ascii_variant_is_hostile(repo: Path, variant: str) -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, sys; print(sys.getfilesystemencoding(), os.environ.get('LC_ALL'),"
            " os.environ.get('PYTHONUTF8'), os.environ.get('PYTHONCOERCECLOCALE'))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    if variant == "ascii":
        assert not repo.as_posix().isascii()
        encoding = (
            "utf-8" if sys.platform == "win32" else "ascii"
        )  # no ASCII strings on Windows
        assert probe.stdout.split() == [encoding, "C", "0", "0"]
    else:
        assert probe.stdout.split()[1:] != ["C", "0", "0"]


# --- A spec starts the CLI by what it does, not by how its source spells it ----------------------

ROOT = HERE.parents[1]
HAS_A_VARIANT = re.compile(r"\[(?:[^\]]*-)?(utf8|ascii)(?:-[^\]]*)?\]$")
STARTED_ANOTHER_WAY = re.compile(r'scripts / "prepush-ci"|record' + "_demo")


def test_a_spec_that_starts_the_cli_another_way_has_both_variants() -> None:
    listing = collect(
        ROOT,
        "--collect-only",
        "tests/integration/skill_wheel_spec.py",
        "tests/integration/demo_spec.py",
    )

    found = ids(listing.stdout)
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert found
    for name in found:
        assert HAS_A_VARIANT.search(name), name
    bases = {HAS_A_VARIANT.sub("", name) for name in found}
    assert len(found) == 2 * len(bases)


def test_no_spec_starts_the_cli_without_a_variant() -> None:
    unmarked = [
        path.name
        for path in sorted(HERE.glob("*_spec.py"))
        if path.name != Path(__file__).name
        for source in [path.read_text(encoding="utf-8")]
        if STARTED_ANOTHER_WAY.search(source) and "starts_the_cli" not in source
    ]

    assert unmarked == []
