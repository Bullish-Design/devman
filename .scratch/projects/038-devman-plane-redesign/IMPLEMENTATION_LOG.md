# Devman plane redesign implementation log

Date: 2026-09-12

## Phase 0 — audit

The three repositories started in these states:

| Repository | Branch | Worktree state | Remote |
|---|---|---|---|
| Devman | `037-follow-up-results` | four pre-existing modified files | `origin/037-follow-up-results` |
| RepoMan | `main` | one pre-existing staged `devenv.lock` change | `origin/main` |
| Vendomat | detached `HEAD` | clean | `origin/main` |

The implementation keeps those changes out of the redesign commits.

The current update path has four repeated steps:

1. each consumer pins Devman in `devenv.yaml`;
2. each consumer updates its `devenv.lock`;
3. each consumer evaluates its devenv configuration;
4. each consumer enters its shell to run the renderer and registry update.

The audit found 51 `devenv.nix` files with a `devman` option under the local
Projects tree. The active registry currently contains four projects and 19
projected workflows. Central state holds metadata under
`~/.local/state/devman/`. Generated workflows and Dagu links remain under
`~/.local/share/devman/`.

The current stale-renderer protection is the consumer-side `planFile` store
path. `modules/devenv.nix` records the path and its shell hook compares it with
the registry entry. `nix/renderer.nix` builds the renderer once per consumer
nixpkgs. This protects stale output, but it causes the repeated consumer update
path.

The current command surfaces have no plane lifecycle operation:

| Repository | Existing surface |
|---|---|
| Devman | `run`, `show`, `doctor`, `watch`, `agent`, `project apply`, `link` |
| RepoMan | `managers`, `doctor`, `status`, `install-skills` |
| Vendomat | `sync`, `add`, `doctor`, `materialize`, `install-hook`, `publish`, `vendor` |

The first shell-entry measurement was 8.42–8.76 seconds for
`devenv shell -- true` in Devman. This measures devenv evaluation and setup as
well as the hook. It is a baseline, not a hook-only measurement.

## Scope matrix

| Current owner | Current input | Current output | Current state location | Current command | Target owner | Target state location | Migration needed | Test needed |
|---|---|---|---|---|---|---|---|---|
| Consumer devenv | Devman flake input and `devman.*` options | Nix plan and shell hook | consumer `devenv.lock`, central registry | `devenv update`; `devenv shell` | Devman contract | tracked `.devman/project.toml` | derive manifest from old options | manifest compatibility |
| Consumer renderer | Nix-resolved groups and overlays | projected Dagu files | `~/.local/share/devman/projects` | `devman project apply` | Devman renderer | staged plane generation | centralize resolution and projection | old/new byte comparison |
| Consumer shell hook | plan path and local file names | registry metadata | `~/.local/state/devman/projects` | shell entry | Devman reconciler | central state and generation records | add central adoption and reconcile | stale and no-op cases |
| Vendomat | package inputs | shared artifacts | Nix store | `nix build` | Vendomat plane | immutable generation store | add plan/build/stage/activate | generation lifecycle |
| RepoMan | repository files and lanes | repository-specific changes | Git worktree and lanes | RepoMan plus Git manager | RepoMan | repository lane | add manifest migration | selected-repository mutation |
| Dagu | projected DAG directory | runs, queues, history | Dagu home | service discovery | Dagu | unchanged Dagu home | reload without history loss | queue and active-run checks |

## Stage 1 decision

The repository manifest is `.devman/project.toml`. It carries only `schema`,
`project`, `groups`, and `policy`. The first supported policy reference is a
name such as `stable`; a content digest is also valid for later promotion.

The contract library records generation identities separately for the Devman
runtime, renderer, policy, Dagu, toolchain, and schema. Every projection record
also records the manifest, source, policy, renderer, and generation identities.

The initial activation policy is `atomic`: a generation does not become active
when a selected projection fails. A later best-effort mode needs separate
evidence because it creates a mixed machine state.

The first code slice is pure and does not change the current shell hook. It
gives Vendomat a stable, path-free interface for the next slice.

## Stage 2 — central renderer and first plane lifecycle

The first complete vertical slice now exists across all three repositories.

Devman added:

- `src/devman/contract.py` for the manifest, generation, projection, and digest
  records;
- `src/devman/reconcile.py` for group, trigger, writes, and central-overlay
  resolution;
- `devman project render` as the public renderer boundary;
- the tracked Devman manifest at `.devman/project.toml`.

Vendomat added:

- `vendomat plane plan devman --to VERSION`;
- `vendomat plane update devman --to VERSION`;
- `vendomat plane rollback [devman] --to GENERATION`;
- `vendomat plane show devman` and `vendomat plane recover devman`;
- repeatable `--project-root` selection for one generation across explicit
  repositories;
- immutable generation directories, an atomic `active` symlink, retained old
  generations, staged Dagu validation, no-op detection, and interrupted-stage
  recovery.

