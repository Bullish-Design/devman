# Project 038 Wave 3 — investigation report

Date: 2026-09-14
Session type: investigation only. No implementation, workflow, Nix, test, consumer,
generated-state, central-configuration or compatibility file was changed.
Checkout: `devman` `main` at `394f13b`, working tree clean.

---

## 1. Executive brief

Wave 3's largest recorded blocker is false: Dagu 2.15.0 expands `${DAG_NAME%.*}`
inside a DAG-level `env:` value, so one shared workflow source, linked twice,
ran two scheduled runs in two correct project directories with no per-project
rendered file — the mechanism §6.2a said "was never designed, only deferred".
The watcher is already gated by `reload.pending`, proven by experiment, so item I
is a documentation repair and a retry policy, not new plumbing. The scheduled-run
race stays open, because Dagu 2.15.0 has no global pause, no drain, and no queue
that a scheduled run passes through. Three records are wrong and must be corrected
before an operator is asked anything: the watcher claim, the Stage 37 "published"
claim, and the `devman doctor` command that reads the wrong registry. One safety
defect found during the inventory outranks all of Wave 3: nineteen repositories
carry `.devman/project.toml` staged as an empty blob, so an ordinary commit in any
of them deletes the manifest that is now the registration.

---

## 2. Current state — measured

Every number below was measured on 2026-09-14 between 13:57 and 14:20 EDT, from
`/tmp`, with `PYTHONPATH` and `PYTHONHOME` cleared.

### 2.1 The active plane

| Fact | Value | Command |
|---|---|---|
| Active pointer | `generations/2` | `readlink ~/.local/state/vendomat/devman/active` |
| Projects in generation | **45** | `find -L …/active/projects -mindepth 1 -maxdepth 1 -type d \| wc -l` |
| DAG files in generation | **143** | `find -L …/active/dags -maxdepth 1 -type f -name '*.yaml' \| wc -l` |
| DAG digest | `5a06aca3a93a8bd8030a8becc42dc57f0560452b04940518b31f8e7f696fe2b9` | `find -L …/dags -type f -name '*.yaml' -exec sha256sum {} + \| sort \| sha256sum` |
| `dagu ls` | **144** lines | `dagu --dagu-home ~/.local/share/dagu ls \| wc -l` |
| Generation record | schema 1, runtime `v0.6.0`, generation 2 | `cat …/active/generation.json` |
| Dagu version | **2.15.0** | `dagu version` |
| Dagu service | up 42 h, `dagu start-all`, pid 762686 | `ps -eo pid,args` |
| Watcher | up since 2026-09-13T14:38, pid 2421304 | `ps -eo pid,args` |
| `dagu ps` | `No running processes` | `dagu ps` |

**The recorded baseline of "46 projects, 146 DAG files, digest `5acf4cc3…`" is
stale.** The operator's `allium-env` housekeeping landed; `NEXT_SESSION_PROMPT.md`
lines 76-80 predicted exactly this change.

### 2.2 The reload markers

`~/.local/state/devman/` holds `projects` and `watch` only. **No `reload.pending`,
`reload.blocked` or `reload.target` file exists.** `doctor` reports `reload — no
reload in progress`. No reload has completed on this machine, because
`reload.target` is written only on success and is absent.

### 2.3 Configured roots

| Root | Value | Source |
|---|---|---|
| `registryDir` (machine module) | `~/.local/state/vendomat/devman/active` | `paths.dags_dir` in `~/.local/share/dagu/config.yaml` |
| `stateDir` | `~/.local/state/devman` | watcher process argv |
| `overlayDir` | `~/.config/devman` | `devman link status` output |
| Dagu home | `~/.local/share/dagu` | watcher process argv |
| `DEFAULT_REGISTRY` (CLI) | `~/.local/share/devman` | `src/devman/registry.py:75` |
| `reloadMaxWaitSec` | 300 s, a stated bound | `nix/nixos-module.nix:473-494` |

### 2.4 A measurement error in the investigation prompt itself

`WAVE_3_INVESTIGATION_PROMPT.md:138` tells the reader to run `devman doctor`.
**That command inspects the wrong plane.** Bare `devman` on `PATH` is
`/nix/store/k1vd7256…-devman-0.6.0`, which uses `DEFAULT_REGISTRY`
(`~/.local/share/devman`, the compatibility registry). It reports
`mode compatibility — 4 projects, 19 workflows`.

The machine module wraps a different store path with explicit flags. The correct
invocation is:

```bash
devman --registry ~/.local/state/vendomat/devman/active \
       --state ~/.local/state/devman \
       --dagu-home ~/.local/share/dagu doctor
```

It reports `mode plane — 4 projects, 16 workflows`, and adds one check the
compatibility run omits: `generation — 3 projections match generation 2`.

**Both runs see 4 projects, not 45.** `doctor` enumerates projects from
`stateDir/projects/`, which holds four entries (`devman`, `flora`,
`flora-037-part-e`, `pydantree`). All 45 active projects carry a `metadata.json`
inside the generation, and `doctor` reads none of them. So `check_load`
(`dagu validate`) covers **16 of 143** projected files, and `literal dir`,
`projection`, `dag names`, `handlers`, `cross-repo`, `fan-out`, `writes` and
`trigger target` all cover the same 16. This is a blocking gap for requirements
11, 12 and 14, and it is not recorded anywhere.

### 2.5 Doctor findings

Four findings, exit 1, identical under both invocations — the known set:

1. `link drift — flora-037-part-e:devenv.local.nix: create`
2. `local sources — vendomat: uncommitted changes, consumed unpinned by 2 projects`
3. `local sources — repoman: uncommitted changes, consumed unpinned by 1 project`
4. the unpinned `git+file:` advice line

### 2.6 Run durations — the measurement `reloadMaxWaitSec` never had

Parsed from 1309 `status.jsonl` files under `~/.local/share/dagu/data/dag-runs/`;
1306 carried both `startedAt` and `finishedAt`.

| Population | n | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| All runs | 1306 | 2 s | 22 s | 29 s | 61 s | **279 s** |
| `triggerType=1` (scheduled) | 550 | 0 s | 1 s | — | — | **20 s** |
| `triggerType=2` (manual, watcher, hook) | 745 | — | — | — | — | **279 s** |
| `triggerType=4` (retry/restart) | 11 | — | — | — | — | 9 s |

Runs over 300 s: **0**. Runs over 60 s: 14. The longest run is `argentic-test` at
279 s — **within 8 % of the 300 s limit**.

`maintain`, the only workflow that carries a schedule, has max 5 s over 551 runs.

### 2.7 Scheduled workload

46 workflow files in the active generation carry a `schedule:` key: 45 at
`5 0 * * *` and one at `20 0 * * *`. **45 DAGs therefore start at 00:05 every day,
and a scheduled run bypasses its queue.** Their cost is small (max 20 s measured),
but the arrival is simultaneous.

### 2.8 Run history

