# tests/test_config.py
"""Test configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devman.config import ProjectConfig


class TestProjectConfig:
    """Test ProjectConfig model."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ProjectConfig(name="test-project")

        assert config.name == "test-project"
        assert config.python_version == "3.11"
        assert config.project_type == "api"
        assert config.container_type == "devenv"
        assert config.dependencies == []
        assert config.dev_dependencies == []
        assert config.local_dependencies == []
        assert config.use_database is False
        assert config.database_type == "postgresql"
        assert config.use_redis is False
        assert config.use_celery is False

    def test_computed_properties(self) -> None:
        """Test computed properties."""
        config = ProjectConfig(
            name="test", python_version="3.12", container_type="docker"
        )

        assert config.use_containers is True
        assert config.python_version_short == "312"

        config_no_containers = ProjectConfig(name="test", container_type="none")
        assert config_no_containers.use_containers is False

    def test_project_type_validation(self) -> None:
        """Test project type validation."""
        valid_types = ["api", "web", "cli", "ml", "lib"]

        for project_type in valid_types:
            config = ProjectConfig(name="test", project_type=project_type)
            assert config.project_type == project_type

        with pytest.raises(ValidationError):
            ProjectConfig(name="test", project_type="invalid")

    def test_container_type_validation(self) -> None:
        """Test container type validation."""
        valid_types = ["devenv", "docker", "nixos", "none"]

        for container_type in valid_types:
            config = ProjectConfig(name="test", container_type=container_type)
            assert config.container_type == container_type

        with pytest.raises(ValidationError):
            ProjectConfig(name="test", container_type="invalid")

    def test_database_type_validation(self) -> None:
        """Test database type validation."""
        valid_types = ["postgresql", "sqlite"]

        for db_type in valid_types:
            config = ProjectConfig(name="test", database_type=db_type)
            assert config.database_type == db_type

        with pytest.raises(ValidationError):
            ProjectConfig(name="test", database_type="invalid")

    def test_get_default_dependencies(self) -> None:
        """Test default dependencies generation."""
        # API project
        api_config = ProjectConfig(name="test", project_type="api")
        api_deps = api_config.get_default_dependencies()
        assert "fastapi>=0.104.0" in api_deps
        assert "uvicorn[standard]>=0.24.0" in api_deps

        # CLI project
        cli_config = ProjectConfig(name="test", project_type="cli")
        cli_deps = cli_config.get_default_dependencies()
        assert "typer[all]>=0.12.0" in cli_deps
        assert "rich>=13.0.0" in cli_deps

        # ML project
        ml_config = ProjectConfig(name="test", project_type="ml")
        ml_deps = ml_config.get_default_dependencies()
        assert "numpy>=1.24.0" in ml_deps
        assert "pandas>=2.0.0" in ml_deps

        # With database
        db_config = ProjectConfig(name="test", use_database=True)
        db_deps = db_config.get_default_dependencies()
        assert "sqlalchemy>=2.0.0" in db_deps
        assert "psycopg2-binary>=2.9.0" in db_deps

    def test_get_default_dev_dependencies(self) -> None:
        """Test default dev dependencies generation."""
        config = ProjectConfig(name="test", project_type="api")
        dev_deps = config.get_default_dev_dependencies()

        # Common dev deps
        assert "pytest>=7.4.0" in dev_deps
        assert "pytest-cov>=4.1.0" in dev_deps
        assert "ruff>=0.1.0" in dev_deps
        assert "mypy>=1.7.0" in dev_deps

        # API-specific dev deps
        assert "httpx>=0.25.0" in dev_deps
        assert "pytest-asyncio>=0.21.0" in dev_deps

    def test_get_template_context(self) -> None:
        """Test template context generation."""
        config = ProjectConfig(
            name="my-project",
            python_version="3.12",
            project_type="api",
            dependencies=["requests"],
            dev_dependencies=["black"],
            use_database=True,
            use_redis=True,
        )

        context = config.get_template_context()

        assert context["name"] == "my-project"
        assert context["python_version"] == "3.12"
        assert context["python_version_short"] == "312"
        assert context["project_type"] == "api"
        assert context["use_database"] is True
        assert context["use_redis"] is True

        # Check dependencies are combined
        deps = context["dependencies"]
        assert "requests" in deps
        assert "fastapi>=0.104.0" in deps  # default API dep

        dev_deps = context["dev_dependencies"]
        assert "black" in dev_deps
        assert "pytest>=7.4.0" in dev_deps  # default dev dep

