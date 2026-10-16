"""The devman command line. Stage 0 has only --version."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from devman import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devman",
        description="Compile, route and show Dagu workflows across repositories.",
    )
    parser.add_argument("--version", action="version", version=f"devman {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
