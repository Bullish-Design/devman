# src/devman/__init__.py
from __future__ import annotations

__all__ = ["__version__", "ProjectConfig", "TemplateEngine"]
__version__ = "0.3.0"

from .models import ProjectConfig, TemplateEngine, GenerationPlan, FileSnapshot
from .config import UserConfig, ConfigManager
from .exceptions import (
    DevmanError,
    TemplateNotFoundError,
    TemplateValidationError,
    ProjectExistsError,
    InvalidProjectNameError,
    ConfigurationError,
    CopierExecutionError,
)