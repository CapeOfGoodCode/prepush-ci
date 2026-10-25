from collections.abc import Callable

from prepush_ci.core.doctor import (
    NAMES,
    RULESET,
    config_check,
    config_skip,
    exit_status,
    fail,
    ok,
    preflight_check,
    prepush_ci_check,
    render,
    ruleset_check,
    ruleset_hidden,
    ruleset_missing,
    ruleset_unread,
    skip,
    up_to_date_check,
)
from prepush_ci.core.ruleset_audit import Audit


def test_the_six_checks_have_stable_names_in_a_fixed_order() -> None:
    assert NAMES == (
        "config",
        "commit-msg",
        "pre-push",
        "preflight",
        "PREPUSH_CI",
        "up-to-date",
    )


def test_a_line_starts_with_its_verdict_then_the_name_and_a_colon() -> None:
    lines = render([ok("config", "loaded"), skip("preflight", "later")])

    assert lines[:2] == ["ok config: loaded", "skip preflight: later"]


def test_a_failure_is_followed_by_an_indented_fix_line_and_then_its_detail() -> None:
    lines = render([fail("preflight", "it failed", "repair it", ["db is down"])])

    assert lines[:3] == [
        "fail preflight: it failed",
        "  fix: repair it",
        "    db is down",
    ]


def test_a_passing_or_skipped_check_has_no_fix_line() -> None:
    lines = render([ok("config", "loaded"), skip("preflight", "later")])

    assert not any("fix:" in line for line in lines)


def test_the_closing_line_says_all_checks_passed_when_every_check_is_ok() -> None:
    assert render([ok("a", "x"), ok("b", "y")])[-1] == "all checks passed"


def test_the_closing_line_counts_failures_and_skips_alike() -> None:
    checks = [fail("a", "x", "f"), skip("b", "y"), skip("c", "z"), ok("d", "w")]

    assert render(checks)[-1] == "3 of 4 checks did not pass"


def test_the_exit_status_is_zero_only_when_every_check_is_ok() -> None:
    assert exit_status([ok("a", "x")]) == 0
    assert exit_status([ok("a", "x"), skip("b", "y")]) == 1
    assert exit_status([ok("a", "x"), fail("b", "y", "f")]) == 1


def test_a_loaded_config_names_the_file_it_came_from() -> None:
    check = config_check(".prepush-ci.toml", [], missing=False)

    assert (check.status, ".prepush-ci.toml" in check.text) == ("ok", True)


def test_a_failed_config_carries_every_problem_and_names_the_file_to_correct() -> None:
    check = config_check(
        ".prepush-ci.toml",
        [".prepush-ci.toml: unknown key `foo`", "`default_branch` must be a string"],
        missing=False,
    )

    assert check.status == "fail"
    assert "foo" in check.text and "default_branch" in check.text
    assert check.fix is not None and ".prepush-ci.toml" in check.fix


def test_a_missing_config_points_to_init() -> None:
    check = config_check(None, ["no config found"], missing=True)

    assert check.status == "fail"
    assert check.fix is not None and "prepush-ci init" in check.fix


def test_a_check_that_needs_the_config_is_skipped_and_says_why() -> None:
    check = config_skip("preflight")

    assert (check.status, check.name) == ("skip", "preflight")
    assert "config" in check.text


def test_prepush_ci_full_says_commits_get_the_trailer() -> None:
    check = prepush_ci_check("full", None)

    assert check.status == "ok"
    assert "full" in check.text and "trailer" in check.text


def test_prepush_ci_off_says_a_trailer_push_is_refused() -> None:
    check = prepush_ci_check("off", None)

    assert check.status == "ok"
    assert "off" in check.text and "refused" in check.text


def test_prepush_ci_unset_or_empty_says_no_trailer_is_written() -> None:
    for value in (None, ""):
        check = prepush_ci_check(value, None)

        assert check.status == "ok"
        assert "no trailer is written" in check.text


