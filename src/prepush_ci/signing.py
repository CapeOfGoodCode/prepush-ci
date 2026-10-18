"""Sign with the app's private key through the `openssl` program: the standard library cannot do
RS256, and a runtime dependency needs a change of its own."""

import tempfile
from pathlib import Path

from prepush_ci import text_io
from prepush_ci.core.report import ReportError


def sign(message: bytes, key: str) -> bytes:
    """The RSA-SHA256 signature of `message` under the PEM text `key`.

    The key reaches `openssl` as a file in a directory only this process can read, which is gone
    when the function returns; `openssl` starts in that directory, so nothing of the repository
    (nor the working directory a Windows search of the `PATH` would try first) decides what runs.
    """
    with tempfile.TemporaryDirectory() as directory:
        key_file = Path(directory) / "app-key.pem"
        text_io.write_text(key_file, key)
        try:
            done = text_io.run_bytes(
                ["openssl", "dgst", "-sha256", "-sign", text_io.text_of(key_file)],
                cwd=Path(directory),
                stdin=message,
            )
        except OSError as error:
            raise ReportError(
                f"cannot run the program `openssl` to sign the token: {error}"
            ) from error
    if done.returncode != 0:
        detail = " ".join(text_io.decode(done.stderr).split())[:200] or "no message"
        raise ReportError(
            f"the key in PREPUSH_CI_APP_KEY cannot be used (`openssl` says: {detail})"
        )
    return done.stdout
