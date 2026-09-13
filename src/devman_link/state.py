"""The link state record, and the content hash the promotion rules compare.

The record lives beside the overlay root, in one file. It holds the canonical
path and the canonical content hash at the moment the link was last made. The
hash is what lets a later promotion tell "the developer edited the view" from
"both sides changed": the second one is refused rather than merged (025 §5.4).

The write is atomic. A half-written record would make the next run believe no
baseline exists, and a missing baseline turns a safe promotion into a refusal.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

STATE_FILE = ".devman-link-state.json"

State = dict[str, dict[str, str]]


def content_hash(path: Path) -> str:
    """Digest a file, a symlink, or a whole directory tree.

    A directory walks its children in sorted order and tags each entry by kind,
    so that a file and a directory of the same name cannot digest alike. A
    symlink digests its target text rather than what it points at, because the
    link itself is the content the plane owns.
    """
    digest = hashlib.sha256()
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            rel = child.relative_to(path).as_posix().encode()
            digest.update(
                b"d\0" + rel + b"\0" if child.is_dir() else b"f\0" + rel + b"\0"
            )
            if child.is_symlink():
                digest.update(b"l\0" + os.readlink(child).encode() + b"\0")
            elif child.is_file():
                digest.update(child.read_bytes())
        return digest.hexdigest()
    if path.is_symlink():
        digest.update(b"l\0" + os.readlink(path).encode())
    else:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def read_state(overlay: Path) -> State:
    """Read the record, treating an absent or damaged file as no baseline."""
    try:
        raw = json.loads((overlay / STATE_FILE).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def write_state(overlay: Path, state: State) -> None:
    """Replace the record atomically, so a reader never sees half of one."""
    overlay.mkdir(parents=True, exist_ok=True)
    temporary = overlay / f".{STATE_FILE}.new"
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, overlay / STATE_FILE)
