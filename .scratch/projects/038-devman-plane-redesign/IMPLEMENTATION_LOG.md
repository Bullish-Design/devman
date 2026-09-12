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
contents remain immutable. The pointer-swap canary follows in Stage 5.

## Stage 5 — active pointer swap

The Dagu service VM test now copies generation 1 to generation 2 and changes
only the generation identity. It switches `active` with one atomic symlink
replacement. The test restarts Dagu to load the new DAG root.

The test passed on 2026-09-12. Dagu discovered `demo.probe` after the swap.
Generation 1 remained available. The previous successful run remained visible.
The project `metadata.jsonl` line count did not change. This proves that stable
Dagu state survives a generation swap.

The service still needs a proof that the active pointer can change while the
service stays up without a manual restart. The current test performs that
pointer swap in Stage 5 with the automatic path enabled.

## Stage 6 — automatic Dagu reload

The NixOS module now installs a user-level systemd path unit. It watches the
active registry pointer and starts a oneshot service when the pointer changes.
That service runs `systemctl --user try-restart dagu.service`.

The pointer-swap VM canary passed on 2026-09-12 without a manual restart. It
observed a new Dagu process, confirmed generation 2, retained generation 1,
rediscovered `demo.probe`, and preserved the prior run record. The stable Dagu
home kept the run history across the restart.

Dagu has no public reload endpoint or reload CLI. The path unit is the current
reload adapter. Its script waits for `dagu ps` to report no active runs before
it restarts Dagu.

The VM canary also covers the active-run rule. It held `demo.hold` open during
the pointer swap. Dagu kept the same process until the run finished. The
deferred restart then loaded generation 2. The run completed and its record was
preserved.

## Stage 7 — immutable package closure

On 2026-09-12, Vendomat added a locked `devman` input and the `devman-plane`
package. The package joins the Devman runtime, canonical renderer, Dagu 2.15.0,
and the shared RepoMan toolchain. It writes one package manifest with known
store paths. The Vendomat CLI reads that manifest for normal plane operations.
Explicit renderer, Dagu, and toolchain flags remain development overrides.

The Devman renderer package now supports both `devman project render` and the
compatibility shell hook's `devman-project apply` entry point. Both paths call
the same Devman CLI and source tree.

The exact proof commands were:

```sh
cd /home/andrew/Documents/Projects/vendomat
devenv shell -- nix build .#devman-plane --no-link --print-out-paths
PATH=/usr/bin:/bin <vendomat-store>/bin/vendomat plane plan devman --to v0.6.0 \
  --project-root /home/andrew/Documents/Projects/devman \
  --policy-root /home/andrew/Documents/Projects/devman \
  --overlay-root /tmp/devman-no-overlay \
  --state-dir /tmp/vendomat-plane-package-test \
  --devman-state /home/andrew/.local/state/devman
devenv shell -- testee verify --mode quick
```

The package build passed. The plan printed one renderer store path, one Dagu
store path, one runtime path, one toolchain path, and the toolchain digest. It
completed with `PATH=/usr/bin:/bin`, which proves normal selection does not use
PATH. Vendomat quick verification passed: ruff, format, ty, and pytest.

One failed attempt found that the old narrow `devman-project` entry point did
not accept `project render`. A second failed attempt found that a direct Python
interpreter wrapper did not carry PyYAML. The final wrapper delegates to the
installed Devman executable and keeps the compatibility `apply` argument
translation. Devman checks passed after the fix: `base:check` and `base:test`
both exited 0. The known doctor findings remain unchanged.

## Stage 8 — project failure results

On 2026-09-12, Vendomat added project-level results to plane plan and update.
Each result names the project, path, operation, status, identity, and whether
the old projection remains retained. Successful renders and unchanged projects
are reported separately. Render, manifest, policy, workflow, project, and
permission errors map to explicit result statuses.

The operation inspects every project before it renders any project. A project
failure returns results for the operation and skips generation staging and
activation. The active pointer therefore remains usable. The CLI reports the
failed project and tells the operator to repair and retry.

The proof ran in Vendomat:

```sh
devenv shell -- pytest tests/test_plane.py
devenv shell -- testee verify --mode quick
```

The unit suite passed with 13 tests. Vendomat quick verification passed with
ruff, format, ty, and pytest. The next failure-model work is fault injection
at each generation boundary and the Dagu reload boundary.

## Stage 9 — generation boundary fault injection

On 2026-09-12, Vendomat added a `fault` test seam to `GenerationStore.build`,
`_activate_number`, `rollback`, `render_project`, and `plan_or_update`. Each
call site accepts an optional hook that a test can raise from at one named
boundary: `renderer-start`, `project-render:<name>`, `staging-complete`,
`after-temp-pointer`, `before-activate`, and `rollback`. Production callers
never pass one; the CLI's default stays `None`.

