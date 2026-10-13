import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

Git = Callable[..., "subprocess.CompletedProcess[str]"]


def last_message(repo: Path, git: Git) -> str:
    """The raw message of HEAD, exactly as stored (everything after the commit headers)."""
    return git(repo, "cat-file", "commit", "HEAD").stdout.split("\n\n", 1)[1]


def editor_command(editor: Path) -> str:
    """`GIT_EDITOR` for a script: git runs it through `sh -c`, which eats the backslashes of a
    Windows path, so use forward slashes and quote it against spaces."""
    return shlex.quote(editor.as_posix())


def run_hook(
    message_file: Path,
    *,
    mode: str | None,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> "subprocess.CompletedProcess[str]":
    env = {k: v for k, v in os.environ.items() if k != "PREPUSH_CI"}
    env.update(extra_env or {})
    if mode is not None:
        env["PREPUSH_CI"] = mode
    return subprocess.run(
        [sys.executable, "-m", "prepush_ci", "hook", "commit-msg", str(message_file)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_commit_in_full_mode_ends_with_the_trailer(hooked_repo: Path, git: Git) -> None:
    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
    )

    assert last_message(hooked_repo, git) == "add x\n\nPrepush-CI: full\n"


def test_configured_trailer_is_written_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    (hooked_repo / ".prepush-ci.toml").write_text(
        'check = "true"\ntrailer = { key = "Full-Check", value = "yes" }\n'
    )

    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
    )

    assert last_message(hooked_repo, git).endswith("\nFull-Check: yes\n")


def test_existing_trailers_are_kept_when_the_trailer_is_added(
    hooked_repo: Path, git: Git
) -> None:
    message = "add x\n\nCo-Authored-By: A <a@example.com>"

    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        message,
        env={"PREPUSH_CI": "full"},
    )

    trailers = git(hooked_repo, "log", "-1", "--format=%(trailers:only,unfold)").stdout
    assert "Prepush-CI: full" in trailers.splitlines()
    assert "Co-Authored-By: A <a@example.com>" in trailers.splitlines()


def test_a_divider_line_in_the_body_stays_in_the_body_and_the_trailer_comes_last(
    hooked_repo: Path, git: Git
) -> None:
    message = "subject\n\nbody\n---\nmore"

    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        message,
        env={"PREPUSH_CI": "full"},
    )

    assert (
        last_message(hooked_repo, git)
        == "subject\n\nbody\n---\nmore\n\nPrepush-CI: full\n"
    )


def test_amending_a_full_mode_commit_keeps_the_trailer_exactly_once(
    hooked_repo: Path, git: Git
) -> None:
    env = {"PREPUSH_CI": "full"}
    git(hooked_repo, "commit", "--allow-empty", "-m", "add x", env=env)

    git(hooked_repo, "commit", "--amend", "--allow-empty", "--no-edit", env=env)

    assert last_message(hooked_repo, git).count("Prepush-CI: full") == 1


def test_running_the_hook_twice_leaves_the_file_as_the_first_run_did(
    hooked_repo: Path,
) -> None:
    message_file = hooked_repo / "MSG"
    message_file.write_text("add x\n")

    run_hook(message_file, mode="full", cwd=hooked_repo)
    after_first = message_file.read_text()
    run_hook(message_file, mode="full", cwd=hooked_repo)

    assert message_file.read_text() == after_first
    assert after_first.count("Prepush-CI: full") == 1


def test_an_empty_message_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    empty = hooked_repo / "EMPTY"
    empty.write_text("")

    result = git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-F",
        str(empty),
        env={"PREPUSH_CI": "full"},
        check=False,
    )

    assert result.returncode != 0
    assert (
        git(hooked_repo, "rev-parse", "--verify", "HEAD", check=False).returncode != 0
    )


def test_a_message_of_only_comment_lines_is_left_unchanged_in_full_mode(
    hooked_repo: Path,
) -> None:
    message_file = hooked_repo / "MSG"
    message_file.write_text("# Please enter the commit message\n\n")

    result = run_hook(message_file, mode="full", cwd=hooked_repo)

    assert result.returncode == 0
    assert message_file.read_text() == "# Please enter the commit message\n\n"


