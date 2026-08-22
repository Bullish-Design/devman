# Interaction Design

This workspace coordinates multiple repositories that together define a NixOS
configuration (system config, Home Manager, overlays, secrets).

## Workspace layout

- Root: `repos/`
- Example repos:
  - `repos/nixos-config`
  - `repos/home-config`
  - `repos/nixpkgs`
  - `repos/secrets`

## Sessions + tmuxp

- Homepage session: `.devman/sessions/home.vim` (mini.sessions compatible)
- tmuxp workspace: `.devman/workspace.tmuxp.yaml`

## Switching behavior

- `llm-core switch <workspace>` should:
  1. Ensure Neovim is in the target workspace directory.
  2. Load the homepage session (`:source .devman/sessions/home.vim`).
  3. Keep repo tabs aligned with the `repos/` layout.
