# src/devman/jj_info.py
"""Jujutsu integration utilities."""

from __future__ import annotations

import subprocess
from typing import Optional


def get_jj_info() -> dict[str, Optional[str]]:
    """Return current jj bookmark and change id info."""

    def run_jj(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["jj", *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None

    bookmark = None
    bookmark_result = run_jj(["bookmark", "list", "-r", "@", "--color=never"])
    if bookmark_result and bookmark_result.returncode == 0:
        lines = [
            line.strip() for line in bookmark_result.stdout.splitlines() if line.strip()
        ]
        if lines:
            bookmark = lines[0].split(":", maxsplit=1)[0].strip() or None

    change_id = None
    change_result = run_jj(["log", "-r", "@", "-T", "change_id.short()"])
    if change_result and change_result.returncode == 0:
        change_id = change_result.stdout.strip() or None

    return {"bookmark": bookmark, "change_id": change_id}
