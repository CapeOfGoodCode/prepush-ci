"""`prepush-ci install` for hook managers: the manager's own files, run by the real manager and git."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

Git = Callable[..., "subprocess.CompletedProcess[str]"]

TRAILER = "Prepush-CI: full"
PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"


@pytest.fixture
def shim(tmp_path: Path) -> Path:
    """A directory with a `prepush-ci` command that starts this interpreter's module, so that the
    files the manager runs find the tool on `PATH` and coverage measures it."""
    directory = tmp_path / "shim"
    directory.mkdir()
    python = Path(sys.executable).as_posix()
    script = directory / "prepush-ci"
    script.write_text(f'#!/bin/sh\nexec "{python}" -m prepush_ci "$@"\n')
    script.chmod(0o755)
    (directory / "prepush-ci.cmd").write_text(
        f'@"{sys.executable}" -m prepush_ci %*\r\n'
    )  # pre-commit on Windows looks for an executable extension
    return directory


@pytest.fixture
def env(shim: Path, tmp_path: Path) -> dict[str, str]:
    """The environment of every command: the shim first on `PATH`, pre-commit's cache away from
    the developer's home, no inherited opt-in or pre-commit variables."""
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return {
        **inherited,
        "PATH": os.pathsep.join([str(shim), os.environ["PATH"]]),
        "PRE_COMMIT_HOME": str(tmp_path / "pre-commit-home"),
    }


@pytest.fixture
def ran(tmp_path: Path) -> Path:
    """The file the config's check appends to."""
    return tmp_path / "ran.log"


@pytest.fixture
def pushing(repo: Path, tmp_path: Path, git: Git, ran: Path) -> Path:
    """`repo` on `main` with one commit, a config whose check logs to `ran` and a bare `origin`."""
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()}"\nrequire_up_to_date = false\n'
    )
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    return repo


def install(
    repo: Path, env: dict[str, str], *args: str
) -> "subprocess.CompletedProcess[str]":
    """Run `prepush-ci install` in `repo`."""
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "install", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def pre_commit_install(repo: Path, env: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def log_hook(directory: Path, log: Path) -> str:
    """The text of a `local` pre-commit hook `lint` without `stages` that appends to `log`."""
    script = directory / "lint.sh"
    script.write_text(f"#!/bin/sh\necho lint >> {log.as_posix()}\n")
    return (
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: lint\n"
        "        name: lint\n"
        f"        entry: sh {script.as_posix()}\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
    )


def commit(
    repo: Path, git: Git, env: dict[str, str], message: str = "add x"
) -> "subprocess.CompletedProcess[str]":
    (repo / "x.txt").write_text(message)
    git(repo, "add", "x.txt")
    return git(
        repo,
        "commit",
        "-q",
        "-m",
        message,
        env={**env, "PREPUSH_CI": "full"},
        check=False,
    )


def body(repo: Path, git: Git, rev: str = "HEAD") -> str:
    return git(repo, "log", "-1", "--format=%B", rev).stdout.strip()


def remote_has(repo: Path, git: Git, sha: str) -> bool:
    return git(repo, "ls-remote", "origin", "refs/heads/main").stdout.startswith(sha)


def lines(path: Path) -> list[str]:
    return path.read_text().split() if path.exists() else []


# pre-commit


def test_a_commit_through_pre_commit_gets_the_trailer_and_the_other_hook_runs(
    pushing: Path, tmp_path: Path, git: Git, env: dict[str, str]
) -> None:
    log = tmp_path / "lint.log"
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n" + log_hook(tmp_path, log))

    result = install(pushing, env)
    pre_commit_install(pushing, env)
    committed = commit(pushing, git, env)

    assert result.returncode == 0, result.stderr
    assert committed.returncode == 0, committed.stderr
    assert body(pushing, git).endswith(TRAILER)
    assert lines(log) == ["lint"]


def test_a_push_through_pre_commit_runs_the_check_and_reaches_the_remote(
    pushing: Path, git: Git, env: dict[str, str], ran: Path
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG)
    commit(pushing, git, env)
    sha = git(pushing, "rev-parse", "HEAD").stdout.strip()

    pushed = git(pushing, "push", "origin", "main", env=env, check=False)

    assert pushed.returncode == 0, pushed.stderr
    assert lines(ran) == ["ran"]
    assert remote_has(pushing, git, sha)


def test_a_failing_check_refuses_a_push_through_pre_commit(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    (pushing / ".prepush-ci.toml").write_text(
        'check = "exit 1"\nrequire_up_to_date = false\n'
    )
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG, ".prepush-ci.toml")
    commit(pushing, git, env)

    pushed = git(pushing, "push", "origin", "main", env=env, check=False)

    assert pushed.returncode != 0
    assert git(pushing, "ls-remote", "origin").stdout == ""


def test_an_existing_pre_commit_hook_runs_on_commit_and_never_on_push(
    pushing: Path, tmp_path: Path, git: Git, env: dict[str, str]
) -> None:
    log = tmp_path / "lint.log"
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n" + log_hook(tmp_path, log))
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG)
    commit(pushing, git, env)
    after_commit = lines(log)

    git(pushing, "push", "origin", "main", env=env)

    assert after_commit == ["lint"]
    assert lines(log) == ["lint"]


