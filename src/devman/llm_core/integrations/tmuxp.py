"""tmuxp integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_available() -> bool:
    return shutil.which("tmuxp") is not None


def ensure_tmuxp(workspace: Path, session_name: str | None = None) -> None:
    if not is_available():
        return
    cmd = ["tmuxp", "load", "-d", "-y"]
    if session_name:
        cmd.extend(["-s", session_name])
    cmd.append(str(workspace))
    subprocess.run(cmd, check=False)
