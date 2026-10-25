"""`prepush-ci land`: real git repositories, a bare `origin` that holds `refs/pull/<n>/head`, and a
result recorded by the tool's own `run`. Nothing of git is mocked; the CLI starts as a module."""

import json
import os
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

DEEP = pytest.param("[" * 100_000, id="nested-too-deep")

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "\n\nPrepush-CI: full"
EXECUTABLE = Path(sys.executable).as_posix()
# What a config of a pull request runs: `exists` is a test of a file, `touch` leaves a mark.
PROBE = (
    "import sys\n"
    "from pathlib import Path\n"
    "action, target = sys.argv[1], Path(sys.argv[2])\n"
    "if action == 'exists':\n"
    "    sys.exit(0 if target.exists() else 1)\n"
    "target.touch()\n"
)
# What the developer's or Actions' own environment may set and a spec must decide itself.
CLEARED = (
    "PREPUSH_CI",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_REPOSITORY",
    "GITHUB_API_URL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
RESULTS = "refs/prepush-ci/results"
POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="the stand-in for upload-pack is an sh script"
)


@dataclass(frozen=True)
class World:
    """A clone on `main`, its bare `origin`, and pull request 7 whose head is `head`."""

    clone: Path
    origin: Path
    base: str  # the tip of `main` of origin
    middle: str  # a commit between the base and the head
    sibling: str  # a commit of `origin` the head does not contain
    head: str
    tree: str
    probe: Path
    mark: Path  # what `probe touch` writes for a config that names @MARK@


def probe(world_probe: Path, action: str, target: Path | str) -> str:
    """A command line for a config: portable, for `sh` and for `cmd`."""
    return (
        f'"{EXECUTABLE}" "{world_probe.as_posix()}" {action} {Path(target).as_posix()}'
    )


