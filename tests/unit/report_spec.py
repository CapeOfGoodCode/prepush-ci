import base64
import json

import pytest

from prepush_ci.core.report import (
    AppCredentials,
    Counts,
    Facts,
    Failure,
    Malformed,
    ReportError,
    Repository,
    Target,
    TokenCredentials,
    Tool,
    annotation,
    annotation_batches,
    annotations,
    check_run_body,
    code_span,
    contradiction,
    count_junit,
    coverage_display,
    credentials,
    file_contradiction,
    format_duration,
    junit_failures,
    jwt,
    jwt_signing_input,
    later_batches_bodies,
    mypy_failures,
    parse_duration,
    parse_name,
    parse_tool,
    redact,
    relative_path,
    ruff_failures,
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


def test_ssh_over_the_https_port_goes_to_the_default_api_address() -> None:
    origin = "ssh://git@ssh.github.com:443/acme/widgets.git"

    assert target(origin, {}) == Target(
        "https://api.github.com", Repository("acme", "widgets")
    )


@pytest.mark.parametrize(
    "origin",
    [
        "ssh://ssh.github.com/acme/widgets",
        "git@ssh.github.com:acme/widgets.git",
        "https://SSH.GitHub.com/acme/widgets",
    ],
)
def test_ssh_github_com_counts_as_github_in_every_form(origin: str) -> None:
    assert target(origin, {}) == Target(
        "https://api.github.com", Repository("acme", "widgets")
    )


def test_an_ssh_host_alias_names_no_repository() -> None:
    with pytest.raises(ReportError, match="no repository could be read from `origin`"):
        target("git@github.com-work:acme/widgets.git", {})


def test_an_ssh_host_alias_with_a_repository_name_goes_to_the_default_api_address() -> (
    None
):
    env = {"GITHUB_REPOSITORY": "acme/widgets"}

    assert target("git@github.com-work:acme/widgets.git", env) == Target(
        "https://api.github.com", Repository("acme", "widgets")
    )


@pytest.mark.parametrize(
    "origin",
    [
        "https://ssh.github.com.example.test/acme/widgets.git",
        "https://xssh.github.com/acme/widgets.git",
        "https://github.com.example.test/acme/widgets.git",
    ],
)
def test_a_host_that_only_starts_like_githubs_names_no_repository(origin: str) -> None:
    with pytest.raises(ReportError, match="no repository could be read from `origin`"):
        target(origin, {})


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


def test_the_summary_table_has_a_header_that_names_its_columns() -> None:
    table = [line for line in summary(facts()).splitlines() if line.startswith("|")]

    assert table[:2] == ["| Fact | Value |", "| --- | --- |"]


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


def test_a_pipe_in_a_value_of_the_summary_table_is_escaped_in_every_row() -> None:
    text = summary(
        facts(
            check="a|b",
            preflight="c|d",
            tools=(Tool("e|f", "1|2"),),
            system="g|h",
            duration=1,
        )
    )

    rows = [line for line in text.splitlines() if line.startswith("| ")]
    assert r"| Check | ` a\|b ` |" in rows
    assert r"| Preflight | ` c\|d ` |" in rows
    assert r"| Tools | e\|f 1\|2 |" in rows
    assert r"| System | g\|h |" in rows


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


# --- Failures become annotations -----------------------------------------------------------------

TOP = "/work/repo"


def located(name: str, file: str, line: str, message: str = "boom") -> str:
    return (
        f"<testcase classname='a' name='{name}' file='{file}' line='{line}'>"
        f"<failure message='{message}'/></testcase>"
    )


def test_a_failed_case_with_a_file_and_a_line_is_a_failure_on_that_line_plus_one() -> (
    None
):
    data = junit(located("test_a", "tests/a_spec.py", "117", "assert 1 == 2"))

    assert junit_failures(data, "r.xml", TOP) == [
        Failure("pytest", "assert 1 == 2", "tests/a_spec.py", 118)
    ]


def test_a_failed_case_without_a_line_is_a_failure_named_by_the_case_and_without_a_place() -> (
    None
):
    data = junit(
        "<testcase classname='a' name='test_a' file='a.py'><failure message='x'/></testcase>",
        "<testcase classname='a' name='test_b' line='4'><failure message='x'/></testcase>",
        "<testcase classname='a' name='test_c' file='a.py' line='four'><error/></testcase>",
        "<testcase classname='a' name='test_d' file='a.py' line='-1'><error/></testcase>",
    )

    assert junit_failures(data, "r.xml", TOP) == [
        Failure("pytest", "test_a"),
        Failure("pytest", "test_b"),
        Failure("pytest", "test_c"),
        Failure("pytest", "test_d"),
    ]


def test_a_passing_or_skipped_case_is_no_failure() -> None:
    assert junit_failures(junit(PASSING, SKIPPED), "r.xml", TOP) == []


def test_the_message_of_a_failed_case_falls_back_to_the_text_of_its_element_and_the_name() -> (
    None
):
    data = junit(
        "<testcase name='t1' file='a.py' line='0'><failure>detail</failure></testcase>",
        "<testcase name='t2' file='a.py' line='0'><error/></testcase>",
    )

    assert junit_failures(data, "r.xml", TOP) == [
        Failure("pytest", "detail", "a.py", 1),
        Failure("pytest", "t2", "a.py", 1),
    ]


def test_the_file_of_a_failed_case_is_made_relative_to_the_top_of_the_worktree() -> (
    None
):
    data = junit(located("t", "/work/repo/tests/a_spec.py", "1"))

    assert junit_failures(data, "r.xml", TOP)[0].path == "tests/a_spec.py"


def test_a_file_of_a_failed_case_outside_the_worktree_is_refused_and_named() -> None:
    with pytest.raises(ReportError, match="/etc/a.py"):
        junit_failures(junit(located("t", "/etc/a.py", "1")), "r.xml", TOP)


def test_a_junit_failure_list_refuses_what_is_not_junit() -> None:
    with pytest.raises(ReportError, match="notes.txt is not JUnit XML"):
        junit_failures(b"plain", "notes.txt", TOP)


RUFF_ENTRY = {
    "filename": "/work/repo/src/a.py",
    "location": {"row": 3, "column": 8},
    "code": "F401",
    "message": "`os` imported but unused",
}


def ruff_text(*entries: object) -> str:
    return json.dumps(list(entries))


def test_a_ruff_error_is_a_failure_on_its_row_with_its_code_and_message() -> None:
    assert ruff_failures(ruff_text(RUFF_ENTRY), "ruff.json", TOP) == [
        Failure("ruff", "F401 `os` imported but unused", "src/a.py", 3)
    ]


def test_a_ruff_file_without_errors_yields_none() -> None:
    assert ruff_failures("[]", "ruff.json", TOP) == []


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "{}",
        '"text"',
        "[1]",
        ruff_text({**RUFF_ENTRY, "filename": None}),
        ruff_text({**RUFF_ENTRY, "location": None}),
        ruff_text({**RUFF_ENTRY, "location": {"column": 1}}),
        ruff_text({**RUFF_ENTRY, "location": {"row": "3"}}),
        ruff_text({**RUFF_ENTRY, "location": {"row": True}}),
        ruff_text({**RUFF_ENTRY, "code": None}),
        ruff_text({**RUFF_ENTRY, "message": 7}),
        ruff_text({k: v for k, v in RUFF_ENTRY.items() if k != "message"}),
    ],
)
def test_a_file_that_is_not_ruff_json_is_refused_and_named(text: str) -> None:
    with pytest.raises(ReportError, match="ruff.json"):
        ruff_failures(text, "ruff.json", TOP)


