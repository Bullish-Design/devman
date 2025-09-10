# src/devman/models.py
from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .exceptions import CopierExecutionError, TemplateNotFoundError
from .validation import ProjectValidator, TemplateValidator
from .remote import TemplateRegistry
from .security import SecurityConfig, SecurityManager


class ProjectConfig(BaseModel):
    """Configuration for project generation."""

    project_name: str
    project_slug: str = Field(default="")
    package_name: str = Field(default="")
    python_version: str = "3.11"
    use_nix: bool = True
    use_docker: bool = True
    use_just: bool = True

    # Security configuration
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @field_validator("project_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        ProjectValidator.validate_project_name(v)
        return v

    @field_validator("package_name")
    @classmethod
    def validate_package(cls, v: str) -> str:
        ProjectValidator.validate_package_name(v)
        return v

    @field_validator("python_version")
    @classmethod
    def validate_python_version(cls, v: str) -> str:
        ProjectValidator.validate_python_version(v)
        return v

    def model_post_init(self, __context) -> None:
        if not self.project_slug:
            self.project_slug = self._slugify(self.project_name)
        if not self.package_name:
            self.package_name = self.project_slug.replace("-", "_")

    @staticmethod
    def _slugify(name: str) -> str:
        import re

        slug_re = re.compile(r"[^a-z0-9_-]+")
        name = name.strip().lower()
        name = slug_re.sub("-", name)
        return re.sub(r"-+", "-", name).strip("-") or "project"


class FileSnapshot(BaseModel):
    """Represents a file in the template snapshot."""

    content: str
    size: int
    is_binary: bool = False


class GenerationPlan(BaseModel):
    """Plan for file generation."""

    destination: Path
    template_path: str
    files: Dict[str, FileSnapshot]
    conflicts: List[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def analyze_conflicts(self, force: bool = False) -> List[str]:
        """Analyze potential file conflicts."""
        if force:
            return []

        conflicts = []
        for rel_path in self.files:
            target = self.destination / rel_path
            if target.exists():
                conflicts.append(rel_path)
        self.conflicts = conflicts
        return conflicts

    def get_summary(self) -> dict:
        """Get a summary of the generation plan."""
        return {
            "total_files": len(self.files),
            "conflicts": len(self.conflicts),
            "destination": str(self.destination),
            "template": self.template_path,
        }


class TemplateEngine(BaseModel):
    """Core template engine using Copier with remote template support."""

    model_config = {"arbitrary_types_allowed": True}

    answers_file: str = ".devman/devman_config.yml"
    registry: TemplateRegistry = Field(default_factory=TemplateRegistry.load)

    def generate_project(
        self,
        template_path: str | Path,
        destination: Path,
        config: ProjectConfig,
        *,
        force: bool = False,
        quiet: bool = True,
        vcs_ref: Optional[str] = None,
    ) -> None:
        """Generate project using Copier with security integration."""
        # Resolve template path (handles remote templates)
        resolved_template_path = self._resolve_template_path(template_path)
        ProjectValidator.validate_destination(destination, force=force)

        try:
            from copier import run_copy

            # Generate base project
            run_copy(
                src_path=str(resolved_template_path),
                dst_path=str(destination),
                data=config.model_dump(),
                answers_file=self.answers_file,
                overwrite=force,
                quiet=quiet,
                vcs_ref=vcs_ref,
            )

            # Apply security configurations
            self._apply_security_configs(destination, config)

        except Exception as e:
            raise CopierExecutionError(
                f"Failed to generate project from template {template_path}: {e}", original_error=e
            ) from e

    def create_plan(
        self,
        template_path: str | Path,
        destination: Path,
        config: ProjectConfig,
        vcs_ref: Optional[str] = None,
    ) -> GenerationPlan:
        """Create generation plan without writing files."""
        # Resolve template path
        resolved_template_path = self._resolve_template_path(template_path)

        try:
            files = self._render_to_memory(resolved_template_path, config, vcs_ref=vcs_ref)

            plan = GenerationPlan(
                destination=destination,
                template_path=str(resolved_template_path),
                files=files,
            )

            # Analyze conflicts
            plan.analyze_conflicts()
            return plan

        except Exception as e:
            raise CopierExecutionError(
                f"Failed to create plan from template {template_path}: {e}", original_error=e
            ) from e

    def _resolve_template_path(self, template_path: str | Path) -> Path:
        """Resolve template path using registry for remote templates."""
        if isinstance(template_path, Path):
            return self._validate_template_path(template_path)

        # Use registry to resolve remote templates
        try:
            return self.registry.resolve_template_path(template_path)
        except TemplateNotFoundError:
            # Fallback to local path validation
            return self._validate_template_path(Path(template_path))

    def _validate_template_path(self, template_path: Path) -> Path:
        """Validate and normalize template path."""
        try:
            return TemplateValidator.validate_template_path(template_path)
        except Exception as e:
            raise TemplateNotFoundError(str(template_path)) from e

    def _render_to_memory(
        self,
        template_path: Path,
        config: ProjectConfig,
        vcs_ref: Optional[str] = None,
    ) -> Dict[str, FileSnapshot]:
        """Render template to memory and return file snapshots."""
        from copier import run_copy

        with tempfile.TemporaryDirectory(prefix="devman-") as tmp:
            tmp_path = Path(tmp)

            # Run copier in temporary directory
            run_copy(
                src_path=str(template_path),
                dst_path=str(tmp_path),
                data=config.model_dump(),
                answers_file=self.answers_file,
                overwrite=True,
                quiet=True,
                vcs_ref=vcs_ref,
            )

            # Collect all generated files
            files = {}
            for file_path in tmp_path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(tmp_path).as_posix()
                    files[rel_path] = self._create_file_snapshot(file_path)

            return files

    def _create_file_snapshot(self, file_path: Path) -> FileSnapshot:
        """Create a snapshot of a single file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            return FileSnapshot(
                content=content,
                size=len(content),
                is_binary=False,
            )
        except UnicodeDecodeError:
            # Handle binary files
            size = file_path.stat().st_size
            return FileSnapshot(
                content=f"<binary file: {size} bytes>",
                size=size,
                is_binary=True,
            )

    def _apply_security_configs(self, destination: Path, config: ProjectConfig) -> None:
        """Apply security configurations to generated project."""
        security_manager = SecurityManager(config.security)

        # Generate security configuration files
        security_manager.generate_pre_commit_config(destination)
        security_manager.generate_security_configs(destination, config.package_name)

        # Install security tools as dev dependencies
        security_manager.install_security_tools(destination)

        # Update justfile with security commands
        self._update_justfile_with_security(destination, security_manager)

    def _update_justfile_with_security(self, destination: Path, security_manager: SecurityManager) -> None:
        """Update justfile with security commands."""
        justfile_path = destination / "justfile"
        if not justfile_path.exists():
            return

        # Get security commands
        security_commands = security_manager.generate_security_justfile_commands()

        # Read existing justfile
        content = justfile_path.read_text()

        # Add security section
        security_section = "\n# Security commands\n"
        for command, action in security_commands.items():
            security_section += f"{command}:\n\t{action}\n\n"

        # Append to justfile
        content += security_section
        justfile_path.write_text(content)
