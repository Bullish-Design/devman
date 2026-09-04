# 011 — RESULT: the system-level plane against a per-repository watcher

Written 2026-09-04, from source read in this session and measurements taken on
this machine on this date. Every number states its method beside it.

**Machine state during every measurement in this document:** 8 logical cores,
load average 3.86 at the start of the scaling run, 4 interactive users, the
live plane running throughout (`dagu start-all` pid 1204, `devman watch` pid
1209, one `watchexec` pid 1271). Nothing under `~/.local/share/dagu` or
`~/.local/share/devman` was stopped, reconfigured or edited. `devman-spike` was not modified: no tracked file changed
(`git status` clean). Its daemon was started once for 90 s to measure a real
process's RSS, which appended one `startup` line to the untracked
`.devman/watch.log`. Raw data and the scripts that took it are in
`measurements/`.

---

## 0. The two corrections that come before any argument

Two premises the kickoff carried are wrong, and both change the shape of the
comparison. They are stated first because the rest of this document depends
on them.

### 0.1 The plane runs ONE watchexec for all projects, not one per project

The kickoff models the plane as `39 fixed + (2 ticks x N watched projects)`,
and concludes it "never amortizes the watching". That model does not match the
code. `watchexec_command()` at `src/devman/watch.py:290` builds a single argv
and appends one `--watch` per distinct path:

```python
for path in sorted({str(e.path) for e in entries}):
    argv += ["--watch", path]
```

`supervise()` has exactly one `subprocess.Popen` (`src/devman/watch.py:435`, inside `supervise()` at `:403`).
The module docstring's phrase "One watchexec for every watched repository"
means *covering* every repository, not *one per*. So the plane is **three
processes at every N**, and the per-repo watcher is **N processes**.

The corrected arithmetic:

- **plane** = 3 processes, fixed. One Rust watcher holding N trees.
- **per-repo watcher** = N processes. N Python interpreters, N registries.

That reverses the kickoff's prediction. The plane's fixed cost is real, but it
is *fixed*, and it is the per-repo design whose cost is linear in N. Section 2
measures where the two curves cross.

### 0.2 The reactive surface today is N = 1, not N = 54

The registry holds 54 projects and 171 projected DAGs, confirmed by reading
`~/.local/share/devman/projects/*/metadata.json`. **Exactly one of them
declares a trigger map:**

```
projects: 54   with trigger map: 1
('devman', '/home/andrew/Documents/Projects/devman',
 {'group': 'format', 'ignore': ['.scratch/**'],
  'map': {'**/*.py': 'format'}, 'source': 'group+local'})
```

Method: read every `metadata.json` in the registry, count entries whose
`triggers.map` is non-empty. All 54 carry a `triggers` key; 53 carry it empty.

**So the entire reactive workload on this machine is one repository, one glob,
one workflow.** Every "at N = 54" argument in either direction is a forecast,
not an observation — including this document's. The 54 number belongs to
*projection and distribution*, which is a different capability from *watching*,
and section 4 is where it actually bites.

---

## 1. Part A — capability inventory, read from source

### 1.1 What the plane has

| Capability | Where | Used today? | Cost for the spike to gain it |
|---|---|---|---|
| Trigger glob -> workflow mapping | `groups/format/triggers.toml` — the only one in the repository — resolved in `modules/devenv.nix:169-215`, stored in the registry entry | yes, 1 project | the spike has `rules.toml` inputs globs; equivalent, but per-repo and not distributable |
| Repository-local trigger veto | `.devman/triggers.toml` `ignore`, `project.py:459-529`, applied in `watch.match()` | yes (`.scratch/**`) | small; a second glob list in `rules.toml` |
| Workflow resolution and group inheritance | `modules/devenv.nix:84-164`, precedence + shadowing | yes, 4 groups, 171 DAGs | **large — this is section 4** |
| Projection into Dagu (render + link + validate) | `src/devman/project.py` (686 lines) | yes | large; the spike has no projection concept |
| Run history, per-run logs, artifacts | Dagu `data/dag-runs` (17 MB), `.devman/.runs/logs/`, `metadata.jsonl` (208 runs recorded) | yes | **not present at all** — see 1.3 |
| Durable queue | Dagu `data/queue` on disk | yes, 5 queues | not present |
| Concurrency limits | `config.yaml` queues: exclusive/gpu/heavy 1, normal 2, light 4 | yes | not present |
| Fan-out bound checking | `workflow.unbounded_fanout()`, doctor check 13 | yes, 1 workflow | not applicable — the spike refuses chains |
| Scheduling | Dagu `schedule:` | yes, 2 workflows (`maintain`, `plane-report`) | not present |
| Retries and backoff | Dagu `retry_policy`, `repeat_policy` | **no shipped workflow uses either** | not present |
| Preconditions / skip logic | Dagu `preconditions:` | yes — `format`'s content hash | the spike's manifest input-hash is the same idea, cheaper |
| Secrets | Dagu `secrets`, `dotenv`; charter §9.4 | **never fired** | not present |
| Health check across the whole plane | `src/devman/doctor.py`, 18 checks, 1,133 lines | yes, exits 0 | not present; the spike has `gen` exit codes only |
| CLI surface | `devman run/watch/doctor/show/project` | yes | `dspike gen/watch/status` — 3 commands |
| Nix module layer / how a repo joins | `modules/devenv.nix` (793 lines) + `nix/nixos-module.nix` (623) | yes, 54 repos | **none — see section 4** |
| Web UI | Dagu server on `127.0.0.1:8080` | yes | not present |
| Multi-machine | explicitly refused — one plane per machine; Dagu's `coordinator` is configured but unused | no | n/a |

