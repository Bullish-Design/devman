#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import typer
import yaml

app = typer.Typer(help="Validate config files against .example templates.")


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def _parse_env_example(lines: Iterable[str]) -> Tuple[List[str], List[str]]:
    required: List[str] = []
    optional: List[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        target = optional if stripped.startswith("#") else required
        line = stripped.lstrip("#").strip()
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        target.append(key)
    return required, optional


def _parse_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _parse_toml_example(lines: Iterable[str]) -> Tuple[List[str], List[str]]:
    required: List[str] = []
    optional: List[str] = []
    current_table: List[str] = []
    table_pattern = re.compile(r"^\s*\[(.+)]\s*$")
    for raw in lines:
        if not raw.strip():
            continue
        is_optional = raw.strip().startswith("#")
        line = raw.lstrip("#")
        table_match = table_pattern.match(line.strip())
        if table_match:
            current_table = table_match.group(1).split(".")
            continue
        content = _strip_comment(line)
        if "=" not in content:
            continue
        key = content.split("=", 1)[0].strip()
        full_key = ".".join([*current_table, key]) if current_table else key
        (optional if is_optional else required).append(full_key)
    return required, optional


def _flatten_dict(data: dict, prefix: str = "") -> List[str]:
    keys: List[str] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            keys.extend(_flatten_dict(value, full_key))
        else:
            keys.append(full_key)
    return keys


def _parse_yaml_example(lines: Iterable[str]) -> Tuple[List[str], List[str]]:
    required: List[str] = []
    optional: List[str] = []
    stack: List[Tuple[int, str]] = []
    for raw in lines:
        if not raw.strip():
            continue
        is_optional = raw.lstrip().startswith("#")
        line = raw.lstrip("#")
        content = _strip_comment(line)
        if ":" not in content:
            continue
        indent = len(line) - len(line.lstrip(" "))
        key = content.split(":", 1)[0].strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        path = ".".join([item[1] for item in stack])
        (optional if is_optional else required).append(path)
    return required, optional


def _detect_format(example_path: Path) -> str:
    name = example_path.name
    if name.endswith(".env.example") or name.endswith(".env"):
        return "env"
    if name.endswith(".toml.example") or name.endswith(".toml"):
        return "toml"
    if name.endswith(".yaml.example") or name.endswith(".yml.example"):
        return "yaml"
    if name.endswith(".yaml") or name.endswith(".yml"):
        return "yaml"
    raise typer.BadParameter("Unsupported example file format.")


@app.command()
def validate(
    example: Path = typer.Argument(..., help="Path to the .example file."),
    target: Path | None = typer.Option(
        None, "--target", "-t", help="Target config file to validate."
    ),
) -> None:
    """Validate config file values against an example template."""
    if not example.exists():
        raise typer.BadParameter("Example file does not exist.")

    format_kind = _detect_format(example)
    lines = example.read_text().splitlines()

    if format_kind == "env":
        required, optional = _parse_env_example(lines)
        target_path = target or example.with_suffix("")
        if not target_path.exists():
            raise typer.BadParameter(f"Target file {target_path} does not exist.")
        data_keys = list(_parse_env_file(target_path).keys())
    elif format_kind == "toml":
        required, optional = _parse_toml_example(lines)
        target_path = target or example.with_suffix("")
        if not target_path.exists():
            raise typer.BadParameter(f"Target file {target_path} does not exist.")
        import tomllib

        data_keys = _flatten_dict(tomllib.loads(target_path.read_text()))
    else:
        required, optional = _parse_yaml_example(lines)
        target_path = target or example.with_suffix("")
        if not target_path.exists():
            raise typer.BadParameter(f"Target file {target_path} does not exist.")
        data = yaml.safe_load(target_path.read_text()) or {}
        data_keys = _flatten_dict(data)

    required_set = set(required)
    optional_set = set(optional)
    allowed = required_set | optional_set
    present = set(data_keys)

    missing = sorted(required_set - present)
    extra = sorted(present - allowed)

    if missing:
        typer.echo("Missing required keys:")
        for key in missing:
            typer.echo(f" - {key}")
        raise typer.Exit(code=1)

    if extra:
        typer.echo("Unexpected keys:")
        for key in extra:
            typer.echo(f" - {key}")
        raise typer.Exit(code=1)

    typer.echo("Config validation passed.")


if __name__ == "__main__":
    app()
