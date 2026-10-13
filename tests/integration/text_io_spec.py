import os
import subprocess
import sys

import pytest

ASCII = {"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}

CODE = """
import sys
from prepush_ci import text_io

assert sys.getfilesystemencoding() == "ascii", sys.getfilesystemencoding()
os_string = text_io.to_os("or\\u00e9")
print(text_io.from_os(os_string) == "or\\u00e9", text_io.from_os(text_io.to_os("x\\udcff")) == "x\\udcff")
"""


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no ASCII file system encoding: its strings are UTF-8",
)
def test_the_tools_text_survives_the_operating_systems_strings_under_an_ascii_file_system_encoding() -> (
    None
):
    done = subprocess.run(
        [sys.executable, "-c", CODE],
        env={**os.environ, **ASCII},
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["True", "True"]
