# 012 — the performance of the plane's Dagu calls

Result. Measured on this machine, 2026-09-04 and 2026-09-05, against the live
plane: `dagu 2.15.0`, `devman 0.3.0`, `watchexec 2.5.1`, 54 registered projects,
170 projected workflows.

---

## 0. The three sentences

**The path from a save to a running step is 2.5 s, and 60% of it is a wait for a
timer nobody knew was there.** Dagu's scheduler drains its queue on a **3.000 s
ticker** — fitted over 50 controlled runs with a 10–12 ms median residual, and
corroborated across 494 recorded runs whose p95 is 3.043 s. It has no
configuration key in Dagu 2.15.0. It is not lock contention, and the KICKOFF's
`lock_retry_interval` lead is wrong.

**And most of that wait is not necessary.** The daemon is the parent of every
run, so a freed slot is already an event; the queue is a directory, so a new
item can be one too. **The only timer that has to exist is the one that notices
a run died without saying so** — absence of a heartbeat cannot be delivered as
an event — and that one is allowed to be slow. Dagu does both jobs in one 3 s
loop, and the merge, not the timer, is what costs the plane 1.5 s a save (§2.4).

**The dispatch half was halved, and the refusals did not move.** `devman watch
--dispatch` started two Python interpreters per filesystem event and imported
the package twice; it now enqueues in-process, and 52 ms of every devman process
was `doctor`, which no automatic caller has ever used. Measured end to end:
**432.1 ms → 216.7 ms, 1.99× faster**, with all 373 existing tests passing
unmodified and 17 new ones added.

**The tail is the queue doing its job.** The 18.5 s that project 011 recorded is
queue admission: the six slowest runs in the whole history each sat with their
queue at its concurrency limit for 73–90% of their wait. Nothing is broken
there, and nothing should be changed.

---

## 1. Part A — the whole path, decomposed

### 1.1 The method, and why the timestamps are already in the plane

Two artefacts made this measurable without instrumenting anything:

* **Dagu's own filenames carry milliseconds.** `status.jsonl` reports
  `startedAt` only to the second, which is useless against a figure near one
  second — and it is what every earlier attempt read. But Dagu names a dag-run
  log `dag-run_<date>.<time>.<ms>.<id>.log` and a step's stdout
  `<step>.<date>.<time>.<ms>.<id>.out`. The first is written at enqueue and
  equals `createdAt` to the millisecond; the second is written when the step
  starts. **The difference between those two names is the segment nobody had
  split.**
* **A second watchexec, with the supervisor's own argv.** The plane's watchexec
  cannot be timed from outside, because the first timestamp devman writes is the
  `fired.jsonl` line — after the registry load, `match()`, and a whole `devman
  run`. So `measurements/watchexec_lat.sh` starts another watchexec with the
  argv `watch.watchexec_command()` builds, over a scratch tree, with a command
  that records the time and nothing else.

Everything below is `hyperfine --warmup 3 --runs 30` unless it says otherwise.
Sample counts, machine state and the load average are stated with each figure.

### 1.2 The decomposition

Each segment measured independently. **`write → fired.jsonl` sums to 499 ms
against project 011's directly measured 502 ms**, which is the check that the
decomposition is complete rather than merely plausible.

| # | segment | p50 | owner | how |
|---|---|---:|---|---|
| 1 | `write()` → inotify → 50 ms debounce → dispatcher `exec` | **72.0 ms** | watchexec | n=30, own watchexec, range 60.5–78.0 |
| 2 | dispatcher: interpreter + `devman.cli` imports | ~137 ms | **devman** | `devman --help`, n=30 |
| 3 | dispatcher: registry load + `match()` over 54 projects | **6.9 ms** | devman | dispatch(no match) − `--help` |
| 4 | `devman run` child: a **second** interpreter + imports | ~137 ms | **devman** | `devman --help`, n=30 |
| 5 | `devman run`: workflow read, YAML parse, **every refusal** | **9.6 ms** | devman | `run --print` − `--help` |
| 6 | `dagu enqueue`: binary start + DAG load + queue write | **119.9 ms** | Dagu | n=20, range 90.9–186.3 |
| 7 | `fired.jsonl` append | <1 ms | devman | one line, one `open`/`write` |
| | **write → the enqueue accepted** | **≈499 ms** | | 011 measured 502 ms |
| 8 | **queue write → the step's first byte** | **≈1,650 ms mean** | **Dagu** | **the 3 s ticker, §2** |
| 9 | shell start + `devenv tasks run format:fmt` + the write | ~420 ms | the work | 2,568 − 499 − 1,650 |
| | **write → effect on disk** | **≈2,568 ms** | | 011's figure, now accounted |

**Two corrections to project 011 §4.2 fall out of this.**

1. **`dagu enqueue` costs 119.9 ms, not 57 ms.** 011 used `dagu --help` as the
   floor, which by construction cannot see the DAG load or the queue write.
   Measured directly against the same binary: `dagu --help` 49.7 ms, `dagu
   enqueue devman.format` 119.9 ms.