def cli(
    clone: Path, *args: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    inherited = {
        key: value
        for key, value in os.environ.items()
        if key not in CLEARED and not key.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", *args],
        cwd=clone,
        env={**inherited, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def land(
    world: World, *args: str, env: dict[str, str] | None = None
) -> "subprocess.CompletedProcess[str]":
    return cli(world.clone, "land", *(args or ("7",)), env=env)


def build(
    repo: Path,
    tmp_path: Path,
    git: Git,
    *,
    lines: Sequence[str] = (),
    check: str | None = None,
    message: str = "work" + TRAILER,
    committer: str | None = None,
    files: dict[str, str] | None = None,
    local_files: dict[str, str] | None = None,
    record: bool = True,
    env: dict[str, str] | None = None,
) -> World:
    """Pull request 7: a head on top of the tip of `main`, with a config that is committed in it and
    a result of its tree recorded by `prepush-ci run` (unless `record` is off). `@MARK@`, `@ORIGIN@`
    and `@SIBLING@` in `lines` and `check` stand for a file path, the path of `origin` and a commit.
    `local_files` are ignored files of the clone, present while the result is recorded."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "remote", "add", "origin", str(origin))
    script = tmp_path / "probe.py"
    script.write_text(PROBE)
    mark = tmp_path / "mark"
    (repo / "notes.txt").write_text("notes\n")
    git(repo, "add", "notes.txt")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "push", "-q", "origin", "main")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "checkout", "-q", "-b", "sibling")
    git(repo, "commit", "--allow-empty", "-q", "-m", "someone else's work")
    sibling = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "push", "-q", "origin", "sibling:refs/heads/sibling")
    git(repo, "checkout", "-q", "-b", "pr", "main")
    git(repo, "commit", "--allow-empty", "-q", "-m", "the first step")
    middle = git(repo, "rev-parse", "HEAD").stdout.strip()

    def fill(text: str) -> str:
        return (
            text.replace("@MARK@", mark.as_posix())
            .replace("@ORIGIN@", origin.as_posix())
            .replace("@SIBLING@", sibling)
        )

    body = [
        f"check = '{fill(check or 'exit 0')}'",
        "require_up_to_date = false",
        *(fill(line) for line in lines),
    ]
    (repo / ".prepush-ci.toml").write_text("\n".join(body) + "\n")
    names = [".prepush-ci.toml"]
    for name, content in (files or {}).items():
        (repo / name).write_text(content)
        names.append(name)
    git(repo, "add", *names)
    ignored = [*(local_files or {})]
    (repo / ".git" / "info" / "exclude").write_text("\n".join(ignored) + "\n")
    for name, content in (local_files or {}).items():
        (repo / name).write_text(content)
    identity = {"GIT_COMMITTER_EMAIL": committer} if committer else {}
    git(repo, "commit", "-q", "-m", message, env=identity)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    tree = git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    git(repo, "push", "-q", "origin", "HEAD:refs/pull/7/head")
    if record:
        recorded = cli(repo, "run", env=env)
        assert recorded.returncode == 0, recorded.stderr
    git(repo, "checkout", "-q", "main")
    return World(repo, origin, base, middle, sibling, head, tree, script, mark)


@pytest.fixture
def world(repo: Path, tmp_path: Path, git: Git) -> World:
    return build(repo, tmp_path, git)


def main_of(world: World, git: Git) -> str:
    return git(world.origin, "rev-parse", "refs/heads/main").stdout.strip()


def refs_of(world: World, git: Git) -> dict[str, str]:
    listing = git(
        world.origin, "for-each-ref", "--format=%(refname) %(objectname)"
    ).stdout
    return dict(line.split(" ") for line in listing.splitlines())


def point_main_at(world: World, git: Git, sha: str) -> None:
    """Move `main` of `origin` the way a push from another clone would."""
    git(world.origin, "update-ref", "refs/heads/main", sha)


def refused(result: "subprocess.CompletedProcess[str]") -> str:
    """The one `not landed:` line of a refusal; the exit status is 1."""
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.endswith("\n") and result.stdout.count("\n") == 1, (
        result.stdout
    )
    line = result.stdout.strip()
    assert line.startswith("not landed: "), line
    return line


def landed(result: "subprocess.CompletedProcess[str]") -> str:
    """The one `landed:` line of a success; the exit status is 0."""
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("\n") and result.stdout.count("\n") == 1, (
        result.stdout
    )
    line = result.stdout.strip()
    assert line.startswith("landed: "), line
    return line


def install_hook(directory: Path, name: str, body: str) -> Path:
    hook = directory / "hooks" / name
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(f"#!/bin/sh\n{body}\n", newline="\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    return hook


def log_hook(directory: Path, name: str, log: Path) -> None:
    install_hook(directory, name, f'echo ran >> "{log.as_posix()}"')


# --- Land pushes the head of a pull request to the default branch ----------------------------------


def test_a_checked_head_lands(world: World, git: Git) -> None:
    result = land(world)

    assert landed(result) == f"landed: {world.head} on main"
    assert main_of(world, git) == world.head


def test_nothing_else_moves_when_a_landing_succeeds_in_a_clone_with_another_branch_and_an_uncommitted_change(
    world: World, git: Git
) -> None:
    git(world.clone, "checkout", "-q", "-b", "side", "main")
    (world.clone / "notes.txt").write_text("changed\n")
    git(world.clone, "config", "push.followTags", "true")
    git(world.clone, "tag", "-a", "-m", "release", "v1", world.head)
    before = refs_of(world, git)
    status = git(world.clone, "status", "--porcelain").stdout

    landed(land(world))

    assert refs_of(world, git) == {**before, "refs/heads/main": world.head}
    assert git(world.clone, "branch", "--show-current").stdout.strip() == "side"
    assert git(world.clone, "status", "--porcelain").stdout == status
    assert (world.clone / "notes.txt").read_text() == "changed\n"


def test_the_repositorys_hooks_do_not_run_when_a_landing_succeeds(
    world: World, git: Git, tmp_path: Path
) -> None:
    ran = {
        name: tmp_path / f"{name}.log" for name in ("pre-push", "reference-transaction")
    }
    for name, log in ran.items():
        log_hook(world.clone / ".git", name, log)
    git(world.clone, "push", "-q", "origin", "main:refs/heads/probe")
    for name, log in ran.items():
        assert log.exists(), f"{name} is installed and runs for a push of the user's"
        log.unlink()

    landed(land(world))

    assert [name for name, log in ran.items() if log.exists()] == []


# --- The head and the branch come from origin --------------------------------------------------------


def test_the_tip_is_read_fresh(repo: Path, tmp_path: Path, git: Git) -> None:
    world = build(repo, tmp_path, git)
    point_main_at(world, git, world.middle)
    assert git(world.clone, "rev-parse", "origin/main").stdout.strip() == world.base

    landed(land(world))

    assert main_of(world, git) == world.head


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param((), id="none"),
        pytest.param(("abc",), id="abc"),
        pytest.param(("0",), id="zero"),
        pytest.param(("-1",), id="minus-one"),
    ],
)
def test_a_number_that_is_not_a_number_exits_2_and_pushes_nothing(
    world: World, git: Git, arguments: tuple[str, ...]
) -> None:
    result = cli(world.clone, "land", *arguments)

    assert result.returncode == 2
    assert main_of(world, git) == world.base


def test_a_pull_request_that_does_not_exist_is_refused_and_named(
    world: World, git: Git
) -> None:
    line = refused(land(world, "99"))

    assert "no pull request 99" in line
    assert main_of(world, git) == world.base


def test_a_repository_without_origin_is_refused_and_says_so(
    world: World, git: Git
) -> None:
    git(world.clone, "remote", "remove", "origin")

    line = refused(land(world))

    assert "no remote named origin" in line


def test_an_origin_that_is_no_repository_is_refused_and_named(
    world: World, git: Git, tmp_path: Path
) -> None:
    git(world.clone, "remote", "set-url", "origin", str(tmp_path / "nowhere"))

    line = refused(land(world))

    assert "origin" in line
    assert "nowhere" in line


def test_a_directory_that_is_no_repository_is_refused_and_says_so(
    tmp_path: Path,
) -> None:
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()

    line = refused(cli(nowhere, "land", "7"))

    assert "not inside a git repository" in line


def test_a_machine_without_git_is_refused_in_one_line(world: World) -> None:
    line = refused(land(world, env={"PATH": ""}))

    assert "cannot run git" in line


# --- An origin without a default branch is refused ----------------------------------------------------


def test_an_origin_whose_head_names_a_branch_it_lacks_is_refused(
    world: World, git: Git
) -> None:
    git(world.origin, "symbolic-ref", "HEAD", "refs/heads/master")

    line = refused(land(world))

    assert "origin names no default branch" in line
    assert main_of(world, git) == world.base


# --- Only a head on top of the tip lands --------------------------------------------------------------


def test_a_branch_that_moved_is_refused_with_the_way_to_fix_it(
    world: World, git: Git
) -> None:
    point_main_at(world, git, world.sibling)

    line = refused(land(world))

    assert "main" in line
    assert "rebase" in line
    assert "push again" in line
    assert main_of(world, git) == world.sibling


def test_a_head_that_is_the_tip_is_already_on_the_branch(
    world: World, git: Git
) -> None:
    point_main_at(world, git, world.head)
    before = refs_of(world, git)

    result = land(world)

    assert landed(result) == f"landed: {world.head} already on main"
    assert refs_of(world, git) == before


def test_a_head_behind_the_tip_is_already_on_the_branch(world: World, git: Git) -> None:
    git(world.clone, "checkout", "-q", "pr")
    git(world.clone, "commit", "--allow-empty", "-q", "-m", "later")
    later = git(world.clone, "rev-parse", "HEAD").stdout.strip()
    git(world.clone, "push", "-q", "origin", "HEAD:refs/heads/main")

    result = land(world)

    assert landed(result) == f"landed: {world.head} already on main"
    assert main_of(world, git) == later


def test_a_config_that_does_not_ask_for_an_up_to_date_branch_does_not_relax_it(
    world: World, git: Git
) -> None:
    committed = git(world.clone, "show", f"{world.head}:.prepush-ci.toml").stdout
    assert "require_up_to_date = false" in committed
    point_main_at(world, git, world.sibling)

    refused(land(world))

    assert main_of(world, git) == world.sibling


def test_a_head_with_no_history_in_common_with_the_branch_is_refused(
    world: World, git: Git
) -> None:
    git(world.clone, "checkout", "-q", "--orphan", "lone")
    git(world.clone, "commit", "--allow-empty", "-q", "-m", "elsewhere")
    lone = git(world.clone, "rev-parse", "HEAD").stdout.strip()
    git(world.clone, "push", "-q", "origin", "lone:refs/heads/lone")
    git(world.clone, "checkout", "-q", "-f", "main")
    point_main_at(world, git, lone)

    line = refused(land(world))

    assert "push again" in line
    assert main_of(world, git) == lone


# --- The required variables are set ---------------------------------------------------------------------

NEEDS = 'require_env = ["LAND_SPEC_A_URL", "LAND_SPEC_B_URL"]'
BOTH = {"LAND_SPEC_A_URL": "a", "LAND_SPEC_B_URL": "b"}


def test_missing_variables_are_named_and_nothing_is_pushed(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=[NEEDS], env=BOTH)

    line = refused(land(world))

    assert "LAND_SPEC_A_URL" in line
    assert "LAND_SPEC_B_URL" in line
    assert main_of(world, git) == world.base


def test_an_empty_variable_is_named(repo: Path, tmp_path: Path, git: Git) -> None:
    world = build(repo, tmp_path, git, lines=[NEEDS], env=BOTH)

    line = refused(land(world, env={**BOTH, "LAND_SPEC_A_URL": ""}))

    assert "LAND_SPEC_A_URL" in line
    assert "LAND_SPEC_B_URL" not in line


def test_variables_that_are_set_let_the_head_land(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=[NEEDS], env=BOTH)

    landed(land(world, env=BOTH))

    assert main_of(world, git) == world.head


# --- The tree must have a pass for the configured check -----------------------------------------------


def test_a_result_in_the_clone_lets_the_head_land(world: World, git: Git) -> None:
    assert git(world.clone, "for-each-ref", RESULTS).stdout

    landed(land(world))


def test_a_result_only_on_origin_lets_the_head_land(world: World, git: Git) -> None:
    git(world.clone, "push", "-q", "origin", f"{RESULTS}/*:{RESULTS}/*")
    for ref in git(
        world.clone, "for-each-ref", "--format=%(refname)", RESULTS
    ).stdout.split():
        git(world.clone, "update-ref", "-d", ref)

    landed(land(world))

    assert main_of(world, git) == world.head


def test_a_tree_without_a_result_is_refused_and_named(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, record=False)

    line = refused(land(world))

    assert world.tree[:12] in line
    assert world.tree[:13] not in line
    assert "no pass was found" in line
    assert main_of(world, git) == world.base


def test_a_result_made_with_another_check_is_refused_like_no_result(
    world: World, git: Git
) -> None:
    (ref,) = git(
        world.clone, "for-each-ref", "--format=%(refname)", RESULTS
    ).stdout.split()
    elsewhere = f"{RESULTS}/{world.tree}-{'f' * 32}"
    git(world.clone, "update-ref", elsewhere, ref)
    git(world.clone, "update-ref", "-d", ref)

    line = refused(land(world))

    assert "no pass was found" in line


@pytest.mark.parametrize("record", [True, False])
def test_the_check_does_not_run(
    repo: Path, tmp_path: Path, git: Git, record: bool
) -> None:
    world = build(
        repo,
        tmp_path,
        git,
        check=probe(tmp_path / "probe.py", "touch", "@MARK@"),
        record=record,
    )
    world.mark.unlink(missing_ok=True)

    land(world)

    assert not world.mark.exists()


def test_a_cache_that_is_off_cannot_land(repo: Path, tmp_path: Path, git: Git) -> None:
    world = build(repo, tmp_path, git, lines=["cache = false"])

    line = refused(land(world))

    assert "the cache is off" in line
    assert main_of(world, git) == world.base


# --- The preflight runs in a checkout of the head -----------------------------------------------------


def ready(tmp_path: Path) -> str:
    return f"preflight = '{probe(tmp_path / 'probe.py', 'exists', 'ready')}'"


def test_a_failing_preflight_stops_the_landing(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(
        repo, tmp_path, git, lines=[ready(tmp_path)], local_files={"ready": ""}
    )

    line = refused(land(world))

    assert "preflight" in line
    assert main_of(world, git) == world.base


def test_the_preflight_sees_the_head_and_not_the_worktree_of_the_clone(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=[ready(tmp_path)], files={"ready": ""})
    assert not (world.clone / "ready").exists()

    landed(land(world))

    assert main_of(world, git) == world.head


def test_the_output_of_the_preflight_is_not_the_answer(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=["preflight = 'echo versions-ok'"])

    result = land(world)

    assert landed(result) == f"landed: {world.head} on main"
    assert "versions-ok" in result.stderr


def test_the_repositorys_hooks_do_not_run_in_the_checkout(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=["preflight = 'echo versions-ok'"])
    ran = tmp_path / "hook.log"
    log_hook(world.clone / ".git", "post-checkout", ran)
    git(world.clone, "worktree", "add", "-q", "--detach", str(tmp_path / "t"), "main")
    assert ran.exists(), "the hook is installed and runs for a checkout of the user's"
    git(world.clone, "worktree", "remove", "--force", str(tmp_path / "t"))
    ran.unlink()

    landed(land(world))

    assert not ran.exists()


def worktrees(world: World, git: Git) -> list[str]:
    listing = git(world.clone, "worktree", "list", "--porcelain").stdout
    return [line for line in listing.splitlines() if line.startswith("worktree ")]


def test_the_checkout_is_removed_after_a_landing(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=["preflight = 'echo versions-ok'"])

    landed(land(world))

    assert len(worktrees(world, git)) == 1


def test_the_checkout_is_removed_after_a_failed_preflight(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(
        repo, tmp_path, git, lines=[ready(tmp_path)], local_files={"ready": ""}
    )

    refused(land(world))

    assert len(worktrees(world, git)) == 1


def test_a_head_that_cannot_be_checked_out_is_refused_and_the_checkout_is_gone(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=["preflight = 'echo versions-ok'"])
    config = git(world.clone, "rev-parse", f"{world.head}:.prepush-ci.toml").stdout
    tree = (
        subprocess.run(
            ["git", "mktree"],
            cwd=world.clone,
            # bytes: in text mode Windows turns the newlines into CRLF and so changes the names
            input=(
                f"100644 blob {config.strip()}\t.prepush-ci.toml\n"
                f"100644 blob {config.strip()}\t.git\n"
            ).encode(),
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    broken = git(
        world.clone, "commit-tree", tree, "-p", world.middle, "-m", "broken" + TRAILER
    ).stdout.strip()
    git(world.clone, "push", "-q", "origin", f"{broken}:refs/pull/8/head")

    line = refused(land(world, "8"))

    assert "cannot check out" in line
    assert len(worktrees(world, git)) == 1


# --- No command of the head runs before the refusals that need none --------------------------------


def marking(tmp_path: Path) -> str:
    return f"preflight = '{probe(tmp_path / 'probe.py', 'touch', '@MARK@')}'"


def test_a_head_without_the_trailer_runs_no_command_of_the_head(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=[marking(tmp_path)], message="work")
    world.mark.unlink()

    refused(land(world))

    assert not world.mark.exists()


def test_a_branch_that_moved_runs_no_command_of_the_head(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=[marking(tmp_path)])
    world.mark.unlink()
    point_main_at(world, git, world.sibling)

    refused(land(world))

    assert not world.mark.exists()


def test_a_head_already_on_the_branch_runs_no_command_of_the_head(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=[marking(tmp_path)])
    world.mark.unlink()
    point_main_at(world, git, world.head)

    landed(land(world))

    assert not world.mark.exists()


@pytest.mark.parametrize(
    "extra, env",
    [
        pytest.param(["cache = false"], {}, id="cache-off"),
        pytest.param([NEEDS], BOTH, id="variable-missing"),
    ],
)
def test_a_cache_that_is_off_or_a_missing_variable_runs_no_command_of_the_head(
    repo: Path, tmp_path: Path, git: Git, extra: list[str], env: dict[str, str]
) -> None:
    world = build(repo, tmp_path, git, lines=[marking(tmp_path), *extra], env=env)
    world.mark.unlink()

    refused(land(world))

    assert not world.mark.exists()


# --- The head must verify ----------------------------------------------------------------------------------


def test_a_head_without_the_trailer_is_refused_though_a_result_exists(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, message="work")

    line = refused(land(world))

    assert "no trailer" in line
    assert main_of(world, git) == world.base


def test_a_head_made_by_a_server_is_refused_and_the_server_is_named(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, committer="noreply@github.com")

    line = refused(land(world))

    assert "noreply@github.com" in line


def test_a_head_whose_committed_config_is_invalid_is_refused_in_one_line(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(repo, tmp_path, git, lines=["unknown_key = 1"], record=False)

    line = refused(land(world))

    assert "config" in line


# --- The answer is one line -------------------------------------------------------------------------------


def test_a_landing_is_one_line_though_origin_warns(world: World, git: Git) -> None:
    install_hook(world.origin, "pre-receive", "echo 'warning: be careful' >&2")

    result = land(world)

    landed(result)
    assert main_of(world, git) == world.head


# --- A refused push is reported, never forced --------------------------------------------------------------


def test_a_remote_that_declines_is_reported_with_its_reason_and_the_ruleset(
    world: World, git: Git
) -> None:
    install_hook(world.origin, "pre-receive", "exit 1")

    line = refused(land(world))

    assert line.startswith("not landed: origin refused the push to main")
    assert "pre-receive hook declined" in line
    assert "ruleset" in line
    assert main_of(world, git) == world.base


def test_a_branch_that_moves_while_landing_gets_the_line_of_a_moved_branch(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    world = build(
        repo,
        tmp_path,
        git,
        lines=[
            "preflight = 'git --git-dir \"@ORIGIN@\" update-ref refs/heads/main @SIBLING@'"
        ],
    )
    point_main_at(world, git, world.base)

    line = refused(land(world))

    assert "push again" in line
    assert main_of(world, git) == world.sibling


# --- A head that landed meanwhile is landed ----------------------------------------------------------------


UNQUARANTINED = "env -u GIT_QUARANTINE_PATH -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES"


def decline_after(world: World, command: str) -> None:
    """A `pre-receive` hook of `origin` that runs `command` (it moves `main` the way another run
    would, inside the window between the fetch and the push) and then declines the push. Git forbids
    ref updates in the quarantine of a push, so `command` runs with that environment removed."""
    install_hook(world.origin, "pre-receive", f"{UNQUARANTINED} {command}\nexit 1")


def test_a_second_landing_of_the_same_head_is_landed_when_the_first_one_wins_the_push(
    world: World, tmp_path: Path, git: Git
) -> None:
    # The first push to reach `origin` runs the winner, a whole `land 7` of the same clone, from the
    # hook, then declines; the winner's own push finds the mark and is accepted. So the loser's push
    # is refused after the winner landed the head.
    mark = tmp_path / "first-push-seen"
    winner = tmp_path / "winner"
    install_hook(
        world.origin,
        "pre-receive",
        f'if [ -e "{mark.as_posix()}" ]; then exit 0; fi\n'
        f'touch "{mark.as_posix()}"\n'
        f'cd "{world.clone.as_posix()}" || exit 1\n'
        f"{UNQUARANTINED} -u GIT_DIR "
        f'"{EXECUTABLE}" -m prepush_ci land 7 > "{winner.as_posix()}.out" 2>&1\n'
        f'echo $? > "{winner.as_posix()}.status"\n'
        "exit 1",
    )

    loser = land(world)

    assert (winner.with_suffix(".status")).read_text().strip() == "0"
    assert (
        winner.with_suffix(".out").read_text().strip()
        == f"landed: {world.head} on main"
    )
    assert landed(loser) == f"landed: {world.head} already on main"
    assert main_of(world, git) == world.head


def test_a_head_that_landed_under_a_later_commit_is_landed(
    world: World, git: Git
) -> None:
    later = git(
        world.clone,
        "commit-tree",
        f"{world.head}^{{tree}}",
        "-p",
        world.head,
        "-m",
        "later",
    ).stdout.strip()
    git(world.clone, "push", "-q", "origin", f"{later}:refs/pull/9/head")
    decline_after(world, f"git update-ref refs/heads/main {later}")

    line = landed(land(world))

    assert line == f"landed: {world.head} already on main"
    assert main_of(world, git) == later


def test_a_branch_that_is_gone_after_a_refused_push_is_not_a_landing(
    world: World,
) -> None:
    decline_after(world, "git update-ref -d refs/heads/main")

    line = refused(land(world))

    assert line.startswith("not landed: origin refused the push to main")
    assert "landed:" not in line.removeprefix("not landed:")


@POSIX_ONLY
def test_a_tip_that_cannot_be_fetched_after_a_refused_push_keeps_the_line_of_a_moved_branch(
    world: World, git: Git, tmp_path: Path
) -> None:
    asked = tmp_path / "asked"
    stand_in = tmp_path / "upload-pack"
    stand_in.write_text(
        "#!/bin/sh\n"
        f'echo x >> "{asked.as_posix()}"\n'
        f'if [ "$(wc -l < "{asked.as_posix()}")" -ge 4 ]; then echo "gone" >&2; exit 1; fi\n'
        'exec git-upload-pack "$@"\n',
        newline="\n",
    )
    stand_in.chmod(stand_in.stat().st_mode | stat.S_IXUSR)
    git(world.clone, "config", "remote.origin.uploadpack", str(stand_in))
    decline_after(world, f"git update-ref refs/heads/main {world.head}")

    line = refused(land(world))

    assert "push again" in line
    assert main_of(world, git) == world.head


def test_a_moved_branch_is_never_overwritten(
    world: World, git: Git, tmp_path: Path
) -> None:
    attempts = tmp_path / "attempts.log"
    log_hook(world.origin, "pre-receive", attempts)
    point_main_at(world, git, world.sibling)

    refused(land(world))

    assert not attempts.exists()
    assert main_of(world, git) == world.sibling


@POSIX_ONLY
def test_an_origin_that_stops_answering_after_it_listed_the_refs_is_refused(
    world: World, git: Git, tmp_path: Path
) -> None:
    served = tmp_path / "served"
    stand_in = tmp_path / "upload-pack"
    stand_in.write_text(
        "#!/bin/sh\n"
        f'if [ -e "{served.as_posix()}" ]; then echo "gone" >&2; exit 1; fi\n'
        f'touch "{served.as_posix()}"\n'
        'exec git-upload-pack "$@"\n',
        newline="\n",
    )
    stand_in.chmod(stand_in.stat().st_mode | stat.S_IXUSR)
    git(world.clone, "config", "remote.origin.uploadpack", str(stand_in))

    line = refused(land(world))

    assert "could not be fetched" in line
    assert main_of(world, git) == world.base


def test_a_pull_request_that_is_no_commit_is_refused(world: World, git: Git) -> None:
    git(world.origin, "update-ref", "refs/pull/9/head", world.tree)

    line = refused(land(world, "9"))

    assert "did not send" in line


# --- A comment of the pull request is a pass when no result is found ------------------------------

COMMENTS = "/repos/acme/widgets/issues/7/comments"
WRITER = {"login": "alice", "type": "User"}


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]

    @property
    def route(self) -> str:
        return urlsplit(self.path).path

    @property
    def query(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}


@dataclass
class Api:
    """A server that answers as GitHub's API is documented to, and notes every request."""

    url: str
    requests: list[Request] = field(default_factory=list)
    comments: list[dict[str, object]] = field(default_factory=list)
    permissions: dict[str, str] = field(default_factory=lambda: {"alice": "write"})
    answers: list[tuple[str, int, str]] = field(default_factory=list)

    def comment(
        self, body: str, user: dict[str, str] | None = None
    ) -> dict[str, object]:
        made: dict[str, object] = {
            "id": 100 + len(self.comments),
            "body": body,
            "user": user or WRITER,
        }
        self.comments.append(made)
        return made

    def answer(self, where: str, status: int, body: str = "{}") -> None:
        """Answer a request whose `METHOD path` holds `where` with `status` and `body`."""
        self.answers.append((where, status, body))

    def respond(self, request: Request) -> tuple[int, str]:
        line = f"{request.method} {request.path}"
        for where, status, body in self.answers:
            if where in line:
                return status, body
        if request.method == "GET" and request.route == COMMENTS:
            page, size = int(request.query["page"]), int(request.query["per_page"])
            return 200, json.dumps(self.comments[(page - 1) * size : page * size])
        prefix = "/repos/acme/widgets/collaborators/"
        if request.method == "GET" and request.route.startswith(prefix):
            login = request.route.removeprefix(prefix).removesuffix("/permission")
            if login in self.permissions:
                return 200, json.dumps({"permission": self.permissions[login]})
        return 404, json.dumps({"message": "Not Found"})

    def asked(self, route: str) -> list[Request]:
        return [r for r in self.requests if r.route == route]

    def permission_asked_for(self) -> list[str]:
        prefix = "/repos/acme/widgets/collaborators/"
        return [
            r.route.removeprefix(prefix).removesuffix("/permission")
            for r in self.requests
            if r.route.startswith(prefix)
        ]


@pytest.fixture
def api() -> Iterator[Api]:
    served: Api

    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            request = Request(
                self.command,
                self.path,
                {key.lower(): value for key, value in self.headers.items()},
            )
            served.requests.append(request)
            status, body = served.respond(request)
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PATCH = _serve  # noqa: N815

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    served = Api(f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield served
    server.shutdown()
    server.server_close()
    thread.join()


def github(api: Api, **extra: str) -> dict[str, str]:
    """The environment of a lander that can read the pull request."""
    return {
        "GITHUB_TOKEN": "tok",
        "GITHUB_REPOSITORY": "acme/widgets",
        "GITHUB_API_URL": api.url,
        "NO_PROXY": "127.0.0.1,localhost",
        **extra,
    }


def report_comment(world: World, result: str = "passed", *args: str) -> str:
    """The comment a session posts: what `report --markdown` prints for the head's tree."""
    printed = cli(
        world.clone,
        "report",
        "--markdown",
        "--result",
        result,
        "--tree",
        world.tree,
        "--commit",
        world.head,
        *args,
    )
    assert printed.returncode == 0, printed.stderr
    return printed.stdout


@pytest.fixture
def unrecorded(repo: Path, tmp_path: Path, git: Git) -> World:
    """Pull request 7 with no result ref anywhere."""
    return build(repo, tmp_path, git, record=False)


def test_a_comment_of_a_session_is_a_pass(
    unrecorded: World, api: Api, git: Git
) -> None:
    api.comment(report_comment(unrecorded))

    result = land(unrecorded, env=github(api))

    assert landed(result) == f"landed: {unrecorded.head} on main"
    assert main_of(unrecorded, git) == unrecorded.head


def test_a_result_ref_wins_over_a_comment(world: World, api: Api) -> None:
    api.comment(report_comment(world))

    landed(land(world, env=github(api)))

    assert api.requests == []


def test_a_comment_past_the_first_page_is_found(unrecorded: World, api: Api) -> None:
    for number in range(100):
        api.comment(f"chatter {number}")
    api.comment(report_comment(unrecorded))

    landed(land(unrecorded, env=github(api)))

    assert [r.query["page"] for r in api.asked(COMMENTS)] == ["1", "2"]


def test_nothing_is_written_when_a_landing_succeeds_on_a_comment(
    unrecorded: World, api: Api, git: Git
) -> None:
    api.comment(report_comment(unrecorded))
    before = refs_of(unrecorded, git)

    landed(land(unrecorded, env=github(api)))

    assert {r.method for r in api.requests} == {"GET"}
    assert refs_of(unrecorded, git) == {**before, "refs/heads/main": unrecorded.head}
    assert git(unrecorded.clone, "for-each-ref", RESULTS).stdout == ""
    assert not [ref for ref in refs_of(unrecorded, git) if ref.startswith(RESULTS)]


def test_the_comments_are_asked_for_with_the_token_the_page_size_and_the_page(
    unrecorded: World, api: Api
) -> None:
    api.comment(report_comment(unrecorded))

    landed(land(unrecorded, env=github(api, GITHUB_TOKEN="s3cr3t")))

    [asked] = api.asked(COMMENTS)
    assert asked.query == {"per_page": "100", "page": "1"}
    assert asked.headers["authorization"] == "Bearer s3cr3t"


# --- A comment states a pass ---------------------------------------------------------------------


def with_title(comment: str, title: str) -> str:
    lines = comment.split("\n")
    lines[1] = f"### prepush-ci / full: {title}"
    return "\n".join(lines)


def test_a_failed_result_is_not_a_pass(
    unrecorded: World, api: Api, tmp_path: Path
) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuite><testcase classname='a' name='t'/></testsuite>")
    api.comment(report_comment(unrecorded, "failed", "--junit", str(junit)))
    api.comment(report_comment(unrecorded, "failed"))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


@pytest.mark.parametrize(
    "title",
    [
        pytest.param("3 passed, 1 failed, 0 skipped", id="failing cases"),
        pytest.param(
            "Failed (3 passed, 0 failed, 0 skipped)", id="failed, none failed"
        ),
        pytest.param("Failed", id="failed"),
    ],
)
def test_a_title_that_is_not_a_pass_is_not_a_pass(
    unrecorded: World, api: Api, title: str
) -> None:
    api.comment(with_title(report_comment(unrecorded), title))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


def test_a_comment_with_a_failures_section_is_not_a_pass(
    unrecorded: World, api: Api
) -> None:
    api.comment(
        report_comment(unrecorded).replace("\n\n", "\n\n### Failures\n\n- x\n\n", 1)
    )

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


def test_a_title_of_another_name_is_not_a_pass(unrecorded: World, api: Api) -> None:
    api.comment(report_comment(unrecorded).replace("full: ", "unit: ", 1))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


def test_another_checks_comment_is_not_a_pass(unrecorded: World, api: Api) -> None:
    api.comment(report_comment(unrecorded, "passed", "--name", "prepush-ci / unit"))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


def test_a_marker_in_the_middle_of_a_comment_does_not_count(
    unrecorded: World, api: Api
) -> None:
    api.comment("my notes\n" + report_comment(unrecorded))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


# --- A comment names this tree, check and preflight ---------------------------------------------


def test_a_comment_of_another_tree_is_not_a_pass(
    unrecorded: World, api: Api, git: Git
) -> None:
    earlier = git(unrecorded.clone, "rev-parse", f"{unrecorded.middle}^{{tree}}").stdout
    api.comment(report_comment(unrecorded).replace(unrecorded.tree, earlier.strip()))

    line = refused(land(unrecorded, env=github(api)))

    assert "no pass was found" in line and unrecorded.tree[:12] in line
    assert main_of(unrecorded, git) == unrecorded.base


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param("exit 0", "make test", id="check"),
        pytest.param(
            "| Preflight | none |", "| Preflight | ` uv sync ` |", id="preflight"
        ),
    ],
)
def test_a_comment_of_another_check_or_preflight_is_not_a_pass(
    unrecorded: World, api: Api, old: str, new: str
) -> None:
    assert old in report_comment(unrecorded)
    api.comment(report_comment(unrecorded).replace(old, new))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


def test_a_check_with_a_pipe_and_a_backtick_lands_on_the_comment_report_printed(
    repo: Path, tmp_path: Path, git: Git, api: Api
) -> None:
    world = build(
        repo,
        tmp_path,
        git,
        check="sh scripts/ci | tee ci.log && echo `x`",
        record=False,
    )
    api.comment(report_comment(world))

    landed(land(world, env=github(api)))


def test_a_preflight_that_printed_something_else_does_not_stop_a_comment(
    repo: Path, tmp_path: Path, git: Git, api: Api
) -> None:
    printing = f'"{EXECUTABLE}" -c "import os; print(os.getpid())"'
    world = build(
        repo, tmp_path, git, lines=[f"preflight = '{printing}'"], record=False
    )
    api.comment(report_comment(world))

    landed(land(world, env=github(api)))


# --- Only a comment of someone with write access counts ------------------------------------------


@pytest.mark.parametrize("permission", ["write", "admin"])
def test_a_writer_s_comment_counts(
    unrecorded: World, api: Api, permission: str
) -> None:
    api.permissions["alice"] = permission
    api.comment(report_comment(unrecorded))

    landed(land(unrecorded, env=github(api)))


@pytest.mark.parametrize("permission", ["read", "none"])
def test_a_comment_of_someone_who_cannot_write_is_not_a_pass(
    unrecorded: World, api: Api, permission: str
) -> None:
    api.permissions["alice"] = permission
    api.comment(report_comment(unrecorded))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


def test_a_permission_that_cannot_be_read_is_no_pass(
    unrecorded: World, api: Api
) -> None:
    api.permissions.clear()  # the stub answers 404
    api.comment(report_comment(unrecorded))

    line = refused(land(unrecorded, env=github(api)))

    assert "no pass was found" in line and "404" in line


@pytest.mark.parametrize("answer", ["[]", '{"permission": 3}', "not json", DEEP])
def test_an_answer_without_a_permission_is_no_pass(
    unrecorded: World, api: Api, answer: str
) -> None:
    api.answer("/permission", 200, answer)
    api.comment(report_comment(unrecorded))

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))


