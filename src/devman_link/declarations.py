"""One link declaration, validated before any path is resolved.

The declaration is the four fields the central Nix file states for one view:
``view``, ``canonical``, ``path`` and ``template``. Validation happens here and
not in the reconciler, so that an invalid declaration is refused before the
component touches the filesystem.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import LinkError

CANONICAL_KINDS = ("central", "repo", "external")


def require_relative(value: str, label: str) -> None:
    """Refuse a value that cannot stay inside the root it is joined to."""
    path = Path(value)
    if value in {"", "."}:
        raise LinkError(f"{label} must name a path")
    if path.is_absolute() or ".." in path.parts:
        raise LinkError(f"{label} must be relative and stay inside its root")


@dataclass(frozen=True)
class Declaration:
    """One declared view and the canonical side that backs it."""

    view: str
    canonical: str = "central"
    path: str = ""
    template: str | None = None

    @classmethod
    def read(cls, view: str, raw: object) -> Declaration:
        """Validate one raw declaration from the central configuration."""
        if not isinstance(raw, dict):
            raise LinkError(f"link {view!r} must be an attribute set")
        canonical = raw.get("canonical", "central")
        path = raw.get("path", "")
        template = raw.get("template")
        if canonical not in set(CANONICAL_KINDS):
            raise LinkError(
                f"link {view!r} states canonical={canonical!r};"
                " use central, repo, or external"
            )
        if not isinstance(path, str) or not isinstance(view, str):
            raise LinkError(f"link {view!r} has a non-string path")
        if template is not None and not isinstance(template, str):
            raise LinkError(f"link {view!r} has a non-string template")
        if template is not None and canonical != "central":
            raise LinkError(
                f"link {view!r} uses template={template!r}, but templates are"
                ' allowed only for canonical="central" links'
            )
        require_relative(view, f"view {view!r}")
        if canonical == "external":
            path = os.path.expanduser(path)
        elif path:
            require_relative(path, f"path for {view!r}")
        return cls(view, canonical, path, template)