2. **Dagu was therefore 24% of the dispatch, not 11%** — and after the change in
   §3 it is 120 ms of 289 ms, which is **41%**. The cheap devman work is gone,
   so what remains is mostly Dagu's.

The ~130 ms that 011 could not account for was segment 1 (72 ms, watchexec) plus
the 63 ms that `dagu --help` under-reported. Nothing is unexplained now.

### 1.3 Where devman's own work actually is

**Segments 3 and 5 together are 16.5 ms.** Reading the registry, resolving
ownership with `deepest()`, matching every glob, reading and parsing the
workflow YAML, and running every refusal in `run.resolve()` — all of it, for 54
projects and 170 workflows, costs about a sixtieth of a second.

Everything else devman spent was **process and import overhead**. Measured per
module, `python -c 'import …'` against a 25 ms interpreter floor, n=30:

| module | mean | over floor |
|---|---:|---:|
| floor (`python -c pass`) | 24.8 ms | — |
| `devman.registry` | 53.1 ms | 28.3 |
| `devman.watch` | 66.1 ms | 41.3 |
| `devman.workflow` | 68.1 ms | 43.3 |
| `devman.run` | 78.0 ms | 53.2 |
| `devman.project` | 84.4 ms | 59.6 |
| **`devman.doctor`** | **127.0 ms** | **102.2** |
| `devman.cli` (imports all five) | 133–144 ms | 108–119 |

`doctor` needs `urllib.request` to poll the Dagu server and
`concurrent.futures` to validate 170 files in parallel. Both are right for what
`doctor` does. Both were paid by every other command, twice per save.

---

## 2. Part A's second question — the 2,568 ms, and the 18,476 ms tail

### 2.1 The answer: a 3.000 second ticker in Dagu's scheduler

**Between `dagu enqueue` returning and the step's first byte, the run waits for a
periodic queue drain whose period is 3.000 seconds.** Latency is therefore
`(next tick − now)`, uniform on [0, 3 s]: **mean ≈1.5 s, p50 ≈1.5 s, max 3.0 s.**

The fit, `measurements/tick_fit.py` scanning period and phase over the measured
latencies:

| set | n | method | best period | phase | median residual | within 50 ms |
|---|---:|---|---:|---:|---:|---|
| 1 | 25 | `devman run`, 5.0 s apart | **3.00 s** | +0.262 s | **12.0 ms** | 18/25 |
| 2 | 25 | `devman run`, 4.1 s apart | **3.00 s** | +2.265 s | **10.0 ms** | 22/25 |
| 3 | 20 | HTTP `POST …/enqueue`, 4.3 s apart | — | — | — | p50 1,776 ms, max 3,099 ms |

**The optimum at 3.00 s is sharp, not chosen.** The next best period in the scan
fits 39× worse — 465 ms median residual against 12 ms. Gaps of 4.1 s and 5.0 s
sweep the enqueue phase through the period independently, and both land on the
same answer.

The runs that do not fit are the confirmation, not the noise:

* **One run per set missed a tick by exactly one period** (+2,995 ms and
  +2,993 ms). Both were enqueued about 80 ms before a tick — written, but not
  yet visible to the drain — so each waited a whole further period. A model that
  could not produce that would be the wrong model.
* **Five runs in set 1 fit the same 3 s grid shifted by exactly 1.000 s.** The
  shift happened once, mid-run. The ticker's phase is not fixed to the wall
  clock and moves in whole seconds. **Stated as measured, not explained** (§7).

**Corroboration over history, with no experiment at all** — the same two
filename timestamps over every enqueued run the plane has recorded:

```
n = 494, enqueue -> the step's stdout file created
  p0    0.120 s        p75   1.974 s
  p10   0.392 s        p90   2.823 s
  p25   0.730 s        p95   3.043 s   <-- the p95 IS the period
  p50   1.278 s        p99  13.477 s
  mean  1.624 s        max  42.992 s
```

The 250 ms histogram is flat from 0.25 s to 2.25 s and stops at 3.0 s, which is
what a uniform wait on a fixed period looks like. The p0 of 0.120 s is the other
half of the answer: **once a run is picked up, starting it costs about 120 ms.**

### 2.2 It is not lock contention, and it is not configurable

The KICKOFF's concrete lead was `scheduler.lock_retry_interval` at 5 s, and an
18.5 s tail "suspiciously close to a small number of 5 s retries". **Both halves
are wrong.**

* The tail latencies are 4.5, 5.7, 7.0, 8.9, 12.9, 13.4, 15.2, 16.3 and 42.4 s.
  They are not multiples of 5 s and show no lock-retry structure.
* `data/queue/.dagu_record_locks/` holds 235 empty two-hex-character **shard**
  directories, not stale locks. `data/scheduler/locks/.dagu_lock/owner` is
  refreshed continuously by the live server, so the scheduler lock is held,
  never contended.

