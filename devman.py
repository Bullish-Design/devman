#!/usr/bin/env python3
"""DevMan CLI for managing local development environments."""

from __future__ import annotations

import datetime
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml

app = typer.Typer(help="DevMan CLI for managing local development environments.")


def get_jj_info() -> dict[str, Optional[str]]:
    """Return current jj bookmark and change id info."""
    def run_jj(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["jj", *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None

    bookmark = None
    bookmark_result = run_jj(["bookmark", "list", "-r", "@", "--color=never"])
    if bookmark_result and bookmark_result.returncode == 0:
        lines = [line.strip() for line in bookmark_result.stdout.splitlines() if line.strip()]
        if lines:
            bookmark = lines[0].split(":", maxsplit=1)[0].strip() or None

    change_id = None
    change_result = run_jj(["log", "-r", "@", "-T", "change_id.short()"])
    if change_result and change_result.returncode == 0:
        change_id = change_result.stdout.strip() or None

    return {"bookmark": bookmark, "change_id": change_id}


def resolve_template_path(template: str, script_dir: Path) -> Path:
    """Resolve the copier template path from a name or filesystem path."""
    if "/" in template or template.startswith("."):
        template_path = Path(template).expanduser()
        if template_path.exists():
            return template_path.resolve()
        raise ValueError(f"Template path '{template}' does not exist.")

    bundled_template = script_dir / "templates" / template
    if bundled_template.exists():
        return bundled_template.resolve()

    raise ValueError(
        "Unknown template. Provide a filesystem path like "
        f"./templates/{template}."
    )


def format_data_payload(data: dict[str, object]) -> str:
    def format_value(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return "\n".join(f"{key}={format_value(value)}" for key, value in data.items())


def validate_template_pretend(template_path: Path, dest: Path, data: dict[str, object]) -> None:
    """Run copier in pretend mode to check template."""
    result = subprocess.run(
        [
            "copier",
            "copy",
            "--pretend",
            "--data-file",
            "-",
            "--defaults",
            str(template_path),
            str(dest),
        ],
        input=format_data_payload(data),
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise ValueError(f"Template validation failed: {result.stderr}")


def validate_nix_syntax(devenv_file: Path) -> None:
    """Validate devenv.nix syntax using nix-instantiate."""
    result = subprocess.run(
        ["nix-instantiate", "--parse", str(devenv_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise ValueError(f"Invalid Nix syntax: {result.stderr}")


def create_state_file(devman_dir: Path, template_source: str | Path, data: dict[str, object]) -> None:
    """Create state.yaml with template metadata."""
    jj_info = get_jj_info()
    branch = jj_info.get("bookmark")
    revision = jj_info.get("change_id")

    timestamp = datetime.datetime.now().isoformat()
    state = {
        "template": {
            "name": data["project_name"],
            "source": str(template_source),
            "version": revision,
            "applied_at": timestamp,
        },
        "variables": data,
        "history": [
            {
                "timestamp": timestamp,
                "action": "init",
                "template": data["project_name"],
                "source": str(template_source),
                "jj_branch": branch,
                "jj_revision": revision,
            }
        ],
    }

    state_file = devman_dir / "state.yaml"
    with open(state_file, "w") as file:
        yaml.dump(state, file, default_flow_style=False)


@app.command()
def init(
    devman_dir: Path = typer.Option(
        Path("devman"),
        "--devman-dir",
        "-d",
        help="Directory where the DevMan project should be created.",
    ),
    template: str = typer.Option(
        "python-devenv",
        "--template",
        "-t",
        help="Copier template name or path.",
    ),
    python_version: str = typer.Option(
        "3.12",
        "--python-version",
        help="Python version to configure in the project.",
    ),
    project_name: Optional[str] = typer.Option(
        None,
        "--project-name",
        help="Project name to use in the generated files.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files if they already exist.",
    ),
) -> None:
    """Initialize a new DevMan project using a Copier template."""
    if devman_dir.exists() and not force:
        typer.echo(
            f"Error: '{devman_dir}' already exists. Use --force to overwrite.",
            err=True,
        )
        raise typer.Exit(1)

    script_dir = Path(__file__).resolve().parent
    try:
        template_path = resolve_template_path(template, script_dir)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if not project_name:
        project_name = Path.cwd().name

    data = {
        "project_name": project_name,
        "python_version": python_version,
        "include_postgres": False,
        "include_redis": False,
    }

    devman_dir.mkdir(parents=True, exist_ok=True)

    try:
        typer.echo("Validating template...")
        validate_template_pretend(template_path, devman_dir, data)

        typer.echo("Generating files...")
        result = subprocess.run(
            [
                "copier",
                "copy",
                "--data-file",
                "-",
                "--defaults",
                str(template_path),
                str(devman_dir),
            ],
            input=format_data_payload(data),
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            raise ValueError(f"Copier failed: {result.stderr}")

        typer.echo("Validating generated devenv.nix...")
        validate_nix_syntax(devman_dir / "devenv.nix")

        typer.echo("Creating state file...")
        create_state_file(devman_dir, template_path, data)

        typer.echo("DevMan project initialized.")
        typer.echo(f"Template: {template_path}")
        typer.echo(f"Project: {project_name}")
        typer.echo(f"Python: {python_version}")
    except Exception as exc:
        if devman_dir.exists():
            shutil.rmtree(devman_dir, ignore_errors=True)
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command()
def validate(
    devman_dir: Path = typer.Option(
        Path(".devman"),
        help="Path to .devman directory",
    ),
) -> None:
    """Validate the current DevMan project configuration."""
    if not devman_dir.exists():
        typer.echo(f"Error: '{devman_dir}' does not exist.", err=True)
        raise typer.Exit(1)

    errors: list[str] = []
    required_files = ["devenv.nix", "justfile", "state.yaml"]
    for file_name in required_files:
        file_path = devman_dir / file_name
        if not file_path.exists():
            errors.append(f"Missing required file: {file_path}")

    devenv_path = devman_dir / "devenv.nix"
    if devenv_path.exists():
        try:
            validate_nix_syntax(devenv_path)
            typer.echo("devenv.nix syntax is valid.")
        except ValueError as exc:
            errors.append(str(exc))

    state_path = devman_dir / "state.yaml"
    if state_path.exists():
        try:
            state_data = yaml.safe_load(state_path.read_text())
        except yaml.YAMLError as exc:
            errors.append(f"Invalid YAML in {state_path}: {exc}")
        else:
            if not isinstance(state_data, dict):
                errors.append(f"{state_path} must contain a mapping at the root.")
            else:
                missing_keys = [
                    key for key in ("template", "variables") if key not in state_data
                ]
                if missing_keys:
                    errors.append(
                        f"{state_path} is missing keys: {', '.join(missing_keys)}"
                    )
                else:
                    typer.echo("state.yaml contains required keys.")

    if errors:
        typer.echo("Validation failed:")
        for error in errors:
            typer.echo(f"- {error}")
        raise typer.Exit(1)

    typer.echo("Validation successful.")


@app.command()
def test(
    container_prefix: str = typer.Option(
        "devman-test",
        "--container-prefix",
        "-p",
        help="Prefix to use when naming the test container.",
    ),
    reuse: bool = typer.Option(
        False,
        "--reuse",
        "-r",
        help="Reuse an existing test container if available.",
    ),
) -> None:
    """Run the DevMan test container for the current repository."""
    jj_info = get_jj_info()
    suffix = jj_info.get("bookmark") or jj_info.get("change_id") or "unknown"
    container_name = f"{container_prefix}-{suffix}"
    typer.echo("Test command (skeleton)")
    typer.echo(f"Container: {container_name}")
    typer.echo(f"Reuse: {reuse}")


@app.command()
def clean(
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Remove all generated artifacts, including caches.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be removed without deleting anything.",
    ),
) -> None:
    """Remove DevMan-generated artifacts from the working tree."""
    typer.echo("Clean command (skeleton)")
    typer.echo(f"All: {all}")
    typer.echo(f"Dry run: {dry_run}")


if __name__ == "__main__":
    app()
