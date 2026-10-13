"""`prepush-ci init`: one command sets a repository up, run as users run it."""

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from prepush_ci.core.config import Config
from prepush_ci.core.config_source import load_config

Git = Callable[..., "subprocess.CompletedProcess[str]"]


def init(
    where: Path,
    *args: str,
    stdin: str | None = None,
    env: dict[str, str | None] | None = None,
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci init` in `where`; standard input is closed unless `stdin` gives lines."""
    merged: dict[str, str | None] = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "init", *args],
        cwd=where,
        capture_output=True,
        text=True,
        check=False,
        input=stdin,
        stdin=subprocess.DEVNULL if stdin is None else None,
        env={k: v for k, v in merged.items() if v is not None},
    )


def config_of(repo: Path) -> Config:
    """The config the repository's files load as."""

    def read(name: str) -> str | None:
        path = repo / name
        return path.read_text(encoding="utf-8") if path.exists() else None

    return load_config(read(".prepush-ci.toml"), read("pyproject.toml"))


def files(root: Path) -> set[str]:
    """Every file below `root`, as posix paths relative to it; of `.git` only the hooks this
    tool wrote."""
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and (
            p.relative_to(root).parts[0] != ".git"
            or p.relative_to(root).parts[1] == "prepush-ci"
        )
    }


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """Contents and modification time of the files `files` lists."""
    return {
        name: ((root / name).read_bytes(), (root / name).stat().st_mtime_ns)
        for name in files(root)
    }


def hooks_path(repo: Path, git: Git) -> str:
    return git(repo, "config", "--get", "core.hooksPath", check=False).stdout.strip()


def test_every_flag_lands_in_the_config(repo: Path) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "make ci",
        "--preflight",
        "make up",
        "--require-env",
        "A",
        "--require-env",
        "B",
        "--default-branch",
        "trunk",
        "--require-up-to-date",
        "upstream/trunk",
        "--hooks",
        "none",
    )

    assert result.returncode == 0, result.stderr
    config = config_of(repo)
    assert config.check == "make ci"
    assert config.preflight == "make up"
    assert config.require_env == ("A", "B")
    assert config.default_branch == "trunk"
    assert config.require_up_to_date == "upstream/trunk"


def test_only_the_check_gives_a_config_with_only_the_check(repo: Path) -> None:
    init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert (repo / ".prepush-ci.toml").read_text() == 'check = "scripts/ci"\n'


def test_a_flag_equal_to_the_default_is_written(repo: Path) -> None:
    init(
        repo,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--default-branch",
        "main",
        "--hooks",
        "none",
    )

    keys = {
        line.split(" = ")[0]
        for line in (repo / ".prepush-ci.toml").read_text().splitlines()
    }
    assert keys == {"check", "default_branch"}


def test_up_to_date_can_be_switched_off(repo: Path) -> None:
    init(
        repo,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--require-up-to-date",
        "false",
        "--hooks",
        "none",
    )

    assert config_of(repo).require_up_to_date is None


def test_a_check_with_quotes_survives(repo: Path) -> None:
    init(
        repo,
        "--non-interactive",
        "--check",
        'sh -c "make ci"',
        "--hooks",
        "none",
    )

    assert config_of(repo).check == 'sh -c "make ci"'


def test_a_check_with_a_character_outside_the_basic_plane_survives(repo: Path) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "echo \N{GRINNING FACE}",
        "--hooks",
        "none",
    )

    assert result.returncode == 0, result.stderr
    assert config_of(repo).check == "echo \N{GRINNING FACE}"


def test_a_check_that_is_not_valid_text_is_refused_with_a_message_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "echo \udcff",
        "--hooks",
        "none",
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "not valid" in result.stderr
    assert not (repo / ".prepush-ci.toml").exists()


def test_no_check_is_a_usage_error_that_writes_nothing(repo: Path) -> None:
    result = init(repo, "--non-interactive", "--hooks", "none")

    assert result.returncode == 2
    assert "--check" in result.stderr
    assert files(repo) == set()


def test_an_empty_check_is_refused_naming_the_key(repo: Path) -> None:
    result = init(repo, "--non-interactive", "--check", "", "--hooks", "none")

    assert result.returncode == 1
    assert "check" in result.stderr
    assert files(repo) == set()


def test_flags_that_agree_with_the_config_change_nothing(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')
    before = snapshot(repo)

    result = init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert snapshot(repo)[".prepush-ci.toml"] == before[".prepush-ci.toml"]


def test_a_flag_that_disagrees_with_the_config_is_refused_before_any_write(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')
    before = snapshot(repo)

    result = init(repo, "--non-interactive", "--check", "make ci", "--hooks", "none")

    assert result.returncode == 1
    assert "check" in result.stderr
    assert snapshot(repo) == before


def test_a_config_that_does_not_load_is_refused_with_its_own_message(
    repo: Path,
) -> None:
    (repo / ".prepush-ci.toml").write_text('chekc = "scripts/ci"\n')
    before = snapshot(repo)

    result = init(repo, "--non-interactive", "--hooks", "native")

    assert result.returncode == 1
    assert "chekc" in result.stderr
    assert snapshot(repo) == before


def test_a_config_in_pyproject_is_used_and_no_file_is_made_for_it(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[tool.prepush-ci]\ncheck = "make ci"\n')

    result = init(repo, "--non-interactive", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert not (repo / ".prepush-ci.toml").exists()


def test_a_detected_manager_gets_the_block_and_git_is_left_alone(
    repo: Path, git: Git
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n"
    )

    result = init(repo, "--non-interactive", "--check", "scripts/ci")

    assert result.returncode == 0, result.stderr
    assert "prepush-ci: begin" in (repo / ".pre-commit-config.yaml").read_text()
    assert hooks_path(repo, git) == ""


def push_after_init(
    repo: Path, tmp_path: Path, git: Git, team_hook: str | None
) -> "subprocess.CompletedProcess[str]":
    """Run `init`, commit what it wrote and one more file with the trailer, and push them to a
    bare remote; `team_hook` is the body of an existing `.git/hooks/pre-push`, if any."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    if team_hook is not None:
        hook = repo / ".git" / "hooks" / "pre-push"
        hook.write_text(f"#!/bin/sh\n{team_hook}\n")
        hook.chmod(0o755)
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "true",
        "--require-up-to-date",
        "false",
    )
    assert result.returncode == 0, result.stderr
    assert hooks_path(repo, git).endswith(".git/prepush-ci/hooks")
    git(repo, "add", ".prepush-ci.toml", ".claude")
    git(repo, "commit", "-q", "-m", "add init files", env={"PREPUSH_CI": "full"})
    return git(repo, "push", "-q", "origin", "main", check=False)


def test_an_existing_pre_push_hook_still_refuses_a_push_after_init(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    mark = tmp_path / "team-hook-ran"

    push = push_after_init(
        repo, tmp_path, git, f"echo ran > '{mark.as_posix()}'; exit 1"
    )

    assert push.returncode != 0
    assert mark.read_text().strip() == "ran"
    assert "worktree is not clean" not in push.stderr
    assert git(tmp_path, "ls-remote", str(tmp_path / "remote.git")).stdout == ""


def test_the_same_push_goes_through_without_the_existing_pre_push_hook(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    push = push_after_init(repo, tmp_path, git, None)

    assert push.returncode == 0, push.stderr
    assert (
        "refs/heads/main"
        in git(tmp_path, "ls-remote", str(tmp_path / "remote.git")).stdout
    )


def test_no_local_hooks_leaves_git_and_the_hook_files_alone(
    repo: Path, git: Git
) -> None:
    result = init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert hooks_path(repo, git) == ""
    assert not (repo / ".git" / "prepush-ci").exists()


def test_native_hooks_set_core_hooks_path_and_show_what_install_printed(
    repo: Path, git: Git
) -> None:
    result = init(
        repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "native"
    )

    assert result.returncode == 0, result.stderr
    assert hooks_path(repo, git).endswith(".git/prepush-ci/hooks")
    assert "installed:" in result.stdout


def test_one_command_sets_a_repository_up(repo: Path, git: Git) -> None:
    result = init(
        repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "native"
    )

    assert result.returncode == 0, result.stderr
    assert (repo / ".prepush-ci.toml").is_file()
    assert hooks_path(repo, git).endswith(".git/prepush-ci/hooks")
    assert (repo / ".claude" / "hooks" / "session-start.sh").is_file()


def test_two_managers_end_init_with_the_refusal_before_the_session_hook(
    repo: Path,
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n"
    )
    (repo / "lefthook.yml").write_text("")

    result = init(repo, "--non-interactive", "--check", "scripts/ci")

    assert result.returncode == 1
    assert "--hooks" in result.stderr
    assert not (repo / ".claude").exists()


def last_line(result: "subprocess.CompletedProcess[str]") -> str:
    return result.stdout.rstrip("\n").splitlines()[-1]


def test_outside_a_repository_init_says_so_and_writes_nothing(tmp_path: Path) -> None:
    result = init(tmp_path, "--non-interactive", "--check", "scripts/ci")

    assert result.returncode == 1
    assert "no git repository" in result.stderr
    assert files(tmp_path) == set()


def test_the_config_goes_to_the_root_of_the_worktree_from_a_subdirectory(
    repo: Path,
) -> None:
    sub = repo / "sub"
    sub.mkdir()

    result = init(sub, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert result.returncode == 0, result.stderr
    assert files(repo) == {".prepush-ci.toml", SESSION_HOOK, SETTINGS}


def test_a_first_run_ends_with_set_up_and_reports_each_step(repo: Path) -> None:
    result = init(
        repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "native"
    )

    assert "set up" in last_line(result)
    assert "already set up" not in last_line(result)
    assert "written: .prepush-ci.toml" in result.stdout


def test_a_second_run_changes_nothing_and_says_already_set_up(repo: Path) -> None:
    args = ("--non-interactive", "--check", "scripts/ci", "--hooks", "native")
    init(repo, *args)
    before = snapshot(repo)

    second = init(repo, *args)

    assert second.returncode == 0, second.stderr
    assert "already set up" in last_line(second)
    assert "kept: .prepush-ci.toml" in second.stdout
    assert snapshot(repo) == before


def test_a_second_run_with_a_manager_file_leaves_it_alone(repo: Path) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n"
    )
    init(repo, "--non-interactive", "--check", "scripts/ci")
    before = snapshot(repo)

    second = init(repo, "--non-interactive", "--check", "scripts/ci")

    assert "already set up" in last_line(second)
    assert snapshot(repo) == before


POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the SessionStart script is a sh script for the Linux container of Claude Code on "
    "the web, and its stubs are sh scripts",
)
SESSION_HOOK = ".claude/hooks/session-start.sh"


@pytest.fixture
def tool_dir(tmp_path: Path) -> Path:
    """The directory the stub `uv` names as the tool bin directory: its `prepush-ci` records
    its arguments in `calls.log` next to it and starts this checkout's tool."""
    directory = tmp_path / "tool-bin"
    directory.mkdir()
    shim = directory / "prepush-ci"
    shim.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{(directory / "calls.log").as_posix()}"\n'
        f'exec "{Path(sys.executable).as_posix()}" -m prepush_ci "$@"\n'
    )
    shim.chmod(0o755)
    return directory


@pytest.fixture
def stub_uv(tmp_path: Path, tool_dir: Path) -> Path:
    """A directory with a `uv` that records its calls in `uv.log` and prints `tool_dir` for
    `tool dir --bin`; it installs nothing."""
    directory = tmp_path / "stub-uv"
    directory.mkdir()
    uv = directory / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{(tmp_path / "uv.log").as_posix()}"\n'
        f'if [ "$1 $2 $3" = "tool dir --bin" ]; then echo "{tool_dir.as_posix()}"; fi\n'
    )
    uv.chmod(0o755)
    return directory


def path_without_the_tool() -> str:
    """`PATH` as it is, minus every directory that holds a `prepush-ci`."""
    return os.pathsep.join(
        entry
        for entry in os.environ["PATH"].split(os.pathsep)
        if shutil.which("prepush-ci", path=entry) is None
    )


def run_session_hook(
    repo: Path,
    stub: Path,
    env_file: Path | None,
    *,
    remote: bool = True,
) -> "subprocess.CompletedProcess[str]":
    """Run the written script as Claude Code would, with the stub `uv` first on `PATH`."""
    env = {
        **os.environ,
        "PATH": os.pathsep.join([str(stub), path_without_the_tool()]),
    }
    env.pop("CLAUDE_CODE_REMOTE", None)
    env.pop("CLAUDE_ENV_FILE", None)
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    if env_file is not None:
        env["CLAUDE_ENV_FILE"] = str(env_file)
    return subprocess.run(
        ["sh", SESSION_HOOK],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@POSIX_ONLY
def test_the_session_hook_is_written_executable_and_a_laptop_session_is_left_alone(
    repo: Path, stub_uv: Path, tmp_path: Path
) -> None:
    init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")
    env_file = tmp_path / "env"
    env_file.write_text("export A=1\n")

    result = run_session_hook(repo, stub_uv, env_file, remote=False)

    assert (repo / SESSION_HOOK).stat().st_mode & 0o111
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "uv.log").exists()
    assert env_file.read_text() == "export A=1\n"


@POSIX_ONLY
def test_the_session_hook_installs_the_hooks_that_were_chosen(
    repo: Path, stub_uv: Path, tool_dir: Path, tmp_path: Path
) -> None:
    (repo / ".husky").mkdir()
    init(repo, "--non-interactive", "--check", "true", "--hooks", "husky")

    result = run_session_hook(repo, stub_uv, tmp_path / "env")

    assert result.returncode == 0, result.stderr
    assert (tool_dir / "calls.log").read_text().splitlines() == [
        "install --hooks husky"
    ]


@POSIX_ONLY
def test_the_session_hook_installs_the_tool_for_good_and_never_through_uvx(
    repo: Path, stub_uv: Path, tmp_path: Path
) -> None:
    init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    run_session_hook(repo, stub_uv, tmp_path / "env")

    calls = (tmp_path / "uv.log").read_text().splitlines()
    assert "tool install prepush-ci" in calls
    assert not [call for call in calls if call.startswith("tool run")]


@POSIX_ONLY
def test_running_the_session_hook_twice_exports_each_variable_once(
    repo: Path, stub_uv: Path, tool_dir: Path, tmp_path: Path
) -> None:
    init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")
    env_file = tmp_path / "env"

    run_session_hook(repo, stub_uv, env_file)
    run_session_hook(repo, stub_uv, env_file)

    lines = env_file.read_text().splitlines()
    assert lines.count("export PREPUSH_CI=full") == 1
    assert len([line for line in lines if line.startswith("export PATH=")]) == 1
    assert tool_dir.as_posix() in env_file.read_text()


@POSIX_ONLY
def test_the_session_hook_starts_its_line_on_a_new_line_after_an_env_file_without_one(
    repo: Path, stub_uv: Path, tmp_path: Path
) -> None:
    init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")
    env_file = tmp_path / "env"
    env_file.write_text("export FOO=1")

    run_session_hook(repo, stub_uv, env_file)

    lines = env_file.read_text().splitlines()
    assert lines[0] == "export FOO=1"
    assert "export PREPUSH_CI=full" in lines


@POSIX_ONLY
def test_a_commit_in_the_session_gets_the_trailer_without_the_tool_on_path(
    repo: Path, stub_uv: Path, tmp_path: Path, git: Git
) -> None:
    init(repo, "--non-interactive", "--check", "true", "--hooks", "native")
    env_file = tmp_path / "env"
    run_session_hook(repo, stub_uv, env_file)
    (repo / "x.txt").write_text("x")
    git(repo, "add", "x.txt")

    subprocess.run(
        ["sh", "-c", f'. "{env_file}" && git commit -q -m "add x"'],
        cwd=repo,
        check=True,
        env={**os.environ, "PATH": path_without_the_tool(), "GIT_AUTHOR_NAME": "T"},
    )

    assert (
        git(repo, "log", "-1", "--format=%B")
        .stdout.strip()
        .endswith("Prepush-CI: full")
    )


@POSIX_ONLY
def test_a_hook_manager_finds_the_tool_in_the_session(
    repo: Path, stub_uv: Path, tmp_path: Path
) -> None:
    (repo / ".husky").mkdir()
    init(repo, "--non-interactive", "--check", "true", "--hooks", "husky")
    env_file = tmp_path / "env"
    run_session_hook(repo, stub_uv, env_file)
    message = tmp_path / "message"
    message.write_text("add x\n")

    subprocess.run(
        ["sh", "-c", f'. "{env_file}" && sh .husky/commit-msg "{message}"'],
        cwd=repo,
        check=True,
        env={**os.environ, "PATH": path_without_the_tool()},
    )

    assert message.read_text().strip().endswith("Prepush-CI: full")


@POSIX_ONLY
def test_the_session_hook_warns_and_succeeds_when_there_is_no_env_file(
    repo: Path, stub_uv: Path
) -> None:
    init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    result = run_session_hook(repo, stub_uv, None)

    assert result.returncode == 0
    assert "CLAUDE_ENV_FILE" in result.stderr


def test_an_existing_session_hook_is_kept_and_reported_so(repo: Path) -> None:
    hook = repo / SESSION_HOOK
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\necho mine\n")
    before = hook.read_bytes()

    result = init(repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none")

    assert hook.read_bytes() == before
    assert f"kept: {SESSION_HOOK}" in result.stdout


def test_opting_out_writes_no_session_hook(repo: Path) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--hooks",
        "none",
        "--no-session-hook",
    )

    assert result.returncode == 0, result.stderr
    assert not (repo / ".claude").exists()


SETTINGS = ".claude/settings.json"


def settings_of(repo: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads((repo / SETTINGS).read_text(encoding="utf-8"))
    return parsed


def quick_init(repo: Path, *extra: str) -> "subprocess.CompletedProcess[str]":
    return init(
        repo, "--non-interactive", "--check", "scripts/ci", "--hooks", "none", *extra
    )


def test_the_settings_file_is_created_with_the_hook_registered(repo: Path) -> None:
    result = quick_init(repo)

    assert result.returncode == 0, result.stderr
    hook = settings_of(repo)["hooks"]["SessionStart"][0]["hooks"][0]
    assert hook["type"] == "command"
    assert ".claude/hooks/session-start.sh" in hook["command"]
    assert f"written: {SETTINGS}" in result.stdout


def test_existing_settings_stay_and_the_hook_is_added_next_to_them(repo: Path) -> None:
    before = {
        "permissions": {"allow": ["Bash(ls)"]},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]},
    }
    (repo / ".claude").mkdir()
    (repo / SETTINGS).write_text(json.dumps(before))

    result = quick_init(repo)

    after = settings_of(repo)
    assert after["permissions"] == before["permissions"]
    assert after["hooks"]["PreToolUse"] == before["hooks"]["PreToolUse"]
    assert (
        ".claude/hooks/session-start.sh"
        in after["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    )
    assert f"updated: {SETTINGS}" in result.stdout


def test_a_second_run_registers_the_hook_only_once(repo: Path) -> None:
    quick_init(repo)
    before = (repo / SETTINGS).read_bytes()

    second = quick_init(repo)

    assert len(settings_of(repo)["hooks"]["SessionStart"]) == 1
    assert (repo / SETTINGS).read_bytes() == before
    assert f"kept: {SETTINGS}" in second.stdout


def test_settings_that_are_not_json_are_refused_before_any_write(repo: Path) -> None:
    (repo / ".claude").mkdir()
    (repo / SETTINGS).write_text("{not json")
    before = snapshot(repo)

    result = quick_init(repo)

    assert result.returncode == 1
    assert SETTINGS in result.stderr
    assert snapshot(repo) == before


def test_settings_of_an_unexpected_shape_are_refused_and_left_as_they_are(
    repo: Path,
) -> None:
    (repo / ".claude").mkdir()
    (repo / SETTINGS).write_text('{"hooks": {"SessionStart": "x"}}')
    before = snapshot(repo)

    result = quick_init(repo)

    assert result.returncode == 1
    assert SETTINGS in result.stderr
    assert snapshot(repo) == before


DOCS_CI = Path(__file__).parents[2] / "docs" / "ci"


def gate_text(name: str) -> str:
    return (DOCS_CI / name).read_text(encoding="utf-8")


def ci_init(repo: Path, *extra: str) -> "subprocess.CompletedProcess[str]":
    return quick_init(repo, "--no-session-hook", *extra)


def test_github_actions_is_detected_and_its_gate_printed_whole(repo: Path) -> None:
    workflow = repo / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: ci\n")

    result = ci_init(repo)

    assert gate_text("github-actions.yml") in result.stdout
    assert workflow.read_text() == "name: ci\n"


def test_gitlab_ci_is_detected_when_there_is_no_workflow(repo: Path) -> None:
    (repo / ".gitlab-ci.yml").write_text("stages: []\n")

    result = ci_init(repo)

    assert gate_text("gitlab-ci.yml") in result.stdout
    assert gate_text("github-actions.yml") not in result.stdout


def test_the_generic_gate_is_printed_when_nothing_is_detected(repo: Path) -> None:
    result = ci_init(repo)

    assert gate_text("gate.sh") in result.stdout


def test_a_directory_of_workflows_without_a_workflow_file_detects_nothing(
    repo: Path,
) -> None:
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "notes.txt").write_text("x")

    result = ci_init(repo)

    assert gate_text("gate.sh") in result.stdout


def test_ci_chooses_the_system_by_hand(repo: Path) -> None:
    workflow = repo / ".github" / "workflows" / "ci.yaml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: ci\n")

    result = ci_init(repo, "--ci", "gitlab")

    assert gate_text("gitlab-ci.yml") in result.stdout
    assert gate_text("github-actions.yml") not in result.stdout


def test_ci_none_prints_no_snippet(repo: Path) -> None:
    result = ci_init(repo, "--ci", "none")

    assert result.returncode == 0, result.stderr
    for name in ("github-actions.yml", "gitlab-ci.yml", "gate.sh"):
        assert gate_text(name) not in result.stdout


def test_the_snippet_is_written_to_the_file_and_not_printed(repo: Path) -> None:
    result = ci_init(repo, "--ci", "github", "--ci-gate-file", "ci/gate.yml")

    assert result.returncode == 0, result.stderr
    assert (repo / "ci" / "gate.yml").read_text() == gate_text("github-actions.yml")
    assert gate_text("github-actions.yml") not in result.stdout
    assert "written: ci/gate.yml" in result.stdout


def test_another_file_in_the_way_stops_init_before_any_write(repo: Path) -> None:
    (repo / "ci").mkdir()
    (repo / "ci" / "gate.yml").write_text("mine\n")
    before = snapshot(repo)

    result = ci_init(repo, "--ci-gate-file", "ci/gate.yml")

    assert result.returncode == 1
    assert "ci/gate.yml" in result.stderr
    assert snapshot(repo) == before


def test_a_file_that_holds_the_snippet_already_is_left_alone(repo: Path) -> None:
    ci_init(repo, "--ci-gate-file", "gate.sh")
    before = snapshot(repo)

    second = ci_init(repo, "--ci-gate-file", "gate.sh")

    assert second.returncode == 0, second.stderr
    assert "kept: gate.sh" in second.stdout
    assert "already set up" in last_line(second)
    assert snapshot(repo) == before


def test_init_from_a_subdirectory_puts_the_files_at_the_root_and_the_gate_here(
    repo: Path,
) -> None:
    sub = repo / "sub"
    sub.mkdir()

    result = init(
        sub,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--hooks",
        "none",
        "--ci-gate-file",
        "gate.yml",
    )

    assert result.returncode == 0, result.stderr
    assert files(repo) == {".prepush-ci.toml", SESSION_HOOK, SETTINGS, "sub/gate.yml"}


def test_a_whole_second_run_changes_nothing(repo: Path) -> None:
    args = (
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--hooks",
        "native",
        "--ci",
        "github",
        "--ci-gate-file",
        "ci/gate.yml",
    )
    init(repo, *args)
    before = snapshot(repo)

    second = init(repo, *args)

    assert second.returncode == 0, second.stderr
    assert "already set up" in last_line(second)
    assert snapshot(repo) == before


def test_a_whole_first_run_with_every_step_ends_with_set_up(repo: Path) -> None:
    result = init(repo, "--non-interactive", "--check", "scripts/ci")

    assert result.returncode == 0, result.stderr
    assert "set up" in last_line(result)
    assert "already set up" not in last_line(result)


def answers(*lines: str) -> str:
    return "".join(f"{line}\n" for line in lines)


EMPTY = (
    "",
    "",
    "",
    "",
    "",
)  # check, preflight, require_env, default_branch, up-to-date


def test_detected_defaults_are_shown_and_taken_on_an_empty_answer(
    repo: Path, git: Git
) -> None:
    (repo / "scripts").mkdir()
    (repo / "scripts" / "ci").write_text("#!/bin/sh\n")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")

    result = init(repo, "--hooks", "none", stdin=answers(*EMPTY, ""))

    assert result.returncode == 0, result.stderr
    assert "[scripts/ci]" in result.stdout
    assert "[trunk]" in result.stdout
    config = config_of(repo)
    assert (config.check, config.default_branch) == ("scripts/ci", "trunk")


def test_a_typed_check_is_what_the_config_holds(repo: Path) -> None:
    result = init(repo, "--hooks", "none", stdin=answers("make ci", "", "", "", "", ""))

    assert result.returncode == 0, result.stderr
    assert config_of(repo).check == "make ci"


def test_a_flag_answers_its_question(repo: Path) -> None:
    result = init(
        repo,
        "--check",
        "scripts/ci",
        "--hooks",
        "none",
        stdin=answers("", "", "", "", ""),
    )

    assert result.returncode == 0, result.stderr
    assert "runs your full CI check" not in result.stdout
    assert "preflight" in result.stdout


def test_declining_the_session_hook_writes_none(repo: Path) -> None:
    result = init(
        repo,
        "--check",
        "scripts/ci",
        "--hooks",
        "none",
        stdin=answers("", "", "", "", "n"),
    )

    assert result.returncode == 0, result.stderr
    assert not (repo / ".claude").exists()


def test_the_branch_default_is_main_without_origin_head(repo: Path) -> None:
    result = init(
        repo, "--check", "x", "--hooks", "none", stdin=answers("", "", "", "", "")
    )

    assert "[main]" in result.stdout


def test_a_makefile_target_is_the_default_check(repo: Path) -> None:
    (repo / "Makefile").write_text("all:\n\ttrue\n\nci: all\n\ttrue\n")

    result = init(repo, "--hooks", "none", stdin=answers(*EMPTY, "n"))

    assert "[make ci]" in result.stdout
    assert config_of(repo).check == "make ci"


def test_a_makefile_without_a_ci_target_is_no_default(repo: Path) -> None:
    (repo / "Makefile").write_text("all:\n\ttrue\n")

    result = init(repo, "--hooks", "none", stdin=answers(*EMPTY, "n"))

    assert result.returncode == 1
    assert "check" in result.stderr
    assert files(repo) == {"Makefile"}


def test_bin_ci_comes_after_scripts_ci(repo: Path) -> None:
    (repo / "bin").mkdir()
    (repo / "bin" / "ci").write_text("#!/bin/sh\n")

    result = init(repo, "--hooks", "none", stdin=answers(*EMPTY, "n"))

    assert config_of(repo).check == "bin/ci"
    assert result.returncode == 0, result.stderr


def test_the_answer_false_switches_the_up_to_date_check_off(repo: Path) -> None:
    result = init(
        repo, "--hooks", "none", stdin=answers("make ci", "", "", "", "false", "n")
    )

    assert result.returncode == 0, result.stderr
    assert config_of(repo).require_up_to_date is None


def test_answers_equal_to_the_built_in_defaults_are_not_written(
    repo: Path, git: Git
) -> None:
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    init(repo, "--hooks", "none", stdin=answers("make ci", "", "", "", "", "n"))

    assert (repo / ".prepush-ci.toml").read_text() == 'check = "make ci"\n'


def test_an_answer_that_differs_is_written_and_a_default_is_not(repo: Path) -> None:
    init(repo, "--hooks", "none", stdin=answers("make ci", "", "", "trunk", "", "n"))

    text = (repo / ".prepush-ci.toml").read_text()
    assert 'default_branch = "trunk"' in text
    assert "require_up_to_date" not in text
    assert "preflight" not in text


def test_the_other_answers_are_written_when_given(repo: Path) -> None:
    init(
        repo,
        "--hooks",
        "none",
        stdin=answers("make ci", "make up", "A, B", "", "upstream/main", "n"),
    )

    config = config_of(repo)
    assert config.preflight == "make up"
    assert config.require_env == ("A", "B")
    assert config.require_up_to_date == "upstream/main"


def test_a_flag_is_written_as_given_even_when_it_equals_the_default(repo: Path) -> None:
    init(
        repo,
        "--check",
        "make ci",
        "--default-branch",
        "main",
        "--hooks",
        "none",
        stdin=answers("", "", "", "n"),
    )

    assert 'default_branch = "main"' in (repo / ".prepush-ci.toml").read_text()


def test_an_existing_config_asks_no_config_question(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')

    result = init(repo, "--hooks", "none", stdin=answers("n"))

    assert result.returncode == 0, result.stderr
    assert "preflight" not in result.stdout
    assert not (repo / ".claude").exists()


def test_an_existing_pre_push_hook_is_named_in_the_hooks_question(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\nexit 0\n")
    hook.chmod(0o755)

    result = init(repo, "--check", "x", stdin=answers("", "", "", "", "none", "n"))

    assert ".git/hooks/pre-push" in result.stdout


def test_a_manager_is_named_and_is_the_default_answer(repo: Path) -> None:
    (repo / "lefthook.yml").write_text("")

    result = init(repo, "--check", "x", stdin=answers("", "", "", "", "", "n"))

    assert result.returncode == 0, result.stderr
    assert "lefthook.yml" in result.stdout
    assert "prepush-ci: begin" in (repo / "lefthook.yml").read_text()


def test_the_answer_none_installs_no_hooks(repo: Path, git: Git) -> None:
    result = init(repo, "--check", "x", stdin=answers("", "", "", "", "none", "n"))

    assert result.returncode == 0, result.stderr
    assert hooks_path(repo, git) == ""
    assert not (repo / ".git" / "prepush-ci").exists()


def test_with_nothing_found_all_five_choices_are_listed_and_native_is_the_default(
    repo: Path, git: Git
) -> None:
    result = init(repo, "--check", "x", stdin=answers("", "", "", "", "", "n"))

    for choice in ("native", "pre-commit", "husky", "lefthook", "none"):
        assert choice in result.stdout
    assert "[native]" in result.stdout
    assert hooks_path(repo, git).endswith(".git/prepush-ci/hooks")


def test_several_managers_leave_no_default_and_an_empty_answer_is_refused(
    repo: Path,
) -> None:
    (repo / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n"
    )
    (repo / "lefthook.yml").write_text("")

    result = init(repo, "--check", "x", stdin=answers("", "", "", "", "", "n"))

    assert result.returncode == 1
    assert "pre-commit" in result.stderr and "none" in result.stderr
    assert not (repo / ".prepush-ci.toml").exists()


def test_an_unknown_hooks_answer_names_the_valid_ones_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(repo, "--check", "x", stdin=answers("", "", "", "", "jenkins", "n"))

    assert result.returncode == 1
    for choice in ("native", "pre-commit", "husky", "lefthook", "none"):
        assert choice in result.stderr
    assert files(repo) == set()


def test_an_unknown_session_hook_answer_names_the_valid_ones_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(repo, "--check", "x", stdin=answers("", "", "", "", "none", "maybe"))

    assert result.returncode == 1
    assert "y" in result.stderr and "n" in result.stderr
    assert files(repo) == set()


def test_input_that_ends_early_names_non_interactive_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(repo, stdin="")

    assert result.returncode == 1
    assert "--non-interactive" in result.stderr
    assert files(repo) == set()


def test_the_session_hook_script_gets_the_hooks_that_were_chosen(repo: Path) -> None:
    (repo / ".husky").mkdir()

    init(repo, "--check", "x", stdin=answers("", "", "", "", "husky", ""))

    assert "prepush-ci install --hooks husky\n" in (repo / SESSION_HOOK).read_text()


def test_an_empty_required_variable_is_refused_naming_the_key_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "true",
        "--require-env",
        "",
        "--hooks",
        "none",
    )

    assert result.returncode == 1
    assert "`require_env`" in result.stderr
    assert "Traceback" not in result.stderr
    assert files(repo) == set()


def test_a_name_the_hook_would_drop_is_refused_naming_the_key_and_the_entry_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "true",
        "--require-env",
        "DATABASE URL",
        "--hooks",
        "none",
    )

    assert result.returncode == 1
    assert "`require_env`" in result.stderr
    assert "'DATABASE URL'" in result.stderr
    assert "Traceback" not in result.stderr
    assert files(repo) == set()


def test_an_interactive_answer_with_an_equals_sign_is_refused_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(repo, "--hooks", "none", stdin=answers("true", "", "A=1", "", "", ""))

    assert result.returncode == 1
    assert "`require_env`" in result.stderr
    assert "'A=1'" in result.stderr
    assert files(repo) == set()


@pytest.mark.parametrize("value", ["refs/remotes/origin/trunk", "origin/trunk"])
def test_a_default_branch_flag_that_is_not_a_branch_name_is_refused_and_writes_nothing(
    repo: Path, value: str
) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--default-branch",
        value,
        "--hooks",
        "none",
    )

    assert result.returncode == 1
    assert "`default_branch`" in result.stderr
    assert 'use "trunk"' in result.stderr
    assert "Traceback" not in result.stderr
    assert files(repo) == set()


def test_a_default_branch_answer_that_is_not_a_branch_name_is_refused_and_writes_nothing(
    repo: Path,
) -> None:
    result = init(
        repo,
        "--hooks",
        "none",
        stdin=answers("scripts/ci", "", "", "refs/remotes/origin/trunk", "", "n"),
    )

    assert result.returncode == 1
    assert "`default_branch`" in result.stderr
    assert 'use "trunk"' in result.stderr
    assert files(repo) == set()


def test_the_default_branch_name_is_accepted_by_init(repo: Path) -> None:
    result = init(
        repo,
        "--non-interactive",
        "--check",
        "scripts/ci",
        "--default-branch",
        "main",
        "--hooks",
        "none",
    )

    assert result.returncode == 0, result.stderr
    assert config_of(repo).default_branch == "main"