**Dagu 2.15.0 has no queue drain interval to set.** Extracted from the config
JSON schema embedded in the pinned binary, the whole of `SchedulerDef` is:

```
port, lock_stale_threshold (30s), lock_retry_interval (5s),
zombie_detection_interval (45s), failure_threshold (3),
heartbeat_interval (5s, deprecated), heartbeat_sync_interval (ignored),
stale_threshold (90s, deprecated)
```

None is the drain period. `QueueConfigDef` has `enabled` and the queue list, and
nothing else. **The 3 s period is compiled in.** Adding any of the eight above to
`config.yaml` would be a line that looks like a fix and is not.

### 2.3 The tail IS queue admission — whether it is *right* is unmeasured

Nine recorded runs exceeded 4 s. For each, the fraction of its wait during which
its own queue stood at `max_concurrency`:

| wait | DAG | queue | limit | peak in queue | window full |
|---:|---|---|---:|---:|---:|
| 42.40 s | talkee-test | normal | 2 | 2 | **90.1%** |
| 16.35 s | vendomat-test | normal | 2 | 2 | **73.4%** |
| 15.22 s | loci.nvim-test | normal | 2 | 2 | **85.4%** |
| 13.42 s | shellij-test | normal | 2 | 2 | **82.0%** |
| 12.90 s | structured-agents-v2-test | normal | 2 | 2 | **85.2%** |
| 8.86 s | devman-bench-entry | exclusive | 1 | 1 | **77.9%** |
| 6.97 s | siteman-maintain | light | 4 | 3 | 0% |
| 5.74 s | siteman-maintain | light | 4 | 3 | 0% |
| 4.48 s | devman.format | light | 4 | 2 | 0% |

**Every wait above 8 s is a run queuing behind its own queue's limit.** That is
the mechanism the plane exists to have. The three between 4 and 7 s had a free
slot; all three ran with three or four other runs executing in other queues, so
the machine rather than the queue was the constraint.

**011's 18,476 ms is not a defect.** It is one save's `format` run waiting for a
slot in the `light` queue while a flood held all four.

**That is a claim about the mechanism, not about the numbers, and the two were
conflated in an earlier draft of this section.** What is measured is that the
tail *is* admission. What is **not** measured is whether `normal: 2` is the
right limit for this machine. `nix/nixos-module.nix:127` generates Dagu's queue
list from `cfg.queues`, a Nix option whose defaults are `exclusive 1, gpu 1,
heavy 1, light 4, normal 2` — and a grep of `CONCEPT.md` and `groups/README.md`
finds those five integers used as values and never argued for. No core count, no
memory figure, no sustained-load measurement. **This machine has 8 cores and
125 GB, and neither number was known when the limits were chosen.** So `talkee-
test` waited 42.4 s because a hand-picked integer said so, and nobody has
checked the integer. See §6 item 4.

### 2.4 What the timer is for — and what it is not

**Most of the 3 s is not structural, and an earlier draft of this document
defended it too readily. The retraction is the point of this section.**

The claim that was wrong: *"a slot freeing is not an event the enqueuer can
signal, so a periodic pass is needed anyway."* The enqueuer cannot signal it —
but the enqueuer is not who needs to know. **Dagu forks a child process per run
and the daemon is its parent**, verified directly: enqueue `devman.format` and
`pid 3015302, ppid 1204, comm dagu` appears for the life of the run. A parent
sees its own child exit. **Slot-freeing is edge-triggered and needs no timer.**

Nor does new work. The queue is a directory; `inotify` on `data/queue/` — or a
socket, or the HTTP server that is already in the same process — would wake the
drain in under a millisecond. **There is no principled reason for 3 s. It is how
the loop is written.**

**One timer is structural, and it is a different timer.** Dagu keeps per-queue
heartbeat files under `data/proc/{exclusive,gpu,heavy,light,normal}/`, read by
`proc.heartbeat_interval` (5 s), `proc.stale_threshold` (90 s) and
`scheduler.zombie_detection_interval` (45 s). They exist because **the absence
of a signal is not a signal.** A run killed with `SIGKILL`, or a machine that
reboots mid-run, sends nothing. The only way to learn it is to look and find a
heartbeat that stopped.

Note what that implies about *rate*: a liveness timer only matters when
something has already failed, so 45 s is fine. **A drain timer is on the hot
path of every save.** Dagu runs both jobs in one 3 s loop, and that merge — not
the existence of a timer — is what costs the plane 1.5 s per save.

#### The obvious alternative, and why it is not simpler

*Start the work immediately as it arrives; keep a set of running ids; if your id
is in the set, do not run.* Two things go wrong, and both are already recorded
elsewhere in this repository.