def test_hook_types_the_team_already_used_keep_their_stages(
    pushing: Path, tmp_path: Path, git: Git, env: dict[str, str]
) -> None:
    log = tmp_path / "lint.log"
    (pushing / PRE_COMMIT_CONFIG).write_text(
        "default_install_hook_types: [pre-commit, pre-push]\n"
        "repos:\n" + log_hook(tmp_path, log)
    )
    install(pushing, env)
    pre_commit_install(pushing, env)
    git(pushing, "add", PRE_COMMIT_CONFIG)
    commit(pushing, git, env)
    git(pushing, "push", "origin", "main", env=env)

    text = (pushing / PRE_COMMIT_CONFIG).read_text()
    assert "default_stages: [pre-commit, pre-push]\n" in text
    assert lines(log) == ["lint", "lint"]  # once on the commit, once on the push


def test_a_pre_commit_config_without_hook_types_gets_all_three_installed(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    install(pushing, env)
    pre_commit_install(pushing, env)

    text = (pushing / PRE_COMMIT_CONFIG).read_text()
    assert "default_install_hook_types: [pre-commit, commit-msg, pre-push]\n" in text
    hooks = {path.name for path in (pushing / ".git" / "hooks").iterdir()}
    assert {"pre-commit", "commit-msg", "pre-push"} <= hooks


def test_a_pre_commit_config_that_is_not_a_block_list_is_refused_and_unchanged(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos: []\n")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "repos" in result.stderr
    assert (pushing / PRE_COMMIT_CONFIG).read_text() == "repos: []\n"


def test_a_pre_commit_install_leaves_git_alone(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    before = sorted(p.name for p in (pushing / ".git" / "hooks").iterdir())

    result = install(pushing, env, "--hooks", "pre-commit")

    assert result.returncode == 0, result.stderr
    assert git(pushing, "config", "core.hooksPath", check=False).stdout == ""
    assert sorted(p.name for p in (pushing / ".git" / "hooks").iterdir()) == before
    assert not (pushing / ".git" / "prepush-ci").exists()


def test_the_pre_commit_block_holds_no_local_path_and_no_check_command(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    (pushing / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')

    install(pushing, env, "--hooks", "pre-commit")

    written = (pushing / PRE_COMMIT_CONFIG).read_text()
    assert "prepush-ci hook" in written
    assert str(pushing) not in written
    assert Path(sys.executable).as_posix() not in written
    assert "scripts/ci" not in written
    assert "args:" not in written


def test_a_second_pre_commit_install_writes_nothing_and_says_so(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / PRE_COMMIT_CONFIG
    path.write_text("repos:\n  - repo: local\n    hooks: []\n")
    first = install(pushing, env, "--hooks", "pre-commit")
    stamp = path.stat().st_mtime_ns
    contents = path.read_text()

    second = install(pushing, env, "--hooks", "pre-commit")

    assert "installed" in first.stdout and "already installed" not in first.stdout
    assert second.returncode == 0
    assert "already installed" in second.stdout
    assert (path.read_text(), path.stat().st_mtime_ns) == (contents, stamp)


def test_a_hand_edited_pre_commit_block_is_restored_and_reported_updated(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / PRE_COMMIT_CONFIG
    path.write_text("repos:\n  - repo: local\n    hooks: []\n")
    install(pushing, env, "--hooks", "pre-commit")
    installed = path.read_text()
    path.write_text(installed.replace("language: system", "language: fail", 1))

    result = install(pushing, env, "--hooks", "pre-commit")

    assert "updated" in result.stdout
    assert path.read_text() == installed


def test_the_pre_commit_report_names_the_file_and_the_activation_step(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    result = install(pushing, env, "--hooks", "pre-commit")

    assert PRE_COMMIT_CONFIG in result.stdout
    assert "pre-commit install" in result.stdout


# husky


ZEROS = "0" * 40


def husky_hook(repo: Path, name: str, text: str) -> Path:
    path = repo / ".husky" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, newline="\n")
    return path


def commit_trailer(repo: Path, git: Git, *paths: str) -> str:
    """Commit `paths` with the trailer in its message; no hook is installed yet."""
    git(repo, "add", *paths)
    git(repo, "commit", "-q", "-m", f"work\n\n{TRAILER}")
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def run_hook(
    repo: Path, env: dict[str, str], name: str, *args: str, stdin: str = ""
) -> "subprocess.CompletedProcess[str]":
    """Run a husky hook file with `sh`, as git does."""
    return subprocess.run(
        ["sh", f".husky/{name}", *args],
        cwd=repo,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def ref_line(sha: str) -> str:
    return f"refs/heads/main {sha} refs/heads/main {ZEROS}\n"


@pytest.fixture
def husky_repo(pushing: Path) -> Path:
    """`pushing` with an empty `.husky` directory."""
    (pushing / ".husky").mkdir()
    return pushing


def test_husky_hook_files_are_created_executable_with_the_block(
    husky_repo: Path, env: dict[str, str]
) -> None:
    result = install(husky_repo, env)

    assert result.returncode == 0, result.stderr
    for name in ("commit-msg", "pre-push"):
        path = husky_repo / ".husky" / name
        text = path.read_text()
        assert text.startswith("#!/usr/bin/env sh\n# prepush-ci: begin\n")
        assert f"prepush-ci hook {name}" in text
        assert text.endswith("# prepush-ci: end\n")
    if sys.platform != "win32":  # Windows has no executable bit
        assert os.access(husky_repo / ".husky" / "commit-msg", os.X_OK)
        assert os.access(husky_repo / ".husky" / "pre-push", os.X_OK)


def test_a_husky_shebang_stays_first_and_the_old_lines_follow_the_block(
    husky_repo: Path, env: dict[str, str]
) -> None:
    path = husky_hook(husky_repo, "pre-push", "#!/bin/sh\nnpm test\n# keep me\n")

    install(husky_repo, env, "--hooks", "husky")

    text = path.read_text()
    assert text.startswith("#!/bin/sh\n# prepush-ci: begin\n")
    assert text.endswith("# prepush-ci: end\nnpm test\n# keep me\n")


def test_a_husky_file_without_a_shebang_gets_the_block_first(
    husky_repo: Path, env: dict[str, str]
) -> None:
    path = husky_hook(husky_repo, "commit-msg", "npm test\n")

    install(husky_repo, env, "--hooks", "husky")

    assert path.read_text().startswith("# prepush-ci: begin\n")
    assert path.read_text().endswith("# prepush-ci: end\nnpm test\n")


def test_the_husky_commit_msg_file_writes_the_trailer(
    husky_repo: Path, env: dict[str, str]
) -> None:
    install(husky_repo, env)
    message = husky_repo / "message.txt"
    message.write_text("add x\n")

    result = run_hook(
        husky_repo, {**env, "PREPUSH_CI": "full"}, "commit-msg", str(message)
    )

    assert result.returncode == 0, result.stderr
    assert message.read_text().strip().endswith(TRAILER)


def test_the_husky_pre_push_file_runs_the_check(
    husky_repo: Path, git: Git, env: dict[str, str], ran: Path
) -> None:
    install(husky_repo, env)
    sha = commit_trailer(husky_repo, git, ".husky")

    result = run_hook(husky_repo, env, "pre-push", "origin", "url", stdin=ref_line(sha))

    assert result.returncode == 0, result.stderr
    assert lines(ran) == ["ran"]


def test_a_failing_check_stops_the_husky_hook_before_the_later_lines(
    husky_repo: Path, git: Git, env: dict[str, str], tmp_path: Path
) -> None:
    (husky_repo / ".prepush-ci.toml").write_text(
        'check = "exit 1"\nrequire_up_to_date = false\n'
    )
    later = tmp_path / "later.log"
    husky_hook(husky_repo, "pre-push", f"echo later >> {later.as_posix()}\n")
    install(husky_repo, env)
    sha = commit_trailer(husky_repo, git, ".husky", ".prepush-ci.toml")

    result = run_hook(husky_repo, env, "pre-push", "origin", "url", stdin=ref_line(sha))

    assert result.returncode != 0
    assert not later.exists()


def test_a_later_husky_line_that_reads_standard_input_does_not_hide_the_refs(
    husky_repo: Path, git: Git, env: dict[str, str], ran: Path, tmp_path: Path
) -> None:
    (husky_repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()} && exit 1"\nrequire_up_to_date = false\n'
    )
    copy = tmp_path / "stdin.copy"
    husky_hook(husky_repo, "pre-push", f"cat > {copy.as_posix()}\n")
    install(husky_repo, env)
    sha = commit_trailer(husky_repo, git, ".husky", ".prepush-ci.toml")

    failing = run_hook(
        husky_repo, env, "pre-push", "origin", "url", stdin=ref_line(sha)
    )

    assert lines(ran) == ["ran"]
    assert failing.returncode != 0


def test_later_husky_lines_still_get_the_ref_lines(
    husky_repo: Path, git: Git, env: dict[str, str], tmp_path: Path
) -> None:
    copy = tmp_path / "stdin.copy"
    husky_hook(husky_repo, "pre-push", f"cat > {copy.as_posix()}\n")
    install(husky_repo, env)
    sha = commit_trailer(husky_repo, git, ".husky")

    run_hook(husky_repo, env, "pre-push", "origin", "url", stdin=ref_line(sha))

    assert copy.read_text().strip() == ref_line(sha).strip()


def test_a_later_exit_zero_in_a_husky_hook_does_not_skip_the_check(
    husky_repo: Path, git: Git, env: dict[str, str], ran: Path
) -> None:
    (husky_repo / ".prepush-ci.toml").write_text(
        f'check = "echo ran >> {ran.as_posix()} && exit 1"\nrequire_up_to_date = false\n'
    )
    husky_hook(husky_repo, "pre-push", "exit 0\n")
    install(husky_repo, env)
    sha = commit_trailer(husky_repo, git, ".husky", ".prepush-ci.toml")

    result = run_hook(husky_repo, env, "pre-push", "origin", "url", stdin=ref_line(sha))

    assert lines(ran) == ["ran"]
    assert result.returncode != 0


def test_real_git_runs_the_husky_files_for_a_commit_and_a_push(
    husky_repo: Path, git: Git, env: dict[str, str], ran: Path
) -> None:
    install(husky_repo, env)
    git(husky_repo, "config", "core.hooksPath", ".husky")  # what husky's prepare does
    git(husky_repo, "add", ".husky")
    git(husky_repo, "commit", "-q", "-m", "add husky", env={**env})
    commit(husky_repo, git, env)
    sha = git(husky_repo, "rev-parse", "HEAD").stdout.strip()

    pushed = git(husky_repo, "push", "origin", "main", env=env, check=False)

    assert body(husky_repo, git).endswith(TRAILER)
    assert pushed.returncode == 0, pushed.stderr
    assert lines(ran) == ["ran"]
    assert remote_has(husky_repo, git, sha)


def test_a_husky_install_refuses_before_writing_when_a_hook_path_is_a_directory(
    husky_repo: Path, env: dict[str, str]
) -> None:
    (husky_repo / ".husky" / "pre-push").mkdir()

    result = install(husky_repo, env, "--hooks", "husky")

    assert result.returncode == 1
    assert ".husky/pre-push" in result.stderr
    assert not (husky_repo / ".husky" / "commit-msg").exists()


def test_a_husky_install_creates_no_native_files(
    husky_repo: Path, env: dict[str, str]
) -> None:
    native = husky_repo / ".git" / "hooks" / "pre-push"
    native.write_text("#!/bin/sh\necho mine\n")

    install(husky_repo, env, "--hooks", "husky")

    assert not (husky_repo / ".git" / "prepush-ci" / "hooks").exists()
    assert native.read_text() == "#!/bin/sh\necho mine\n"


def test_the_husky_report_names_both_files_and_no_activation_step(
    husky_repo: Path, env: dict[str, str]
) -> None:
    result = install(husky_repo, env, "--hooks", "husky")

    assert ".husky/commit-msg" in result.stdout
    assert ".husky/pre-push" in result.stdout
    assert "next:" not in result.stdout


def test_the_husky_block_holds_no_local_path(
    husky_repo: Path, env: dict[str, str]
) -> None:
    install(husky_repo, env, "--hooks", "husky")

    for name in ("commit-msg", "pre-push"):
        text = (husky_repo / ".husky" / name).read_text()
        assert str(husky_repo) not in text
        assert Path(sys.executable).as_posix() not in text


# lefthook


LEFTHOOK_CONFIG = (
    "pre-commit:\n  commands:\n    lint:\n      run: make lint\n"
    "pre-push:\n  commands:\n    test:\n      run: make test\n"
)


def parsed(path: Path) -> dict[str, dict[str, dict[str, dict[str, object]]]]:
    loaded = yaml.safe_load(path.read_text())
    assert isinstance(loaded, dict)
    return loaded


def test_a_lefthook_config_under_a_dotted_name_is_detected_and_no_other_is_made(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / ".lefthook.yaml").write_text(LEFTHOOK_CONFIG)

    result = install(pushing, env)

    assert result.returncode == 0, result.stderr
    assert "prepush-ci hook" in (pushing / ".lefthook.yaml").read_text()
    assert not (pushing / "lefthook.yml").exists()


def test_the_lefthook_commands_pass_the_message_file_and_standard_input(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / "lefthook.yml"
    path.write_text(LEFTHOOK_CONFIG)

    install(pushing, env, "--hooks", "lefthook")

    config = parsed(path)
    assert (
        config["commit-msg"]["commands"]["prepush-ci"]["run"]
        == "prepush-ci hook commit-msg {1}"
    )
    assert config["pre-push"]["commands"]["prepush-ci"]["use_stdin"] is True
    assert set(config["pre-push"]["commands"]) == {"prepush-ci", "test"}
    assert config["pre-commit"] == parsed(path)["pre-commit"]


def test_the_lefthook_hook_sections_are_added_at_the_end_and_the_rest_is_unchanged(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / "lefthook.yml"
    original = "pre-commit:\n  commands:\n    lint:\n      run: make lint\n"
    path.write_text(original)

    install(pushing, env)

    text = path.read_text()
    assert text.startswith(original)
    assert text[len(original) :].startswith("commit-msg:\n  commands:\n")
    assert list(parsed(path)) == ["pre-commit", "commit-msg", "pre-push"]


def test_existing_lefthook_commands_stay_next_to_ours_under_the_same_key(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / "lefthook.yml"
    path.write_text(LEFTHOOK_CONFIG)

    install(pushing, env)

    text = path.read_text()
    assert "pre-push:\n  commands:\n    # prepush-ci: begin\n" in text
    assert "    test:\n      run: make test\n" in text
    assert list(parsed(path)["pre-push"]["commands"]) == ["prepush-ci", "test"]


def test_a_lefthook_hook_without_commands_is_refused_and_unchanged(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / "lefthook.yml"
    path.write_text("pre-push:\n  jobs:\n    - run: make test\n")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "pre-push" in result.stderr and "commands" in result.stderr
    assert path.read_text() == "pre-push:\n  jobs:\n    - run: make test\n"


def test_a_second_lefthook_install_writes_nothing(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / "lefthook.yml"
    path.write_text(LEFTHOOK_CONFIG)
    first = install(pushing, env)
    stamp, contents = path.stat().st_mtime_ns, path.read_text()

    second = install(pushing, env)

    assert "already installed" not in first.stdout and "installed" in first.stdout
    assert second.returncode == 0
    assert "already installed" in second.stdout
    assert (path.stat().st_mtime_ns, path.read_text()) == (stamp, contents)


def test_a_hand_edited_lefthook_block_is_restored_and_the_other_lines_stay(
    pushing: Path, env: dict[str, str]
) -> None:
    path = pushing / "lefthook.yml"
    path.write_text(LEFTHOOK_CONFIG)
    install(pushing, env)
    installed = path.read_text()
    path.write_text(installed.replace("use_stdin: true", "use_stdin: false"))

    result = install(pushing, env)

    assert "updated" in result.stdout
    assert path.read_text() == installed


def test_the_lefthook_report_names_the_file_and_the_activation_step(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / "lefthook.yml").write_text(LEFTHOOK_CONFIG)

    result = install(pushing, env)

    assert "lefthook.yml" in result.stdout
    assert "lefthook install" in result.stdout


def test_the_lefthook_block_holds_no_local_path_and_no_check_command(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    (pushing / ".prepush-ci.toml").write_text('check = "scripts/ci"\n')

    install(pushing, env)

    text = (pushing / "lefthook.yml").read_text()
    assert str(pushing) not in text
    assert Path(sys.executable).as_posix() not in text
    assert "scripts/ci" not in text


# the choice of hooks


def hooks_path(repo: Path, git: Git) -> str:
    return git(repo, "config", "--local", "core.hooksPath", check=False).stdout.strip()


def test_pre_commit_is_detected_and_core_hooks_path_stays_unset(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    install(pushing, env)

    assert "prepush-ci hook" in (pushing / PRE_COMMIT_CONFIG).read_text()
    assert hooks_path(pushing, git) == ""


def test_husky_is_detected_and_core_hooks_path_stays_unset(
    husky_repo: Path, git: Git, env: dict[str, str]
) -> None:
    install(husky_repo, env)

    for name in ("commit-msg", "pre-push"):
        assert "prepush-ci hook" in (husky_repo / ".husky" / name).read_text()
    assert hooks_path(husky_repo, git) == ""


def test_without_a_manager_the_hooks_are_native(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    result = install(pushing, env)

    assert result.returncode == 0, result.stderr
    configured = Path(hooks_path(pushing, git))
    assert configured == (pushing / ".git" / "prepush-ci" / "hooks").resolve()


def test_native_can_be_forced_in_a_repository_with_a_manager(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    config = "repos:\n  - repo: local\n    hooks: []\n"
    (pushing / PRE_COMMIT_CONFIG).write_text(config)

    install(pushing, env, "--hooks", "native")

    assert hooks_path(pushing, git) != ""
    assert (pushing / PRE_COMMIT_CONFIG).read_text() == config


def test_an_unknown_choice_of_hooks_exits_2_and_lists_the_four(
    pushing: Path, env: dict[str, str]
) -> None:
    result = install(pushing, env, "--hooks", "jenkins")

    assert result.returncode == 2
    for name in ("native", "pre-commit", "husky", "lefthook"):
        assert name in result.stderr


def test_two_managers_are_refused_by_name_and_neither_file_changes(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    (pushing / "lefthook.yml").write_text(LEFTHOOK_CONFIG)

    result = install(pushing, env)

    assert result.returncode == 1
    for word in ("pre-commit", "lefthook", "--hooks"):
        assert word in result.stderr
    assert (pushing / PRE_COMMIT_CONFIG).read_text().count("prepush-ci") == 0
    assert (pushing / "lefthook.yml").read_text() == LEFTHOOK_CONFIG


def test_the_option_settles_two_managers(pushing: Path, env: dict[str, str]) -> None:
    config = "repos:\n  - repo: local\n    hooks: []\n"
    (pushing / PRE_COMMIT_CONFIG).write_text(config)
    (pushing / "lefthook.yml").write_text(LEFTHOOK_CONFIG)

    result = install(pushing, env, "--hooks", "lefthook")

    assert result.returncode == 0, result.stderr
    assert "prepush-ci hook" in (pushing / "lefthook.yml").read_text()
    assert (pushing / PRE_COMMIT_CONFIG).read_text() == config


@pytest.mark.parametrize(
    ("manager", "missing"),
    [
        ("pre-commit", PRE_COMMIT_CONFIG),
        ("husky", ".husky"),
        ("lefthook", "lefthook.yml"),
    ],
)
def test_a_named_manager_without_its_files_is_refused_and_creates_nothing(
    pushing: Path, git: Git, env: dict[str, str], manager: str, missing: str
) -> None:
    before = git(pushing, "status", "--porcelain", "--ignored").stdout

    result = install(pushing, env, "--hooks", manager)

    assert result.returncode == 1
    assert missing in result.stderr
    assert git(pushing, "status", "--porcelain", "--ignored").stdout == before
    assert not (pushing / missing).exists()


def test_a_manager_is_installed_from_a_subdirectory_of_the_worktree(
    husky_repo: Path, env: dict[str, str]
) -> None:
    (husky_repo / "src").mkdir()

    result = install(husky_repo / "src", env)

    assert result.returncode == 0, result.stderr
    assert (husky_repo / ".husky" / "pre-push").exists()
    assert not (husky_repo / "src" / ".husky").exists()


def test_a_manager_named_outside_a_git_repository_says_there_is_none(
    tmp_path: Path, env: dict[str, str]
) -> None:
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()

    result = install(
        nowhere,
        {**env, "GIT_CEILING_DIRECTORIES": str(tmp_path)},
        "--hooks",
        "lefthook",
    )

    assert result.returncode == 1
    assert "no git repository" in result.stderr


def test_a_manager_named_in_a_bare_repository_is_refused(
    tmp_path: Path, git: Git, env: dict[str, str]
) -> None:
    git(tmp_path, "init", "-q", "--bare", str(tmp_path / "bare.git"))

    result = install(tmp_path / "bare.git", env, "--hooks", "husky")

    assert result.returncode == 1
    assert "worktree" in result.stderr


def test_a_second_husky_install_writes_nothing_and_says_so(
    husky_repo: Path, env: dict[str, str]
) -> None:
    first = install(husky_repo, env)
    files = [husky_repo / ".husky" / name for name in ("commit-msg", "pre-push")]
    before = [(f.read_text(), f.stat().st_mtime_ns) for f in files]

    second = install(husky_repo, env)

    assert "installed" in first.stdout and "already installed" not in first.stdout
    assert second.returncode == 0
    assert "already installed" in second.stdout
    assert [(f.read_text(), f.stat().st_mtime_ns) for f in files] == before


def test_a_hand_edited_husky_block_is_restored_and_reported_updated(
    husky_repo: Path, env: dict[str, str]
) -> None:
    path = husky_hook(husky_repo, "pre-push", "npm test\n")
    install(husky_repo, env)
    installed = path.read_text()
    path.write_text(installed.replace("refs=$(cat)", "refs="))

    result = install(husky_repo, env)

    assert "updated" in result.stdout
    assert path.read_text() == installed


def test_a_file_with_a_begin_marker_but_no_end_marker_is_refused_and_unchanged(
    husky_repo: Path, env: dict[str, str]
) -> None:
    path = husky_hook(husky_repo, "pre-push", "# prepush-ci: begin\nnpm test\n")

    result = install(husky_repo, env)

    assert result.returncode == 1
    assert ".husky/pre-push" in result.stderr
    assert path.read_text() == "# prepush-ci: begin\nnpm test\n"
    assert not (husky_repo / ".husky" / "commit-msg").exists()


def test_a_file_named_husky_is_not_a_husky_directory_and_the_hooks_are_native(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / ".husky").write_text("not a directory\n")

    result = install(pushing, env)

    assert result.returncode == 0, result.stderr
    assert hooks_path(pushing, git) != ""
    assert (pushing / ".husky").read_text() == "not a directory\n"


def test_husky_named_where_a_file_is_called_husky_is_refused_naming_it(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / ".husky").write_text("not a directory\n")

    result = install(pushing, env, "--hooks", "husky")

    assert result.returncode == 1
    assert ".husky" in result.stderr
    assert "Traceback" not in result.stderr
    assert (pushing / ".husky").read_text() == "not a directory\n"


# a manager while the native hooks hold core.hooksPath

UNSET = "git config --local --unset core.hooksPath"


def native_hooks_directory(repo: Path) -> Path:
    return (repo / ".git" / "prepush-ci" / "hooks").resolve()


def test_pre_commit_after_a_native_install_is_refused_and_nothing_changes(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    config = "repos:\n  - repo: local\n    hooks: []\n"
    (pushing / PRE_COMMIT_CONFIG).write_text(config)
    install(pushing, env, "--hooks", "native")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "core.hooksPath" in result.stderr and UNSET in result.stderr
    assert (pushing / PRE_COMMIT_CONFIG).read_text() == config
    assert Path(hooks_path(pushing, git)) == native_hooks_directory(pushing)


def test_lefthook_after_a_native_install_is_refused_and_nothing_changes(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / "lefthook.yml").write_text(LEFTHOOK_CONFIG)
    install(pushing, env, "--hooks", "native")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "core.hooksPath" in result.stderr and UNSET in result.stderr
    assert (pushing / "lefthook.yml").read_text() == LEFTHOOK_CONFIG
    assert Path(hooks_path(pushing, git)) == native_hooks_directory(pushing)


def test_a_rerun_after_the_setting_is_removed_installs_the_manager_block(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")
    install(pushing, env, "--hooks", "native")
    assert install(pushing, env).returncode == 1
    git(pushing, "config", "--local", "--unset", "core.hooksPath")

    result = install(pushing, env)

    assert result.returncode == 0, result.stderr
    assert "installed" in result.stdout
    assert "prepush-ci hook" in (pushing / PRE_COMMIT_CONFIG).read_text()
    assert hooks_path(pushing, git) == ""


def test_husky_is_not_refused_after_a_native_install(
    husky_repo: Path, env: dict[str, str]
) -> None:
    install(husky_repo, env, "--hooks", "native")

    result = install(husky_repo, env, "--hooks", "husky")

    assert result.returncode == 0, result.stderr
    for name in ("commit-msg", "pre-push"):
        assert "prepush-ci hook" in (husky_repo / ".husky" / name).read_text()


def test_a_core_hooks_path_that_is_not_ours_does_not_refuse_a_manager(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    git(pushing, "config", "--local", "core.hooksPath", "custom-hooks")
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    result = install(pushing, env)

    assert result.returncode == 0, result.stderr
    assert "prepush-ci hook" in (pushing / PRE_COMMIT_CONFIG).read_text()
    assert hooks_path(pushing, git) == "custom-hooks"


def test_the_refusal_names_a_previous_directory_that_stops_being_used(
    pushing: Path, git: Git, env: dict[str, str]
) -> None:
    custom = pushing / "custom-hooks"
    custom.mkdir()
    (custom / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    git(pushing, "config", "--local", "core.hooksPath", "custom-hooks")
    install(pushing, env, "--hooks", "native")
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "custom-hooks" in result.stderr and "no longer run" in result.stderr


def test_the_refusal_stays_quiet_about_a_previous_directory_that_stays_in_use(
    pushing: Path, env: dict[str, str]
) -> None:
    (pushing / ".git" / "hooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    install(pushing, env, "--hooks", "native")
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "no longer run" not in result.stderr


def test_the_refusal_stays_quiet_when_the_previous_directory_is_the_global_one(
    pushing: Path, tmp_path: Path, env: dict[str, str]
) -> None:
    shared = tmp_path / "shared-hooks"
    shared.mkdir()
    (shared / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text(f"[core]\n\thooksPath = {shared.as_posix()}\n")
    env = {**env, "GIT_CONFIG_GLOBAL": str(global_config)}
    install(pushing, env, "--hooks", "native")
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    result = install(pushing, env)

    assert result.returncode == 1
    assert "no longer run" not in result.stderr


def test_the_refusal_still_comes_when_the_record_of_the_previous_directory_is_gone(
    pushing: Path, env: dict[str, str]
) -> None:
    install(pushing, env, "--hooks", "native")
    (pushing / ".git" / "prepush-ci" / "hooks" / "previous").unlink()
    (pushing / PRE_COMMIT_CONFIG).write_text("repos:\n  - repo: local\n    hooks: []\n")

    result = install(pushing, env)

    assert result.returncode == 1
    assert UNSET in result.stderr and "no longer run" not in result.stderr
