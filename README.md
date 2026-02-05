# Devman: Self-Bootstrapping File-Oriented Learning System

Devman is a minimal self-bootstrapping system that uses [copier](https://copier.readthedocs.io/) templates to generate and manage file type configurations. It tracks template versions via git tags and provides update mechanisms to evolve configurations over time.

## Core Concepts

**File Types** - Devman manages configuration for specific file types (e.g., `pyproject.toml`, `devenv.nix`). Each file type lives in the devman store as a directory with its own `.devman/` configuration, validation workflows, and boomtube symlink definitions.

**Meta-Templates** - Higher-level templates (e.g., `pyproj`) that orchestrate multiple file types to scaffold entire projects.

**Self-Bootstrapping** - Devman uses copier templates to extend itself. New file types are created by running a copier template that lives inside devman's own configuration.

**Version Tracking** - Git tags on the devman store repository provide reproducible, pinnable template versions. New bootstraps automatically capture the current version; users can also pin to a specific version.

## MVP Scope

**Included:**
- File type bootstrapping via copier templates
- Git-based template versioning (automatic tag capture)
- Template update mechanism via copier
- Project generation from meta-templates (e.g., `pyproj`)
- Type-level validation workflows
- Boomtube symlink management
- Four core CLI commands: `init`, `bootstrap`, `project`, `update`

**Deferred to later phases:**
- Testing framework (Phase 2)
- Instance-level validation (Phase 2)
- List/query commands (filesystem inspection suffices for MVP)
- Auto-sync workflows (manual workflow only)

## Installation

```bash
# Install as a UV tool
uv tool install -e .

# Or install from source in development mode
uv pip install -e ".[dev]"
```

## Usage

### Initialize the devman store

```bash
devman init
# Creates ~/.devman-store/devman/ with git repo and v0.1.0 tag
```

### Bootstrap a new file type

```bash
# Uses current template version automatically
devman bootstrap pyproject.toml

# Pin to a specific version
devman bootstrap devenv.nix --version v0.1.0
```

### Create a project from a meta-template

```bash
# Uses current template version automatically
devman project pyproj ~/projects/my-lib

# Pin to a specific version
devman project pyproj ~/projects/my-lib --version v1.0.0
```

### Update a file type or project

```bash
# Update file type to latest
devman update ~/.devman-store/pyproject.toml

# Update to a specific version
devman update ~/.devman-store/pyproject.toml --version v0.2.0

# Preview changes without applying
devman update ~/.devman-store/pyproject.toml --dry-run

# Update a project
devman update ~/projects/my-lib
```

## Architecture

### Devman Store Structure

```
~/.devman-store/
  devman/                          # Meta-type configuration (git repo)
    .git/
      refs/tags/v0.1.0            # Template versions as git tags
    .devman/
      .templates/
        file-type/                # Copier template for new file types
          copier.yml
          {{file_type}}/
            .devman/
              config.toml.jinja
              workflows/
                validate.py.jinja
              boomtube.yaml.jinja

        pyproj/                   # Python project meta-template
          copier.yml
          {{project_name}}/
            pyproject.toml.jinja
            devenv.nix.jinja
            src/{{package_name}}/
              __init__.py.jinja
              __main__.py.jinja
            README.md.jinja
            .devman-bootstrap.py

      workflows/
        bootstrap.py
        bootstrap_project.py
        update.py

      config.toml

  pyproject.toml/                 # Generated file type
    .devman/
      config.toml                 # Contains template version info
      workflows/
        validate.py
      boomtube.yaml

  devenv.nix/                     # Generated file type
    .devman/
      config.toml
      workflows/
        validate.py
      boomtube.yaml
```

### Version Metadata

Each file type tracks its template origin:

```toml
# ~/.devman-store/pyproject.toml/.devman/config.toml
[file_type]
name = "pyproject.toml"
description = "Python project configuration"

[template]
name = "file-type"
devman_version = "v0.1.0"
created_at = "2026-02-04T10:00:00Z"

[validation]
script = "workflows/validate.py"
```

Projects track their meta-template origin:

```toml
# ~/projects/my-lib/.devman-project.toml
[project]
name = "my-lib"
description = "My awesome library"

[template]
name = "pyproj"
version = "v1.0.0"
created_at = "2026-02-04T10:00:00Z"
file_types = ["pyproject.toml", "devenv.nix"]
```

## Template Evolution Workflow

1. Edit templates in `~/.devman-store/devman/.devman/.templates/`
2. Commit and tag: `git tag -a v0.2.0 -m "Add UV validation"`
3. Update existing types: `devman update ~/.devman-store/pyproject.toml`
4. New bootstraps automatically use the latest tagged version

## Key Design Principles

1. **Self-bootstrapping** - Devman uses copier to extend itself
2. **Version tracking** - Git tags provide reproducible builds
3. **Automatic versioning** - Captures current version by default
4. **Explicit pinning** - Users can override with specific versions
5. **Update mechanism** - Copier handles template evolution
6. **Composable templates** - Meta-templates orchestrate file types
7. **Type-level validation** - Common checks for all instances
8. **Boomtube symlinks** - Robust link management
9. **TOML everywhere** - Consistent metadata format
10. **Python-native** - All workflows in Python with uv

## Implementation Roadmap

### Phase 1: MVP (Current)

1. `devman init` with git initialization
2. File-type copier template
3. `devman bootstrap` with version capture
4. `pyproj` copier template
5. `devman project` with version flag
6. `devman update` for file types and projects
7. Boomtube integration

### Phase 2: Enhanced Validation

- Instance-level validation support
- Validation hierarchy (type -> instance)
- `devman validate` command
- Validation caching and result reporting

### Phase 3: Testing Framework

- Test case structure and runner
- `--test` flag on bootstrap command
- Test generators for file types

### Phase 4: Discovery and Tooling

- `devman list-types` and `devman list-projects` commands
- Version comparison utilities
- Migration helpers
- Template documentation generator

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```

## Dependencies

- [typer](https://typer.tiangolo.com/) - CLI framework
- [copier](https://copier.readthedocs.io/) - Template engine
- [rich](https://rich.readthedocs.io/) - Terminal formatting
- [tomli](https://github.com/hukkin/tomli) / [tomli-w](https://github.com/hukkin/tomli-w) - TOML reading/writing
- [boomtube](https://github.com/Bullish-Design/boomtube) - Symlink management
- [uv](https://github.com/astral-sh/uv) - Python packaging

## License

MIT License
