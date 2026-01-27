# DevMan Development Guide

## CLI Skeleton

**Application help**

Use this exact help string for the Typer app:

```
DevMan CLI for managing local development environments.
```

### `init`

Docstring:

```
Initialize a new DevMan project using a Copier template.
```

Options:

- `--template`, `-t` (default: `python-devenv`)
  - Help: `Copier template name or path.`
- `--output`, `-o` (default: `.`)
  - Help: `Output directory for the generated project.`
- `--force`, `-f`
  - Help: `Overwrite existing files if they already exist.`

### `validate`

Docstring:

```
Validate the current DevMan project configuration.
```

Options:

- `--config`, `-c` (default: `devman.yaml`)
  - Help: `Path to the DevMan config file.`
- `--strict`, `-s`
  - Help: `Enable strict validation checks.`

### `test`

Docstring:

```
Run the DevMan test container for the current repository.
```

Options:

- `--container-prefix`, `-p` (default: `devman-test`)
  - Help: `Prefix to use when naming the test container.`
- `--reuse`, `-r`
  - Help: `Reuse an existing test container if available.`

### `clean`

Docstring:

```
Remove DevMan-generated artifacts from the working tree.
```

Options:

- `--all`, `-a`
  - Help: `Remove all generated artifacts, including caches.`
- `--dry-run`
  - Help: `Show what would be removed without deleting anything.`

## Tooling Note

`devenv.nix` must provide the `just`, `jj`, and `uv` tools.