No DAG name in `~/.local/share/dagu/data/dag-runs/` uses the current dot codec;
every recorded name uses the legacy `-` form, and the newest records are
`devman_format-2904` from 2026-09-14 12:40. Generation 2 was activated
2026-09-12 21:13. Three manifests (`copyroom`, `docman`, `mypi-agent`) were written
2026-09-13 21:41 — **one day after the generation was built.** 48 manifest-backed
checkouts exist on disk; 45 are in the plane. **No generation has been built since
2026-09-12, so the reload boundary has not executed in production at all.**

### 2.9 Central configuration

`~/.config/devman` is on a **detached HEAD** with 68 dirty lines. `vendomat` and
`repoman` are dirty and unpinned, matching findings 2 and 3.

---

## 3. Record reconciliation

Classification values: **resolved and published** · **resolved locally but not
published** · **still blocked** · **no longer applicable** · **contradicted by
current evidence**.

| # | Historical record | Current evidence | Classification | Remaining action |
|---|---|---|---|---|
| R1 | `nix/nixos-module.nix:266-271` and `IMPLEMENTATION_LOG.md:379-381`: "Dagu's own scheduled enqueues, **and the watcher's**, do not pass through `devman run`'s Python entry point" | `src/devman/watch.py:612` calls `run.trigger`, whose first statement is the `reload.pending` refusal (`src/devman/run.py:352-359`). Proven by experiment E2 (§6.1): the dispatcher refused and recorded `refused (1)`. `git log -S` dates the call to `373a8b6`, 2026-09-04; the comment to `5f32817`, 2026-09-12 — **eight days later** | **contradicted by current evidence** | Correct the module comment and the Stage 10 log entry. The watcher half of item I is already built |
| R2 | `NEXT_SESSION_PROMPT.md:232-241`: item K blocked on "three manifest placements" and "seven detached-HEAD branch decisions" | Stage 37 (`IMPLEMENTATION_LOG.md:1770-1793`) records operator approval for all ten, with commit SHAs. Every one of the ten commits exists, carries the manifest, and is on `origin/038-devman-consumer-<name>` | **contradicted by current evidence** — the decisions are made | Do not re-ask the placement or destination question |
| R3 | Stage 37: "Published consumer commits are `a0e922e5…`, `660d6790…`, `3a45c14e…`" | All three are published **to a branch**. For all ten repositories `git merge-base --is-ancestor <commit> origin/main` returns **NO**, and `origin/main:.devman/project.toml` is **absent in all ten** | **resolved locally but not published** to trunk | Land ten branches on `main`, or record an explicit exception |
| R4 | `CONSUMER_MIGRATION_GUIDE.md:200-213`: copyroom, docman, mypi-agent keep identity in `dev/devenv.nix` | No repository under `Documents/Projects` contains a literal `devman.project = …;`. All three now have a root `.devman/project.toml` — but **untracked**: `git cat-file -p HEAD:.devman/project.toml` fails for all three | **no longer applicable** as written; superseded by R3 | Restate the problem as "manifest not on the checked-out branch" |
| R5 | `IMPLEMENTATION_LOG.md:1096`: "copyroom, docman, mypi-agent — no manifest and no literal devman.project" | Both halves now false (R4) | **no longer applicable** | Mark the Stage 16 line as superseded |
| R6 | `CONSUMER_MIGRATION_GUIDE.md:230-243`: five compatibility-only projects — copyroom, docman, fleetman, flora-037-part-e, mypi-agent | copyroom, docman and mypi-agent are manifest-backed (Wave 2H already recorded this, `IMPLEMENTATION_LOG.md:2411-2413`). `fleetman` moved to `Documents/Projects/.archive/fleetman`. `flora-037-part-e` is an orphaned git worktree at `flora/.worktrees/037-part-e-flora`, absent from `flora worktree list` | **contradicted by current evidence** — the set is two, not five | Dispose of `fleetman` and `flora-037-part-e` only |
| R7 | `NEXT_SESSION_PROMPT.md:199-210` and item 4: "`devman link status --all` reads the compatibility registry" | Removed in `976d14e`, the commit before HEAD. `_link_all` takes no registry; `--all` refuses without `--projects-root` | **resolved and published** | Remove item H from the open list |
| R8 | `025/CONCEPT.md:876-888`: "the mechanism for scheduled runs was never designed, only deferred" | The mechanism exists in Dagu 2.15.0 and is proven end-to-end (§6.2, experiments F–J) | **contradicted by current evidence** | Amend `025/CONCEPT.md` Stage 3 item 4 and Stage 4 |
| R9 | `025/CONCEPT.md:859-873`: the collision lives in `project.py`'s `_sources()` and `apply()` | Wave 2G moved both. The read is `src/devman/reconcile.py:283-292`; the write is `:453-454` and `:486-489`. **The collision is worse than recorded:** `:479-484` *deletes* a published file absent from the render | **still blocked**, with a corrected and enlarged description | Update the charter text in the same commit as any fix |
| R10 | `nix/nixos-module.nix:324`: "Caught by the VM test once `reload.pending` made a stuck loop visible" | `grep -rn reload nix/tests/` returns nothing. **The VM test contains no reload subtest.** Coverage is three unit tests in `tests/unit/test_run.py:449-483` and `tests/unit/test_doctor.py:373-417`, which write markers by hand | **contradicted by current evidence** | Correct the comment, or add the test it names |
| R11 | `WAVE_3_INVESTIGATION_PROMPT.md:85-86` cites `LINK_PLANE_A_TO_C_GUIDE.md` §13 | The file ends at §11, line 565. There is no §12 or §13 | **no longer applicable** | Read §1, §5.1 and §9 instead |
| R12 | `NEXT_SESSION_PROMPT.md:42-50` ground truth block | Superseded by §2.1 | **no longer applicable** | Re-measure; do not copy |

### 3.1 Two findings with no prior record

| # | Finding | Evidence |
|---|---|---|
| N1 | **Nineteen repositories had `.devman/project.toml` staged as the empty blob** `e69de29bb2d1…`, while `HEAD` and the working tree held the real manifest. `git status` showed `DA`. `git diff --cached --stat` reported `1 file changed, 4 deletions(-)`. **A commit in any of them would delete the manifest, which is the registration.** In six of them the only committed copy was on an unreachable HEAD. The affected index entries were restored before this report was amended; a second sweep found no manifest staged as an empty blob. Affected: `argentic`, `eventic`, `flora-core`, `flora-qc`, `gitman`, `image-gen-pipeline`, `llgym`, `loci-core`, `loci.nvim`, `nix-nvim`, `nix-paseo`, `poddantic`, `pydantree`, `pyjutsu`, `pyllij`, `pytuin`, `templateer_v2`, `testee`, `vendomat` | initial and follow-up `git -C <repo> ls-files -s .devman/project.toml` sweeps |
| N2 | **Seven repositories sit on orphan commits.** `gitman`, `image-gen-pipeline`, `llgym`, `loci-core`, `nix-paseo`, `pydantree`, `pyjutsu` each have `HEAD` = a commit titled `chore: join the devman machine plane` whose parent is `origin/main`. For each, `git for-each-ref --contains HEAD` is **empty** and `git ls-remote origin` does not contain it. This is a *different* artefact from the Stage 37 branches, which are published. A `git checkout main` or `git gc --prune` loses it | `git for-each-ref --contains $(git rev-parse HEAD)` |

