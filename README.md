# llm-core

Minimal workspace orchestrator for tmuxp + OpenCode + Neovim.

## Features

- Discover `.devman/` workspaces under configured roots.
- Cache index at `~/.cache/llm-core/index.json`.
- Launch tmuxp sessions with OpenCode + Neovim windows.
- Switch workspaces and load Neovim sessions via remote commands.
- OpenCode support is optional if the `opencode` binary is available.

## Quick start

```bash
./cli/llm-core index rebuild
./cli/llm-core
```

## Development

Use `devenv` + `uv` for local development.

```bash
uv sync
uv run ./cli/llm-core --help
```

## Config validation helper

Use `cli/setup_config.py` to validate `.env.example`, `.toml.example`, or
`.yaml.example` files against their target configs.

```bash
uv run ./cli/setup_config.py validate .env.example
```

## Templates

The `templates/workspace-min` directory provides a starter `.devman/` layout.
