"""Resolve both sides of a declaration, and refuse every unsafe path.

Three canonical classes, and one root check each:

    central    below the overlay
    repo       canonical in the repository, exposed below the overlay
    external   an absolute path outside the repository and the overlay

Every check resolves symlinked parents first. A symlinked directory inside the
overlay that points outside it is the escape this refuses; comparing the
unresolved path would accept it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .declarations import Declaration, require_relative
from .errors import LinkError


@dataclass(frozen=True)
class ResolvedLink:
    """One declaration with both of its sides resolved to absolute paths."""

    declaration: Declaration
    project: str
    overlay: Path
    root: Path
    view_path: Path
    canonical_path: Path

    @property
    def key(self) -> str:
        return f"{self.project}:{self.declaration.view}"


def user_path(value: str | Path) -> Path:
    """Expand the shell forms an operator types, without resolving symlinks."""
    return Path(os.path.expandvars(str(value))).expanduser()


def expanded_path(root: Path, value: str, project: str, label: str) -> Path:
    """Expand ``${project}``, then refuse anything that leaves ``root``."""
    rendered = value.replace("${project}", project)
    require_relative(rendered, label)
    root = root.resolve()
    path = (root / rendered).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise LinkError(f"{label} escapes {root}") from exc
    if path == root:
        raise LinkError(f"{label} must name a path below {root}")
    return path


def view_path(root: Path, view: str) -> Path:
    """Resolve a view while refusing a symlinked parent outside the repo."""
    root = root.resolve()
    path = root / view
    parent = path.parent.resolve()
    try:
        parent.relative_to(root)
    except ValueError as exc:
        raise LinkError(f"view {view!r} escapes project repository {root}") from exc
    return path


def local_gitignore_path(overlay: Path, project: str) -> Path:
    """The one central file that owns a repository's Git exclusions."""
    return expanded_path(
        overlay,
        f"projects/{project}/.local.gitignore",
        project,
        f"local gitignore for {project!r}",
    )


def local_gitignore_key(project: str) -> str:
    return f"{project}:.git/info/exclude"


def resolve(
    declaration: Declaration, *, overlay: Path, root: Path, project: str
) -> ResolvedLink:
    """Resolve both sides without inferring identity from a directory name."""
    root = root.resolve()
    overlay = overlay.resolve()
    view = view_path(root, declaration.view)
    default = f"projects/{project}/repo/{declaration.view}"
    if declaration.canonical == "external":
        rendered = declaration.path.replace("${project}", project)
        rendered = os.path.expandvars(os.path.expanduser(rendered))
        candidate = Path(rendered)
        if not candidate.is_absolute():
            raise LinkError(
                f"path for {declaration.view!r} must be absolute after expansion"
            )
        external = candidate.resolve()
        for name, boundary in (("project repository", root), ("overlay", overlay)):
            boundary = boundary.resolve()
            if external == boundary or boundary in external.parents:
                raise LinkError(
                    f"external path for {declaration.view!r} resolves inside the"
                    f" {name}: {external}"
                )
        return ResolvedLink(declaration, project, overlay, root, view, external)
    central = expanded_path(
        overlay,
        declaration.path or default,
        project,
        f"path for {declaration.view!r}",
    )
    if declaration.canonical == "central":
        return ResolvedLink(declaration, project, overlay, root, view, central)
    # A `repo` link inverts the two sides: the repository holds the canonical
    # content and the overlay carries the view into it.
    return ResolvedLink(declaration, project, overlay, root, central, view)