def test_a_misspelled_prepush_ci_fails_and_names_the_valid_values() -> None:
    check = prepush_ci_check("ful", None)

    assert check.status == "fail"
    assert "ful" in check.text and "full" in check.text and "off" in check.text
    assert check.fix is not None and "PREPUSH_CI=full" in check.fix


def test_a_value_is_compared_exactly() -> None:
    assert prepush_ci_check("FULL", None).status == "fail"
    assert prepush_ci_check(" full", None).status == "fail"


def test_the_expected_mode_passes_when_the_value_matches() -> None:
    assert prepush_ci_check("full", "full").status == "ok"
    assert prepush_ci_check("off", "off").status == "ok"
    assert prepush_ci_check(None, "unset").status == "ok"


def test_an_empty_value_counts_as_unset_for_the_expected_mode() -> None:
    assert prepush_ci_check("", "unset").status == "ok"


def test_a_mismatch_names_the_value_found_the_mode_expected_and_the_fix() -> None:
    unset = prepush_ci_check(None, "full")
    assert unset.status == "fail"
    assert "unset" in unset.text and "full" in unset.text
    assert unset.fix is not None and "export PREPUSH_CI=full" in unset.fix

    set_off = prepush_ci_check("off", "unset")
    assert set_off.status == "fail"
    assert set_off.fix is not None and "unset PREPUSH_CI" in set_off.fix

    assert prepush_ci_check("full", "off").status == "fail"


def test_an_invalid_value_fails_even_when_a_mode_is_expected() -> None:
    check = prepush_ci_check("ful", "full")

    assert check.status == "fail"
    assert "ful" in check.text


def never() -> tuple[int, str]:
    raise AssertionError("the preflight command must not run")


def test_nothing_to_verify_passes_and_says_so() -> None:
    check = preflight_check(None, (), (), never)

    assert check.status == "ok"
    assert "nothing to verify" in check.text


def test_variables_that_are_set_pass_without_a_command() -> None:
    check = preflight_check(None, ("A_URL",), (), never)

    assert check.status == "ok"
    assert "A_URL" in check.text


def test_missing_variables_fail_naming_every_one_and_the_command_does_not_run() -> None:
    check = preflight_check("make up", ("A_URL", "B_URL"), ("A_URL", "B_URL"), never)

    assert check.status == "fail"
    assert "A_URL" in check.text and "B_URL" in check.text


def test_a_command_that_exits_zero_passes_and_its_output_is_not_shown() -> None:
    check = preflight_check("make up", (), (), lambda: (0, "all good\n"))

    assert check.status == "ok"
    assert "all good" not in check.text
    assert check.detail == ()


def test_a_failing_command_names_itself_and_its_status_and_shows_its_output() -> None:
    check = preflight_check("make up", (), (), lambda: (3, "db is down\nretry\n"))

    assert check.status == "fail"
    assert "make up" in check.text and "3" in check.text
    assert check.detail == ("db is down", "retry")


def reached(status: int, error: str = "") -> "Callable[[str, str], tuple[int, str]]":
    def ls_remote(remote: str, branch: str) -> tuple[int, str]:
        return status, error

    return ls_remote


def test_a_disabled_up_to_date_passes_without_asking_the_remote() -> None:
    def refuse(remote: str, branch: str) -> tuple[int, str]:
        raise AssertionError("no remote is contacted")

    check = up_to_date_check(None, [], refuse)

    assert check.status == "ok"
    assert "disabled" in check.text


def test_a_branch_the_remote_has_passes_and_the_ref_is_named() -> None:
    check = up_to_date_check("origin/main", ["origin"], reached(0))

    assert check.status == "ok"
    assert "origin/main" in check.text


def test_the_branch_is_everything_after_the_first_slash() -> None:
    asked: list[tuple[str, str]] = []

    def ls_remote(remote: str, branch: str) -> tuple[int, str]:
        asked.append((remote, branch))
        return 0, ""

    up_to_date_check("origin/release/1", ["origin"], ls_remote)

    assert asked == [("origin", "release/1")]