def test_commit_without_the_variable_keeps_the_message_exactly(
    hooked_repo: Path, git: Git
) -> None:
    git(hooked_repo, "commit", "--allow-empty", "-m", "add x")

    assert last_message(hooked_repo, git) == "add x\n"


def test_commit_with_the_variable_off_keeps_the_message_exactly(
    hooked_repo: Path, git: Git
) -> None:
    git(
        hooked_repo, "commit", "--allow-empty", "-m", "add x", env={"PREPUSH_CI": "off"}
    )

    assert last_message(hooked_repo, git) == "add x\n"


def test_commit_with_the_variable_empty_keeps_the_message_exactly(
    hooked_repo: Path, git: Git
) -> None:
    git(hooked_repo, "commit", "--allow-empty", "-m", "add x", env={"PREPUSH_CI": ""})

    assert last_message(hooked_repo, git) == "add x\n"


def test_commit_succeeds_without_a_config_when_not_opted_in(
    hooked_repo: Path, git: Git
) -> None:
    (hooked_repo / ".prepush-ci.toml").unlink()

    git(hooked_repo, "commit", "--allow-empty", "-m", "add x")

    assert last_message(hooked_repo, git) == "add x\n"


def test_misspelled_variable_aborts_the_commit_and_the_error_names_full_and_off(
    hooked_repo: Path, git: Git
) -> None:
    result = git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "ful"},
        check=False,
    )

    assert result.returncode != 0
    assert "`full`" in result.stderr
    assert "`off`" in result.stderr


def test_upper_case_variable_aborts_the_commit_and_the_error_names_full_and_off(
    hooked_repo: Path, git: Git
) -> None:
    result = git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "FULL"},
        check=False,
    )

    assert result.returncode != 0
    assert "`full`" in result.stderr
    assert "`off`" in result.stderr


def test_full_mode_without_a_config_aborts_the_commit_and_names_the_config_file(
    hooked_repo: Path, git: Git
) -> None:
    (hooked_repo / ".prepush-ci.toml").unlink()

    result = git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
        check=False,
    )

    assert result.returncode != 0
    assert ".prepush-ci.toml" in result.stderr


def test_full_mode_with_an_unknown_config_key_aborts_the_commit_and_names_the_key(
    hooked_repo: Path, git: Git
) -> None:
    (hooked_repo / ".prepush-ci.toml").write_text('check = "true"\nchekc = "x"\n')

    result = git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
        check=False,
    )

    assert result.returncode != 0
    assert "chekc" in result.stderr


def test_hook_reads_the_config_at_the_root_when_run_in_a_subdirectory(
    hooked_repo: Path,
) -> None:
    (hooked_repo / ".prepush-ci.toml").write_text(
        'check = "true"\ntrailer = { key = "Full-Check" }\n'
    )
    subdirectory = hooked_repo / "src"
    subdirectory.mkdir()
    message_file = hooked_repo / "MSG"
    message_file.write_text("add x\n")

    result = run_hook(message_file, mode="full", cwd=subdirectory)

    assert result.returncode == 0
    assert message_file.read_text().endswith("Full-Check: full\n")


def stage_a_file(repo: Path, git: Git) -> None:
    (repo / "b").write_text("b\n")
    git(repo, "add", "b")


