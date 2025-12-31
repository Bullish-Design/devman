"""tmux integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_available() -> bool:
    """Return True when tmux is installed."""
    return shutil.which("tmux") is not None


def session_exists(session_name: str) -> bool:
    """Check if a tmux session already exists."""
    tmux_bin = shutil.which("tmux")
    if not tmux_bin:
        return False
    result = subprocess.run(
        [tmux_bin, "has-session", "-t", session_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def ensure_session(session_name: str, cwd: Path) -> None:
    """Ensure a tmux session exists for the workspace."""
    tmux_bin = shutil.which("tmux")
    if not tmux_bin:
        return
    if session_exists(session_name):
        return
    subprocess.run(
        [tmux_bin, "new-session", "-d", "-s", session_name, "-c", str(cwd)],
        check=False,
    )