MYPY_ERROR = "src/a.py:42: error: Returning Any from function  [no-any-return]"
MYPY_NOTE = 'src/a.py:43: note: Use "-> None" if function does not return a value'
MYPY_FOUND = "Found 1 error in 1 file (checked 1 source file)"


def test_a_mypy_error_is_a_failure_and_a_note_is_none() -> None:
    text = "\n".join([MYPY_ERROR, MYPY_NOTE, MYPY_FOUND])

    assert mypy_failures(text, "mypy.txt", TOP) == [
        Failure("mypy", "Returning Any from function  [no-any-return]", "src/a.py", 42)
    ]


def test_a_mypy_error_with_a_column_is_on_its_line() -> None:
    text = (
        f'src/a.py:42:9: error: Name "x" is not defined  [name-defined]\n{MYPY_FOUND}'
    )

    assert mypy_failures(text, "mypy.txt", TOP)[0].line == 42


def test_a_mypy_error_with_an_end_position_is_on_its_line() -> None:
    text = (
        f"src/a.py:42:10:44:12: error: Incompatible types  [assignment]\n{MYPY_FOUND}"
    )

    assert mypy_failures(text, "mypy.txt", TOP) == [
        Failure("mypy", "Incompatible types  [assignment]", "src/a.py", 42)
    ]


