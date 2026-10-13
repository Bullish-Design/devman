# Paseo Claude version in devman — 2026-10-13

## Failure

Paseo reported: `Claude Code 2.1.207 does not support this model; version 2.1.280 or newer is required`.
The request failed at the Claude API version check, before a model response.

## Local path

- `nix-meta` installs Claude Code 2.1.291 through `profiles/agent.nix`.
  `/run/current-system/sw/bin/claude --version` returned `2.1.291`.
- `nix-paseo` launches the built-in `claude` provider through
  `paseo-agent-shell claude`. That launcher enters the worktree's `devenv shell`.
- Before the change, `devman/devenv.nix` installed a second Claude package.
  `devman/devenv.lock` resolved it at revision
  `b8106a2893d7b1c5b116bebbcf17df80ead302b1`.
  Both `devenv shell -- claude --version` and the Paseo launcher returned
  `2.1.207`. The repo shell put this package before the system profile on `PATH`.
- `devenv.lock` is ignored by this repository's `.gitignore`. Its local pin
  can therefore lag behind the host pin without a tracked change.

The separate package originally supported this repository's `agent:review`
workflow. Stage 4 recorded that the task ran inside `devenv` and called the
repo-installed CLI. The server now installs Claude through the `nix-meta` agent
profile. Other checked project shells do not add a Claude package.

## Change and verification

Remove `claude-code` from `devenv.yaml` and `devenv.nix`. Keep the workflow's
`claude` command; it now resolves the host agent profile package.

After the change, `devenv shell -- sh -c 'command -v claude; claude --version'`
returned `/run/current-system/sw/bin/claude` and `2.1.291`. Running the actual
Paseo launcher from the `devman` directory also returned `2.1.291`.

This verifies the executable selection. It does not prove an authenticated
Paseo model request. The host Claude pin still needs routine updates when a
model raises its minimum client version.

## Upstream reference

- [Anthropic Claude Code issue #96130](https://github.com/anthropics/claude-code/issues/96130)
  records the same API error and the 2.1.280 minimum for the affected model.
