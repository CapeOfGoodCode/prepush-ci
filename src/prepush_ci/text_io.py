"""The one module that decides how bytes become text and text becomes bytes.

The tool's text is UTF-8 with `surrogateescape`, whatever the locale: git, TOML and JSON are
UTF-8, and a byte that is no UTF-8 (a path, a ref, a message) survives as an escape and is written
back unchanged. The locale decides only the operating system's own strings (an argument, an
environment value, a path): `from_os` and `to_os` are the two conversions that depend on it, and
both are exact for every byte sequence. Every other crossing takes bytes.

Nothing else outside `core/` calls `read_text`, `write_text`, `open`, `decode`, `encode`,
`fsdecode`, `fsencode`, `reconfigure` or `input`, passes `encoding`, `errors`, `text` or
`universal_newlines`, or uses `sys.stdin` or `subprocess`; a unit spec scans for it.
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

CODEC = "utf-8"
ERRORS = "surrogateescape"
FOLLOW_SECONDS = 0.1


class NotUtf8(Exception):
    """A file the tool parses holds bytes that are no UTF-8; the message names it."""

    def __init__(self, name: str) -> None:
        super().__init__(f"{name} is not valid UTF-8")
        self.name = name


# --- The domain: bytes and the tool's text -----------------------------------------------------


def decode(data: bytes) -> str:
    """The tool's text of `data`: UTF-8, a byte that is no UTF-8 kept as an escape."""
    return data.decode(CODEC, ERRORS)


def encode(text: str) -> bytes:
    """The bytes of the tool's text; the inverse of `decode`."""
    return text.encode(CODEC, ERRORS)


def decode_utf8(data: bytes, name: str) -> str:
    """The text of a file the tool parses; `NotUtf8` naming `name` when it is not UTF-8."""
    try:
        return _universal(data.decode(CODEC))
    except UnicodeDecodeError as error:
        raise NotUtf8(name) from error


# --- The operating system's strings: the only step the locale decides ----------------------------


def from_os(value: str) -> str:
    """The tool's text of an operating system string (an argument, an environment value, a path)."""
    return decode(os.fsencode(value))


def to_os(text: str) -> str:
    """The operating system string of the tool's text, for an argument, a value or a path.

    Exact for every byte sequence where the system's strings are bytes (POSIX). Windows strings are
    Unicode: a byte that is no UTF-8 cannot be one there, and becomes U+FFFD."""
    data = encode(text)
    if sys.platform == "win32":  # pragma: no cover (the coverage run is on Linux)
        return data.decode(CODEC, "replace")
    return os.fsdecode(data)


def to_path(text: str) -> Path:
    """The path the tool's text names."""
    return Path(to_os(text))


def text_of(path: Path) -> str:
    """The tool's text of a path, with `/` as the separator."""
    return from_os(path.as_posix())


def arguments(argv: Sequence[str]) -> list[str]:
    return [from_os(argument) for argument in argv]


def environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """The tool's text of an environment (the process's own by default)."""
    return {
        from_os(name): from_os(value)
        for name, value in (os.environ if env is None else env).items()
    }


# --- Files ---------------------------------------------------------------------------------------


def _universal(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: Path, *, keep_line_ends: bool = False) -> str:
    """The text of a file the tool edits or only compares: every byte survives. Line ends are
    read as `\\n` unless `keep_line_ends`."""
    text = decode(path.read_bytes())
    return text if keep_line_ends else _universal(text)


def read_utf8(path: Path, name: str) -> str:
    """The text of a file the tool parses; `NotUtf8` naming `name` when it is not UTF-8."""
    return decode_utf8(path.read_bytes(), name)


def write_text(path: Path, text: str) -> None:
    """Write `text` as it is, line ends included."""
    path.write_bytes(encode(text))


