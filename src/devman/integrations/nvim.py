"""Neovim integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NvimIntegration:
    """Class-based Neovim integration."""

    def is_available(self) -> bool:
        """Return True when Neovim is installed."""
        return shutil.which("nvim") is not None

    def setup(self, workspace_root: Path, listen: Path, init: Path | None = None) -> None:
        """Prepare and launch a Neovim instance."""
        self.launch(workspace_root, listen, init)

    def launch(self, workspace_root: Path, listen: Path, init: Path | None = None) -> None:
        """Launch Neovim with a listen socket and optional init file."""
        if not self.is_available():
            return

        listen.parent.mkdir(parents=True, exist_ok=True)

        command = ["nvim", "--listen", str(listen)]
        if init is not None:
            command.extend(["-u", str(init)])

        subprocess.Popen(command, cwd=str(workspace_root))

    def build_session_commands(self, workspace_root: Path, session_path: Path) -> list[str]:
        """Build remote commands to load a Neovim session."""
        return [
            f"<cmd>cd {workspace_root}<cr>",
            f"<cmd>silent! source {session_path}<cr>",
        ]

    def remote_send(self, listen: Path, command: str) -> None:
        """Send a remote command to an existing Neovim instance."""
        if not self.is_available():
            return

        subprocess.run(
            ["nvim", "--server", str(listen), "--remote-send", command],
            check=False,
        )
