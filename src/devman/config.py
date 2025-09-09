# src/devenv_templater/config.py
"""Configuration models for devenv templater."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

@dataclass
class ProjectConfig:
    """Configuration for a devenv project."""
    
    name: str
    python_version: str = "3.11"
    project_type: str = "api"  # api, web, cli, ml, lib
    container_type: str = "devenv"  # devenv, docker, nixos, none
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)
    local_dependencies: List[str] = field(default_factory=list)
    
    # Features
    use_database: bool = False
    database_type: str = "postgresql"  # postgresql, sqlite
    use_redis: bool = False
    use_celery: bool = False
    
    @property
    def use_containers(self) -> bool:
        """Whether project uses containers."""
        return self.container_type != "none"
    
    @property
    def python_version_short(self) -> str:
        """Python version without dots (e.g., '311')."""
        return self.python_version.replace(".", "")
    
    def get_default_dependencies(self) -> List[str]:
        """Get default dependencies for project type."""
        deps = []
        
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
                "matplotlib>=3.7.0"
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
    
    def get_default_dev_dependencies(self) -> List[str]:
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