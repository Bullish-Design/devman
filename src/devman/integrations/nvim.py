"""Neovim integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def is_available() -> bool:
    """Return True when Neovim is installed."""
    return shutil.which("nvim") is not None


def launch(workspace_root: Path, listen: Path, init: Optional[Path] = None) -> None:
    """Launch Neovim with a listen socket and optional init file."""
    nvim_bin = shutil.which("nvim")
    if not nvim_bin:
        return

    listen.parent.mkdir(parents=True, exist_ok=True)

    command = [nvim_bin, "--listen", str(listen)]
    if init is not None:
        command.extend(["-u", str(init)])

    subprocess.Popen(command, cwd=str(workspace_root))


def build_session_commands(session_path: Path) -> list[str]:
    """Build remote commands to load a Neovim session."""
    return [f":silent! source {session_path}\n"]


def remote_send(listen: Path, command: str) -> None:
    """Send a remote command to an existing Neovim instance."""
    nvim_bin = shutil.which("nvim")
    if not nvim_bin:
        return

    subprocess.run(
        [nvim_bin, "--server", str(listen), "--remote-send", command],
        check=False,
    )
