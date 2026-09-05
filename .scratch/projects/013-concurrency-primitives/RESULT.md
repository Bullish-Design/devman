# 013 — concurrency primitives: what the plane should say

**Status: in progress.** Part A is complete and its method is reproducible.
Parts B–E are open. Sections are written as they are earned.

## 0. The machine, for every number below

* 8 cores, 125 GB, Linux 6.18.38. Dagu 2.15.0, store path
  `/nix/store/2mjbj2imilxj56l8l79z689hz40ram6a-dagu-2.15.0`.
* **The machine is not quiet.** The unrelated `find` over sysfs that 012
  recorded is *still running* — `pid 1082086`, 99.4% of one core, now past 20
  hours. A `bzip2` at 90.6% joined it. Load average at the start of this
  project: **4.56 / 3.92 / 3.07**. Load is printed with every timing figure.
* **`devman doctor` exits 0.** 012's constraint — that the daemon predated
  `UnsetEnvironment = "SHELL"` and doctor therefore exited 1 — **is cleared**.
  The machine was rebuilt between 012 and this project. No rebuild was needed
  and none was requested.
* The live plane was read, never written. 54 projects, 170 projected files.

---

## 1. What Dagu 2.15.0 can actually express

### 1.1 Method — and why 012's answer was incomplete

012 read the **config** schema and concluded the queue was the only lever. It
missed that **the binary ships its own schema browser**:

```
dagu schema <dag|config> [path]
```

`dagu schema dag` emits **302 KB of JSON schema, 58 root fields**, none of
which 012 read. Both dumps are kept beside this file:
`measurements/dag_schema.json`, `measurements/config_schema.json`.

**The DAG schema is `additionalProperties: false`.** Any field not in those 58
is rejected, so the enumeration below is closed, not a survey.

**A trap 012 fell into and this project nearly repeated.** Searching the binary
for `maxActiveRuns` finds it three times, and it is **absent** from the DAG
schema. Both are true: the camelCase spellings are Go struct and JSON-tag
names, and the YAML surface is snake_case. Grep the schema, not the binary.

Also corrected: the upstream module path is **`github.com/dagucloud/dagu/v2`**,
not `dagu-org/dagu` as the KICKOFF states.

### 1.2 The mechanisms

Every field in the DAG schema and the config schema that can produce "not
concurrently with itself", each against the KICKOFF's four questions.

| mechanism | defer or drop | scope | survives SIGKILL | composes with a machine bound |
|---|---|---|---|---|
| implicit per-DAG queue (no `queue:`) | **defer** | machine-global, per DAG name | via proc heartbeat + `proc.stale_threshold` (90 s), `zombie_detection_interval` (45 s) | **no — it *is* the queue field** |
| named `queue: <name>` | **defer** | machine-global, shared by every DAG naming it | same | no — same field, one string |
| DAG `max_active_runs` | — | — | — | **`deprecated: true`, `default: 1`**, and its own description says *"This field is ignored for local (DAG-based) queues."* |
| queue config `max_active_runs` | — | — | — | *"Deprecated: use `max_concurrency`"* — a **different field** from the row above; 012 conflated the two |
| queue config `max_concurrency` | **defer** | machine-global per queue name | same | this is the machine bound today |
| `preconditions` (DAG or step) | **drop** | evaluated per run | n/a | n/a — and see the KICKOFF trap |
| `skip_if_successful` | **drop** | scheduled runs only; *"Manual triggers always run"* | n/a | n/a |
| `overlap_policy` | **drop / defer / drop-all-but-latest** | **catchup runs only** — a missed *cron* interval, not a triggered run | n/a | n/a for a reactive plane |
| `max_active_steps` | defer | within **one run** | n/a | bounds nothing across runs |
| `resources.limits` (cpu/memory) | neither | per run, **enforcement not admission** — *"attempts to enforce … and warns while continuing when enforcement is unavailable"* | n/a | **not an admission bound** |
| `worker_selector` + labelled workers | routing | machine-global | worker heartbeat | **yes — see §1.4** |
| `worker.max_active_runs` | **defer** | **per worker process** | worker heartbeat | **yes — see §1.4** |
| `type: build` materialisation reuse | drop | per step | n/a | already rejected for `format` at 006 E1: it cannot declare one path as both input and output |

Three KICKOFF rows resolve as follows.

