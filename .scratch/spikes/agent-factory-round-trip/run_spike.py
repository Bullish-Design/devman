"""Run the complete round-trip spike and preserve evidence."""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path


class Recorder:
    """Write the same concise evidence to stdout and run.log."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, line: str) -> None:
        print(line)
        with self.path.open("a") as stream:
            stream.write(line + "\n")


def dependency_version(distribution: str, module: str) -> str:
    """Read installed metadata, then fall back to a source module version."""

    try:
        return version(distribution)
    except Exception:
        loaded = importlib.import_module(module)
        return str(getattr(loaded, "__version__", "source-tree"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    artifacts: Path = args.artifacts
    if artifacts.exists() and any(artifacts.iterdir()):
        parser.error(f"artifact directory is not fresh: {artifacts}")
    artifacts.mkdir(parents=True, exist_ok=True)
    record = Recorder(artifacts / "run.log")
    command = " ".join(sys.argv)
    environment = {
        "started_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "python": platform.python_version(),
        "pydantic": dependency_version("pydantic", "pydantic"),
        "pydantree-sitter": dependency_version("pydantree-sitter", "pydantree_sitter"),
        "templateer": dependency_version("templateer", "templateer"),
        "tree-sitter-python": dependency_version(
            "tree-sitter-python", "tree_sitter_python"
        ),
        "ruff": subprocess.run(
            ["ruff", "--version"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "network": "disabled by spike contract",
    }
    (artifacts / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n"
    )
    record.write(f"command={command}")
    record.write(f"python={environment['python']}")
    record.write(f"pydantree-sitter={environment['pydantree-sitter']}")
    record.write(f"templateer={environment['templateer']}")
    record.write(f"ruff={environment['ruff']}")
    try:
        from cases import run_all

        results = run_all(artifacts)
    except Exception:
        detail = traceback.format_exc()
        (artifacts / "failure.txt").write_text(detail)
        record.write("status=failed")
        record.write(detail.rstrip())
        return 1
    (artifacts / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n"
    )
    for result in results:
        record.write(f"case={result['case']} passed={str(result['passed']).lower()}")
    passed = all(bool(result["passed"]) for result in results)
    record.write(f"status={'passed' if passed else 'failed'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