### 1.2 What the spike has

| Capability | Where | Used today? | Cost for the plane to gain it |
|---|---|---|---|
| Declarative rule loading with refusals | `rules.py:55-104` — unknown key, missing template dir, duplicate output all refused at load | yes, 8 rules | moderate; devman deliberately never parses a workflow (§7.2) |
| Content-addressed staleness (manifest) | `reconcile.py:259-267` — input hash + output hash | yes | the plane pushes this into each workflow's `preconditions:` — already done for `format` |
| Purity audit hook | `reconcile.py:126-172` — `sys.addaudithook` catches a collector reading a file no glob covers, and names it | yes (gate P2) | **the plane cannot do this**: it never runs the work in-process |
| Lazy Templateer registry + fingerprint gate | `registry.py` — skips a 148 ms import when nothing is stale, without losing the refusal | yes | n/a |
| Unix socket + compiled C client | `server.py`, `client/dspike-gen.c` — 5.9 ms round trip | yes | the plane's equivalent is `devman run` -> `dagu enqueue`, measured at 502 ms p50 dispatch |
| Obsolete-output report and `--prune` | `reconcile.py:186-225` — reports every run, removes only on request, refuses a file edited since | yes | the plane has `doctor --prune` for registry entries, not for artifacts |
| Output ownership (one output, one rule) | `rules.py:96-103` | yes | the plane has the DAG-name codec for the analogous collision |
| Two-clause watcher selection | `watcher.py:347-366` — input glob OR the output it owns, which is what repairs a hand edit | yes | the plane's analogue is the content-hash precondition |
| Single-process reconcile lock | `watcher.py:93`, `server.py:73` | yes | the plane has Dagu's queue, which is stronger |

### 1.3 What each cannot do at all

This list is shorter than either feature list, and more decisive.

**The plane cannot:**

1. **Run work in-process.** Every unit of work is a `devenv tasks run`
   subprocess under Dagu. The measured floor is 502 ms of dispatch before
   anything starts (§15.2). There is no path to the spike's 2.4 ms warm no-op.
2. **Audit what the work read.** `sys.addaudithook` needs the work in the
   same interpreter. The plane's charter (§7.2, "devman never parses a
   workflow to understand it") forecloses this by design, not by omission.
3. **Refuse a workflow's *content*.** `doctor` checks the projection, the
   names, the queues, the handlers and the fan-out. It cannot check that a
   step does what it says. §12 rule 4 exists precisely because the plane
   cannot tell a successful run that did nothing from one that worked.
4. **Work without machine state.** A repository outside the registry has no
   workflows, no DAG names and no triggers. Reactivity requires the daemon,
   the registry and the projection to all be present and agreeing.
5. **Amortize a language runtime.** Each run pays process start.

**The spike cannot:**

1. **Survive its own process.** No durable queue. A `SIGKILL` between an
   event and a render loses that event; the next reconcile recovers by
   re-deriving from hashes (gate A7 passed) — but only for work that is a
   pure function of the tree. Work with a side effect outside the tree is
   simply lost, unrecorded.
2. **Answer "what ran, when, and why".** `.devman/watch.log` is 22 lines of
   `{at, trigger, written, duration_ms}`. There is no run identity, no exit
   status per step, no log capture, no artifact, no retention policy, and no
   history to query. The plane has 208 recorded runs with run ids, statuses
   and log paths, and a UI.
3. **Bound concurrency.** No queue, no limit, no fairness. Limitation 1 in
   `PIPELINE_RESULT.md` §7 — the cross-process manifest race — is
   unreproduced and unfixed, and there is no mechanism that would fix it.
4. **Chain, schedule, or fan out.** Refused by design.
5. **Reload its own rules.** `.devman/rules.toml` sits under an ignored
   directory, so a rule change never wakes the watcher (limitation 2). A rule
   change requires a manual daemon restart.
6. **Reach a second repository.** No registry, no identity, no cross-project
   anything. Every capability is per-checkout.
7. **Be distributed.** Section 4.

---

## 2. The scaling curve — the measurement nobody had taken

**Method.** 25 synthetic repository trees in `/tmp/dm011/repos`, 316
directories and 15 `.py` files each (the live `devman` repository has 674
directories excluding `.git`, so these are about half a real repository).

