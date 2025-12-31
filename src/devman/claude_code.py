"""Claude Code integration helpers."""

from __future__ import annotations

import shutil

from devman.workspace_config import WorkspaceConfig


def check_claude_code() -> bool:
    """Return True when the Claude Code CLI is available."""
    return shutil.which("claude") is not None


def generate_claude_code_settings(config: WorkspaceConfig) -> dict[str, object]:
    """Generate settings payload for Claude Code."""
    settings: dict[str, object] = {
        "workspace_name": config.name,
        "workspace_root": str(config.root),
        "emit_project_config": config.claude_code_emit_project_config,
    }
    if config.claude_code_interaction:
        settings["interaction_file"] = str(config.claude_code_interaction)
    return settings
