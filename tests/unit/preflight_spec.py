from prepush_ci.core.preflight import (
    fetch_refspec,
    message_bad_ref,
    message_fetch_failed,
    message_merge_base_failed,
    message_missing_env,
    message_no_remote,
    message_not_up_to_date,
    message_preflight_failed,
    missing_env,
    split_ref,
)


def test_a_variable_that_is_set_to_a_value_is_not_missing() -> None:
    assert missing_env(["DATABASE_URL"], {"DATABASE_URL": "postgres://x"}) == []


def test_an_unset_variable_is_missing() -> None:
    assert missing_env(["DATABASE_URL"], {"OTHER": "x"}) == ["DATABASE_URL"]


def test_an_empty_variable_is_missing() -> None:
    assert missing_env(["DATABASE_URL"], {"DATABASE_URL": ""}) == ["DATABASE_URL"]


def test_every_missing_variable_is_listed_in_the_configured_order() -> None:
    assert missing_env(["A_URL", "B_URL", "C_URL"], {"B_URL": "x"}) == [
        "A_URL",
        "C_URL",
    ]


def test_no_required_variables_means_none_missing() -> None:
    assert missing_env([], {}) == []


def test_the_message_for_missing_variables_names_all_of_them() -> None:
    message = message_missing_env(["A_URL", "B_URL"])

    assert "A_URL" in message and "B_URL" in message
    assert "fetch" not in message


def test_a_ref_is_split_at_the_first_slash_into_remote_and_branch() -> None:
    assert split_ref("origin/main") == ("origin", "main")
    assert split_ref("origin/release/1") == ("origin", "release/1")


def test_a_ref_without_a_remote_or_a_branch_does_not_split() -> None:
    for ref in ("main", "/main", "origin/", "/", ""):
        assert split_ref(ref) is None


def test_the_fetch_refspec_updates_the_remote_tracking_ref() -> None:
    assert fetch_refspec("origin", "release/1") == (
        "+refs/heads/release/1:refs/remotes/origin/release/1"
    )


def test_the_refusal_for_a_branch_that_is_behind_names_the_ref_and_says_rebase_or_merge() -> (
    None
):
    message = message_not_up_to_date("origin/main")

    assert "origin/main" in message
    assert "rebase" in message and "merge" in message


def test_the_refusal_for_a_failed_fetch_says_so_and_names_git_s_reason_and_two_ways_out() -> (
    None
):
    message = message_fetch_failed("origin/main", "fatal: no such remote ref")

    assert "fetch" in message and "origin/main" in message
    assert "fatal: no such remote ref" in message
    assert "require_up_to_date = false" in message
    assert "without the trailer" in message


def test_the_refusal_for_a_ref_without_a_remote_says_it_must_be_remote_slash_branch() -> (
    None
):
    message = message_bad_ref("main")

    assert "main" in message
    assert "<remote>/<branch>" in message
    assert "require_up_to_date = false" in message
    assert "without the trailer" in message


def test_the_refusal_for_an_unknown_remote_names_it() -> None:
    message = message_no_remote("upstream", "upstream/develop")

    assert "upstream" in message
    assert "require_up_to_date = false" in message
    assert "without the trailer" in message


def test_the_refusal_for_a_failed_merge_base_names_the_ref_and_the_cause() -> None:
    message = message_merge_base_failed("origin/main", "fatal: bad object")

    assert "origin/main" in message
    assert "fatal: bad object" in message
    assert "require_up_to_date = false" in message


def test_the_refusal_for_a_failing_preflight_names_the_command_and_the_status() -> None:
    message = message_preflight_failed("./ready.sh", 3)

    assert "./ready.sh" in message
    assert "3" in message
