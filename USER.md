# USER.md — llm-core quickstart & user guide

## Overview

llm-core is a minimal workspace orchestrator for tmuxp + OpenCode + Neovim that
finds `.devman/` workspaces, indexes them, and launches the matching tmux sessions
and editor setup. This repo also ships the `devman` CLI for generating
Nix-based project templates.

## Prerequisites

- **Python 3.11+** (use `uv` for environments).
- **tmux** + **tmuxp** for session management.
- **Neovim** (`nvim`) if you want session bootstrapping.
- **OpenCode** (`opencode`) is optional.
- **devenv + Nix** if you plan to use Nix-based templates.

## Quickstart (llm-core)

1. **Create or copy a `.devman/` workspace**
   - Use the starter template in `templates/workspace-min/`.
   - Place the `.devman/` directory in the project root you want to manage.

2. **Build the workspace index**

   ```bash
   ./cli/llm-core index rebuild
   ```

3. **Launch llm-core from a workspace**

   ```bash
   ./cli/llm-core
   ```

4. **Switch workspaces by name, tag, or path**

   ```bash
   ./cli/llm-core switch <query>
   ```

## Workspace configuration

llm-core looks for `.devman/devman.toml` plus supporting assets like tmuxp and
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
./cli/llm-core index list
./cli/llm-core index status
./cli/llm-core doctor
./cli/llm-core down
```

## Project templating (devman CLI)

The `devman` CLI generates a Python project scaffold with Nix/devenv support.
It is separate from llm-core’s workspace orchestration, but pairs well with
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

- Run `./cli/llm-core doctor` to confirm external tools are installed.
- If llm-core can’t find workspaces, confirm `.devman/` exists in the project
  root and rebuild the index.
- For tmuxp sessions, ensure the `workspace.tmuxp.yaml` path in
  `.devman/devman.toml` is correct.
