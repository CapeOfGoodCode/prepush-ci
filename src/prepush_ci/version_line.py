"""The line `prepush-ci --version` prints."""

import argparse
import sys
from collections.abc import Sequence
from importlib import metadata
from importlib.metadata import Distribution
from typing import Any

from prepush_ci import text_io
from prepush_ci.core.build_origin import origin_suffix

RECORD = "direct_url.json"


def version_line(distribution: Distribution) -> str:
    """`prepush-ci <version>` and, for a build that did not come from a package index, where from."""
    record = text_io.metadata_text(distribution, RECORD)
    return f"prepush-ci {distribution.version}{origin_suffix(record)}"


class PrintVersionLine(argparse.Action):
    """`--version` that prints the line as it is: argparse's own `version` action wraps its text to
    the width of the terminal, and a line the requirement calls one line must stay one."""

    def __init__(self, option_strings: Sequence[str], dest: str, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        print(version_line(metadata.distribution("prepush-ci")))
        sys.exit(0)
