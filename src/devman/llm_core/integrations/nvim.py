"""Neovim integration helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_available() -> bool:
    return shutil.which("nvim") is not None


def build_session_commands(workspace_root: Path, session_path: Path) -> list[str]:
    return [
        f"<cmd>cd {workspace_root}<cr>",
        f"<cmd>source {session_path}<cr>",
    ]


def remote_send(listen: Path, command: str) -> None:
    if not is_available():
        return
    subprocess.run(
        ["nvim", "--server", str(listen), "--remote-send", command],
        check=False,
    )


def launch(workspace_root: Path, listen: Path, init: Path | None = None) -> None:
    if not is_available():
        return
    cmd = ["nvim", "--listen", str(listen)]
    if init:
        cmd.extend(["-u", str(init)])
    cmd.append(str(workspace_root))
    subprocess.run(cmd, check=False)