def test_a_mypy_error_without_a_line_is_a_failure_without_a_place() -> None:
    text = (
        'b/x.py: error: Duplicate module named "x" (also at "a/x.py")\n'
        "Found 1 error in 1 file (errors prevented further checking)"
    )

    assert mypy_failures(text, "mypy.txt", TOP) == [
        Failure("mypy", 'b/x.py: Duplicate module named "x" (also at "a/x.py")')
    ]


def test_a_mypy_path_that_holds_a_colon_is_read_whole() -> None:
    text = f'src/a:b.py:42: error: Name "x" is not defined\n{MYPY_FOUND}'

    (failure,) = mypy_failures(text, "mypy.txt", TOP)

    assert (failure.path, failure.line) == ("src/a:b.py", 42)


def test_a_note_that_quotes_an_error_is_not_a_failure() -> None:
    text = f"src/a.py:42: note: see the line: error: x\n{MYPY_FOUND}"

    assert mypy_failures(text, "mypy.txt", TOP) == []


def test_clean_mypy_output_yields_none() -> None:
    text = "Success: no issues found in 12 source files\n"

    assert mypy_failures(text, "mypy.txt", TOP) == []


def test_a_mypy_path_with_backslashes_and_a_drive_letter_is_made_relative() -> None:
    text = f'C:\\work\\repo\\src\\a.py:42: error: Name "x" is not defined\n{MYPY_FOUND}'

    (failure,) = mypy_failures(text, "mypy.txt", "C:/work/repo")

    assert (failure.path, failure.line) == ("src/a.py", 42)


@pytest.mark.parametrize("text", ["plain text", "", MYPY_ERROR, "Found errors"])
def test_a_file_that_is_not_mypy_output_is_refused_and_named(text: str) -> None:
    with pytest.raises(ReportError, match="mypy.txt"):
        mypy_failures(text, "mypy.txt", TOP)


@pytest.mark.parametrize(
    ("path", "top", "relative"),
    [
        ("src/a.py", TOP, "src/a.py"),
        ("./src//a.py", TOP, "src/a.py"),
        ("src/../lib/a.py", TOP, "lib/a.py"),
        ("/work/repo/src/a.py", TOP, "src/a.py"),
        ("/work/repo/src/a.py", "/work/repo/", "src/a.py"),
        ("src\\a.py", TOP, "src/a.py"),
        ("C:\\work\\repo\\src\\a.py", "C:/work/repo", "src/a.py"),
        ("c:/work/repo/src/a.py", "C:/work/repo", "src/a.py"),
        ("C:/work/repo/src/a.py", "c:/work/repo", "src/a.py"),
    ],
)
def test_a_path_is_taken_from_the_top_of_the_worktree_with_slashes(
    path: str, top: str, relative: str
) -> None:
    assert relative_path(path, top) == relative


@pytest.mark.parametrize(
    "path",
    [
        "/etc/a.py",
        "/work/repository/a.py",
        "/work/a.py",
        "../a.py",
        "src/../../a.py",
        "D:\\work\\repo\\a.py",
        "",
        ".",
        "/work/repo",
        "/work/repo/../repo/a.py",
    ],
)
def test_a_path_outside_the_worktree_or_naming_no_file_is_refused(path: str) -> None:
    with pytest.raises(ReportError, match="not a file inside the worktree"):
        relative_path(path, TOP)


def test_an_error_in_a_ruff_or_mypy_file_contradicts_a_passed_result() -> None:
    failures = [Failure("ruff", "F401 x", "a.py", 1)]

    problem = file_contradiction("passed", "ruff.json", failures)

    assert problem is not None
    assert "contradicts" in problem
    assert "ruff.json" in problem


