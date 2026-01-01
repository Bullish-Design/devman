# Getting Started

## Overview

devman is a minimal workspace orchestrator for tmuxp, Claude Code, and Neovim.
It discovers `.devman/` workspaces, builds an index, and launches tmux sessions
with the right editor context.

## Prerequisites

- **Python 3.11+** (use `uv` for environments).
- **tmux** + **tmuxp** for session management.
- **Neovim** (`nvim`) if you want editor/session bootstrapping.
- **Claude Code** (`claude`) is required for Claude integration.

## Create a workspace

A workspace is any project root that contains a `.devman/` directory. The
minimum requirement is the directory itself, but a `devman.toml` file provides
metadata and paths.

Example `.devman/devman.toml`:

```toml
[workspace]
name = "my-app"

[tmuxp]
workspace = "workspace.tmuxp.yaml"
session_name = "my-app"

[claude_code]
interaction = "interaction.md"
emit_project_config = false

[nvim]
init = "nvim/init.lua"
listen = ".devman/.state/nvim.sock"
sessions_dir = "sessions"
default_session = "home.vim"
```

For the full schema, see [`docs/workspace-schema.md`](workspace-schema.md).

## Build the index

```bash
./cli/devman index rebuild
```

## Launch devman

```bash
./cli/devman
```

## Switch workspaces

```bash
./cli/devman switch <name|tag|path>
```

## Next steps

- Review the workspace schema in [`docs/workspace-schema.md`](workspace-schema.md).
- Configure Claude Code in [`docs/claude-integration.md`](claude-integration.md).
- If something fails, check [`docs/troubleshooting.md`](troubleshooting.md).
