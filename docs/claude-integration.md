# Claude Code integration

## Requirements

Claude Code integration requires the `claude` CLI to be installed and available
on your `PATH`. You can verify this with:

```bash
claude --version
```

## Workspace configuration

Configure Claude Code in `.devman/devman.toml`:

```toml
[claude_code]
interaction = "interaction.md"     # optional
emit_project_config = false         # optional
```

- `interaction` points to the interaction guide used by Claude Code.
- `emit_project_config` controls whether devman writes `.claude/project.json`
  and an optional `CLAUDE.md` to the workspace root.

## What devman writes

When enabled, devman will:

- Create `.claude/settings.json` with workspace metadata.
- Optionally emit `.claude/project.json` plus `CLAUDE.md` instructions so Claude
  Code can load workspace-specific context.

## Helpful commands

```bash
./cli/devman doctor
./cli/devman up
./cli/devman bootstrap
```

If the CLI is missing, these commands will surface a message pointing you to
https://claude.ai/code.
