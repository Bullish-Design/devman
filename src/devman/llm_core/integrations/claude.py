"""Claude Code integration helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def is_available() -> bool:
    return shutil.which("claude") is not None


def emit_project_config(workspace_root: Path, interaction: Path | None) -> Path:
    config_dir = workspace_root / ".claude"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "project.json"
    payload = {
        "workspace": str(workspace_root),
        "interaction": str(interaction) if interaction else None,
    }
    config_path.write_text(json.dumps(payload, indent=2))
    return config_path
