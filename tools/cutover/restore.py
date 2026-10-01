"""Restore every raw symlink target recorded by `snapshot.py`.

The undo for Lane 5 and Lane 6: both rewrite live symlinks, and both capture a
snapshot immediately before. `restore.py` reads that manifest and recreates
every recorded raw target exactly, byte for byte, through an atomic replace —
never through `realpath` or effective-target comparison (Trap 6).

`restore.py` only ever recreates a symlink. A managed path recorded as real
content (`file`, `dir`) is never created or overwritten here: `devman_link`
and Linkman both refuse to touch real content outside an explicit migration,
and this tool keeps the same boundary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .snapshot import DEFAULT_PROJECTS_ROOT, path_kind


class RestoreRefusedError(RuntimeError):
    """A live path's kind no longer matches the snapshot, and `--force` was not given."""


def _atomic_symlink(path: Path, raw_target: bytes) -> None:
    """Replace `path` with a symlink to `raw_target`, atomically."""
    tmp = path.with_name(f".{path.name}.restore-tmp")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(raw_target, os.fsencode(tmp))
    os.replace(os.fsencode(tmp), os.fsencode(path))


def restore(
    manifest: dict[str, object],
    *,
    projects_root: Path = DEFAULT_PROJECTS_ROOT,
    force: bool = False,
) -> list[str]:
    """Recreate every recorded symlink raw target. Returns the changed keys."""
    entries = manifest["entries"]
    mismatches: list[str] = []
    for entry in entries:
        path = projects_root / entry["project"] / entry["link_rel"]
        live_kind = path_kind(path)
        if live_kind != entry["kind"]:
            mismatches.append(
                f"{entry['project']}:{entry['link_rel']}: live kind is"
                f" {live_kind!r}, recorded kind is {entry['kind']!r}"
            )
    if mismatches and not force:
        detail = "\n".join(f"  {line}" for line in mismatches)
        raise RestoreRefusedError(
            f"refusing to restore: {len(mismatches)} path(s) changed kind since"
            f" the snapshot:\n{detail}\n  pass --force to override"
        )

    changed: list[str] = []
    for entry in entries:
        if entry["kind"] != "symlink" or entry["raw_target_hex"] is None:
            continue
        path = projects_root / entry["project"] / entry["link_rel"]
        raw_target = bytes.fromhex(entry["raw_target_hex"])
        try:
            current = os.readlink(os.fsencode(path))
        except OSError:
            current = None
        if current == raw_target:
            continue
        _atomic_symlink(path, raw_target)
        changed.append(f"{entry['project']}:{entry['link_rel']}")
    return changed


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Restore every raw symlink target from a snapshot.py manifest."
    )
    ap.add_argument(
        "--manifest", required=True, type=Path, help="a snapshot.py output file"
    )
    ap.add_argument(
        "--projects-root",
        type=Path,
        default=DEFAULT_PROJECTS_ROOT,
        help="the directory holding every project checkout",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="restore even where a live path's kind no longer matches the snapshot",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    try:
        changed = restore(manifest, projects_root=args.projects_root, force=args.force)
    except RestoreRefusedError as exc:
        print(f"restore: {exc}", file=sys.stderr)
        return 1
    for key in changed:
        print(f"restored {key}")
    print(f"restore: {len(changed)} path(s) changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
