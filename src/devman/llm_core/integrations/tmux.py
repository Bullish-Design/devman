"""tmux integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_available() -> bool:
    return shutil.which("tmux") is not None


def _tmux_cmd(*args: str) -> list[str]:
    return ["tmux", *args]


def session_exists(session_name: str) -> bool:
    if not is_available():
        return False
    result = subprocess.run(
        _tmux_cmd("has-session", "-t", session_name),
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def ensure_session(session_name: str, root: Path) -> None:
    if not is_available() or session_exists(session_name):
        return
    subprocess.run(
        _tmux_cmd("new-session", "-d", "-s", session_name, "-c", str(root)),
        check=False,
    )


def ensure_windows(session_name: str, root: Path) -> None:
    if not is_available() or not session_exists(session_name):
        return
    subprocess.run(
        _tmux_cmd("rename-window", "-t", f"{session_name}:0", root.name),
        check=False,
    )


def kill_session(session_name: str) -> None:
    if not is_available():
        return
    subprocess.run(_tmux_cmd("kill-session", "-t", session_name), check=False)
