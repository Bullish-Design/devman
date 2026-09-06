"""Probe Templateer's raw Python source boundary without changing Templateer."""

from __future__ import annotations

import argparse
import ast
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from pydantic import ValidationError
from templateer.api import TemplateRegistry

VALID_FRAGMENT = """def answer() -> int:
    return 42
"""

INJECTION_LABEL = 'safe"\nINJECTED = True\n#'

FRAGMENT_SCHEMA = '''\
"""Probe schema with a validated Python source-fragment field."""

import ast
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def validate_python_fragment(value: str) -> str:
    """Require one syntactically valid Python module fragment."""

    try:
        ast.parse(value)
    except SyntaxError as error:
        raise ValueError(
            f"invalid Python fragment at {error.lineno}:{error.offset}: {error.msg}"
        ) from error
    return value


PythonFragment = Annotated[str, AfterValidator(validate_python_fragment)]


class PythonModuleModel(BaseModel):
    """Ordered validated Python module fragments."""

    model_config = ConfigDict(extra="forbid")

    sections: list[PythonFragment]
'''

MIXED_SCHEMA = '''\
"""Unsafe comparison schema with source and ordinary strings."""

from pydantic import BaseModel, ConfigDict


class MixedModel(BaseModel):
    """Mix source and ordinary data under identity escaping."""

    model_config = ConfigDict(extra="forbid")

    label: str
    section: str
'''


def _write_template(
    root: Path,
    *,
    name: str,
    language: str,
    schema_source: str,
    class_name: str,
    template_source: str,
    parse_python: bool = False,
) -> None:
    target = root / name
    target.mkdir(parents=True)
    validators = ""
    if parse_python:
        validators = "\nvalidators:\n  - kind: parse\n    language: python\n"
    metadata = f"""\
name: {name}
description: Local raw Python boundary probe.

output:
  path: module.py
  language: {language}

schema:
  module: schema
  class: {class_name}

prompt:
  file: prompt.md

renderer:
  engine: minijinja
  file: template.j2
{validators}
"""
    (target / "metadata.yml").write_text(metadata, encoding="utf-8")
    (target / "schema.py").write_text(schema_source, encoding="utf-8")
    (target / "prompt.md").write_text("Render the validated input.\n", encoding="utf-8")
    (target / "template.j2").write_text(template_source, encoding="utf-8")


def _ruff_format(source: str) -> str:
    result = subprocess.run(
        ["ruff", "format", "--stdin-filename", "module.py", "-"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def run_probe(artifacts: Path) -> dict[str, object]:
    """Run all boundary comparisons and return structured observations."""

    if artifacts.exists() and any(artifacts.iterdir()):
        raise ValueError(f"artifact directory is not fresh: {artifacts}")
    artifacts.mkdir(parents=True, exist_ok=True)
    templates = artifacts / "templates"

    _write_template(
        templates,
        name="python-current",
        language="python",
        schema_source=FRAGMENT_SCHEMA,
        class_name="PythonModuleModel",
        template_source='{{ sections | join("\\n\\n") }}',
    )
    _write_template(
        templates,
        name="text-validated",
        language="text",
        schema_source=FRAGMENT_SCHEMA,
        class_name="PythonModuleModel",
        template_source='{{ sections | join("\\n\\n") }}',
        parse_python=True,
    )
    _write_template(
        templates,
        name="text-mixed-unsafe",
        language="text",
        schema_source=MIXED_SCHEMA,
        class_name="MixedModel",
        template_source='LABEL = "{{ label }}"\n\n{{ section }}',
        parse_python=True,
    )

    registry = TemplateRegistry.from_paths([templates])
    model_data = {"sections": [VALID_FRAGMENT]}

    python_rendered = registry.render_from_model("python-current", model_data)
    try:
        ast.parse(python_rendered)
        python_parse_error = None
    except SyntaxError as error:
        python_parse_error = f"{error.msg} at {error.lineno}:{error.offset}"

    text_rendered = registry.render_from_model("text-validated", model_data)
    text_errors, text_warnings = registry.validate_artifact(
        "text-validated", text_rendered, model_data=model_data
    )
    text_repeat = registry.render_from_model("text-validated", model_data)
    text_formatted = _ruff_format(text_rendered)

    invalid_rejected = False
    invalid_detail = ""
    try:
        registry.render_from_model("text-validated", {"sections": ["def broken("]})
    except ValidationError as error:
        invalid_rejected = True
        invalid_detail = str(error)

    mixed_data = {"label": INJECTION_LABEL, "section": VALID_FRAGMENT}
    mixed_rendered = registry.render_from_model("text-mixed-unsafe", mixed_data)
    mixed_errors, _ = registry.validate_artifact(
        "text-mixed-unsafe", mixed_rendered, model_data=mixed_data
    )
    mixed_tree = ast.parse(mixed_rendered)
    assigned_names = sorted(
        node.targets[0].id
        for node in mixed_tree.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    )

    outside_rendered = "\n\n".join(model_data["sections"])
    ast.parse(outside_rendered)

    results: dict[str, object] = {
        "current_python": {
            "preserves_fragment": python_rendered == VALID_FRAGMENT,
            "parse_error": python_parse_error,
            "rendered_repr": repr(python_rendered),
        },
        "text_plus_validation": {
            "preserves_fragment": text_rendered == VALID_FRAGMENT,
            "parse_errors": text_errors,
            "warnings": text_warnings,
            "deterministic_repeat": text_repeat == text_rendered,
            "ruff_idempotent": _ruff_format(text_formatted) == text_formatted,
            "invalid_fragment_rejected_before_render": invalid_rejected,
            "invalid_detail": invalid_detail,
        },
        "text_mixed_counterexample": {
            "artifact_parse_errors": mixed_errors,
            "assigned_names": assigned_names,
            "ordinary_string_changed_structure": "INJECTED" in assigned_names,
            "rendered_repr": repr(mixed_rendered),
        },
        "outside_renderer": {
            "preserves_fragment": outside_rendered == VALID_FRAGMENT,
            "syntax_valid": True,
        },
    }

    passed = (
        python_parse_error is not None
        and python_rendered != VALID_FRAGMENT
        and text_rendered == VALID_FRAGMENT
        and not text_errors
        and not text_warnings
        and text_repeat == text_rendered
        and invalid_rejected
        and "INJECTED" in assigned_names
        and not mixed_errors
        and outside_rendered == VALID_FRAGMENT
    )
    results["probe_passed"] = passed

    (artifacts / "current-python-rendered.txt").write_text(
        python_rendered, encoding="utf-8"
    )
    (artifacts / "text-validated-rendered.py").write_text(
        text_rendered, encoding="utf-8"
    )
    (artifacts / "text-mixed-rendered.py").write_text(mixed_rendered, encoding="utf-8")
    (artifacts / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (artifacts / "environment.json").write_text(
        json.dumps(
            {
                "command": " ".join(sys.argv),
                "python": platform.python_version(),
                "templateer": version("templateer"),
                "pydantic": version("pydantic"),
                "ruff": subprocess.run(
                    ["ruff", "--version"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    try:
        results = run_probe(args.artifacts)
    except Exception as error:
        args.artifacts.mkdir(parents=True, exist_ok=True)
        (args.artifacts / "failure.txt").write_text(
            f"status=failed\nerror_type={type(error).__name__}\nerror={error}\n",
            encoding="utf-8",
        )
        raise
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if results["probe_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
