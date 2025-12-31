"""tmuxp integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def is_available() -> bool:
    """Return True when tmuxp is installed."""
    return shutil.which("tmuxp") is not None


def load_workspace(config_path: Path, session_name: Optional[str] = None) -> None:
    """Load a tmuxp workspace configuration."""
    tmuxp_bin = shutil.which("tmuxp")
    if not tmuxp_bin:
        return

    command = [tmuxp_bin, "load", "-d", str(config_path)]
    if session_name:
        command.extend(["--session-name", session_name])

    subprocess.run(command, check=False)
