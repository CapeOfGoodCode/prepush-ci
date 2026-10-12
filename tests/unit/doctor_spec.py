from prepush_ci.core.doctor import (
    NAMES,
    config_check,
    config_skip,
    exit_status,
    fail,
    ok,
    prepush_ci_check,
    render,
    skip,
)


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
