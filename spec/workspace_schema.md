# Workspace schema (llm-core)

This document defines the `.devman/devman.toml` schema used by llm-core.

## Overview

- **Required** fields are listed explicitly.
- All paths are relative to the `.devman/` directory unless noted.
- TOML overrides `.env` if both are present.

## Schema

```toml
[workspace]
name = "my-app"           # required
tags = ["api", "web"]  # optional
group = "client-x"       # optional

[tmuxp]
workspace = "workspace.tmuxp.yaml" # optional
session_name = "my-app"            # optional

[opencode]
interaction = "interaction.md"     # optional
emit_project_config = false         # optional

[nvim]
init = "nvim/init.lua"            # optional
listen = ".devman/.state/nvim.sock" # optional (relative to workspace root)
sessions_dir = "sessions"          # optional
default_session = "home.vim"        # optional
```

## Precedence rules

1. `.devman/devman.toml` is the primary configuration source.
2. `.devman/.env` may supply environment toggles for:
   - `LLM_CORE_TMUXP_WORKSPACE`
   - `LLM_CORE_SESSION_NAME`
3. If TOML fields are present they always override `.env` values.

## Required files

A workspace is valid if `.devman/` exists. The following files are optional but
recommended for full functionality:

- `.devman/devman.toml`
- `.devman/interaction.md`
- `.devman/workspace.tmuxp.yaml`
- `.devman/nvim/init.lua`
- `.devman/sessions/home.vim`