def test_a_readers_comment_beside_a_writers_lands(unrecorded: World, api: Api) -> None:
    api.permissions.update({"mallory": "read", "alice": "write"})
    api.comment(report_comment(unrecorded), {"login": "mallory", "type": "User"})
    api.comment(report_comment(unrecorded), {"login": "alice", "type": "User"})

    landed(land(unrecorded, env=github(api)))

    assert api.permission_asked_for() == ["mallory", "alice"]


def test_an_author_is_asked_about_once(unrecorded: World, api: Api) -> None:
    api.permissions["alice"] = "read"
    api.comment(report_comment(unrecorded))
    api.comment(report_comment(unrecorded))

    refused(land(unrecorded, env=github(api)))

    assert api.permission_asked_for() == ["alice"]


def test_only_matching_comments_are_asked_about(unrecorded: World, api: Api) -> None:
    api.comment(
        report_comment(unrecorded).replace(unrecorded.tree, "b" * 40),
        {"login": "bob", "type": "User"},
    )
    api.comment(report_comment(unrecorded))

    landed(land(unrecorded, env=github(api)))

    assert api.permission_asked_for() == ["alice"]


def test_a_comment_whose_author_is_unknown_is_no_pass(
    unrecorded: World, api: Api
) -> None:
    made = api.comment(report_comment(unrecorded))
    made["user"] = None

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))
    assert api.permission_asked_for() == []


