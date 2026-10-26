import pytest

from prepush_ci.core import land
from prepush_ci.core.land import Position
from prepush_ci.core.report import Malformed

SHA = "d" * 40
OTHER = "e" * 40


# --- Only a head on top of the tip lands ---------------------------------------------------------


def test_a_head_on_top_of_the_tip_is_a_fast_forward() -> None:
    assert land.position(False, True) is Position.ON_TOP


def test_a_head_that_is_the_tip_or_behind_it_is_already_on_the_branch() -> None:
    assert land.position(True, False) is Position.ON_BRANCH
    assert land.position(True, True) is Position.ON_BRANCH


def test_a_tip_with_commits_the_head_lacks_is_a_moved_branch() -> None:
    assert land.position(False, False) is Position.MOVED


def test_a_shallow_clone_that_gets_two_noes_cannot_tell_whether_the_branch_moved() -> (
    None
):
    assert land.position(False, False, shallow=True) is Position.CANNOT_TELL


def test_a_shallow_clone_keeps_every_answer_it_can_give() -> None:
    assert land.position(False, True, shallow=True) is Position.ON_TOP
    assert land.position(True, False, shallow=True) is Position.ON_BRANCH
    assert land.position(True, True, shallow=True) is Position.ON_BRANCH


def test_a_complete_clone_with_two_noes_is_a_moved_branch() -> None:
    assert land.position(False, False, shallow=False) is Position.MOVED


def test_the_line_of_a_shallow_clone_says_so_and_names_the_two_ways_to_deepen_it() -> (
    None
):
    answer = land.shallow_cannot_tell("main")

    assert not answer.landed
    assert answer.line.startswith("not landed: ")
    assert "shallow" in answer.line
    assert "cannot tell whether main of origin moved" in answer.line
    assert "git fetch --unshallow" in answer.line
    assert "fetch-depth" in answer.line
    assert "rebase" not in answer.line


def test_the_line_of_a_moved_branch_names_it_and_says_to_rebase_and_push_again() -> (
    None
):
    answer = land.branch_moved("main")

    assert not answer.landed
    assert answer.line.startswith("not landed: ")
    assert "main" in answer.line
    assert "rebase onto main and push again" in answer.line


# --- The head and the branch come from origin ----------------------------------------------------


@pytest.mark.parametrize("text", ["abc", "", "0", "-1", "1.5", " "])
def test_a_number_that_is_not_a_number_of_a_pull_request_is_malformed(
    text: str,
) -> None:
    with pytest.raises(Malformed):
        land.parse_number(text)


@pytest.mark.parametrize("text, number", [("7", 7), ("007", 7), ("1234", 1234)])
def test_a_positive_integer_is_a_number_of_a_pull_request(
    text: str, number: int
) -> None:
    assert land.parse_number(text) == number


def test_the_default_branch_is_the_one_the_symref_of_head_names() -> None:
    listing = f"ref: refs/heads/release/1\tHEAD\n{SHA}\tHEAD\n{SHA}\trefs/pull/7/head\n"

    assert land.default_branch(listing) == "release/1"


def test_a_listing_without_a_symref_of_head_names_no_default_branch() -> None:
    assert land.default_branch("") is None
    assert land.default_branch(f"{SHA}\tHEAD\n") is None
    assert land.default_branch("ref: refs/tags/v1\tHEAD\n") is None
    assert land.default_branch("ref: refs/heads/x\trefs/other\n") is None


def test_the_commit_of_a_ref_is_the_object_listed_for_exactly_that_name() -> None:
    listing = (
        f"ref: refs/heads/main\tHEAD\n{SHA}\tHEAD\n"
        f"{OTHER}\trefs/heads/x/refs/pull/7/head\n{SHA}\trefs/pull/7/head\n"
    )

    assert land.listed_commit(listing, "refs/pull/7/head") == SHA
    assert land.listed_commit(listing, "HEAD") == SHA


def test_a_ref_the_listing_lacks_has_no_commit() -> None:
    listing = f"ref: refs/heads/main\tHEAD\n{SHA}\trefs/pull/7/head\n"

    assert land.listed_commit(listing, "refs/pull/8/head") is None
    assert land.listed_commit(listing, "HEAD") is None


def test_the_line_of_a_missing_pull_request_names_its_number() -> None:
    assert "99" in land.no_pull_request(99).line


def test_the_line_of_an_origin_without_a_default_branch_says_so() -> None:
    assert "origin names no default branch" in land.no_default_branch().line


# --- The tree must have a pass for the configured check ------------------------------------------


def test_the_line_of_a_tree_without_a_pass_names_its_first_twelve_characters() -> None:
    tree = "0123456789abcdef" * 2 + "01234567"

    line = land.no_pass(tree).line

    assert "0123456789ab" in line
    assert "0123456789abc" not in line
    assert "no pass was found" in line


