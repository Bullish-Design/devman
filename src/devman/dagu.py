"""Calls to Dagu. Stage 4 and Stage 6 add `enqueue`, `last_run` and `version`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


def configured_queues(config: Path) -> list[str]:
    """The queue names in a Dagu `config.yaml`, in file order."""
    data = yaml.safe_load(Path(config).read_text()) or {}
    queues = (data.get("queues") or {}).get("config") or []
    return [q["name"] for q in queues if isinstance(q, dict) and "name" in q]


def validate(config: Path, file: Path) -> str | None:
    """Run `dagu validate`. Return the error text, or None when the file is valid."""
    dagu = shutil.which("dagu")
    if dagu is None:
        return "dagu is not on PATH"
    result = subprocess.run(
        [dagu, "--config", str(config), "validate", str(file)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return None
    lines = (result.stdout + result.stderr).splitlines()
    text = "; ".join(
        ln.strip("- ").strip() for ln in lines if ln and not ln.startswith("time=")
    )
    return text or f"dagu validate exited {result.returncode}"