- **Plane side:** ONE `watchexec` 2.5.1 — the exact binary the live service
  runs, from the same nix store path — with the live flag set copied verbatim
  from pid 1271 (`--emit-events-to=json-stdio --postpone
  --on-busy-update=queue --project-origin=<registry>` plus all seven
  `DEFAULT_IGNORES`), and one `--watch` per tree. Command `/bin/true`.
- **Spike side:** N `watchfiles` 1.2.0 daemons under Python 3.13.14 — the
  spike's own venv interpreter — each running `watchfiles.watch` with
  `dspike.watcher.watch`'s exact parameters (`SpikeFilter`, `step=100`,
  `debounce=1600`, `rust_timeout=1000`, `yield_on_timeout=True`).
- 15 s settle, then a 60 s window. CPU is `utime+stime` from `/proc/<pid>/stat`
  summed over every process. Inotify watches are lines beginning `inotify` in
  `/proc/<pid>/fdinfo/*`. One sample per point — see §8.
- The live plane was running throughout and is **not** included in these
  columns. Its fixed 41 ticks / 142 MB come from `PIPELINE_RESULT.md` §15 and
  were re-confirmed by `ps` at the start of this session.

| N | plane: procs | ticks/60 s | RSS | fds | inotify | spike: procs | ticks/60 s | RSS | fds | inotify |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | **0** | 9.1 MB | 12 | 316 | 1 | **2** | 18.8 MB | 6 | 316 |
| 5 | 1 | **0** | 9.5 MB | 12 | 1,580 | 5 | **8** | 93.8 MB | 30 | 1,580 |
| 10 | 1 | **0** | 9.9 MB | 12 | 3,160 | 10 | **17** | 188.1 MB | 60 | 3,160 |
| 25 | 1 | **0** | 11.6 MB | 12 | 7,900 | 25 | **41** | 469.9 MB | 150 | 7,900 |

### 2.1 What the curve says

**Inotify consumption is identical at every N** — 316 per tree, exactly the
directory count, for both designs. Both use notify-rs underneath. The
kickoff's guess was right: *the file-watching layer was never the expense, and
it is not the differentiator either.* Neither design threatens the 524,288
limit: 54 real repositories at ~2,272 watches each (measured on live pid 1271
against `devman`) is about 123,000, under a quarter.

**One inotify finding worth recording:** live pid 1271 holds **2,272** watches
on a repository with 872 directories, because watchexec follows symlinks —
`find -L . -type d` gives 2,814. `--ignore` filters *events*, not watch
*registration*, so `.devenv` (835 MB) is watched and then ignored. The
per-repository cost is the symlink-followed tree, not the filtered one.

**The plane's watching layer is flat.** One process, 0 measurable ticks over
60 s idle at every N, and RSS grows 9.1 -> 11.6 MB across a 25x increase in
watched trees — 100 KB per repository. **This is amortization, and the kickoff
predicted there was none.**

**The per-repo watcher is strictly linear.** 1.64 ticks and 18.8 MB per
repository, on a *bare* watcher that does nothing. A real `dspike` daemon,
measured on the spike's own repository in this session, is **41.5 MB RSS, 3
threads, 1,919 inotify watches** — it carries an interpreter, a rule set and a
Templateer registry that the bare watcher does not.

### 2.2 The crossover, stated plainly

The plane's fixed cost is 41 ticks/60 s and 142 MB (§15.3, re-confirmed). The
per-repo design pays nothing fixed and everything per repository.

| | crossover N |
|---|---|
| **CPU** | **~25** — 25 bare watchers cost 41 ticks, exactly the plane's entire fixed cost. Below 25 the per-repo design is cheaper; above it, the plane is. |
| **Memory, bare watcher** (18.8 MB) | **~7.5** |
| **Memory, real `dspike` daemon** (41.5 MB) | **~3.4** |

**So at the 54 repositories the registry actually holds, the plane wins both
axes decisively** — 41 ticks against ~89, and 142 MB against ~2.2 GB of
Python reconcilers. At the **N = 1** the plane actually watches today, the
per-repo design wins both — 2 ticks against 41, and 41.5 MB against 142 MB.

**The comparison is therefore entirely decided by a number nobody has chosen:
how many repositories are meant to be reactive.** That is a policy question,
not a measurement, and §12 is what answers it — see section 5.

---

## 3. Part B — the distribution answer

**The spike has no distribution story, and this is the strongest single
argument for the plane.**

Read from source: `devman-spike/pyproject.toml` declares
`templateer = { path = "../templateer_v2" }`. There is no `flake.nix`. The
package resolves a dependency by relative filesystem position. It works on
this machine because a sibling directory happens to exist.

### 3.1 How a repository joins the plane today

Three keys in `devenv.nix`, one input in `devenv.yaml`:

```nix
devman = { enable = true; project = "pyjutsu"; groups = [ "base" ]; };
```

```yaml
inputs:
  devman: { url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>" }
imports: [ devman/modules ]
```

