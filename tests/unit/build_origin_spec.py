import json

import pytest

from prepush_ci.core.build_origin import origin_suffix

COMMIT = "7a42451df0fd6a1b2c3d4e5f60718293a4b5c6d7"


def git_record(**vcs_info: object) -> str:
    return json.dumps(
        {
            "url": "https://github.com/CapeOfGoodCode/prepush-ci",
            "vcs_info": {"vcs": "git", **vcs_info},
        }
    )


def test_an_install_from_git_names_the_first_12_characters_of_the_commit() -> None:
    assert origin_suffix(git_record(commit_id=COMMIT)) == " (git 7a42451df0fd)"


def test_an_install_from_an_index_has_no_record_and_no_suffix() -> None:
    assert origin_suffix(None) == ""


def test_a_short_commit_is_kept_whole() -> None:
    assert origin_suffix(git_record(commit_id="7a42451")) == " (git 7a42451)"


@pytest.mark.parametrize("editable", [True, False])
def test_a_directory_install_is_a_direct_install_without_its_path(
    editable: bool,
) -> None:
    record = json.dumps(
        {"url": "file:///home/someone/prepush-ci", "dir_info": {"editable": editable}}
    )

    assert origin_suffix(record) == " (direct install)"


def test_an_archive_install_is_a_direct_install_without_its_url() -> None:
    record = json.dumps(
        {"url": "https://user:secret@example.invalid/p.whl", "archive_info": {}}
    )

    assert origin_suffix(record) == " (direct install)"


def test_another_repository_system_is_a_direct_install() -> None:
    record = json.dumps(
        {
            "url": "https://example.invalid/r",
            "vcs_info": {"vcs": "hg", "commit_id": "7a42451df0fd6a1b"},
        }
    )

    assert origin_suffix(record) == " (direct install)"


def test_a_git_record_without_a_commit_is_a_direct_install() -> None:
    assert origin_suffix(git_record()) == " (direct install)"


def test_a_repository_system_that_is_not_a_string_is_a_direct_install() -> None:
    record = json.dumps(
        {
            "url": "https://example.invalid/r",
            "vcs_info": {"vcs": 1, "commit_id": "7a42451df0fd6a1b"},
        }
    )

    assert origin_suffix(record) == " (direct install)"


@pytest.mark.parametrize(
    "commit", [42, None, ["7a42451"], {"id": "7a42451"}, "", "7a42451\nfake", "7a4\n"]
)
def test_a_commit_that_is_not_a_string_of_hex_digits_is_a_direct_install(
    commit: object,
) -> None:
    assert origin_suffix(git_record(commit_id=commit)) == " (direct install)"


def test_a_commit_in_capitals_is_a_hex_string() -> None:
    assert origin_suffix(git_record(commit_id="7A42451DF0FD6A1B")) == (
        " (git 7A42451DF0FD)"
    )


def test_a_commit_of_digits_other_than_ascii_is_not_hex() -> None:
    assert origin_suffix(git_record(commit_id="٣٣٣٣")) == " (direct install)"


@pytest.mark.parametrize(
    "record",
    [
        "{not json",
        "",
        "[]",
        '"git"',
        "42",
        "null",
        '{"url": "https://example.invalid/p"}',
        '{"vcs_info": null}',
        '{"vcs_info": "git"}',
        '{"dir_info": []}',
        '{"dir_info": "editable"}',
        '{"archive_info": 1}',
        '{"vcs_info": null, "dir_info": {}}',
        '{"vcs_info": {"vcs": "git", "commit_id": "7a42451"}, "dir_info": 1}',
        pytest.param("[" * 100_000, id="nesting_too_deep"),
        pytest.param(
            '{"vcs_info": {"vcs": "git", "commit_id": ' + "9" * 5000 + "}}",
            id="number_of_5000_digits",
        ),
    ],
)
def test_an_unreadable_record_is_no_record(record: str) -> None:
    assert origin_suffix(record) == ""
