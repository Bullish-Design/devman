"""Focused reproductions for project 009's Python-layer review findings.

Run this file inside the repository's devenv shell. It writes only to a
temporary directory and does not read the installed devman registry.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from devman import run, watch
from devman.registry import Registry, dag_name_fault
from devman.workflow import PROJECT_DIR


ORDINARY = "steps:\n  - name: step\n    run: echo ok\n"
TRIGGERS = {"group": "format", "map": {"**/*.py": "format"}}


def add_project(
    registry: Path,
    name: str,
    project_path: Path,
    *,
    workflow: str = "format",
    body: str = ORDINARY,
    triggers: dict | None = TRIGGERS,
) -> None:
    project_path.mkdir(parents=True, exist_ok=True)
    entry = registry / "projects" / name
    workflows = entry / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / f"{workflow}.yaml").write_text(body)
    dags = registry / "dags"
    dags.mkdir(parents=True, exist_ok=True)
    (dags / f"{name}.{workflow}.yaml").symlink_to(
        f"../projects/{name}/workflows/{workflow}.yaml"
    )
    (entry / "metadata.json").write_text(
        json.dumps(
            {
                "schema": 3,
                "project": name,
                "path": str(project_path),
                "groups": ["format"],
                "local": [],
                "workflows": {workflow: {"group": "format"}},
                "triggers": triggers,
                "plan": "",
            }
        )
    )


def nested_watch_reproduction(root: Path) -> None:
    registry = root / "registry"
    outer = root / "outer"
    inner = outer / "inner"
    add_project(registry, "outer", outer)
    add_project(registry, "inner", inner)

    hits = watch.match(Registry(registry), [str(inner / "changed.py")])
    projects = [entry.project for entry, _ in hits]
    print(f"nested watcher hits: {projects}")
    assert projects == ["inner"], projects


def undeclared_override_reproduction(root: Path) -> None:
    registry = root / "registry-override"
    project_path = root / "override-project"
    add_project(
        registry,
        "override",
        project_path,
        workflow="check",
        triggers=None,
    )
    project = Registry(registry).project("override")

    _dag, params, _dir_var = run.resolve(
        Registry(registry), project, "check", {"TYPO": "value"}
    )
    print(f"resolved parameters: {params}")
    assert "TYPO" not in params, params


def directory_override_reproduction(root: Path) -> None:
    registry = root / "registry-directory-override"
    project_path = root / "directory-project"
    other_path = root / "different-project"
    other_path.mkdir()
    add_project(
        registry,
        "directory",
        project_path,
        workflow="check",
        triggers=None,
    )
    reg = Registry(registry)
    project = reg.project("directory")

    _dag, params, _dir_var = run.resolve(
        reg, project, "check", {PROJECT_DIR: str(other_path)}
    )
    print(f"resolved target after directory override: {params[PROJECT_DIR]}")
    assert params[PROJECT_DIR] == str(project_path), params


def malformed_registry_reproduction(root: Path) -> None:
    registry = root / "registry-malformed"
    entry = registry / "projects" / "bad"
    entry.mkdir(parents=True)
    (entry / "metadata.json").write_text("[]\n")

    projects = Registry(registry).projects()
    print(f"projects after a non-object entry: {projects}")
    assert projects == {}, projects


def invalid_dag_name_reproduction(root: Path) -> None:
    registry = root / "registry-name"
    project_path = root / "name-project"
    add_project(
        registry,
        "bad@project",
        project_path,
        workflow="check",
        triggers=None,
    )
    reg = Registry(registry)
    project = reg.project("bad@project")

    dag, _params, _dir_var = run.resolve(reg, project, "check", {})
    print(f"codec result for a Dagu-invalid name: {dag}")
    assert dag_name_fault("check") is None
    assert "@" not in dag, dag


def schema_invalid_workflow_reproduction(root: Path) -> None:
    registry = root / "registry-schema"
    project_path = root / "schema-project"
    body = "name: forbidden\n" + ORDINARY
    add_project(
        registry,
        "schema",
        project_path,
        workflow="check",
        body=body,
        triggers=None,
    )
    reg = Registry(registry)
    project = reg.project("schema")

    resolved = run.resolve(reg, project, "check", {})
    print(f"schema-invalid workflow resolved for enqueue: {resolved[0]}")
    raise AssertionError("run.resolve accepted a file Dagu refuses")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="devman-review-") as raw:
        root = Path(raw)
        cases = [
            nested_watch_reproduction,
            undeclared_override_reproduction,
            directory_override_reproduction,
            malformed_registry_reproduction,
            invalid_dag_name_reproduction,
            schema_invalid_workflow_reproduction,
        ]
        for case in cases:
            try:
                case(root)
            except Exception as exc:  # The failure is the reproduction output.
                print(f"{case.__name__}: CONFIRMED — {type(exc).__name__}: {exc}")
            else:
                print(f"{case.__name__}: not reproduced")


if __name__ == "__main__":
    main()
