# src/devman/remote.py
from __future__ import annotations
import json
import subprocess
import hashlib
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from rich.console import Console
from rich.table import Table

from .exceptions import TemplateNotFoundError, ConfigurationError


class RemoteTemplate(BaseModel):
    """Remote template configuration."""

    name: str
    url: str
    ref: Optional[str] = None
    subdirectory: Optional[str] = None
    description: str = ""
    verified: bool = False
    last_updated: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not any(
            v.startswith(prefix)
            for prefix in [
                "git+",
                "https://github.com/",
                "git@github.com:",
                "https://gitlab.com/",
                "git@gitlab.com:",
                "https://",
            ]
        ):
            raise ValueError(f"Invalid Git URL format: {v}")
        return v


class TemplateRegistry(BaseModel):
    """Template registry for managing remote templates."""

    templates: Dict[str, RemoteTemplate] = Field(default_factory=dict)
    cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "devman" / "templates")

    model_config = {"arbitrary_types_allowed": True}

    def add_template(
        self, name: str, url: str, ref: Optional[str] = None, description: str = "", force: bool = False
    ) -> None:
        """Add a remote template to registry."""
        if name in self.templates and not force:
            raise ConfigurationError(f"Template '{name}' already exists. Use --force to overwrite.")

        template = RemoteTemplate(name=name, url=url, ref=ref, description=description)

        # Validate template can be cloned
        try:
            self._clone_template(template.url, template.ref, template.subdirectory, validate_only=True)
        except Exception as e:
            raise ConfigurationError(f"Cannot access template at {url}: {e}")

        self.templates[name] = template
        self.save()

    def remove_template(self, name: str) -> None:
        """Remove template from registry."""
        if name not in self.templates:
            raise ConfigurationError(f"Template '{name}' not found in registry")

        # Remove from cache
        template = self.templates[name]
        cache_key = self._generate_cache_key(template.url, template.ref)
        cache_path = self.cache_dir / cache_key

        if cache_path.exists():
            import shutil

            shutil.rmtree(cache_path)

        del self.templates[name]
        self.save()

    def list_templates(self) -> Table:
        """List all registered templates as Rich table."""
        table = Table(title="Registered Templates")
        table.add_column("Name", style="bold")
        table.add_column("URL", style="cyan")
        table.add_column("Ref", style="yellow")
        table.add_column("Description")

        for name, template in self.templates.items():
            table.add_row(name, template.url, template.ref or "main", template.description)

        return table

    def resolve_template_path(self, template_ref: str) -> Path:
        """Resolve template reference to local path."""
        # Handle built-in templates
        builtin_templates = ["python-lib", "python-cli", "fastapi-api"]
        if template_ref in builtin_templates:
            return Path(__file__).parent / "templates" / template_ref

        # Handle direct Git URLs (gh:org/repo format)
        if template_ref.startswith("gh:"):
            github_url = f"https://github.com/{template_ref[3:]}.git"
            return self._clone_template(github_url)

        # Handle full Git URLs
        if self._is_git_url(template_ref):
            return self._clone_template(template_ref)

        # Handle registered template names
        if template_ref in self.templates:
            template = self.templates[template_ref]
            return self._clone_template(template.url, template.ref, template.subdirectory)

        # Handle local paths
        path = Path(template_ref)
        if path.exists():
            return path

        raise TemplateNotFoundError(template_ref)

    def update_template(self, name: str) -> None:
        """Update cached template to latest version."""
        if name not in self.templates:
            raise ConfigurationError(f"Template '{name}' not found")

        template = self.templates[name]
        cache_key = self._generate_cache_key(template.url, template.ref)
        cache_path = self.cache_dir / cache_key

        if cache_path.exists():
            try:
                subprocess.run(["git", "pull"], cwd=cache_path, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                # If pull fails, re-clone
                import shutil

                shutil.rmtree(cache_path)
                self._clone_template(template.url, template.ref, template.subdirectory)

    def update_all_templates(self) -> List[str]:
        """Update all cached templates."""
        updated = []
        for name in self.templates:
            try:
                self.update_template(name)
                updated.append(name)
            except Exception:
                pass  # Skip failed updates
        return updated

    def _is_git_url(self, url: str) -> bool:
        """Check if URL is a Git repository."""
        return any(
            url.startswith(prefix)
            for prefix in [
                "git+",
                "https://github.com/",
                "git@github.com:",
                "https://gitlab.com/",
                "git@gitlab.com:",
                "https://",
            ]
        )

    def _clone_template(
        self, url: str, ref: Optional[str] = None, subdirectory: Optional[str] = None, validate_only: bool = False
    ) -> Path:
        """Clone remote template to local cache."""
        cache_key = self._generate_cache_key(url, ref)
        cache_path = self.cache_dir / cache_key

        if validate_only:
            # Just test if we can clone
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                cmd = ["git", "clone", "--depth", "1", url, temp_dir]
                if ref:
                    cmd.extend(["--branch", ref])
                subprocess.run(cmd, check=True, capture_output=True)
            return cache_path

        if not cache_path.exists():
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            try:
                cmd = ["git", "clone", url, str(cache_path)]
                if ref:
                    cmd.extend(["--branch", ref])

                subprocess.run(cmd, check=True, capture_output=True)

            except subprocess.CalledProcessError as e:
                raise TemplateNotFoundError(f"Failed to clone template {url}: {e}")

        if subdirectory:
            template_path = cache_path / subdirectory
            if not template_path.exists():
                raise TemplateNotFoundError(f"Subdirectory {subdirectory} not found in {url}")
            return template_path

        return cache_path

    def _generate_cache_key(self, url: str, ref: Optional[str] = None) -> str:
        """Generate cache key for template."""
        content = f"{url}#{ref or 'main'}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def save(self) -> None:
        """Save registry to disk."""
        registry_file = Path.home() / ".config" / "devman" / "registry.json"
        registry_file.parent.mkdir(parents=True, exist_ok=True)

        data = {name: template.model_dump() for name, template in self.templates.items()}
        registry_file.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> TemplateRegistry:
        """Load registry from disk."""
        registry_file = Path.home() / ".config" / "devman" / "registry.json"

        if not registry_file.exists():
            return cls()

        try:
            data = json.loads(registry_file.read_text())
            templates = {name: RemoteTemplate(**template_data) for name, template_data in data.items()}
            return cls(templates=templates)
        except Exception:
            return cls()
