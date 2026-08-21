# devman

The development automation plane.

> **devman installs one Dagu control plane per machine, and gives every
> devenv-managed repository a shared automation contract through one Nix flake.**

Dagu orchestrates. devenv executes. devman is the contract between them, and
executes nothing itself.

## Status

**Pre-implementation.** The charter is written; the investigations that gate
planning are not yet run. This repository currently holds design work and a
development shell.

The previous devman — a tmuxp workspace orchestrator — is superseded and its
source has been removed.

## What it will be

Three things, and the list is closed:

1. **A shared Nix flake** — a NixOS interface and a devenv interface, one
   version.
2. **A project registry** — which repositories opted in, and where they are.
3. **A contract** — a queue name, and nothing else.

A repository adopts it in three lines:

```nix
devman = {
  enable  = true;
  project = "pyjutsu";
  groups  = [ "base" "python" ];
};
```

A workflow is a Dagu YAML file with no devman-specific key in it. Groups layer
by directory; a repository overrides one by shadowing the file name.

## Documents

| Path | What |
|---|---|
| [`CONCEPT.md`](.scratch/projects/006-automation-plane/CONCEPT.md) | the charter |
| [`KICKOFF_PROMPT.md`](.scratch/projects/006-automation-plane/KICKOFF_PROMPT.md) | the investigations that gate planning |
| [`INITIAL_PROPOSAL.md`](.scratch/projects/006-automation-plane/INITIAL_PROPOSAL.md) | the source guide the charter adopted |
| [`SPIKES.md`](.scratch/spikes/SPIKES.md) | measurements; Spike A is load-bearing |

`.scratch/projects/001`–`005` are earlier attempts to define devman. They are
superseded and carry no authority.

## Development

```bash
devenv shell
```
