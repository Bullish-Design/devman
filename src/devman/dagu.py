"""Calls to Dagu: the CLI (`validate`, `enqueue`, `version`) and the REST API."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

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


def version() -> str | None:
    """The version `dagu version` prints, or None when it cannot run."""
    dagu = shutil.which("dagu")
    if dagu is None:
        return None
    result = subprocess.run([dagu, "version"], capture_output=True, text=True)
    return result.stdout.strip() or None


def get(config: Path, path: str) -> Any:
    """GET one REST path. Raise OSError or ValueError when Dagu does not answer."""
    data = yaml.safe_load(Path(config).read_text()) or {}
    host, port = data.get("host") or "127.0.0.1", data.get("port") or 8080
    with urllib.request.urlopen(f"http://{host}:{port}/api/v1{path}", timeout=3) as r:
        return json.load(r)


def last_run(config: Path, dag: str) -> dict[str, Any] | None:
    """The newest run of one DAG, or None. Raise OSError when Dagu is down.

    Measured on 2.20.1: `name` is a filter, the list is newest first, and a run
    holds `dagRunId`, `statusLabel`, `startedAt` and `finishedAt`.
    """
    query = urllib.parse.urlencode({"name": dag, "limit": 5})
    runs = get(config, f"/dag-runs?{query}")["dagRuns"]
    return next((r for r in runs if r["name"] == dag), None)
