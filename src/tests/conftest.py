# tests/conftest.py
"""Shared test fixtures and configuration."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pytest

from devman.config import ProjectConfig
from devman.devman_config import DevmanConfig
from devman.templates import TemplateRegistry


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create temporary directory for tests."""
    with TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config() -> ProjectConfig:
    """Create sample project configuration."""
    return ProjectConfig(
        name="test-project",
        python_version="3.11",
        project_type="api",
        container_type="devenv",
        dependencies=["requests>=2.28.0"],
        dev_dependencies=["black>=22.0.0"],
        local_dependencies=["../my-lib"],
        use_database=True,
        database_type="postgresql",
        use_redis=True,
        use_celery=False,
    )


@pytest.fixture
def sample_devman_config(sample_config: ProjectConfig) -> DevmanConfig:
    """Create sample DevmanConfig."""
    return DevmanConfig.create_from_project_config(sample_config)


@pytest.fixture
def api_config() -> ProjectConfig:
    """Create API project configuration."""
    return ProjectConfig(
        name="api-project", project_type="api", container_type="docker"
    )


@pytest.fixture
def api_devman_config(api_config: ProjectConfig) -> DevmanConfig:
    """Create API DevmanConfig."""
    return DevmanConfig.create_from_project_config(api_config)


@pytest.fixture
def cli_config() -> ProjectConfig:
    """Create CLI project configuration."""
    return ProjectConfig(name="cli-tool", project_type="cli", container_type="none")


@pytest.fixture
def cli_devman_config(cli_config: ProjectConfig) -> DevmanConfig:
    """Create CLI DevmanConfig."""
    return DevmanConfig.create_from_project_config(cli_config)


@pytest.fixture
def ml_config() -> ProjectConfig:
    """Create ML project configuration."""
    return ProjectConfig(
        name="ml-project",
        project_type="ml",
        python_version="3.12",
        use_database=True,
        database_type="sqlite",
    )


@pytest.fixture
def ml_devman_config(ml_config: ProjectConfig) -> DevmanConfig:
    """Create ML DevmanConfig."""
    return DevmanConfig.create_from_project_config(ml_config)


@pytest.fixture
def sample_templates() -> dict[str, str]:
    """Sample templates for testing."""
    return {
        "test.j2": "Hello {{ name }}! Type: {{ project_type }}",
        "conditional.j2": """
{%- if use_database -%}
Database: {{ database_type }}
{%- endif -%}
""".strip(),
        "loop.j2": """
dependencies = [
{%- for dep in dependencies %}
    "{{ dep }}",
{%- endfor %}
]
""".strip(),
        "devenv.nix.j2": """
{ pkgs, ... }: {
  name = "{{ name }}";
  languages.python.version = "{{ python_version }}";
}
""".strip(),
        "pyproject.toml.j2": """
[project]
name = "{{ name }}"
dependencies = [
{%- for dep in dependencies %}
    "{{ dep }}",
{%- endfor %}
]
""".strip(),
    }


@pytest.fixture
def mock_registry(sample_templates: dict[str, str]) -> TemplateRegistry:
    """Create mock template registry with sample templates."""
    registry = TemplateRegistry(templates={})
    for name, content in sample_templates.items():
        registry.add_template(name, content)
    return registry


@pytest.fixture
def templates_dir(temp_dir: Path, sample_templates: dict[str, str]) -> Path:
    """Create temporary templates directory with sample files."""
    templates_path = temp_dir / "templates"
    templates_path.mkdir()

    for name, content in sample_templates.items():
        (templates_path / name).write_text(content)

    return templates_path


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create temporary project directory with structure."""
    project_path = temp_dir / "test-project"
    project_path.mkdir()

    # Create basic structure
    (project_path / "src" / "test-project").mkdir(parents=True)
    (project_path / "tests").mkdir()

    # Create files
    (project_path / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
version = "0.1.0"
""".strip()
    )

    (project_path / "src" / "test-project" / "__init__.py").touch()
    (project_path / "tests" / "__init__.py").touch()

    return project_path


@pytest.fixture
def devman_project_dir(temp_dir: Path, sample_devman_config: DevmanConfig) -> Path:
    """Create temporary project directory with devman.toml."""
    project_path = temp_dir / "devman-project"
    project_path.mkdir()

    # Create devman config
    devman_dir = project_path / ".devman"
    devman_dir.mkdir()

    # Save config to proper location
    sample_devman_config.save(devman_dir / "devman.toml")

    return project_path


@pytest.fixture
def sample_toml_content() -> str:
    """Sample TOML content for testing."""
    return """
[devman]
version = "0.2.0"
created_at = "2025-01-15T10:30:00"
updated_at = "2025-01-15T10:30:00"

[project]
name = "test-project"
python_version = "3.11"
project_type = "api"
container_type = "devenv"
dependencies = ["fastapi>=0.104.0"]
dev_dependencies = ["pytest>=7.4.0"]
local_dependencies = []
use_database = false
database_type = "postgresql"
use_redis = false
use_celery = false

[templates]
files = ["devenv.nix.j2", "justfile.j2"]

[generation]
generated_files = []
"""


@pytest.fixture(autouse=True)
def clean_test_environment() -> Iterator[None]:
    """Ensure clean test environment for each test."""
    # Store original working directory
    original_cwd = Path.cwd()

    yield

    # Clean up any test artifacts and restore original directory
    os.chdir(original_cwd)

    # Remove any test .devman directories that might have been created
    for potential_devman in Path.cwd().rglob(".devman"):
        if potential_devman.is_dir():
            import shutil

            shutil.rmtree(potential_devman, ignore_errors=True)


def reset_global_registry() -> Iterator[None]:
    """Reset global template registry after each test."""
    from devman.templates import TEMPLATE_REGISTRY

    # Store original state
    original_templates = TEMPLATE_REGISTRY.templates.copy()

    yield

    # Restore original state
    TEMPLATE_REGISTRY.templates.clear()
    TEMPLATE_REGISTRY.templates.update(original_templates)
    TEMPLATE_REGISTRY._setup_environment()
