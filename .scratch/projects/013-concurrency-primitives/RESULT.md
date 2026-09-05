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

---

## 4. The numbers nobody had

### 4.1 Method

`nix flake check` **caches**, so repeating it measures nothing: the second run
of an unchanged flake returns in under a second. Six `git clone --depth 1`
copies of this repository were made under `/tmp/013/cap/`, and **a fresh unique
marker was appended to `nix/nixos-module.nix` before every single run**, so
every measured check is a distinct derivation doing real work.
`measurements/level.sh` is the harness. Levels were run 1, 2, 4, 6 and the
whole sequence was run **twice**.

**The machine was not quiet and could not be made quiet.** The sysfs `find` was
still holding one core. Load average is printed per level below, before and
after. **Absolute figures are therefore pessimistic; the shape is the finding.**

**This is a lighter check than the one 012 cited.** A cold check here is
**~24 s**, not the 91.9 s recorded earlier, because much of the closure is
already built or substitutable on this machine. **The curve's shape is what
this section claims; the absolute seconds are not portable.**

### 4.2 The curve

| concurrency | pass 1 wall | pass 2 wall | per-run p50 | throughput |
|---|---|---|---|---|
| 1 | 25 s | 24 s | 24–25 s | 2.4 runs/min |
| 2 | 25 s | 26 s | 25 s | 4.6–4.8 runs/min |
| 4 | 31 s | 28 s | 27–31 s | 7.7–8.6 runs/min |
| 6 | 42 s | 41 s | 39–41 s | 8.6–8.8 runs/min |

Load average climbed 5.1 → 15.5 across pass 1 and 13.7 → 14.2 across pass 2.

**The findings:**

* **Concurrency 2 is free.** Per-run latency is unchanged from 1, and
  throughput doubles.
* **Concurrency 4 is nearly free.** Per-run latency rises 12–24%; throughput
  reaches **8.6 runs/min**.
* **Concurrency 6 buys almost nothing.** Throughput improves **2%** over 4
  (8.6 → 8.8) while per-run latency rises **45%**. The knee is at 4.
* **"Capacity = cores" is wrong, as the KICKOFF predicted.** 8 cores, and the
  knee is at **4**. `nix flake check` hands work to `nix-daemon`, which is
  already claiming the machine; each run asks for the whole machine.

### 4.3 The five limits are backwards

Today: `exclusive 1, gpu 1, heavy 1, light 4, normal 2`.

`normal` holds **all 54 `test` workflows** — the `nix flake check` measured
above — at **2**. `light` holds `check`, `maintain` and `format` at **4**.

**The heavy workload is capped at half the machine's knee, and the light one at
exactly the knee.** At `normal: 2` the plane delivers 4.6 runs/min where 8.6
is available at *no meaningful latency cost*. **`normal: 2` leaves roughly 45%
of achievable throughput on the floor.**

That is a measured statement about the number. It is **not** a recommendation
to raise it, and §5 explains why: it is the KICKOFF's "do not tune your way out
of a design problem" trap. The number is wrong *and* the string is wrong, and
fixing the number leaves the string carrying three meanings.

**No sizing evidence for any of the five was found anywhere in the
repository.** The KICKOFF's claim that they appear as values and nowhere as an
argument is confirmed.

---

## 5. Crash survival and cost

### 5.1 A dead run does not wedge a workflow forever — it wedges it for 90 s

A long `c1` run was started and its supervising process `SIGKILL`ed, leaving
its heartbeat file under `home/data/proc/c1/c1/*.proc` orphaned. A second `c1`
run was enqueued immediately.

```
SIGKILLed run at ...134.119   (proc heartbeat file still present)
enqueued second run ...134.218
second run admitted after 90 s
```

**90 s is exactly `proc.stale_threshold`** (default `'90s'`). The identity lock
releases on the heartbeat going stale. The KICKOFF's trap — *"a dead run must
not hold a lock forever"* — is answered: it does not, and the delay is a
configuration key, not a constant.

