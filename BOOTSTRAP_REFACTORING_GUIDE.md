# Bootstrap Refactoring Guide

This guide walks you through refactoring the existing devman codebase into the new self-bootstrapping, file-oriented learning system. It is written step-by-step so you can follow each task in order.

## What You Need to Know First

Read the [README.md](README.md) to understand the end-state architecture. The short version:

- **Old design**: devman finds `.devman/` directories, runs devenv commands, creates projects from copier templates, and validates copier YAML schemas. It uses a layered architecture with domain models, use cases, protocols, and Railway-Oriented Programming (`Result` types).
- **New design**: devman manages a **store** at `~/.devman-store/` that is itself a git repo. It bootstraps new **file type** configurations using copier templates that live inside the store. It creates **projects** from meta-templates. It **updates** file types and projects when templates evolve. Versions are tracked via git tags.

The new design has four CLI commands: `init`, `bootstrap`, `project`, `update`. The old commands (`run`, `launch`, `new`, `config`, `hello`, `version`) are being replaced.

---

## Current Codebase Map

Before making changes, understand what exists and what each file does:

```
src/devman/
  __init__.py              # Package version (keep, update version string later)
  cli.py                   # OLD CLI commands (run, launch, new, config, version, hello)
                           #   -> REPLACE with new CLI (init, bootstrap, project, update)
  config.py                # Pydantic-settings config with env file storage
                           #   -> REMOVE (new design uses TOML config in the store)
  constants.py             # Constants: DEVMAN_DIR_NAME, DEVENV_COMMAND, CONFIG_DIR, CONFIG_FILE
                           #   -> REPLACE with new constants for the store path
  templates.py             # TemplateReference + TemplateValidator (old, duplicated in domain/)
                           #   -> REMOVE (replaced by new bootstrap/update logic)

  application/
    __init__.py
    use_cases.py           # FindDevman, RunDevenv, ValidateTemplate, CreateProject use cases
                           #   -> REMOVE entirely (new design doesn't use this layer)

  domain/
    __init__.py
    errors.py              # DomainError hierarchy (PathNotFound, InvalidGitUrl, etc.)
                           #   -> KEEP errors.py, simplify to what's needed
    finder.py              # DevmanFinder: walks up directories looking for .devman/
                           #   -> REMOVE (no longer needed; store has a fixed path)
    models.py              # ProjectRoot, DevmanDirectory, ValidationResult, ValidationIssue
                           #   -> SIMPLIFY: remove ProjectRoot/DevmanDirectory, keep ValidationResult
    protocols.py           # CommandExecutor, FileReader protocols + SubprocessExecutor
                           #   -> REMOVE (new design calls subprocess directly)
    templates.py           # TemplateReference + TemplateValidator (domain version)
                           #   -> REMOVE (replaced by new bootstrap/update logic)

  schemas/
    __init__.py
    copier.py              # CopierConfig pydantic model for parsing copier.yaml
    questions.py           # Question type models (StrQuestion, BoolQuestion, etc.)
    tasks.py               # Task/TaskList models
                           #   -> KEEP schemas/ for now; validation will use them later

scripts/
  generate_example.py      # Generates example copier.yaml
                           #   -> REMOVE (not part of new design)
  validate_copier.py       # Standalone copier validator
                           #   -> REMOVE (validation moves into workflows)

tests/                     # Existing tests
                           #   -> Will need to be rewritten per new modules, but
                           #      defer major test rewrite to Phase 2
```

---

## Prerequisites

Before starting, make sure you have these tools installed:

