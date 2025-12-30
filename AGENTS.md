# AGENTS.md — llm-core

## Scope
This file applies to the entire repository.

## Guidelines
- Keep scripts minimal and auditable.
- Never commit secrets or tokens.
- Prefer Python for core logic; keep shell usage to thin wrappers.
- Use `UV` for Python environments and `devenv.sh` for Nix-based workflows.
- Any workspace-specific editor config must live under `.devman/` in templates.