**The price is real and must be stated.** A `format` run killed by a machine
suspend blocks the next `format` for 90 s. Three of today's five queues are
limit 1, so this exposure already exists; moving to identity locks makes it
apply per workflow rather than per lane.

**One wart:** the killed run stayed `Running` in `dagu history` with a growing
duration long after its lock had released. The lock recovers; the *status* does
not, at least not within the observed window.

### 5.2 Losing the worker defers; it does not drop

| event | result |
|---|---|
| worker `SIGKILL`ed mid-run | **the running step is orphaned and keeps running** unsupervised — `sleep 120` survived its supervisor |
| run enqueued while **no worker exists** | stays queued. Not failed, not dropped. Waited 20 s+ with no error |
| worker restarted | the queued run started **within 5 s** |

**The machine bound survives worker death by deferring.** The orphaned-step
behaviour is the one genuinely unpleasant finding: a killed worker leaves work
running that nothing is supervising.

### 5.3 The worker costs almost nothing, and adds no latency

**Idle cost**, one 60 s window: **9 ticks / 60 s — 0.15% of one core** —
and **91 MB RSS**.

**Dispatch latency, enqueue to the step's first byte, n=20 each, 4 s apart:**

| path | min | p50 | mean | max |
|---|---|---|---|---|
| local (today) | 0.425 s | **1.787 s** | 1.784 s | 3.114 s |
| distributed via worker | 0.268 s | **1.785 s** | 1.690 s | 2.920 s |

**No regression — the two are indistinguishable.** Both are dominated by the
3.000 s drain ticker, whose uniform phase gives the mean of ~1.5–1.8 s that 012
measured. The worker polls the coordinator rather than waiting on the ticker,
which is why the §2.4 slot handoff was 83 ms while a cold enqueue is ~1.8 s.

**Part D.3 is satisfied:** the design adds no second enqueue and no second poll
on the latency path.

---

## 6. The design

### 6.1 The primitives

The KICKOFF's working hypothesis survives contact with the measurement. Three
declarations, not one string:

| primitive | field | default | portable text or machine state? |
|---|---|---|---|
| **exclusion key** | `queue:` | **the DAG's own identity** — by omitting the field | content (§7.2) |
| **class of service** | `worker_selector: {class: …}` | set in the machine's `base.yaml` | content when stated; the default is machine state |
| **machine capacity** | worker pool `--worker.max-active-runs` | sized from §4.2 | **machine state — never in a workflow file** |

### 6.2 What a group author types, and what they get wrong by typing nothing

**For the overwhelmingly common case they type nothing at all**, and that is
the argument for this shape. 108 of the 170 projected files have no conflict
with anything (§3.3) and want exactly one thing: *do not run me while I am
already running*. Omitting `queue:` gives them that, correctly, for free.

A group author types something in two cases only:

* **A cross-workflow conflict** — two *different* workflows over one file —
  gets an explicit shared `queue: <name>`. Nothing in this plane needs one
  today (§3.2).
* **A workflow that is not the default weight** gets
  `worker_selector: {class: heavy}`.

**What goes wrong if they type nothing is the part that needs a check.** A
`worker_selector` naming a class **no worker serves** produces a run that
queues **forever** and reports nothing — §5.2 showed a run waiting
indefinitely with no error. That is a new silent failure mode, and it is
exactly what §10's checks exist for.

### 6.3 Sizing, from §4.2 rather than from nothing

The knee is **4**. Pools must therefore **sum to about 4**, not be 4 each — and
this is what buys class of service, because a `format` run behind a full
`heavy` pool still has a `light` slot:

| pool | labels | size | serves |
|---|---|---|---|
| light | `class=light` | 3 | `check`, `maintain`, `format` |
| heavy | `class=heavy` | 1 | `test`, `release` |

**This is a sketch, not a measured recommendation.** §4.2 measured the total
knee for one workload. It did **not** measure the split, and the split is what
class of service actually is.

