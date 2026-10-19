"""One text-encoding policy for every command: the reproductions of the bugs of this class.

Each spec runs in both variants (`conftest.py`): under `ascii` the repository lives below a directory
with a non-ASCII name and every process has an ASCII locale, which is where these bugs live.
"""

import locale
import os
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]

# What the tool prints is encoded for the terminal: UTF-8 on POSIX, the code page on Windows.
OUTPUT_ENCODING = (
    locale.getpreferredencoding(False) if sys.platform == "win32" else "utf-8"
)
TRAILER = "Prepush-CI: full"
NOT_UTF8 = b'check = "caf\xe9"\n'


def cli_bytes(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    stdin: str | bytes | None = None,
) -> "subprocess.CompletedProcess[bytes]":
    inherited = {
        k: v
        for k, v in os.environ.items()
        if k != "PREPUSH_CI" and not k.startswith("PRE_COMMIT_")
    }
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", *args],
        cwd=repo,
        env={**inherited, **(env or {})},
        input=stdin.encode() if isinstance(stdin, str) else stdin,
        capture_output=True,
        check=False,
    )


def cli(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    stdin: str | bytes | None = None,
) -> "subprocess.CompletedProcess[str]":
    done = cli_bytes(repo, *args, env=env, stdin=stdin)
    return subprocess.CompletedProcess(
        done.args,
        done.returncode,
        done.stdout.decode(OUTPUT_ENCODING, "replace"),
        done.stderr.decode(OUTPUT_ENCODING, "replace"),
    )


def line(result: "subprocess.CompletedProcess[str]", name: str) -> str:
    return next(
        row for row in result.stdout.splitlines() if row.split(" ")[1:2] == [f"{name}:"]
    )


def committed(repo: Path, git: Git, *names: str) -> None:
    git(repo, "add", *names)
    git(repo, "commit", "-q", "-m", "add " + " ".join(names))


