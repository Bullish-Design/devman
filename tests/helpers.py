"""The builders every test in this suite uses: a registry made of real files.

Imported by name rather than through a package, because `pyproject.toml` puts
`tests/` on pytest's `pythonpath`. `conftest.py` beside this file turns the
builders into fixtures.


**Nothing here mocks devman, and nothing here reaches the installed plane.**
Everything writes into `tmp_path`. The registry is a directory shape
(`registry.py`'s docstring), so building one is `mkdir` plus `json.dump` plus a
symlink — cheaper and more faithful than a stub of `Registry`.

`.git` is written as a marker rather than by `git init`, because
`_checkout_between()` tests existence and not kind (`registry.py`). A real
subprocess would prove the same contract at a hundred times the cost.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from devman.registry import (
    DAG_SEPARATOR,
    LEGACY_DAG_SEPARATOR,
    Project,
    Registry,
)


@dataclass
class Plane:
    """One registry root, and the repositories it names.

    Not the installed plane — a throwaway one under `tmp_path`. `root` is what
    `Registry(--registry)` points at; `repos` is where the fake repositories
    live, so a project's registered path is never inside the registry.
    """

    root: Path
    repos: Path

    @property
    def reg(self) -> Registry:
        return Registry(self.root)

    def add(
        self,
        name: str,
        *,
        workflows: dict[str, str] | None = None,
        path: Path | None = None,
        local: list[str] | None = None,
        groups: list[str] | None = None,
        sources: dict[str, str] | None = None,
        triggers: dict | None = None,
        link: bool = True,
        legacy: bool = False,
        make_dir: bool = True,
    ) -> Project:
        """Register one project, exactly as the devenv module's projection does.

        `workflows` maps a workflow name to the YAML text of its projected file.
        `link` writes the `dags/` symlink the projection writes, under the
        current codec; `legacy` writes it under the pre-S-12 name instead, which
        is what a repository that has not been re-entered since looks like.
        `make_dir` creates the repository the entry points at. `sources` records
        where a name resolved from, which is what `doctor` check 4 diffs a
        shadowing file against (schema 2, §7.3).
        """
        workflows = workflows or {}
        sources = sources or {}
        path = path if path is not None else self.repos / name
        if make_dir:
            path.mkdir(parents=True, exist_ok=True)

        entry = self.root / "projects" / name
        wdir = entry / "workflows"
        wdir.mkdir(parents=True, exist_ok=True)
        for workflow, text in workflows.items():
            (wdir / f"{workflow}.yaml").write_text(text)
            if link:
                self.link(
                    name, workflow, f"../projects/{name}/workflows/{workflow}.yaml"
                )
            if legacy:
                self.link(
                    name,
                    workflow,
                    f"../projects/{name}/workflows/{workflow}.yaml",
                    sep=LEGACY_DAG_SEPARATOR,
                )

        # `metadata.json` is written LAST, which is what makes an interrupted
        # projection leave an entry `projects()` skips rather than half-reads
        # (registry.py, §9.3).
        (entry / "metadata.json").write_text(
            json.dumps(
                {
                    "schema": 3,
                    "project": name,
                    "path": str(path),
                    "groups": groups or [],
                    "local": local or [],
                    "workflows": {
                        w: {
                            "group": "base",
                            **({"source": s} if (s := sources.get(w)) else {}),
                        }
                        for w in {*workflows, *sources}
                    },
                    "triggers": triggers,
                    "plan": "",
                }
            )
        )
        return self.reg.project(name)

    def link(
        self, project: str, workflow: str, target: str, sep: str = DAG_SEPARATOR
    ) -> Path:
        """Write the `dags/` link for one workflow, replacing any that is there.

        The projection is `ln -sfn`, so the second writer of one flat name takes
        the first one's link and says nothing (§9.2). `target` is stated rather
        than derived so a test can write the intruder.
        """
        dags = self.root / "dags"
        dags.mkdir(parents=True, exist_ok=True)
        link = dags / f"{project}{sep}{workflow}.yaml"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
        return link


def mark_checkout(path: Path, *, worktree: bool = False) -> Path:
    """Give a directory its own `.git`.

    A directory in an ordinary clone, a **file** holding a `gitdir:` line in a
    linked worktree and in a submodule. `_checkout_between()` tests existence
    rather than kind, and this fixture is what proves it.
    """
    path.mkdir(parents=True, exist_ok=True)
    marker = path / ".git"
    if worktree:
        marker.write_text("gitdir: /somewhere/.git/worktrees/feature\n")
    else:
        marker.mkdir()
    return path


ORDINARY = "steps:\n  - name: s\n    run: echo hi\n"
"""A projected workflow that declares nothing — the ordinary case (§7.2, E4)."""
