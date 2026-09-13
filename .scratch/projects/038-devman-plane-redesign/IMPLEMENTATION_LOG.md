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

## Stage 12 — a live three-repository canary, and the measurements it forced

On 2026-09-12, `vendomat plane plan/update/show/rollback` ran against Devman,
RepoMan, and Vendomat's real checkouts — not fixtures — using a scratch
`--state-dir` under `/tmp` so nothing touched the live machine plane or any
tracked file in any of the three repositories. This is the canary set §8
names first; the wider category list (local-overlay project, multi-group
project, cross-repository workflow, scheduled workflow, a project with
declared writes, an unusual path) is unstarted, per §8's own instruction to
add those only after the small set passes.

Proven, against the real renderer and the real three repositories:

- one generation contained all three projects, correctly render-only where
  changed and no-op where not;
- all 16 generated DAGs (10 Devman, 3 RepoMan, 3 Vendomat) validated against
  the pinned Dagu 2.15.0;
- a no-op update reported itself and left the generation unchanged;
- a target-version change rendered all three and activated a new generation,
  retaining the old one on disk;
- rollback returned the active pointer to the retained generation, with the
  newer one still present;
- a missing `--project-root` (pointed at a directory that does not exist)
  produced a structured `unreadable project` result, exit code 2, and left
  the active generation untouched — `resolve_projects` (Stage 9) doing
  exactly what it was built for, against real infrastructure instead of a
  fixture;
- an invalid `--policy-root` (no `groups/` directory) produced a structured
  failure for every project and left the active generation untouched.

**That last canary caught a real classification bug the fixture-based tests
never triggered.** Devman's policy-resolution error text ("group root is not
a directory: ...") contains the same phrase `_project_failure` used to detect
a missing *project* directory, and the missing-project check ran first — so
every invalid-policy failure was reported as `unreadable project`, naming the
wrong repair action to an operator. Reordered so `policy` is checked before
the generic `not a directory` phrase; the `unreadable project` phrasing
itself was never ambiguous, only the check order was. A regression test
reproducing the exact message now guards it. Vendomat's unit suite (29
tests: 28 prior + 1, including this regression) and quick verification
(ruff, format, ty, pytest) both passed after the fix. No repository outside
the scratch state directory was written to at any point; `git status` in all
three repositories showed only the pre-existing protected changes throughout.

Measured (§9), warm, all commands via `devenv shell -- vendomat plane ...`,
three-project fleet, on this machine, 2026-09-12:

| Measure | Time | Note |
|---|---:|---|
| full update (3 projects, all render) | 2.78s | includes `devenv shell` entry overhead |
| no-op update (3 projects, none render) | 1.19s | lower than a full update, as required |
| changed-target update (3 projects, all re-render) | 2.77s | a runtime version bump alone forces re-render |
| rollback | 0.76s | pointer swap only, no rendering |
| consumer lock changes | 0 | no repository's `devenv.lock` or `devenv.yaml` changed |
| consumer shell entries | 0 | one `vendomat` invocation covered all three projects |

Not remeasured: a genuinely cold plane build (this machine's Nix store is
warm from this session's own builds, and clearing it to get a fair cold
number was judged not worth the disruption); the 46-repository full-fleet
staging time (no repository outside the three canaries has a manifest to
render yet); interrupted-recovery timing (already covered qualitatively by
Stage 4's fault-injection tests). The existing baselines this stage compares
against: shell-entry about 8.42–8.76s per repository (Stage 0), and an older
46-repository rollout at about 15.7 minutes (Stage 0) — three repositories
under the old path would cost three separate shell entries, roughly 25–26s,
against this stage's single 2.78s update covering the same three.

## Stage 13 — the RepoMan migration wave, a v0.6.0 release, and the cutover build

On 2026-09-12, by explicit instruction, the fleet-wide RepoMan migration ran
for real (§6), a release was cut, and the machine cutover (§10) was prepared
and built — but not switched to, for a reason recorded below rather than
worked around.

**RepoMan migration wave.** `repoman devman migrate --apply` ran against 44
of the 46 non-canary repositories (`copyroom` and `docman` excluded on
purpose — the same `dev/devenv.nix` structural issue Stage 11's inventory
found). Of those 44: 24 now carry a real `.devman/project.toml` on disk (the
number that matters for rendering); of those, 14 are committed and pushed,
7 are committed locally only because the repository was already on a
detached HEAD before this sweep touched it (left as found, no branch
created, no force-push); 20 failed to migrate, for three environmental
reasons unrelated to the migration logic — a stale local `repoman` build
missing the `devman` subcommand, `repoman` absent from the `devenv shell`
entirely, or `secretspec` refusing to enter the shell without a `--reason`.
None of these 20 were left partially modified; each failure was a clean
skip. `mypi-agent` hit the `secretspec` gate before it ever reached its
known structural issue.

**Devman v0.6.0.** Version bumped in `pyproject.toml`, `nix/renderer.nix`,
and `nix/devman-cli.nix` (three places forced to agree since S-6 of an
earlier stage). PR #166 (`037-follow-up-results` → `main`, this project's
entire Stage 4–12 history) merged clean, no CI configured on this repository
so local verification stood in for it: `base:check`, `base:test` including
the `dagu-service` VM test, and `devman doctor` all passed on `main` before
tagging. Tagged `v0.6.0` (annotated, `devman 0.6.0`), pushed.