RepoMan added `repoman devman status` and `repoman devman migrate`. The
migration derives portable manifest facts from one repository's current
`devenv.nix` and writes only `.devman/project.toml` when explicitly asked.
RepoMan does not activate the plane.

The first real proof used Devman, RepoMan, and Vendomat together, the pinned
Dagu 2.15.0 binary, and a temporary Vendomat state root. One command supplied
the three repository roots and the Devman policy root:

```sh
vendomat plane update devman --to v0.6.0 \
  --project-root /home/andrew/Documents/Projects/devman \
  --project-root /home/andrew/Documents/Projects/repoman \
  --project-root /home/andrew/Documents/Projects/vendomat \
  --policy-root /home/andrew/Documents/Projects/devman
```

That command proved the following:

1. `devman project render` resolved the manifest, group sources, and central
   overlay without running a task;
2. Vendomat rendered one generation for all three projects and validated every
   generated workflow;
3. Vendomat activated generation 1;
4. the same update reported a no-op and left generation 1 active;
5. a target change activated generation 2 while retaining generation 1;
6. rollback pointed `active` back to generation 1;
7. unit failure injection proved a rejected staged workflow left the old active
   generation unchanged;
8. recovery moved an interrupted staging directory to `recovered/` without
   touching the active pointer.

Verification evidence:

- Devman unit suite: 538 passed;
- Devman `base:check` passed;
- Devman `base:test` passed;
- Vendomat `testee verify --mode quick`: ruff, format, ty, and pytest passed;
- RepoMan `base:check` and `base:test` passed;
- RepoMan migration and CLI tests: 37 passed.

The required Devman doctor gate ran after the slice. It returned four existing
machine findings: one link drift and dirty or unpinned local RepoMan and
Vendomat sources. The implementation did not alter those unrelated machine
state findings or the pre-existing worktree edits. The new generation path is
not yet the active compatibility registry, so the generation check has no
active registry record to inspect.

An old/new comparison then rendered the ten current Devman workflows through
the new renderer and compared them with the compatibility registry after
normalising only the generated source comment. All ten matched. The only
byte-level difference before that normalisation was the source comment: the
old path names a Nix store file, while the new renderer names the relative
policy source. The new path is portable and does not change the YAML body.

## Stage 3 — identity-first reconciliation and active-root canary

Devman now exposes `devman project inspect`. It resolves the same manifest,
policy, overlay, and source identities as render, but it does not render files
or write state. Vendomat uses this result before every update. It renders only
changed projects and copies unchanged valid projections into the new immutable
generation. The copy updates the projection generation record and the
compatibility metadata marker.

Vendomat serializes update, rollback, and recovery operations with a machine
state lock. The plan operation remains read-only and does not create the plane
state root. The lock closes the race where two updates choose the same next
generation number.

The second cross-repository proof used a temporary overlay. It activated
generation 1, changed only Devman's `agent-review` overlay, and activated
generation 2. Vendomat reported only `devman` as changed. A byte comparison
proved that RepoMan's unchanged workflow was copied into generation 2.

The active generation is self-contained. Its `active` root contains the
registry `projects/` tree, the flat Dagu `dags/` tree, and `generation.json`.
The first manual canary pointed both `registryDir` and `stateDir` at the active
symlink. That proved the root was self-contained, but it also moved watcher
state with every generation. The service canary keeps `stateDir` at the stable
Devman state root and points only `registryDir` at the active symlink. Devman
now reads active-root `projection.json` records before the compatibility state
copy, so `doctor` can check the active generation without moving runtime state.

The compatibility shell hook and registry remain the default. Vendomat still
receives explicit renderer and Dagu paths. Package-closure reuse and automatic
service reload remain open Phase 3 work.

## Stage 4 — Dagu active-registry service canary

On 2026-09-12, the NixOS Dagu service check passed:

```text
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
```

The service used the active generation for `registryDir` and the stable
`$HOME/.local/state/devman` root for `stateDir`. The test seeded generation 1,
activated its symlink, and started the watcher. Dagu discovered the generated
workflows, ran `demo.probe`, and wrote the expected run records and logs.
The watcher stayed live. The service and doctor checks passed.

The fixture changes only VM test data after activation. Production generation
contents remain immutable. A pointer-swap test that proves reload without
losing Dagu history, and automatic service reload, remain open.

## Stage 5 — active pointer swap

The Dagu service VM test now copies generation 1 to generation 2 and changes
only the generation identity. It switches `active` with one atomic symlink
replacement. The test restarts Dagu to load the new DAG root.

The test passed on 2026-09-12. Dagu discovered `demo.probe` after the swap.
Generation 1 remained available. The previous successful run remained visible.
The project `metadata.jsonl` line count did not change. This proves that stable
Dagu state survives a generation swap.

The service still needs an automatic reload path. The next test should swap the
pointer while the service stays up and prove that Dagu reloads without a manual
restart or loss of history.
