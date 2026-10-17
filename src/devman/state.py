"""One validated reader for `compile.json` (048 state validation, PLAN §A.3).

Every command reads compile state through `read`. A missing file is an
initial condition: `read` returns None. An existing file with broken JSON or
a wrong shape is an error: `read` raises `StateError` with a field path. The
message never names the bad value, which can hold private data.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"[0-9a-f]{64}")
STATUSES = ("ok", "refused")


class StateError(ValueError):
    """Malformed compile state. The message carries a field path."""


def _field(label: str, path: str, expected: str) -> StateError:
    return StateError(f"{label}: {path} must be {expected}")


def _required(doc: dict, key: str, label: str, where: str = "") -> Any:
    """The value of a required key. `where` is the full field path."""
    if key not in doc:
        raise StateError(f"{label}: {where or key} is required")
    return doc[key]


def _mapping(value: Any, label: str, path: str) -> dict:
    if not isinstance(value, dict):
        raise _field(label, path, "a mapping")
    return value


def _string(value: Any, label: str, path: str) -> str:
    if not isinstance(value, str):
        raise _field(label, path, "a string")
    return value


def _string_list(value: Any, label: str, path: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(i, str) for i in value):
        raise _field(label, path, "a list of strings")
    return value


def _time(value: Any, label: str, path: str) -> str:
    try:
        ok = (
            isinstance(value, str)
            and bool(value)
            and datetime.fromisoformat(value).tzinfo is not None
        )
    except ValueError:
        ok = False
    if not ok:
        raise _field(label, path, "a UTC time")
    return value


def _digest(value: Any, label: str, path: str, null: bool = False) -> str | None:
    """A 64-character lowercase SHA-256 string; with `null`, also None."""
    if isinstance(value, str) and SHA256_RE.fullmatch(value):
        return value
    if null and value is None:
        return None
    expected = "a 64-character lowercase sha256 string"
    raise _field(label, path, f"{expected} or null" if null else expected)


def _status(value: Any, label: str, path: str) -> str:
    if value not in STATUSES:
        raise _field(label, path, "ok or refused")
    return value


def _boolean(value: Any, label: str, path: str) -> bool:
    if not isinstance(value, bool):
        raise _field(label, path, "true or false")
    return value


def _on_entry(entry: Any, label: str, path: str) -> None:
    _mapping(entry, label, path)
    _string(_required(entry, "event", label), label, f"{path}.event")
    _string(_required(entry, "run", label), label, f"{path}.run")
    _string_list(_required(entry, "match", label), label, f"{path}.match")
    _string_list(_required(entry, "exclude", label), label, f"{path}.exclude")


def _on_entry(entry: Any, label: str, path: str) -> None:
    _mapping(entry, label, path)
    _string(_required(entry, "event", label, f"{path}.event"), label, f"{path}.event")
    _string(_required(entry, "run", label, f"{path}.run"), label, f"{path}.run")
    _string_list(
        _required(entry, "match", label, f"{path}.match"), label, f"{path}.match"
    )
    _string_list(
        _required(entry, "exclude", label, f"{path}.exclude"),
        label,
        f"{path}.exclude",
    )


def _project(record: Any, label: str, path: str) -> None:
    _mapping(record, label, path)
    status = _status(
        _required(record, "status", label, f"{path}.status"), label, f"{path}.status"
    )
    _boolean(_required(record, "stale", label, f"{path}.stale"), label, f"{path}.stale")
    _time(_required(record, "at", label, f"{path}.at"), label, f"{path}.at")
    _string_list(
        _required(record, "reasons", label, f"{path}.reasons"),
        label,
        f"{path}.reasons",
    )
    on = _required(record, "on", label, f"{path}.on")
    if not isinstance(on, list):
        raise _field(label, f"{path}.on", "a list")
    for index, entry in enumerate(on):
        _on_entry(entry, label, f"{path}.on[{index}]")
    flows = _mapping(
        _required(record, "workflows", label, f"{path}.workflows"),
        label,
        f"{path}.workflows",
    )
    for name, flow in flows.items():
        where = f"{path}.workflows.{name}"
        _mapping(flow, label, where)
        for key in ("dag", "file", "origin", "source"):
            _string(
                _required(flow, key, label, f"{where}.{key}"),
                label,
                f"{where}.{key}",
            )
        _digest(
            _required(flow, "sha256", label, f"{where}.sha256"),
            label,
            f"{where}.sha256",
        )
    record_path = _required(record, "path", label, f"{path}.path")
    if status == "ok":
        if not isinstance(record_path, str) or not record_path:
            raise StateError(
                f"{label}: {path}.path must be a nonempty string when status is ok"
            )
    elif record_path is not None and not isinstance(record_path, str):
        raise StateError(f"{label}: {path}.path must be a nonempty string or null")


def _global(record: Any, label: str) -> None:
    _mapping(record, label, "global")
    status = _status(
        _required(record, "status", label, "global.status"), label, "global.status"
    )
    _time(_required(record, "at", label, "global.at"), label, "global.at")
    reasons = _string_list(
        _required(record, "reasons", label, "global.reasons"),
        label,
        "global.reasons",
    )
    digest = _digest(
        _required(
            record, "successful_input_sha256", label, "global.successful_input_sha256"
        ),
        label,
        "global.successful_input_sha256",
        null=True,
    )
    if status == "ok":
        if digest is None:
            raise StateError(
                f"{label}: global.successful_input_sha256 is required"
                " when global.status is ok"
            )
        if reasons:
            raise StateError(
                f"{label}: global.reasons must be empty when global.status is ok"
            )


def validate(doc: Any, label: str = "compile.json") -> dict[str, Any]:
    """Return `doc` when it holds valid version 1 or version 2 state.

    Extra keys stay: they may carry future additions, and a reader never uses
    them to fill a missing required field.
    """
    if not isinstance(doc, dict):
        raise StateError(f"{label}: the top-level document must be a mapping")
    version = _required(doc, "version", label)
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version
        not in (
            1,
            2,
        )
    ):
        raise StateError(f"{label}: version must be integer 1 or 2")
    _time(_required(doc, "compiled_at", label), label, "compiled_at")
    projects = _mapping(_required(doc, "projects", label), label, "projects")
    for name, record in projects.items():
        _project(record, label, f"projects.{name}")
    if version == 2:
        _global(_required(doc, "global", label), label)
    if "orphans" in doc:  # version 1 kept orphan names at the top level
        _string_list(doc["orphans"], label, "orphans")
    return doc


def read(path: Path) -> dict[str, Any] | None:
    """Read `compile.json` and validate it. None when the file is missing.

    Raise StateError when the file exists but is unreadable or malformed.
    """
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StateError(f"{path.name}: cannot be read: {exc.strerror}") from exc
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise StateError(f"{path.name}: invalid JSON: {exc}") from exc
    return validate(doc, path.name)