def test_an_empty_message_with_the_verbose_diff_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)

    result = git(
        hooked_repo,
        "commit",
        "-v",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert result.returncode != 0
    assert (
        git(hooked_repo, "rev-parse", "--verify", "HEAD", check=False).returncode != 0
    )


def test_an_empty_message_with_a_custom_comment_char_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)

    result = git(
        hooked_repo,
        "-c",
        "core.commentChar=;",
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert result.returncode != 0
    assert (
        git(hooked_repo, "rev-parse", "--verify", "HEAD", check=False).returncode != 0
    )


def test_a_message_with_a_custom_comment_char_and_the_verbose_diff_gets_the_trailer(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    editor = hooked_repo / "editor.sh"
    editor.write_text(
        '#!/bin/sh\nprintf "add b\\n\\n" | cat - "$1" > "$1.new" && mv "$1.new" "$1"\n'
    )
    editor.chmod(0o755)

    git(
        hooked_repo,
        "-c",
        "core.commentChar=;",
        "commit",
        "-v",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": editor_command(editor)},
    )

    assert last_message(hooked_repo, git) == "add b\n\nPrepush-CI: full\n"


def test_the_automatic_comment_char_aborts_the_commit_in_full_mode_and_says_why(
    hooked_repo: Path, git: Git
) -> None:
    result = git(
        hooked_repo,
        "-c",
        "core.commentChar=auto",
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
        check=False,
    )

    assert result.returncode != 0
    assert "auto" in result.stderr


def test_the_automatic_comment_char_does_not_matter_when_not_opted_in(
    hooked_repo: Path, git: Git
) -> None:
    git(
        hooked_repo,
        "-c",
        "core.commentChar=auto",
        "commit",
        "--allow-empty",
        "-m",
        "add x",
    )

    assert last_message(hooked_repo, git) == "add x\n"


def write_editor(repo: Path, message: str) -> Path:
    """An editor script that puts `message` in front of what git prepared."""
    editor = repo / "editor.sh"
    editor.write_text(
        f'#!/bin/sh\nprintf "{message}\\n" | cat - "$1" > "$1.new" && mv "$1.new" "$1"\n'
    )
    editor.chmod(0o755)
    return editor


def assert_commit_aborted(
    repo: Path, git: Git, result: "subprocess.CompletedProcess[str]"
) -> None:
    assert result.returncode != 0
    assert git(repo, "rev-parse", "--verify", "HEAD", check=False).returncode != 0


def test_a_message_given_with_m_that_starts_with_a_hash_gets_the_trailer(
    hooked_repo: Path, git: Git
) -> None:
    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "#123 fix the bug",
        env={"PREPUSH_CI": "full"},
    )

    assert last_message(hooked_repo, git) == "#123 fix the bug\n\nPrepush-CI: full\n"


def test_a_message_from_a_file_that_starts_with_a_hash_gets_the_trailer(
    hooked_repo: Path, git: Git
) -> None:
    message = hooked_repo / "MSG"
    message.write_text("#123 fix the bug\n")

    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-F",
        str(message),
        env={"PREPUSH_CI": "full"},
    )

    assert last_message(hooked_repo, git) == "#123 fix the bug\n\nPrepush-CI: full\n"


def test_an_unchanged_editor_template_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)

    result = git(
        hooked_repo,
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)


def test_an_editor_that_strips_a_hash_message_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    result = git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "#123 fix the bug",
        "--edit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)


def test_the_no_op_editor_chosen_by_the_user_aborts_an_empty_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)

    result = git(
        hooked_repo,
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": ":"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)


def test_an_unchanged_template_with_a_comment_string_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)

    result = git(
        hooked_repo,
        "-c",
        "core.commentString=//",
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)


def test_a_hash_message_written_in_the_editor_gets_the_trailer_when_cleanup_is_whitespace(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)

    git(
        hooked_repo,
        "-c",
        "commit.cleanup=whitespace",
        "commit",
        env={
            "PREPUSH_CI": "full",
            "GIT_EDITOR": editor_command(write_editor(hooked_repo, "#123 fix the bug")),
        },
    )

    message = last_message(hooked_repo, git)
    assert message.startswith(
        "#123 fix the bug\n\nPrepush-CI: full\n\n# Please enter the commit message"
    )


def write_template(repo: Path, text: str) -> None:
    (repo / "template.txt").write_text(text)


def test_an_unchanged_commit_template_with_text_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    write_template(hooked_repo, "Subject here\n\n# describe why\n")

    result = git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)
    assert "did not edit the message" in result.stderr


def test_an_edited_commit_template_gets_the_trailer_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    write_template(hooked_repo, "Subject here\n\n# describe why\n")

    git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        env={
            "PREPUSH_CI": "full",
            "GIT_EDITOR": editor_command(write_editor(hooked_repo, "Real subject")),
        },
    )

    message = last_message(hooked_repo, git)
    assert message.startswith("Real subject\nSubject here\n")
    assert "Prepush-CI: full" in message.splitlines()


def test_a_message_given_with_m_gets_the_trailer_when_a_commit_template_is_set(
    hooked_repo: Path, git: Git
) -> None:
    write_template(hooked_repo, "Subject here\n")

    git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
    )

    assert last_message(hooked_repo, git) == "add x\n\nPrepush-CI: full\n"