* **"Identity locks are not expressible in Dagu" — the module comment is
  right and 012 was wrong.** Omitting `queue:` gives a DAG a queue named after
  itself, and that queue **defers**. This is a free, correct identity lock.
* **"`max_active_runs` is deprecated and ignored" — now verified for *both*
  fields**, and they are genuinely two different fields with two different
  deprecation notices. 012's conflation was real but its conclusion holds.
* **"The queue is the plane's only lever"** — **false as stated**, and §1.4 is
  the counter-example.

### 1.3 The default in `nix/nixos-module.nix` masks the identity lock entirely

`baseFile` sets `queue = cfg.defaultQueue`, which lands in the machine's
`base.yaml` as `queue: light`. **Dagu's base config is merged into every DAG.**
So on this machine the S-9 behaviour the module comment describes — "a DAG
naming no queue lands in a queue named after itself" — **never happens**. A
workflow that omits `queue:` does not get an identity lock; it gets `light`.

The comment states the trade correctly and then the code takes the far side of
it for every DAG on the machine, including the 110 that never needed a shared
lane. Nothing records that this is what the default costs.

### 1.4 The crux: a run *can* be constrained by two things at once

The KICKOFF's Part A.4 asks whether S-9's either/or is real. **It is not.**
Dagu has a second admission dimension that is not the queue field:

```
config.default_execution_mode: distributed
config.worker.max_active_runs      # "Maximum concurrent DAG runs for this worker"
config.worker.labels               # key=value capability labels
DAG   worker_selector: {k: v}      # or the literal "local"
```

`dagu worker --worker.max-active-runs=N --worker.labels=class=light` is a
plain CLI, and `dagu license check` reports **"Community mode (no license)"**,
so nothing here is gated behind a licence *at the CLI surface*. Whether
distributed execution actually admits work in community mode is **not yet
verified** and is the first thing the spike must prove.

If it holds, the three ideas the KICKOFF says one string is carrying separate
cleanly, each into its own field:

| idea | field | where it lives | who owns it |
|---|---|---|---|
| mutual exclusion | `queue:` — **defaulting to the DAG's own identity** | workflow file, portable text | group author |
| class of service | `worker_selector:` labels | workflow file, portable text | group author |
| machine capacity | worker pool sizes | machine config | the machine module |

and **S-9's either/or evaporates**, because the exclusion lock and the machine
bound stop being the same field.

**This is a hypothesis with a schema behind it and no measurement behind it.**
It is not adopted until Part D runs it.

### 1.5 Not yet resolved in Part A

* `dispatchAdmissionSlot` (8 occurrences) and `internal/queue/enqueue_retry`
  (1) are symbols in the binary with no schema surface. Neither is reachable
  from a configuration file, so neither is a *declarable* primitive; what they
  do to admission timing is unknown.
* The binary is a prebuilt tarball. **No source was read** — there is no
  `dagu` source in the Nix store to read, and this project has not fetched it.
  Every row in §1.2 comes from the shipped schema and its own descriptions.

---

## 2. The spike: S-9's either/or is disproved

All of §2 ran on a throwaway `DAGU_HOME` at `/tmp/013/home`, ports
**18080 / 50155**. The live plane kept 8080 / 50055 and was never stopped or
reconfigured; its three processes (**1204, 1209, 1271**) are the same ones that
were running when this project started. Load average during §2: **4.5–5.2**,
with the sysfs `find` still holding one core.

### 2.1 Two operational traps, both recorded because both cost a run

* **`--dagu-home` is not propagated to forked children.** The daemon dispatches
  a run by forking `dagu start`, and that child does **not** inherit the flag —
  it resolves its own home and reports `Error: dag-run is not queued`, having
  looked in the *default* home. **Use the `DAGU_HOME` environment variable, not
  the flag**, or a throwaway instance is not isolated at all.
* **The coordinator advertises its hostname by default.** Here that is
  `server`, which resolves to `127.0.0.2`, and every dispatch failed with
  `connection refused` while the coordinator was listening on `127.0.0.1`.
  `coordinator.advertise` must be set explicitly.
* 012's `pkill -f "dagu --dagu-home $H"` pattern **matched this session's own
  shell** and killed it. Kill by recorded PID.

### 2.2 The implicit identity queue is real, and it defers

