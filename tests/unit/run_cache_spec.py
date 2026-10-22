import dataclasses

import pytest

from prepush_ci.core.config import Config, Trailer
from prepush_ci.core.run_cache import (
    Key,
    batches,
    expired_refs,
    fingerprint,
    lists_ref,
    message_not_asked,
    message_not_cached,
    message_not_cleaned,
    message_not_cleaned_from_origin,
    message_not_shared,
    message_skipped,
    message_skipped_from_origin,
    passed_commit,
    pushes_to_origin,
    result_message,
    result_ref,
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
TREE = "b" * 40
KEY = Key(TREE, fingerprint(CONFIG, "uv 0.8.1\n"))


def test_the_same_inputs_give_the_same_fingerprint() -> None:
    assert fingerprint(CONFIG, "uv 0.8.1\n") == fingerprint(
        dataclasses.replace(CONFIG), "uv 0.8.1\n"
    )


def test_the_name_of_a_result_ref_leaves_room_in_a_windows_path() -> None:
    # Windows refuses paths of 260 characters; git adds `.lock` to the file of a ref it updates,
    # so the file name of a ref (a 40-hex tree, a dash and the fingerprint) stays under 80.
    name = result_ref(KEY).rsplit("/", 1)[1]
    assert len(name) <= 80


def test_another_check_command_changes_the_fingerprint() -> None:
    assert fingerprint(dataclasses.replace(CONFIG, check="make other"), "") != (
        fingerprint(CONFIG, "")
    )


def test_another_preflight_changes_the_fingerprint() -> None:
    assert fingerprint(dataclasses.replace(CONFIG, preflight=None), "") != (
        fingerprint(CONFIG, "")
    )


def test_other_required_variables_change_the_fingerprint() -> None:
    changed = dataclasses.replace(CONFIG, require_env=("DATABASE_URL", "TOKEN"))

    assert fingerprint(changed, "") != fingerprint(CONFIG, "")


def test_another_up_to_date_ref_changes_the_fingerprint() -> None:
    changed = dataclasses.replace(CONFIG, require_up_to_date=None)

    assert fingerprint(changed, "") != fingerprint(CONFIG, "")


def test_another_output_of_the_preflight_changes_the_fingerprint() -> None:
    assert fingerprint(CONFIG, "uv 0.8.2\n") != fingerprint(CONFIG, "uv 0.8.1\n")


def test_no_output_of_the_preflight_differs_from_some_output() -> None:
    assert fingerprint(CONFIG, "") != fingerprint(CONFIG, "uv 0.8.1\n")


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

    assert fingerprint(changed, "") == fingerprint(CONFIG, "")


def test_values_that_would_run_together_in_a_naive_join_give_different_fingerprints() -> (
    None
):
    one = dataclasses.replace(CONFIG, check="a b", preflight="c")
    other = dataclasses.replace(CONFIG, check="a", preflight="b c")

    assert fingerprint(one, "") != fingerprint(other, "")


def test_output_that_is_no_utf8_still_gives_a_fingerprint() -> None:
    assert len(fingerprint(CONFIG, "a\udcffb")) == 32


def test_a_result_ref_is_the_tree_and_the_config_under_the_results_namespace() -> None:
    assert result_ref(KEY) == f"refs/prepush-ci/results/{TREE}-{KEY.config}"


def test_a_result_ref_depends_on_the_tree_and_on_the_config() -> None:
    names = {
        result_ref(KEY),
        result_ref(dataclasses.replace(KEY, tree="c" * 40)),
        result_ref(dataclasses.replace(KEY, config="0" * 64)),
    }

    assert len(names) == 3


def test_a_result_ref_name_is_hex_apart_from_its_fixed_parts() -> None:
    name = result_ref(KEY).removeprefix("refs/prepush-ci/results/")

    assert set(name) <= set("0123456789abcdef-")


def test_the_message_of_a_result_commit_names_the_commit_that_was_checked() -> None:
    assert result_message("a" * 40) == [
        "prepush-ci: the check passed",
        f"commit {'a' * 40}",
    ]


def test_a_result_commit_of_the_tree_gives_the_commit_it_names() -> None:
    assert passed_commit(f"{TREE}\ncommit {'a' * 40}\n", KEY) == "a" * 40


def test_a_result_commit_of_another_tree_is_a_miss() -> None:
    assert passed_commit(f"{'c' * 40}\ncommit {'a' * 40}\n", KEY) is None


def test_a_result_commit_that_names_no_commit_is_a_miss() -> None:
    assert passed_commit(f"{TREE}\nsomething else\n", KEY) is None


def test_a_result_commit_with_an_empty_message_is_a_miss() -> None:
    assert passed_commit(f"{TREE}\n\n", KEY) is None


def test_no_answer_from_git_is_a_miss() -> None:
    assert passed_commit("", KEY) is None


def test_the_skip_message_names_the_tree_and_the_commit_by_twelve_characters_each() -> (
    None
):
    message = message_skipped("1" * 40, "2" * 40)

    assert "111111111111" in message and "1" * 13 not in message
    assert "222222222222" in message and "2" * 13 not in message
    assert "passed earlier" in message


def test_the_warning_for_an_unwritable_cache_says_the_pass_was_not_cached() -> None:
    message = message_not_cached("[Errno 17] File exists")

    assert "could not be cached" in message
    assert "File exists" in message


def test_the_remote_name_in_the_first_argument_is_origin() -> None:
    assert pushes_to_origin(["origin", "https://example.test/x.git"], {})


def test_another_remote_name_in_the_first_argument_is_not_origin() -> None:
    assert not pushes_to_origin(["upstream", "https://example.test/x.git"], {})


def test_a_url_in_the_first_argument_is_not_origin_whatever_the_url() -> None:
    assert not pushes_to_origin(["../remote.git", "../remote.git"], {})


def test_without_an_argument_the_name_pre_commit_sets_decides() -> None:
    assert pushes_to_origin([], {"PRE_COMMIT_REMOTE_NAME": "origin"})
    assert not pushes_to_origin([], {"PRE_COMMIT_REMOTE_NAME": "upstream"})


def test_the_first_argument_wins_over_the_name_pre_commit_sets() -> None:
    env = {"PRE_COMMIT_REMOTE_NAME": "origin"}

    assert not pushes_to_origin(["upstream", "u"], env)


def test_without_an_argument_and_without_the_pre_commit_name_the_remote_is_unknown() -> (
    None
):
    assert not pushes_to_origin([], {})


LINE = (
    "prepush-ci: the result was not shared through origin ({cause}), "
    "so another clone runs the check again; the push goes on"
)
HTTP_403 = (
    "fatal: unable to access 'http://h/x.git/': The requested URL returned error: 403"
)
RPC_403 = (
    "error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403\n"
    "fatal: expected 'acknowledgments', received 'packfile'"
)
REJECTED = (
    "remote: refusing refs/prepush-ci/results/t-k\n"
    "To /x.git\n"
    " ! [remote rejected] refs/prepush-ci/results/t-k -> refs/prepush-ci/results/t-k "
    "(pre-receive hook declined)\n"
    "error: failed to push some refs to '/x.git'"
)
NOT_A_REPOSITORY = (
    "fatal: '/x.git' does not appear to be a git repository\n"
    "fatal: Could not read from remote repository."
)


def test_the_warning_for_a_result_that_was_not_shared_is_one_line_naming_origin_and_the_cause() -> (
    None
):
    text = message_not_shared(REJECTED)

    assert text == LINE.format(cause="origin rejected the ref")


def test_git_s_lines_stay_out_of_the_warning_for_a_result_that_was_not_shared() -> None:
    text = message_not_shared(REJECTED)

    assert "\n" not in text
    assert not {"fatal:", "error:", "remote:"} & set(text.split())


def test_a_status_from_the_transport_is_the_cause_of_a_result_that_was_not_shared() -> (
    None
):
    for output in (HTTP_403, RPC_403):
        assert message_not_shared(output) == LINE.format(
            cause="origin refused the ref, HTTP 403"
        )


def test_a_failure_without_a_status_is_that_git_could_not_push_it() -> None:
    assert message_not_shared(NOT_A_REPOSITORY) == LINE.format(
        cause="git could not push it"
    )


def test_a_number_that_is_not_a_status_is_not_the_cause_of_a_result_that_was_not_shared() -> (
    None
):
    for output in ("error: 200", "fatal: HTTP 302", "error: 4031", "error: 99"):
        assert message_not_shared(output) == LINE.format(cause="git could not push it")


def test_a_status_wins_over_a_rejected_line() -> None:
    assert "HTTP 502" in message_not_shared(REJECTED + "\nerror: RPC failed; HTTP 502")


def test_a_status_in_the_remote_s_own_text_is_not_the_cause_of_a_result_that_was_not_shared() -> (
    None
):
    output = (
        "remote: error: 500 files are over the limit\n"
        " ! [remote rejected] main -> refs/prepush-ci/results/t-k (pre-receive hook declined)"
    )

    assert message_not_shared(output) == LINE.format(cause="origin rejected the ref")


@pytest.mark.parametrize(
    "separator",
    [
        pytest.param("\v", id="vertical-tab"),
        pytest.param("\f", id="form-feed"),
        pytest.param("\x1c", id="file-separator"),
        pytest.param("\x85", id="next-line"),
        pytest.param("\u2028", id="line-separator"),
    ],
)
def test_a_status_after_a_line_separator_in_the_remote_s_own_text_is_not_the_cause_of_a_result_that_was_not_shared(
    separator: str,
) -> None:
    output = (
        f"remote: hello{separator}error: 500 files are over the limit\n"
        " ! [remote rejected] main -> refs/prepush-ci/results/t-k (pre-receive hook declined)"
    )

    assert message_not_shared(output) == LINE.format(cause="origin rejected the ref")


def test_the_line_for_a_result_from_origin_names_origin_the_tree_and_the_commit() -> (
    None
):
    text = message_skipped_from_origin("t" * 40, "c" * 40)

    assert "origin" in text
    assert "t" * 12 in text
    assert "c" * 12 in text
    assert "t" * 13 not in text


def test_the_line_for_a_local_result_does_not_name_origin() -> None:
    assert "origin" not in message_skipped("t" * 40, "c" * 40)


def test_the_warning_for_a_lookup_that_failed_names_origin_and_the_reason() -> None:
    text = message_not_asked("no route")

    assert "origin" in text
    assert "no route" in text
    assert "could not be asked" in text


def test_a_listing_that_holds_the_ref_lists_it() -> None:
    ref = result_ref(KEY)

    assert lists_ref(f"{'a' * 40}\t{ref}\n", ref)


def test_an_empty_listing_does_not_list_the_ref() -> None:
    assert not lists_ref("", result_ref(KEY))


def test_a_ref_that_only_ends_like_the_ref_is_not_the_ref() -> None:
    ref = result_ref(KEY)

    assert not lists_ref(f"{'a' * 40}\trefs/heads/x/{ref}\n", ref)


NOW = 1_800_000_000
DAY = 24 * 60 * 60


def listed(**ages: int) -> str:
    """What `git for-each-ref --format='%(refname) %(committerdate:unix)'` prints, for refs whose
    commits are `ages` days old."""
    return "".join(f"{name} {NOW - days * DAY}\n" for name, days in ages.items())


def test_a_result_older_than_30_days_is_expired() -> None:
    assert expired_refs(listed(old=31), NOW) == ["old"]


def test_a_result_of_exactly_30_days_is_kept() -> None:
    assert expired_refs(listed(edge=30), NOW) == []


def test_a_result_of_29_days_is_kept() -> None:
    assert expired_refs(listed(recent=29), NOW) == []


def test_a_result_dated_in_the_future_is_kept() -> None:
    assert expired_refs(listed(future=-1), NOW) == []


def test_only_the_old_results_of_a_listing_are_expired() -> None:
    listing = listed(a=40, b=3, c=31)

    assert expired_refs(listing, NOW) == ["a", "c"]


def test_a_line_without_a_date_is_kept() -> None:
    assert expired_refs(f"refs/x \n{listed(old=31)}refs/y\nrefs/z nan\n", NOW) == [
        "old"
    ]


def test_an_empty_listing_expires_nothing() -> None:
    assert expired_refs("", NOW) == []


def test_refs_are_split_into_batches_of_a_hundred() -> None:
    refs = [f"r{number}" for number in range(250)]

    assert [len(batch) for batch in batches(refs)] == [100, 100, 50]


def test_no_refs_make_no_batch() -> None:
    assert batches([]) == []


def test_the_warning_for_a_cleanup_that_failed_gives_the_reason() -> None:
    text = message_not_cleaned("locked")

    assert "old results could not be removed" in text
    assert "locked" in text
    assert "origin" not in text


def test_the_warning_for_a_cleanup_of_origin_that_failed_names_origin_and_the_reason() -> (
    None
):
    text = message_not_cleaned_from_origin("declined")

    assert "origin" in text
    assert "old results could not be removed" in text
    assert "declined" in text
