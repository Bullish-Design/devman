# src/devenv_templater/templater.py
"""Template engine for devenv projects."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict

from .config import ProjectConfig
from .templates import TEMPLATES


class DevEnvTemplater:
    """DevEnv project templater."""
    
    def __init__(self, templates_dir: str = "~/.devenv-templates"):
        self.templates_dir = Path(templates_dir).expanduser()
    
    def ensure_templates_exist(self) -> None:
        """Create templates directory and default templates."""
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        for name, content in TEMPLATES.items():
            template_file = self.templates_dir / name
            template_file.write_text(content)
    
    def generate_project(self, config: ProjectConfig, target_dir: Path | str) -> None:
        """Generate project files from templates."""
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Prepare template context
        context = self._build_context(config)
        
        # Generate files
        files_to_generate = ["devenv.nix", "justfile", "pyproject.toml", ".envrc"]
        
        if config.use_containers:
            if config.container_type == "docker":
                files_to_generate.extend(["Dockerfile", "docker-compose.yml"])
            elif config.container_type == "nixos":
                files_to_generate.append("container.nix")
        
        for file_name in files_to_generate:
            template_name = f"{file_name}.j2"
            
            # Check custom templates first
            custom_template = self.templates_dir / template_name
            if custom_template.exists():
                template_content = custom_template.read_text()
            elif template_name in TEMPLATES:
                template_content = TEMPLATES[template_name]
            else:
                continue  # Skip missing templates
            
            rendered = self.render_template(template_content, context)
            (target_path / file_name).write_text(rendered)
        
        # Create directory structure
        self._create_project_structure(target_path, config)
        
        # Initialize Python project if needed
        if not (target_path / "pyproject.toml").exists():
            try:
                subprocess.run(
                    ["uv", "init", "--python", config.python_version],
                    cwd=target_path,
                    check=True,
                    capture_output=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass  # uv not available or failed
    
    def _build_context(self, config: ProjectConfig) -> Dict[str, Any]:
        """Build template context from config."""
        # Combine default and custom dependencies
        all_deps = config.get_default_dependencies() + config.dependencies
        all_dev_deps = config.get_default_dev_dependencies() + config.dev_dependencies
        
        return {
            "name": config.name,
            "python_version": config.python_version,
            "python_version_short": config.python_version_short,
            "project_type": config.project_type,
            "container_type": config.container_type,
            "use_containers": config.use_containers,
            "use_database": config.use_database,
            "database_type": config.database_type,
            "use_redis": config.use_redis,
            "use_celery": config.use_celery,
            "dependencies": all_deps,
            "dev_dependencies": all_dev_deps,
            "local_dependencies": config.local_dependencies,
        }
    
    def _create_project_structure(self, target_path: Path, config: ProjectConfig) -> None:
        """Create project directory structure."""
        # Main source directory
        (target_path / "src" / config.name).mkdir(parents=True, exist_ok=True)
        
        # Tests directory
        (target_path / "tests").mkdir(exist_ok=True)
        
        # Create __init__.py files
        (target_path / "src" / config.name / "__init__.py").touch()
        (target_path / "tests" / "__init__.py").touch()
        
        # Create starter files based on project type
        self._create_starter_files(target_path, config)
    
    def _create_starter_files(self, target_path: Path, config: ProjectConfig) -> None:
        """Create starter application files."""
        src_dir = target_path / "src" / config.name
        tests_dir = target_path / "tests"
        
        if config.project_type == "api":
            main_py = '''"""FastAPI application."""

from fastapi import FastAPI

app = FastAPI(title="{name}", version="0.1.0")

@app.get("/")
async def root():
    return {{"message": "Hello from {name}!"}}

@app.get("/health")
async def health():
    return {{"status": "healthy"}}
'''.format(name=config.name)
            (src_dir / "main.py").write_text(main_py)
            
        elif config.project_type == "cli":
            cli_py = '''"""Command line interface."""

import typer

app = typer.Typer()

@app.command()
def hello(name: str = "World"):
    """Say hello."""
    typer.echo(f"Hello {name}!")

def main():
    app()

if __name__ == "__main__":
    main()
'''.format(name=config.name)
            (src_dir / "cli.py").write_text(cli_py)
        
        # Basic test file
        test_content = f'''"""Test {config.name}."""

def test_placeholder():
    """Placeholder test."""
    assert True
'''
        (tests_dir / "test_main.py").write_text(test_content)
    
    def render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render template with context."""
        
        def replace_var(match):
            var_name = match.group(1)
            return str(context.get(var_name, f"{{{{{var_name}}}}}"))
        
        def replace_if(match):
            condition = match.group(1)
            content = match.group(2)
            else_content = match.group(3) if len(match.groups()) > 2 and match.group(3) else ""
            
            if condition in context and context[condition]:
                return content
            return else_content
        
        def replace_for(match):
            var_name = match.group(1)
            list_name = match.group(2)
            content = match.group(3)
            
            if list_name in context and isinstance(context[list_name], list):
                result = ""
                for item in context[list_name]:
                    item_content = content.replace(f"{{{{{var_name}}}}}", str(item))
                    result += item_content
                return result
            return ""
        
        # Apply template transformations
        template = re.sub(r'\{\{(\w+)\}\}', replace_var, template)
        template = re.sub(
            r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}',
            replace_if, template, flags=re.DOTALL
        )
        template = re.sub(
            r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}',
            replace_if, template, flags=re.DOTALL
        )
        template = re.sub(
            r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}',
            replace_for, template, flags=re.DOTALL
        )
        
        return template