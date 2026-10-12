from prepush_ci.core.config import Config, Trailer
from prepush_ci.core.verify import (
    Verdict,
    invalid_config,
    no_config,
    render,
    server_made,
    trailer_verdict,
    unreadable,
    unresolved,
    usage_problem,
)

SHA = "a" * 40


def config(key: str = "Prepush-CI", legacy: tuple[str, ...] = ()) -> Config:
    return Config(
        check="true",
        preflight=None,
        require_env=(),
        require_up_to_date=None,
        default_branch="main",
        trailer=Trailer(key, "full"),
        legacy_keys=legacy,
        cache=True,
    )


def test_a_trailer_with_the_configured_key_verifies_and_the_reason_names_it() -> None:
    verdict = trailer_verdict("Prepush-CI: full\n", config())

    assert verdict.verified
    assert "Prepush-CI: full" in verdict.reason


def test_a_trailer_key_in_another_case_verifies() -> None:
    assert trailer_verdict("prepush-ci: full\n", config()).verified


def test_any_value_of_the_trailer_verifies() -> None:
    verdict = trailer_verdict("Prepush-CI: off\n", config())

    assert verdict.verified
    assert "Prepush-CI: off" in verdict.reason


def test_a_legacy_key_verifies_and_the_reason_names_it() -> None:
    verdict = trailer_verdict(
        "Full-Pre-Push: required\n", config(legacy=("Full-Pre-Push",))
    )

    assert verdict.verified
    assert "Full-Pre-Push" in verdict.reason


def test_the_default_key_does_not_verify_under_a_configured_key() -> None:
    verdict = trailer_verdict("Prepush-CI: full\n", config("Full-Check"))

    assert not verdict.verified
    assert "full-check" in verdict.reason


def test_a_commit_without_trailers_does_not_verify_and_the_reason_says_there_is_none() -> (
    None
):
    verdict = trailer_verdict("", config())

    assert not verdict.verified
    assert "no trailer" in verdict.reason


def test_a_server_committer_never_verifies_and_the_reason_names_the_address() -> None:
    for email in ("noreply@github.com", "noreply@gitlab.com"):
        verdict = server_made(email)

        assert verdict is not None
        assert not verdict.verified
        assert email in verdict.reason


def test_a_server_committer_in_another_case_is_still_a_server() -> None:
    assert server_made("NoReply@GitHub.com") is not None


def test_a_user_address_is_not_a_server() -> None:
    assert server_made("me@example.com") is None


def test_the_private_github_address_of_a_user_is_not_a_server() -> None:
    assert server_made("123+u@users.noreply.github.com") is None


def test_an_address_that_only_ends_in_a_server_address_is_not_a_server() -> None:
    assert server_made("x-noreply@github.com") is None
    assert server_made("noreply@github.com.example.org") is None


def test_the_line_of_a_verified_commit_starts_with_verified_and_the_full_sha() -> None:
    assert render(Verdict(True, "has it"), SHA) == f"verified: {SHA} has it"


def test_the_line_of_a_refused_commit_starts_with_not_verified() -> None:
    assert render(Verdict(False, "nope"), SHA) == f"not verified: {SHA} nope"


def test_a_line_without_a_sha_has_no_empty_field() -> None:
    assert render(Verdict(False, "the sha is missing"), None) == (
        "not verified: the sha is missing"
    )


def test_a_sha_with_control_characters_is_shown_escaped_so_the_line_stays_one() -> None:
    line = render(Verdict(False, "nope"), "a\nb")

    assert "\n" not in line
    assert "a\\nb" in line


def test_no_argument_is_a_usage_problem_that_says_the_sha_is_missing() -> None:
    problem = usage_problem([])

    assert problem is not None
    assert "missing" in problem


def test_an_empty_argument_is_a_usage_problem() -> None:
    problem = usage_problem([""])

    assert problem is not None
    assert "empty" in problem


def test_extra_arguments_are_a_usage_problem_that_counts_them() -> None:
    problem = usage_problem(["HEAD", "HEAD~1"])

    assert problem is not None
    assert "2" in problem


def test_one_argument_is_no_usage_problem() -> None:
    assert usage_problem(["HEAD"]) is None


def test_an_unknown_sha_in_a_complete_repository_says_to_fetch_it_from_origin() -> None:
    reason = unresolved(SHA, shallow=False).reason

    assert SHA in reason
    assert f"git fetch origin {SHA}" in reason


def test_an_unknown_sha_in_a_shallow_clone_says_to_unshallow_or_deepen_the_checkout() -> (
    None
):
    reason = unresolved(SHA, shallow=True).reason

    assert SHA in reason
    assert "git fetch --unshallow" in reason
    assert "fetch-depth" in reason


def test_a_commit_without_a_config_does_not_verify_and_the_reason_says_so() -> None:
    verdict = no_config()

    assert not verdict.verified
    assert "no config" in verdict.reason


def test_an_invalid_committed_config_does_not_verify_and_the_reason_lists_the_problems() -> (
    None
):
    verdict = invalid_config(["unknown key `chek`", "`cache` must be true or false"])

    assert not verdict.verified
    assert "unknown key `chek`" in verdict.reason
    assert "`cache` must be true or false" in verdict.reason


def test_a_failure_to_read_git_does_not_verify_and_the_reason_passes_the_message_on() -> (
    None
):
    verdict = unreadable("cannot read the message of abc")

    assert not verdict.verified
    assert "cannot read the message of abc" in verdict.reason


def test_a_reason_with_a_newline_is_shown_escaped_so_the_line_stays_one() -> None:
    line = render(Verdict(False, "bad key `x\nverified: 000`"), SHA)

    assert "\n" not in line
    assert line.startswith(f"not verified: {SHA} ")
    assert "x\\nverified: 000" in line


def test_a_printable_reason_is_shown_as_it_is() -> None:
    assert render(Verdict(False, "é is fine"), SHA).endswith("é is fine")


def test_an_option_given_as_a_sha_is_called_an_option() -> None:
    reason = unresolved("-h", shallow=False).reason

    assert "option" in reason
    assert "git fetch" not in reason
