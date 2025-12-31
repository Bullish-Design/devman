# llm-core

Minimal workspace orchestrator for tmuxp + Claude Code + Neovim.

## Features

- Discover `.devman/` workspaces under configured roots.
- Cache index at `~/.cache/llm-core/index.json`.
- Launch tmuxp sessions with Claude Code + Neovim windows.
- Switch workspaces and load Neovim sessions via remote commands.
- Claude Code support is optional if the `claude` binary is available.

## Quick start

```bash
./cli/llm-core index rebuild
./cli/llm-core
```

## NixOS + Home Manager (flakes)

Use a flake input pinned with `git+` to avoid GitHub API rate limits.

```nix
inputs.llm-core.url = "git+https://github.com/<org>/<repo>?ref=<branch>&rev=<commit>";
# Optional: add &dir=path/to/subdir if the flake isn't at the repo root.
```

Home Manager:

```nix
home.packages = [
  inputs.llm-core.packages.${pkgs.system}.default
];
```

NixOS:

```nix
environment.systemPackages = [
  inputs.llm-core.packages.${pkgs.system}.default
];
```

Usage:

```bash
llm-core index rebuild
llm-core
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

- `templates/workspace-min`: starter `.devman/` layout for a single repo.
- `templates/workspace-nixos-collection`: example multi-repo NixOS workspace
  with tmuxp + mini.sessions defaults.
