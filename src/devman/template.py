# src/devman/template.py
"""Template operations."""

from __future__ import annotations

import subprocess
from pathlib import Path


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
        f"Unknown template '{template}'. Provide a filesystem path like "
        f"./templates/{template}."
    )


def format_data_payload(data: dict[str, object]) -> str:
    """Format data dict into copier data-file format."""

    def format_value(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    return "\n".join(f"{key}={format_value(value)}" for key, value in data.items())


def run_copier(template_path: Path, dest: Path, data: dict[str, object]) -> None:
    """Run copier to generate files from template."""
    result = subprocess.run(
        [
            "copier",
            "copy",
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
        raise ValueError(f"Copier failed: {result.stderr}")