def remote_named(repo: Path, tmp_path: Path, git: Git, name: str) -> Path:
    """A bare remote called `name` that has `main` at the tip of `repo`."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", name, str(remote))
    git(repo, "push", "-q", name, "HEAD:refs/heads/main")
    return remote


def config(repo: Path, git: Git, *lines: str) -> None:
    (repo / ".prepush-ci.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    committed(repo, git, ".prepush-ci.toml")


# --- Every command handles non-ASCII names the same way -------------------------------------


def test_a_remote_with_a_non_ascii_name_matches_the_config(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    config(repo, git, 'check = "true"', 'require_up_to_date = "oré/main"')
    remote_named(repo, tmp_path, git, "oré")

    result = cli(repo, "doctor", "--hooks", "none")

    assert line(result, "up-to-date").startswith("ok up-to-date"), result.stdout


def test_run_with_a_remote_that_has_a_non_ascii_name_is_not_refused(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    config(repo, git, 'check = "true"', 'require_up_to_date = "oré/main"')
    remote_named(repo, tmp_path, git, "oré")

    result = cli(repo, "run")

    assert result.returncode == 0, result.stderr
    assert "remote" not in result.stderr


def test_doctor_and_init_work_in_a_repository_whose_path_is_non_ascii(
    repo: Path, tmp_path: Path, git: Git
) -> None:
    where = tmp_path / "dé"
    where.mkdir()
    git(where, "init", "-q")

    doctor = cli(where, "doctor", "--hooks", "none")
    init = cli(
        where,
        "init",
        "--non-interactive",
        "--check",
        "true",
        "--hooks",
        "none",
        "--ci",
        "none",
        "--no-session-hook",
        "--default-branch",
        "main",
        "--require-up-to-date",
        "false",
    )

    assert "Traceback" not in doctor.stderr and "Traceback" not in init.stderr
    assert init.returncode == 0, init.stderr
    assert (where / ".prepush-ci.toml").is_file()


def test_install_writes_the_hooks_in_a_non_ascii_path_and_says_so_once(
    tmp_path: Path, git: Git
) -> None:
    where = tmp_path / "dé"
    where.mkdir()
    git(where, "init", "-q")

    first = cli(where, "install", "--hooks", "native")
    written = {
        path: path.read_bytes()
        for path in (where / ".git").rglob("*")
        if path.is_file()
    }
    second = cli(where, "install", "--hooks", "native")

    assert first.returncode == 0, first.stderr
    assert (where / ".git" / "prepush-ci" / "hooks" / "pre-push").is_file()
    assert second.stdout.startswith("already installed"), second.stdout
    assert written == {
        path: path.read_bytes()
        for path in (where / ".git").rglob("*")
        if path.is_file()
    }


def test_init_sees_the_previous_hook_in_a_non_ascii_hooks_directory(
    repo: Path, git: Git, printed: Callable[[str], str]
) -> None:
    hooks = repo / "pré"
    hooks.mkdir()
    (hooks / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    (hooks / "pre-push").chmod(0o755)
    git(repo, "config", "--local", "core.hooksPath", "pré")

    result = cli(
        repo,
        "init",
        "--check",
        "true",
        "--default-branch",
        "main",
        "--require-up-to-date",
        "false",
        "--preflight",
        "true",
        "--ci",
        "none",
        "--no-session-hook",
        stdin="\n\n",
    )

    assert "Traceback" not in result.stderr, result.stderr
    shown = printed("pré/pre-push")
    assert (
        f"the pre-push hook {shown} (an existing pre-push hook is kept and runs first)"
        in result.stdout
    ), result.stdout


def test_a_non_ascii_argument_reaches_the_config(repo: Path) -> None:
    result = cli(
        repo,
        "init",
        "--non-interactive",
        "--check",
        "echo é",
        "--hooks",
        "none",
        "--ci",
        "none",
        "--no-session-hook",
        "--default-branch",
        "main",
        "--require-up-to-date",
        "false",
    )

    assert result.returncode == 0, result.stderr
    assert 'check = "echo é"'.encode() in (repo / ".prepush-ci.toml").read_bytes()


def test_a_non_ascii_answer_reaches_the_config(repo: Path) -> None:
    result = cli(
        repo,
        "init",
        "--hooks",
        "none",
        "--ci",
        "none",
        "--no-session-hook",
        "--default-branch",
        "main",
        "--require-up-to-date",
        "false",
        stdin="echo é\n\n\n",
    )

    assert result.returncode == 0, result.stderr
    assert 'check = "echo é"'.encode() in (repo / ".prepush-ci.toml").read_bytes()


def test_a_check_with_a_non_ascii_character_runs(repo: Path, git: Git) -> None:
    config(repo, git, 'check = "echo é"', "require_up_to_date = false")

    result = cli_bytes(repo, "run")

    assert result.returncode == 0, result.stderr
    assert b"Traceback" not in result.stderr
    # passed through untouched: the bytes the same command writes when nothing stands between
    direct = subprocess.run("echo é", shell=True, capture_output=True, check=True)
    assert direct.stdout.strip() in result.stdout


def test_a_preflight_with_a_non_ascii_character_runs(repo: Path, git: Git) -> None:
    config(
        repo,
        git,
        'check = "true"',
        'preflight = "echo é"',
        "require_up_to_date = false",
    )

    run = cli(repo, "run")
    doctor = cli(repo, "doctor", "--hooks", "none")

    assert "Traceback" not in run.stderr and "Traceback" not in doctor.stderr
    assert run.returncode == 0, run.stderr
    assert line(doctor, "preflight").startswith("ok preflight"), doctor.stdout


def test_an_environment_value_with_a_non_ascii_character_reaches_the_preflight(
    repo: Path, git: Git
) -> None:
    script = repo.parent / "greeting.py"
    script.write_text(
        "import os, sys\nsys.exit(0 if os.fsencode(os.environ['GREETING']) == '\u00e9'.encode() else 1)\n"
    )
    config(
        repo,
        git,
        'check = "true"',
        f'preflight = \'"{Path(sys.executable).as_posix()}" "{script.as_posix()}"\'',
        "require_up_to_date = false",
    )

    doctor = cli(repo, "doctor", "--hooks", "none", env={"GREETING": "é"})

    assert "Traceback" not in doctor.stderr, doctor.stderr
    assert line(doctor, "preflight").startswith("ok preflight"), doctor.stdout


def test_a_branch_with_a_non_ascii_name_is_pushed(pushing_repo: Path, git: Git) -> None:
    git(pushing_repo, "add", ".prepush-ci.toml")
    git(pushing_repo, "commit", "-q", "--allow-empty", "-m", "init")
    git(pushing_repo, "switch", "-q", "-c", "fé")
    git(
        pushing_repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        f"work\n\n{TRAILER}",
    )

    pushed = git(pushing_repo, "push", "origin", "fé", check=False)

    assert pushed.returncode == 0, pushed.stderr
    assert (pushing_repo.parent / "ran.log").read_text().split() == ["ran"]


def test_a_commit_template_in_a_non_ascii_path_is_read(
    hooked_repo: Path, tmp_path: Path, git: Git
) -> None:
    directory = tmp_path / "dé"
    directory.mkdir(exist_ok=True)
    template = directory / "template.txt"
    template.write_text("Subject here\n\n# describe why\n", encoding="utf-8")
    git(hooked_repo, "config", "--local", "commit.template", template.as_posix())
    (hooked_repo / "x.txt").write_text("x")
    git(hooked_repo, "add", "x.txt")

    result = git(
        hooked_repo,
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert result.returncode != 0
    assert "did not edit the message" in result.stderr
    assert TRAILER not in result.stdout + result.stderr


# --- A file the tool parses must be UTF-8, and says so --------------------------------------


def test_the_commit_msg_hook_refuses_a_config_that_is_not_utf8(
    hooked_repo: Path, git: Git
) -> None:
    (hooked_repo / ".prepush-ci.toml").write_bytes(NOT_UTF8)
    (hooked_repo / "x.txt").write_text("x")
    git(hooked_repo, "add", "x.txt")

    result = git(
        hooked_repo,
        "commit",
        "-q",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
        check=False,
    )

    assert result.returncode != 0
    lines = [row for row in result.stderr.splitlines() if "UTF-8" in row]
    assert len(lines) == 1 and ".prepush-ci.toml" in lines[0]
    assert "not valid UTF-8" in lines[0]
    assert "Traceback" not in result.stderr


def test_doctor_reports_a_config_that_is_not_utf8(repo: Path) -> None:
    (repo / ".prepush-ci.toml").write_bytes(NOT_UTF8)

    result = cli(repo, "doctor", "--hooks", "none")

    config_line = line(result, "config")
    assert config_line.startswith("fail config")
    assert ".prepush-ci.toml" in config_line and "not valid UTF-8" in config_line
    assert {row.split(" ")[1] for row in result.stdout.splitlines() if " " in row} >= {
        "config:",
        "commit-msg:",
        "pre-push:",
        "preflight:",
        "PREPUSH_CI:",
        "up-to-date:",
    }


def test_verify_reports_a_committed_config_that_is_not_utf8(
    repo: Path, git: Git
) -> None:
    (repo / ".prepush-ci.toml").write_bytes(NOT_UTF8)
    git(repo, "add", ".prepush-ci.toml")
    git(repo, "commit", "-q", "-m", f"work\n\n{TRAILER}")

    result = cli(repo, "verify", "HEAD")

    assert result.returncode == 1
    assert ".prepush-ci.toml" in result.stdout and "not valid UTF-8" in result.stdout
    assert "Traceback" not in result.stderr


def test_init_refuses_settings_that_are_not_utf8(repo: Path) -> None:
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_bytes(b'{"x": "caf\xe9"}\n')
    before = sorted(
        path.relative_to(repo) for path in repo.rglob("*") if ".git" not in path.parts
    )

    result = cli(
        repo,
        "init",
        "--non-interactive",
        "--check",
        "true",
        "--hooks",
        "none",
        "--ci",
        "none",
        "--default-branch",
        "main",
        "--require-up-to-date",
        "false",
    )

    assert result.returncode == 1
    assert (
        ".claude/settings.json" in result.stderr and "not valid UTF-8" in result.stderr
    )
    assert (
        sorted(
            path.relative_to(repo)
            for path in repo.rglob("*")
            if ".git" not in path.parts
        )
        == before
    )


# --- A file the tool edits keeps its bytes -------------------------------------------------


def test_a_message_that_is_not_utf8_gets_the_trailer_with_its_bytes_kept(
    hooked_repo: Path,
) -> None:
    message = hooked_repo.parent / "MSG"
    message.write_bytes(b"caf\xe9\n")
    env = {k: v for k, v in os.environ.items() if k != "PREPUSH_CI"}

    done = subprocess.run(
        [sys.executable, "-m", "prepush_ci", "hook", "commit-msg", str(message)],
        cwd=hooked_repo,
        env={**env, "PREPUSH_CI": "full"},
        capture_output=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert message.read_bytes() == b"caf\xe9\n\n" + TRAILER.encode() + b"\n"


def test_a_managers_file_keeps_a_byte_that_is_not_utf8(repo: Path) -> None:
    config_file = repo / ".pre-commit-config.yaml"
    config_file.write_bytes(b"repos:\n  - repo: local\n    hooks: []\n# caf\xe9\n")

    result = cli(repo, "install", "--hooks", "pre-commit")

    assert result.returncode == 0, result.stderr
    kept = config_file.read_bytes()
    assert b"# caf\xe9\n" in kept
    assert b"prepush-ci" in kept


# --- A file the tool writes reads back equal ------------------------------------------------


def test_a_hook_script_that_embeds_a_non_ascii_path_reads_back_equal(
    repo: Path,
) -> None:
    first = cli(repo, "install", "--hooks", "native")
    second = cli(repo, "install", "--hooks", "native")

    assert first.returncode == 0, first.stderr
    assert second.stdout.startswith("already installed"), second.stdout


def test_a_result_in_a_non_ascii_repository_is_found_again(
    pushing_repo: Path, tmp_path: Path, git: Git
) -> None:
    git(pushing_repo, "commit", "-q", "--allow-empty", "-m", f"work\n\n{TRAILER}")
    pre_receive = tmp_path / "remote.git" / "hooks" / "pre-receive"
    pre_receive.write_text("#!/bin/sh\nexit 1\n")
    pre_receive.chmod(pre_receive.stat().st_mode | stat.S_IXUSR)

    refused = git(pushing_repo, "push", "origin", "main", check=False)
    pre_receive.unlink()
    again = git(pushing_repo, "push", "origin", "main", check=False)

    assert refused.returncode != 0
    assert again.returncode == 0, again.stderr
    assert (tmp_path / "ran.log").read_text().split() == ["ran"]
    assert "passed earlier" in again.stderr


# --- The terminal never makes a command fail ------------------------------------------------


def test_a_report_that_quotes_a_non_ascii_key_prints(
    repo: Path, printed: Callable[[str], str]
) -> None:
    (repo / ".prepush-ci.toml").write_text(
        'check = "true"\n"unknownÉ" = 1\n', encoding="utf-8"
    )

    result = cli(repo, "doctor", "--hooks", "none")

    assert "Traceback" not in result.stderr, result.stderr
    assert line(result, "config").startswith("fail config")
    assert f"`{printed('unknownÉ')}`" in line(result, "config")


def test_a_refusal_that_quotes_a_non_ascii_key_prints(
    hooked_repo: Path, git: Git
) -> None:
    (hooked_repo / ".prepush-ci.toml").write_text(
        'check = "true"\n"unknownÉ" = 1\n', encoding="utf-8"
    )
    (hooked_repo / "x.txt").write_text("x")
    git(hooked_repo, "add", "x.txt")

    result = git(
        hooked_repo,
        "commit",
        "-q",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
        check=False,
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stderr, result.stderr
    assert ".prepush-ci.toml" in result.stderr and "unknown" in result.stderr


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_a_character_the_terminal_cannot_encode_is_replaced_not_raised(
    stream: str,
) -> None:
    code = (
        "import sys\nfrom prepush_ci import text_io\ntext_io.configure_streams()\n"
        f"print('caf\\u00e9', file=sys.{stream})\n"
    )
    env = {
        **os.environ,
        "LC_ALL": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONIOENCODING": "ascii",
    }

    done = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, check=False
    )

    assert done.returncode == 0, done.stderr
    assert (done.stdout if stream == "stdout" else done.stderr).strip() == b"caf?"