**A set membership test drops; a queue defers.** Save `a.py`, a run starts; save
again 200 ms later, your id is in the set, the second trigger is discarded — and
**the second edit is never formatted**, because the drop left nothing behind to
retry. That is precisely the failure
`groups/format/workflows/format.yaml` was designed against: its own comment says
a suppression window "would have swallowed that edit, and would still have
passed a naive 'one save, one run' test". Dedup-by-id *is* a suppression window,
keyed on identity rather than time. Repair it — "if busy, run once more when the
current one finishes" — and you have re-derived a queue of depth 1. **The queue
is not there for throughput. It is there so the last edit is covered.**

**And nothing removes a killed run's id.** The set keeps a stale entry and that
workflow never runs again, silently, which is the shape law 4 exists to refuse.
Detecting it means a heartbeat and a staleness threshold — the timer above,
arrived at from the other direction.

**The wider version of the same idea already has a verdict.** "Fire the work off
in subprocesses as it arrives, with no central queue" is structurally the 010
reconciler spike, and 011 closed it — **not on latency**, where it won handily
at 255 ms edit-to-artifact against the plane's 2,568 ms, but on what it could
not do: no run identity, no status, no log path, nothing durable across a
`SIGKILL`, and no lock across processes
(`011-plane-vs-watcher/DECISION.md`, and §4.3 of its RESULT).

#### What actually needs a timer

| | timer? | why |
|---|---|---|
| noticing a newly enqueued item | **no** | `inotify` on the queue directory, or a socket |
| noticing a slot has freed | **no** | the daemon is the run's parent and sees the exit |
| deferring work rather than dropping it | **no** | durable storage, not a clock — but it must exist (above) |
| noticing a run died without saying so | **yes** | absence of a heartbeat cannot be delivered as an event |

**Only the last row is forced, and only it is allowed to be slow.** This changes
what is worth asking upstream — see §6 item 3.

### 2.5 The 2,568 ms, added up

| term | ms | share |
|---|---:|---:|
| watchexec: inotify + 50 ms debounce + exec | 72 | 3% |
| devman: two Python starts, one of them redundant | 274 | 11% |
| devman: registry, `match()`, workflow parse, every refusal | 17 | <1% |
| `dagu enqueue`: process, DAG load, queue write | 120 | 5% |
| **Dagu: the wait for the 3 s drain tick** | **≈1,500** | **58%** |
| Dagu: picking the run up and starting the shell | ≈120 | 5% |
| the work — `devenv tasks run format:fmt` and the write | ≈420 | 16% |

**Nearly 60% of a save's latency is a timer, and it belongs to neither devman
nor the workload.**

---

## 3. Part B — the four candidates

| # | candidate | measured saving | risk | shipped |
|---|---|---:|---|---|
| 1 | in-process dispatch | **−137 ms** of the dispatch | one property given up, named below | **yes** |
| 2 | defer the `doctor` import | **−52 ms** per devman process | one property given up, tested | **yes** |
| 3 | enqueue over HTTP instead of a process | **0 ms** | bypasses every refusal | **no** |
| 4 | turn the coordinator off | **1 tick / 60 s**, no memory | a config line that changes nothing | **no** |

Together, 1 and 2 give the whole dispatch, measured end to end with hyperfine
against the same registry, the same DAG and a real `dagu enqueue`:

```
BEFORE  dispatch a matching batch -> enqueued   432.1 ms ± 80.0   [346.3 … 672.4]
AFTER   dispatch a matching batch -> enqueued   216.7 ms ± 22.5   [186.3 … 253.7]
                                                1.99x faster, n=20 each, load 4.3
```

**The spread collapsed with the mean** — σ 80.0 → 22.5 ms, max 672 → 254 ms.
A second process start is also a second chance to be descheduled.

Adding watchexec's 72 ms, **a write reaches an accepted enqueue in ≈289 ms,
against ≈504 ms before.** 011's gate A4 requires a dispatch of ≤400 ms p50 and
recorded the plane at 502 ms. **The plane now passes A4's dispatch clause.** It
still fails the effect clause (≤2,000 ms) at ≈2,350 ms, and §2 says why.

### 3.1 Candidate 1 — in-process dispatch (shipped)

`watch.dispatch()` ran `subprocess.run([self_binary(), …, "run", …])` per
matched `(project, workflow)` pair. It now calls `run.trigger()`, which is
`run.main()`'s own body lifted into a function that both callers use.

**Every refusal is on this side of the call and none moved.** `run.resolve()`
raises all of them; `run.assert_target()` runs before `command()` and before the
`--print` branch, exactly as it did. `tests/unit/test_run.py` is the
specification and **it was not modified** — all 373 existing tests pass.

Two properties the child process gave for free, and what happened to each:

* **A refusal did not end the batch.** Kept. `RegistryError` is caught per
  entry, printed with the same `registry.report()` the CLI uses, and recorded
  as `refused (1)` — the exit code `cli.main` gives a refusal.
  `test_a_refusal_is_recorded_and_the_rest_of_the_batch_still_fires` asserts it.
