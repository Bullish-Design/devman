"""Inspect a link, and make a declaration true without losing content.

Five states, and the reconciler never removes a real view:

    ok        the view already points at its canonical side
    repoint   the view is a symlink to something else
    promote   the view is real content, so it moves to the canonical side first
    link      the view is absent and the canonical side exists
    create    neither side exists, so the canonical side is made first

The promotion rule is the safety rule. The canonical content hash is recorded
after every successful link, and a later promotion refuses when the canonical
side changed since that record. Refusing is the point: merging two edits
silently is the failure this design exists to prevent (025 §5.4).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .declarations import Declaration
from .errors import LinkError
from .excludes import ensure_local_gitignore
from .paths import ResolvedLink, resolve
from .state import State, content_hash, read_state, write_state

STATES = ("ok", "repoint", "promote", "link", "create")

# The declarations a brand-new central file starts with. It is written here and
# not by the central file itself, because the bootstrap link must exist before
# the next shell entry can evaluate anything (025 §5.5): Nix reads
# `devenv.local.nix` before any hook runs, so a dangling one fails shell entry
# with a trace nothing can intercept.
BOOTSTRAP_CENTRAL_FILE = (
    "{ config, ... }:\n\n"
    "{\n"
    "  devman.link = {\n"
    '    ".envrc" = { canonical = "central"; path = "common/envrc"; };\n'
    '    ".loci" = { canonical = "external";'
    ' path = "~/Notes/1_Projects/${config.devman.project}"; };\n'
    '    ".agents" = { canonical = "central";'
    ' path = "projects/${config.devman.project}/agents"; };\n'
    '    ".claude/skills" = { canonical = "central";'
    ' path = "projects/${config.devman.project}/agents/skills"; };\n'
    "  };\n"
    "}\n"
)


@dataclass(frozen=True)
class LinkResult:
    """What one view was, and what the reconciler did about it."""

    link: ResolvedLink
    state: str
    detail: str = ""


def inspect(link: ResolvedLink) -> LinkResult:
    """Report one view's state. This reads and never writes."""
    view = link.view_path
    if view.is_symlink():
        target = view.resolve(strict=False)
        if target == link.canonical_path and link.canonical_path.exists():
            return LinkResult(link, "ok")
        if target == link.canonical_path:
            return LinkResult(link, "create", "canonical target is absent")
        return LinkResult(link, "repoint", f"points to {target}")
    if view.exists():
        return LinkResult(link, "promote")
    if link.canonical_path.exists():
        return LinkResult(link, "link")
    return LinkResult(link, "create")


def link_path(
    view: Path,
    canonical: Path,
    *,
    promoted: bool = False,
    backup: bool = True,
) -> None:
    """Replace a view with a symlink, keeping a backup of real content."""
    view.parent.mkdir(parents=True, exist_ok=True)
    if view.is_symlink():
        view.unlink()
    elif view.exists():
        if not promoted:
            raise LinkError(f"refusing to replace real view {view}")
        if backup:
            backup_path = view.with_name(f"{view.name}.devman-promoted")
            if backup_path.exists() or backup_path.is_symlink():
                raise LinkError(
                    f"refusing to replace {view}; promotion backup already"
                    f" exists at {backup_path}"
                )
            os.replace(view, backup_path)
        else:
            view.unlink()
    view.symlink_to(canonical)


def _copy_content(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if destination.exists() and not destination.is_dir():
            raise LinkError(
                f"cannot promote directory {source} into file {destination}"
            )
        shutil.copytree(source, destination, dirs_exist_ok=True)
        return
    if destination.exists() and destination.is_dir():
        raise LinkError(f"cannot promote file {source} into directory {destination}")
    temporary = destination.with_name(f".{destination.name}.promote")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def _create_canonical(link: ResolvedLink, *, as_directory: bool = False) -> None:
    path = link.canonical_path
    if link.declaration.canonical == "external":
        path.mkdir(parents=True, exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if link.declaration.view == "devenv.local.nix":
        path.write_text(BOOTSTRAP_CENTRAL_FILE)
        return
    if link.declaration.template:
        copyroom = shutil.which("copyroom")
        if copyroom is None:
            raise LinkError(
                f"cannot render template {link.declaration.template!r} for {link.key};"
                " copyroom is not on PATH"
            )
        result = subprocess.run(
            [copyroom, "new", link.declaration.template, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise LinkError(
                f"copyroom could not render {link.declaration.template!r} for"
                f" {link.key}: {detail or f'exit {result.returncode}'}"
            )
        return
    if as_directory or "/" in link.declaration.view:
        path.mkdir(exist_ok=True)
    else:
        path.touch()


def _record(link: ResolvedLink, state: State) -> None:
    state[link.key] = {
        "canonical": str(link.canonical_path),
        "hash": content_hash(link.canonical_path),
    }


def _record_available(links: list[ResolvedLink], state: State) -> bool:
    """Record canonical paths that appeared while reconciling earlier views."""
    changed = False
    for link in links:
        if link.canonical_path.exists() and link.key not in state:
            _record(link, state)
            changed = True
    return changed


def resolve_all(
    declarations: dict[str, object], *, overlay: Path, root: Path, project: str
) -> list[ResolvedLink]:
    """Read and resolve every declaration before any of them is applied."""
    return [
        resolve(
            Declaration.read(view, raw), overlay=overlay, root=root, project=project
        )
        for view, raw in declarations.items()
    ]


def reconcile(
    declarations: dict[str, object],
    *,
    overlay: Path,
    root: Path,
    project: str,
) -> list[LinkResult]:
    """Apply declarations and return one result per view."""
    state = read_state(overlay)
    results: list[LinkResult] = []
    all_links = resolve_all(declarations, overlay=overlay, root=root, project=project)
    canonical_paths = [link.canonical_path for link in all_links]
    # A canonical path that is the parent of another must be made as a
    # directory, even when its own view name has no separator in it.
    directory_paths = {
        candidate
        for candidate in canonical_paths
        for other in canonical_paths
        if other != candidate and candidate in other.parents
    }
    changed = False
    for link in all_links:
        result = inspect(link)
        if result.state == "ok":
            if link.canonical_path.exists() and link.key not in state:
                _record(link, state)
                changed = True
            results.append(result)
            continue
        if result.state == "promote":
            if link.canonical_path.exists():
                previous = state.get(link.key, {})
                expected = previous.get("hash")
                actual = content_hash(link.canonical_path)
                if not expected or expected != actual:
                    raise LinkError(
                        f"refusing promotion for {link.key}: canonical changed"
                        " since the link was made; review both sides"
                    )
            _copy_content(link.view_path, link.canonical_path)
            link_path(link.view_path, link.canonical_path, promoted=True)
        elif result.state == "create":
            _create_canonical(link, as_directory=link.canonical_path in directory_paths)
            link_path(link.view_path, link.canonical_path)
        else:
            if not link.canonical_path.exists():
                _create_canonical(
                    link, as_directory=link.canonical_path in directory_paths
                )
            link_path(link.view_path, link.canonical_path)
        _record(link, state)
        changed = True
        if _record_available(all_links, state):
            changed = True
        results.append(result)
    if ensure_local_gitignore(
        root.resolve(), overlay, project, all_links, state, link_path=link_path
    ):
        changed = True
    if changed:
        write_state(overlay, state)
    return results


def status(
    declarations: dict[str, object],
    *,
    overlay: Path,
    root: Path,
    project: str,
) -> list[LinkResult]:
    """Report one result per view without changing a single file."""
    return [
        inspect(link)
        for link in resolve_all(
            declarations, overlay=overlay, root=root, project=project
        )
    ]
