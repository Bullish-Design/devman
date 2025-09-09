# tests/test_templates.py
"""Test template registry and Jinja2 integration."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from jinja2 import TemplateNotFound

from devman.templates import TemplateRegistry


class TestTemplateRegistry:
    """Test TemplateRegistry functionality."""

    def test_empty_registry(self) -> None:
        """Test registry with no templates."""
        with TemporaryDirectory() as temp_dir:
            registry = TemplateRegistry(templates_dir=Path(temp_dir) / "nonexistent")

            assert len(registry.templates) == 0
            assert registry.list_templates() == []
            assert registry.has_template("test.j2") is False
            assert registry.get_template("test.j2") is None

    def test_load_templates_from_directory(self) -> None:
        """Test loading templates from directory."""
        with TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir)

            # Create test templates
            (templates_dir / "test1.j2").write_text("Hello {{ name }}!")
            (templates_dir / "test2.j2").write_text("Project: {{ project_type }}")
            (templates_dir / "not_template.txt").write_text("Should be ignored")

            registry = TemplateRegistry(templates_dir=templates_dir)

            assert len(registry.templates) == 2
            assert "test1.j2" in registry.templates
            assert "test2.j2" in registry.templates
            assert "not_template.txt" not in registry.templates

    def test_get_template_source(self) -> None:
        """Test getting template source."""
        registry = TemplateRegistry()
        registry.add_template("test.j2", "Hello {{ name }}!")

        source = registry.get_template_source("test.j2")
        assert source == "Hello {{ name }}!"

        assert registry.get_template_source("nonexistent.j2") is None

    def test_has_template(self) -> None:
        """Test template existence check."""
        registry = TemplateRegistry()
        registry.add_template("exists.j2", "content")

        assert registry.has_template("exists.j2") is True
        assert registry.has_template("missing.j2") is False

    def test_render_template(self) -> None:
        """Test template rendering with Jinja2."""
        registry = TemplateRegistry()
        registry.add_template("test.j2", "Hello {{ name }}! Type: {{ project_type }}")

        context = {"name": "TestProject", "project_type": "api"}
        result = registry.render_template("test.j2", context)

        assert result == "Hello TestProject! Type: api"

    def test_render_template_with_conditionals(self) -> None:
        """Test template rendering with Jinja2 conditionals."""
        registry = TemplateRegistry()
        template_content = """
{%- if use_database -%}
Database: {{ database_type }}
{%- endif -%}
{%- if use_redis -%}
Redis enabled
{%- endif -%}
""".strip()
        registry.add_template("conditional.j2", template_content)

        # Test with database only
        context = {
            "use_database": True,
            "database_type": "postgresql",
            "use_redis": False,
        }
        result = registry.render_template("conditional.j2", context)
        assert "Database: postgresql" in result
        assert "Redis enabled" not in result

        # Test with both
        context["use_redis"] = True
        result = registry.render_template("conditional.j2", context)
        assert "Database: postgresql" in result
        assert "Redis enabled" in result

    def test_render_template_with_loops(self) -> None:
        """Test template rendering with Jinja2 loops."""
        registry = TemplateRegistry()
        template_content = """
dependencies = [
{%- for dep in dependencies %}
    "{{ dep }}",
{%- endfor %}
]
""".strip()
        registry.add_template("loop.j2", template_content)

        context = {"dependencies": ["fastapi>=0.104.0", "uvicorn[standard]>=0.24.0"]}
        result = registry.render_template("loop.j2", context)

        assert '"fastapi>=0.104.0",' in result
        assert '"uvicorn[standard]>=0.24.0",' in result

    def test_render_nonexistent_template(self) -> None:
        """Test rendering nonexistent template raises error."""
        registry = TemplateRegistry()

        with pytest.raises(TemplateNotFound):
            registry.render_template("nonexistent.j2", {})

    def test_add_template(self) -> None:
        """Test adding template dynamically."""
        registry = TemplateRegistry()

        assert not registry.has_template("new.j2")

        registry.add_template("new.j2", "New template: {{ value }}")

        assert registry.has_template("new.j2")
        result = registry.render_template("new.j2", {"value": "test"})
        assert result == "New template: test"

    def test_reload_templates(self) -> None:
        """Test reloading templates from disk."""
        with TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir)

            # Create initial template
            (templates_dir / "test.j2").write_text("Version 1")

            registry = TemplateRegistry(templates_dir=templates_dir)
            assert registry.get_template_source("test.j2") == "Version 1"

            # Update template file
            (templates_dir / "test.j2").write_text("Version 2")

            # Should still have old content
            assert registry.get_template_source("test.j2") == "Version 1"

            # After reload, should have new content
            registry.reload()
            assert registry.get_template_source("test.j2") == "Version 2"

    def test_list_templates(self) -> None:
        """Test listing available templates."""
        registry = TemplateRegistry(
            templates_dir=Path("nonexistent")
        )  # Avoid loading defaults
        registry.add_template("a.j2", "content")
        registry.add_template("b.j2", "content")

        templates = registry.list_templates()
        assert len(templates) == 2
        assert "a.j2" in templates
        assert "b.j2" in templates

    def test_jinja_environment_configuration(self) -> None:
        """Test Jinja2 environment is properly configured."""
        registry = TemplateRegistry()
        env = registry.environment

        # Check environment settings
        assert env.trim_blocks is True
        assert env.lstrip_blocks is True
        assert env.keep_trailing_newline is True
