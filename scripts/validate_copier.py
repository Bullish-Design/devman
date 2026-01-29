#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pydantic>=2.0.0",
#     "pyyaml>=6.0.0",
# ]
# ///

# scripts/validate_copier.py
"""Standalone UV script to validate copier.yaml files."""

from __future__ import annotations

import sys
from pathlib import Path

# Import from local devman package if available, otherwise inline minimal validator
try:
    from devman.schemas import CopierConfig
    from devman.templates import TemplateValidator

    def validate_template(template_path: Path) -> int:
        """Validate a copier template using devman schemas."""
        issues = TemplateValidator.validate_structure(template_path)

        if issues["warnings"]:
            print("Warnings:")
            for warning in issues["warnings"]:
                print(f"  Warning: {warning}")

        if issues["errors"]:
            print("Errors:")
            for error in issues["errors"]:
                print(f"  Error: {error}")
            return 1

        print(f"Template at {template_path} is valid")
        return 0

except ImportError:
    import yaml

    def validate_template(template_path: Path) -> int:
        """Minimal inline validator when devman is not installed."""
        yaml_files = list(template_path.glob("copier.y*ml"))

        if not yaml_files:
            print(f"No copier.yaml found in {template_path}")
            return 1

        try:
            content = yaml.safe_load(yaml_files[0].read_text())

            # Basic structural checks
            questions = {k: v for k, v in content.items() if not k.startswith("_")}

            for name, spec in questions.items():
                if not isinstance(spec, dict):
                    print(f"Question '{name}' is not a dictionary")
                    return 1

                if "type" not in spec:
                    print(f"Question '{name}' missing 'type' field")
                    return 1

            print(f"Template at {template_path} is valid (basic checks)")
            return 0

        except Exception as e:
            print(f"Failed to parse copier.yaml: {e}")
            return 1


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_copier.py <template_directory>")
        return 1

    template_path = Path(sys.argv[1]).expanduser().resolve()

    if not template_path.exists():
        print(f"Template path does not exist: {template_path}")
        return 1

    if not template_path.is_dir():
        print(f"Template path is not a directory: {template_path}")
        return 1

    return validate_template(template_path)


if __name__ == "__main__":
    sys.exit(main())
