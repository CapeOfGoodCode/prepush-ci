"""What the pre-push hook verifies before it runs the check, pushed with a real `git push`."""

import subprocess
from collections.abc import Callable
from pathlib import Path

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
NO_TRAILER = "plain work"
DATABASE = {"DATABASE_URL": "postgres://localhost/test"}


def configure(
    repo: Path, git: Git, *lines: str, keep_default_ref: bool = False
) -> None:
    """Commit a config whose `check` and `preflight` log their name; extra TOML lines follow.

    The up-to-date step is off unless a line sets `require_up_to_date`; with
    `keep_default_ref` the key is left out, so the hook's default `origin/<default_branch>` decides.
    """
    log = (repo.parent / "ran.log").as_posix()
    body = [f'check = "echo check >> {log}"', f'preflight = "echo preflight >> {log}"']
    if not keep_default_ref and not any(
        line.startswith("require_up_to_date") for line in lines
    ):
        body.append("require_up_to_date = false")
    for line in lines:
        if line.startswith("preflight"):
            body = [b for b in body if not b.startswith("preflight")]
        body.append(line)
    (repo / ".prepush-ci.toml").write_text("\n".join(body) + "\n")
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "configure")


def commit(repo: Path, git: Git, message: str) -> str:
    git(repo, "commit", "--allow-empty", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def push(
    repo: Path, git: Git, *refs: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    return git(repo, "push", "origin", *(refs or ("main",)), env=env, check=False)


def steps(repo: Path) -> list[str]:
    """The names the preflight and the check logged, in order."""
    log = repo.parent / "ran.log"
    return log.read_text().split() if log.exists() else []


def output(result: "subprocess.CompletedProcess[str]") -> str:
    return result.stdout + result.stderr


def publish_main(repo: Path, git: Git) -> None:
    """Put `main` on the empty remote, as a project that already pushed once has it."""
    result = push(repo, git, "main")
    assert result.returncode == 0, result.stderr


def add_second_remote(repo: Path, tmp_path: Path, git: Git) -> None:
    """A reachable remote `second` to push to while `origin` is not."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "second.git"))
    git(repo, "remote", "add", "second", str(tmp_path / "second.git"))
    git(repo, "remote", "set-url", "origin", str(tmp_path / "nowhere"))


def advance_remote_main(repo: Path, tmp_path: Path, git: Git) -> None:
    """Another clone pushes a commit to the remote `main` that `repo` does not contain."""
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(other))
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.com")
    git(other, "config", "commit.gpgsign", "false")
    git(other, "checkout", "-q", "main")
    git(other, "commit", "--allow-empty", "-q", "-m", "someone else's work")
    git(other, "push", "-q", "origin", "main")


# Required variables


def test_all_required_variables_set_runs_the_check(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_env = ["DATABASE_URL"]')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, env=DATABASE)

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == ["preflight", "check"]


def test_an_unset_required_variable_refuses_the_push_and_is_named(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_env = ["DATABASE_URL"]')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert "DATABASE_URL" in output(result)
    assert steps(pushing_repo) == []


def test_an_empty_required_variable_refuses_the_push(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_env = ["DATABASE_URL"]')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, env={"DATABASE_URL": ""})

    assert result.returncode != 0
    assert steps(pushing_repo) == []


def test_a_missing_variable_stops_the_fetch_so_an_unreachable_remote_is_not_mentioned(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    configure(
        pushing_repo,
        git,
        'require_env = ["DATABASE_URL"]',
        'require_up_to_date = "origin/main"',
    )
    commit(pushing_repo, git, "work" + TRAILER)
    add_second_remote(pushing_repo, tmp_path, git)

    result = git(pushing_repo, "push", "second", "main", check=False)

    assert result.returncode != 0
    assert "DATABASE_URL" in output(result)
    assert "could not fetch" not in output(result)


def test_every_missing_variable_is_named(pushing_repo: Path, git: Git) -> None:
    configure(pushing_repo, git, 'require_env = ["A_URL", "B_URL"]')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert "A_URL" in output(result) and "B_URL" in output(result)


# The preflight command


def test_a_passing_preflight_runs_and_then_the_check_runs(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git)
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == ["preflight", "check"]


def test_a_failing_preflight_refuses_the_push_and_names_the_command_and_status(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'preflight = "exit 3"')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert "exit 3" in output(result)
    assert steps(pushing_repo) == []


def test_the_preflight_runs_from_the_repository_root_when_pushing_from_a_subdirectory(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'preflight = "echo here > preflight-marker"')
    (pushing_repo / "sub").mkdir()
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo / "sub", git)

    assert result.returncode == 0, result.stderr
    assert (pushing_repo / "preflight-marker").exists()
    assert not (pushing_repo / "sub" / "preflight-marker").exists()


def test_a_missing_variable_stops_the_preflight(pushing_repo: Path, git: Git) -> None:
    configure(pushing_repo, git, 'require_env = ["DATABASE_URL"]')
    commit(pushing_repo, git, "work" + TRAILER)

    push(pushing_repo, git)

    assert "preflight" not in steps(pushing_repo)


# Preflight fails, never skips


def test_a_preflight_command_that_does_not_exist_refuses_the_push(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'preflight = "no-such-command-here"')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert steps(pushing_repo) == []


def test_an_unset_mode_still_runs_the_preflight(pushing_repo: Path, git: Git) -> None:
    configure(pushing_repo, git, 'preflight = "exit 1"')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, env={})

    assert result.returncode != 0
    assert steps(pushing_repo) == []


def test_the_preflight_runs_before_the_check(pushing_repo: Path, git: Git) -> None:
    configure(pushing_repo, git)
    commit(pushing_repo, git, "work" + TRAILER)

    push(pushing_repo, git)

    assert steps(pushing_repo) == ["preflight", "check"]


# The branch must contain the default branch


def test_a_branch_that_contains_the_remote_default_branch_runs_the_check(
    pushing_repo: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, 'require_up_to_date = "origin/main"')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == ["preflight", "check"]


def test_a_branch_that_is_behind_the_default_branch_is_refused_with_how_to_fix_it(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, 'require_up_to_date = "origin/main"')
    commit(pushing_repo, git, "work" + TRAILER)
    advance_remote_main(pushing_repo, tmp_path, git)

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode != 0
    text = output(result)
    assert "origin/main" in text
    assert "rebase" in text and "merge" in text
    assert steps(pushing_repo) == []


def test_a_remote_branch_that_is_no_commit_refuses_the_push_and_says_it_could_not_compare(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, 'require_up_to_date = "origin/main"')
    commit(pushing_repo, git, "work" + TRAILER)
    remote = tmp_path / "remote.git"
    nothing = tmp_path / "nothing"
    nothing.write_text("")
    tree = git(remote, "hash-object", "-w", "-t", "tree", str(nothing)).stdout.strip()
    (remote / "refs" / "heads" / "main").write_text(tree + "\n")  # a branch gone wrong

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode != 0
    assert "could not compare this branch with origin/main" in output(result)
    assert steps(pushing_repo) == []


def test_a_branch_behind_stops_the_preflight(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(
        pushing_repo,
        git,
        'require_up_to_date = "origin/main"',
        'preflight = "echo here > preflight-marker"',
    )
    commit(pushing_repo, git, "work" + TRAILER)
    advance_remote_main(pushing_repo, tmp_path, git)

    push(pushing_repo, git, "main:topic")

    assert not (pushing_repo / "preflight-marker").exists()


def test_a_branch_that_is_the_remote_default_branch_tip_runs_the_check(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_up_to_date = "origin/main"')
    tip = commit(pushing_repo, git, "work" + TRAILER)
    # a tag push is not checked, and it brings the objects; then the remote main is the tip
    git(pushing_repo, "push", "-q", "origin", "HEAD:refs/tags/tip")
    git(pushing_repo.parent / "remote.git", "update-ref", "refs/heads/main", tip)

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == ["preflight", "check"]


def test_a_stale_tracking_ref_does_not_decide(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, 'require_up_to_date = "origin/main"')
    commit(pushing_repo, git, "work" + TRAILER)
    advance_remote_main(pushing_repo, tmp_path, git)
    stale = git(pushing_repo, "rev-parse", "origin/main").stdout.strip()
    assert (
        git(
            pushing_repo, "merge-base", "--is-ancestor", stale, "HEAD", check=False
        ).returncode
        == 0
    )

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode != 0
    assert steps(pushing_repo) == []


def test_a_configured_ref_of_another_remote_is_fetched_and_named(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    upstream = tmp_path / "upstream.git"
    git(tmp_path, "init", "-q", "--bare", str(upstream))
    git(pushing_repo, "remote", "add", "upstream", str(upstream))
    git(pushing_repo, "push", "-q", "upstream", "main:develop")
    configure(pushing_repo, git, 'require_up_to_date = "upstream/develop"')
    commit(pushing_repo, git, "work" + TRAILER)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(upstream), str(other))
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.com")
    git(other, "config", "commit.gpgsign", "false")
    git(other, "checkout", "-q", "develop")
    git(other, "commit", "--allow-empty", "-q", "-m", "ahead")
    git(other, "push", "-q", "origin", "develop")

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert "upstream/develop" in output(result)


def test_a_branch_name_with_a_slash_is_split_at_the_first_slash(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    git(pushing_repo, "push", "-q", "origin", "main:release/1")
    configure(pushing_repo, git, 'require_up_to_date = "origin/release/1"')
    commit(pushing_repo, git, "work" + TRAILER)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(other))
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.com")
    git(other, "config", "commit.gpgsign", "false")
    git(other, "checkout", "-q", "release/1")
    git(other, "commit", "--allow-empty", "-q", "-m", "ahead")
    git(other, "push", "-q", "origin", "release/1")

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode != 0
    assert "origin/release/1" in output(result)


# The fetch must succeed


def test_an_unreachable_remote_refuses_the_push_and_says_the_fetch_failed(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_up_to_date = "origin/main"')
    commit(pushing_repo, git, "work" + TRAILER)
    add_second_remote(pushing_repo, tmp_path, git)

    result = git(pushing_repo, "push", "second", "main", check=False)

    assert result.returncode != 0
    assert "could not fetch origin/main" in output(result)
    assert steps(pushing_repo) == []


def test_a_ref_of_a_remote_that_is_not_configured_names_the_remote(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_up_to_date = "upstream/develop"')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert "upstream" in output(result)
    assert steps(pushing_repo) == []


def test_a_ref_without_a_remote_must_be_remote_slash_branch(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_up_to_date = "main"')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert "<remote>/<branch>" in output(result)
    assert steps(pushing_repo) == []


# A refused fetch names a way out


def test_a_branch_missing_on_the_remote_refuses_the_push_and_says_the_fetch_failed(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_up_to_date = "origin/gone"')
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert "could not fetch origin/gone" in output(result)
    assert steps(pushing_repo) == []


def test_the_first_push_to_an_empty_remote_is_refused_by_the_default_ref(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, keep_default_ref=True)
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert "origin/main" in output(result)
    assert steps(pushing_repo) == []


def test_the_refusal_for_an_empty_remote_names_both_ways_out(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, keep_default_ref=True)
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert "require_up_to_date = false" in output(result)
    assert "without the trailer" in output(result)


def test_the_default_ref_is_the_remote_default_branch_and_a_branch_behind_it_is_refused(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, keep_default_ref=True)
    commit(pushing_repo, git, "work" + TRAILER)
    advance_remote_main(pushing_repo, tmp_path, git)

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode != 0
    assert "origin/main has commits" in output(result)
    assert steps(pushing_repo) == []


def test_the_default_ref_follows_the_configured_default_branch(
    pushing_repo: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, 'default_branch = "trunk"', keep_default_ref=True)
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode != 0
    assert "origin/trunk" in output(result)
    assert steps(pushing_repo) == []


def test_a_branch_that_contains_the_default_ref_runs_the_check_without_naming_it_in_the_config(
    pushing_repo: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, keep_default_ref=True)
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == ["preflight", "check"]


def test_every_refusal_of_the_fetch_step_names_both_ways_out(
    pushing_repo: Path, git: Git
) -> None:
    for ref in ("main", "upstream/develop", "origin/gone"):
        configure(pushing_repo, git, f'require_up_to_date = "{ref}"')
        commit(pushing_repo, git, "work" + TRAILER)

        result = push(pushing_repo, git)

        assert result.returncode != 0
        assert "require_up_to_date = false" in output(result), ref
        assert "without the trailer" in output(result), ref
        git(pushing_repo, "reset", "-q", "--hard", "HEAD~2")


def test_a_tip_without_the_trailer_gets_past_an_empty_remote(
    pushing_repo: Path, git: Git
) -> None:
    configure(pushing_repo, git, 'require_up_to_date = "origin/main"')
    commit(pushing_repo, git, NO_TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == []


# The up-to-date check can be disabled


def test_disabled_and_behind_the_check_runs(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    publish_main(pushing_repo, git)
    configure(pushing_repo, git, "require_up_to_date = false")
    commit(pushing_repo, git, "work" + TRAILER)
    advance_remote_main(pushing_repo, tmp_path, git)

    result = push(pushing_repo, git, "main:topic")

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == ["preflight", "check"]


def test_disabled_does_not_fetch_so_an_unreachable_origin_does_not_matter(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    configure(pushing_repo, git, "require_up_to_date = false")
    commit(pushing_repo, git, "work" + TRAILER)
    add_second_remote(pushing_repo, tmp_path, git)

    result = git(pushing_repo, "push", "second", "main", check=False)

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == ["preflight", "check"]


def test_disabled_does_not_skip_the_required_variables(
    pushing_repo: Path, git: Git
) -> None:
    configure(
        pushing_repo,
        git,
        "require_up_to_date = false",
        'require_env = ["DATABASE_URL"]',
    )
    commit(pushing_repo, git, "work" + TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode != 0
    assert steps(pushing_repo) == []


# Only a demanding tip is preflighted


def test_a_tip_without_the_trailer_runs_neither_the_preflight_nor_the_variables_check(
    pushing_repo: Path, git: Git
) -> None:
    configure(
        pushing_repo, git, 'preflight = "exit 1"', 'require_env = ["DATABASE_URL"]'
    )
    commit(pushing_repo, git, NO_TRAILER)

    result = push(pushing_repo, git)

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == []


def test_a_tag_push_runs_neither_the_preflight_nor_the_variables_check(
    pushing_repo: Path, git: Git
) -> None:
    configure(
        pushing_repo, git, 'preflight = "exit 1"', 'require_env = ["DATABASE_URL"]'
    )
    commit(pushing_repo, git, "work" + TRAILER)
    git(pushing_repo, "tag", "v1")

    result = push(pushing_repo, git, "v1")

    assert result.returncode == 0, result.stderr
    assert steps(pushing_repo) == []