From that, at evaluation time: workflow resolution across groups with
precedence and shadowing (`modules/devenv.nix:84-164`), trigger resolution
(`:169-215`), a content-hashed `enterShell` registration, and projection into
Dagu. **Changing `groups/base/workflows/test.yaml` changes every taker at
once, on their next shell entry.** 54 repositories, 171 DAGs, one edit.

### 3.2 How a per-repo watcher would reach 54 repositories

Answer the question concretely, as the kickoff demands. A per-repo reconciler
needs, in every repository:

1. `dspike` itself, at a pinned version — a package, not a path dependency.
2. Its `templateer` dependency, likewise pinned.
3. A `templates/` library.
4. A `.devman/rules.toml`.
5. A way to start the daemon and keep it started.
6. A way to upgrade all six of the above across 54 repositories at once.

Items 1, 2 and 6 are a packaging and pinning problem. **The answer is a Nix
flake** — there is no other mechanism on this machine that pins a version
across 54 repositories and upgrades them together. So:

| devman piece | re-created by the flake answer? |
|---|---|
| `nix/devman-cli.nix` — package the tool | **yes**, identically |
| `modules/devenv.nix` options + `enterShell` | **yes** — a repo must state its version and get the tool on PATH |
| `groups/` — shared content, precedence, shadowing | **yes** — item 3 and 4 are exactly group content; 54 repositories will not each hand-write a template library |
| `groups/*/triggers.toml` — glob to work | **partly** — `rules.toml` inputs are the same idea, but per-repo and not inherited |
| Registry + projection | **no** — a per-repo watcher genuinely does not need these |
| Dagu, queues, history, UI | **no** |

**So the honest count is: a distributed per-repo watcher re-creates the Nix
module layer and the group mechanism — 793 + 623 lines of Nix plus
`groups/` — and drops the registry, the projection and Dagu.** It does not
re-create "most of devman"; it re-creates devman's *distribution and policy*
half and discards its *orchestration* half.

Item 5 is the one the plane already answered and the spike has not.
`src/devman/watch.py:1-12` records the measurement: a per-repository watcher's
only plausible home is a `processes.` entry in that repository's devenv, and
devenv processes start under `devenv up` and nothing else — not `devenv
shell`, not direnv entry, not `devenv test`. **Reactivity would then apply to
whichever repositories somebody happened to have open.** That is finding D7 in
the charter and it is a lifetime problem, not a capability problem. The
per-repo design has no answer to it that is not "a machine-level supervisor
that starts N daemons" — which is a control plane with a registry.

### 3.3 What happens on a breaking change

