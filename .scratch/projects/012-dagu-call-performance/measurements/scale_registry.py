#!/usr/bin/env python3
"""012 Part C — what gets slower as the plane grows.

Builds a synthetic registry of N projects with the shape the projection writes,
under /tmp, and leaves the real one alone. The repositories it names are real
directories, because `watch_map()` skips a project whose path is gone and a
registry of ghosts would measure nothing.

Every project takes the `format` group, so `watch_map()` returns an entry for
each and `match()` does its full work over all N — which is the dispatch's own
scaling question, asked without Dagu in the picture.

Usage: scale_registry.py N OUTDIR
"""
from __future__ import annotations
import json, pathlib, shutil, sys

REAL = pathlib.Path.home() / ".local/share/devman"
WORKFLOW = (REAL / "projects/devman/workflows/format.yaml").read_text()
TRIGGERS = '[map]\n"**/*.py" = "format"\n'


def build(n: int, out: pathlib.Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    repos = out / "repos"
    (out / "dags").mkdir(parents=True)
    for i in range(n):
        name = f"p{i:05d}"
        repo = repos / name
        (repo / "src").mkdir(parents=True)
        entry = out / "projects" / name
        (entry / "workflows").mkdir(parents=True)
        (entry / "workflows/format.yaml").write_text(WORKFLOW)
        (entry / "triggers.toml").write_text(TRIGGERS)
        (entry / "metadata.json").write_text(json.dumps({
            "schema": 4, "project": name, "path": str(repo),
            "groups": ["base", "format"], "plan": "", "local": [],
            "workflows": {"format": {"group": "format", "shadows": [], "source": ""}},
            "triggers": {"group": "format", "map": {"**/*.py": "format"}, "ignore": []},
        }))
        (out / "dags" / f"{name}.format.yaml").symlink_to(
            f"../projects/{name}/workflows/format.yaml")
    print(f"{out}: {n} projects")


if __name__ == "__main__":
    build(int(sys.argv[1]), pathlib.Path(sys.argv[2]))
