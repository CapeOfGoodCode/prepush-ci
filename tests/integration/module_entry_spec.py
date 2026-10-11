import subprocess
import sys


def test_python_dash_m_prepush_ci_runs_the_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("prepush-ci ")
