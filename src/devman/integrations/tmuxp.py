"""tmuxp integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TmuxpIntegration:
    """Class-based tmuxp integration."""

    def is_available(self) -> bool:
        """Return True when tmuxp is installed."""
        return shutil.which("tmuxp") is not None

    def setup(self, workspace: Path, session_name: str | None = None) -> None:
        """Load a tmuxp workspace configuration."""
        if not self.is_available():
            return

        command = ["tmuxp", "load", "-d", "-y"]
        if session_name:
            command.extend(["-s", session_name])
        command.append(str(workspace))

        subprocess.run(command, check=False)

    def launch(self, workspace: Path, session_name: str | None = None) -> None:
        """Launch (or ensure) a tmuxp workspace."""
        self.setup(workspace, session_name)