def test_a_file_without_errors_or_a_failed_result_is_no_contradiction() -> None:
    assert file_contradiction("passed", "ruff.json", []) is None
    assert (
        file_contradiction(
            "failed", "ruff.json", [Failure("ruff", "F401 x", "a.py", 1)]
        )
        is None
    )


def test_an_annotation_sits_on_its_line_with_the_tool_as_title() -> None:
    assert annotation(Failure("mypy", "bad  [code]", "src/a.py", 42)) == {
        "path": "src/a.py",
        "start_line": 42,
        "end_line": 42,
        "annotation_level": "failure",
        "title": "mypy",
        "message": "bad  [code]",
    }


def test_an_annotation_message_is_cut_below_what_github_accepts() -> None:
    long = annotation(Failure("pytest", "x" * 100_000, "a.py", 1))

    assert len(long["message"]) == 32_000  # type: ignore[arg-type]


def test_a_failure_without_a_place_has_no_annotation() -> None:
    assert annotations(
        [Failure("pytest", "test_a"), Failure("ruff", "F", "a.py", 2)]
    ) == [annotation(Failure("ruff", "F", "a.py", 2))]


def test_a_check_run_carries_the_annotations_of_the_failures_that_have_a_place() -> (
    None
):
    placed = Failure("ruff", "F401 x", "a.py", 3)
    body = check_run_body(
        "n", facts(failures=(placed, Failure("pytest", "test_a"))), "failed", None
    )

    assert body["output"]["annotations"] == [annotation(placed)]  # type: ignore[index]


def test_a_check_run_without_a_failure_that_has_a_place_has_no_annotations() -> None:
    body = check_run_body(
        "n", facts(failures=(Failure("pytest", "t"),)), "failed", None
    )

    assert "annotations" not in body["output"]  # type: ignore[operator]


# --- Annotations are sent in batches of 50 -------------------------------------------------------


def many(count: int) -> list[Failure]:
    return [Failure("mypy", f"error {n}", "a.py", n + 1) for n in range(count)]


def test_annotations_are_batched_by_50_in_order_and_each_arrives_once() -> None:
    batches = annotation_batches(many(120))

    assert [len(batch) for batch in batches] == [50, 50, 20]
    assert [a["start_line"] for batch in batches for a in batch] == list(range(1, 121))


def test_exactly_50_annotations_are_one_batch_and_none_is_no_batch() -> None:
    assert [len(batch) for batch in annotation_batches(many(50))] == [50]
    assert annotation_batches(many(51))[1] == [annotation(many(51)[50])]
    assert annotation_batches([]) == []


def test_the_first_batch_is_in_the_body_that_creates_the_run_and_the_rest_follow() -> (
    None
):
    given = facts(failures=tuple(many(120)))

    body = check_run_body("n", given, "failed", None)
    later = later_batches_bodies(given, "failed", None)

    assert len(body["output"]["annotations"]) == 50  # type: ignore[index]
    assert [len(b["output"]["annotations"]) for b in later] == [50, 20]  # type: ignore[index]
    for patch in later:
        assert set(patch) == {"output"}
        assert patch["output"]["title"] == body["output"]["title"]  # type: ignore[index]
        assert patch["output"]["summary"] == body["output"]["summary"]  # type: ignore[index]


def test_a_run_of_50_annotations_has_no_later_batch() -> None:
    assert later_batches_bodies(facts(failures=tuple(many(50))), "failed", None) == []


# --- The summary of a red run lists the failures first -------------------------------------------


def listed(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("- ")]


def test_the_summary_of_a_red_run_begins_with_the_failures_and_then_names_what_ran() -> (
    None
):
    text = summary(
        facts(
            failures=(
                Failure("pytest", "assert 1 == 2", "tests/a_spec.py", 118),
                Failure("mypy", "Name x is not defined", "src/a.py", 42),
            )
        )
    )

    assert text.startswith("### Failures\n\n")
    assert listed(text) == [
        "- pytest ` tests/a_spec.py:118 ` ` assert 1 == 2 `",
        "- mypy ` src/a.py:42 ` ` Name x is not defined `",
    ]
    assert text.index("mypy") < text.index(SHA)
    assert text.index("mypy") < text.index("sh scripts/ci")