- Python >= 3.13
- [uv](https://github.com/astral-sh/uv)
- [copier](https://copier.readthedocs.io/) >= 9.0.0
- git

You will also need to add these new dependencies to `pyproject.toml`:

- `tomli` (for reading TOML on Python < 3.11, but since we require 3.13 you can use `tomllib` from stdlib)
- `tomli-w` (for writing TOML)
- `rich` (for terminal output formatting)

And remove these dependencies that are no longer needed:

- `pydantic-settings` (config moves to TOML in the store)
- `result` (no more Railway-Oriented Programming; use plain exceptions)

---

## Step-by-Step Refactoring Tasks

### Task 1: Update `pyproject.toml` dependencies

**File:** `pyproject.toml`

Update the dependency list. The new design needs:

```toml
dependencies = [
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "copier>=9.0.0",
    "pyyaml>=6.0.0",
    "tomli-w>=1.0.0",
    "rich>=13.0.0",
]
```

Remove `pydantic-settings` and `result` from the dependency list.

Update the description:

```toml
description = "Self-bootstrapping file-oriented learning system"
```

Keep the `[project.scripts]` entry as-is (`devman = "devman.cli:app"`).

### Task 2: Update `constants.py`

**File:** `src/devman/constants.py`

Replace the contents with constants for the new store-based design:

```python
# src/devman/constants.py
"""Module-level constants for devman."""

from pathlib import Path

STORE_ROOT = Path.home() / ".devman-store"
DEVMAN_META_DIR = STORE_ROOT / "devman"
TEMPLATES_DIR = DEVMAN_META_DIR / ".devman" / ".templates"
WORKFLOWS_DIR = DEVMAN_META_DIR / ".devman" / "workflows"
CONFIG_FILE = DEVMAN_META_DIR / ".devman" / "config.toml"
```

These constants define the fixed locations for the devman store, removing the need for the old `DevmanFinder` that walked up directories.

### Task 3: Create `src/devman/bootstrap.py`

**New file:** `src/devman/bootstrap.py`

This module contains two functions:

1. **`init_devman_store()`** - Creates `~/.devman-store/devman/` with subdirectories, a minimal `config.toml`, initializes a git repo, makes an initial commit, and tags it `v0.1.0`. Returns the store root path. Raises `ValueError` if the store already exists.

2. **`bootstrap_file_type(file_type, answers_file=None, template_version=None)`** - Uses copier to copy the `file-type` template into `~/.devman-store/{file_type}/`. Captures the current git tag version (via `get_current_devman_version()`) unless `template_version` is explicitly provided. After copier runs, appends version metadata to the generated `config.toml`. Returns the path to the created type directory.

3. **`get_current_devman_version()`** - Runs `git describe --tags --abbrev=0` in the devman meta-directory and returns the tag string (e.g., `"v0.1.0"`). Returns `"unversioned"` if no tags exist.

Here is the reference implementation from the design spec:

```python
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Optional
from datetime import datetime


def init_devman_store() -> Path:
    """Initialize devman store with git-backed meta-configuration."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"

    if devman_path.exists():
        raise ValueError(f"Devman store already initialized at {store_root}")

    # Create structure
    devman_path.mkdir(parents=True)
    devman_config = devman_path / ".devman"
    devman_config.mkdir()

    templates_dir = devman_config / ".templates"
    templates_dir.mkdir()

    workflows_dir = devman_config / "workflows"
    workflows_dir.mkdir()

    # Create minimal config
    config_path = devman_config / "config.toml"
    config_path.write_text(
        '[devman]\n'
        'version = "0.1.0"\n'
        'store_path = "~/.devman-store"\n'
    )

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=devman_path, check=True)
    subprocess.run(["git", "add", "."], cwd=devman_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "[init] Initialize devman store"],
        cwd=devman_path,
        check=True,
    )
    subprocess.run(
        ["git", "tag", "-a", "v0.1.0", "-m", "Initial devman version"],
        cwd=devman_path,
        check=True,
    )

    return store_root


def get_current_devman_version() -> str:
    """Get current devman template version from git tags."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"

    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=devman_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return "unversioned"

    return result.stdout.strip()


def bootstrap_file_type(
    file_type: str,
    answers_file: Optional[Path] = None,
    template_version: Optional[str] = None,
) -> Path:
    """Bootstrap a new file type using copier templates."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"
    template_path = devman_path / ".devman/.templates/file-type"
    target_path = store_root / file_type

    if target_path.exists():
        raise ValueError(f"File type already exists: {file_type}")

    if not template_version:
        template_version = get_current_devman_version()

    copier_cmd = ["copier", "copy"]

    if template_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", template_version])

    if answers_file:
        copier_cmd.extend(["--data-file", str(answers_file)])

    copier_cmd.extend([str(template_path), str(target_path.parent)])

    result = subprocess.run(copier_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Copier failed: {result.stderr}")

    # Add version metadata to config
    config_path = target_path / ".devman/config.toml"
    if config_path.exists():
        with open(config_path, "a") as f:
            f.write(f"\n[template]\n")
            f.write(f'name = "file-type"\n')
            f.write(f'devman_version = "{template_version}"\n')
            f.write(f'created_at = "{datetime.now().isoformat()}"\n')

    return target_path
```

**Key things to note:**

- `init_devman_store()` creates the directory structure, writes a config, runs `git init`, commits, and tags.
- `bootstrap_file_type()` shells out to `copier copy` with the file-type template as source.
- Version is captured from git tags automatically unless explicitly overridden.
- The `[template]` section is appended to the generated config.toml after copier runs.

### Task 4: Create `src/devman/bootstrap_project.py`

**New file:** `src/devman/bootstrap_project.py`

This module has one function:

**`bootstrap_project(project_template, target_dir, answers_file=None, template_version=None)`** - Uses copier to copy a meta-template (e.g., `pyproj`) into `target_dir`. After copier runs, it executes `.devman-bootstrap.py` in the target directory if that file exists. It then writes or updates `.devman-project.toml` with template name, version, and creation timestamp.

Here is the reference implementation:

```python
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Optional
from datetime import datetime

import tomli
import tomli_w


def bootstrap_project(
    project_template: str,
    target_dir: Path,
    answers_file: Optional[Path] = None,
    template_version: Optional[str] = None,
) -> dict:
    """Bootstrap a complete project using a meta-template."""
    store_root = Path.home() / ".devman-store"
    devman_path = store_root / "devman"
    template_path = devman_path / f".devman/.templates/{project_template}"

    if not template_path.exists():
        raise ValueError(f"Project template not found: {project_template}")

    if not template_version:
        from devman.bootstrap import get_current_devman_version
        template_version = get_current_devman_version()

    copier_cmd = ["copier", "copy"]

    if template_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", template_version])

    if answers_file:
        copier_cmd.extend(["--data-file", str(answers_file)])

    copier_cmd.extend([str(template_path), str(target_dir)])

    result = subprocess.run(copier_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Copier failed: {result.stderr}")

    # Execute .devman-bootstrap.py if it exists
    bootstrap_script = target_dir / ".devman-bootstrap.py"
    if bootstrap_script.exists():
        result = subprocess.run(
            ["python", str(bootstrap_script)],
            cwd=target_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Bootstrap script failed: {result.stderr}")

    # Read/update project metadata
    metadata_file = target_dir / ".devman-project.toml"
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, "rb") as f:
            metadata = tomli.load(f)

    if "template" not in metadata:
        metadata["template"] = {}

    metadata["template"]["name"] = project_template
    metadata["template"]["version"] = template_version
    metadata["template"]["created_at"] = datetime.now().isoformat()

    with open(metadata_file, "wb") as f:
        tomli_w.dump(metadata, f)

    return {
        "project_path": target_dir,
        "file_types": metadata.get("file_types", []),
        "template": project_template,
        "version": template_version,
    }
```

**Note:** Since we require Python >= 3.13, you can use `tomllib` from the standard library instead of `tomli` for reading TOML. Use `tomli_w` for writing (there is no stdlib TOML writer).

### Task 5: Create `src/devman/update.py`

**New file:** `src/devman/update.py`

This module has two functions:

1. **`update_file_type(file_type, target_version=None, dry_run=False)`** - Reads the current version from `config.toml`, runs `copier update` to bring the file type to the target version, and updates the config. Returns a result dictionary.

2. **`update_project(project_path, target_version=None, dry_run=False)`** - Reads the current version from `.devman-project.toml`, runs `copier update`, and updates the metadata file. Returns a result dictionary.

Here is the reference implementation:

```python
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Optional
from datetime import datetime

import tomli
import tomli_w


def update_file_type(
    file_type: str,
    target_version: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Update a file type configuration to a new template version."""
    store_root = Path.home() / ".devman-store"
    type_path = store_root / file_type

    if not type_path.exists():
        raise ValueError(f"File type not found: {file_type}")

    config_path = type_path / ".devman/config.toml"
    with open(config_path, "rb") as f:
        config = tomli.load(f)

    current_version = config.get("template", {}).get("devman_version", "unknown")

    if not target_version:
        from devman.bootstrap import get_current_devman_version
        target_version = get_current_devman_version()

    if current_version == target_version:
        return {
            "success": True,
            "message": f"Already at version {target_version}",
            "changes": [],
        }

    copier_cmd = ["copier", "update"]

    if target_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", target_version])

    if dry_run:
        copier_cmd.append("--pretend")

    copier_cmd.append(str(type_path))

    result = subprocess.run(copier_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr,
            "current_version": current_version,
            "target_version": target_version,
        }

    if not dry_run:
        config["template"]["devman_version"] = target_version
        config["template"]["updated_at"] = datetime.now().isoformat()

        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)

    return {
        "success": True,
        "current_version": current_version,
        "target_version": target_version,
        "changes": result.stdout.splitlines(),
        "dry_run": dry_run,
    }


def update_project(
    project_path: Path,
    target_version: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Update a project to a new meta-template version."""
    metadata_file = project_path / ".devman-project.toml"

    if not metadata_file.exists():
        raise ValueError(f"Not a devman project: {project_path}")

    with open(metadata_file, "rb") as f:
        metadata = tomli.load(f)

    current_version = metadata.get("template", {}).get("version", "unknown")
    template_name = metadata.get("template", {}).get("name")

    if not template_name:
        raise ValueError("Project metadata missing template name")

    if not target_version:
        from devman.bootstrap import get_current_devman_version
        target_version = get_current_devman_version()

    copier_cmd = ["copier", "update"]

    if target_version != "unversioned":
        copier_cmd.extend(["--vcs-ref", target_version])

    if dry_run:
        copier_cmd.append("--pretend")

    copier_cmd.append(str(project_path))

    result = subprocess.run(copier_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr,
            "current_version": current_version,
            "target_version": target_version,
        }

    if not dry_run:
        metadata["template"]["version"] = target_version
        metadata["template"]["updated_at"] = datetime.now().isoformat()

        with open(metadata_file, "wb") as f:
            tomli_w.dump(metadata, f)

    return {
        "success": True,
        "template": template_name,
        "current_version": current_version,
        "target_version": target_version,
        "changes": result.stdout.splitlines(),
        "dry_run": dry_run,
    }
```

### Task 6: Rewrite `src/devman/cli.py`

**File:** `src/devman/cli.py`

Delete the entire contents and replace with the new CLI that has four commands: `init`, `bootstrap`, `project`, `update`. The new CLI uses `rich` for formatted output instead of plain `typer.echo`.

Here is the reference implementation:

```python
from __future__ import annotations

import typer
from pathlib import Path
from rich.console import Console

app = typer.Typer(
    name="devman",
    help="Self-bootstrapping file-oriented learning system",
    add_completion=False,
)
console = Console()


@app.command()
def init():
    """Initialize devman store with git-backed templates."""
    from devman.bootstrap import init_devman_store

    try:
        store_path = init_devman_store()
        console.print(f"[green]OK[/green] Devman store initialized: {store_path}")
        console.print("  Git repository created with tag v0.1.0")
    except ValueError as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


@app.command()
def bootstrap(
    file_type: str = typer.Argument(..., help="File type name (e.g., pyproject.toml)"),
    answers: Path = typer.Option(None, "--answers", "-a", help="Copier answers file"),
    version: str = typer.Option(None, "--version", "-v", help="Pin to specific version"),
):
    """Bootstrap a new file type configuration."""
    from devman.bootstrap import bootstrap_file_type, get_current_devman_version

    console.print(f"Bootstrapping file type: [cyan]{file_type}[/cyan]")

    try:
        type_path = bootstrap_file_type(
            file_type=file_type,
            answers_file=answers,
            template_version=version,
        )
        console.print(f"[green]OK[/green] File type created: {type_path}")

        ver = version or get_current_devman_version()
        console.print(f"  Template version: {ver}")

    except (ValueError, RuntimeError) as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


@app.command()
def project(
    template: str = typer.Argument(..., help="Project template (e.g., pyproj)"),
    target: Path = typer.Argument(..., help="Target directory for project"),
    answers: Path = typer.Option(None, "--answers", "-a", help="Copier answers file"),
    version: str = typer.Option(None, "--version", "-v", help="Pin to specific version"),
):
    """Create a new project from a meta-template."""
    from devman.bootstrap_project import bootstrap_project

    console.print(f"Creating project from template: [cyan]{template}[/cyan]")

    try:
        result = bootstrap_project(
            project_template=template,
            target_dir=target,
            answers_file=answers,
            template_version=version,
        )

        console.print(f"[green]OK[/green] Project created: {result['project_path']}")
        console.print(f"  Template: {result['template']}@{result['version']}")

        if result["file_types"]:
            console.print("\n  File types used:")
            for ft in result["file_types"]:
                console.print(f"    - {ft}")

    except (ValueError, RuntimeError) as e:
        console.print(f"[red]Error[/red] {e}")
        raise typer.Exit(1)


@app.command()
def update(
    target: Path = typer.Argument(..., help="File type or project to update"),
    version: str = typer.Option(None, "--version", "-v", help="Target version"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
):
    """Update a file type or project to a new template version."""
    from devman.update import update_file_type, update_project

    target = Path(target).resolve()

    # Determine if it's a project (has .devman-project.toml) or a file type
    if (target / ".devman-project.toml").exists():
        console.print(f"Updating project: [cyan]{target.name}[/cyan]")

        try:
            result = update_project(
                project_path=target,
                target_version=version,
                dry_run=dry_run,
            )

            if result["success"]:
                action = "Would update" if dry_run else "Updated"
                console.print(
                    f"[green]OK[/green] {action}: "
                    f"{result['current_version']} -> {result['target_version']}"
                )

                if result.get("changes"):
                    console.print("\n  Changes:")
                    for change in result["changes"][:10]:
                        console.print(f"    {change}")
                    if len(result["changes"]) > 10:
                        console.print(
                            f"    ... and {len(result['changes']) - 10} more"
                        )
            else:
                console.print(
                    f"[yellow]Info[/yellow] "
                    f"{result.get('message', 'No changes needed')}"
                )

        except (ValueError, RuntimeError) as e:
            console.print(f"[red]Error[/red] {e}")
            raise typer.Exit(1)

    else:
        file_type = target.name
        console.print(f"Updating file type: [cyan]{file_type}[/cyan]")

        try:
            result = update_file_type(
                file_type=file_type,
                target_version=version,
                dry_run=dry_run,
            )

            if result["success"]:
                action = "Would update" if dry_run else "Updated"
                console.print(
                    f"[green]OK[/green] {action}: "
                    f"{result['current_version']} -> {result['target_version']}"
                )

                if result.get("changes"):
                    console.print("\n  Changes:")
                    for change in result["changes"][:10]:
                        console.print(f"    {change}")
                    if len(result["changes"]) > 10:
                        console.print(
                            f"    ... and {len(result['changes']) - 10} more"
                        )
            else:
                console.print(
                    f"[yellow]Info[/yellow] "
                    f"{result.get('message', 'No changes needed')}"
                )

        except (ValueError, RuntimeError) as e:
            console.print(f"[red]Error[/red] {e}")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
```

**Key differences from the old CLI:**
- No more `run`, `launch`, `new`, `config`, `hello`, `version` commands.
- Uses `rich.console.Console` instead of `typer.echo`.
- Imports are done inside command functions (lazy imports) so the CLI starts fast.
- No dependency injection or Result types; plain try/except error handling.

### Task 7: Remove files that are no longer needed

Delete these files entirely:

- `src/devman/config.py` - replaced by TOML config in the store
- `src/devman/templates.py` - functionality moved to `bootstrap.py`
- `src/devman/application/__init__.py` - entire application layer removed
- `src/devman/application/use_cases.py` - entire application layer removed
- `src/devman/domain/finder.py` - store has a fixed path; no directory walking
- `src/devman/domain/protocols.py` - no more DI protocols; direct subprocess calls
- `src/devman/domain/templates.py` - functionality moved to `bootstrap.py`
- `scripts/generate_example.py` - not part of the new design
- `scripts/validate_copier.py` - validation moves into workflows

You can delete the `application/` directory entirely.

### Task 8: Simplify `src/devman/domain/errors.py`

Keep the file but simplify it. The new design only needs a few error types. Remove errors that were specific to the old design:

**Remove:**
- `DevmanNotFoundError` (no more directory walking)
- `QuestionValidationError` (validation handled differently now)
- `InvalidGitUrlError` (not relevant to store-based templates)
- `ValidationError` (replaced by simpler exception handling)

**Keep:**
- `DomainError` (base class)
- `PathNotFoundError`
- `PathNotDirectoryError`

You may also want to add:
- `StoreAlreadyExistsError` (for when `init` is called twice)
- `FileTypeExistsError` (for when bootstrapping a type that already exists)
- `TemplateNotFoundError` (for when a template name doesn't exist in the store)

However, since the new design uses plain `ValueError` and `RuntimeError` in the reference implementations, you can simplify this file to just keep the base `DomainError` and the path errors for now. The bootstrap/update modules raise standard exceptions.

### Task 9: Simplify `src/devman/domain/models.py`

The new design no longer needs `ProjectRoot` or `DevmanDirectory` value objects since the store has a fixed, known path.

**Remove:**
- `ProjectRoot` class (no more configurable project root)
- `DevmanDirectory` class (no more directory walking)

**Keep:**
- `ValidationIssue` class
- `ValidationResult` class

These are still useful for the type-level validation that will be done in workflows.

### Task 10: Clean up `src/devman/domain/__init__.py`

Make sure it doesn't import anything that was deleted. It can be empty or just contain a docstring.

### Task 11: Keep `src/devman/schemas/` as-is

The `schemas/` package (`copier.py`, `questions.py`, `tasks.py`) models copier YAML configuration. This is still useful for template validation in the new design. No changes needed here for the MVP.

### Task 12: Create the file-type copier template

Create the initial copier template that `devman bootstrap` will use to generate new file types. This lives inside the devman store, but for development purposes you should create it as a template directory in the repo that `init_devman_store()` can copy into place.

**Create:** `src/devman/seed_templates/file-type/copier.yml`

```yaml
_subdirectory: ""
_templates_suffix: ".jinja"

file_type:
  type: str
  help: "Name of the file type (e.g., pyproject.toml)"

description:
  type: str
  help: "Brief description of this file type"
  default: ""
```

**Create:** `src/devman/seed_templates/file-type/{{file_type}}/.devman/config.toml.jinja`

```toml
[file_type]
name = "{{ file_type }}"
description = "{{ description }}"

[validation]
script = "workflows/validate.py"
```

**Create:** `src/devman/seed_templates/file-type/{{file_type}}/.devman/workflows/validate.py.jinja`

```python
#!/usr/bin/env python3
"""Validation workflow for {{ file_type }}."""

from pathlib import Path
import sys


def validate(file_path: Path) -> bool:
    """Validate a {{ file_type }} file."""
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return False

    # Add type-specific validation rules here
    print(f"Validated: {file_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate.py <file_path>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1])
    sys.exit(0 if validate(target) else 1)
```

**Create:** `src/devman/seed_templates/file-type/{{file_type}}/.devman/boomtube.yaml.jinja`

```yaml
# Boomtube symlink configuration for {{ file_type }}
links: []
```

Then update `init_devman_store()` in `bootstrap.py` to copy these seed templates into the store's `.devman/.templates/` directory when initializing. You can use `shutil.copytree()` for this.

### Task 13: Update tests

The existing tests in `tests/` are written against the old architecture and will fail. For the MVP, you have two options:

**Option A (recommended for MVP):** Delete or skip the old tests that test removed code. Keep any tests that still apply (like schema tests). Write minimal smoke tests for the new modules:

- `test_bootstrap.py` - Test `init_devman_store()` creates the expected directory structure and git repo. Test `get_current_devman_version()` returns a version string.
- `test_cli.py` - Test that the `init` command runs without error (using a temp directory as the store root).

**Option B (defer):** Mark all old tests as skipped with a `@pytest.mark.skip(reason="Pending refactor")` decorator and write new tests in Phase 2.

**Tests to delete or skip:**
- `test_config.py` - tests old config system
- `test_domain_finder.py` - tests removed DevmanFinder
- `test_domain_models.py` - tests removed ProjectRoot/DevmanDirectory (keep parts that test ValidationResult)
- `test_finder.py` - tests removed finder
- `test_integration.py` - tests old CLI commands
- `test_templates.py` - tests removed TemplateReference/TemplateValidator
- `test_use_cases.py` - tests removed use cases

**Tests to keep:**
- `test_schemas.py` - still valid, schemas package is unchanged
- `test_project_structure.py` - may need updates but project structure tests can be useful

### Task 14: Update `__init__.py`

**File:** `src/devman/__init__.py`

Update the docstring to reflect the new design:

```python
"""Self-bootstrapping file-oriented learning system."""

__version__ = "0.1.0"
```

---

## Execution Order Summary

Here is the recommended order to carry out the refactoring:

1. **Update `pyproject.toml`** - Get dependencies right first
2. **Update `constants.py`** - Define the new constants
3. **Create `bootstrap.py`** - Core initialization and bootstrapping
4. **Create `bootstrap_project.py`** - Project generation
5. **Create `update.py`** - Update mechanism
6. **Rewrite `cli.py`** - New CLI commands
7. **Delete unused files** - Clean out old architecture
8. **Simplify `domain/errors.py`** - Remove unused error types
9. **Simplify `domain/models.py`** - Remove unused value objects
10. **Clean up `domain/__init__.py`** - Fix imports
11. **Leave `schemas/` alone** - Still useful
12. **Create seed templates** - The file-type copier template
13. **Update tests** - Delete or skip broken tests, add smoke tests
14. **Update `__init__.py`** - New docstring

After each task, run `ruff check src/` to catch import errors and unused imports. Run `pytest` after tasks 7-13 to verify nothing is broken.

---

## How to Verify Your Work

After completing all tasks, verify:

1. **`devman init`** should create `~/.devman-store/devman/` with:
   - A `.devman/` directory containing `config.toml`, `.templates/`, and `workflows/`
   - A git repo with a `v0.1.0` tag
   - Run `git -C ~/.devman-store/devman tag` to confirm

2. **`devman bootstrap pyproject.toml`** should create `~/.devman-store/pyproject.toml/` with:
   - A `.devman/config.toml` containing a `[template]` section with the version
   - A `.devman/workflows/validate.py`
   - A `.devman/boomtube.yaml`

3. **`devman update ~/.devman-store/pyproject.toml --dry-run`** should report the current version and say no changes needed (since we just created it at the latest version).

4. **`ruff check src/`** should pass with no errors.

5. **`pytest`** should pass (with skipped tests for deferred functionality).

---

## Architecture Comparison: Before and After

### Before (Old Design)

```
CLI commands:  run, launch, new, config, version, hello
Config:        ~/.config/devman/config.env (pydantic-settings)
Error model:   Result types (Railway-Oriented Programming)
Architecture:  Domain -> Application -> Infrastructure layers
Key classes:   DevmanFinder, ProjectRoot, DevmanDirectory
               TemplateReference, TemplateValidator
               FindDevmanUseCase, RunDevenvUseCase, CreateProjectUseCase
Dependencies:  pydantic-settings, result
```

### After (New Design)

```
CLI commands:  init, bootstrap, project, update
Config:        ~/.devman-store/devman/.devman/config.toml (TOML)
Error model:   Standard Python exceptions (ValueError, RuntimeError)
Architecture:  Flat modules (bootstrap, update, cli)
Key functions: init_devman_store(), bootstrap_file_type()
               bootstrap_project(), update_file_type(), update_project()
Dependencies:  tomli-w, rich
```

The new design is deliberately simpler. It trades the layered architecture for flat, function-based modules. It trades Result types for plain exceptions. It trades pydantic-settings for TOML files in the store. The complexity budget is spent on the self-bootstrapping mechanism and version tracking instead.

---

## Glossary

- **Devman store**: The `~/.devman-store/` directory that contains all devman configuration and generated file types.
- **Meta-type**: The `devman/` directory inside the store. It is itself a git repo that contains templates and workflows.
- **File type**: A directory in the store (e.g., `pyproject.toml/`) containing `.devman/` configuration for managing that file type.
- **Meta-template**: A copier template that generates entire projects (e.g., `pyproj`).
- **Seed template**: The initial copier template (for generating file types) that ships with devman and is copied into the store during `init`.
- **Boomtube**: A library for declarative symlink management. Each file type has a `boomtube.yaml` defining its symlinks.
- **Version**: A git tag on the devman meta-type repo (e.g., `v0.1.0`). Used to pin and track template versions.
