# Troubleshooting

## Verify external tools

Run the doctor command to check for required dependencies:

```bash
./cli/devman doctor
```

Ensure these tools are installed:

- `tmux`
- `tmuxp`
- `nvim` (if you use Neovim integration)
- `claude`

## Workspace not found

- Confirm the workspace root contains a `.devman/` directory.
- Rebuild the index:

```bash
./cli/devman index rebuild
```

## tmuxp session issues

- Verify the `workspace.tmuxp.yaml` path in `.devman/devman.toml`.
- Confirm the file exists relative to `.devman/`.

## Claude Code not detected

- Ensure the `claude` CLI is on your `PATH`.
- Re-run `./cli/devman doctor` to confirm availability.
