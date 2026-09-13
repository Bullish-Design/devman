"""The stable component surface: two operations and three exit meanings.

    status       inspect links without changing a file
    reconcile    apply declarations and return one result per view

    0  the operation succeeded, and status found no drift
    1  status found drift, or reconciliation refused a requested change
    2  a usage or infrastructure error

One call does the whole sequence: resolve the identity, validate the central
file, resolve every declaration, then inspect or reconcile. A Python caller
reads the structured result; the command prints the operator's plain text.

Normal operation reads no compatibility registry entry, no ``metadata.json``,
and no ``generation.json``. A workflow generation update cannot change a link
target, because nothing here looks at one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .config import LinkConfiguration, validate_link_configuration
from .errors import LinkAdapterError, LinkError
from .identity import ProjectIdentity, resolve_project_identity
from .paths import user_path
from .reconcile import LinkResult, reconcile, status

DEFAULT_OVERLAY = "~/.config/devman"

OPERATIONS = ("status", "reconcile")


@dataclass(frozen=True, slots=True)
class LinkOutcome:
    """Everything one link operation decided, for a Python caller."""

    operation: str
    identity: ProjectIdentity
    configuration: LinkConfiguration
    results: tuple[LinkResult, ...]

    @property
    def project(self) -> str:
        return self.configuration.project

    @property
    def central_file(self) -> Path:
        return self.configuration.central_file

    @property
    def drifted(self) -> tuple[LinkResult, ...]:
        return tuple(result for result in self.results if result.state != "ok")

    @property
    def exit_code(self) -> int:
        """Status reports drift as 1. A completed reconcile is always 0."""
        if self.operation == "status" and self.drifted:
            return 1
        return 0


def run(
    operation: str,
    *,
    root: Path | str,
    overlay: Path | str = DEFAULT_OVERLAY,
    project: str | None = None,
    evaluator: Callable[[Path, str], object] | None = None,
) -> LinkOutcome:
    """Resolve, validate, then inspect or reconcile one repository's links."""
    if operation not in OPERATIONS:
        raise LinkError(
            f"unknown link operation {operation!r}\n"
            f"repair: use one of {', '.join(OPERATIONS)}"
        )
    repository = user_path(root)
    overlay_root = user_path(overlay)
    identity = resolve_project_identity(repository, project)
    configuration = validate_link_configuration(
        identity.root,
        overlay_root,
        identity.project,
        evaluator=evaluator,
    )
    action = status if operation == "status" else reconcile
    results = action(
        configuration.declarations,
        overlay=configuration.overlay,
        root=configuration.root,
        project=configuration.project,
    )
    return LinkOutcome(operation, identity, configuration, tuple(results))


def format_results(outcome: LinkOutcome) -> list[str]:
    """The operator's plain text, one line per view."""
    lines = []
    if outcome.operation == "status":
        lines.append(f"central config {outcome.central_file}")
    lines.extend(
        f"{result.state:7} {result.link.key}  {result.link.view_path}"
        for result in outcome.results
    )
    return lines


__all__ = [
    "DEFAULT_OVERLAY",
    "OPERATIONS",
    "LinkAdapterError",
    "LinkOutcome",
    "format_results",
    "run",
]