def create_private(path: Path, text: str) -> None:
    """Create `path` holding `text`, readable by its owner only from the first byte; a file that
    exists is never touched (`FileExistsError`)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        stream.write(encode(text))


def packaged_text(package: str, *parts: str) -> str:
    """The text of a file shipped inside `package`."""
    return _universal(decode(resources.files(package).joinpath(*parts).read_bytes()))


# --- Subprocesses ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str


def _arguments(args: Sequence[str]) -> list[str]:
    return [to_os(argument) for argument in args]


def _environment(env: Mapping[str, str] | None) -> dict[str, str] | None:
    if env is None:
        return None
    return {to_os(name): to_os(value) for name, value in env.items()}


def run_bytes(
    args: Sequence[str], *, cwd: Path, stdin: bytes | None = None
) -> "subprocess.CompletedProcess[bytes]":
    """Run a program; its output stays bytes."""
    return subprocess.run(
        _arguments(args), cwd=cwd, input=stdin, capture_output=True, check=False
    )


def run(
    args: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None
) -> Completed:
    """Run a program with arguments and environment in the tool's text (`env` replaces the
    environment; None inherits it); its output comes back as the tool's text."""
    done = subprocess.run(
        _arguments(args),
        cwd=cwd,
        env=_environment(env),
        capture_output=True,
        check=False,
    )
    return Completed(
        done.returncode,
        _universal(decode(done.stdout)),
        _universal(decode(done.stderr)),
    )


def run_shell(command: str, *, cwd: Path, env: Mapping[str, str] | None = None) -> int:
    """Run the user's own command through the shell, asking nothing; its output is the child's
    own, passed through untouched. Only the command text crosses the locale."""
    return subprocess.run(
        to_os(command),
        shell=True,
        cwd=cwd,
        env=_environment(env),
        stdin=subprocess.DEVNULL,
        check=False,
    ).returncode


def run_shell_captured(
    command: str, *, cwd: Path, env: Mapping[str, str] | None = None
) -> tuple[int, str]:
    """`run_shell`, with the output (both streams) collected: the exit status and the text.

    The output goes to an unnamed temporary file, not a pipe: a process the command leaves
    running keeps a pipe open and would hold the caller, while a hook returns at once.
    """
    with tempfile.TemporaryFile() as output:
        status = subprocess.run(
            to_os(command),
            shell=True,
            cwd=cwd,
            env=_environment(env),
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            check=False,
        ).returncode
        output.seek(0)
        return status, decode(output.read())


def run_shell_tee(
    command: str, *, cwd: Path, env: Mapping[str, str] | None = None
) -> tuple[int, str]:
    """`run_shell`, with the standard output also collected: it reaches our standard output as the
    command writes it, and comes back as text with the status. The error stream stays the child's.

    The output goes to a temporary file that is followed while the command runs, not to a pipe: a
    process the command leaves running keeps a pipe open and would hold the caller. The file is
    unlinked as soon as both ends are open, so a signal that kills us leaves nothing behind.
    Standard output that cannot be written (a pipe closed early, a full disk) stops the showing;
    the command still runs to its end and its output is still collected.
    """
    descriptor, name = tempfile.mkstemp()
    try:
        with os.fdopen(descriptor, "wb") as writer, open(name, "rb") as reader:
            _unlink(name)
            process = subprocess.Popen(
                to_os(command),
                shell=True,
                cwd=cwd,
                env=_environment(env),
                stdin=subprocess.DEVNULL,
                stdout=writer,
            )
            status: int | None = None
            collected = b""
            showing = True
            while status is None:
                with contextlib.suppress(
                    subprocess.TimeoutExpired
                ):  # still running: show so far
                    status = process.wait(timeout=FOLLOW_SECONDS)
                chunk = reader.read()
                collected += chunk
                showing = showing and _show(chunk)
    finally:
        _unlink(name)
    return status, decode(collected)


def _unlink(name: str) -> None:
    """Remove the file; where the system refuses while a process holds it open (Windows), the
    caller's last call removes it once they have closed."""
    with contextlib.suppress(FileNotFoundError, PermissionError):
        os.unlink(name)


def _show(chunk: bytes) -> bool:
    """Write `chunk` to our standard output; False when it cannot be written."""
    try:
        sys.stdout.flush()
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
    except OSError:
        _discard_standard_output()
        return False
    return True


def _discard_standard_output() -> None:
    """Point our standard output at the null device: the bytes it could not take stay in its
    buffers, and the flush at exit would fail again and turn the exit status into 120."""
    with contextlib.suppress(OSError, ValueError):
        descriptor = sys.stdout.fileno()
        null = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null, descriptor)
        finally:
            os.close(null)


# --- The terminal --------------------------------------------------------------------------------


def stdin_text() -> str:
    """All of standard input, read as bytes and decoded in the domain."""
    return decode(sys.stdin.buffer.read())


def stdin_line() -> str:
    """One line of standard input (empty at the end of it), read as bytes."""
    return decode(sys.stdin.buffer.readline())


def configure_streams() -> None:
    """Make a character the terminal cannot encode come out as `?`, never as a traceback."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
