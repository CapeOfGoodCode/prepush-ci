import io
import sys
import time
from pathlib import Path

import pytest

from prepush_ci import text_io


def test_bytes_survive_the_round_trip() -> None:
    for data in (b"or\xc3\xa9", b"x\xff", b"", b"caf\xe9\n"):
        assert text_io.encode(text_io.decode(data)) == data


def test_a_byte_that_is_no_utf8_is_kept_as_an_escape_and_utf8_is_text() -> None:
    assert text_io.decode(b"or\xc3\xa9") == "oré"
    assert text_io.decode(b"x\xff") == "x\udcff"


def test_the_tools_text_survives_the_operating_systems_strings() -> None:
    for text in ("oré", "plain"):
        assert text_io.from_os(text_io.to_os(text)) == text


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows strings are Unicode: a byte that is no UTF-8 cannot be one",
)
def test_a_byte_that_is_no_utf8_survives_the_operating_systems_strings() -> None:
    assert text_io.from_os(text_io.to_os("x\udcff")) == "x\udcff"


def test_a_path_made_of_the_tools_text_names_the_same_bytes() -> None:
    path = text_io.to_path("dé/x")

    assert path.parts == ("dé", "x")
    assert text_io.text_of(path) == "dé/x"


def test_arguments_and_environment_are_the_tools_text() -> None:
    assert text_io.arguments(["a", "oré"]) == ["a", "oré"]
    assert text_io.environment({"NAME": "oré"}) == {"NAME": "oré"}


def test_the_process_environment_is_read_when_none_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREPUSH_CI_TEXT_IO", "yes")

    assert text_io.environment()["PREPUSH_CI_TEXT_IO"] == "yes"


def test_a_file_with_a_byte_that_is_no_utf8_is_read_and_written_back_unchanged(
    tmp_path: Path,
) -> None:
    path = tmp_path / "hook"
    path.write_bytes(b"# caf\xe9\r\nline\r\n")

    text = text_io.read_text(path, keep_line_ends=True)
    text_io.write_text(path, text)

    assert path.read_bytes() == b"# caf\xe9\r\nline\r\n"


def test_line_ends_are_read_as_newlines_unless_kept(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"a\r\nb\rc\n")

    assert text_io.read_text(path) == "a\nb\nc\n"
    assert text_io.read_text(path, keep_line_ends=True) == "a\r\nb\rc\n"


def test_a_file_that_is_parsed_must_be_utf8_and_the_error_names_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config"
    path.write_bytes(b'check = "caf\xe9"\n')

    with pytest.raises(
        text_io.NotUtf8, match=r"^\.prepush-ci\.toml is not valid UTF-8$"
    ):
        text_io.read_utf8(path, ".prepush-ci.toml")


def test_a_file_that_is_parsed_is_read_with_newlines(tmp_path: Path) -> None:
    path = tmp_path / "config"
    path.write_bytes('check = "é"\r\n'.encode())

    assert text_io.read_utf8(path, "config") == 'check = "é"\n'


def test_bytes_that_are_parsed_must_be_utf8_and_the_error_names_the_file() -> None:
    assert text_io.decode_utf8("é".encode(), "x") == "é"
    with pytest.raises(text_io.NotUtf8, match="x is not valid UTF-8"):
        text_io.decode_utf8(b"\xe9", "x")


def test_a_packaged_file_is_read_as_text() -> None:
    assert text_io.packaged_text("prepush_ci", "ci_gates", "gate.sh").startswith(
        "#!/bin/sh"
    )


def test_a_program_gets_arguments_and_environment_in_the_tools_text(
    tmp_path: Path,
) -> None:
    done = text_io.run(
        [
            sys.executable,
            "-c",
            "import os, sys; sys.stdout.buffer.write((sys.argv[1] + ' ' + os.environ['NAME']).encode())",
            "oré",
        ],
        cwd=tmp_path,
        env={"NAME": "café", "SYSTEMROOT": "C:\\Windows"},
    )

    assert done.returncode == 0
    assert done.stdout.strip() == "oré café"
    assert done.stderr == ""


def test_a_program_that_fails_reports_its_status_and_its_error_output(
    tmp_path: Path,
) -> None:
    done = text_io.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('bad'); sys.exit(3)"],
        cwd=tmp_path,
    )

    assert (done.returncode, done.stderr) == (3, "bad")


