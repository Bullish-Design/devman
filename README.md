# DevMan

DevMan is a DevEnv project templating system for NixOS development environments.

## Installation requirements

- Python 3.11+
- Copier (`copier`)
- Nix (`nix-instantiate`)
- `just`
- `jj`

## Quick Start

```bash
./devman.py init --devman-dir .devman --template python-devenv --project-name my-project
./devman.py validate --devman-dir .devman
./devman.py test --devman-dir .devman
./devman.py clean --devman-dir .devman
```

## Commands

### init

Initialize a new DevMan project using a Copier template.

```bash
./devman.py init [OPTIONS]
```

Options:

- `--devman-dir`, `-d` (default: `devman`): Directory where the DevMan project should be created.
- `--template`, `-t` (default: `python-devenv`): Copier template name or path.
- `--python-version` (default: `3.12`): Python version to configure in the project.
- `--project-name`: Project name to use in the generated files.
- `--force`, `-f`: Overwrite existing files if they already exist.

### validate

Validate the current DevMan project configuration.

```bash
./devman.py validate [OPTIONS]
```

Options:

- `--devman-dir` (default: `.devman`): Path to .devman directory.

### test

Run the DevMan test container for the current repository.

```bash
./devman.py test [OPTIONS]
```

Options:

- `--devman-dir` (default: `.devman`): Path to .devman directory.
- `--keep-container`: Don't remove container.
- `--container-name`: Override container name.

### clean

Remove DevMan-generated artifacts from the working tree.

```bash
./devman.py clean [OPTIONS]
```

Options:

- `--devman-dir` (default: `.devman`): Path to .devman directory.
- `--all`, `-a`: Remove all generated artifacts, including caches.
- `--container-name`: Override container name.
- `--all-containers`: Remove all DevMan containers.

## Development

```bash
uv sync --dev
./test_devman.sh
```

## License

MIT
