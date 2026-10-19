import dataclasses

from prepush_ci.core.config import Config, Trailer
from prepush_ci.core.run_cache import (
    Key,
    fingerprint,
    message_not_cached,
    message_skipped,
    passed_commit,
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
