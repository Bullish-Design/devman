"""The `devman-link` command.

It takes a repository root, an overlay root, and an optional explicit identity.
It takes no registry and no state root, because a normal link operation reads
neither. This works for a repository the compatibility registry has never heard
of:

    devman-link status --project vendomat --root /path/to/vendomat \\
        --overlay ~/.config/devman

The old registry-driven command is a different program and keeps its own name.
This one refuses `--registry` and `--state` with a repair action rather than
accepting and ignoring them, because a flag that is silently dropped is how a
caller keeps believing it selected something.
"""

from __future__ import annotations

import argparse
import sys

from .api import DEFAULT_OVERLAY, OPERATIONS, format_results, run
from .errors import LinkAdapterError

_RETIRED = {
    "--registry": "the compatibility registry",
    "--state": "the compatibility state root",
}


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        help="explicit project identity; the manifest is authoritative when both exist",
    )
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument(
        "--overlay", default=DEFAULT_OVERLAY, help="the central configuration root"
    )


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="devman-link", description="Reconcile one repository's link plane."
    )
    sub = ap.add_subparsers(dest="operation", required=True)
    for name in OPERATIONS:
        _add_arguments(sub.add_parser(name))
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for flag, owner in _RETIRED.items():
        if flag in argv or any(item.startswith(f"{flag}=") for item in argv):
            print(
                f"devman-link: {flag} names {owner}, which this command does not read\n"
                "devman-link:   repair: drop the flag, or call the compatibility"
                " command for a registry-driven run",
                file=sys.stderr,
            )
            return 2
    args = parser().parse_args(argv)
    try:
        outcome = run(
            args.operation,
            root=args.root,
            overlay=args.overlay,
            project=args.project,
        )
    except LinkAdapterError as exc:
        for line in str(exc).splitlines():
            print(f"devman-link: {line}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — an infrastructure fault is exit 2
        print(f"devman-link: link operation failed: {exc}", file=sys.stderr)
        return 2
    for line in format_results(outcome):
        print(line)
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