# --- A comment of an App does not count -----------------------------------------------------------


def test_a_comment_of_an_app_is_not_a_pass_and_its_permission_is_not_asked(
    unrecorded: World, api: Api
) -> None:
    api.permissions["acme-ci[bot]"] = "write"
    api.comment(report_comment(unrecorded), {"login": "acme-ci[bot]", "type": "Bot"})

    refused(land(unrecorded, env=github(api)))

    assert api.permission_asked_for() == []


# --- The comments are read as report reaches GitHub -----------------------------------------------


def test_the_repository_comes_from_the_environment_when_origin_names_none(
    unrecorded: World, api: Api
) -> None:
    api.comment(report_comment(unrecorded))

    landed(land(unrecorded, env=github(api)))

    assert [r.route for r in api.asked(COMMENTS)] == [COMMENTS]


def test_the_token_of_gh_token_is_used_when_github_token_is_empty(
    unrecorded: World, api: Api
) -> None:
    api.comment(report_comment(unrecorded))

    landed(land(unrecorded, env=github(api, GITHUB_TOKEN="", GH_TOKEN="from-gh")))

    assert api.asked(COMMENTS)[0].headers["authorization"] == "Bearer from-gh"


def test_a_cache_that_is_off_reads_no_comment(
    repo: Path, tmp_path: Path, git: Git, api: Api
) -> None:
    world = build(repo, tmp_path, git, lines=["cache = false"], record=False)
    api.comment(report_comment(world))

    line = refused(land(world, env=github(api)))

    assert "the cache is off" in line
    assert api.requests == []