def test_the_line_of_a_cache_that_is_off_says_so() -> None:
    assert "the cache is off" in land.cache_off().line


def test_the_line_of_missing_variables_names_every_one() -> None:
    line = land.missing_variables(["A_URL", "B_URL"]).line

    assert "A_URL" in line
    assert "B_URL" in line


def test_the_line_of_a_failed_preflight_names_the_command_and_the_status() -> None:
    line = land.preflight_failed("test -f ready", 3).line

    assert "preflight" in line
    assert "exit 3" in line
    assert "test -f ready" in line


# --- The answer is one line ----------------------------------------------------------------------


def test_a_landing_is_one_line_with_the_full_sha_and_the_branch() -> None:
    answer = land.landed(SHA, "main")

    assert answer.landed
    assert answer.line == f"landed: {SHA} on main"


def test_a_head_already_on_the_branch_is_a_landed_line() -> None:
    answer = land.already_on(SHA, "main")

    assert answer.landed
    assert answer.line == f"landed: {SHA} already on main"


def test_every_refusal_starts_not_landed() -> None:
    answers = [
        land.not_in_repository("nope"),
        land.no_origin(),
        land.origin_unreachable("gone"),
        land.not_fetched("gone"),
        land.refused("any other reason"),
    ]

    assert all(not answer.landed for answer in answers)
    assert all(answer.line.startswith("not landed: ") for answer in answers)


def test_a_refusal_that_holds_a_line_break_stays_one_line_that_does_not_start_landed() -> (
    None
):
    answer = land.refused("x\nlanded: " + SHA + " on main")

    assert "\n" not in answer.line
    assert answer.line.startswith("not landed: ")


# --- A refused push is reported, never forced ----------------------------------------------------


def test_the_reason_of_a_refused_push_is_the_text_in_the_last_parentheses_of_its_line() -> (
    None
):
    output = (
        "remote: error: hook said (not this)\n"
        "To /tmp/o.git\n"
        "!\tHEAD:refs/heads/main\t[remote rejected] (pre-receive hook declined)\n"
        "Done\n"
    )

    assert land.refusal_reason(output) == "pre-receive hook declined"


def test_the_reason_of_a_rejected_ref_is_read_as_well() -> None:
    output = "!\tHEAD:refs/heads/main\t[rejected] (non-fast-forward)\n"

    assert land.refusal_reason(output) == "non-fast-forward"


def test_a_push_output_without_a_refused_ref_has_no_reason() -> None:
    assert land.refusal_reason("fatal: the remote end hung up\n") is None
    assert land.refusal_reason("remote: !\tx:y\t[x] (looks like a reason)\n") is None


def test_the_line_of_a_refused_push_names_the_branch_the_reason_and_the_ruleset() -> (
    None
):
    line = land.push_refused("main", "pre-receive hook declined").line

    assert line.startswith("not landed: origin refused the push to main")
    assert "pre-receive hook declined" in line
    assert "ruleset" in line


def test_the_line_of_a_refused_push_without_a_reason_still_says_it_was_refused() -> (
    None
):
    line = land.push_refused("main", None).line

    assert line.startswith("not landed: origin refused the push to main")
    assert "ruleset" in line


# --- A head that landed meanwhile is landed ------------------------------------------------------


def after_refusal(now: str | None, *, behind_now: bool) -> land.Answer:
    return land.after_refusal(
        SHA, OTHER, now, "main", "pre-receive hook declined", behind_now
    )


def test_a_head_behind_the_tip_listed_after_a_refusal_is_already_on_the_branch() -> (
    None
):
    answer = after_refusal("f" * 40, behind_now=True)

    assert answer == land.already_on(SHA, "main")
    assert answer.line == f"landed: {SHA} already on main"


def test_a_head_that_is_the_tip_listed_after_a_refusal_is_already_on_the_branch() -> (
    None
):
    assert after_refusal(SHA, behind_now=True) == land.already_on(SHA, "main")


def test_a_tip_that_moved_without_the_head_after_a_refusal_is_a_moved_branch() -> None:
    assert after_refusal("f" * 40, behind_now=False) == land.branch_moved("main")


def test_a_tip_that_did_not_move_after_a_refusal_is_the_refusal() -> None:
    assert after_refusal(OTHER, behind_now=False) == land.push_refused(
        "main", "pre-receive hook declined"
    )


def test_a_branch_no_longer_listed_after_a_refusal_is_the_refusal() -> None:
    assert after_refusal(None, behind_now=False) == land.push_refused(
        "main", "pre-receive hook declined"
    )


# --- A comment of the pull request is a pass ------------------------------------------------------

TREE = "a" * 40
MARKER = "<!-- prepush-ci:prepush-ci / full -->"


