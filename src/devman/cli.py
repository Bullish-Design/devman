# src/devman/cli.py
from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .copier_engine import (
    generate_from_template,
    DEFAULT_ANSWERS_FILE,
    snapshot_render_to_memory,
    plan_against_destination,
)

app = typer.Typer(
    name="devman", no_args_is_help=True, help="Generate Python projects with Copier"
)
console = Console()

BUILTINS = {"python-lib", "python-cli", "fastapi-api"}


_slug_re = re.compile(r"[^a-z0-9_-]+")


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = _slug_re.sub("-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "project"


def answers_dict(
    name: str, python: str, package, nix: bool, docker: bool, just: bool
) -> dict:
    base = Path(name).name  # "mylib" from "/home/.../mylib"
    slug = _slugify(base)  # "mylib"
    pkg = (package or slug.replace("-", "_")).lstrip(".")
    return {
        "project_name": base,
        "project_slug": slug,
        "package_name": pkg,
        "python_version": python,
        "use_nix": nix,
        "use_docker": docker,
        "use_just": just,
    }


@app.command("list-templates")
def list_templates() -> None:
    """List built-in templates bundled with devman."""
    table = Table(title="Built-in Templates")
    table.add_column("Slug", style="bold")
    table.add_column("Description")
    table.add_row("python-lib", "Minimal Python library project")
    table.add_row("python-cli", "Typer-based CLI application")
    table.add_row("fastapi-api", "FastAPI web service")
    console.print(table)


@app.command(no_args_is_help=True)
def generate(
    name: str = typer.Argument(..., help="Project name / target directory"),
    template: str = typer.Option(
        "python-lib",
        "--template",
        "-t",
        help="Built-in slug (python-lib|python-cli|fastapi-api) or a local path or a Git URL",
    ),
    python: str = typer.Option(
        "3.11", "--python", "-p", help="Python version for the project"
    ),
    package: Optional[str] = typer.Option(
        None, "--package", "-k", help="Package import name"
    ),
    nix: bool = typer.Option(True, "--nix/--no-nix", help="Include Nix devenv files"),
    docker: bool = typer.Option(
        True, "--docker/--no-docker", help="Include Docker files"
    ),
    just: bool = typer.Option(True, "--just/--no-just", help="Include Justfile"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
    non_interactive: bool = typer.Option(
        True, "--no-input/--input", help="Run without prompts"
    ),
    vcs_ref: Optional[str] = typer.Option(
        None, "--ref", help="Git tag/branch/commit for remote templates"
    ),
    subdir: Optional[str] = typer.Option(
        None, "--subdir", help="Template subdirectory"
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
    demo: bool = typer.Option(
        False,
        "--demo",
        "--no-output",
        "--test",
        help="Do not write to disk. Render to a sandbox, snapshot in-memory, and show the plan.",
    ),
    plan_json: Optional[Path] = typer.Option(
        None, "--plan-json", help="Write the demo plan as JSON to this file"
    ),
    preview_lines: int = typer.Option(
        15,
        "--preview-lines",
        min=0,
        max=200,
        help="Number of lines to preview per file in demo mode",
    ),
) -> None:
    """Generate a new Python project from a template."""
    if no_color:
        os.environ["NO_COLOR"] = "1"

    dst = Path.cwd() / name
    if template in BUILTINS:
        src = Path(__file__).parent / "copier_templates" / template
    else:
        src = template  # path or Git URL

    answers = answers_dict(name, python, package, nix, docker, just)

    if demo:
        # DEMO path: simulate generation
        with console.status("[bold blue]Simulating generation in a sandbox..."):
            snapshot = snapshot_render_to_memory(
                template_path=src,
                data=answers if non_interactive else None,
                vcs_ref=vcs_ref,
                subdirectory=subdir,
            )
            plan = plan_against_destination(snapshot, dst, force=force)

        # Show plan
        table = Table(title="Generation plan (demo mode)")
        table.add_column("Status", style="bold")
        table.add_column("Path")
        table.add_column("Size")
        table.add_column("Note", no_wrap=True)
        for item in plan:
            table.add_row(
                item["status"], item["path"], str(item["size"]), item.get("note", "")
            )
        console.print(table)

        # Previews
        if preview_lines > 0:
            console.print(
                Panel.fit(
                    f"Showing up to {preview_lines} lines per file", title="Previews"
                )
            )
            for rel, meta in sorted(snapshot.items()):
                if meta.get("type") == "text":
                    lines = meta["text"].splitlines()
                    preview = "\n".join(lines[:preview_lines])
                    console.print(Panel(preview, title=rel, border_style="cyan"))
                else:
                    console.print(
                        Panel(
                            f"<binary file> {rel} ({meta['size']} bytes)",
                            title=rel,
                            border_style="cyan",
                        )
                    )

        if plan_json:
            data = {
                "destination": str(dst),
                "template": str(src),
                "force": force,
                "plan": plan,
                # omit binary payloads from JSON for brevity
                "files": {
                    rel: {k: v for k, v in meta.items() if k != "b64"}
                    for rel, meta in snapshot.items()
                },
            }
            plan_json.parent.mkdir(parents=True, exist_ok=True)
            plan_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
            console.print(f"[green]Wrote plan JSON to[/green] {plan_json}")

        console.print(
            "[bold yellow]Demo complete. No files were written to the destination.[/bold yellow]"
        )
        return

    # NORMAL generation
    with console.status("[bold blue]Generating project..."):
        generate_from_template(
            template_path=src,
            dst_path=dst,
            data=answers if non_interactive else None,
            force=force,
            vcs_ref=vcs_ref,
            subdirectory=subdir,
        )
    console.print(
        Panel.fit(
            f"[bold green]✅ Project generated![/bold green]\n"
            f"[bold]Location:[/bold] {dst}\n"
            f"[bold]Template:[/bold] {template}\n"
            f"[bold]Answers file:[/bold] {dst / DEFAULT_ANSWERS_FILE}",
            title="🚀 Ready",
            border_style="green",
        )
    )
