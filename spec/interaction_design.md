# Interaction Design Document (devman)

This document defines how Claude Code should shape the interaction layer for a
workspace. It is designed to be copied into `.devman/interaction.md` and
customized per repository.

## Scope and ownership

- Claude Code must only edit files under `.devman/` unless explicitly requested.
- devman never ships global Neovim configuration. Any editor changes must live
  under `.devman/nvim/`.
- Sessions are stored in `.devman/sessions/` and should be mini.sessions
  compatible.

## Interaction goals

- Provide a predictable “homepage” session that opens a landing buffer or
  project overview.
- Make switching between workspaces fast and reliable.
- Keep commands documented in `.devman/interaction.md`.

## Editing Neovim configuration

- Keep `init.lua` minimal.
- Add keymaps or plugins only when requested.
- Use `.devman/nvim/init.lua` as the entrypoint and keep any additional
  Lua files under `.devman/nvim/lua/`.

## Sessions

- Each workspace should have a default session (e.g. `home.vim`).
- Sessions should be updated when switching workspaces.
- If multiple sessions exist, document them in `.devman/interaction.md`.

## Multi-workspace behavior

- devman can load multiple workspaces into its index.
- When switching, Claude Code should:
  1. Ensure Neovim is in the target workspace directory.
  2. Load the target workspace session (`:source .devman/sessions/home.vim`).
  3. Update any interaction instructions to match the active workspace.

## Example section for `.devman/interaction.md`

```
# Interaction Design

- Homepage: `.devman/sessions/home.vim`
- Keymaps: keep workspace-specific mappings in `.devman/nvim/init.lua`
- Switching: `devman switch <workspace>` should load the session and update
  working directory.
```
