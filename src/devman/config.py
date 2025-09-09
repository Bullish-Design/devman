# src/devman/config.py
"""Configuration models for devenv templater."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field


class ProjectConfig(BaseModel):
    """Configuration for a devenv project."""

    name: str = Field(..., description="Project name")
    python_version: str = Field(default="3.11", description="Python version")
    project_type: Literal["api", "web", "cli", "ml", "lib"] = Field(
        default="api", description="Project type"
    )
    container_type: Literal["devenv", "docker", "nixos", "none"] = Field(
        default="devenv", description="Container type"
    )

    # Dependencies
    dependencies: list[str] = Field(default_factory=list, description="Runtime dependencies")
    dev_dependencies: list[str] = Field(default_factory=list, description="Development dependencies")
    local_dependencies: list[str] = Field(default_factory=list, description="Local path dependencies")

    # Features
    use_database: bool = Field(default=False, description="Enable database integration")
    database_type: Literal["postgresql", "sqlite"] = Field(
        default="postgresql", description="Database type"
    )
    use_redis: bool = Field(default=False, description="Enable Redis integration")
    use_celery: bool = Field(default=False, description="Enable Celery integration")

    @computed_field
    @property
    def use_containers(self) -> bool:
        """Whether project uses containers."""
        return self.container_type != "none"

    @computed_field
    @property
    def python_version_short(self) -> str:
        """Python version without dots (e.g., '311')."""
        return self.python_version.replace(".", "")

    def get_default_dependencies(self) -> list[str]:
        """Get default dependencies for project type."""
        deps: list[str] = []

        if self.project_type == "api":
            deps.extend(["fastapi>=0.104.0", "uvicorn[standard]>=0.24.0"])
        elif self.project_type == "web":
            deps.extend(["flask>=3.0.0", "jinja2>=3.1.0"])
        elif self.project_type == "cli":
            deps.extend(["typer[all]>=0.12.0", "rich>=13.0.0"])
        elif self.project_type == "ml":
            deps.extend([
                "numpy>=1.24.0",
                "pandas>=2.0.0",
                "scikit-learn>=1.3.0",
                "matplotlib>=3.7.0",
            ])

        if self.use_database:
            if self.database_type == "postgresql":
                deps.append("psycopg2-binary>=2.9.0")
            deps.append("sqlalchemy>=2.0.0")

        if self.use_redis:
            deps.append("redis>=5.0.0")

        if self.use_celery:
            deps.extend(["celery>=5.3.0", "redis>=5.0.0"])

        return deps

    def get_default_dev_dependencies(self) -> list[str]:
        """Get default dev dependencies for project type."""
        deps = [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "ruff>=0.1.0",
            "mypy>=1.7.0",
        ]

        if self.project_type == "api":
            deps.extend(["httpx>=0.25.0", "pytest-asyncio>=0.21.0"])
        elif self.project_type == "web":
            deps.append("pytest-flask>=1.3.0")
        elif self.project_type == "ml":
            deps.extend(["jupyter>=1.0.0", "ipykernel>=6.25.0"])

        return deps

    def get_template_context(self) -> dict[str, object]:
        """Get template context dictionary for Jinja2 rendering."""
        all_deps = self.get_default_dependencies() + self.dependencies
        all_dev_deps = self.get_default_dev_dependencies() + self.dev_dependencies

        return {
            "name": self.name,
            "python_version": self.python_version,
            "python_version_short": self.python_version_short,
            "project_type": self.project_type,
            "container_type": self.container_type,
            "use_containers": self.use_containers,
            "use_database": self.use_database,
            "database_type": self.database_type,
            "use_redis": self.use_redis,
            "use_celery": self.use_celery,
            "dependencies": all_deps,
            "dev_dependencies": all_dev_deps,
            "local_dependencies": self.local_dependencies,
        }
