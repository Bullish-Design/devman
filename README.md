# DevMan

DevMan is a DevEnv project templating system for NixOS development environments with container-based testing.

## Features

- Quick Setup: Initialize complete devenv.nix projects in seconds
- Pre-flight Validation: Catch template errors before generation
- Container Testing: Validate environments in isolation
- Template System: Copier-based templates with Jinja2
- Version Control: Deep jujutsu integration

## Installation

### Requirements

- Python 3.11+
- Nix with flakes enabled
- nixos-container (for testing)
- jujutsu (recommended)
- copier
- just
- uv

### Install DevMan

```bash
# Clone repository
git clone https://github.com/Bullish-Design/devman.git
cd devman

# Install with uv
uv pip install -e .

# Or use directly
devman --help
```

## Quick Start

```bash
# Initialize a new Python project
devman init --project-name my-project

# Validate the configuration
devman validate

# Test in container (requires sudo)
sudo devman test

# Clean up
devman clean --all
```

## Project Structure

DevMan follows its own conventions - all development files live in `.devman/`:

```
your-project/
├── .devman/              # All devenv files here
│   ├── devenv.nix       # Generated environment
│   ├── justfile         # Development commands
│   ├── pyproject.toml   # Project config
│   ├── .envrc           # direnv integration
│   └── state.yaml       # Template metadata
├── .jj/                 # Version control
├── src/                 # Your code
└── tests/               # Your tests
```

## Commands

### devman init

Initialize a new DevMan project:

```bash
devman init [OPTIONS]

Options:
  --devman-dir PATH         Directory for devenv files (default: .devman)
  --template NAME           Template to use (default: python-devenv)
  --python-version VERSION  Python version (default: 3.12)
  --project-name NAME       Project name (default: current directory)
  --force                   Overwrite existing directory
```

### devman validate

Validate existing configuration:

```bash
devman validate [OPTIONS]

Options:
  --devman-dir PATH  Directory to validate (default: .devman)
```

### devman test

Test environment in container:

```bash
sudo devman test [OPTIONS]

Options:
  --devman-dir PATH      Directory to test (default: .devman)
  --keep-container       Don't remove container after test
  --container-name NAME  Override container name
```

### devman clean

Clean generated artifacts:

```bash
devman clean [OPTIONS]

Options:
  --devman-dir PATH       Directory to clean (default: .devman)
  --all                   Remove all artifacts including caches
  --container-name NAME   Specific container to remove
  --all-containers        Remove all devman containers
  --dry-run               Show what would be removed
```

## Templates

### python-devenv

Default Python template with:

- Python (configurable version)
- uv package manager
- just command runner
- Optional PostgreSQL
- Optional Redis

### Creating Custom Templates

Templates use Copier with Jinja2:

```
templates/
└── my-template/
    ├── copier.yaml        # Template config
    ├── devenv.nix.j2      # Nix configuration
    ├── justfile.j2        # Commands
    └── pyproject.toml.j2  # Python config
```

Use your template:

```bash
devman init --template ./templates/my-template
```

## Container Testing

DevMan tests environments in nixos-containers for isolation:

```bash
# Create unique container per branch
sudo devman test

# Container name: devman-{branch}-{revision}
# Example: devman-main-abc12345

# Keep container for debugging
sudo devman test --keep-container

# Shell into container
sudo just -f .devman/justfile container-shell devman-main-abc12345

# List containers
just -f .devman/justfile container-list

# Clean all containers
sudo devman clean --all-containers
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/Bullish-Design/devman.git
cd devman

# Enter devenv
cd .devman
direnv allow

# Install dependencies
just setup

# Run tests
just test

# Lint code
just lint

# Format code
just format
```

### Running Tests

```bash
# All tests
just test

# Specific file
uv run pytest tests/test_cli.py -v

# With coverage
uv run pytest --cov=src/devman --cov-report=html

# Watch mode
just test-watch
```

### Project Structure

```
devman/
├── .devman/              # DevMan's own development environment
│   ├── devenv.nix
│   └── justfile
├── src/devman/           # Main package
│   ├── cli.py           # CLI entry point
│   ├── commands/        # Command implementations
│   ├── container.py     # Container operations
│   ├── template.py      # Template handling
│   └── validation.py    # Validation logic
├── templates/            # Bundled templates
│   └── python-devenv/
├── tests/               # Test suite
└── pyproject.toml       # Package configuration
```

## Troubleshooting

### Container Creation Fails

```bash
# Check nixos-container is available
which nixos-container

# Verify sudo access
sudo -v

# Check existing containers
nixos-container list
```

### Template Validation Fails

```bash
# Check copier is installed
copier --version

# Verify template structure
ls -la templates/python-devenv/

# Test template manually
copier copy templates/python-devenv /tmp/test-output
```

### Nix Parse Errors

```bash
# Validate syntax manually
nix-instantiate --parse .devman/devenv.nix

# Check for template variable issues
cat .devman/devenv.nix | grep -E '{{|}}'
```

## License

MIT
