"""tmux integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TmuxIntegration:
    """Class-based tmux integration."""

    def is_available(self) -> bool:
        """Return True when tmux is installed."""
        return shutil.which("tmux") is not None

    def setup(self, session_name: str, root: Path) -> None:
        """Ensure a tmux session exists for the workspace."""
        self.ensure_session(session_name, root)

    def launch(self, session_name: str, root: Path) -> None:
        """Launch (or ensure) a tmux session for the workspace."""
        self.ensure_session(session_name, root)

    def session_exists(self, session_name: str) -> bool:
        """Check if a tmux session already exists."""
        if not self.is_available():
            return False
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    def ensure_session(self, session_name: str, root: Path) -> None:
        """Ensure a tmux session exists for the workspace."""
        if not self.is_available() or self.session_exists(session_name):
            return
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-c", str(root)],
            check=False,
        )

    def ensure_windows(self, session_name: str, root: Path) -> None:
        """Ensure the first tmux window matches the workspace name."""
        if not self.is_available() or not self.session_exists(session_name):
            return
        subprocess.run(
            ["tmux", "rename-window", "-t", f"{session_name}:0", root.name],
            check=False,
        )

    def kill_session(self, session_name: str) -> None:
        """Kill a tmux session if it exists."""
        if not self.is_available():
            return
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False)