def test_a_ref_that_is_not_remote_slash_branch_fails_and_offers_the_way_out() -> None:
    for ref in ("main", "/main", "origin/"):
        check = up_to_date_check(ref, ["origin"], reached(0))

        assert check.status == "fail"
        assert "<remote>/<branch>" in check.text
        assert check.fix is not None and "require_up_to_date = false" in check.fix


def test_a_remote_that_is_not_configured_fails_and_names_it() -> None:
    check = up_to_date_check("upstream/develop", ["origin"], reached(0))

    assert check.status == "fail"
    assert "upstream" in check.text
    assert check.fix is not None and "require_up_to_date = false" in check.fix


def test_a_branch_the_remote_lacks_fails_and_names_the_ref() -> None:
    check = up_to_date_check("origin/gone", ["origin"], reached(2))

    assert check.status == "fail"
    assert "origin/gone" in check.text
    assert check.fix is not None and "require_up_to_date = false" in check.fix


def test_a_remote_that_cannot_be_reached_fails_with_the_reason() -> None:
    check = up_to_date_check("origin/main", ["origin"], reached(128, "fatal: nope"))

    assert check.status == "fail"
    assert "cannot be reached" in check.text and "fatal: nope" in check.text
    assert check.fix is not None and "require_up_to_date = false" in check.fix


def test_an_unreachable_remote_without_a_reason_still_says_so() -> None:
    check = up_to_date_check("origin/main", ["origin"], reached(128))

    assert check.status == "fail"
    assert check.text.endswith("cannot be reached")


def test_the_ruleset_check_is_a_seventh_name_that_comes_after_the_six() -> None:
    assert RULESET == "ruleset"
    assert RULESET not in NAMES


def test_the_closing_line_counts_seven_checks_when_there_are_seven() -> None:
    checks = [ok(name, "x") for name in (*NAMES, RULESET)]
    checks[-1] = fail(RULESET, "x", "f")

    assert render(checks)[-1] == "1 of 7 checks did not pass"


def test_a_ruleset_without_a_problem_passes_and_names_the_actor() -> None:
    check = ruleset_check(Audit((), "the repository-admin role", None))

    assert check.status == "ok"
    assert check.name == "ruleset"
    assert "the repository-admin role" in check.text
    assert check.fix is None


def test_a_ruleset_with_problems_fails_with_all_of_them_and_the_address_in_the_fix() -> (
    None
):
    audit = Audit(("a is wrong", "b is wrong"), "", "https://github.com/acme/w/rules/1")

    check = ruleset_check(audit)

    assert check.status == "fail"
    assert "a is wrong" in check.text and "b is wrong" in check.text
    assert check.fix is not None
    assert "https://github.com/acme/w/rules/1" in check.fix


def test_a_ruleset_with_problems_and_no_page_link_still_names_the_settings() -> None:
    check = ruleset_check(Audit(("a is wrong",), "", None))

    assert check.fix is not None and "settings" in check.fix


def test_a_missing_ruleset_has_the_ruleset_command_as_its_fix() -> None:
    check = ruleset_missing()

    assert check.status == "fail"
    assert "missing" in check.text
    assert check.fix is not None and "prepush-ci app ruleset" in check.fix


def test_hidden_bypass_actors_ask_for_administration_rights() -> None:
    check = ruleset_hidden()

    assert check.status == "fail"
    assert "administration rights" in check.text
    assert "bypass actors" in check.text


def test_an_unread_ruleset_carries_the_reason_and_asks_for_a_token_and_a_repository() -> (
    None
):
    check = ruleset_unread("GET /x answered 403: no")

    assert check.status == "fail"
    assert "403" in check.text
    assert check.fix is not None and "GITHUB_TOKEN" in check.fix