def comment(
    title: str = "Passed",
    *,
    first: str = MARKER,
    tree_cell: str = f"` {TREE} `",
    check_cell: str = "` sh scripts/ci `",
    preflight_cell: str = "none",
    more: str = "",
) -> str:
    """A comment as `report --markdown` writes it: marker, title line, commit line, the table."""
    return (
        f"{first}\n### prepush-ci / full: {title}\nCommit {SHA}\n\n"
        f"{more}| Fact | Value |\n| --- | --- |\n| Commit | ` {SHA} ` |\n"
        f"| Tree | {tree_cell} |\n| Check | {check_cell} |\n"
        f"| Preflight | {preflight_cell} |\n| System | Linux |\n"
    )


@pytest.mark.parametrize(
    "title",
    [
        "Passed",
        "3 passed, 0 failed, 1 skipped",
        "812 passed, 0 failed, 0 skipped",
    ],
)
def test_a_comment_with_a_pass_title_states_a_pass(title: str) -> None:
    assert land.states_a_pass(comment(title))


@pytest.mark.parametrize(
    "title",
    [
        "Failed",
        "Failed (3 passed, 0 failed, 0 skipped)",
        "3 passed, 1 failed, 0 skipped",
        "3 passed, 0 failed",
        "passed",
        "Passed.",
    ],
)
def test_a_comment_with_another_title_states_no_pass(title: str) -> None:
    assert not land.states_a_pass(comment(title))


def test_a_pass_title_of_another_check_states_no_pass() -> None:
    other = comment().replace("prepush-ci / full: Passed", "prepush-ci / unit: Passed")

    assert not land.states_a_pass(other)


def test_the_marker_of_another_check_states_no_pass() -> None:
    assert not land.states_a_pass(
        comment(first="<!-- prepush-ci:prepush-ci / unit -->")
    )


def test_a_marker_after_other_text_states_no_pass() -> None:
    assert not land.states_a_pass("hello\n" + comment())


def test_a_comment_with_a_failures_section_states_no_pass() -> None:
    assert not land.states_a_pass(comment(more="### Failures\n\n- mypy `x`\n\n"))


def test_a_failures_line_inside_other_text_is_not_the_section() -> None:
    assert land.states_a_pass(comment(more="See ### Failures in the log\n\n"))


def test_a_comment_with_windows_line_ends_states_a_pass() -> None:
    assert land.states_a_pass(comment().replace("\n", "\r\n"))


def test_an_empty_comment_states_no_pass() -> None:
    assert not land.states_a_pass("")


def names(
    body: str, *, check: str = "sh scripts/ci", preflight: str | None = None
) -> bool:
    return land.names_this(body, TREE, check, preflight)


def test_a_comment_names_the_tree_the_check_and_the_preflight_it_is_compared_with() -> (
    None
):
    assert names(comment())
    assert names(comment(preflight_cell="` uv --version `"), preflight="uv --version")


def test_a_comment_of_another_tree_names_nothing_of_this_one() -> None:
    assert not names(comment(tree_cell=f"` {'b' * 40} `"))


def test_a_tree_that_is_not_in_a_code_span_is_not_named() -> None:
    assert not names(comment(tree_cell=TREE))


def test_a_comment_of_another_check_or_preflight_names_nothing_of_this_one() -> None:
    assert not names(comment(), check="make test")
    assert not names(comment(), preflight="uv --version")
    assert not names(comment(preflight_cell="` uv --version `"))


def test_the_cells_are_compared_as_report_writes_them_a_pipe_and_a_backtick() -> None:
    check = "sh scripts/ci | tee ci.log && echo `x`"
    cell = "`` sh scripts/ci \\| tee ci.log && echo `x` ``"

    assert names(comment(check_cell=cell), check=check)
    assert not names(comment(check_cell=cell.replace("\\|", "|")), check=check)


def test_a_cell_is_never_compared_with_its_white_space_stripped() -> None:
    assert not names(comment(check_cell="`  sh scripts/ci  `"))


@pytest.mark.parametrize("permission", ["admin", "write"])
def test_admin_and_write_are_a_permission_to_write(permission: str) -> None:
    assert land.may_write(permission)


@pytest.mark.parametrize(
    "permission", ["read", "none", "maintain", "triage", "", "Write"]
)
def test_any_other_permission_is_no_permission_to_write(permission: str) -> None:
    assert not land.may_write(permission)


def test_the_line_of_a_tree_without_a_pass_says_where_it_looked() -> None:
    line = land.no_pass(TREE).line

    assert "no pass was found for tree aaaaaaaaaaaa" in line
    assert "in this clone, on origin or in a comment of the pull request" in line


def test_the_line_of_a_tree_without_a_pass_adds_why_github_could_not_be_asked() -> None:
    line = land.no_pass(TREE, "no token: set GITHUB_TOKEN").line

    assert "no pass was found for tree aaaaaaaaaaaa" in line
    assert "GitHub could not be asked: no token: set GITHUB_TOKEN" in line


def test_a_comment_that_is_only_the_marker_states_no_pass() -> None:
    assert not land.states_a_pass(MARKER)