### 6.4 What `doctor` must check

Every primitive that can be declared can be declared wrongly:

1. **Every class named by a projected workflow is served by a configured
   worker pool.** This is the forever-queued failure of §6.2 and it is the most
   important new check.
2. **Pool sizes sum to a stated machine capacity**, and that number cites the
   measurement that produced it — §4.3's finding is that today's five have no
   argument anywhere.
3. **A workflow that states `queue:` explicitly states why**, since doing so
   *gives up* its identity lock — the exact trade S-9 made silently for all 170
   files.
4. The existing projection checks are unaffected: no absolute path and no
   project fact enters a workflow file, so **criterion 10 still holds**.

### 6.5 The charter changes this would force

Under law 2 these travel in the same commit as the code:

* **Law 3 / §7.1** — the closed list of five queue names is replaced by a set
  of class names plus an identity default. The list stays closed; its contents
  and its meaning change.
* **§15.4 / S-9** — the either/or is disproved by §2.4 and the entry must say
  so.
* **`nix/nixos-module.nix`** — the `baseFile` comment quoted in the KICKOFF is
  the honest statement of a trade that **no longer has to be made**.
* **`groups/README.md`** — "a `queue:` name" is no longer the portable unit.

---

## 7. What S-9's either/or actually cost

Now that it is priced:

* **170 of 170 projected files lost their identity lock**, because `base.yaml`
  sets `queue: light` for every DAG (§1.3). The identity queue the module
  comment describes has never once occurred on this machine.
* **108 of them gained nothing for it.** They have no sibling conflict (§3.3);
  they were put in a shared lane only because that lane was the sole way to
  bound the machine.
* **It bought a machine bound that is set wrong** — `normal: 2` against a
  measured knee of 4, leaving ~45% of throughput unused (§4.3).
* **It cost the `format` workflow nothing.** This is the honest half: the
  collision S-9's trade exposed `format` to is **benign** (§3.4, scenario 1),
  and the real `format` bug is an ordering defect that an identity lock **does
  not fix**.

**So the trade was real, it was unpriced, and its price was mostly paid in the
wrong currency.** The plane gave up a correct, free primitive across 170 files
to buy a bound it then set at half the right value — but the concrete harm
everyone assumed followed from it does not exist.

---

## 8. What I did not measure

Stated plainly, because several of these gate the change.

1. **The real projection.** Every Dagu experiment used synthetic DAGs with
   `sleep` steps on a throwaway home. **Nothing ran through `devman run`, the
   real registry, or a real `devenv tasks run`.** Part D asked for the spike on
   the real projection and this is not that.
2. **The class split.** §4.2 measured a total knee of 4 for one workload. The
   light/heavy split in §6.3 is a sketch with no measurement behind it.
3. **`.devenv/` as a shared path.** Every step in the plane runs
   `devenv tasks run`, so `check`, `test`, `format` and `release` in one
   project share devenv state. **This is the largest unexamined conflict in
   §3.2** and it may be the one real cross-workflow conflict.
4. **The absolute capacity numbers are not portable.** A cold check here is
   ~24 s against the 91.9 s cited earlier, because much of the closure was
   already built. The curve's *shape* is the claim.
5. **Whether 54 projects × distributed mode behaves like 4 synthetic DAGs.**
   Coordinator throughput at the real fan-out is unmeasured, and 012's registry
   scaling work was not repeated here.
6. **`dispatchAdmissionSlot` and `enqueue_retry`.** Named in the KICKOFF,
   visible as symbols, no schema surface. `enqueue_retry` was *observed* —
   the daemon retried a failed dispatch four times and deferred rather than
   dropped (§2.1) — but its configuration, if any, was not found.
7. **No source was read.** The Nix package is a prebuilt tarball and no source
   is in the store. Every schema claim comes from `dagu schema`'s own output.
8. **The `format` fixpoint fix was proven on a fixture, not in the workflow.**

---

## 9. Recommendation