The audit also found a real gap the failure model needs closed: `_plane_operation`
resolved every explicit `--project-root` or `--project` through a bare list
comprehension. A missing repository among several raised immediately and lost
the structured result for every other project in the same invocation — the
CLI printed a bare error, not a per-project report. Vendomat added
`resolve_projects`, which resolves every requested project independently and
returns a structured `unreadable project` result for one that fails, leaving
the rest resolved. `_plane_operation` now prints and fails closed on any
discovery failure with the same structured report style as plan and update
results, before it ever asks Devman to inspect or render.

New tests in `tests/test_plane.py` proved:

- `_project_failure` classifies every documented status: unreadable project,
  missing manifest, invalid policy, invalid workflow, permission failure, and
  failed render;
- `resolve_projects` keeps a healthy project independent of a missing one;
- a fault at `renderer-start` touches no plane state at all;
- one failed project beside one healthy project blocks activation, reports
  both projects by name, path, and operation, and leaves the active
  generation unchanged;
- a fault after staging completes cleans up the staging directory itself and
  leaves nothing for `recover()`;
- a fault after the temporary active pointer is created, and a fault before
  the active pointer replacement, both leave an orphaned pointer that
  `recover()` moves aside without touching the active generation;
- a fault during rollback, and a fault mid-activation during rollback, both
  leave the pre-rollback active generation in place and recoverable.

The proof ran in Vendomat:

```sh
devenv shell -- pytest tests/test_plane.py
devenv shell -- testee verify --mode quick
```

The unit suite passed with 28 tests (13 prior + 15 new). Vendomat quick
verification passed: ruff, format, ty, and pytest.

Devman `base:check` and `base:test` passed unchanged. `devman doctor` reported
the same four pre-existing findings as Stage 8: the `flora-037-part-e` link
drift and the unpinned RepoMan/Vendomat local sources. RepoMan `base:check`
passed; `base:test` still fails only on the two pre-existing unformatted files
recorded before this project began.

Remaining §4 work: the assertion set in §4.1 (reject a normal directory at
the active path, a generation without `generation.json`, mixed project
identities, a projection record naming a different generation, a
post-activation file mutation, and a staging path outside the plane state
root) is not yet added.

## Stage 10 — the reload boundary, and a bug the VM test caught

On 2026-09-12, Devman made the reload adapter's state visible and closed the
`devman run` half of the run-start race (§5).

`nix/nixos-module.nix` now writes `reload.pending` under
`services.devman-dagu.stateDir` before it waits for `dagu ps` to empty, and
`reload.blocked` if a new option, `reloadMaxWaitSec` (default 300, a stated
bound and not a measurement — the same honesty `queues` states about `llm`),
expires first. On timeout the old Dagu process and generation are left alone,
and the script reports the repair action:
`systemctl --user restart devman-dagu-reload.service`. `devman doctor` gained
a `reload` check reading both markers: `ok` when neither exists, `..` (not a
finding) while pending, `!!` (a finding, with the repair action) when
blocked. `src/devman/run.py`'s `trigger()` refuses an enqueue while
`reload.pending` exists, except for `--print`, which enqueues nothing.

**This closes the race only for the `devman run` path.** Dagu's own scheduled
enqueues and the watcher's do not pass through `trigger()`, so a run either
of them starts can still race the restart. That limitation is documented in
the module rather than claimed away, per §5.3's instruction not to assert an
absolute guarantee from a polling loop. Closing it fully needs a daemon-side
hook nothing in this design has built.

**The NixOS `dagu-service` VM test caught two real, previously-latent bugs
while proving this boundary — not new ones the markers introduced, ones the
markers made visible for the first time:**

1. `dagu ps` prints the literal line `No running processes` when idle; it is
   never empty. `[ -n "$(dagu ps)" ]` was therefore true whether or not
   anything was running, and the reload script's wait loop never terminated
   on its own — a restart only ever happened when `dagu ps` itself
   transiently failed and `2>/dev/null` emptied its output by accident. Fixed
   by matching the exact idle string instead of emptiness.
