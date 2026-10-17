"""Check a workflow source and render the compiled file (PLAN §A.2)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection
from pathlib import Path
from typing import Any

import yaml

# Top-level keys the header owns, and what to do instead.
HEADER_OWNED = {
    "working_dir": "the manifest sets the project directory",
    "env": "use step env or params",
    "log_dir": "devman sets the log directory",
    "shell": "devman sets the checkout guard shell",
}
EVENT_PARAMS = ("DEVMAN_EVENT", "DEVMAN_SUBJECT")


def _first_document(text: str) -> Any:
    return next(yaml.safe_load_all(text), None)


def _param_names(params: Any) -> set[str]:
    """The names a `params:` value declares, in map, list or string form."""
    if isinstance(params, dict):
        return {str(k) for k in params}
    if isinstance(params, str):
        params = params.split()
    names: set[str] = set()
    for item in params if isinstance(params, list) else []:
        if isinstance(item, dict):
            names.update(str(k) for k in item)
        elif isinstance(item, str):
            names.add(item.split("=", 1)[0])
    return names


def check_source(text: str, queues: Collection[str], label: str) -> list[str]:
    """The reasons a source is refused. `label` names the file in each reason."""
    try:
        doc = _first_document(text)
    except yaml.YAMLError as exc:
        return [f"{label}: invalid YAML: {str(exc).splitlines()[0]}"]
    if not isinstance(doc, dict):
        return [f"{label}: the first document is not a mapping"]
    reasons = [
        f"{label}: top-level {key} is set by devman; {advice}"
        for key, advice in HEADER_OWNED.items()
        if key in doc
    ]
    handlers = doc.get("handler_on")
    if isinstance(handlers, dict) and "exit" in handlers:
        reasons.append(
            f"{label}: handler_on.exit is set by devman; "
            "use handler_on.success or handler_on.failure"
        )
    if "params" in doc and not set(EVENT_PARAMS) <= _param_names(doc["params"]):
        reasons.append(f"{label}: params must declare DEVMAN_EVENT and DEVMAN_SUBJECT")
    queue = doc.get("queue")
    if not isinstance(queue, str) or not queue.strip():
        reasons.append(f"{label}: queue must be a nonempty configured string")
    elif queue not in queues:
        reasons.append(
            f"{label}: queue {queue} is not configured; configured: {', '.join(queues)}"
        )
    actions = doc.get("actions")
    if isinstance(actions, dict) and "devman.task" in actions:
        reasons.append(f"{label}: action devman.task is reserved by the packaged base")
    return reasons


def _strip_document_marker(text: str) -> str:
    """Drop a leading `---` line, so the header and the source stay one document."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() and not line.lstrip().startswith("#"):
            if line.strip() == "---":
                del lines[i]
            break
    return "".join(lines)


def render(
    project: str,
    workflow: str,
    project_path: Path,
    log_dir: Path,
    origin: str,
    source_path: Path,
    source_text: str,
    guard: str,
) -> str:
    """Return the compiled file: the header, then the source unchanged.

    The header sets `shell` to the checkout guard. A `shell` in `base.yaml` does
    not reach a step on Dagu 2.20.1 (measured in Stage 7), so the header owns it.
    """
    keys = _first_document(source_text)
    q = json.dumps  # JSON strings are valid YAML, so any path is quoted correctly
    head = [
        "# devman: compiled file. Do not edit. Edit the source and run `devman compile`.",
        f"# devman: project={project} workflow={workflow} origin={origin}",
        f"# devman: source={source_path}",
        f"# devman: source-sha256={hashlib.sha256(source_text.encode()).hexdigest()}",
        f"working_dir: {q(str(project_path))}",
        f"log_dir: {q(str(log_dir))}",
        f"shell: {q(guard)}",
        f"group: {q(project)}" if "group" not in keys else "",
        f"labels:\n  project: {q(project)}" if "labels" not in keys else "",
        f"env:\n  - DEVMAN_PROJECT_DIR: {q(str(project_path))}",
        'params:\n  - DEVMAN_EVENT: ""\n  - DEVMAN_SUBJECT: ""'
        if "params" not in keys
        else "",
        "# devman: source text follows",
    ]
    body = _strip_document_marker(source_text)
    if not body.endswith("\n"):
        body += "\n"
    return "\n".join(line for line in head if line) + "\n" + body
