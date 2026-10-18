import base64
import json

import pytest

from prepush_ci.core.report import (
    AppCredentials,
    Counts,
    Facts,
    Malformed,
    ReportError,
    Repository,
    Target,
    TokenCredentials,
    Tool,
    check_run_body,
    code_span,
    contradiction,
    count_junit,
    coverage_display,
    credentials,
    format_duration,
    jwt,
    jwt_signing_input,
    parse_duration,
    parse_name,
    parse_tool,
    redact,
    status_body,
    status_description,
    summary,
    target,
    title,
    tree_problem,
    value,
)

TREE = "1a2b3c4d" * 5
SHA = "f" * 40


def facts(**changes: object) -> Facts:
    base = Facts(
        sha=SHA,
        tree=TREE,
        check="sh scripts/ci",
        preflight=None,
        tools=(),
        system="Linux",
        duration=None,
        counts=None,
        coverage=None,
    )
    return Facts(**{**base.__dict__, **changes})  # type: ignore[arg-type]


def junit(*cases: str, wrap: str = "testsuite") -> bytes:
    return f"<{wrap}>{''.join(cases)}</{wrap}>".encode()


PASSING = "<testcase classname='a' name='ok'/>"
FAILING = "<testcase classname='a' name='bad'><failure message='x'/></testcase>"
SETUP_ERROR = "<testcase classname='a' name='setup'><error message='x'/></testcase>"
SKIPPED = "<testcase classname='a' name='later'><skipped/></testcase>"


# --- The command line ----------------------------------------------------------------------------


def test_a_tool_is_a_name_and_a_version() -> None:
    assert parse_tool("ruff=0.14.2") == Tool("ruff", "0.14.2")


def test_a_tool_version_may_hold_an_equals_sign() -> None:
    assert parse_tool("pip=a=b") == Tool("pip", "a=b")


@pytest.mark.parametrize("text", ["ruff", "=1.0", "ruff=", "="])
def test_a_tool_without_a_name_or_a_version_is_malformed(text: str) -> None:
    with pytest.raises(Malformed, match="NAME=VERSION"):
        parse_tool(text)


def test_a_duration_is_a_whole_number_of_seconds() -> None:
    assert parse_duration("492") == 492
    assert parse_duration("0") == 0


@pytest.mark.parametrize("text", ["abc", "-5", "1.5", "", "²"])
def test_a_duration_that_is_not_a_whole_number_is_malformed(text: str) -> None:
    with pytest.raises(Malformed, match="whole number"):
        parse_duration(text)


def test_a_name_is_taken_as_given() -> None:
    assert parse_name("prepush-ci / unit") == "prepush-ci / unit"


def test_an_empty_name_is_malformed() -> None:
    with pytest.raises(Malformed, match="empty"):
        parse_name("")


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0s"), (45, "45s"), (492, "8m 12s"), (3725, "1h 2m 5s"), (3600, "1h 0m 0s")],
)
def test_a_duration_reads_as_hours_minutes_and_seconds(seconds: int, text: str) -> None:
    assert format_duration(seconds) == text


def test_the_tree_of_the_commit_is_accepted() -> None:
    assert tree_problem(TREE, TREE) is None


def test_another_tree_is_refused_with_both_hashes() -> None:
    other = "9" * 40

    problem = tree_problem(other, TREE)

    assert problem is not None
    assert other in problem
    assert TREE in problem


def test_an_abbreviated_tree_is_refused_with_both_hashes() -> None:
    problem = tree_problem(TREE[:7], TREE)

    assert problem is not None
    assert TREE[:7] in problem
    assert TREE in problem
    assert "full" in problem


# --- Where the result goes -----------------------------------------------------------------------


def test_an_empty_variable_counts_as_unset() -> None:
    assert value({"A": ""}, "A") is None
    assert value({}, "A") is None
    assert value({"A": "x"}, "A") == "x"


@pytest.mark.parametrize(
    "origin",
    [
        "https://github.com/acme/widgets.git",
        "https://github.com/acme/widgets",
        "https://github.com/acme/widgets/",
        "git@github.com:acme/widgets",
        "git@github.com:acme/widgets.git",
        "github.com:acme/widgets.git",
        "ssh://git@github.com/acme/widgets.git",
        "ssh://git@github.com:22/acme/widgets.git",
        "ssh://github.com/acme/widgets",
        "https://x-access-token:s3cret@github.com/acme/widgets.git",
        "https://token@github.com/acme/widgets",
        "https://GitHub.com/acme/widgets",
    ],
)
def test_the_repository_is_read_from_the_forms_of_the_remote(origin: str) -> None:
    assert target(origin, {}) == Target(
        "https://api.github.com", Repository("acme", "widgets")
    )


