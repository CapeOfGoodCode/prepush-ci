"""`prepush-ci land`: real git repositories, a bare `origin` that holds `refs/pull/<n>/head`, and a
result recorded by the tool's own `run`. Nothing of git is mocked; the CLI starts as a module."""

import os
import stat
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

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
        if key != "PREPUSH_CI" and not key.startswith("PRE_COMMIT_")
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