Plane: bump `rev` in each repository's `devenv.yaml`; the schema field in the
registry entry (`project.py:66`, `SCHEMA = 4`) plus `doctor`'s
`check_schema` names every repository still on an old schema. The migration
is observable and the plane says which repositories have not taken it — the
live `doctor` run does exactly this today for the DAG-name codec ("6 still
project under the pre-codec name, in 2 repositories: gitman, pyjutsu").

Spike: nothing observes it. There is no registry, so nothing knows which 54
repositories exist, which version each runs, or which have migrated. The
manifest has a `version` field (`manifest.py:470`) and an unknown version is
discarded and rebuilt — correct locally, silent globally.

---

## 4. Part C — operational properties under failure

### 4.1 The flood — the plane's answer to spike gate A14

**Method, and its honest limit.** Gate A14 floods the spike with 20,000 files
and requires convergence within 120 s. Running 20,000 files against the *live*
plane would have created 20,000 tracked-source-shaped files in a repository
somebody uses, so this was **scaled down 10x to 2,000 files** and run inside
the real `devman` repository — the one repository the plane actually watches —
in `zz_flood/`, outside `.scratch/**` which that repository's own
`triggers.toml` ignores. Files were removed afterwards; `git status` is clean
and `devman doctor` still exits 0.

Result, 2026-09-04 19:54:30:

```
created 2000 files
elapsed to quiet:   17 s   (37 s measured, minus the 20 s quiet window)
dispatches fired:   4
runs recorded:      4      all "status":"succeeded"
```

**2,000 filesystem events produced 4 runs, not 2,000, and every one
succeeded.** That is `watch.match()`'s coalescing — one `(project, workflow)`
pair per batch (`src/devman/watch.py:546`) — plus watchexec's debounce and
`--on-busy-update=queue`, plus the `light` queue's limit of 4. The design
holds under burst, and it converges 7x inside gate A14's bound at a tenth of
the load.

One honest detail: **deleting the 2,000 files fired a fifth dispatch** at
19:55:07. A deletion is a change, so the formatter ran again. The
content-hash precondition is what stops that being a loop, not the detector.

### 4.2 The rest of Part C, side by side

| Question | The plane | The spike |
|---|---|---|
| **The work failed — where does a person look?** | Dagu UI at `127.0.0.1:8080`; `dagu status`/`history`; per-run log under `.devman/.runs/logs/<dag>/<run>/`; one line per run in `metadata.jsonl` (208 lines) carrying run id, attempt, status and log path | `.devman/watch.log` — 22 lines of `{at, trigger, written, duration_ms}`. **No status, no log path, no run identity.** A rule error reaches `report.errors` and the `gen` exit code; through the daemon it is not written to the log at all |
| **Survives `SIGKILL`?** | The enqueue is durable — Dagu persists to `data/queue` on disk, so an accepted run survives the daemon's death and a reboot | Nothing is durable. Gate A7 passes because the work is a pure function of the tree: the next reconcile re-derives it from hashes. Anything with a side effect outside the tree is lost silently |
| **Survives a full disk?** | Not measured, either side. See §8 | Not measured |
| **Two runs of the same work overlap** | Dagu's queue serialises. Measured (`STAGE_2_LOG.md` S11): two DAGs naming `exclusive` ran 6 ms apart under `start` and serialised strictly under `enqueue`. `run.py` therefore has no `--now` | One in-process lock covers the watcher and the socket (`watcher.py:93`). **Across processes there is no lock.** `PIPELINE_RESULT.md` §7 item 1 — a full `gen` committing inside the watcher's window reverts the manifest entries it touched. Unreproduced, unfixed, and there is no mechanism that would fix it |
| **A repository is moved, renamed or deleted** | Identity is `devman.project`, never the directory name (`modules/devenv.nix:425`, criterion 11 / C5), so a rename keeps run history. `watch_map()` skips a registered path that is gone — because watchexec exits on a missing `--watch` path and `Restart=on-failure` would then leave the unit **failed**, killing reactivity for every repository (`STAGE_5_LOG.md` S2). `unwatchable()` names it out loud, `doctor` check 5 reports it, `doctor --prune` reconciles it | Nothing to break: the root is the working directory. Also nothing to notice — no history exists to keep or lose |
| **Can it say it is healthy, and can that claim be false?** | `devman doctor` — 18 checks, 1,133 lines, exits 0 today. **Yes, it can be false**, in a bounded way it states itself: it validates the projection, the DAG names, the queues, the handlers and the fan-out. It cannot check that a step does what it claims. §12 rule 4 exists because of exactly this gap, and `full-test`'s "exit 0, 15.2 s, nothing tested, in 30 of 58 repositories" is the worked example | No health command. `dspike status` prints the manifest. The manifest's honesty is real and stronger *per artifact* — an input hash plus an output hash means "up to date" is checkable — but it is silent about the daemon, the rules and everything outside the tree |
| **Rules change while running** | The supervisor re-derives the watch set from the registry every 5 s and replaces its watchexec child when the path set changes (`watch.py:400-460`, S16); glob changes need no restart because the dispatcher calls `watch_map()` per batch | **`.devman/rules.toml` is under an ignored directory, so a rule change never wakes the watcher.** Manual restart required (limitation 2) |

**The pattern.** The plane's failures are *visible and named*; that is what
1,133 lines of `doctor` and the refusal messages in `run.py` buy. The spike's
failures are *fewer* — it has less to go wrong — but the ones it has are
silent, because it has no place to report them to.

---

## 5. Part D — how much of Dagu's surface devman's own laws close

`PROPOSAL.md` §12 has **nine** rules, not the eight the kickoff cites; rule 9
(expensive fan-out by a parent) was added at stage 7 from measurement S-8.

Method: `dagu schema dag` on the pinned 2.15.0 gives 58 top-level DAG keys, 44
step keys and 57 builtin actions. Each was read against §12. **Classifying a
key as "closed" is a judgement, not a mechanical fact** — §12 forbids kinds of
*work*, not YAML keys — so the table below states the rule that narrows each
group, and a determined author could still find a legal use for most of them.

### 5.1 Top-level DAG keys — 58

| Bucket | Count | Detail |
|---|---:|---|
| **Used** by a shipped workflow or `base.yaml` | **10** | `steps params queue type schedule working_dir log_dir preconditions handler_on hist_retention_days` |
| Closed or sharply narrowed by §12 | **27** | remote/distributed 10 (`worker_selector ssh kubernetes container registry_auths resources otel artifacts s3 redis`) — rules 2 and 5, and devman is one plane per machine; external side effects 5 (`mail_on error_mail info_mail smtp webhook`) — rule 2; LLM/agent 5 (`llm harness harnesses tasks tools`) — rule 3; secrets 2 (`secrets dotenv`) — §9.4, never fired; scheduling extras 5 (`catchup_window overlap_policy skip_if_successful restart_wait_sec delay_sec`) — rule 8 |
| Deprecated on the pin | **3** | `max_active_runs step_types tags` |
| Permitted and unused | **18** | `actions consts defaults description env group hist_retention_runs labels log_output max_active_steps max_clean_up_time_sec max_output_size name retry_policy run_config shell shell_args timeout_sec` |

### 5.2 Builtin actions — 57

| Bucket | Count |
|---|---:|
| Used by a shipped workflow | **1** (`dag.run`) |
| Narrowed by rule 2 — irreversible or off this machine | 16 |
| Narrowed by rule 3 — writes tracked source unattended | 13 |
| Narrowed by rules 8/9 — scheduling and fan-out | 8 |
| Narrowed by rule 6 — a second implementation of what the repo has (`state.*`, `sqlite.*`, `file.read/list/stat`, `jq.filter`, `data.*`) | 18 |
| Permitted, unused | 1 (`human.task`) |

### 5.3 The count, and what it means

**devman uses 10 of 58 DAG keys (17%), 6 of 44 step keys, and 1 of 57 actions
(1.8%).** Of the 48 keys it does not use, 27 are narrowed by its own laws and
18 are simply unused.

**The kickoff's hypothesis is confirmed, and it is a finding.** Scheduling,
unattended writes to tracked source, expensive periodic work and cross-machine
execution are Dagu's headline strengths and §12's explicit refusals. The
comparison narrows to what is left: **queues, run history, a durable enqueue,
a UI, and bounded cross-project fan-out.** Those five are real and the spike
has none of them — but they are a much smaller surface than "Dagu versus a
Python daemon" suggests.

**The sharpest form of it:** the plane ships three live groups —
`base`, `format`, `release` — holding five workflows, plus two deliberate
tombstones (`python`, `python-format`, both README-only). Two of them (`check`, `test`) are one line each — `devenv tasks run
-v base:check`. §12 rule 1 forbids firing `check` from a save. §12 rule 6
forbids the workflow doing anything the repository's own task does not already
do. So for two of the five shipped workflows, Dagu contributes a queue, a
history record and a UI row — and nothing else.

---

## 6. Both gate sets, run against both systems

The kickoff's methodological warning is the right one: **a comparison that
only runs one side's gates is not a comparison.** So both sets are here, and
each is marked where it is unfair to the system it is applied to.

### 6.1 The spike's gates, against both

| Gate | Bound | The spike | The plane | Fair? |
|---|---|---|---|---|
| A4 edit -> effect | p50 <= 400 ms, max <= 2 s | **PASS** 255 / 276 ms | **FAIL** 2,568 / 18,476 ms; dispatch alone 502 ms p50 | **Half fair.** The dispatch column is fair — it is pure overhead before any work. The effect column is not: the plane's effect includes `devenv tasks run format:fmt`, real work, against the spike's Markdown render |
| A10 idle cost | <= 20 ticks / 60 s | **PASS** 2 | **FAIL** 41 | **Fair at N=1, unfair at scale.** Section 2 shows the plane's 41 is fixed and the spike's 2 is per-repository. At N=25 the spike measures 41 too |
| A8 cold/warm ratio | >= 20 | **PASS** 365 | **n/a** — the plane has no warm path to amortize; every run is a process | **Unfair by construction.** This gate asks "did the daemon pay for itself", a question the plane's design never poses |
| A9 size | <= 1,200 lines | **PASS** 1,028 core | **FAIL** 3,923 Python + 2,126 Nix | **Unfair.** A9 compares a spike core against a system that also carries a registry, a projection, a Nix module layer and 1,133 lines of health checking. Line count is only a gate when the two do the same job |
| A14 flood | converges <= 120 s | **PASS** 20,000 files | **PASS** 2,000 files in 17 s, 4 runs, all succeeded (§4.1) | Fair, but the plane was tested at a tenth of the load |

### 6.2 The gates Dagu would have set, against both

Written before reading either result, from what an orchestrator is for.

| Gate | The plane | The spike | Fair? |
|---|---|---|---|
| **D1 Run history.** Answer "what ran, when, with what status, and where is its log" for the last 100 runs | **PASS** — 208 runs in `metadata.jsonl`, 17 MB of Dagu history, a UI | **FAIL** — 22 lines with no status, no log, no run id | **Unfair by design.** The spike refuses history; a reconciler's answer is "the tree is correct", which is checkable without history |
| **D2 Durable accept.** An accepted unit of work survives `SIGKILL` and a reboot | **PASS** — `data/queue` on disk | **FAIL** — nothing durable; recovery is re-derivation, which only works for pure work | Fair, and it is a real gap |
| **D3 Bounded cross-project fan-out.** One trigger reaches N repositories with a stated bound | **PASS** — 1 workflow does this; `doctor` check 13 refuses an unstated bound | **FAIL** — cannot reach a second repository at all | **Unfair.** The spike refuses chains and cross-repo work by design |
| **D4 Concurrency and fairness.** A burst does not take the machine down | **PASS** — 5 queues, limits 1/1/1/2/4; §4.1's flood produced 4 runs from 2,000 events | **FAIL** — no queue, no limit, and an unfixed cross-process manifest race | Fair. This is the gap that matters most |
| **D5 One place to look at 3am** | **PASS** — UI, `dagu status`, `devman doctor`'s 18 checks | **FAIL** — a 22-line log and the daemon's stderr | **Unfair in kind, fair in fact.** The spike is per-repository, so "one place" is a category it does not have |
| **D6 Distribution.** One edit changes behaviour for 54 repositories, and the system names who has not taken it | **PASS** — groups + `SCHEMA`; the live `doctor` names `gitman` and `pyjutsu` as unmigrated | **FAIL** — no mechanism exists | **Fair, and decisive.** See section 3 |
| **D7 Scheduling** | **PASS** — 2 scheduled workflows | **FAIL** | **Unfair.** §12 rule 8 makes this nearly unusable for the plane too |

**Reading both tables together:** each system passes its own gates and fails
the other's, which is what the kickoff predicted and is not by itself
informative. The informative rows are the ones marked **fair**: A14 (both
pass), A10 at scale (both 41 at N=25), D2, D4 and D6 (the plane passes, the
spike fails and has no path). **The plane's fair wins are durability,
concurrency and distribution. The spike's fair win is latency before work
starts — 502 ms of dispatch it does not pay.**

---

## 7. Part E — what each shape forecloses, and whether a hybrid is real

### 7.1 The finding the kickoff anticipated

**The two systems are not alternatives. One is a distribution and policy
layer; the other is an execution strategy.** Every measurement in this
document points the same way:

- Section 2: the plane's *watching* layer is one flat Rust process. The spike's
  watcher is the same library, the same inotify cost, the same job. **Neither
  design's watcher is the argument.**
- Section 5: devman uses 10 of 58 DAG keys and 1 of 57 actions, and its own
  laws close 27 more keys. **Dagu's capability surface is mostly out of
  bounds by charter.**
- Section 3: what actually carries the 54 repositories is `modules/devenv.nix`
  and `groups/` — Nix, not Dagu. A per-repo watcher that wanted to reach 54
  repositories would re-create exactly that half.

So the real question is the one the kickoff put last: **which parts of the
plane survive if Dagu does not?**

### 7.2 The three parts, priced

| Layer | Lines | Survives without Dagu? |
|---|---:|---|
| Nix module + groups + projection input | 793 + 623 + `groups/` | **Yes, entirely.** Nothing in group resolution, shadowing, identity or `enterShell` registration needs an orchestrator |
| Registry (`registry.py` 622, part of `project.py`) | ~900 | **Yes.** Identity -> path, ownership by `deepest()`, faults, schema. Only `dags_dir`, `dag_name()` and the link checks are Dagu-shaped |
| Watcher (`watch.py` 574) | 574 | **Yes.** It is a supervisor around watchexec that maps a path to a project and a workflow. Only the last two lines of `dispatch()` are Dagu |
| Projection into Dagu (`project.py` render/link/validate) | ~400 | **No.** This exists to produce DAG files |
| `run.py` | 359 | **Mostly no.** Its refusals are about DAG names, queues, `dag.run` parents and `log_dir` |
| `doctor.py` | 1,133 | **About half.** Of 18 checks, 7 are Dagu-shaped (plane, queues, validate, queue names, dag names, handlers, daemon shell); 11 are registry-, projection- or watcher-shaped |

**Roughly 2,000 of 3,923 Python lines and all 2,126 Nix lines are independent
of Dagu.** That is the honest measure of "how much of devman is Dagu".

### 7.3 Is a hybrid real, or the worst of both?

`SYSTEM_LEVEL_OPTIONS.md` §3.1 proposes "the daemon for state, a client for
triggering". Costed against what is now measured:

**Hybrid A — keep the registry and group distribution, drop Dagu.**
`devman run` would exec the work directly instead of enqueueing. Gains: the
502 ms dispatch floor, the 39 fixed ticks and 132 MB of the two upper
processes. Loses: D2 (durable accept), D4 (queues — and §4.1 shows the queue
turning 2,000 events into 4 bounded runs), D1 (208 runs of history), the UI,
and the 2 scheduled workflows. **Real, and the cost is exactly the five
capabilities in section 5.3.** This is the serious option.

**Hybrid B — Dagu for scheduled and cross-project work, saves go direct.**
Two trigger paths, two failure modes, two places to look, and `doctor` grows a
check for the boundary. It buys latency on the *one* workload — a save firing
one idempotent step — that §12 has already bounded to a single glob, a content
hash and its own group. **This is the worst of both**, and the reason is
§12 rule 6: a second implementation of a path the repository already has, which
drifts silently because both keep passing.

**Hybrid C — the spike's socket, inside the plane.** `dspike`'s Unix socket
answers in 5.9 ms because a live process already holds the interpreter, the
imports and the registry. The plane has a live process holding a registry:
`devman watch`, pid 1209. A socket on it would not remove Dagu, but it would
remove the 502 ms dispatch for the work that does not need a queue. **Not
costed here; the smallest experiment with the largest measured headroom.**

### 7.4 Directions each forecloses

**Choosing the plane forecloses:** a repository that works standalone with no
machine state; a reconciler used as a library rather than a service; the
in-process purity audit (§1.3); and the generative path in
`PIPELINE_RESULT.md` §14, where a model writes an input and a person accepts
it — because that path needs the work in-process, and the plane's charter
(§7.2) forbids the plane from understanding the work at all.

**Choosing the per-repo watcher forecloses:** anything machine-wide. Not just
cross-project workflows — also *the ability to answer a question about the
machine*. `devman doctor` naming `gitman` and `pyjutsu` as unmigrated is a
capability that requires a registry, and no per-repo design produces it.

---

## 8. The recommendation

**Keep the plane, and treat the spike as an execution strategy to be adopted
*inside* it rather than an alternative to it.** The decisive evidence is not
latency: it is that the plane's costs are fixed and the per-repo design's are
linear (section 2 — memory crosses over at N between 3 and 8, CPU at N ~ 25),
that the per-repo design has no distribution mechanism and would re-create
devman's Nix and group layers to get one (section 3), and that the three fair
gates the spike fails — durable accept, concurrency bound, distribution — have
no path to being fixed within its shape. What the spike proves is narrower and
still true: **for a save that fires one deterministic idempotent step, the
orchestrator is 502 ms of pure overhead and the file watcher underneath it is
free.** That workload is real, it is bounded by §12 to one glob and a content
hash, and it is currently the *only* reactive workload on this machine (N = 1).
The right next move is therefore Hybrid C — a socket on the already-live
`devman watch` process, for work that needs no queue — and not a rewrite in
either direction.

**The three measurements that would reverse this:**

1. **Reactive N stays at 1 for another quarter.** Every plane advantage in
   section 2 is an advantage at scale, and the machine has none. If nothing
   but `devman` is ever watched, the plane is 41 ticks and 142 MB to serve one
   repository that a 41.5 MB daemon serves in 2 ticks. *Measure: count
   registry entries with a non-empty `triggers.map`, monthly.*
2. **The 502 ms dispatch does not come down, and someone depends on it.** If
   Hybrid C is built and still cannot get an edit-to-effect p50 under ~400 ms,
   the plane cannot host the reconciler workload at all and the two must
   genuinely separate. *Measure: gate A4 against a socket-triggered `devman
   run`, n >= 20.*
3. **The queue turns out not to be load-bearing.** §4.1 is the plane's best
   fair win — 2,000 events into 4 bounded runs. If a year of `metadata.jsonl`
   shows the queue never actually throttled anything (no run ever waited),
   then D2 and D4 are theoretical and Hybrid A becomes the cheaper shape.
   *Measure: count runs whose `started_at` trails their enqueue by more than a
   second.*

---

## 9. What I did not measure

Listed plainly. This document is worth more with an honest gap list.

1. **The 20,000-file flood against the plane.** Scaled 10x down to 2,000, to
   avoid creating 20,000 source-shaped files in a repository in use (§4.1).
2. **One sample per point in the scaling curve**, not a distribution. The
   kickoff warns that the plane's latency varied 490 ms to 18 s across ten
   runs; CPU-tick and RSS sampling is far more stable than that, but a single
   60 s window is still a single window, and the machine carried load average
   3.86 throughout.
3. **Synthetic trees, not real repositories,** in section 2 — 316 directories
   each against a real median of ~650, and no file *activity*. The curve
   measures idle cost only. A busy tree may not scale the same way.
4. **A real `dspike` daemon at N > 1.** The spike columns use a bare
   `watchfiles` daemon with `dspike`'s parameters. The one real daemon measured
   (41.5 MB) is 2.2x the bare one, so the spike's memory curve in section 2 is
   an *under*-estimate, and I did not measure whether that factor holds at N=25.
5. **Full-disk behaviour**, either side.
6. **The cross-process manifest race** (`PIPELINE_RESULT.md` §7 item 1). Still
   unreproduced. I did not attempt it.
7. **Latency re-measurement.** §15.2's plane numbers (502 ms / 2,568 ms /
   18,476 ms) and the spike's 255 ms are taken from `PIPELINE_RESULT.md`, not
   re-run here. The kickoff said not to redo them; I leaned on them and did not
   verify them.
8. **Hybrid C's actual cost.** Recommended without a line estimate or a
   prototype. The 5.9 ms socket figure is the spike's, in the spike's process,
   and does not transfer without measurement.
9. **Whether `doctor`'s 18 checks can each fail.** The kickoff asked; I read
   the check list and the live output, which is clean, and did not induce a
   failure in any check. The claim in §4.2 that `doctor` can be false rests on
   §12 rule 4's worked example, not on a test I ran.
10. **The 54-repository projection cost.** How long shell entry takes, how
    much the projection writes, and whether `enterShell` is on anyone's
    critical path — all relevant to section 3 and none of it measured.

### 9.1 One incidental defect found while reading

`groups/format/triggers.toml` line 1 reads
`# python-format — which glob fires which workflow (CONCEPT.md §8).`
The group was renamed `format` at stage 7 and `groups/python-format/` is now a
tombstone. The comment names the tombstone. It is the only `triggers.toml` in
the repository, so this is the first line of the whole trigger mechanism. Not
fixed here — this document changes nothing.