@pytest.mark.parametrize(
    "origin",
    [
        "/tmp/remote.git",
        "../remote.git",
        "C:/work/remote.git",
        "C:\\work\\remote.git",
        "https://github.com/acme",
        "https://github.com/acme/widgets/extra",
        "http://github.com/acme/widgets",
        "",
    ],
)
def test_a_remote_that_is_no_github_url_names_no_repository(origin: str) -> None:
    with pytest.raises(ReportError, match="no repository could be read from `origin`"):
        target(origin, {})


def test_a_remote_that_does_not_exist_names_no_repository() -> None:
    with pytest.raises(ReportError, match="no repository could be read from `origin`"):
        target(None, {})


def test_the_repository_comes_from_the_environment_when_origin_names_none() -> None:
    assert target("/tmp/remote.git", {"GITHUB_REPOSITORY": "acme/widgets"}) == Target(
        "https://api.github.com", Repository("acme", "widgets")
    )


def test_origin_wins_over_github_repository() -> None:
    env = {"GITHUB_REPOSITORY": "other/repo"}

    assert target("https://github.com/acme/widgets.git", env).repository == Repository(
        "acme", "widgets"
    )


def test_a_malformed_github_repository_is_never_read_while_origin_names_one() -> None:
    env = {"GITHUB_REPOSITORY": "acme"}

    assert target("git@github.com:acme/widgets", env).repository == Repository(
        "acme", "widgets"
    )


@pytest.mark.parametrize("named", ["acme", "acme/", "/widgets", "a/b/c", "a b/c"])
def test_a_malformed_repository_name_is_refused_and_named(named: str) -> None:
    with pytest.raises(ReportError, match="GITHUB_REPOSITORY"):
        target("/tmp/remote.git", {"GITHUB_REPOSITORY": named})


def test_an_empty_repository_name_counts_as_unset() -> None:
    with pytest.raises(ReportError, match="no repository could be read from `origin`"):
        target(None, {"GITHUB_REPOSITORY": ""})


def test_another_api_address_makes_a_host_count() -> None:
    env = {"GITHUB_API_URL": "http://127.0.0.1:9/"}

    assert target("https://git.example.test/acme/widgets.git", env) == Target(
        "http://127.0.0.1:9", Repository("acme", "widgets")
    )


def test_a_host_without_an_api_address_names_no_repository() -> None:
    with pytest.raises(ReportError, match="no repository could be read from `origin`"):
        target("https://git.example.test/acme/widgets.git", {})


def test_an_empty_api_address_does_not_make_a_host_count() -> None:
    with pytest.raises(ReportError, match="no repository could be read from `origin`"):
        target("https://git.example.test/acme/widgets.git", {"GITHUB_API_URL": ""})


def test_a_proxy_remote_with_a_repository_name_goes_to_the_default_api_address() -> (
    None
):
    env = {"GITHUB_REPOSITORY": "acme/widgets"}

    assert target("https://git.example.test/acme/widgets.git", env) == Target(
        "https://api.github.com", Repository("acme", "widgets")
    )


def test_the_refusal_never_quotes_the_remote() -> None:
    with pytest.raises(ReportError) as refused:
        target("https://x-access-token:s3cret@git.example.test/acme/w.git", {})

    assert "s3cret" not in str(refused.value)


def test_the_api_address_of_the_environment_replaces_the_default() -> None:
    env = {"GITHUB_API_URL": "https://ghe.example.test/api/v3"}

    assert target("https://github.com/acme/widgets", env).api_url == (
        "https://ghe.example.test/api/v3"
    )


# --- The credentials -----------------------------------------------------------------------------


def test_both_app_variables_make_the_app() -> None:
    env = {"PREPUSH_CI_APP_ID": "7", "PREPUSH_CI_APP_KEY": "pem", "GITHUB_TOKEN": "t"}

    assert credentials(env) == AppCredentials("7", "pem")


def test_a_token_alone_makes_a_status() -> None:
    assert credentials({"GITHUB_TOKEN": "t"}) == TokenCredentials("t")


