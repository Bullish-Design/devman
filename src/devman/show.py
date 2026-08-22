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
    target = Path(path).resolve()
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
    sys.stdout.write(target.read_text())
    return 0
