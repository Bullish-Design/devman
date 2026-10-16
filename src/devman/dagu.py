"""Calls to Dagu. Stage 6 adds `last_run` and `version`."""

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


def enqueue(
    config: Path, dag_file: Path, run_id: str, event: str, params: list[str]
) -> str | None:
    """Run `dagu enqueue` on the absolute path of a compiled file.

    Return the error text, or None when Dagu queued the run. The path form is
    required: the CLI does not find a subdirectory DAG by name (M4). `--name`
    and `--default-working-dir` are never used (M6).
    """
    dagu = shutil.which("dagu")
    if dagu is None:
        return "dagu is not on PATH"
    argv = [
        dagu,
        "--config",
        str(config),
        "enqueue",
        "--run-id",
        run_id,
        "--labels",
        f"devman.event={event}",
        str(dag_file),
        "--",
        *params,
    ]
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return None
    lines = (result.stdout + result.stderr).splitlines()
    text = "; ".join(ln.strip() for ln in lines if ln.strip() and "time=" not in ln)
    return text or f"dagu enqueue exited {result.returncode}"
