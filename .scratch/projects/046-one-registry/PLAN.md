# 046 — one registry, built by devman

**Status:** superseded, 2026-10-15, by `047-greenfield/CONCEPT.md`. Owner ruling in session had been option C.

## Goal

devman has one way to build and read its registry. No compatibility mode, no
second registry form, no migration code. devman is new, so old data is deleted,
not migrated.

## Decisions

**D1. devman builds the registry (option C).** One command,
`devman registry build`, renders every listed project into a new generation and
swaps one link. Options A (store-path `mkRegistry`) and B (Vendomat generation)
are rejected:

- A needs a switch for every workflow edit, and puts the project list in nix-meta.
- B has no builder. Vendomat removed `plane.py` on 2026-10-09 (`663b8643`). Only
  an outdated installed binary still has it.

**D2. The layout.**

| Path | Holds |
|---|---|
| `~/.local/state/devman/generations/<N>/` | one complete registry: `generation.json`, `projects/<p>/`, `dags/` (the layout `nix/registry.nix` documents today) |
| `~/.local/state/devman/active` | a symlink to the current generation. Swapped atomically (`rename(2)` over a temporary link) |
| `~/.local/state/devman/` | `stateDir`, unchanged: watcher state, run metadata, reload markers |

`registryDir` stops being an option. The NixOS module and the CLI both use the
fixed default `~/.local/state/devman/active`. Every `devman` binary then reads
the same root with no flag. This fixes the two-binary fault: a repo shell's
`devman doctor` read `~/.local/share/devman` (4 projects) while Dagu read the
Vendomat generation (44).

**D3. One project list.** `~/.config/devman/projects.toml`:

```toml
[projects]
devman = "~/Documents/Projects/devman"
```

The key is the project name. The value is the checkout path. The checkout's
`.devman/project.toml` stays the identity source (name, groups, policy).
`build` refuses, loudly, and changes nothing when:

- a listed checkout or its manifest is missing;
- the manifest's `project` differs from the list key;
- an overlay `projects/<p>/` directory has no list entry;
- any rendered workflow fails `dagu validate`.

A refused build never moves `active` (property 4).

**D4. Reload.** The existing mutable-registry path unit watches `active` and
reloads Dagu. No switch is needed for a workflow edit.

**D5. Rollback and cleanup.** `devman registry rollback` points `active` at the
previous generation. `build` keeps the newest 5 generations and deletes older
ones.

**D6. Charter.** §5.2 ("registration is automatic and has no manual path")
changes: registration is one line in `projects.toml`. The change lands in
`006-automation-plane/CONCEPT.md` in the same commit as the builder.

## The keep list — 33 projects

agentman, argentic, atuout, copyroom, devenv-py, devman, eventic, gitman,
inferference, knappy, linkman, loci-core, loci.nvim, mancore, mnemonix,
nix-desktop, nix-meta, nix-nvim, nix-paseo, nix-secrets, nix-terminal,
nixos-core, pydantree, pyjutsu, pyllij, pytuin, scopeman, silverbullet-server,
template-py, templateer_v2, testee, tyo3, vendomat

Each one has a checkout at `~/Documents/Projects/<name>` and a manifest (checked
2026-10-15).

## Dropped — 28 projects

browsee, cairn, clinch, docman, embeddy, flora, flora-core, flora-qc, forgelab,
fornix, fsdantic, grail, interplay, llgym, nixbuild, nixvim, observantic,
parsedantic, poddantic, PyGentic, repoman, shellij, siteman,
structured-agents-v2, talkee, terminal-state, webdantic, zelligate

Their overlay entries leave `~/.config/devman/projects/`. Their repos lose the
overlay symlinks and the matching `.git/info/exclude` lines. The repos themselves
stay untouched otherwise.

## Removed compatibility code

| What | Where |
|---|---|
| `project apply`, the `devman-project` entry point | `pyproject.toml:43-47`, `project.py` `main`/`cli`/`add_arguments`, `cli.py` docstring |
| `compatibility_apply` and helpers | `reconcile.py:403-630` |
| The shell-entry renderer package | `nix/renderer.nix` |
| The old registry and its prune | `registry.py:626-765`, `doctor.py:542-563`, the legacy name handling (`registry.py:475`, `doctor.py:692`) |
| Doctor's two modes | `doctor.py:1086` and its callers |
| The store-path builder | `nix/registry.nix`, `nix/mk-registry.py`, `lib.mkRegistry`, `nix/tests/dagu-store-registry.nix`, `isStoreRegistry`, `restartTriggers` on the registry |
| `registryDir` as an option | `nix/nixos-module.nix:520-530` and every caller |
| The old link engine | `src/devman_link/` reconciler, `DEVMAN_LINK_ENGINE` (044 lanes 5-6) |
| One-time migration tooling | `tools/cutover/` |
| A second module name | `nixosModules.devman-dagu` (`flake.nix:131`) |
| The `devman_contract` re-export | `devman_contract/__init__.py:8`, `devman.registry` |

## Stages

| # | Stage | Owner |
|---|---|---|
| 1 | `devman registry build`/`rollback`, `projects.toml`, fixed root, module change, VM test | registry agent |
| 2 | Remove the compatibility code above, except the link engine | registry agent, after stage 1 |
| 3 | 044 lanes 5-6: the adapter calls linkman; the old engine goes | link agent, in parallel |
| 4 | Write `projects.toml` (33 entries); remove the 28 overlay entries; write the operator script for old data and dropped-repo symlinks | overlay agent, in parallel |
| 5 | Operator: run the script; pin devman in nix-meta, drop its `registryDir` line, switch; `devman registry build`; `devman doctor` | owner |
| 6 | Doc sweep: AGENTS.md property 6 table, README, USER, AGENTS_GUIDE, skills | registry agent, last |

## Old data to delete (stage 5, operator)

- `~/.local/share/devman/` (58 projects, 183 DAG links)
- `~/.local/state/vendomat/devman/` (generations 3 and 4, `active`)
- `~/.config/devman/dags/` if nothing reads it