def test_github_token_comes_before_gh_token() -> None:
    assert credentials({"GITHUB_TOKEN": "a", "GH_TOKEN": "b"}) == TokenCredentials("a")


def test_gh_token_serves_when_github_token_is_unset() -> None:
    assert credentials({"GH_TOKEN": "b"}) == TokenCredentials("b")


def test_an_empty_github_token_falls_to_gh_token() -> None:
    assert credentials({"GITHUB_TOKEN": "", "GH_TOKEN": "b"}) == TokenCredentials("b")


def test_an_empty_app_id_counts_as_unset() -> None:
    env = {"PREPUSH_CI_APP_ID": "", "GITHUB_TOKEN": "t"}

    assert credentials(env) == TokenCredentials("t")


def test_an_empty_app_id_with_a_key_names_the_app_id() -> None:
    with pytest.raises(ReportError, match="PREPUSH_CI_APP_ID"):
        credentials({"PREPUSH_CI_APP_ID": "", "PREPUSH_CI_APP_KEY": "pem"})


def test_an_app_id_without_a_key_names_the_key_whatever_the_token() -> None:
    with pytest.raises(ReportError, match="PREPUSH_CI_APP_KEY"):
        credentials({"PREPUSH_CI_APP_ID": "7", "GITHUB_TOKEN": "t"})


def test_a_key_without_an_app_id_names_the_app_id() -> None:
    with pytest.raises(ReportError, match="PREPUSH_CI_APP_ID"):
        credentials({"PREPUSH_CI_APP_KEY": "pem"})


def test_no_credentials_name_the_app_variables_and_the_token_variables() -> None:
    with pytest.raises(ReportError) as refused:
        credentials({})

    for name in ("PREPUSH_CI_APP_ID", "PREPUSH_CI_APP_KEY", "GITHUB_TOKEN", "GH_TOKEN"):
        assert name in str(refused.value)


def test_redaction_removes_every_secret_and_the_longest_whole() -> None:
    text = "bad token abc and abcdef"

    assert redact(text, ("abc", "abcdef")) == "bad token *** and ***"


# --- What the files say --------------------------------------------------------------------------


def test_a_pytest_file_counts_a_setup_error_as_failed() -> None:
    data = junit(PASSING, FAILING, SKIPPED, SETUP_ERROR, wrap="testsuites")

    assert count_junit(data, "r.xml") == Counts(1, 2, 1)


def test_a_node_file_counts_nested_suites_once() -> None:
    data = (
        b"<?xml version='1.0'?><!-- node --><testsuites><testsuite name='root'>"
        b"<testsuite name='inner'><testcase name='a'/><testcase name='b'><failure/></testcase>"
        b"</testsuite><testcase name='c'><skipped/></testcase></testsuite></testsuites>"
    )

    assert count_junit(data, "node.xml") == Counts(1, 1, 1)


def test_counts_add_up() -> None:
    assert Counts(2, 0, 0) + Counts(3, 1, 4) == Counts(5, 1, 4)


def test_a_file_that_is_not_xml_is_refused_and_named() -> None:
    with pytest.raises(ReportError, match="notes.txt is not JUnit XML"):
        count_junit(b"plain text", "notes.txt")


def test_xml_that_is_not_junit_is_refused_and_named() -> None:
    with pytest.raises(ReportError, match="page.xml is not JUnit XML"):
        count_junit(b"<html/>", "page.xml")


def test_the_coverage_is_the_display_total() -> None:
    text = json.dumps({"totals": {"percent_covered_display": "94.5"}})

    assert coverage_display(text, "coverage.json") == "94.5"


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '"text"',
        "{}",
        '{"totals": []}',
        '{"totals": {}}',
        '{"totals": {"percent_covered_display": 94.5}}',
    ],
)
def test_a_file_that_is_not_a_coverage_json_is_refused_and_named(text: str) -> None:
    with pytest.raises(ReportError, match="c.json is not the coverage.json"):
        coverage_display(text, "c.json")


def test_a_passed_result_with_a_failing_test_is_a_contradiction() -> None:
    problem = contradiction("passed", Counts(3, 1, 0))

    assert problem is not None
    assert "contradicts" in problem


def test_a_failed_result_without_a_failing_test_is_no_contradiction() -> None:
    assert contradiction("failed", Counts(3, 0, 0)) is None


def test_a_passed_result_with_passing_tests_or_none_is_no_contradiction() -> None:
    assert contradiction("passed", Counts(3, 0, 1)) is None
    assert contradiction("passed", None) is None