# --- A comment that cannot be read is not a pass --------------------------------------------------


def test_without_a_token_no_request_is_sent_and_the_line_names_the_variable(
    unrecorded: World, api: Api
) -> None:
    api.comment(report_comment(unrecorded))

    line = refused(land(unrecorded, env=github(api, GITHUB_TOKEN="")))

    assert "no pass was found" in line and "GITHUB_TOKEN" in line
    assert api.requests == []


def test_without_a_repository_the_line_says_none_could_be_read_from_origin(
    unrecorded: World, api: Api
) -> None:
    env = github(api)
    del env["GITHUB_REPOSITORY"]

    line = refused(land(unrecorded, env=env))

    assert "no repository could be read from `origin`" in line
    assert api.requests == []


def test_an_api_that_fails_leaves_the_line_with_its_status_and_pushes_nothing(
    unrecorded: World, api: Api, git: Git
) -> None:
    api.answer(COMMENTS, 500, '{"message": "Server Error"}')

    line = refused(land(unrecorded, env=github(api)))

    assert "500" in line
    assert main_of(unrecorded, git) == unrecorded.base


@pytest.mark.parametrize("answer", ['{"not": "a list"}', DEEP])
def test_an_answer_the_api_does_not_document_is_no_pass(
    unrecorded: World, api: Api, answer: str
) -> None:
    api.answer(COMMENTS, 200, answer)

    line = refused(land(unrecorded, env=github(api)))

    assert "no pass was found" in line and "not what the API documents" in line


def test_the_token_stays_secret_when_the_api_refuses_it(
    unrecorded: World, api: Api
) -> None:
    api.answer(COMMENTS, 401, '{"message": "Bad credentials: s3cret"}')

    result = land(unrecorded, env=github(api, GITHUB_TOKEN="s3cret"))

    assert result.returncode == 1
    assert "s3cret" not in result.stdout + result.stderr


def test_a_comment_whose_author_has_no_login_is_an_answer_the_api_does_not_document(
    unrecorded: World, api: Api
) -> None:
    made = api.comment(report_comment(unrecorded))
    made["user"] = "alice"

    line = refused(land(unrecorded, env=github(api)))

    assert "not what the API documents" in line


def test_the_marker_of_another_check_is_not_a_pass_even_under_a_full_title(
    unrecorded: World, api: Api
) -> None:
    other = report_comment(unrecorded).replace(
        "<!-- prepush-ci:prepush-ci / full -->", "<!-- prepush-ci:prepush-ci / unit -->"
    )
    api.comment(other)

    assert "no pass was found" in refused(land(unrecorded, env=github(api)))