Two DAGs, `a1` and `a2`, neither naming a queue, no `base.yaml`. Three `a1`
runs and one `a2` run enqueued within 340 ms (`measurements/A.log`):

| run | start | end |
|---|---|---|
| a2 #1 | 538.712 | 544.720 |
| a1 #1 | 538.718 | 544.727 |
| a1 #2 | 547.697 | 553.708 |
| a1 #3 | 556.683 | 562.691 |

* **The three `a1` runs never overlap.** The implicit per-DAG queue holds a
  DAG against itself at concurrency 1. The daemon says so in its own log:
  `msg="Processing batch of items" queue=a1 count=1 max-concurrency=1`.
* **`a2` runs concurrently with `a1`.** Different DAG name, different queue.
* **All four ran. Nothing was dropped.** This is a **defer**, and it is the
  property `preconditions` and `skip_if_successful` do not have.
* The gaps — 544.727 → 547.697 and 553.708 → 556.683 — are **2.970 s and
  2.975 s**. 012's 3.000 s drain ticker, confirmed a third time.

**This settles the KICKOFF's first row. Identity locks are expressible in
Dagu, they are free, and they defer.** 012's claim was wrong and the module
comment was right.

### 2.3 A machine bound that is not the queue field

`default_execution_mode: distributed`, one local worker:

```
dagu worker --worker.coordinators=127.0.0.1:50155 \
            --worker.max-active-runs=2 --worker.labels=class=light --peer.insecure
```

**This runs in community mode.** `dagu license check` reports *"Community mode
(no license)"* and the worker started, matched, and executed. Distributed
execution is **not** licence-gated at 2.15.0.

Four distinct DAGs (`b1`–`b4`), each carrying `worker_selector: {class: light}`
and **no `queue:`**, enqueued within 220 ms:

| runs | start | end |
|---|---|---|
| b2, b1 | 693.165, 693.171 | 701.176, 701.181 |
| b4, b3 | 701.265, 701.270 | 709.275, 709.280 |

Exactly two at a time, all four completed. **The worker bound defers.**
Handoff from a freed slot to the next start was **83 ms**, not a 3 s tick — the
worker polls the coordinator and does not wait for the queue drain.

### 2.4 The proof: both constraints hold one run at the same time

Six runs — **three of `b1`** plus one each of `b2`, `b3`, `b4` — enqueued
together against the same worker (`measurements/B.log`):

| run | start | end |
|---|---|---|
| b1 #1, b3 | 762.473, 762.475 | 770.484, 770.485 |
| b4, b2 | 770.828, 770.843 | 778.834, 778.849 |
| b1 #2 | 778.962 | 786.970 |
| b1 #3 | 789.236 | 797.247 |

* **Peak observed concurrency: 2.** The machine bound held.
* **The three `b1` runs never overlap each other** — and at 770.83 the worker
  had a free slot and gave it to `b4` rather than to a second `b1`. The
  identity lock held *while* the capacity bound was binding.
* **Six enqueued, six completed.** Neither mechanism dropped a run.

**S-9's either/or is disproved.** A per-identity limit and a shared machine
capacity limit can admit the same run, because they are two different fields.
The module comment's "a per-DAG queue bounds a DAG against ITSELF and bounds
the machine against nothing" is true, and its implied conclusion — that the
plane must therefore give up the identity lock — **is not**.

### 2.5 What §2 has not yet shown

* Crash survival. Neither the identity queue nor the worker bound has been
  `SIGKILL`ed and watched to recover.
* Cost. The worker is a **fourth machine process** and its latency and idle
  cost are unmeasured. Part D.3 requires both.
* Nothing here used the real projection, the real registry, or a real
  `devenv tasks run`. These are synthetic 6–8 s sleeps.

---

## 3. The conflict set

### 3.1 What the plane actually runs

54 projects, 170 projected files, 10 distinct workflow names. Every project
takes `base`, and almost nothing else:

| workflow | copies | queue |
|---|---|---|
| `check`, `maintain` | 54 each | `light` |
| `test` | 54 | `normal` |
| `release` | 2 | `heavy` |
| `format` | 1 | `light` |
| `agent-review`, `bench-entry`, `gitman-commit-message`, `plane-report`, `stack-validate` | 1 each | 1 `gpu`, 1 `exclusive`, rest mixed |

Totals by queue: **110 `light`, 55 `normal`, 2 `heavy`, 2 `exclusive`, 1 `gpu`**.

