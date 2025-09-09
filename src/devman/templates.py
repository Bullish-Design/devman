# src/devman/templates.py
"""Template registry for devman project templates with Jinja2 integration."""

from __future__ import annotations

from pathlib import Path

from jinja2 import BaseLoader, Environment, TemplateNotFound
from pydantic import BaseModel, Field, ConfigDict


class TemplateLoader(BaseLoader):
    """Custom Jinja2 loader for template registry."""

    def __init__(self, registry: TemplateRegistry) -> None:
        self.registry = registry

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, callable[[], bool] | None]:
        """Load template source from registry."""
        source = self.registry.get_template_source(template)
        if source is None:
            raise TemplateNotFound(template)

        # Return (source, filename, uptodate_func)
        return source, template, lambda: True


class TemplateRegistry(BaseModel):
    """Registry for project templates with Jinja2 integration."""

    templates: dict[str, str] = Field(
        default_factory=dict, description="Template name to content mapping"
    )
    templates_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent / "templates",
        description="Directory containing template files",
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        self._environment: Environment | None = None
        self._load_templates()
        self._setup_environment()

    def _load_templates(self) -> None:
        """Load all .j2 templates from the templates directory."""
        if not self.templates_dir.exists():
            return

        for template_file in self.templates_dir.glob("*.j2"):
            template_name = template_file.name
            try:
                self.templates[template_name] = template_file.read_text(
                    encoding="utf-8"
                )
            except (OSError, UnicodeDecodeError):
                # Skip files that can't be read
                continue

    def _setup_environment(self) -> None:
        """Setup Jinja2 environment with custom loader."""
        loader = TemplateLoader(self)
        self._environment = Environment(
            loader=loader,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    @property
    def environment(self) -> Environment:
        """Get Jinja2 environment."""
        if self._environment is None:
            self._setup_environment()
        return self._environment

    def get_template_source(self, name: str) -> str | None:
        """Get template source by name."""
        return self.templates.get(name)

    def get_template(self, name: str) -> str | None:
        """Get a template by name (for backward compatibility)."""
        return self.get_template_source(name)

    def render_template(self, name: str, context: dict[str, object]) -> str:
        """Render a template with given context using Jinja2."""
        template = self.environment.get_template(name)
        return template.render(context)

    def list_templates(self) -> list[str]:
        """List available template names."""
        return list(self.templates.keys())

    def has_template(self, name: str) -> bool:
        """Check if template exists."""
        return name in self.templates

    def add_template(self, name: str, content: str) -> None:
        """Add a template to the registry."""
        self.templates[name] = content
        # Invalidate environment to force reload
        self._environment = None
        self._setup_environment()

    def reload(self) -> None:
        """Reload templates from disk."""
        self.templates.clear()
        self._load_templates()
        self._setup_environment()


# Global template registry instance
TEMPLATE_REGISTRY = TemplateRegistry()

