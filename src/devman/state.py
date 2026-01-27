# src/devman/state.py
"""State file management."""

from __future__ import annotations

import datetime
from pathlib import Path

import yaml

from devman.jj_info import get_jj_info


def create_state_file(
    devman_dir: Path, template_source: str | Path, data: dict[str, object]
) -> None:
    """Create state.yaml with template metadata."""
    jj_info = get_jj_info()
    branch = jj_info.get("bookmark")
    revision = jj_info.get("change_id")

    timestamp = datetime.datetime.now(datetime.UTC).isoformat()
    state = {
        "template": {
            "name": data["project_name"],
            "source": str(template_source),
            "version": revision,
            "applied_at": timestamp,
        },
        "variables": data,
        "history": [
            {
                "timestamp": timestamp,
                "action": "init",
                "template": data["project_name"],
                "source": str(template_source),
                "jj_branch": branch,
                "jj_revision": revision,
            }
        ],
    }

    state_file = devman_dir / "state.yaml"
    with open(state_file, "w") as file:
        yaml.dump(state, file, default_flow_style=False)