def test_the_output_of_a_program_keeps_a_byte_that_is_no_utf8(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.buffer.write(b'x\\xff')"

    assert text_io.run([sys.executable, "-c", code], cwd=tmp_path).stdout == "x\udcff"
    assert (
        text_io.run_bytes([sys.executable, "-c", code], cwd=tmp_path).stdout == b"x\xff"
    )


def test_a_program_can_be_given_bytes_on_standard_input(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"

    done = text_io.run_bytes(
        [sys.executable, "-c", code], cwd=tmp_path, stdin=b"a\xffb"
    )

    assert done.stdout == b"a\xffb"


def test_a_shell_command_runs_in_the_directory_and_reports_its_status(
    tmp_path: Path,
) -> None:
    assert text_io.run_shell("exit 0", cwd=tmp_path) == 0
    assert text_io.run_shell("exit 7", cwd=tmp_path) == 7


def test_a_shell_command_gets_no_standard_input(tmp_path: Path) -> None:
    command = f'"{sys.executable}" -c "import sys; sys.exit(len(sys.stdin.read()))"'

    assert text_io.run_shell(command, cwd=tmp_path) == 0


def test_a_captured_shell_command_returns_its_status_and_both_streams(
    tmp_path: Path,
) -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(2)"
    status, output = text_io.run_shell_captured(
        f'"{sys.executable}" -c "{code}"', cwd=tmp_path
    )

    assert status == 2
    assert sorted(output.split()) == ["err", "out"]


def test_standard_input_is_read_as_bytes_and_decoded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def replace_stdin() -> None:
        monkeypatch.setattr(
            sys, "stdin", io.TextIOWrapper(io.BytesIO(b"one \xc3\xa9\ntwo \xff\n"))
        )

    replace_stdin()
    assert text_io.stdin_line() == "one é\n"
    assert text_io.stdin_line() == "two \udcff\n"
    assert text_io.stdin_line() == ""
    replace_stdin()
    assert text_io.stdin_text() == "one é\ntwo \udcff\n"


def test_a_stream_that_cannot_encode_a_character_replaces_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="ascii", errors="strict", newline="\n")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    text_io.configure_streams()
    print("caf\u00e9 x\udcff", file=stream, flush=True)

    assert buffer.getvalue() == b"caf? x?\n"


def test_a_teed_shell_command_returns_its_status_and_its_output_and_shows_it(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(2)"

    status, output = text_io.run_shell_tee(
        f'"{sys.executable}" -c "{code}"', cwd=tmp_path
    )

    shown = capfd.readouterr()
    assert status == 2
    assert output.split() == ["out"]
    assert shown.out.split() == ["out"]
    assert shown.err.split() == ["err"]


def test_a_teed_shell_command_that_runs_for_a_while_is_shown_and_collected_whole(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    code = (
        "import sys, time; print('first', flush=True); time.sleep(0.5); print('second')"
    )

    status, output = text_io.run_shell_tee(
        f'"{sys.executable}" -c "{code}"', cwd=tmp_path
    )

    assert status == 0
    assert output.split() == ["first", "second"]
    assert capfd.readouterr().out.split() == ["first", "second"]


def test_a_teed_shell_command_that_prints_bytes_that_are_no_utf8_keeps_them(
    tmp_path: Path,
) -> None:
    code = "import sys; sys.stdout.buffer.write(b'a\\xffb')"

    _, output = text_io.run_shell_tee(f'"{sys.executable}" -c "{code}"', cwd=tmp_path)

    assert output == "a\udcffb"


def test_a_teed_shell_command_runs_in_the_directory_and_gets_no_standard_input(
    tmp_path: Path,
) -> None:
    code = "import os, sys; print(os.getcwd()); sys.exit(len(sys.stdin.read()))"

    status, output = text_io.run_shell_tee(
        f'"{sys.executable}" -c "{code}"', cwd=tmp_path
    )

    assert status == 0
    assert Path(output.strip()).resolve() == tmp_path.resolve()


def test_a_teed_shell_command_does_not_wait_for_a_process_it_leaves_running(
    tmp_path: Path,
) -> None:
    command = (
        f'"{sys.executable}" -c "import subprocess, sys; '
        f"subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)']); "
        f'print(1)"'
    )
    started = time.monotonic()

    status, output = text_io.run_shell_tee(command, cwd=tmp_path)

    assert (status, output.strip()) == (0, "1")
    assert time.monotonic() - started < 4  # the child sleeps for 5 seconds
