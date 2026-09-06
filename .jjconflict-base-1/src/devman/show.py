"""`devman show <workflow>` — print the resolved file, to start an override (§7.3).

    devman show check > .devman/workflows/check.yaml

That line is criterion 5's own wording, so the file on stdout must be the
resolved file byte for byte. Everything about where it came from goes to
stderr, which keeps the redirect exact and still tells a person at a prompt
which group won and what it displaced.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .registry import Registry


def main(args, reg: Registry) -> int:
    project = reg.project(args.project) if args.project else reg.project_for(Path.cwd())

    if not args.workflow:
        # No workflow named: say what this project has. That is not §10's
        # forbidden `list` command — it is the resolution table for one project,
        # which is what `show` is for.
        print(f"{project.name}  {project.path}", file=sys.stderr)
        print(f"groups: {' '.join(project.groups) or '(none)'}", file=sys.stderr)
        for name in project.workflow_names():
            info = project.workflows.get(name, {})
            if name in project.local:
                where = "your own .devman/workflows/"
                if info.get("group"):
                    where += f" (shadows {info['group']})"
            else:
                where = f"group {info.get('group', '?')}"
                if info.get("shadows"):
                    where += f" (shadows {', '.join(info['shadows'])})"
            print(f"  {name:<16} {where}")
        return 0

    path = reg.workflow_file(project, args.workflow)
    target = source_file(project, args.workflow, path)
    if args.path:
        print(target)
        return 0

    info = project.workflows.get(args.workflow, {})
    origin = (
        "your own .devman/workflows/"
        if args.workflow in project.local
        else f"group {info.get('group', '?')}"
    )
    shadows = info.get("shadows") or []
    print(f"devman: {project.name}/{args.workflow} — {origin}", file=sys.stderr)
    if shadows:
        print(f"devman:   shadows: {', '.join(shadows)}", file=sys.stderr)
    print(f"devman:   {target}", file=sys.stderr)
    print(f"devman:   projected as {path}", file=sys.stderr)
    sys.stdout.write(target.read_text())
    return 0


def source_file(project, workflow: str, projected: Path) -> Path:
    """The file a person would copy — never the generated projection.

    Since stage 6 the projection is a **generated** file: the group body with a
    header stating this project's `working_dir`, `log_dir` and directory
    variable, so that Dagu's own scheduler can fire it (`STAGE_6_LOG.md`, S2).
    Printing that would break criterion 5's own wording —

        devman show check > .devman/workflows/check.yaml

    — because the saved copy would carry one project's absolute paths, and the
    next projection would add a second header to it.

    The registry already records where each workflow came from: `source` for a
    group file, and the repository's own `.devman/workflows/` for an override.
    """
    if workflow in project.local:
        own = project.path / ".devman" / "workflows" / f"{workflow}.yaml"
        if own.is_file():
            return own
    source = (project.workflows.get(workflow) or {}).get("source")
    if source and Path(source).is_file():
        return Path(source)
    # No recorded source: an older entry, or a projection whose group file is
    # gone. The projected file is then the only thing there is to print.
    return Path(projected).resolve()