* **A crash was isolated.** **Given up, deliberately.** An unexpected exception
  now ends the batch instead of one entry of it. Catching every exception here
  would turn a defect in this package into a `fired.jsonl` line nobody reads,
  which is what §12 rule 4 refuses.
  `test_an_unexpected_exception_ends_the_batch_rather_than_being_swallowed`
  makes that a decision rather than a gap.

`dispatch()` had **no test of its own** before this change. It now has five,
including `test_dispatch_starts_no_devman_process`, which fails if a later edit
puts the child back — a regression that is otherwise invisible to the suite.

### 3.2 Candidate 2 — the `doctor` import (shipped)

`cli.py` imported all five handler modules at the top of the file. `doctor` is
127 ms of a 133 ms `devman.cli` import, because it needs `urllib.request` and
`concurrent.futures` — right for `doctor`, and paid by every other command.

```
BEFORE  devman --help          181.2 ms ± 64.7          BEFORE  run --print  139.7 ms
AFTER   devman --help           99.4 ms ± 11.3          AFTER   run --print  110.2 ms
BEFORE  dispatch (no match)    176.0 ms ± 24.8
AFTER   dispatch (no match)    129.6 ms ± 30.8
```

**Deferring the other four saves nothing measurable** — 82.2 ms against 81.0 —
because `project` and `run` already pull the registry, the workflow reader and
`yaml`, which `parser()` needs anyway. So exactly one import moved.

**What it costs, and what pays it back.** `devman --help` no longer proves that
`doctor.py` imports, so a broken import there would reach a person only when
they run `devman doctor`. `tests/unit/test_cli.py` replaces that proof with
four stated ones, covering all five subcommands rather than the four that
happened to be on one line.

### 3.3 Candidate 3 — do not start a Dagu process (rejected, measured)

Dagu 2.15.0 serves `POST /api/v1/dags/<name>/enqueue`. It works. It buys
nothing:

| | p50 | note |
|---|---:|---|
| `dagu enqueue` — the whole process | **119.9 ms** | n=20; `dagu --help` floor is 49.7 ms |
| `POST …/enqueue` — round trip only, no process | **138.7 ms** | n=20, from an already-running interpreter |
| HTTP-enqueued run → step's first byte | **1,776 ms** | n=20, max 3,099 ms — **the same 3 s tick** |

**The cost is the enqueue work, not the process start.** The DAG load and the
queue write are ~70 ms whichever way you ask, and an HTTP round trip from a warm
process is no cheaper than a cold Go binary. **It also does not skip the tick**,
which is the only term worth attacking.

And it is worse than neutral. The API named a DAG and enqueued it with no
project resolution, no parameter derivation, and **none of `run.py`'s refusals**
— a `POST` with an empty body enqueued a real run. `auth.mode: none`, bound to
127.0.0.1. Adopting it would make the plane's own path depend on the surface
that bypasses the plane's safety boundary. `run.py`'s docstring says it must
never grow a `--now`; the distinction survives contact, and this is on the wrong
side of it anyway.

### 3.4 Candidate 4 — turn off what is not used (rejected, measured)

`coordinator.enabled` defaults true and 011 recorded the coordinator as
configured and unused. Two 60 s idle windows on a throwaway `DAGU_HOME` with 170
DAGs, on ports 18080/50155 — **the live plane was never stopped or
reconfigured**:

