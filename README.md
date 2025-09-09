# devenv-templater

🚀 Generate NixOS devenv projects from templates with container support.

## Installation

```bash
# Install with uv
uv tool install devenv-templater

# Or install from source
git clone https://github.com/example/devenv-templater
cd devenv-templater
uv sync --all-extras
uv run devenv-templater --help
```

## Quick Start

```bash
# Create FastAPI project
devenv-templater new myapi --type api --database postgresql

# Create web app with local dependencies
devenv-templater new webapp --type web --local-deps shared-utils

# Create CLI tool (no containers)
devenv-templater new mytool --type cli --containers none

# List available templates
devenv-templater list-templates

# Update existing project
cd myproject
devenv-templater update myproject --type api
```

## Project Types

- **api**: FastAPI + uvicorn, async-ready
- **web**: Flask web application  
- **cli**: Typer-based command line tool
- **ml**: Machine learning with jupyter, pandas, scikit-learn
- **lib**: Python library for publishing

## Container Types

- **devenv**: Native devenv container generation (default)
- **docker**: Dockerfile + docker-compose.yml
- **nixos**: NixOS containers configuration
- **none**: No containers

## Features

- ✅ **devenv.nix** generation with Python, uv, containers
- ✅ **justfile** with project-specific tasks
- ✅ **pyproject.toml** with dependencies and tooling
- ✅ Local dependency support via uv sources
- ✅ Database integration (PostgreSQL/SQLite)
- ✅ Container generation (devenv/Docker/NixOS)
- ✅ Rich CLI with validation and help

## Generated Structure

```
myproject/
├── devenv.nix              # Development environment
├── justfile                # Task automation
├── pyproject.toml          # Python project config
├── .envrc                  # Direnv activation
├── docker-compose.yml      # Services (if containers)
├── src/myproject/          # Source code
├── tests/                  # Test files
└── README.md               # Project documentation
```

## Workflow

```bash
# 1. Create project
devenv-templater new myapi --type api

# 2. Enter development
cd myapi
just shell                 # Enter devenv (or automatic with direnv)

# 3. Start development
just dev                   # Start dev server
just test                  # Run tests
just lint                  # Format and lint

# 4. Container workflow (if enabled)
just build                 # Build container
just run                   # Run containerized app
just push                  # Push to registry
```

## Local Dependencies

For shared libraries across projects:

```bash
# Create workspace structure
workspace/
├── shared-lib/           # Shared library
├── project-a/           # Uses ../shared-lib  
└── project-b/           # Uses ../shared-lib

# Generate with local deps
devenv-templater new project-a --local-deps shared-lib
```

Auto-generates in `pyproject.toml`:
```toml
[tool.uv.sources]
shared-lib = { path = "../shared-lib" }
```

## CLI Reference

```bash
devenv-templater new <name>                    # Create project
  --type {api,web,cli,ml,lib}                  # Project type
  --python 3.11                               # Python version
  --containers {devenv,docker,nixos,none}      # Container type  
  --database {postgresql,sqlite}              # Database
  --deps package1 package2                    # Extra dependencies
  --local-deps lib1 lib2                      # Local dependencies
  --force                                     # Overwrite existing

devenv-templater update <name>                 # Update project files
devenv-templater list-templates                # Show available types
devenv-templater config                        # Show configuration
devenv-templater init-templates                # Reset templates
```

## Template Customization

Templates stored in `~/.devenv-templates/`:

```bash
# Edit templates
$EDITOR ~/.devenv-templates/devenv.nix.j2
$EDITOR ~/.devenv-templates/justfile.j2

# Reinitialize defaults
devenv-templater init-templates --force
```

## Requirements

- NixOS with devenv
- uv for Python package management
- Docker (if using containers)
- just command runner