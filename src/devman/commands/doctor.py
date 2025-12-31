"""Diagnostics for external dependencies."""

from __future__ import annotations

from typing import Dict

from devman.integrations import claude_code, nvim, tmux, tmuxp


def run() -> Dict[str, bool]:
    """Return availability of external tools."""
    return {
        "tmux": tmux.is_available(),
        "tmuxp": tmuxp.is_available(),
        "nvim": nvim.is_available(),
        "claude": claude_code.is_available(),
    }


def render_report(status: Dict[str, bool]) -> list[str]:
    """Render a human-readable report."""
    lines = []
    for tool, available in status.items():
        lines.append(f"{tool}: {'ok' if available else 'missing'}")
    return lines