`copyroom`, `docman` and `mypi-agent` are declared centrally and in the share
registry, but contribute **0 DAGs** and are **absent from the active generation**,
because generation 2 predates their manifests by one day (§2.8).

---

## 4. Requirement traceability

Status values: `proven` · `unproven` · `accepted limitation` · `blocking gap`.
Kind: **gate** (hard safety property) · **design** · **operator** · **limitation**.

| # | Requirement | Kind | Current implementation | Evidence | Status | Decision / owner |
|---|---|---|---|---|---|---|
| 1 | An active run is never killed by reload | gate | Drain loop polls `dagu ps` for the literal `No running processes` (`nix/nixos-module.nix:327`) | Loop read; `dagu ps` idle string confirmed live | **unproven** | No test exercises the script (R10). Owner: implementer |
| 2 | Reload cannot report success when the new generation did not start | gate | `set -eu`; `rm -f pending` and `reload.target` are written only after `try-restart` (`:339-342`) | Source read | **unproven** | `try-restart` exit status is never inspected |
| 3 | A blocked reload leaves the old generation available | gate | Timeout branch does not restart Dagu (`:328-334`) | Source read | **proven by construction** | — |
| 4 | A failed reload leaves a structured marker and a clear operator action | gate | `reload.blocked` plus three stderr lines; `doctor` prints the repair | Experiment E6 (§6.1) | **proven** | — |
| 5 | Manual `devman run` has defined behaviour in every reload state | gate | `run.trigger` refuses unless `--print` (`run.py:352-359`) | Experiments E3, E4 | **proven** | — |
| 6 | Watcher-fired runs have defined behaviour in every reload state | gate | `watch.dispatch` → `run.trigger`; refusal caught per entry, logged `refused (1)` | Experiment E2 | **proven** — the record denying it is wrong (R1) | — |
| 7 | Scheduled Dagu runs have defined behaviour in every reload state | gate | **None.** The daemon enqueues in-process and executes no Python | Source read; Dagu capability survey §6.3 | **blocking gap** | Decision A3 |
| 8 | A crashed reload or stale marker is detectable and recoverable | gate | `doctor` detects; nothing recovers | Source read | **blocking gap** | See D1 below |
| 9 | Watcher events have an explicit loss, retry, coalescing and duplicate policy | design | Coalesced per batch at `watch.py:560`; **no retry**; a refusal drops the event | Source read; experiment E2 | **accepted limitation**, undocumented | Decision A2 |
| 10 | Run history and run metadata survive generation changes | gate | Dagu home is outside the generation | `~/.local/share/dagu` is stable; VM subtest at `dagu-service.nix:176` | **proven** | — |
| 11 | Direct links preserve identity, project dir, log dir, queue and schedule | design | Not built | **Experiments F–J prove it is achievable** (§6.2) | **unproven, now achievable** | Decision B1 |
| 12 | Direct linking cannot overwrite authored central workflow files | gate | Not built | Collision confirmed live (R9) | **blocking gap** | Decision B2 |
| 13 | A `registryDir` move cannot merge authored and generated namespaces | gate | Blocked deliberately; `registryDir` stays at `~/.local/share/devman` | `registry.py:62-75`; `reconcile.py:283-292` vs `:453-489` | **blocking gap** | Decision B2 |
| 14 | Compatibility removal leaves no supported repository without workflow, identity, task surface, trigger or rollback | gate | Compatibility mode still on; identity fallback still present | §3 R4, R6; fleet sweep | **unproven** | Decision C1, C4 |
| 15 | Rollback restores the prior generation and preserves recovery | gate | `vendomat plane rollback`; generation 1 retained | Both generations present on disk | **unproven** | Never exercised since 2026-09-12 |
| 16 | **New.** A scheduled run in the wrong directory must not report success | gate | `base.yaml` supplies `working_dir: ${DEVMAN_PROJECT_DIR}`; nothing verifies it at run time | **Experiment H measured `Succeeded` with `PWD=/tmp/${DEVMAN_PROJECT_DIR}`** | **blocking gap** | Decision B3 |
| 17 | **New.** `doctor` must see the whole plane | gate | Enumerates from `stateDir`, sees 4 of 45 | §2.4 | **blocking gap** | Precedes every other gate |
| 18 | **New.** A commit must not delete a manifest | gate | None | N1 | **blocking gap** | Operator, before anything else |

---

## 5. Measurements and experiments

All experiments ran in disposable directories under `/tmp` with their own Dagu
home. The live plane, the live Dagu home, the active generation, the central
configuration and every consumer checkout were untouched. Cleanup is recorded in
§5.3.

### 5.1 The reload gate — isolated registry, isolated Dagu home

Fixture: `/tmp/inv-wave3` with one fake project `fix`, a projected `format.yaml`,
a `dags/` link, a `metadata.json` naming `**/*.py → format`, and a throwaway Dagu
home so a stray enqueue could not reach the live daemon.

| # | Hypothesis | Command | Observed result | Conclusion |
|---|---|---|---|---|
| E1 | Control: with no marker the dispatcher reaches `dagu enqueue` | `echo '<watchexec json>' \| devman … watch --dispatch` | Reached `dagu enqueue`; failed only because the throwaway home had no DAG; logged `refused (1)` | The gate is not what stops a run in the control case |
| E2 | **The watcher refuses while `reload.pending` exists** | same, after `date -u > state/reload.pending` | `devman: refusing to enqueue 'format' in 'fix' / a plane reload has been pending since …`, exit 1 | **The watcher IS gated.** R1 is false |
| E3 | Manual `devman run` refuses | `devman … run format --project fix` | Same refusal, exit 1 | Requirement 5 holds |
| E4 | `--print` is exempt | `devman … run format --project fix --print` | Printed the enqueue line, exit 0 | Requirement 5 holds |
| E5 | `doctor` shows pending | `devman … doctor` | `.. reload  pending since … — waiting for active runs to finish` | Requirement 4 partly holds |
| E6 | `doctor` shows blocked | after writing `reload.blocked` | `!! reload  blocked since … / Dagu was not restarted … / operator action: …` | Requirement 4 holds |

**Side finding from E1 and E2:** `fired.jsonl` records both as `refused (1)`. A
reload refusal is indistinguishable from a resolution refusal in the watcher's own
log, and `check_watcher` never classifies a refusal as a finding. A machine with a
stuck marker shows `watcher ok` while every save is dropped.

### 5.2 Render-to-link — isolated Dagu home, isolated scheduler

Fixture: `/tmp/inv-dagu2`, its own `config.yaml` (`dags_dir`, `symlinks: true`,
`recursive: true`, port 18080, scheduler port 18090), run with `dagu scheduler`
only, so the live port 8080 was never contended.

