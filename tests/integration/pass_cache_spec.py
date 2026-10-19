"""The result cache against real repositories: what is stored, found, missed and survived."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from prepush_ci import pass_cache
from prepush_ci.core.config import Config, parse_config
from prepush_ci.core.run_cache import Key, fingerprint
from prepush_ci.git import GitError

Git = Callable[..., "subprocess.CompletedProcess[str]"]


def config(**table: object) -> Config:
    return parse_config({"check": "true", **table})


def key_of(cfg: Config, root: Path, output: str = "") -> Key:
    return Key(pass_cache.current_head(root).tree, fingerprint(cfg, output))


def record(cfg: Config, root: Path, output: str = "") -> None:
    head = pass_cache.current_head(root)
    pass_cache.record_pass(cfg, root, key_of(cfg, root, output), head.sha)


def found(cfg: Config, root: Path, output: str = "") -> str | None:
    return pass_cache.has_pass(cfg, root, key_of(cfg, root, output))


@pytest.fixture
def committed(repo: Path, git: Git) -> Path:
    """`repo` with one commit."""
    (repo / "a.txt").write_text("a")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def head_of(repo: Path, git: Git) -> str:
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def refs(repo: Path, git: Git) -> list[str]:
    listing = git(
        repo, "for-each-ref", "--format=%(refname)", "refs/prepush-ci/results"
    )
    return listing.stdout.split()


def test_a_recorded_pass_names_the_commit_that_passed(
    committed: Path, git: Git
) -> None:
    record(config(), committed)

    assert found(config(), committed) == head_of(committed, git)


def test_nothing_is_found_before_a_pass_was_recorded(committed: Path) -> None:
    assert found(config(), committed) is None


def test_a_pass_is_recorded_as_a_ref_of_the_tree_and_the_config(
    committed: Path, git: Git
) -> None:
    record(config(), committed)

    tree = git(committed, "rev-parse", "HEAD^{tree}").stdout.strip()
    assert refs(committed, git) == [
        f"refs/prepush-ci/results/{tree}-{fingerprint(config(), '')}"
    ]


def test_the_commit_of_a_result_has_the_tree_and_no_parent(
    committed: Path, git: Git
) -> None:
    record(config(), committed)

    [ref] = refs(committed, git)
    assert (
        git(committed, "rev-parse", f"{ref}^{{tree}}").stdout
        == git(committed, "rev-parse", "HEAD^{tree}").stdout
    )
    assert git(committed, "rev-list", "--parents", "-1", ref).stdout.split() == [
        git(committed, "rev-parse", ref).stdout.strip()
    ]


def test_a_pass_recorded_from_a_subdirectory_lands_in_the_same_place(
    committed: Path, git: Git
) -> None:
    (committed / "sub").mkdir()
    record(config(), committed / "sub")

    assert len(refs(committed, git)) == 1
    assert found(config(), committed) is not None


def test_a_linked_worktree_finds_the_pass_of_the_main_one(
    committed: Path, git: Git, tmp_path: Path
) -> None:
    record(config(), committed)
    linked = tmp_path / "linked"
    git(committed, "worktree", "add", "-q", "--detach", str(linked))

    assert found(config(), linked) == head_of(committed, git)


def test_an_amended_message_finds_the_pass_of_the_old_commit(
    committed: Path, git: Git
) -> None:
    record(config(), committed)
    passed = head_of(committed, git)
    git(committed, "commit", "-q", "--amend", "-m", "other message")

    assert found(config(), committed) == passed
    assert head_of(committed, git) != passed


def test_another_tree_does_not_find_the_pass(committed: Path, git: Git) -> None:
    record(config(), committed)
    (committed / "b.txt").write_text("b")
    git(committed, "add", "b.txt")
    git(committed, "commit", "-q", "-m", "second")

    assert found(config(), committed) is None


def test_a_changed_check_command_does_not_find_the_pass(committed: Path) -> None:
    record(config(), committed)

    assert found(config(check="true # other"), committed) is None


def test_another_output_of_the_preflight_does_not_find_the_pass(
    committed: Path,
) -> None:
    record(config(), committed, "uv 0.8.1\n")

    assert found(config(), committed, "uv 0.8.2\n") is None
    assert found(config(), committed, "uv 0.8.1\n") is not None


def test_a_key_that_does_not_change_the_result_still_finds_the_pass(
    committed: Path,
) -> None:
    record(config(require_up_to_date="origin/main"), committed)

    assert (
        found(
            config(require_up_to_date="origin/main", default_branch="trunk"), committed
        )
        is not None
    )


def test_an_emptied_ref_is_a_miss(committed: Path, git: Git) -> None:
    record(config(), committed)
    [ref] = refs(committed, git)
    (committed / ".git" / ref).write_text("")

    assert found(config(), committed) is None


def test_a_ref_that_points_at_a_commit_of_another_tree_is_a_miss(
    committed: Path, git: Git
) -> None:
    (committed / "b.txt").write_text("b")
    git(committed, "add", "b.txt")
    git(committed, "commit", "-q", "-m", "second")
    record(config(), committed)  # a result for the tree of the second commit
    [other] = refs(committed, git)
    elsewhere = git(committed, "rev-parse", other).stdout.strip()
    git(committed, "reset", "-q", "--hard", "HEAD~1")
    record(config(), committed)
    [ref] = [name for name in refs(committed, git) if name != other]
    git(committed, "update-ref", ref, elsewhere)

    assert found(config(), committed) is None


def test_a_ref_that_points_at_a_commit_that_names_no_commit_is_a_miss(
    committed: Path, git: Git
) -> None:
    record(config(), committed)
    [ref] = refs(committed, git)
    plain = git(
        committed, "commit-tree", "HEAD^{tree}", "-m", "hand made"
    ).stdout.strip()
    git(committed, "update-ref", ref, plain)

    assert found(config(), committed) is None


def test_a_ref_that_points_at_a_blob_is_a_miss(committed: Path, git: Git) -> None:
    record(config(), committed)
    [ref] = refs(committed, git)
    blob = git(committed, "rev-parse", "HEAD:a.txt").stdout.strip()
    git(committed, "update-ref", ref, blob)

    assert found(config(), committed) is None


def test_a_pass_survives_packed_refs_and_garbage_collection(
    committed: Path, git: Git
) -> None:
    record(config(), committed)
    git(committed, "pack-refs", "--all")
    git(committed, "gc", "-q", "--prune=now")

    assert found(config(), committed) == head_of(committed, git)


def test_nothing_is_recorded_when_the_cache_is_off(committed: Path, git: Git) -> None:
    record(config(cache=False), committed)

    assert refs(committed, git) == []


def test_a_ref_is_ignored_when_the_cache_is_off(committed: Path) -> None:
    record(config(), committed)

    assert found(config(cache=False), committed) is None


def test_a_cache_that_cannot_be_written_warns_and_does_not_raise(
    committed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (committed / ".git" / "refs" / "prepush-ci").write_text("in the way")

    record(config(), committed)

    assert "could not be cached" in capsys.readouterr().err
    assert found(config(), committed) is None


def test_a_repository_git_can_no_longer_use_has_no_cache_and_a_pass_only_warns(
    committed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key = key_of(config(), committed)
    (committed / ".git" / "HEAD").write_text("not a ref\n")  # what a check could do

    pass_cache.record_pass(config(), committed, key, "a" * 40)

    assert "could not be cached" in capsys.readouterr().err
    assert pass_cache.has_pass(config(), committed, key) is None


def test_a_result_is_recorded_for_a_tree_even_when_the_commit_is_unknown_to_git(
    committed: Path, git: Git
) -> None:
    key = key_of(config(), committed)

    pass_cache.record_pass(config(), committed, key, "f" * 40)

    assert pass_cache.has_pass(config(), committed, key) == "f" * 40


def test_a_repository_without_a_commit_has_no_head(repo: Path) -> None:
    with pytest.raises(GitError):
        pass_cache.current_head(repo)
