"""Input hashes and derived compile health for status and doctor."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from devman.paths import Paths


def input_digest(paths: Paths) -> tuple[str | None, list[str]]:
    """Hash every required compile input in a stable order."""
    items: list[tuple[str, bytes]] = []
    errors: list[str] = []

    def add(key: str, value: bytes) -> None:
        items.append((key, value))

    required_files = [("manifest", paths.projects_toml), ("base", paths.base_src)]
    if paths.dagu_config is None:
        errors.append("DEVMAN_DAGU_CONFIG is not set")
    else:
        required_files.append(("dagu-config", paths.dagu_config))
    if not paths.guard:
        errors.append("DEVMAN_GUARD is not set")
    else:
        required_files.append(("guard", Path(paths.guard)))

    for name, path in required_files:
        try:
            key = f"file:{name}" if name == "base" else f"file:{name}:{path}"
            add(key, path.read_bytes())
        except OSError as exc:
            errors.append(f"cannot read {path}: {exc.strerror or exc}")

    values = {
        "DEVMAN_BASH": paths.bash,
        "DEVMAN_GUARD": paths.guard,
        "DEVMAN_BIN": paths.bin,
        "DEVMAN_STATE": str(paths.state),
    }
    for name, value in values.items():
        if value is None or not value:
            errors.append(f"{name} is not set")
        else:
            add(f"env:{name}", value.encode())

    for label, root in (
        ("project-workflows", paths.workflows),
        ("library-workflows", paths.library / "workflows"),
    ):
        try:
            root.stat()
        except FileNotFoundError:
            add(f"optional-dir:{label}:{root}", b"absent")
            continue
        except OSError as exc:
            errors.append(f"cannot read {root}: {exc.strerror or exc}")
            continue
        if not root.is_dir():
            errors.append(f"{root} is not a directory")
            continue
        add(f"optional-dir:{label}:{root}", b"present")
        try:
            if label == "project-workflows":
                for child in sorted(root.iterdir(), key=lambda item: item.name):
                    if child.is_dir():
                        add(f"project-dir:{child.name}", b"present")
            files = sorted(root.rglob("*.yaml"), key=lambda item: str(item))
        except OSError as exc:
            errors.append(f"cannot list {root}: {exc.strerror or exc}")
            continue
        for path in files:
            try:
                add(f"workflow:{path}", path.read_bytes())
            except OSError as exc:
                errors.append(f"cannot read {path}: {exc.strerror or exc}")

    if errors:
        return None, errors

    digest = hashlib.sha256()
    for key, value in sorted(items, key=lambda item: item[0]):
        key_bytes = key.encode()
        digest.update(struct.pack(">Q", len(key_bytes)))
        digest.update(key_bytes)
        digest.update(struct.pack(">Q", len(value)))
        digest.update(value)
    return digest.hexdigest(), []


def global_health(doc: dict, paths: Paths) -> dict:
    """Return stored global state with staleness derived from live inputs."""
    digest, input_errors = input_digest(paths)
    stored = doc.get("global") if doc.get("version") == 2 else None
    if not isinstance(stored, dict):
        reasons = ["a full compile is required for compile.json version 2"]
        reasons.extend(input_errors)
        return {
            "status": "refused",
            "at": None,
            "reasons": reasons,
            "successful_input_sha256": None,
            "stale": True,
        }

    saved_reasons = stored.get("reasons", [])
    reasons = list(saved_reasons) if isinstance(saved_reasons, list) else []
    successful = stored.get("successful_input_sha256")
    stale = stored.get("status") != "ok"
    if input_errors:
        reasons.extend(error for error in input_errors if error not in reasons)
        stale = True
    elif not successful:
        reasons.append("no successful full compile is recorded")
        stale = True
    elif digest != successful:
        reasons.append("inputs changed since the last successful full compile")
        stale = True

    return {
        "status": stored.get("status", "refused"),
        "at": stored.get("at"),
        "reasons": reasons,
        "successful_input_sha256": successful,
        "stale": stale,
    }