2. `dagu.service`'s own `ExecStartPre` (`installConfig`) creates
   `registryDir` with `mkdir -p` the first time it starts on a machine with no
   generation activated yet, and separately, a write inside an already-active
   generation (the compatibility `project apply` path, or that same `mkdir
   -p` populating a fresh generation's subdirectories) can retrigger the path
   unit without the active pointer's target ever changing. Fixed with two
   guards in the reload script: `readlink` on the registry path — empty means
   a bootstrap placeholder, not a generation, so the script exits without
   touching `reload.pending`; and a `reload.target` marker recording the last
   successfully reloaded symlink target — unchanged means skip, because
   restarting Dagu for a generation that is already active earns nothing and
   only adds another run-start race window.

Both bugs were invisible before this stage because a reload script that never
finished, or that fired redundantly, had no previously-observed side effect —
the pointer-swap VM canary in Stage 5/6 measured only that a *deliberate*
swap eventually restarted Dagu, not that the script terminated promptly or
fired exactly once per real change. `reload.pending` blocking every
`devman run` on the machine for the marker's stuck lifetime is what surfaced
both, and finding them here is themselves the failure-model work: property 4
holds independent of whether the exposed failure was one this stage set out
to fix.

The proof ran in Devman:

```sh
devenv tasks run -v base:check
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- devman doctor
```

`base:check` and `base:test` passed, including the `dagu-service` VM test,
which now proves — beyond what Stage 5/6 proved — that a real activation
triggers exactly one reload each, that a bootstrap placeholder and a
same-generation rewrite trigger none, and that `devman doctor` reports the
reload state throughout. The unit suite passed with 545 tests (538 prior + 7
new, covering the refusal, the `--print` exemption, and all four `check_reload`
report states). `devman doctor` reported the same three pre-existing findings
as Stage 9 plus the new `reload` check reporting `ok`.

Not done in this stage: the strict maintenance gate's remaining half (the
watcher waiting on `reload.pending`) needs `src/devman/watch.py`, which this
session's protected-file list forbids touching — recorded here rather than
worked around. Scheduled Dagu runs remain ungated, as documented above. The
§5.2 NixOS test additions beyond what already existed (proving generation 1
stays retained and generation 2 becomes visible across the swap) were already
present from Stage 5; this stage did not need to add them.

## Stage 11 — RepoMan inventory, and explicit projection mode

On 2026-09-12, a read-only inventory sweep ran RepoMan's migration proposal
(`repoman devman migrate`, no `--apply`) against 46 registered repositories
beyond the three canary repositories, which already carry a migrated
manifest. Findings, for a human to review before any repository lane is
opened:

- 43 of 46 propose cleanly, almost all to a single `base` group;
  `observantic` is the only one proposing `base, release`.
- `copyroom`, `docman`, and `mypi-agent` cannot migrate mechanically: each
  carries its `devman` option block in `dev/devenv.nix` rather than the
  tracked root `devenv.nix`, which is a structural choice a human has to
  resolve, not a tool gap.
- Four repositories (`fornix`, `interplay`, `structured-agents-v2`, `talkee`)
  carry nested `.git` checkouts, all inside vendor or scratch directories —
  worth a glance before migrating, not necessarily a blocker.
- Every one of the 46 already carries a `devenv.local.nix` machine-local
  overlay, which the link-plane design (project 025) expects and is not
  itself a finding.

No repository outside the three canaries was written to. Applying any of
these migrations is a separate, explicit decision this project has not been
asked to make.

Devman added an explicit `mode` line to `devman doctor` (§7): `plane` when
the registry root carries a `generation.json` — written only by
`GenerationStore.build` — and `compatibility` otherwise. Vendomat's
`plane show` now states `projection mode: plane` for the same reason
`plane show` states anything else about a generation: Vendomat only ever
produces plane projections, and saying so removes the one implicit fact `git
grep compatibility` found nowhere stated. Neither reads or infers anything
from `PATH`.

**Building this stage's VM-test proof surfaced a second, unrelated latent
bug, and also a false lead worth recording so it is not re-chased.** Adding
the `mode` check appeared to make the `dagu-service` VM test fail
deterministically at the same subtest, four runs in a row — every symptom of
a real regression. Isolating it by reverting just the `mode` change and
forcing a fresh (non-cached) rebuild of that reverted version, under the same
host load, reproduced the identical failure. **The `mode` check was never the
cause.** The actual defect, latent since Stage 4, is in `check_queues`
(`check_queues` docstring, S14): a queued item can read as "0 running" for
longer than an instant before Dagu's own scheduler dispatches it, and under a
sufficiently loaded host that window can exceed even a generous single
re-check. `check_queues` now re-checks up to three times, one second apart,
before it concludes a queue is genuinely wedged rather than merely
mid-dispatch — bounding the added cost at three seconds, and only when a
queue looks momentarily empty of runners. This is a production hardening as
much as a test fix: an operator running `devman doctor` under machine load
could hit the exact same false "!!" today.

The proof ran in Devman and Vendomat:

```sh
devenv tasks run -v base:check
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link --rebuild
devenv shell -- devman doctor
cd vendomat && devenv shell -- testee verify --mode quick
```

`base:check` and `base:test` passed. The `dagu-service` VM test passed twice
in a row after the `check_queues` fix, including one `--rebuild` run that
also verified output reproducibility — after having failed reproducibly
four times running before it. The unit suite passed with 547 tests (545
prior + 2 new, covering both `mode` states; `check_queues` itself stays
untested by unit tests per this file's own stated policy — it belongs to the
VM test, which now covers it under load). `devman doctor` reported the same
three pre-existing findings as Stage 10, plus the new `mode` line. Vendomat
quick verification passed: ruff, format, ty, and pytest.

Not done in this stage: the fleet-wide RepoMan migration itself (applying
any of the 46 proposals) — inventory only, by explicit instruction. The full
§7 comparison sweep (eleven dimensions across every canary) has not run; it
needs a live side-by-side environment this stage did not build.
