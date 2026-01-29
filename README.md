# devman

devman is a CLI for managing devenv-based projects and creating new projects from copier templates.

## Features

- **Project Finder**: Locate and run commands in the nearest `.devman` directory
- **Template System**: Create new projects from copier templates (local or git)
- **Configuration**: Store project root directory for scoped searches
- **Validation**: Validate copier templates before use

## Installation

### As UV Tool (Recommended)
```bash
uv tool install git+https://github.com/Bullish-Design/devman.git
```

### From Source
```bash
git clone https://github.com/Bullish-Design/devman.git
cd devman
uv sync
```

## Usage

### Create New Project
```bash
# From local template
devman new ./my-template ./new-project

# From git repository
devman new https://github.com/user/template.git ./new-project

# With data overrides
devman new gh:user/template ./project --data project_name=MyApp --data use_docker=true

# Skip validation
devman new ./template ./project --no-validate
```

### Find and Run DevEnv
```bash
# Run devenv command in nearest .devman directory
devman run up

# Set projects root to limit search scope
devman config --projects-root ~/projects
devman run shell
```

### Validate Templates
```bash
# Using CLI
uv run scripts/validate_copier.py ./my-template

# Generate example template
uv run scripts/generate_example.py ./copier.yaml
```

## Template Format

Templates use the [copier](https://copier.readthedocs.io/) format:
```yaml
_subdirectory: template
_templates_suffix: .jinja

project_name:
  type: str
  help: What is your project name?

use_docker:
  type: bool
  default: false

_tasks:
  - git init
  - echo 'Done!'
```

See `tests/fixtures/example_copier.yaml` for a complete example.

## Available Commands

- `devman run [ARGS...]`: Run `devenv` with the provided arguments in the nearest `.devman` directory.
- `devman new TEMPLATE DESTINATION`: Create a new project from a copier template.
- `devman config --projects-root PATH`: Set the default projects root directory.
- `devman config --show`: Show the current configuration.
- `devman version`: Print the current devman version.
- `devman hello NAME`: Print a greeting.

## Architecture

devman follows a layered architecture:

### Domain Layer (`src/devman/domain/`)
Pure business logic with no framework dependencies:
- **Models**: Value objects (`ProjectRoot`, `DevmanDirectory`, `ValidationResult`)
- **Errors**: Structured error types for all failure cases
- **Services**: `DevmanFinder` for .devman directory location
- **Protocols**: Interfaces for dependency inversion

### Application Layer (`src/devman/application/`)
Use cases orchestrating domain objects:
- `FindDevmanUseCase`: Locate .devman directory
- `RunDevenvUseCase`: Execute devenv commands
- `ValidateTemplateUseCase`: Validate template structure

### Infrastructure Layer
- **CLI** (`cli.py`): Typer-based command interface
- **Schemas** (`schemas/`): Pydantic models for copier.yaml
- **Templates** (`templates.py`): Template reference and validation

### Error Handling
Uses Railway-Oriented Programming with `Result` types:
- `Ok(value)` for success
- `Err(error)` for failures
- No exceptions in business logic
- All errors are typed domain objects

Example:
```python
result = ProjectRoot.create(path)
if result.is_ok():
    root = result.unwrap()
    # ... use root
else:
    error = result.unwrap_err()
    print(f"Failed: {error}")
```

## Development
```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
pytest

# Run linters
ruff check src/
mypy src/
```
