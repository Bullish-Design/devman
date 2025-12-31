# tests/conftest.py
"""Shared test fixtures and configuration."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pytest

from devman.config import ProjectConfig


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
def api_config() -> ProjectConfig:
    """Create API project configuration."""
    return ProjectConfig(
        name="api-project", project_type="api", container_type="docker"
    )


@pytest.fixture
def cli_config() -> ProjectConfig:
    """Create CLI project configuration."""
    return ProjectConfig(name="cli-tool", project_type="cli", container_type="none")


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