| `coordinator.enabled` | CPU / 60 s idle | RSS |
|---|---:|---:|
| `true` (today's default) | 31 ticks | 103.3 MB |
| `false` | 30 ticks | 110.0 MB |

**One tick in sixty seconds, and more resident memory with it off than on.** The
25 ticks and 103 MB that 011 attributed to "the orchestrator" are `dagu
start-all` itself — the scheduler, the web server and the DAG index. The
coordinator is not where the plane's idle cost is, and a config line that
changes nothing is a line to maintain and a claim to disprove later.

---

## 4. Part C — what gets slower as the plane grows

### 4.1 Registered projects: linear, and not the problem

Synthetic registries under `/tmp`, built by `measurements/scale_registry.py`
with the shape the projection writes; every project takes `format`, so
`watch_map()` returns an entry for each and `match()` walks all of them. The
batch names a `.txt` file, so the full match runs and nothing is enqueued.

| projects | BEFORE | AFTER | AFTER, minus the ~99 ms process start |
|---:|---:|---:|---:|
| 54 (today) | 144.5 ms | **108.4 ms** | ≈9 ms |
| 200 | 157.5 ms | **122.5 ms** | ≈24 ms |
| 1,000 | 250.9 ms | **264.1 ms** | ≈165 ms |

**About 0.15 ms per registered project, linear.** At 1,000 projects — 18× this
machine — the dispatch is ≈264 ms, still less than a tenth of one drain tick.
The registry is not what will make this plane slow.

(At 1,000 the two builds converge, because this batch matches nothing and so
never started the child process the AFTER build removes. The 54-project column
is where candidate 2's saving shows.)

### 4.2 Queue depth: the mean drifts, the tail does not

Throwaway `DAGU_HOME`, no scheduler running, so the queue only grows.

| depth | on disk | `dagu enqueue` |
|---:|---:|---|
| 1 | 12 KB | 83.0 ms ± 7.7 |
| 100 | 412 KB | 91.3 ms ± 10.1 |
| 1,000 | 4.0 MB | **137.5 ms ± 87.8, max 401.1** |

The mean grows gently. **The variance does not** — σ rises 11× and the worst
case is 4.8× the median. Each enqueue rewrites `<queue>/.queue-index.json`, and
that file grows with depth. A queue 1,000 deep is already a queue nobody is
waiting on, so this ranks low; it is recorded because it is the one term here
that is worse than linear in its tail.

### 4.3 History size: no effect at all

Same throwaway home, queue emptied first so depth cannot confound it. The live
plane's `data/dag-runs` copied in and multiplied.

| history | files | on disk | `dagu enqueue` |
|---:|---:|---:|---|
| none | 0 | 0 | 112.0 ms ± 8.4 |
| 1× the live plane | 2,588 | 19 MB | 114.3 ms ± 11.7 |
| **≈15× the live plane** | **38,210** | **261 MB** | **109.9 ms ± 10.1** |

**17,870 recorded runs and a quarter of a gigabyte measure the same as an empty
history.** Enqueue writes the queue; it does not walk `dag-runs`.

**But retention is not running.** `hist_retention_days: 7`, and **505 of 1,171
recorded runs — 43% — are older than seven days**, back to 2026-08-22.
`devman doctor`'s "run output" check reports OK because it looks at a
repository's `.devman/.runs/`, not at Dagu's `data/dag-runs`. At 12.0 KiB per
run and the current rate of 80–180 runs a day, **a year is ≈35,000 runs, ≈420 MB
and ≈77,000 files.** On this evidence that costs enqueue nothing; it costs disk,
and it costs whatever walks it — which is the UI, not the plane. Not measured
here (§7).

### 4.4 `dag_discovery` over many DAGs: nothing, and here is why

| DAGs in `dags_dir` | `dagu enqueue` |
|---:|---|
| 170 (today) | 112.0 ms ± 8.4 |
| 1,000 | **104.1 ms ± 11.8** |

**No cost, because Dagu does not walk the directory to find a DAG.** It keeps a
binary index beside it — `dags/.dag.index`, 24 KB on the live plane, holding
each DAG's name, its schedule and its resolved path. `recursive: true` and
`symlinks: true` are paid when the index is built, not per enqueue.

---

## 5. Part D — the floor, and whether any of this was worth doing

### 5.1 The bound

Terms that cannot be removed without removing a component:

| term | ms | why it is irreducible |
|---|---:|---|
| inotify delivery + `fork`/`exec` of the dispatcher | ≈22 | the kernel's, and a process must start |
| watchexec's 50 ms debounce | 50 | one save is several `write()`s; removing it multiplies runs |
| a Python interpreter plus the imports devman genuinely needs | ≈70 | `python -c pass` is 25 ms; `devman.workflow` is 68 ms |
| devman's own work — registry, `match()`, parse, every refusal | 17 | measured, and it is the safety boundary |
| `dagu enqueue` — DAG load and queue write | ≈120 | HTTP measured no cheaper (§3.3) |
| **the plane's dispatch floor** | **≈279** | |
| what the plane does today, after this project | **≈289** | |
| what it did before | ≈504 | |

**The dispatch is within about 10 ms of its own floor.** There is nothing
meaningful left in it. Halving it again means removing a whole process — a
compiled `devman`, or an enqueue that is not `dagu`'s — and §3.3 measured the
second of those at zero.

The other half is not the plane's:

| | ms |
|---|---:|
| the plane's dispatch floor | 279 |
| **Dagu's 3 s drain tick, mean** | **1,500** |
| Dagu picking the run up and starting a shell | 120 |
| **edit-to-effect floor, excluding the work** | **≈1,900** |

### 5.2 Is dispatch latency worth optimising at all?

**Mostly no, and the two changes that shipped are the exception rather than the
argument against it.**

The honest form of the answer the KICKOFF asked for: **the 1.5 s matters and the
500 ms did not.** A developer saving a `.py` file waits about 2.4 s for the
formatter, and 60% of that is a timer inside Dagu with no configuration key.
Removing the entire devman dispatch — every process, every refusal, the whole
CLI — would take 2,568 ms to about 2,290 ms. Nobody would notice.

**What made candidates 1 and 2 worth shipping is that they cost nothing.** One
was an import no automatic caller has ever used. The other was a process whose
only content was 10 ms of work the parent could do itself. Neither traded a
property for speed; both removed something that was never doing anything.
`PROPOSAL.md` §12 rule 1 — the plane must not compete with what the editor does
synchronously — is untouched by either, and remains the reason not to spend more
here.

**And the reactive workload is one repository.** 54 projects are registered;
exactly one takes `format`. The whole of this machine's save-to-effect latency
is one developer, in one repository, waiting for `ruff`.

---

## 6. What to do next, ranked — and what not to do

### Worth doing

1. **Rebuild the machine and restart the two services.** Not a change; a state.
   The running plane is behind this repository by at least a project:
   `/run/current-system/sw/bin/devman` has no `project` subcommand, and the
   watcher (pid 1209) runs a **third** devman build from a different store path
   under Python 3.13 while the profile has 3.14. `devman doctor` exits 1 today
   for the same reason — `!! daemon shell  pid 1204: SHELL=…/zsh` — and
   `nix/nixos-module.nix:539` **already sets** `UnsetEnvironment = "SHELL"`. The
   finding is a daemon that predates its own fix. **Nothing here ships until
   that rebuild happens**, including this project's two changes.
2. **Say the 3 s tick out loud, where somebody looking at latency will find it.**
   It is the single largest term in the plane and nothing in the repository
   mentions it. A `devman doctor` line, or a paragraph in
   `groups/format/README.md` beside the loop-break argument. **The cost of not
   writing it down is that the next investigation re-measures it** — this one
   spent its first hours re-deriving what 011 had already half-seen.
3. **Ask upstream to wake the drain on enqueue — not for a tunable.** §2.4 is
   why the ask changed. A `scheduler.queue_poll_interval` would help
   (≈2.4 s → ≈1.2 s at 500 ms), but it asks upstream to make a wrong shape
   adjustable. **The right ask is to separate the two timers**: edge-trigger the
   drain on a queue write and on a child's exit, and keep the periodic pass for
   heartbeats and zombies, where it belongs and where 45 s is already fine.
   That takes this machine's save-to-effect to **≈0.9 s** — better than the
   tunable, and a smaller argument to make, because nothing in Dagu's own design
   wants the delay either. `dagu-org/dagu` is GPL-3.0 and takes issues. **Read
   `internal/service/scheduler/` at the v2.15.0 tag first** (§7): this project
   read only the pinned binary's embedded schema, so whether the loop is
   structured to allow it is unverified.
4. **Size the queues from the machine.** `nix/nixos-module.nix:127` builds
   Dagu's queue list from `cfg.queues`, whose defaults — `exclusive 1, gpu 1,
   heavy 1, light 4, normal 2` — appear nowhere in the design documents as an
   argument, only as values. **They are therefore identical on an 8-core laptop
   and a 64-core workstation**, which is a defect on every machine except
   whichever one they were guessed on. The module already knows the machine, so
   this is a Nix change needing no upstream.

   **Take the measurement before changing a number.** The obvious rule —
   "capacity = cores" — is wrong here, because the runs are not single-threaded:
   `nix flake check` hands its work to `nix-daemon`, which already claims the
   machine. Admitting `nproc` of those into an `nproc`-sized pool asks for
   `nproc²`. What is unknown is what this box sustains for 1, 2, 4 concurrent
   `base:test` — 91.9 s alone is the only figure anyone has. With 125 GB the
   binding constraint is cores, and raising `normal` could easily make things
   worse.

   **Keep the five names.** They are not capacity, they are class of service:
   `format` on `light` does not queue behind `test` on `normal`, which is what
   keeps a save responsive under load and what §12 rule 1 is about. A single
   pool sized to the machine would lose that. **The name is the class and the
   number is the capacity; only the number should be derived.**

### Worth doing if the plane grows

5. **A retention check that looks at Dagu's data, not the repository's.**
   `doctor`'s "run output" check reports OK while 43% of `data/dag-runs` is past
   `hist_retention_days`. That is a check passing without checking the thing its
   name claims — the shape law 4 refuses. Either it prunes, or it says it
   cannot.
6. **Revisit queue-depth variance above ~1,000 items.** §4.2. Only matters for a
   plane that queues faster than it drains, which this one does not.

### Not worth doing

* **Enqueueing over HTTP.** Measured at zero saving, same tick, and it bypasses
  every refusal (§3.3).
* **Disabling the coordinator.** One tick in sixty seconds (§3.4).
* **Anything else in the dispatch.** It is 10 ms above its floor (§5.1).
* **Setting any `scheduler.*` duration in `config.yaml`.** None of them is the
  drain period, and a line that looks like a fix is worse than no line (§2.2).
  The heartbeat and zombie intervals *are* real, and they are the one timer that
  has to exist (§2.4) — shortening them buys nothing and costs wakeups.
* **Reopening 011.** Dagu's 3 s tick is a reason to ask upstream for a knob, not
  a reason to re-litigate the orchestrator. The queue is what produces the tail,
  and the tail is the queue working.

---

## 7. What was not measured, plainly

* **Why the ticker's phase shifts by whole seconds.** Observed once, in set 1,
  mid-run (§2.1). The 3 s period survives the shift; its cause does not have an
  answer here. Reading Dagu's source would give one; this project read only the
  pinned binary's embedded schema.
* **The three tail runs between 4 and 7 s** that had a free queue slot (§2.3).
  All three coincided with other runs executing, so the machine was busy — but
  "busy" was not decomposed into CPU, disk or scheduler contention.
* **Segment 9 — shell start, `devenv tasks run`, `ruff`, the write** — is
  ≈420 ms by subtraction, never measured directly. It is the workload's, not the
  plane's, and §12 rule 1 says the plane should not be trying to shorten it.
* **What a year of history does to the UI and to `doctor`.** §4.3 measured
  enqueue against 261 MB and found nothing. Neither the web UI's dashboard
  queries nor `doctor`'s own walk was timed at that size.
* **`dagu start-all`'s startup cost** against 1,000 DAGs — only the steady idle
  state was measured, and only at 170.
* **Anything under memory or disk pressure.** Every figure here was taken with
  free memory and free disk.
* **The two changes in §3 under the real watcher.** They are measured as
  processes, with the real registry, the real DAG and a real `dagu enqueue`, and
  the segment sum reproduces 011's independently measured 502 ms to within 3 ms.
  But the systemd watcher still runs the old build (item 1 above), so
  `write → fired.jsonl` has not been re-timed end to end through the service.
* **Whether Dagu's drain loop could be edge-triggered at all.** §2.4 argues it
  should be, from the outside: the queue is a directory, the daemon is the run's
  parent, and the HTTP enqueue happens in the drain's own process. **Whether the
  code is shaped to allow it was not checked** — this project read the pinned
  binary's embedded config schema and never the source.
* **What this machine sustains for concurrent `nix flake check`.** §6 item 4.
  `base:test` was measured once, alone, at 91.9 s. Two, four and six concurrent
  are unmeasured, so no queue limit here is defended by a number.
* **Concurrency between dispatches.** watchexec's `--on-busy-update=queue`
  serialises them, so the in-process change cannot introduce overlap — but that
  was reasoned from the flag, not tested with a burst.

---

## 8. Method, and the machine

* **Every timing figure is `hyperfine --warmup 3 --runs 30`** unless stated;
  `--runs 20` where a run enqueues real work. Latency distributions are n=25,
  n=25 and n=20 for the controlled sets and n=494 for the historical one.
* **`hyperfine` and `watchexec` were added to `devenv.nix`** rather than typed
  into a `nix shell`, so a number here is reproducible by whoever enters this
  shell next. The `watchexec` it provides is the same store path the live
  service runs.
* **The machine was not quiet, and could not be made quiet.** An unrelated
  `find -L /sys/bus/pci/… -name *busy*` has held one core at 98.9% for 4.6 hours
  and predates this session. Load average ran 3.8–5.9 throughout. Both builds in
  every comparison were measured in the same hyperfine invocation under the same
  load; absolute figures are therefore pessimistic and the comparisons are fair.
  Where load differed between two tables it is printed with them.
* **Nothing under `~/.local/share/dagu` or `~/.local/share/devman` was written
  by hand.** Both were read. Every Dagu experiment that needed to change
  configuration ran on a throwaway `DAGU_HOME` under `/tmp` on ports
  18080/50155. The live plane's three processes (1204, 1209, 1271) are the same
  ones that were running when this project started.
* **What did touch the live plane:** **182 `devman.format` runs**, every one of
  them in the `devman` repository, which is what 011 did and what the KICKOFF
  permits. **All 182 are recorded `succeeded`**; most skipped their step on the
  content-hash precondition, which is what that precondition is for. No other
  DAG was enqueued and no other repository was touched.
* **`base:check`, `base:unit` (390 tests) and `base:test` (`nix flake check`)
  all pass.** `devman doctor` exits 1, byte-identically before and after these
  changes, for the pre-existing daemon-shell finding in item 1 of §6.

### The scripts

| file | what it does |
|---|---|
| `measurements/micro.sh` | the dispatch half, one process at a time; enqueues nothing |
| `measurements/watchexec_lat.sh` | a write to the dispatcher's first instruction, through a real watchexec |
| `measurements/enqueue_lat.py` | enqueue to the step's first byte, `devman run` or HTTP |
| `measurements/tick_fit.py` | fits period and phase to those latencies, and prints what does not fit |
| `measurements/scale_registry.py` | builds a synthetic registry of N projects |
| `measurements/scale_queue.sh` | enqueue cost against queue depth |
| `measurements/scale_history.sh` | enqueue cost against history size |
| `measurements/coordinator_cost.sh` | two idle windows, coordinator on and off |
| `measurements/*.json` | the raw per-run latencies behind §2.1 |