| # | Hypothesis | Setup | Observed result | Conclusion |
|---|---|---|---|---|
| F | Two links to one source give two DAGs | `dags/projA.bare.yaml` and `dags/projB.bare.yaml` → `shared/bare.yaml` | `dagu ls` listed `projA.bare` and `projB.bare` | **The DAG name comes from the link basename. Two links to one target do not collide** |
| G | `${DAG_NAME}` resolves in a DAG-level `env:` value | `env: - PROBE_NAME: "${DAG_NAME}"`, two links, scheduler run | `PROBE_NAME=[projA.named]` and `[projB.named]` | **One shared source yields per-link values** |
| H | Command substitution and `dotenv` interpolation work | `env: DEVMAN_PROJECT_DIR: "` `` ` ``…`` ` ``"`, and `dotenv: [/…/${DAG_NAME}.env]` | **Both failed.** Backticks and `$(…)` were left literal; `${DAG_NAME}` was not expanded in the `dotenv` path; `DEVMAN_PROJECT_DIR` was unset. `PWD=/tmp/${DEVMAN_PROJECT_DIR}` and `PWD=/tmp/`` `…` ``. **All four runs reported `Succeeded`** | **No command substitution at DAG level. No interpolation in `dotenv` paths. And an unexpanded variable produces a literal directory and a green run** — requirement 16 |
| I | A per-project subdirectory namespaces the DAG name | `dags/projA/check.yaml` and `dags/projB/check.yaml` → one source, each with a sibling `.env` | `warning: duplicate DAG name "check"` … **`No DAGs found`** | **Recursive discovery does not namespace by directory, and a collision refuses both DAGs.** The flat dotted codec is required |
| J | Shell parameter expansion works, and matches the codec | `env:` with `${DAG_NAME%%.*}`, `${DAG_NAME%.*}`, `$DAG_NAME`, `${env.DAG_NAME}` | `E_STRIP=[projA]`, `E_PREFIX=[/tmp/inv-dagu2/projA.expand]`, `$DAG_NAME` and `${env.DAG_NAME}` both resolve | **`${VAR%pattern}` works.** Prefix concatenation works |
| **K** | **End-to-end: one shared source, two scheduled runs, two correct directories** | `shared/final.yaml` with `DEVMAN_PROJECT_DIR: "/tmp/inv-dagu2/${DAG_NAME%.*}"` and `working_dir: ${DEVMAN_PROJECT_DIR}`; links `projA.check` and **`loci.nvim.check`** | `projA.check` → `PWD=/tmp/inv-dagu2/projA`. `loci.nvim.check` → `PWD=/tmp/inv-dagu2/loci.nvim`. Both `Succeeded` | **The §6.2a blocker is removed.** And the codec detail matters: greedy `%%` gave `loci` (wrong), lazy `%` gave `loci.nvim` (right), mirroring `registry.py`'s `rsplit` rule |
| L | The convention K depends on holds for the fleet | compare each active `metadata.json` `path` against `<projectsRoot>/<name>` | **45 of 45 conform.** In the old share registry, `fleetman` violates (`.archive/fleetman`) and `flora-037-part-e` has no metadata | The convention holds for everything in the plane today |

### 5.3 Cleanup

`rm -rf /tmp/inv-wave3 /tmp/inv-dagu2` and `rm -f /tmp/inv-dagschema.json
/tmp/inv-cfgschema.json /tmp/inv-doctor-plane.txt /tmp/inv-durations.tsv
/tmp/.x_steps.json`. Verified removed. `/tmp/.x_steps.json` was created by a
sub-investigation and is included here for completeness.

After cleanup the plane re-measured identically: `generations/2`, 45 projects,
143 DAG files, digest `5a06aca3…`, no reload markers.

### 5.4 Not run, and why

| Experiment | Why not |
|---|---|
| Reload while a run is active, on the live plane | Writes `reload.pending` to live state and restarts the live Dagu. Belongs in the VM test |
| Generation activation and rollback | Changes the active pointer. Forbidden by the safety boundary |
| Does an `active → generations/N` re-point invalidate `.dag.index`? | Requires an activation. **This is the single highest-risk unproven assumption** — `.dag.index` stores fully resolved paths pinned to `generations/2` |
| Does a suspended DAG still accept a manual enqueue? | Requires writing a suspend flag into the live Dagu home |
| `max_clean_up_time_sec` as a bounded drain | Requires a long-running live run |

---

## 6. Dagu 2.15.0 capability survey

Pin: `nix/dagu.nix` fetches a prebuilt release tarball, `v2.15.0`, sha256
`7789fd5bf53101ff6442faf602ae404f3e64f438e982c86c57653277d93d1ad2`. There is **no
Go source and no `-source` derivation on this machine**, so claims below come from
the binary's own `dagu schema`, from `--help`, from live state, or from experiment.
`dagu schema dag` is `additionalProperties: false`, so absence of a key is proof.

| Capability | Verdict | Evidence |
|---|---|---|
| Global scheduler pause / maintenance mode | **Absent** | `dagu schema config` `SchedulerDef` holds only `failure_threshold`, `heartbeat_interval`, `lock_retry_interval`, `lock_stale_threshold`, `port`, `stale_threshold`, `zombie_detection_interval` |
| `dagu suspend` / `pause` / `resume` CLI verb | **Absent** | `dagu --help`, 30 commands |
| Per-DAG suspend | **Present**, API/UI only | config key `suspend_flags_dir`; live dir `~/.local/share/dagu/suspend`, currently empty |
| Suspend semantics | **Drops**, not defers | symbol names `dropSuspendedQueuedRun`, `dropSuspendedCatchupState` |
| Queue system | **Present** | Dagu is configured with six queues on this machine |
| Does a `schedule:` run enter the queue? | **No** | Measured in S-1: 58 scheduled runs started at once while queue depth stayed 0; the enqueued control path serialized |
| Runtime queue close or drain | **Absent** | `queues.enabled` is configuration only. Changing it needs the restart that the gate is meant to protect |
| `dequeue` | Removes a **queued** run only | `dagu dequeue --help` |
| `dagu ps` as a "no active runs" predicate | **Unreliable** | reads a process store; `proc.stale_threshold` default 90 s, `zombie_detection_interval` 45 s. A killed run can read alive for 90 s. It is not a lock |
| DAG-level `max_active_runs` | **Deprecated and ignored** | schema text |
| `preconditions` at DAG level | Present, but **drops** | schema; and this repository measured that an unmet DAG-level precondition records `Aborted` |
| `skip_if_successful` | Scheduled runs only | schema |
| Symlink discovery | **Follows, and resolves fully** | `dag_discovery.symlinks`; `.dag.index` stores the fully resolved target |
| Scheduler DAG discovery | fsnotify-driven in-memory index, not a per-tick re-read | symbols `entryReaderImpl.handleFSEvent`, `reloadDAGFile`; on-disk `.dag.index` |
| Stop signal escalation | Schema claims `max_clean_up_time_sec` kills; this repository measured no escalation (022 M3) | **contradiction, untested** |

**Consequence:** option A3.1 (a Dagu-native pause or drain) is **closed negative**.
Dagu has a queue system, but scheduled runs bypass it, and Dagu has no runtime
operation to close or drain a queue. The two Dagu-native gates that reach the
scheduled path — per-DAG suspend and DAG-level preconditions — both *destroy* the
run rather than defer it. The queue is therefore not a scheduled-run maintenance
gate.

