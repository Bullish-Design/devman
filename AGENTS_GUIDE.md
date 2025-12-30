# AGENTS_GUIDE.md — LLM agent usage & configuration

## Purpose

This guide is for LLM agents working in the `devman` repo. It describes how to
locate workspace metadata, run llm-core, and understand the tooling and config
layout.

## Repository map

- `cli/llm-core`: workspace orchestrator CLI.
- `cli/setup_config.py`: config validation helper for example configs.
- `templates/workspace-min/`: starter `.devman/` workspace layout.
- `spec/workspace_schema.md`: canonical `.devman/devman.toml` schema.
- `src/devman/`: `devman` templating CLI and template registry.

## Workspace discovery

llm-core expects a `.devman/` directory in each workspace root. It reads
`.devman/devman.toml` for metadata. If no workspace is detected, llm-core
rebuilds the index and prompts for a selection.

### Required/optional files

- Required: `.devman/` directory.
- Recommended:
  - `.devman/devman.toml`
  - `.devman/interaction.md`
  - `.devman/workspace.tmuxp.yaml`
  - `.devman/nvim/init.lua`
  - `.devman/sessions/home.vim`

## Running llm-core (agents)

```bash
./cli/llm-core index rebuild
./cli/llm-core
```

Useful commands:

```bash
./cli/llm-core index list
./cli/llm-core index status
./cli/llm-core doctor
./cli/llm-core down
```

## Template generation (devman CLI)

The `devman` CLI generates Nix/devenv-based project scaffolds. It is installed
as a console script via `pyproject.toml` (aliases: `devman`, `dev`, `dt`).

```bash
uv run devman list-templates
uv run devman new demo-app --type api --python 3.11
```

## Configuration references

- `.devman/devman.toml` follows the schema in `spec/workspace_schema.md`.
- `.devman/.env` can define
  - `LLM_CORE_TMUXP_WORKSPACE`
  - `LLM_CORE_SESSION_NAME`
  TOML values override `.env` values.

## Tips for agent operation

- Use `templates/workspace-min/` when you need a minimal `.devman/` scaffold.
- Confirm external dependencies (tmux, tmuxp, nvim, opencode) via
  `./cli/llm-core doctor`.
- When updating workspace metadata, prefer editing `.devman/devman.toml` instead
  of relying on `.env` overrides.
