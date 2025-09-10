# tests/conftest.py
from __future__ import annotations
import pytest
import tempfile
from pathlib import Path

from devman.models import ProjectConfig
from devman.config import UserConfig


@pytest.fixture
def sample_config():
    """Sample project configuration for testing."""
    return ProjectConfig(
        project_name="test-project",
        python_version="3.11",
        use_nix=True,
        use_docker=False,
        use_just=True,
    )


@pytest.fixture
def sample_user_config():
    """Sample user configuration for testing."""
    return UserConfig(
        default_python_version="3.11",
        default_template="python-lib",
        author_name="Test User",
        author_email="test@example.com",
        use_nix=True,
        use_docker=False,
        use_just=True,
    )


@pytest.fixture
def minimal_copier_template(tmp_path):
    """Create a minimal but valid Copier template for testing."""
    template_dir = tmp_path / "minimal-template"
    template_dir.mkdir()

    # Create copier.yml - this is the key fix
    copier_config = """_templates_suffix: .j2

project_name:
  type: str
  help: What is your project name?

project_slug:
  type: str
  default: "{{ project_name|lower|replace(' ', '-') }}"

package_name:
  type: str
  default: "{{ project_slug|replace('-', '_') }}"

python_version:
  type: str
  default: "3.11"

use_nix:
  type: bool
  default: true

use_docker:
  type: bool
  default: true

use_just:
  type: bool
  default: true
"""
    (template_dir / "copier.yml").write_text(copier_config)

    # Create template files
    (template_dir / "README.md.j2").write_text("""
# {{ project_name }}

{{ project_name }} is a Python project.

## Installation

```bash
uv add {{ project_slug }}
```

## Usage

```python
import {{ package_name }}
```

## Development

This project uses Python {{ python_version }}.

{% if use_just -%}
Use `just` to run common tasks:

```bash
just test
just lint
just fmt
```
{% endif %}
""")

    # Create pyproject.toml template
    (template_dir / "pyproject.toml.j2").write_text("""
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{ project_slug }}"
version = "0.1.0"
description = "{{ project_name }}"
requires-python = ">={{ python_version }}"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "ruff>=0.1",
    "mypy>=1.7",
]

[tool.ruff]
line-length = 120
target-version = "py{{ python_version.replace('.', '') }}"

[tool.mypy]
python_version = "{{ python_version }}"
strict = true
""")

    # Create package structure
    src_dir = template_dir / "src" / "{{ package_name }}"
    src_dir.mkdir(parents=True)

    (src_dir / "__init__.py.j2").write_text("""
\"\"\"{{ project_name }} package.\"\"\"

__version__ = "0.1.0"

def hello(name: str = "world") -> str:
    \"\"\"Say hello to someone.\"\"\"
    return f"Hello, {name}!"
""")

    # Create tests directory
    tests_dir = template_dir / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_{{ package_name }}.py.j2").write_text("""
from {{ package_name }} import hello


def test_hello_default():
    assert hello() == "Hello, world!"


def test_hello_custom():
    assert hello("Python") == "Hello, Python!"
""")

    # Create conditional files
    if True:  # Always create these for testing
        (template_dir / "{% if use_just %}justfile{% endif %}.j2").write_text("""
# Justfile for {{ project_name }}

default: test

# Run tests
test:
    uv run pytest

# Format code
fmt:
    uv run ruff format .

# Lint code
lint:
    uv run ruff check .

# Type check
check:
    uv run mypy src

# Install dependencies
install:
    uv sync

# Clean up
clean:
    rm -rf .pytest_cache
    rm -rf __pycache__
    find . -name "*.pyc" -delete
""")

        (template_dir / "{% if use_docker %}Dockerfile{% endif %}.j2").write_text("""
FROM python:{{ python_version }}-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml ./
COPY src ./src

# Install dependencies
RUN uv sync

# Run tests by default
CMD ["uv", "run", "pytest"]
""")

        (template_dir / "{% if use_nix %}flake.nix{% endif %}.j2").write_text("""
{
  description = "{{ project_name }} development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python{{ python_version.replace('.', '') }};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            uv
            python
            ruff
            mypy
            {% if use_just %}just{% endif %}
          ];
          
          shellHook = ''
            echo "🐍 {{ project_name }} development environment"
            echo "📦 Python {{ python_version }} with UV"
          '';
        };
      }
    );
}
""")

    return template_dir


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary directory for project generation."""
    project_dir = tmp_path / "generated-project"
    return project_dir


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Isolate configuration to a temporary directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Override environment variables to use temp directory
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    monkeypatch.setenv("HOME", str(tmp_path))

    # Clear any existing DEVMAN_CONFIG override
    monkeypatch.delenv("DEVMAN_CONFIG", raising=False)

    return config_dir


class TestHelper:
    """Helper class for common test operations."""

    @staticmethod
    def create_copier_template(path: Path, name: str = "test-template") -> Path:
        """Create a minimal copier template at the given path."""
        template_dir = path / name
        template_dir.mkdir(parents=True, exist_ok=True)

        # Minimal copier.yml
        (template_dir / "copier.yml").write_text("""
project_name:
  type: str
  help: Project name
""")

        # Minimal template file
        (template_dir / "README.md.j2").write_text("# {{ project_name }}")

        return template_dir

    @staticmethod
    def assert_file_contains(file_path: Path, content: str, message: str = ""):
        """Assert that a file contains specific content."""
        assert file_path.exists(), f"File {file_path} does not exist"
        file_content = file_path.read_text()
        assert content in file_content, f"{message}: '{content}' not found in {file_path}"

    @staticmethod
    def assert_file_not_contains(file_path: Path, content: str, message: str = ""):
        """Assert that a file does not contain specific content."""
        if file_path.exists():
            file_content = file_path.read_text()
            assert content not in file_content, f"{message}: '{content}' found in {file_path}"


@pytest.fixture
def test_helper():
    """Provide test helper utilities."""
    return TestHelper

