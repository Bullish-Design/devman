# USER.md — devman quickstart & user guide

## Overview

devman is a minimal workspace orchestrator for tmuxp + Claude Code + Neovim that
finds `.devman/` workspaces, indexes them, and launches the matching tmux sessions
and editor setup. This repo also ships the `devman` CLI for generating
Nix-based project templates.

## Prerequisites

- **Python 3.11+** (use `uv` for environments).
- **tmux** + **tmuxp** for session management.
- **Neovim** (`nvim`) if you want session bootstrapping.
- **Claude Code** (`claude`) is required.
- **devenv + Nix** if you plan to use Nix-based templates.

## Quickstart (devman)

1. **Create or copy a `.devman/` workspace**
   - Use the starter template in `templates/workspace-min/`.
   - Place the `.devman/` directory in the project root you want to manage.

2. **Build the workspace index**

   ```bash
   ./cli/devman index rebuild
   ```

3. **Launch devman from a workspace**

   ```bash
   ./cli/devman
   ```

4. **Switch workspaces by name, tag, or path**

   ```bash
   ./cli/devman switch <query>
   ```

## Workspace configuration

devman looks for `.devman/devman.toml` plus supporting assets like tmuxp and
Neovim session files. See the full schema in `spec/workspace_schema.md`. The
minimum requirement is a `.devman/` directory in the workspace root.

Common optional files:

- `.devman/devman.toml`
- `.devman/interaction.md`
- `.devman/workspace.tmuxp.yaml`
- `.devman/nvim/init.lua`
- `.devman/sessions/home.vim`

## Useful commands

```bash
./cli/devman index list
./cli/devman index status
./cli/devman doctor
./cli/devman down
```

## Project templating (devman CLI)

The `devman` CLI generates a Python project scaffold with Nix/devenv support.
It is separate from devman’s workspace orchestration, but pairs well with
`.devman/` workspaces.

```bash
uv run devman list-templates
uv run devman new my-service --type api --python 3.11
```

### Updating an existing project

```bash
uv run devman update my-service --type api --python 3.11
```

## Configuration validation helper

Use `cli/setup_config.py` to validate example config files against their targets.

```bash
uv run ./cli/setup_config.py validate .env.example
```

## Troubleshooting

- Run `./cli/devman doctor` to confirm external tools are installed.
- If devman can’t find workspaces, confirm `.devman/` exists in the project
  root and rebuild the index.
- For tmuxp sessions, ensure the `workspace.tmuxp.yaml` path in
  `.devman/devman.toml` is correct.