# --- What is posted ------------------------------------------------------------------------------


def test_a_code_span_survives_backticks_and_line_ends() -> None:
    assert code_span("sh ci") == "` sh ci `"
    assert code_span("echo `date`\nmake") == "`` echo `date` make ``"
    assert code_span("a ``b`` c") == "``` a ``b`` c ```"


def test_the_title_is_the_counts_or_the_result() -> None:
    assert title("passed", Counts(3, 0, 1)) == "3 passed, 0 failed, 1 skipped"
    assert title("passed", None) == "Passed"
    assert title("failed", None) == "Failed"


def test_the_summary_names_the_commit_the_tree_the_check_and_the_session() -> None:
    text = summary(facts(preflight="test -f ready"))

    assert SHA in text
    assert TREE in text
    assert "sh scripts/ci" in text
    assert "test -f ready" in text
    assert "reported from a session" in text
    assert "Linux" in text


def test_the_summary_says_none_for_a_missing_preflight() -> None:
    assert "| Preflight | none |" in summary(facts())


def test_the_summary_lists_tools_duration_counts_and_coverage_when_given() -> None:
    text = summary(
        facts(
            tools=(Tool("ruff", "0.14.2"), Tool("mypy", "1.18.2")),
            duration=492,
            counts=Counts(3, 0, 1),
            coverage="94.5",
        )
    )

    assert "ruff 0.14.2, mypy 1.18.2" in text
    assert "8m 12s" in text
    assert "3 passed, 0 failed, 1 skipped" in text
    assert "94.5%" in text


def test_the_summary_leaves_out_what_was_not_given() -> None:
    text = summary(facts())

    for label in ("Tools", "Duration", "Tests", "overage"):
        assert label not in text


def test_the_status_description_has_counts_coverage_tree_and_the_session() -> None:
    text = status_description(facts(counts=Counts(3, 0, 0), coverage="94.5"))

    assert text == (
        "3 passed, 0 failed, 0 skipped, 94.5%, tree 1a2b3c4 (reported from a session)"
    )


def test_the_status_description_without_files_has_the_tree_and_the_session() -> None:
    assert status_description(facts()) == "tree 1a2b3c4 (reported from a session)"


def test_the_longest_status_description_stays_under_github_s_limit() -> None:
    big = 10**9
    text = status_description(facts(counts=Counts(big, big, big), coverage="100"))

    assert len(text) < 140


def test_a_check_run_for_a_passed_result_is_a_success() -> None:
    body = check_run_body("prepush-ci / full", facts(), "passed", Counts(3, 0, 1))

    assert body["conclusion"] == "success"
    assert body["status"] == "completed"
    assert body["head_sha"] == SHA
    assert body["name"] == "prepush-ci / full"
    assert body["output"]["title"] == "3 passed, 0 failed, 1 skipped"  # type: ignore[index]


def test_a_check_run_for_a_failed_result_is_a_failure() -> None:
    assert check_run_body("n", facts(), "failed", None)["conclusion"] == "failure"


def test_a_status_carries_the_state_the_context_and_the_description() -> None:
    assert status_body("unit", facts(), "failed") == {
        "state": "failure",
        "context": "unit",
        "description": "tree 1a2b3c4 (reported from a session)",
    }
    assert status_body("unit", facts(), "passed")["state"] == "success"


def test_the_signing_input_is_a_header_and_claims_of_nine_minutes() -> None:
    header, claims = (
        json.loads(base64.urlsafe_b64decode(part + "=="))
        for part in jwt_signing_input("7", 1000).decode().split(".")
    )

    assert header == {"alg": "RS256", "typ": "JWT"}
    assert claims == {"iat": 940, "exp": 1540, "iss": "7"}


def test_the_token_is_the_signing_input_and_the_signature_in_base64url() -> None:
    assert jwt(b"a.b", b"\xfb\xff") == "a.b.-_8"


def test_redaction_cleans_a_secret_quoted_with_its_white_space_folded() -> None:
    key = "-----BEGIN KEY-----\nabc\ndef\n-----END KEY-----\n"
    quoted = "bad key -----BEGIN KEY----- abc def -----END KEY----- here"

    assert redact(quoted, (key,)) == "bad key *** here"


def test_redaction_leaves_alone_a_secret_that_is_only_white_space() -> None:
    assert redact("a b", (" ", "")) == "a b"