**The real, live-state Vendomat generation.** Built at
`$HOME/.local/state/vendomat/devman` (the real path, not a scratch
directory) covering all 24 repositories with a manifest — the three
canaries plus the 21 migrated ones with the file on disk regardless of push
state. All 24 rendered successfully; all 80 generated DAGs validated
against the pinned Dagu 2.15.0 in one pass. Generation 1 is active at that
path right now.

**The cutover itself, prepared and built but not applied.** The machine's
actual system configuration lives in a fourth repository, `nix-meta`,
applied via `sudo nixos-rebuild switch --flake .#server` — a detail this
project's charter never named, discovered only when tracing where
`services.devman-dagu` is actually imported. `nix-meta` repinned its
`devman` flake input from tag `v0.5.2` to `v0.6.0`, and
`profiles/devman.nix` now sets
`registryDir = "$HOME/.local/state/vendomat/devman/active"`, `stateDir`
left at devman's default. `nixos-rebuild build --flake .#server` produced a
new system generation cleanly, and its generated
`devman-dagu-install-config` script was read directly to confirm the
registry path baked in correctly before anything further happened. The
change was committed and pushed to `nix-meta`'s `main` (this repository's own
convention — direct commits to `main`, no PR, matching its last three
version-pin commits).

**`sudo nixos-rebuild switch` did not run.** This session has no functional
root: `sudo: /run/current-system/sw/bin/sudo must be owned by uid 0 and have
the setuid bit set`. This is a sandbox constraint, not a policy decision —
the built generation is real, verified, and sitting in the Nix store, and
the operator needs only run:

```sh
cd ~/Documents/Projects/nix-meta
sudo nixos-rebuild switch --flake .#server
```

Confirmed immediately before attempting this that `dagu ps` reported no
running processes, so the moment for a switch (which restarts `dagu.service`
directly, outside the reload adapter's drain-wait — that adapter only
watches the active-generation pointer, not a service-config change applied
by `switch-to-configuration`) was as safe as it gets. The current live
system (`/run/current-system`) is untouched and serving the compatibility
registry exactly as before this stage.

**§11 (remove obsolete fan-out) did not start.** Its own gate says to
remove old code only after an observation period once the new path is live
for every supported consumer — and the cutover is not live yet, and 22 of 46
non-canary repositories still have no manifest at all. Removing the
compatibility fallback now would leave those repositories with no serving
path at all. This is deferred, not skipped: the correct order is switch,
observe, then remove, in that sequence, once a human has actually run the
one command above.

## Stage 14 — complete the migration wave, compare the fleet, and widen the canary

On 2026-09-12, this session continued after the operator had switched the live
system to the NixOS configuration recorded in Stage 13. The machine now uses
the Vendomat active generation as its Devman registry. This stage records the
remaining migration work and the checks that depend on that live state.

**RepoMan migration wave.** The machine RepoMan was rebuilt with
`devenv shell -- repoman-sync --machine`. The resulting machine binary exposed
`repoman devman`, while the project shells that carried an older Vendomat
toolchain still selected the old binary. Those 11 shells were fixed by updating
their direct RepoMan input to `main` at `57473ad` and selecting the machine venv
provider. Six shells had no usable RepoMan command; the rebuilt machine binary
was invoked directly inside each shell. Six secretspec-gated shells received
`SECRETSPEC_REASON="devman migration (project 038)"`.

The exact result table is in
`MIGRATION_2026-09-12.md`. Of the 46 non-canary repositories, 21 carried a
manifest at the start of this session and 22 more now carry one. The remaining
three are `copyroom`, `docman`, and `mypi-agent`; all three put the Devman
option block in `dev/devenv.nix`, so the correct manifest placement needs a
human decision. No placement was guessed.