---

## 7. Option matrices

### 7.1 Decision Group A — reload and maintenance gate

#### A1 — gate owner

| Option | Requirements met | Benefits | Costs | Risks | Implications | Opportunities | Migration | Rollback | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| **A1-1 Stable markers + cooperative clients (current)** | 3,4,5,6 | Already built and proven for two of three producers; survives a crash as a file; visible to `doctor` | Cannot cover a producer that runs no Python | Scheduler ignores it (req 7); a blocked reload never clears `pending` (D1) | The marker stays the contract | Add a scheduler-side reader (A3-3) and it covers everything | none | delete a file | E2–E6 |
| A1-2 Shared lock or lease | 5,6,7 if every producer takes it | Atomic; a lease expires, so no permanent wedge | The scheduler still takes no lock — it is in-process Go | Adds a second state machine beside the markers | Two mechanisms to keep agreeing | Lease TTL solves D1 | rewrite `run.trigger` | — |
| A1-3 systemd maintenance state | 5,6,7 | One state for every producer; systemd already owns the units | `dagu` is `start-all` — stopping the scheduler drops the web UI and coordinator too; `StartLimitBurst=5/60s` can wedge the unit | Stopping Dagu makes `dagu ps` unusable, and the drain loop then blocks for the full 300 s (D2) | The gate becomes unit ordering | Clean conceptually | new units | `systemctl` revert | §6, §8 D2 |
| A1-4 Dagu-native pause or drain | — | — | — | — | — | — | — | **Closed negative**, §6 |
| A1-5 Accept a documented global race | none | free | leaves req 7 open | a scheduled run can be killed by the restart | — | — | none | — | current state |

#### A2 — watcher behaviour

The watcher already **refuses and drops** (option 2). The decision is whether to
keep that.

| Option | One event | Many events | Change during shutdown | Stale marker | Duplicates | Hash loop break | Crash after accept |
|---|---|---|---|---|---|---|---|
| **A2-1 Wait and retry while pending** | delayed | batches pile into watchexec's `queue` | queued, then fires | **blocks forever** — D1 makes this dangerous | coalesced per batch | unaffected | batch lost, next batch arrives |
| **A2-2 Refuse and drop (current)** | lost | all lost | lost | harmless | n/a | **recovers the loss**: the next save re-fires, and the content hash still differs | isolated per entry |
| A2-3 Persist and replay | none lost | replay storm after reload | replayed | replay after a stale marker clears | needs dedup | may fire a no-op run | needs durable state |
| A2-4 Stop and restart the watcher | lost during the window | same | same | watcher stays down | n/a | same as A2-2 | — |

**A2-2 is the right default, and the content-hash precondition is why.** A dropped
`format` event is recovered by the next save, because the hash still differs. The
defect is not the drop; it is that the drop is invisible (§5.1 side finding).

#### A3 — scheduled-run behaviour

Dagu has a queue system, but a scheduled run does not enter it. Dagu also has no
runtime queue close or drain operation. These are separate facts from the queue
system being enabled.

| Option | Requirements met | Benefits | Costs | Risks | Rollback | Evidence |
|---|---|---|---|---|---|---|
| A3-1 Dagu pause or drain | — | — | — | — | — | **Closed negative** (§6) |
| A3-2 Gate the queue | — | Queue admission would defer work | Scheduled runs bypass the queue; no runtime queue close or drain exists | It cannot gate the scheduled path | — | **Closed negative** — S-1; §6 |
| **A3-3 Wrap the scheduled entry point** | 7 | Covers the only uncovered producer; reuses the marker already proven | Every scheduled DAG's step must call the wrapper; a missed file is silently ungated | A wrapper that refuses turns a nightly run into a failed run unless it exits 0 with a skip | remove the wrapper | — |
| A3-4 Generate a per-project wrapper | 7, 11 | Carries project context too | Re-introduces generation, which B wants to remove | conflicts with B1 | — | — |
| **A3-5 Accept and document the race** | none | free; the measured exposure is small | leaves req 7 open | 45 DAGs start at 00:05; a reload in that second can kill one | none | §2.6, §2.7 |
| A3-6 Remove schedules | 7 | closes it absolutely | loses `maintain` on 45 repositories | operator loss | restore | §2.7 |

**The measured risk is smaller than the records imply.** Scheduled runs on this
machine max at **20 s** and `maintain` maxes at **5 s**. The exposure is a reload
landing inside a window of a few seconds, once a day, at 00:05 — and a killed
`maintain` run costs one day of cache pruning. A3-5 is defensible *if it is stated
with this measurement*. A3-3 is the only option that actually closes it.

#### A4 — wait and failure policy

| Option | Verdict |
|---|---|
| Indefinite drain | **Reject.** D2 shows a down Dagu makes the loop never terminate |
| **A measured deadline** | **Adopt.** The measurement now exists: max observed run 279 s over 1306 runs; p99 61 s. The current 300 s is above the max by 8 % — **thin but not wrong**. 600 s gives a 2× margin over the observed worst case |
| A configured deadline | Already configurable (`reloadMaxWaitSec`) — keep |
| Refuse to activate after the deadline | **Already the behaviour**, and correct |

No option kills an active run, and none is proposed.

#### A5 — observable states

| State | systemd | doctor | marker on disk | Operator action | Gap |
|---|---|---|---|---|---|
| idle | inactive (oneshot) | `ok no reload in progress` | none | — | cannot tell "never fired" from "fired and finished" |
| pending / waiting | activating | `.. pending since …` | `reload.pending` | wait | does not say **what** it waits for |
| waiting for admission / watcher drain / scheduler drain | — | — | — | — | **not modelled at all** |
| started | — | — | — | — | **not modelled** |
| complete | inactive, success | `ok` | `reload.target` updated | — | `reload.target` is never read by `doctor` |
| blocked | failed, exit 1 | `!! blocked since …` + repair | **both** `blocked` and `pending` | restart the service | `!!` text says "the previous generation is still serving runs", which reads as healthy while **every** enqueue is refused |
| failed restart | failed | `.. pending` | `pending` only | none stated | **indistinguishable from waiting** |
| stale marker / crashed reload | inactive | `.. pending` | `pending` | none stated | **no timestamp age test, no recovery** |

#### A6 — proof matrix

| Check | Unit | Harness | VM |
|---|---|---|---|
| `run.trigger` refuses on pending; `--print` exempt | **exists** | | |
| `doctor` reload states | **exists** | | |
| **Watcher dispatcher refuses on pending** | **missing** — add it; §5.1 E2 is the specification | | |
| Drain loop terminates on the idle string | | ✓ | |
| Drain loop when Dagu is down (D2) | | ✓ | |
| Timeout writes `blocked`, keeps the old generation, does not restart | | | ✓ |
| **Timeout clears the plane for manual use** (D1) | | | ✓ |
| `try-restart` failure is detected (req 2) | | | ✓ |
| Long active run survives activation | | | ✓ (§5.2 of the guide names nine assertions) |
| Several active runs; simultaneous activations | | | ✓ |
| Stale marker recovery | | ✓ | |
| Rollback, history, retention, queue, working dir, log dir | | | ✓ |
| Scheduled run during every marker state | | | ✓ |

