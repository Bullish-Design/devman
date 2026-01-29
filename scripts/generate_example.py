#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pydantic>=2.0.0",
#     "pyyaml>=6.0.0",
# ]
# ///

# scripts/generate_example.py
"""Generate an example copier.yaml file with common patterns."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from devman.schemas import CopierConfig

    def generate_example() -> str:
        """Generate example using CopierConfig model."""
        config = CopierConfig(
            subdirectory="template",
            templates_suffix=".jinja",
            skip_if_exists=["README.md", ".gitignore"],
            questions={
                "project_name": {
                    "type": "str",
                    "help": "What is your project name?",
                    "validator": r"^[a-z][a-z0-9_-]*$",
                },
                "project_description": {
                    "type": "str",
                    "help": "Brief description of your project",
                    "default": "A new project",
                },
                "author_name": {
                    "type": "str",
                    "help": "Author name",
                },
                "author_email": {
                    "type": "str",
                    "help": "Author email",
                    "validator": r"^[\w\.-]+@[\w\.-]+\.\w+$",
                },
                "python_version": {
                    "type": "str",
                    "help": "Python version",
                    "default": "3.13",
                    "choices": ["3.11", "3.12", "3.13"],
                },
                "use_docker": {
                    "type": "bool",
                    "help": "Include Docker configuration?",
                    "default": False,
                },
                "use_ci": {
                    "type": "bool",
                    "help": "Include CI/CD configuration?",
                    "default": True,
                },
                "ci_provider": {
                    "type": "str",
                    "help": "Which CI provider?",
                    "choices": {
                        "github": "GitHub Actions",
                        "gitlab": "GitLab CI",
                        "none": "No CI",
                    },
                    "default": "github",
                    "when": "{{ use_ci }}",
                },
            },
            tasks=[
                "git init",
                {"command": "docker compose build", "when": "{{ use_docker }}"},
                "echo 'Project {{ project_name }} created successfully!'",
            ],
        )

        # Write to temporary file and read back as string
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config.to_yaml_file(Path(f.name))
            return Path(f.name).read_text()

except ImportError:
    import yaml

    def generate_example() -> str:
        """Generate example without devman package."""
        example = {
            "_subdirectory": "template",
            "_templates_suffix": ".jinja",
            "_skip_if_exists": ["README.md", ".gitignore"],
            "project_name": {
                "type": "str",
                "help": "What is your project name?",
                "validator": r"^[a-z][a-z0-9_-]*$",
            },
            "python_version": {
                "type": "str",
                "help": "Python version",
                "default": "3.13",
                "choices": ["3.11", "3.12", "3.13"],
            },
            "use_docker": {
                "type": "bool",
                "help": "Include Docker configuration?",
                "default": False,
            },
            "_tasks": [
                "git init",
                "echo 'Done!'",
            ],
        }

        return yaml.dump(example, sort_keys=False)


def main() -> int:
    output = generate_example()

    if len(sys.argv) > 1:
        output_file = Path(sys.argv[1])
        output_file.write_text(output)
        print(f"Generated example copier.yaml at {output_file}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
