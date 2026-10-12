import dataclasses

from prepush_ci.core.config import Config, Trailer
from prepush_ci.core.run_cache import (
    Key,
    fingerprint,
    is_pass_for,
    message_not_cached,
    message_skipped,
    pass_record,
    record_name,
)

CONFIG = Config(
    check="make test",
    preflight="make up",
    require_env=("DATABASE_URL",),
    require_up_to_date="origin/main",
    default_branch="main",
    trailer=Trailer("Prepush-CI", "full"),
    legacy_keys=(),
    cache=True,
)
KEY = Key("a" * 40, "b" * 40, fingerprint(CONFIG))


def test_the_same_config_values_give_the_same_fingerprint() -> None:
    assert fingerprint(CONFIG) == fingerprint(dataclasses.replace(CONFIG))


def test_another_check_command_changes_the_fingerprint() -> None:
    assert fingerprint(dataclasses.replace(CONFIG, check="make other")) != fingerprint(
        CONFIG
    )


def test_another_preflight_changes_the_fingerprint() -> None:
    assert fingerprint(dataclasses.replace(CONFIG, preflight=None)) != fingerprint(
        CONFIG
    )


def test_other_required_variables_change_the_fingerprint() -> None:
    changed = dataclasses.replace(CONFIG, require_env=("DATABASE_URL", "TOKEN"))

    assert fingerprint(changed) != fingerprint(CONFIG)


def test_another_up_to_date_ref_changes_the_fingerprint() -> None:
    assert fingerprint(
        dataclasses.replace(CONFIG, require_up_to_date=None)
    ) != fingerprint(CONFIG)


def test_keys_that_do_not_change_what_a_pass_means_leave_the_fingerprint_alone() -> (
    None
):
    changed = dataclasses.replace(
        CONFIG,
        default_branch="trunk",
        trailer=Trailer("Checked", "yes"),
        legacy_keys=("Old",),
        cache=False,
    )

    assert fingerprint(changed) == fingerprint(CONFIG)


def test_values_that_would_run_together_in_a_naive_join_give_different_fingerprints() -> (
    None
):
    one = dataclasses.replace(CONFIG, check="a b", preflight="c")
    other = dataclasses.replace(CONFIG, check="a", preflight="b c")

    assert fingerprint(one) != fingerprint(other)


def test_the_record_of_a_pass_is_intact_for_its_own_key() -> None:
    assert is_pass_for(pass_record(KEY), KEY)


def test_the_record_of_a_pass_names_the_commit_and_the_tree() -> None:
    assert KEY.sha in pass_record(KEY) and KEY.tree in pass_record(KEY)


def test_a_missing_record_is_not_a_pass() -> None:
    assert not is_pass_for(None, KEY)


def test_an_empty_record_is_not_a_pass() -> None:
    assert not is_pass_for("", KEY)


def test_a_truncated_record_is_not_a_pass() -> None:
    record = pass_record(KEY)

    assert not is_pass_for(record[: len(record) // 2], KEY)


def test_a_record_for_another_commit_is_not_a_pass() -> None:
    other = dataclasses.replace(KEY, sha="c" * 40)

    assert not is_pass_for(pass_record(other), KEY)


def test_a_record_for_another_tree_is_not_a_pass() -> None:
    other = dataclasses.replace(KEY, tree="c" * 40)

    assert not is_pass_for(pass_record(other), KEY)


def test_a_record_for_another_fingerprint_is_not_a_pass() -> None:
    other = dataclasses.replace(KEY, fingerprint="0" * 64)

    assert not is_pass_for(pass_record(other), KEY)


def test_a_record_is_filed_by_a_name_that_is_safe_and_depends_on_the_whole_key() -> (
    None
):
    names = {
        record_name(KEY),
        record_name(dataclasses.replace(KEY, sha="c" * 40)),
        record_name(dataclasses.replace(KEY, tree="c" * 40)),
        record_name(dataclasses.replace(KEY, fingerprint="0" * 64)),
    }

    assert len(names) == 4
    assert all(name.isalnum() for name in names)


def test_the_skip_message_names_the_commit_and_says_the_check_passed_earlier() -> None:
    message = message_skipped("a" * 40)

    assert "aaaaaaaaaaaa" in message
    assert "passed earlier" in message


def test_the_warning_for_an_unwritable_cache_says_the_pass_was_not_cached() -> None:
    message = message_not_cached("[Errno 17] File exists")

    assert "could not be cached" in message
    assert "File exists" in message
