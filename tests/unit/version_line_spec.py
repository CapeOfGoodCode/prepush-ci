import errno
import json
import sys
from importlib.metadata import PathDistribution
from pathlib import Path

import pytest

from prepush_ci.version_line import version_line

COMMIT = "7a42451df0fd6a1b2c3d4e5f60718293a4b5c6d7"


def installed(tmp_path: Path, record: bytes | None) -> PathDistribution:
    """A distribution as an installer leaves it: a `.dist-info` directory with its record."""
    info = tmp_path / "prepush_ci-9.8.7.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: prepush-ci\nVersion: 9.8.7\n"
    )
    if record is not None:
        (info / "direct_url.json").write_bytes(record)
    return PathDistribution(info)


def test_the_line_of_a_package_from_an_index_is_the_bare_version(
    tmp_path: Path,
) -> None:
    assert version_line(installed(tmp_path, None)) == "prepush-ci 9.8.7"


def test_the_line_of_a_build_from_git_names_its_commit(tmp_path: Path) -> None:
    record = json.dumps({"vcs_info": {"vcs": "git", "commit_id": COMMIT}})

    line = version_line(installed(tmp_path, record.encode()))

    assert line == "prepush-ci 9.8.7 (git 7a42451df0fd)"


def test_the_line_of_a_build_from_a_directory_is_a_direct_install(
    tmp_path: Path,
) -> None:
    record = b'{"url": "file:///home/someone/p", "dir_info": {"editable": true}}'

    assert (
        version_line(installed(tmp_path, record)) == "prepush-ci 9.8.7 (direct install)"
    )


@pytest.mark.parametrize("record", [b"\xff\xfe\x00\x80", '{"é": 1}'.encode("latin-1")])
def test_a_record_whose_bytes_are_not_utf_8_is_no_record(
    tmp_path: Path, record: bytes
) -> None:
    assert version_line(installed(tmp_path, record)) == "prepush-ci 9.8.7"


def test_a_record_with_two_keys_prints_one_line_and_does_not_fail(
    tmp_path: Path,
) -> None:
    record = b'{"vcs_info": null, "dir_info": {}}'

    assert version_line(installed(tmp_path, record)) == "prepush-ci 9.8.7"


def test_a_record_that_is_a_directory_is_no_record(tmp_path: Path) -> None:
    distribution = installed(tmp_path, None)
    (tmp_path / "prepush_ci-9.8.7.dist-info" / "direct_url.json").mkdir()

    assert version_line(distribution) == "prepush-ci 9.8.7"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows symlinks need a privilege")
def test_the_line_of_a_record_that_loops_back_on_itself_is_the_bare_version(
    tmp_path: Path,
) -> None:
    distribution = installed(tmp_path, None)
    record = tmp_path / "prepush_ci-9.8.7.dist-info" / "direct_url.json"
    record.symlink_to(record.name)

    assert version_line(distribution) == "prepush-ci 9.8.7"


def test_the_line_of_a_record_the_disk_fails_to_read_is_the_bare_version(
    tmp_path: Path,
) -> None:
    class FailingDisk(PathDistribution):
        def read_text(self, filename: str) -> str | None:
            if filename == "direct_url.json":
                raise OSError(errno.EIO, "Input/output error")
            return super().read_text(filename)

    installed(tmp_path, None)

    distribution = FailingDisk(tmp_path / "prepush_ci-9.8.7.dist-info")

    assert version_line(distribution) == "prepush-ci 9.8.7"
