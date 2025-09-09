# tests/test_devman_config.py
"""Test DevmanConfig TOML functionality."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from devman.config import ProjectConfig
from devman.devman_config import DevmanConfig, DevmanMetadata, TemplateConfig


class TestDevmanMetadata:
    """Test DevmanMetadata model."""

    def test_default_values(self) -> None:
        """Test default metadata values."""
        metadata = DevmanMetadata()

        assert metadata.version == "0.2.0"
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.updated_at, datetime)

    def test_custom_values(self) -> None:
        """Test custom metadata values."""
        created = datetime(2025, 1, 15, 10, 30)
        updated = datetime(2025, 1, 15, 11, 30)

        metadata = DevmanMetadata(
            version="0.1.0", created_at=created, updated_at=updated
        )

        assert metadata.version == "0.1.0"
        assert metadata.created_at == created
        assert metadata.updated_at == updated


class TestTemplateConfig:
    """Test TemplateConfig model."""

    def test_default_values(self) -> None:
        """Test default template config."""
        config = TemplateConfig()

        assert config.files == []
        assert config.custom_templates_dir is None

    def test_get_default_files_api(self) -> None:
        """Test default files for API project."""
        config = TemplateConfig()
        files = config.get_default_files("api", "devenv")

        expected = ["devenv.nix.j2", "justfile.j2", "pyproject.toml.j2", ".envrc.j2"]
        assert files == expected

    def test_get_default_files_docker(self) -> None:
        """Test default files for Docker container."""
        config = TemplateConfig()
        files = config.get_default_files("api", "docker")

        assert "Dockerfile.j2" in files
        assert "docker-compose.yml.j2" in files

    def test_get_default_files_nixos(self) -> None:
        """Test default files for NixOS container."""
        config = TemplateConfig()
        files = config.get_default_files("cli", "nixos")

        assert "container.nix.j2" in files


class TestDevmanConfig:
    """Test DevmanConfig model."""

    def test_create_from_project_config(self) -> None:
        """Test creating DevmanConfig from ProjectConfig."""
        project_config = ProjectConfig(
            name="test-project", project_type="api", container_type="docker"
        )

        devman_config = DevmanConfig.create_from_project_config(project_config)

        assert devman_config.project == project_config
        assert len(devman_config.templates.files) > 0
        assert "Dockerfile.j2" in devman_config.templates.files

    def test_ensure_templates_list(self) -> None:
        """Test template list initialization."""
        project_config = ProjectConfig(name="test", project_type="api")
        devman_config = DevmanConfig(project=project_config)

        assert devman_config.templates.files == []

        devman_config.ensure_templates_list()

        assert len(devman_config.templates.files) > 0
        assert "devenv.nix.j2" in devman_config.templates.files

    def test_update_metadata(self) -> None:
        """Test metadata update."""
        project_config = ProjectConfig(name="test")
        devman_config = DevmanConfig(project=project_config)

        original_time = devman_config.devman.updated_at
        devman_config.update_metadata()

        assert devman_config.devman.updated_at > original_time

    def test_mark_generated(self) -> None:
        """Test marking files as generated."""
        project_config = ProjectConfig(name="test")
        devman_config = DevmanConfig(project=project_config)

        generated_files = ["devenv.nix", "justfile"]
        devman_config.mark_generated(generated_files)

        assert devman_config.generation.generated_files == generated_files
        assert devman_config.generation.last_generated is not None

    def test_to_toml(self) -> None:
        """Test TOML serialization."""
        project_config = ProjectConfig(
            name="test-project", project_type="api", dependencies=["fastapi"]
        )
        devman_config = DevmanConfig.create_from_project_config(project_config)

        toml_content = devman_config.to_toml()

        assert "[devman]" in toml_content
        assert "[project]" in toml_content
        assert "[templates]" in toml_content
        assert "test-project" in toml_content
        assert "fastapi" in toml_content

    def test_from_toml(self) -> None:
        """Test TOML deserialization."""
        toml_content = """
[devman]
version = "0.2.0"
created_at = "2025-01-15T10:30:00"
updated_at = "2025-01-15T10:30:00"

[project]
name = "test-project"
python_version = "3.11"
project_type = "api"
container_type = "devenv"
dependencies = ["fastapi"]
dev_dependencies = ["pytest"]
local_dependencies = []
use_database = false
database_type = "postgresql"
use_redis = false
use_celery = false

[templates]
files = ["devenv.nix.j2"]

[generation]
generated_files = []
"""

        devman_config = DevmanConfig.from_toml(toml_content)

        assert devman_config.project.name == "test-project"
        assert devman_config.project.project_type == "api"
        assert "fastapi" in devman_config.project.dependencies
        assert devman_config.templates.files == ["devenv.nix.j2"]

    def test_save_and_load_file(self) -> None:
        """Test saving and loading TOML file."""
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devman.toml"

            project_config = ProjectConfig(name="file-test", project_type="cli")
            devman_config = DevmanConfig.create_from_project_config(project_config)

            # Save to file
            devman_config.save(config_path)
            assert config_path.exists()

            # Load from file
            loaded_config = DevmanConfig.from_file(config_path)

            assert loaded_config.project.name == "file-test"
            assert loaded_config.project.project_type == "cli"
            assert loaded_config.devman.version == devman_config.devman.version

    def test_file_not_found(self) -> None:
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            DevmanConfig.from_file("nonexistent.toml")

    def test_get_template_context(self) -> None:
        """Test template context generation."""
        project_config = ProjectConfig(
            name="context-test", python_version="3.12", dependencies=["requests"]
        )
        devman_config = DevmanConfig.create_from_project_config(project_config)

        context = devman_config.get_template_context()

        assert context["name"] == "context-test"
        assert context["python_version"] == "3.12"
        assert "requests" in context["dependencies"]

    def test_computed_properties(self) -> None:
        """Test computed properties."""
        project_config = ProjectConfig(name="test")
        devman_config = DevmanConfig(project=project_config)

        # Should use current working directory
        assert devman_config.devman_dir == Path.cwd() / ".devman"
        assert devman_config.config_file == Path.cwd() / ".devman" / "devman.toml"
