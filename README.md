# devman

Minimal workspace orchestrator for tmuxp + Claude Code + Neovim.

## Features

- Discover `.devman/` workspaces under configured roots.
- Cache index at `~/.cache/devman/index.json`.
- Launch tmuxp sessions with Claude Code + Neovim windows.
- Switch workspaces and load Neovim sessions via remote commands.
- Claude Code requires the `claude` CLI to be installed.

## Quick start

```bash
./cli/devman index rebuild
./cli/devman
```

## NixOS + Home Manager (flakes)

Use a flake input pinned with `git+` to avoid GitHub API rate limits.

```nix
inputs.devman.url = "git+https://github.com/<org>/<repo>?ref=<branch>&rev=<commit>";
# Optional: add &dir=path/to/subdir if the flake isn't at the repo root.
```

Home Manager:

```nix
home.packages = [
  inputs.devman.packages.${pkgs.system}.default
];
```

NixOS:

```nix
environment.systemPackages = [
  inputs.devman.packages.${pkgs.system}.default
];
```

Usage:

```bash
devman index rebuild
devman
```

## Development

Use `devenv` + `uv` for local development.

```bash
uv sync
uv run ./cli/devman --help
```

## Config validation helper

Use `cli/setup_config.py` to validate `.env.example`, `.toml.example`, or
`.yaml.example` files against their target configs.

```bash
uv run ./cli/setup_config.py validate .env.example
```

## Templates

- `templates/workspace-min`: starter `.devman/` layout for a single repo.
- `templates/workspace-nixos-collection`: example multi-repo NixOS workspace
  with tmuxp + mini.sessions defaults.