def test_a_missing_commit_template_file_does_not_stop_the_trailer(
    hooked_repo: Path, git: Git, tmp_path: Path
) -> None:
    # Git itself refuses to commit with a missing template, so run the hook on a file.
    git(hooked_repo, "config", "commit.template", "missing.txt")
    message_file = tmp_path / "MSG"
    message_file.write_text("add x\n")

    result = run_hook(message_file, mode="full", cwd=hooked_repo)

    assert result.returncode == 0
    assert message_file.read_text() == "add x\n\nPrepush-CI: full\n"


def test_known_limit_the_no_op_editor_with_a_comment_only_template_makes_a_trailer_only_commit(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    write_template(hooked_repo, "# only comments\n")

    git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": ":"},
    )

    assert last_message(hooked_repo, git) == "Prepush-CI: full\n"


def test_known_limit_the_no_op_editor_on_an_m_message_made_of_comments_makes_a_trailer_only_commit(
    hooked_repo: Path, git: Git
) -> None:
    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "-m",
        "#123 x",
        "--edit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": ":"},
    )

    assert last_message(hooked_repo, git) == "Prepush-CI: full\n"


def test_known_limit_cleanup_strip_on_the_command_line_makes_a_trailer_only_commit(
    hooked_repo: Path, git: Git
) -> None:
    git(
        hooked_repo,
        "commit",
        "--allow-empty",
        "--cleanup=strip",
        "-m",
        "#123 x",
        env={"PREPUSH_CI": "full"},
    )

    assert last_message(hooked_repo, git) == "Prepush-CI: full\n"


def test_a_signed_off_empty_message_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)

    result = git(
        hooked_repo,
        "commit",
        "-s",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)
    assert "empty commit message" in result.stderr


def test_a_signed_off_unchanged_template_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    write_template(hooked_repo, "Subject here\n\n# describe why\n")

    result = git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        "-s",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)
    assert "did not edit the message" in result.stderr


def test_a_signed_off_message_gets_the_trailer_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    git(
        hooked_repo,
        "commit",
        "-s",
        "--allow-empty",
        "-m",
        "add x",
        env={"PREPUSH_CI": "full"},
    )

    message = last_message(hooked_repo, git).splitlines()
    assert "Prepush-CI: full" in message
    assert message[-1].startswith("Signed-off-by: ")


def test_an_m_message_equal_to_the_commit_template_gets_the_trailer_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    write_template(hooked_repo, "Subject here\n")

    git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        "--allow-empty",
        "-m",
        "Subject here",
        env={"PREPUSH_CI": "full"},
    )

    assert last_message(hooked_repo, git) == "Subject here\n\nPrepush-CI: full\n"


