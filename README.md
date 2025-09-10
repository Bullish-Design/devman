# devman (MVP, Copier-based)

A thin CLI over [Copier] with three built-in templates:
- `python-lib` – minimal library
- `python-cli` – Typer-powered CLI
- `fastapi-api` – FastAPI service

Core infra is included by default: **Nix (devenv.nix + .envrc), Docker (Dockerfile + compose), and a Justfile**.
Copier's answers live at `.devman/devman_config.yml` in generated projects.

## Install (editable)
```bash
pip install -e .
```

## Usage
```bash
# list built-in templates
devman list-templates

# generate a project from a built-in
devman generate my-lib --template python-lib

# from a local path or Git URL
devman generate my-api --template https://github.com/yourorg/your-template.git --ref v1.0.0

# disable infra if you want
devman generate my-cli --template python-cli --no-nix --no-docker --no-just
```

[Copier]: https://copier.readthedocs.io/