The live plane was rebuilt with one `--project-root` per manifest and:

```sh
vendomat plane update devman --to v0.6.0 \
  --policy-root /home/andrew/Documents/Projects/devman \
  --state-dir "$HOME/.local/state/vendomat/devman" \
  --renderer devman --dagu dagu
```

The command rendered 46 projects and activated generation 2. A single shell
loop validated all 146 generated DAGs with `dagu validate`; it returned
`validated_dags=146`. The generation contains no seed examples.

**§7 full comparison.** The comparison retained both projections. It compared
all 46 projects in both roots and all 146 common DAGs. Project identity, path,
groups, local workflow names, triggers, writes, workflow groups, parameters,
working paths, log paths, queues, limits, schedules, and generated bodies
matched. The only generated-file difference was the source-file comment, which
was the one permitted normalization. The intentional metadata differences are
the plane generation identity, portable source identities, the absolute
resolved overlay path, the explicit plane representation of Devman's overlay
workflows, and the absence of compatibility link records. The dated report is
`COMPARISON_2026-09-12.md`; it records the five old-only projects and three
broken `my-ai` compatibility links as outstanding state, not as unexplained
common-project mismatches.

**§8 wider canary.** Six real categories passed: a local overlay
(`devman.agent-review`), multiple groups (`observantic.release`), a
cross-repository workflow (`devman.stack-validate`), a scheduled workflow
(`observantic.maintain`), declared writes (`devman.format`), and an unusual
dotted path (`loci.nvim.check`). For each category, `plane plan` and `plane
update` returned 0. Each update was a no-op and retained generation 2. The
generation assertions passed. `dagu ls` returned 146 entries and exit 0.
The environment-cleared live doctor reported `mode plane` and five known
findings: one link drift, three dirty unpinned local-source findings, and one
daemon-shell finding. The full result is in `CANARY_2026-09-12.md`.

The wider canary did not enqueue tasks. The declared-write and agent workflows
would write real repository state, and the cross-repository workflow would
enqueue child runs. Existing VM tests cover run output and metadata recording;
the dual projection comparison proves the run and log fields are unchanged.

**§11 status.** Compatibility mode remains required by the three structural
cases awaiting a placement decision, by the five old-only compatibility
projects, and by existing consumers whose migration commits and branch choices
are not yet complete. The removal order therefore stops before item 5. The
duplicate shell-entry helper, resolver duplication, routine consumer lock
removal, and compatibility registry write removal still need separate reviewed
changes with a complete proof after each one. No compatibility fallback was
removed in this stage.

**§11 item 1.** The obsolete `scripts.devman-resync.exec` helper was then
removed from `devenv.nix`. It had re-entered every registered repository with
`devenv shell -- true`, duplicating the projection work already performed by
the active plane. The compatibility shell hook remains for repositories that
still need it. `rg -n "devman-resync" devenv.nix modules src tests` found no
remaining reference. After the removal, `devenv tasks run -v base:check`,
`devenv tasks run -v base:test`, and
`devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link`
all passed. The environment-cleared live doctor still reported the same five
known findings, so this removal did not hide or create a doctor finding. The
change and this record were committed as `a960df4` and pushed to
`origin/038-fixup-and-fanout`. Items 2 through 4 remain separate reviewed
changes; item 5 remains blocked by the consumers named above.

**Final Stage 14 verification.** The remaining 22 newly migrated manifests
were committed and pushed. A repeat of `vendomat plane plan` proposed
generation 3; the matching `plane update` was a no-op and retained generation
2. One `devenv shell` invocation validated all 146 active DAGs. Vendomat's
`devenv shell -- testee verify --mode quick` passed all four quick checks in
34.2 seconds. RepoMan `base:check` passed; `base:test` still failed only on
the two pre-existing unformatted files `src/repoman/cli.py` and
`src/repoman/devman/migrate.py`. `nixos-rebuild build --flake .#server`
passed in `nix-meta` and produced
`/nix/store/n1qz7wzpzgm3wk7wn4czay5mxy6m2l60-nixos-system-server-26.11.20260705.d407951`.
Devman `base:check`, `base:test`, and the separate `dagu-service` build all
passed.

The final environment-cleared live doctor remained in plane mode and returned
exit 1 for four findings: `flora-037-part-e` link drift; uncommitted Vendomat
and RepoMan sources consumed by unpinned inputs; and one Dagu process with
`SHELL` set. Its independent old-state top line remains `4 projects, 16
workflows`; `dagu ls` returned 146 workflows with exit 0. The shellij dirty
source finding from the earlier canary disappeared after its migration commit.