**The gate is not ready: no proof exists for the scheduled producer, and the VM
test contains no reload subtest at all (R10).**

### 7.2 Decision Group B — render-to-link and registry layout

#### B1 — project-directory mechanism

| Option | Requirements met | Benefits | Costs | Risks | Implications | Opportunities | Migration | Rollback | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| B1-1 Keep generated per-project files | 11 today | Zero change; path is explicit and auditable; `doctor literal dir` can check it | Keeps ~500 lines of `project.py`; keeps the B2 collision; edits need re-projection | none new | `registryDir` cannot move | — | none | none | current |
| **B1-2 Link one shared source; derive the directory from `${DAG_NAME%.*}`** | 11 | **Proven end-to-end** (K); removes the renderer; an in-place source edit takes effect with no re-projection; unblocks B2 and L | Requires the convention `<projectsRoot>/<project>`; no command substitution available to escape it | **A repository outside the convention silently runs in the wrong or a literal directory and reports `Succeeded`** (H) | The projects root becomes a machine-level contract | `registryDir` can then move | re-link 143 DAGs | restore the renderer | **F, G, I, J, K, L** |
| B1-3 Stable launcher mapping name → directory | 11 | Arbitrary paths | **Not available**: command substitution does not run at DAG level (H). Would need a step-level launcher, which loses `working_dir` | the launcher becomes the working dir | — | — | — | **H** |
| B1-4 Dagu params or context | 11 | — | A scheduled run receives declared defaults only; a default cannot vary per link | — | — | — | — | schema |
| B1-5 One Dagu per project | 11 | total isolation | 45 daemons, 45 queues, 45 homes | resource cost; queues stop being machine-global | contradicts the charter | — | — | — |
| B1-6 Keep rendering until fully proven | — | safe | Wave 3 L does not move | — | — | — | — | — |

**B1-2's convention holds for 45 of 45 projects in the plane today (L).** It fails
for `fleetman` (`.archive/`) and `flora-037-part-e` (a worktree) — neither of which
is in the plane.

#### B2 — registry and overlay layout

The collision, re-verified in the current tree:

- **read** `overlay_root/projects/<p>/workflows/*.yaml` — `reconcile.py:283-292`
- **write** `registry/projects/<p>/workflows/<name>.yaml` — `reconcile.py:453-454`, `:486-489`
- **delete** `registry/projects/<p>/workflows/<name>.yaml` for any published file
  absent from the render — `reconcile.py:479-484`

At risk: five tracked, hand-authored files plus a README under
`~/.config/devman/projects/devman/workflows/` — `agent-review.yaml`,
`bench-entry.yaml`, `gitman-commit-message.yaml`, `plane-report.yaml`,
`stack-validate.yaml`. Only `devman` has such a directory.

| Option | Requirements met | Benefits | Costs | Risks | Rollback | Evidence |
|---|---|---|---|---|---|---|
| **B2-1 Keep `registryDir` where it is until B1-2 is proven in the VM** | 12,13 | Zero risk today; matches the recorded gate | Wave 3 L stays open | none | none | `registry.py:62-75` |
| B2-2 Move after B1-2 removes the write | 12,13 | The intended end state | Depends on B1-2 landing | If any write path survives, five tracked files are destroyed | restore from the central repo | R9 |
| **B2-3 Split authored and generated into separate roots** | 12,13 | Removes the collision **without** depending on B1-2; each path has one owner | A third root to explain | low | revert the option default | — |
| B2-4 Two-root migration window | 12,13 | gradual | Two readers and two writers at once — the shape that created the collision | high | — | — |
| B2-5 Never move; document the current layout as the end state | 12,13 | cheapest | Contradicts `025/CONCEPT.md` §6.1 | needs a charter amendment | — | — |

#### B3 — the direct-link gate

Status of each required piece of evidence:

| Evidence required | Status |
|---|---|
| In-place source edit seen through a symlink | Recorded in `025/CONCEPT.md` §6.3 for the manual case; **not re-measured under renderer removal** |
| A scheduled run after that edit | **not measured** |
| Correct working and log directory | **proven** (K) for `working_dir`; `log_dir` not separately asserted |
| Correct queue and run history | **not measured** |
| Multiple workflow documents | recorded in §6.3; not re-measured |
| Cross-repository names and duplicate-name refusal | **proven** (F, I) — two links to one target are distinct; a duplicate name refuses **both** |
| Activation and rollback | **not measured** |
| No authored-file overwrite | depends on B2 |
| Reload while a run is active | **not measured** |
| No dependence on an untracked shell entry point | satisfied by construction |
| **New: a wrong or missing project directory must refuse, not succeed** | **failed** (H) |
| **New: `.dag.index` must re-resolve across a generation swap** | **not measured — highest risk** |

**The gate is not met. It is now achievable, which it was not before.** The
smallest prototype that would remove the remaining uncertainty is a VM subtest that
links one shared source under two project names, activates a generation, lets the
scheduler fire both, and asserts two distinct working directories, two log
directories, two queue assignments and two history entries.

### 7.3 Decision Group C — compatibility mode and fleet migration

#### C1 — the supported set

| Project | Manifest | In plane | Disposition | Owner | Lost capability | Rollback |
|---|---|---|---|---|---|---|
| `copyroom`, `docman`, `mypi-agent` | on disk, **untracked** | **no** | Land the published Stage 37 branch, then rebuild the generation | implementer | none | the branch remains |
| `fleetman` | none; literal Nix in `.archive/fleetman/devenv.nix:23` | no | **Archive.** Already moved to `.archive/` | operator | its 6 link declarations | central overlay retained |
| `flora-037-part-e` | none; state-side entry points at `flora/.worktrees/037-part-e-flora`; not in `flora worktree list` | no | **Archive or re-register.** It is an orphaned worktree, and it is the source of doctor finding 1 | operator | the `devenv.local.nix` link | — |
| `foreman`, `my-ai`, `siteman` | none | no | **Archive.** Central overlay only, no checkout | operator | none | overlay retained |
| `forgelab`, `lodestar` | none; **live literal `devman.project`** | no | **Archive** (already decided, `IMPLEMENTATION_LOG.md:2039-2044`); `lodestar`'s overlay waits on a corrupted index | operator | none | — |

**The compatibility-only set is two live cases, not five** (R6).

#### C2 — structural manifest placement

**Resolved. Do not ask again.** Stage 37 approved a root `.devman/project.toml`
for all three, the commits exist, carry the manifest, and are on
`origin/038-devman-consumer-<name>`. The remaining item is not a placement
decision; it is that the branch is not merged and the checkout is not on it (R3).

#### C3 — branch decisions for the seven

**Resolved as a decision. Two artefacts, and the records conflate them.**

