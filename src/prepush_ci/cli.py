"""Command-line entry point."""

import argparse
from importlib.metadata import version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prepush-ci")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('prepush-ci')}"
    )
    parser.parse_args(argv)
    parser.print_help()
    return 0
