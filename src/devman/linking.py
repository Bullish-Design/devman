"""The concept §14 flow: devman drives Linkman to manage its symlinks.

Six steps, in this order (`linkman-concept.md` §14; Lane 7 of the M14
cutover, decision D-b):

    1. resolve the project identity from .devman/project.toml
    2. ensure the central per-project directory exists; assert links.yaml
    3. read-only inspection, through Linkman's documented pipeline
    4. pre-create the one target Linkman cannot: the devenv.local.nix
       bootstrap
    5. project .local.gitignore -> .git/info/exclude (devman's, under D5)
    6. symlink topology only, through linkman.apply_plan

Step 2 comes before step 3 because a missing overlay layer is valid, empty
input: Linkman manages nothing and says nothing about it, so devman is the
only thing that can refuse a project it knows about but has no declaration
for.

Step 4 exists because Nix reads `devenv.local.nix` before any shell hook
runs, so a dangling link there fails shell entry with a trace nothing can
intercept. `apply_plan` must never be the thing that first creates it.
`excludes.py`, the copyroom call, and the bootstrap writer still live in
`devman_link`; Phase D (Lane 8) moves them into devman proper, unchanged.
This module reuses them rather than duplicating their logic ahead of that
move — `_as_resolved_links` below is a narrow adapter from Linkman's desired
state to `devman_link`'s domain shape, built only so
`devman_link.excludes.ensure_local_gitignore` can run unmodified.

Two corrections to the concept document, found while wiring this flow.
First, `linkman.load_layers` takes the two declaration file paths, not a
`Repository`; `linkman.api.load` shows the real two-argument call this
module follows. Second, `linkman apply` with no `--project` flag resolves
identity from the repository's own manifest, matching
`devman_link.resolve_project_identity`'s behaviour — this module calls that
same resolver directly rather than inferring identity from a path twice.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import linkman

from devman_link.declarations import Declaration
from devman_link.excludes import ensure_local_gitignore
from devman_link.identity import ProjectIdentity, resolve_project_identity
from devman_link.paths import ResolvedLink
from devman_link.reconcile import BOOTSTRAP_CENTRAL_FILE, link_path
from devman_link.state import read_state, write_state

DEFAULT_OVERLAY = Path("~/.config/devman").expanduser()


class LinkingError(RuntimeError):
    """A refusal from the concept §14 flow."""


@dataclass(frozen=True, slots=True)
class LinkingResult:
    """What one Linkman-backed `devman link reconcile` run did."""

    identity: ProjectIdentity
    apply_result: object  # linkman.ApplyResult; left untyped to avoid a hard import at type-check time for callers that only read .applied/.refused/.failed


def _central_project_dir(overlay: Path, project: str) -> Path:
    return overlay / "projects" / project


def _assert_links_yaml(overlay: Path, project: str) -> Path:
    """A missing overlay layer is valid, empty input to Linkman — Linkman
    will manage nothing and say nothing. devman is the only thing that can
    refuse a project it knows about but has no declaration for.
    """
    central = _central_project_dir(overlay, project)
    central.mkdir(parents=True, exist_ok=True)
    links_yaml = central / "links.yaml"
    if not links_yaml.exists():
        raise LinkingError(
            f"no links.yaml for project {project!r} at {links_yaml}\n"
            "repair: run the Phase A converter, or add one by hand; devman"
            " refuses to manage nothing for a project it knows about"
        )
    return links_yaml


def _ensure_bootstrap(desired: linkman.DesiredState) -> None:
    """Write the central `devenv.local.nix` before Linkman ever reads it.

    Mirrors `devman_link.api._bootstrap_central_file`: idempotent, and it
    never overwrites a file that already exists.
    """
    bootstrap = desired.links.get("devenv.local.nix")
    if bootstrap is None:
        return
    target = bootstrap.target_abs
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(BOOTSTRAP_CENTRAL_FILE)


def _as_resolved_links(
    desired: linkman.DesiredState, *, root: Path, overlay: Path, project: str
) -> list[ResolvedLink]:
    """Adapt Linkman's desired state to `devman_link`'s domain shape.

    Every link this module ever resolves is external to Linkman's own
    classification (targets live under the overlay or elsewhere outside the
    repository, never inside it), so `canonical="external"` is accurate for
    all of them here — the only distinction `exclusion_entries` makes is
    excluding a `canonical="repo"` link, and the Phase A converter already
    refuses that kind at cutover.
    """
    return [
        ResolvedLink(
            declaration=Declaration(
                view=link_rel, canonical="external", path=str(link.target_abs)
            ),
            project=project,
            overlay=overlay,
            root=root,
            view_path=link.link_abs,
            canonical_path=link.target_abs,
        )
        for link_rel, link in desired.links.items()
    ]


def _project_local_gitignore(
    desired: linkman.DesiredState, *, root: Path, overlay: Path, project: str
) -> None:
    """`.local.gitignore` -> `.git/info/exclude`. devman's own feature,
    under D5 — Linkman never touches version control.
    """
    state = read_state(overlay)
    resolved_links = _as_resolved_links(
        desired, root=root, overlay=overlay, project=project
    )
    changed = ensure_local_gitignore(
        root.resolve(), overlay, project, resolved_links, state, link_path=link_path
    )
    if changed:
        write_state(overlay, state)


def reconcile_with_linkman(
    root: Path | str,
    *,
    overlay: Path | str = DEFAULT_OVERLAY,
    project: str | None = None,
) -> LinkingResult:
    """Make this repository's symlink topology match its declarations,
    through Linkman, following concept §14's six steps.
    """
    repository_root = Path(root).expanduser().resolve()
    overlay_root = Path(overlay).expanduser().resolve()

    # 1. identity
    identity = resolve_project_identity(repository_root, project)

    # 2. the central directory and its links.yaml must already exist
    _assert_links_yaml(overlay_root, identity.project)

    # 3. read-only inspection, Linkman's documented pipeline (D-b)
    repo = linkman.discover_repository(
        repo_root=repository_root, overlay=overlay_root, name=identity.project
    )
    repo_layer = repo.repo_config if os.path.lexists(repo.repo_config) else None
    overlay_layer = (
        repo.overlay_config if os.path.lexists(repo.overlay_config) else None
    )
    config = linkman.load_layers(repo_layer, overlay_layer)
    desired = linkman.build_desired_state(repo, config, os.environ)
    linkman.validate_topology(desired)
    actual = linkman.inspect_state(desired)

    # 4. pre-create the one target Linkman cannot
    _ensure_bootstrap(desired)
    # The bootstrap write can change MISSING -> CORRECT for devenv.local.nix,
    # so the plan is built from a fresh inspection rather than the one above.
    actual = linkman.inspect_state(desired)
    plan = linkman.build_plan(desired, actual)

    # 5. the exclude projection, devman's own feature
    _project_local_gitignore(
        desired, root=repository_root, overlay=overlay_root, project=identity.project
    )

    # 6. symlink topology only
    result = linkman.apply_plan(repo, plan)
    return LinkingResult(identity=identity, apply_result=result)