### 3.2 What is written to a fixed path

**Exactly one workflow body writes a fixed path**: `format`, to
`.devman/.runs/.format.hash`. Every other write is keyed by
`${context.run.id}` and cannot collide — `maintain` and `release` both write
`reports/<name>-<run-id>.md`.

**But two shared writes are not in any workflow body, and so appear in no
audit of the workflows:**

* **`.devman/.runs/metadata.jsonl`.** The exit handler in the machine's
  `base.yaml` appends one line **for every run of every workflow** in a
  project. This is a genuine cross-workflow shared path. It is a single
  `printf` of well under `PIPE_BUF` opened `O_APPEND`, so concurrent appends
  do not interleave — **safe, but safe by accident**, and nothing states the
  dependency. `release`'s gate *reads* this file to decide whether to build.
* **`.devenv/`.** Every workflow step in the plane runs `devenv tasks run`, so
  `check`, `test`, `format` and `release` in one project share devenv's state
  directory. **Not measured by this project.** See §7.

### 3.3 The classification

| conflict | example | real? |
|---|---|---|
| **self** | `format` vs `format`, one repo | **yes — §3.4** |
| **sibling** | `format` in repo A vs repo B | **no.** Different `working_dir`, different `.devman/.runs/`. Nothing is shared. The `light` queue binds them anyway. |
| **cross-workflow** | `check` + `test` + `format`, one repo | **unproven.** Shared `.devenv/`; not measured. |
| **resource** | 54 × `test` = 54 × `nix flake check` | **yes** — Part E. |

The sibling row is the interesting one. **110 of the 170 files sit in a shared
`light` lane, and 108 of those have no conflict with each other at all.** They
are bound together only because the plane had one string with which to bound
the machine.

### 3.4 The `format` race: 012's claim is wrong, and the real bug is worse

Fixture in `measurements/fmt-race/`: 120 `.py` files, a formatter that rewrites
each in turn, and the **exact** precondition and hash expression from
`groups/format/workflows/format.yaml`.

**Scenario 1 — two concurrent runs, the race 012 asserted. It is benign.**

```
B RUN  ...525.782      A DONE ...531.418 hash=44bad61f815b
A RUN  ...525.782      B DONE ...531.489 hash=44bad61f815b
final stored 44bad61f815b   actual tree 44bad61f815b   unformatted 0
```

Both ran, both wrote the same hash, the tree is consistent and fully
formatted. **The cost is duplicated work, not corruption.** 012 inferred a
corruption race from observing four concurrent runs and never demonstrated it.
**It does not occur.** That row of the KICKOFF table is now disproved, not
confirmed.

**Scenario 2 — a save that lands *during* a run. This one is real, and it is
silent.**

```
A RUN   ...560.310                    (A begins; formats f000 first)
EDIT    ...561.285  f000.py <- unformatted save
A DONE  ...564.640  hash=370c5ca6575f (hash computed AFTER the edit landed)
B SKIP  ...564.730                    (tree hash == stored hash)
FINAL unformatted: 1   ->   f000.py:x=999
```

`f000.py` is left unformatted. **Both runs report success.** This is precisely
Law 5 — a successful run that did the wrong thing — and it is invisible,
because a skipped step is the same `Succeeded` status a correct loop-break
produces.

**The workflow's own comment claims this cannot happen.** It argues the hash
beats a suppression window because *"edit `foo.py` immediately after the
formatter wrote it and the hash no longer matches, so the work runs."* That is
true for an edit landing **after** the run and **false** for one landing
**during** it. The comment tests the wrong window.

**Mutual exclusion does not fix it.** In the transcript above B ran strictly
after A finished — a perfect identity lock — and still skipped. The defect is
**ordering**, not concurrency: the hash is computed *after* the work, so it
records a tree the formatter never validated.

**The fix is a fixpoint, and it is verified** (`measurements/fmt-race/run2.sh`):
format, hash, format again, hash again; store only when two consecutive passes
agree, so a tree that moved under the formatter is detected and re-formatted.

```
A RUN ...591.617    EDIT ...592.609
A RETRY pass=1 (tree moved under the formatter)
A DONE  pass=2      after A: unformatted=0      B SKIP      FINAL unformatted: 0
```

**This is a bug in `format`, not in the concurrency model, and it should be
fixed on its own merits regardless of what this project decides about queues.**
