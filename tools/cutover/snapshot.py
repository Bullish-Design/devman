"""Snapshot every `devman_link`-managed path across the live project set.

Lane 2 of the M14 devman cutover. This is the rollback evidence for every
later lane that rewrites a live symlink: Lane 5 normalizes 11 relative
`.agents` targets, and Lane 6 runs the first real Linkman apply. Both capture
a snapshot immediately before they touch anything, and `restore.py` is the
undo.

A managed path's raw target is read with `os.readlink` and stored as bytes
(hex-encoded in JSON). A Unicode normalization difference between two raw
targets that look alike would otherwise compare equal and hide a real
rewrite — see the M14 refactoring guide, Trap 6.

Discovery never hardcodes a key list or a project list. It reuses
`devman.cli._manifest_candidates`, the same manifest sweep `devman link
status --all` already uses, so there is one definition of "the live project
set" in this repository.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from devman.cli import _manifest_candidates
from devman_link.config import validate_link_configuration
from devman_link.declarations import Declaration
from devman_link.excludes import git_exclude_path
from devman_link.paths import resolve

SCHEMA_VERSION = 1
DEFAULT_OVERLAY = Path("~/.config/devman").expanduser()
DEFAULT_PROJECTS_ROOT = Path("~/Documents/Projects").expanduser()


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """One managed path, as `os.lstat` and `os.readlink` see it."""

    project: str
    link_rel: str
    raw_target_hex: str | None
    kind: str
    declared_in: str


def path_kind(path: Path) -> str:
    """Classify a path by `lstat`, never by `exists` (Trap 1)."""
    try:
        mode = path.lstat().st_mode
    except OSError:
        return "missing"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "dir"
    return "special"


def raw_target_hex(path: Path) -> str | None:
    """The raw symlink target, as bytes, hex-encoded. `None` off a symlink."""
    try:
        raw = os.readlink(os.fsencode(path))
    except OSError:
        return None
    return raw.hex()


def project_entries(
    project: str,
    root: Path,
    *,
    overlay: Path,
    evaluator: Callable[[Path, str], object] | None = None,
) -> list[SnapshotEntry]:
    """Every managed path for one live project.

    Declared links come from the central `devenv.local.nix`, resolved through
    the same `devman_link.paths.resolve` the reconciler uses. `.git/info/
    exclude` is added separately: it is devman's by D5, projected from a
    `.local.gitignore` rather than declared in `devman.link`.
    """
    configuration = validate_link_configuration(
        root, overlay, project, evaluator=evaluator
    )
    resolved_root = root.resolve()
    entries: list[SnapshotEntry] = []
    for view, raw in sorted(configuration.declarations.items()):
        declaration = Declaration.read(view, raw)
        if declaration.canonical == "repo":
            raise RuntimeError(
                f'{project}:{view} declares canonical="repo"; this kind is'
                " refused at cutover (decisions.md D-16, revision 16) — fix the"
                " central declaration before snapshotting"
            )
        resolved = resolve(declaration, overlay=overlay, root=root, project=project)
        entries.append(
            SnapshotEntry(
                project=project,
                link_rel=view,
                raw_target_hex=raw_target_hex(resolved.view_path),
                kind=path_kind(resolved.view_path),
                declared_in="overlay",
            )
        )
    exclude = git_exclude_path(resolved_root)
    if exclude is not None:
        entries.append(
            SnapshotEntry(
                project=project,
                link_rel=str(exclude.relative_to(resolved_root)),
                raw_target_hex=raw_target_hex(exclude),
                kind=path_kind(exclude),
                declared_in="implicit",
            )
        )
    return sorted(entries, key=lambda entry: entry.link_rel)


def take_snapshot(
    projects_root: Path = DEFAULT_PROJECTS_ROOT,
    *,
    overlay: Path = DEFAULT_OVERLAY,
    evaluator: Callable[[Path, str], object] | None = None,
) -> dict[str, object]:
    """Snapshot every manifest-backed project under `projects_root`.

    The payload holds no wall-clock field, so two consecutive snapshots of an
    unchanged tree are byte-identical — the Lane 2 gate depends on that.
    """
    candidates, errors = _manifest_candidates([str(projects_root)])
    if errors:
        detail = "\n".join(f"  {root}: {message}" for root, message in errors)
        raise RuntimeError(f"cannot snapshot every project cleanly:\n{detail}")
    entries: list[SnapshotEntry] = []
    for project, root in sorted(candidates.items()):
        entries.extend(
            project_entries(project, root, overlay=overlay, evaluator=evaluator)
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "projects_root": str(projects_root),
        "overlay": str(overlay),
        "entries": [asdict(entry) for entry in entries],
    }


def write_snapshot(out: Path, snapshot: dict[str, object]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Snapshot every devman_link-managed path, for restore.py."
    )
    ap.add_argument(
        "--out", required=True, type=Path, help="where to write the manifest"
    )
    ap.add_argument(
        "--projects-root",
        type=Path,
        default=DEFAULT_PROJECTS_ROOT,
        help="the directory holding every project checkout",
    )
    ap.add_argument(
        "--overlay",
        type=Path,
        default=DEFAULT_OVERLAY,
        help="the central configuration root",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        snapshot = take_snapshot(args.projects_root, overlay=args.overlay)
    except RuntimeError as exc:
        print(f"snapshot: {exc}", file=sys.stderr)
        return 1
    write_snapshot(args.out, snapshot)
    projects = {entry["project"] for entry in snapshot["entries"]}
    print(
        f"snapshot: {len(snapshot['entries'])} entries across"
        f" {len(projects)} projects -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