| Artefact | State | Action |
|---|---|---|
| Stage 37's approved commit, e.g. `gitman` `e0f706cb…` | on `origin/038-devman-consumer-gitman`; **not merged to `main`**; `origin/main` has no manifest | land it on `main` |
| The checkout's `HEAD`, e.g. `gitman` `bb88523` "chore: join the devman machine plane" | **orphan** — zero containing refs, absent from origin | operator: keep or abandon (N2) |

Option comparison for the orphan commit, per repository: merge into the owner
branch · continue on the existing feature branch · create and publish a branch ·
keep local · **abandon and recreate from current trunk**. Recreation is cheap: the
commit adds a four-line manifest that the Stage 37 branch already carries. No
force-push and no branch move is proposed.

#### C4 — identity fallback policy

`grep -rn 'devman\.project[[:space:]]*=' --include='*.nix'` over
`Documents/Projects` returns **zero hits**. The only live users of
`_legacy_identities()` are `forgelab` and `lodestar`, both in the archive set, plus
four repositories under `.archive/`.

| Option | Verdict |
|---|---|
| C4-1 Remove the literal fallback once supported consumers have manifests | **Recommended**, after the archive set leaves. It is two repositories away |
| C4-2 Finite allowlist | Unnecessary — the set is `forgelab`, `lodestar` |
| C4-3 Time-bounded deprecation | Over-engineered for two repositories |
| C4-4 Move to a separate package | `devman_link.identity` is already that package |

Note `resolve_project_identity` calls `_legacy_identities()` **unconditionally**,
even when a manifest exists, because the manifest/Nix drift refusal needs both
(`identity.py:260-271`). Removing the fallback also removes that refusal — state
that trade explicitly.

#### C5 — compatibility write retirement gate

| Operation | Caller | Data | Current path | Replacement | Evidence | Retirement gate |
|---|---|---|---|---|---|---|
| Enumerate registered projects | `devman link status --all` | project list | compatibility registry | manifest sweep over `--projects-root` | `976d14e`; Wave 2H recorded 48 blocks, 246 clean, 0 refusals | **already retired** (R7) |
| Publish a rendered projection | `devman project apply` → `reconcile.compatibility_apply` | workflow bodies, `dags/` links | `registry/projects/<p>/workflows/` | the machine-plane generation | `reconcile.py:437` "until item 4 lands" | devman's own self-adoption must stop needing it |
| Keep `metadata.json` | shell entry | identity, path, groups, triggers | `stateDir/projects/<p>/` | the generation's own `metadata.json` | 45 of 45 present in the generation | **`doctor` must read the generation first** (req 17) |
| Keep `triggers.toml` / `writes.toml` copies | shell entry | drift check | `stateDir/projects/<p>/` | same | — | with the above |
| Literal `devman.project` | `devman_link.identity` | identity | `devenv.nix`, `devenv.local.nix` | manifest | zero live non-archive hits | C4-1 |
| Rollback by pinning a pre-adapter revision | operator | — | git | — | `IMPLEMENTATION_LOG.md:1221-1223` | keep until compatibility mode is removed |

**Retire first:** the enumeration read (done). **Retire last:** compatibility mode
itself, because it is still the documented rollback.

---

## 8. Recommended design

### D1 — Fix the permanent-refusal defect first (a safety bug, not Wave 3)

The timeout branch (`nix/nixos-module.nix:328-334`) writes `reload.blocked` and
exits 1 **without removing `reload.pending`**. `run.trigger` tests only `pending`.
So after a blocked reload, **every manual run and every watcher-fired run on the
machine is refused indefinitely**, and `doctor`'s `!!` line says "the previous
generation is still serving runs", which reads as healthy.

Recommendation: on timeout, remove `reload.pending` and keep `reload.blocked`. The
old generation is still serving, so refusing new work earns nothing. Make
`check_reload` report both markers rather than returning early on `blocked`.

### D2 — Make the drain loop terminate when Dagu is down

`dagu ps 2>/dev/null || true` yields an empty string when Dagu is stopped, which is
`!= "No running processes"`, so the loop runs the full 300 s and then blocks —
even though there are definitionally no active runs. Recommendation: treat a
non-zero `dagu ps` exit **and** a stopped `dagu.service` as "drained".

### D3 — Correct the records before asking the operator anything

R1 (the watcher claim), R3 (Stage 37 "published"), R7 (the removed registry read),
R10 (the VM test that does not exist) and R11 (the missing §13). Rule 2 requires
the charter change in the same commit.

### D4 — Give `doctor` the whole plane (requirement 17)

`doctor` must enumerate from the active generation when it runs in plane mode. It
currently validates 16 of 143 files. Every Wave 3 gate that says "doctor gains no
new finding" is weak until this lands.

### D5 — Group A: keep markers, add a scheduler-side reader, raise the deadline

Adopt **A1-1 + A3-3 + A4 measured deadline**, and keep **A2-2**.

- The marker stays the contract. It already covers two of three producers.
- Add a DAG-level `preconditions:` entry to the one shared `maintain` source that
  tests for the marker. Dagu drops rather than defers a precondition failure, and
  for `maintain` that is acceptable: it is idempotent, it runs daily, and the next
  day recovers it. **State that in the workflow file, with this measurement.**
- Raise `reloadMaxWaitSec` from 300 s to **600 s**, citing max observed 279 s over
  1306 runs. 300 s is above the observed max by only 8 %.
- Make a refusal visible: record the reload refusal distinctly in `fired.jsonl`,
  and make `check_watcher` report a recent refusal as a finding.

Rejected: A1-3 (systemd) because `dagu start-all` bundles the scheduler with the
web UI, and stopping it makes `dagu ps` unusable, worsening D2. A1-4 and A3-1/A3-2
are closed negative (§6). A3-6 loses `maintain` on 45 repositories.

### D6 — Group B: prototype B1-2, adopt B2-3, do not move `registryDir` yet

- **B1-2** is proven in isolation (K). Prototype it in `nix/tests/dagu-service.nix`
  before touching `project.py`. Use `${DAG_NAME%.*}` — **lazy, not greedy** — and
  add a test whose project name contains a dot, because `loci.nvim` is live.
- The convention `<projectsRoot>/<project>` becomes a machine-level contract. It
  holds for 45 of 45 today (L). `doctor` must refuse a registered project whose
  path does not satisfy it.
- Requirement 16 must be closed in the same change: a shared source that resolves
  to a missing directory currently reports `Succeeded` (H). Add a first step, or a
  DAG-level precondition, that refuses when `$DEVMAN_PROJECT_DIR` is not a
  directory.
- **B2-3** (separate authored and generated roots) removes the collision without
  waiting for B1-2, and is the smaller, safer change.
- **B2-1**: `registryDir` does not move in Wave 3.

### D7 — Group C: land ten branches, archive two, then remove the fallback

1. Repair N1 in all nineteen repositories **before any commit anywhere**.
2. Land the ten Stage 37 branches on `main`, one PR each.
3. Decide the seven orphan commits (C3) — recreation is the cheap answer.
4. Archive `fleetman` and `flora-037-part-e`; clear doctor finding 1.
5. Rebuild and activate a generation; `copyroom`, `docman` and `mypi-agent` join.
6. Then remove the literal identity fallback (C4-1).
7. Compatibility mode itself stays until devman's self-adoption leaves
   `project apply`.