def test_known_limit_a_template_given_with_t_makes_a_commit_of_the_template_and_the_trailer(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    write_template(hooked_repo, "Subject here\n\n# describe why\n")

    git(
        hooked_repo,
        "commit",
        "-t",
        "template.txt",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
    )

    assert last_message(hooked_repo, git) == "Subject here\n\nPrepush-CI: full\n"


def test_known_limit_the_no_op_editor_with_an_unchanged_template_makes_a_commit_of_the_template_and_the_trailer(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    write_template(hooked_repo, "Subject here\n\n# describe why\n")

    git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": ":"},
    )

    assert last_message(hooked_repo, git) == "Subject here\n\nPrepush-CI: full\n"


def test_a_message_that_is_not_utf8_gets_the_trailer_with_its_bytes_kept(
    hooked_repo: Path, git: Git, tmp_path: Path
) -> None:
    message_file = tmp_path / "MSG"
    message_file.write_bytes(b"vierte Nachricht \xe9\n")

    result = run_hook(message_file, mode="full", cwd=hooked_repo)

    assert result.returncode == 0
    assert message_file.read_bytes() == b"vierte Nachricht \xe9\n\nPrepush-CI: full\n"


def test_a_commit_message_that_is_not_utf8_is_committed_with_the_trailer(
    hooked_repo: Path, git: Git, tmp_path: Path
) -> None:
    stage_a_file(hooked_repo, git)
    message_file = tmp_path / "MSG"
    message_file.write_bytes(b"vierte Nachricht \xe9\n")

    result = git(
        hooked_repo, "commit", "-q", "-F", str(message_file), env={"PREPUSH_CI": "full"}
    )

    assert result.returncode == 0
    stored = subprocess.run(
        ["git", "cat-file", "commit", "HEAD"],
        cwd=hooked_repo,
        capture_output=True,
        check=True,
    ).stdout
    # git stores the message re-encoded to UTF-8
    assert stored.endswith("vierte Nachricht é\n\nPrepush-CI: full\n".encode())


def test_a_commit_template_path_that_is_not_utf8_does_not_stop_the_trailer(
    hooked_repo: Path, tmp_path: Path
) -> None:
    config = hooked_repo / ".git" / "config"
    config.write_bytes(config.read_bytes() + b'[commit]\n\ttemplate = "t\xe9.txt"\n')
    message_file = tmp_path / "MSG"
    message_file.write_text("add x\n")

    result = run_hook(message_file, mode="full", cwd=hooked_repo)

    assert result.returncode == 0
    assert message_file.read_text() == "add x\n\nPrepush-CI: full\n"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Git for Windows does not hand a raw non-UTF-8 comment byte back unchanged",
)
def test_a_message_of_comment_lines_with_a_comment_char_that_is_not_utf8_is_left_unchanged(
    hooked_repo: Path, tmp_path: Path
) -> None:
    config = hooked_repo / ".git" / "config"
    config.write_bytes(config.read_bytes() + b'[core]\n\tcommentChar = "\xe9"\n')
    message_file = tmp_path / "MSG"
    message_file.write_bytes(b"\xe9 only a comment\n")

    result = run_hook(message_file, mode="full", cwd=hooked_repo)

    assert result.returncode == 0
    assert message_file.read_bytes() == b"\xe9 only a comment\n"


def git_is_older_than(major: int, minor: int) -> bool:
    words = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, check=True
    ).stdout.split()
    found = tuple(int(part) for part in words[2].split(".")[:2])
    return found < (major, minor)


@pytest.mark.skipif(
    git_is_older_than(2, 45),
    reason="git before 2.45 refuses a comment string of more than one byte",
)
def test_a_message_of_comment_lines_with_a_comment_string_of_two_bytes_is_left_unchanged_under_an_ascii_locale(
    hooked_repo: Path, tmp_path: Path
) -> None:
    config = hooked_repo / ".git" / "config"
    config.write_bytes(
        config.read_bytes() + '[core]\n\tcommentString = "\u00e9"\n'.encode()
    )
    message_file = tmp_path / "MSG"
    message_file.write_bytes("\u00e9 only a comment\n".encode())

    result = run_hook(
        message_file,
        mode="full",
        cwd=hooked_repo,
        extra_env={
            "LC_ALL": "C",
            "PYTHONCOERCECLOCALE": "0",
            "PYTHONUTF8": "0",
        },
    )

    assert result.returncode == 0
    assert message_file.read_bytes() == "\u00e9 only a comment\n".encode()


NOT_UTF8_ON_DISK = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows file names are Unicode"
)


@NOT_UTF8_ON_DISK
def test_an_unchanged_commit_template_at_a_path_that_is_not_utf8_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    template = Path(os.fsdecode(os.fsencode(hooked_repo) + b"/t\xe9.txt"))
    template.write_bytes(b"Subject here\n\n# describe why\n")
    git(hooked_repo, "config", "--local", "commit.template", os.fspath(template))

    result = git(
        hooked_repo,
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)
    assert "did not edit the message" in result.stderr


def test_an_unchanged_commit_template_that_is_not_utf8_aborts_the_commit_in_full_mode(
    hooked_repo: Path, git: Git
) -> None:
    stage_a_file(hooked_repo, git)
    (hooked_repo / "template.txt").write_bytes(b"Betreff \xe9\n\n# describe why\n")

    result = git(
        hooked_repo,
        "-c",
        "commit.template=template.txt",
        "commit",
        env={"PREPUSH_CI": "full", "GIT_EDITOR": "true"},
        check=False,
    )

    assert_commit_aborted(hooked_repo, git, result)
    assert "did not edit the message" in result.stderr
