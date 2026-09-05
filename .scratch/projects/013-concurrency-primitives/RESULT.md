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