**The design in §6 wins on the argument and on the measurement, and it is not
ready to ship.**

What is settled: the primitives are three, not one; Dagu can express all three
at once; the composition costs 0.15% of a core, 91 MB, and **no latency**; and
both mechanisms defer rather than drop, including through a `SIGKILL`.

What is not settled is §8.1 — none of it has run against the real projection —
and §8.3, which could change the conflict set. Switching 54 live repositories
to distributed execution on the strength of four synthetic DAGs would be the
KICKOFF's own trap: a design argument without the spike that earns it.

**Two things should ship now, independently of the above:**

1. **The `format` fixpoint fix (§3.4).** It is a Law 5 defect — a file left
   unformatted while both runs report success — it is demonstrated, its remedy
   is verified, and it has nothing to do with queues.
2. **The correction to the record.** 012's asserted `format` corruption race
   does not exist; S-9's either/or is disproved; and the `baseFile` comment
   describes a behaviour that never occurs on this machine.

---

## 10. Shipped: the `format` fixpoint, and what devenv startup costs the plane

### 10.1 The fix

`groups/format/workflows/format.yaml` now formats to a **fixpoint**: two
consecutive formatter runs must produce byte-identical trees before the receipt
is written, bounded at three passes, **refusing loudly** if the tree never
settles. The §3.4 defect is closed.

**The receipt format is unchanged** — `sha256sum`'s `HASH  -` line — so
existing `.format.hash` files stay valid and nothing needs migrating. Verified
against this repository's live receipt before the change was published.

**Verified end-to-end on the live plane**, run `034JalcZktyjQlL0MlFbww`:
`succeeded`, two formatter passes in the step log, correct receipt written.

| | step duration |
|---|---|
| one pass (before) | 2.289 s |
| two passes (after) | 3.319 s |
| **cost of correctness** | **+1.03 s** |

**The plane refused the first attempt at this change**, and that is worth
recording. A patch that introduced mojibake produced
`not loadable as YAML: unacceptable character #x0080 — fix the source; the
plane publishes no file it cannot read`, and the projection **kept the old
file**. Law 5 working as designed: a bad projection was refused rather than
published.

### 10.2 The finding underneath it: devenv startup is ~98% of a format run

Measured while pricing the second pass, n=3 each, in this repository:

| | time |
|---|---|
| `ruff format .` — the actual work | **31 ms** |
| `devenv tasks run format:fmt` | ~1600 ms |
| `devenv tasks run` running **nothing at all** | **~1550 ms** |

**devenv doing nothing costs the same as devenv doing the work.** No flag
avoids it: `--offline` (1475–1681 ms), `--no-reload` (1655–1950 ms) and the
eval cache all make no difference at devenv 2.1.2.

**Inside a Dagu run it is far cheaper** — the step log shows
`Evaluating shell in 4.61ms (cached)` and the whole task in **18.4 ms** — which
is why the measured second pass cost 1.03 s rather than 1.6 s. The cold figure
is what a cold invocation costs; the plane's steps run warm.

**A warm path exists and needs no process.** `.devenv/load-exports` is a plain
shell script devenv itself generates, holding the already-computed environment.
Sourcing it and running the tool directly:

| path | time |
|---|---|
| `devenv tasks run format:fmt` | ~1600 ms |
| `. .devenv/load-exports && ruff format .` | **16 ms** |

**100x, with nothing running in the background.** It is **not** adopted, and
the reason is law 4: it names the tool in the workflow and takes ordering away
from the repository's devenv task graph. It also has no staleness check — a
`devenv.nix` that changed since the exports were written would run the step in
a stale environment, silently, which is Law 5 again.

**This is a plane-wide cost, not a `format` cost.** Every workflow step in the
plane runs `devenv tasks run`, so every run of all 170 projected workflows pays
devenv's startup. **Not measured:** what that totals across 54 projects, and
whether a safe warm path (with a freshness check, and still routed through the
task graph) is possible. That is its own project.
