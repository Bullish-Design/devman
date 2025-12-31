# workspace-nixos-collection

Example llm-core workspace for a NixOS configuration split across multiple repos.

## Layout

```
repos/
  nixos-config/
  home-config/
  nixpkgs/
  secrets/
```

Rename or remove repos as needed; update `.devman/workspace.tmuxp.yaml` and
`.devman/sessions/home.vim` accordingly.

## Usage

1. Copy this template into a new project.
2. Populate the `repos/` directory.
3. Launch `llm-core` from the project root.
