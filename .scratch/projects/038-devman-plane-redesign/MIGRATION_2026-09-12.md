# Project 038 migration wave — 2026-09-12

This table records every non-canary repository in the 46-repository wave. The
three canaries (`devman`, `repoman`, and `vendomat`) already had manifests before
this wave.

| Repository | Result | Exact reason or state |
|---|---|---|
| allium-env | already migrated | Manifest was committed and pushed before this session. |
| argentic | migrated | Stale RepoMan environment fixed. Manifest written. Repository checks: `base:check` passed; `base:test` stalled after five errors at 10% and was stopped after 219 seconds. |
| atuout | already migrated | Manifest was committed and pushed before this session. |
| boomtube | already migrated | Manifest was committed and pushed before this session. |
| browsee | migrated | Secretspec reason supplied. Manifest written. Shell also reported `playwright: command not found` and existing mypi-agent runtime warnings. |
| cairn | already migrated | Manifest was committed and pushed before this session. |
| copyroom | blocked | Its Devman option block is in `dev/devenv.nix`, not root `devenv.nix`. Manifest placement needs a human decision. |
| docman | blocked | Its Devman option block is in `dev/devenv.nix`, not root `devenv.nix`. Manifest placement needs a human decision. |
| embeddy | already migrated | Manifest was committed and pushed before this session. |
| eventic | migrated | Stale RepoMan environment fixed. Manifest written. Repository checks: `base:check` passed; `base:test` timed out at 180 seconds after failures in `tests/conformance/test_cli.py` (two failures at 19%). |
| flora | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` passed. `base:test` failed during collection with two existing `curator` test import errors. Existing unrelated `.claude/settings.local.json.devman-promoted` was preserved. |
| flora-core | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` found one existing Ruff error. |
| flora-qc | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` passed. |
| fornix | migrated | Secretspec reason supplied. Manifest written. Existing `devenv.lock` change was preserved. |
| gitman | already migrated | Manifest was committed locally before this session on a detached HEAD. No branch was invented and no force-push was attempted. |
| grail | already migrated | Manifest was committed and pushed before this session. |
| image-gen-pipeline | already migrated | Manifest was committed locally before this session on a detached HEAD. No branch was invented and no force-push was attempted. |
| interplay | already migrated | Manifest was committed and pushed before this session. |
| knappy | already migrated | Manifest was committed and pushed before this session. |
| llgym | already migrated | Manifest was committed locally before this session on a detached HEAD. No branch was invented and no force-push was attempted. |
| loci-core | already migrated | Manifest was committed locally before this session on a detached HEAD. No branch was invented and no force-push was attempted. |
| loci.nvim | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` passed. |
| mypi-agent | blocked | Secretspec reason supplied, then migration reached the structural error: zero root Devman option blocks because the block is in `dev/devenv.nix`. Manifest placement needs a human decision. |
| nix-desktop | already migrated | Manifest was committed and pushed before this session. |
| nix-nvim | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` passed. |
| nix-paseo | already migrated | Manifest was committed locally before this session on a detached HEAD. No branch was invented and no force-push was attempted. |
| nix-secrets | already migrated | Manifest was committed and pushed before this session. |
| nixbuild | already migrated | Manifest was committed and pushed before this session. |
| nixvim | already migrated | Manifest was committed and pushed before this session. |
| observantic | already migrated | Manifest was committed and pushed before this session. It remains the multi-group (`base`, `release`) canary. |
| paloma-text-pipeline | migrated | Stale RepoMan environment fixed. Manifest written. No `base:check` task exists. Existing worktree and lane changes were preserved. |
| parsedantic | already migrated | Manifest was committed and pushed before this session. |
| poddantic | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` passed. |
| pydantree | already migrated | Manifest was committed locally before this session on a detached HEAD. No branch was invented and no force-push was attempted. |
| pyjutsu | already migrated | Manifest was committed locally before this session on a detached HEAD. No branch was invented and no force-push was attempted. |
| pyllij | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` passed. |
| pytuin | migrated | RepoMan was absent from the project shell. The rebuilt machine RepoMan binary was used. Manifest written. `base:check` passed. |
| shellij | migrated | Stale RepoMan environment fixed. Manifest written. `base:check` passed. |
| structured-agents-v2 | migrated | RepoMan was absent from the project shell. The rebuilt machine RepoMan binary was used. Manifest written. `base:check` found existing lint errors. Existing scratch moves and lock changes were preserved. |
| talkee | migrated | RepoMan was absent from the project shell. The rebuilt machine RepoMan binary was used. Manifest written. The shell warned that `cliProvider` was `store` without `REPOMAN_TOOLCHAIN_BIN`. `base:check` passed. Existing worktree changes were preserved. |
| templateer_v2 | migrated | Secretspec reason supplied. Manifest written. Existing lanes and worktree changes were preserved. |
| terminal-state | migrated | RepoMan was absent from the project shell. The rebuilt machine RepoMan binary was used. Manifest written. `base:check` found one existing lint error. Existing `devenv.lock` change was preserved. |
| testee | migrated | RepoMan was absent from the project shell. The rebuilt machine RepoMan binary was used. Manifest written. `base:check` passed. |
| tyo3 | migrated | Secretspec reason supplied. Manifest written. `base:check` was gated by the same secretspec reason until the explicit reason was supplied. |
| webdantic | migrated | RepoMan was absent from the project shell. The rebuilt machine RepoMan binary was used. Manifest written. `base:check` found existing lint errors. Existing `devenv.lock` change was preserved. |
| zelligate | migrated | Secretspec reason supplied. Manifest written. `base:check` was gated by the same secretspec reason until the explicit reason was supplied. |

## Counts

At the start, 21 of the 46 non-canary repositories had manifests. The wave
added 22. There are now 43 migrated non-canary repositories and three blocked
repositories: `copyroom`, `docman`, and `mypi-agent`.

The active plane also contains the three canaries, for 46 projects and 146
generated DAGs.

The 11 stale-RepoMan repositories were fixed by updating their direct RepoMan
input to RepoMan `main` at `57473ad` and selecting the machine venv provider:
`repoman.cliProvider = "venv"` and `vendor.toolchain.enable = false`. The six
repositories without a shell RepoMan used the rebuilt machine binary directly.
The six secretspec-gated shells received:
`SECRETSPEC_REASON="devman migration (project 038)"`.

All 22 newly migrated non-canary manifests were committed and pushed. The
detached-at-`main` repositories received a `038-devman-migration` branch; no
branch was invented for the seven earlier detached commits. `talkee` had an
old `/.devman/` ignore rule, so its commit also narrows that rule to
`/.devman/.runs/`, which keeps the manifest trackable. The RepoMan canary's
manifest was committed separately on its own `038-devman-migration` branch;
its protected `devenv.lock` and other existing changes were not staged.
