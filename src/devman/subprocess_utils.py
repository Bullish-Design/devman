from __future__ import annotations

from pathlib import Path
import shlex
import subprocess
from typing import Sequence


def _default_remediation_hints(command: Sequence[str]) -> list[str]:
    if not command:
        return []

    executable = command[0]
    if executable == "git":
        return [
            "Set git identity with: git config --global user.name \"Your Name\"",
            "Set git email with: git config --global user.email \"you@example.com\"",
        ]

    if executable == "copier":
        return ["Ensure Copier is installed and available on PATH (for example: uv tool install copier)."]

    return []


def run_checked_subprocess(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    context: str = "Command",
    remediation_hints: Sequence[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with strict checks and rich error messages."""
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        cmd = shlex.join(command)
        raise RuntimeError(
            f"{context} failed: executable not found while running `{cmd}`. "
            "Ensure the command is installed and on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        cmd = shlex.join(command)
        hints = list(remediation_hints or _default_remediation_hints(command))

        details = [
            f"{context} failed while running `{cmd}` (exit code {exc.returncode}).",
        ]

        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        if stdout:
            details.append(f"stdout: {stdout}")
        if stderr:
            details.append(f"stderr: {stderr}")
        if hints:
            details.append("Remediation hints:")
            details.extend(f"- {hint}" for hint in hints)

        raise RuntimeError("\n".join(details)) from exc
