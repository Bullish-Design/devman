"""Diagnostics for external dependencies."""

from __future__ import annotations

from typing import Dict

from devman.integrations import (
    ClaudeIntegration,
    NvimIntegration,
    TmuxIntegration,
    TmuxpIntegration,
)


TMUX = TmuxIntegration()
TMUXP = TmuxpIntegration()
NVIM = NvimIntegration()
CLAUDE = ClaudeIntegration()


def run() -> Dict[str, bool]:
    """Return availability of external tools."""
    return {
        "tmux": TMUX.is_available(),
        "tmuxp": TMUXP.is_available(),
        "nvim": NVIM.is_available(),
        "claude": CLAUDE.is_available(),
    }


def render_report(status: Dict[str, bool]) -> list[str]:
    """Render a human-readable report."""
    lines = []
    for tool, available in status.items():
        lines.append(f"{tool}: {'ok' if available else 'missing'}")
    return lines