---

## 9. Operator decision sheet

Only one operator decision remains. Everything else is resolved by evidence in §3
or is now an implementation step below.

| # | Decision | Recommended | Alternatives | Consequence | Latest safe point | Owner | Evidence still needed |
|---|---|---|---|---|---|---|---|
| **O1** | Disposition of the seven orphan `chore: join the devman machine plane` commits | Abandon and rely on the published Stage 37 branches | merge to owner branch · publish a new branch · keep local | A checkout change or `git gc --prune` can lose them | before moving any of the seven checkouts | operator | Confirm the Stage 37 branch content equals each orphan commit |

---

## 10. Implementation sequence

Each item is one commit with its own evidence directory under
`artifacts/<TS>-<slug>/`. Do not batch.

| # | Work unit | Gate before starting |
|---|---|---|
| 1 | **Operator repairs N1** in nineteen repositories | completed before this sequence; N1 |
| 2 | **Record corrections** — R1, R3, R7, R10, R11, and the `025/CONCEPT.md` amendments for R8 and R9 | none |
| 3 | **D1 + D2** — the reload script's timeout and down-Dagu defects, plus `check_reload` reporting both markers | none |
| 4 | **D4** — `doctor` enumerates the active generation | none |
| 5 | **Watcher unit test** — the dispatcher refuses under `reload.pending` (§5.1 E2 is the specification), and a reload refusal is distinguishable in `fired.jsonl` | 3 |
| 6 | **VM reload subtest** — the nine assertions of guide §5.2, plus timeout, blocked, stale marker and `try-restart` failure | 3, 5 |
| 7 | **Set `reloadMaxWaitSec` to 600 s**, citing the measured 279 s maximum and p99 of 61 s | §2.6; A4 |
| 8 | **Resolve the scheduled-run race** — implement the selected A3 path and prove scheduled behaviour in the VM | §6; §7.1 A3; guide §5.3 item 4 |
| 9 | **Adopt `<projectsRoot>/<project>` as a machine contract** and run the B1-2 prototype | Experiment L; §7.2 B1-2 |
| 10 | **Requirement 16 refusal** — a missing `DEVMAN_PROJECT_DIR` must not report success | 9 |
| 11 | **B2-3** — split authored and generated roots | 9, 10 |
| 12 | **Renderer narrowing** — only after 9, 10 and 11 pass | 11 |
| 13 | **Land the ten Stage 37 branches**, one PR each; rebuild and activate a generation | O1; R3; Stage 37 records |
| 14 | **Archive `fleetman` and `flora-037-part-e`**, then clear doctor finding 1 | R6; §7.3 C1 |
| 15 | **Remove the literal identity fallback** (C4-1), stating the lost drift refusal | 13, 14 |
| 16 | **Documentation** — `AGENTS.md` property 6, `AGENTS_GUIDE.md` §4, `README.md`, `USER.md`, `025/CONCEPT.md` §6.2a/§6.3/Stage 3/Stage 4 | after each of the above |

---

## 11. Stop conditions

Stop and ask when any of these is true.

1. **A `git status` in any repository again shows `D `, `DA` or `AD` for
   `.devman/project.toml`.** The nineteen initial index entries were repaired (N1).
2. A change would move, delete or force-push any of the seven orphan HEADs before
   O1 is answered.
3. `devman doctor` gains a finding outside the four known ones.
4. The active pointer, project count (45), DAG count (143) or digest
   (`5a06aca3…`) changes without an intended activation.
5. A `registryDir` change would make `overlayDir` and `registryDir` share a root
   before B2 lands. Five tracked files are destroyed by the write path, and
   `reconcile.py:479-484` deletes as well as overwrites.
6. A B1-2 change is proposed for a repository whose path is not
   `<projectsRoot>/<project>`.
7. A scheduled run is observed reporting `Succeeded` with a literal
   `${DEVMAN_PROJECT_DIR}` directory (H).
8. A generation activation is proposed before the `.dag.index` re-resolution
   question is answered (§5.4).
9. Compatibility mode, compatibility registry writes or a consumer pin would be
   removed without its gate passing.

---

## 12. Definition of done for Wave 3

Wave 3 is complete when all of the following are true and recorded.

**Tests**

- [ ] `tests/unit/test_watch.py` proves the dispatcher refuses under
      `reload.pending` and records it distinguishably.
- [ ] `tests/unit/test_doctor.py` proves `check_reload` reports a blocked reload
      that is also pending, and an aged stale marker.
- [ ] `base:check`, `base:unit` and `base:test` pass; any dropped test count is
      explained.

**VM proofs (`nix/tests/dagu-service.nix`)**

- [ ] A long active run survives an activation; Dagu's main PID is unchanged
      until the run completes; generation 1 is retained; generation 2 is visible;
      run record and Dagu history are present.
- [ ] The timeout branch writes `reload.blocked`, does not restart Dagu, and
      **leaves the plane usable for manual runs**.
- [ ] A failed `try-restart` is detected and reported (requirement 2).
- [ ] A reload while `dagu.service` is stopped completes promptly (D2).
- [ ] A scheduled run during every marker state has the recorded behaviour.
- [ ] One shared source linked under two project names — one containing a dot —
      fires two scheduled runs in two correct working directories, with two log
      directories, the declared queue and two history entries.
- [ ] A missing project directory refuses instead of reporting `Succeeded`.
- [ ] Rollback restores the prior generation.

**Status checks**

- [ ] `devman --registry … --state … --dagu-home … doctor` enumerates all 45
      projects and validates all 143 files, and exits 0 or exits 1 with only
      known findings.
- [ ] The fleet sweep shows no new refusal.
- [ ] Both link canaries return 0 with five `ok` states.

**Migration checks**

- [ ] No repository has `.devman/project.toml` staged as an empty blob.
- [ ] The ten Stage 37 branches are on `main`, and `origin/main:.devman/project.toml`
      exists in all ten.
- [ ] The seven orphan commits have a recorded disposition.
- [ ] `fleetman` and `flora-037-part-e` have a recorded disposition, and doctor
      finding 1 is gone.
- [ ] A rebuilt generation includes `copyroom`, `docman` and `mypi-agent`.
- [ ] `grep -rn 'devman\.project[[:space:]]*=' --include='*.nix'` over the live
      fleet returns zero before the fallback is removed.

**Documentation**

- [ ] R1, R3, R7, R10 and R11 corrected in the files that hold them.
- [ ] `025/CONCEPT.md` Stage 3 item 4 and Stage 4 amended with the `${DAG_NAME%.*}`
      measurement (R8), and the collision description corrected to `reconcile.py`
      including the delete path (R9).
- [ ] Every new Wave 3 line cites its measurement, in the stage-log shape.

---

## Status

`READY FOR ONE OPERATOR DECISION`

One decision remains (§9): the disposition of the seven orphan commits. The N1
safety repair is complete. Groups A and B have a recommended option with evidence;
Group C's placement and destination questions are already resolved and must not be
re-asked.
