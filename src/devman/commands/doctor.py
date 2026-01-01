"""Diagnostics for external dependencies."""

from __future__ import annotations

from devman.claude_code import ClaudeCodeWorkspace
from devman.integrations import NvimIntegration, TmuxIntegration, TmuxpIntegration


TMUX = TmuxIntegration()
TMUXP = TmuxpIntegration()
NVIM = NvimIntegration()
CLAUDE_WORKSPACE = ClaudeCodeWorkspace()


def run() -> dict[str, bool]:
    """Return availability of external tools."""
    return {
        "tmux": TMUX.is_available(),
        "tmuxp": TMUXP.is_available(),
        "nvim": NVIM.is_available(),
        "claude": CLAUDE_WORKSPACE.is_available(),
    }


def render_report(status: dict[str, bool]) -> list[str]:
    """Render a human-readable report."""
    lines = []
    for tool, available in status.items():
        lines.append(f"{tool}: {'ok' if available else 'missing'}")
    return lines


def doctor() -> dict[str, bool]:
    """Backward-compatible alias for run."""
    return run()