def test_a_failed_case_without_a_place_is_listed_by_its_name() -> None:
    text = summary(facts(failures=(Failure("pytest", "test_a"),)))

    assert listed(text) == ["- pytest ` test_a `"]


def test_the_summary_lists_20_failures_then_the_number_of_the_others() -> None:
    text = summary(facts(failures=tuple(many(25))))

    assert len(listed(text)) == 21
    assert listed(text)[-1] == "- and 5 more"
    assert "error 19" in text
    assert "error 20" not in text


def test_the_summary_of_exactly_20_failures_says_nothing_of_others() -> None:
    assert not any(
        "more" in line for line in listed(summary(facts(failures=tuple(many(20)))))
    )


def test_a_summary_without_failures_has_no_section_of_failures() -> None:
    assert "Failures" not in summary(facts())


def test_a_listed_failure_is_the_first_line_of_its_message() -> None:
    text = summary(
        facts(
            failures=(Failure("pytest", "AssertionError: a == b\n- a\n+ b", "a.py", 1),)
        )
    )

    assert listed(text) == ["- pytest ` a.py:1 ` ` AssertionError: a == b `"]


def test_a_listed_failure_skips_leading_empty_lines_of_its_message() -> None:
    text = summary(facts(failures=(Failure("pytest", "\n \nsecond", "a.py", 1),)))

    assert listed(text) == ["- pytest ` a.py:1 ` ` second `"]


def test_a_failure_with_an_empty_message_is_listed_with_an_empty_text() -> None:
    assert listed(summary(facts(failures=(Failure("pytest", "", "a.py", 1),)))) == [
        "- pytest ` a.py:1 ` `  `"
    ]


@pytest.mark.parametrize("name", ["a" * 5000, "b " * 3000])
def test_a_long_text_is_cut_to_200_characters_with_an_ellipsis_last(name: str) -> None:
    (line,) = listed(summary(facts(failures=(Failure("pytest", name),))))

    shown = line.removeprefix("- pytest ` ").removesuffix(" `")
    assert len(shown) == 200
    assert shown.endswith("…")
    assert shown.startswith(" ".join(name.split())[:5])


def test_a_text_of_exactly_200_characters_is_whole() -> None:
    message = "x" * 200

    (line,) = listed(summary(facts(failures=(Failure("pytest", message, "a.py", 1),))))

    assert line == f"- pytest ` a.py:1 ` ` {message} `"


def test_the_200_characters_are_counted_after_runs_of_white_space_are_merged() -> None:
    spaced = "x" * 99 + "     " + "y" * 100
    longer = "x" * 99 + "     " + "y" * 101

    (whole,) = listed(summary(facts(failures=(Failure("pytest", spaced, "a.py", 1),))))
    (cut,) = listed(summary(facts(failures=(Failure("pytest", longer, "a.py", 1),))))

    assert whole.endswith("y" * 100 + " `")
    assert "…" not in whole
    assert cut.endswith("y" * 99 + "… `")


def test_the_cut_counts_the_text_and_not_the_backticks_around_it() -> None:
    whole = "`" * 200
    cut = "`" * 250

    (kept,) = listed(summary(facts(failures=(Failure("pytest", whole, "a.py", 1),))))
    (shortened,) = listed(summary(facts(failures=(Failure("pytest", cut, "a.py", 1),))))

    fence = "`" * 201
    assert kept == f"- pytest ` a.py:1 ` {fence} {whole} {fence}"
    fence = "`" * 200
    assert shortened == f"- pytest ` a.py:1 ` {fence} {'`' * 199}… {fence}"


def test_markdown_characters_of_a_text_are_in_a_code_span_as_typed() -> None:
    text = summary(
        facts(
            failures=(
                Failure("pytest", "assert 2*3 == 7*1", "a.py", 1),
                Failure("pytest", "<built-in function len>", "a.py", 2),
                Failure("pytest", "test_x[__init__]"),
                Failure("mypy", "Name `x` is not defined | a|b", "a.py", 3),
            )
        )
    )

    assert listed(text) == [
        "- pytest ` a.py:1 ` ` assert 2*3 == 7*1 `",
        "- pytest ` a.py:2 ` ` <built-in function len> `",
        "- pytest ` test_x[__init__] `",
        "- mypy ` a.py:3 ` `` Name `x` is not defined | a|b ``",
    ]
