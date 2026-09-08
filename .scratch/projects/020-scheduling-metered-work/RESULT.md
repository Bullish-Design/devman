# 020 — RESULT: the scheduler does not enqueue, and the answer is not to make it

Closed 2026-09-08. Every option in `KICKOFF.md` §5 is decided below, each with
the measurement that decided it. The sixth queue name landed; the scheduled path
did not.

---

## 1. Option C — "not supported", and it is now a stronger claim than "not found"

**The kickoff recorded "NOT FOUND, NOT DOES NOT EXIST" and asked for two things:
the documentation, and the direct test. Both are done, and they agree.**

### 1.1 The documentation, from the binary itself

`dagu 2.15.0` ships a `schema` command the kickoff did not know about:

```
dagu schema <dag|config> [path]     Display schema documentation for DAG or config
```

`dagu config` prints resolved paths only, which is why the kickoff could not
settle this. **`dagu schema config` prints the whole settable key space as JSON
Schema, and it sets `additionalProperties: false` at the root and on every
definition.** So the absence of a key is now evidence rather than a failed
search.

```
$ dagu schema config | jq '.definitions.SchedulerDef.properties | keys'
["failure_threshold", "heartbeat_interval", "heartbeat_sync_interval",
 "lock_retry_interval", "lock_stale_threshold", "port", "stale_threshold",
 "zombie_detection_interval"]
```

**Eight keys, and every one of them is about locks, heartbeats and zombies.
There is no queue-routing setting, and `additionalProperties: false` means one
cannot be added by configuration.** `QueueConfigDef` holds only `enabled` and a
list of `{name, max_concurrency}`; nothing there names the scheduler either.

**Record it as: NOT SUPPORTED.**

### 1.2 The direct test, run as the kickoff specified

Two DAGs, both naming `exclusive` (`max_concurrency: 1`), both under
`schedule: "* * * * *"`, each holding for 20 s, against a scheduler with its own
`DAGU_HOME` and its own `config.yaml`:

```
START a 1788877199.730          START b 1788877199.746     ← 16 ms apart
START a 1788877200.101          START b 1788877200.122
END   a 1788877219.737          END   b 1788877219.752
END   a 1788877220.108          END   b 1788877220.129
```

**Four concurrent runs on a queue whose limit is one.** The scheduler log holds
`msg="Dispatching planned run"` four times and **no admission line at all** —
where `dag.enqueue` logs one (007 S-8).

This reproduces 007 S-1 on the pin and adds one thing S-1 did not show: **the
same DAG ran twice concurrently** (two `START a`, 0.37 s apart).

### 1.3 Option F, rejected again and now with a primary source

`dagu schema dag` on the same binary:

> `max_active_runs` — **DEPRECATED: This field is ignored for local (DAG-based)
> queues.** For concurrency control, define a global queue in config and use the
> `queue` field.

The kickoff rejected it by argument. It is now rejected by the vendor, in the
binary. §1.2's duplicate `START a` is the same fact from the other side.

---

## 2. Option E's list — and it is the answer

The kickoff said: *"If the list is entirely event-driven, Option E is the answer
and this project ships a paragraph."*

**The intended workload is `groups/agent/` — an Agentman capsule, run from the
plane (project 022). Every trigger it has is an event:** a commit hook, a
watcher glob, or a person at a prompt. Nothing in the Agentman Phase 5 design
asks for a schedule, and the two things the plane does schedule today —
`maintain` and `plane-report` — remain cheap by construction.

**So `groups/agent/workflows/agent.yaml` ships no `schedule:`.** Every Agentman
run reaches Dagu through `devman run`, which always enqueues
(`src/devman/run.py`) and never starts. **That is the one gated arrow, and the
gate therefore binds.**

This is the honest reading of the rule the kickoff quoted: *if what the plane
schedules must be cheap, and an LLM call is not cheap, then an LLM call is not
something the plane schedules.*

---

## 3. What was chosen for the day a periodic LLM workload appears

**Option B — a scheduled dispatcher DAG whose steps are `action: dag.enqueue`.**
Recorded as the chosen shape and **not built**, because a workflow nobody fires
is a workflow nobody reads (`groups/README.md`).

It is chosen over Option A because A takes the schedule out of the repository
(§7.4 says a schedule is content), puts it where `doctor` cannot see it, and
re-introduces a per-machine unit holding a project name — law 5 exactly.

Its unsolved problem is the one the kickoff named: **the dispatcher must derive
its fan-out from the registry rather than state a list of 54 project names.**
That is the first thing to solve when it is built, and §12 rule 9's stated
bound is the second.

**Option D — the workflow throttles itself — is rejected in writing**, on 013's
evidence and not on taste: mutual exclusion is not the same property as correct
ordering, and 013 measured it failing at exactly this. It also re-implements the
queue in shell in a shared group file (law 7), and a lock leaked by a killed run
blocks every repository until a person finds it. **Do not propose it again.**

---

## 4. The sixth queue name landed

`llm`, concurrency 2. Charter §7.1 is amended in the same commit, with §1's
measurement as the reason, and `nix/nixos-module.nix` declares it.

**Why a sixth rather than sharing `heavy`.** The other five bound a local
resource. `llm` bounds a quota held outside this machine — requests per minute,
tokens per minute, and money — shared by every repository at once. `heavy` is
sized against local builds and `gpu` is the local, unmetered inference server
(`groups/changelog/`). Sharing either couples two limits and tunes neither.

**Why a queue helps here when the standing objection said it would not.** §3 of
the kickoff, and it holds: for CPU work a queue buys a quieter peak and the same
total work. For a metered resource it buys correctness — 54 concurrent calls
against a per-minute limit return `429` and a partial fan-out; the same 54 at 2
at a time succeed for the same money.

**2 is a stated bound and not a measurement**, which the module says where the
number is. devman cannot measure another vendor's quota, and the other five
limits are unmeasured too (`AGENTS_GUIDE.md` §1).

---

## 5. The kickoff's other four, and where each landed

**§4.2 — §9.4 fires for the first time.** Done, in `groups/agent/`. Per
workflow, never in `base.yaml`. **And it produced a finding the section did not
have:** Dagu masks the **exact** value only. A step echoing `$TOKEN` logged
`*******`; the same step echoing its first five characters logged them in clear.
§9.4 is amended to say so, and `src/devman/agent.py` redacts to the same limit
deliberately, so devman's diagnostic is not safer than the log beside it.

**§4.3 — rule 4 is sharper for an LLM.** Handled by the receipt, and 019 was a
hard dependency as the kickoff said. `devman agent` trusts a
`missing_receipt: true` and **checks** a `false`: the file must exist, be inside
the repository this run targeted, and record this run's id.

**§4.4 — an LLM that edits tracked source is tier B.** Not devman's to enforce
here: a capsule declares its own `[writes]` tier and Agentman enforces it before
the backend starts. `groups/agent/writes.toml` declares only what devman writes,
and says so rather than paraphrasing a file it cannot read.

**§4.5 — cost has no ceiling.** Decided, and it is where the retry policy comes
from: **the plane retries nothing.** Every failure at this boundary is either
deterministic — where a retry fails identically — or post-invocation, where the
model was already billed. `agent.yaml` states no `retry_policy` and
`agent.invoke()` has one `Popen`. The bound that does not exist is stated in
`groups/agent/README.md` under what taking the group costs.

**§8 — `human-task`.** Still unexamined. It is not on this project's path and
it should be looked at before the next project assumes the lane is the only
review shape available.

---

## 6. What this left on the machine

Nothing. The scheduler test ran under `/tmp/devman-p5-sched` with its own
`DAGU_HOME`, its own `config.yaml` and its own `--dags` directory; the installed
plane was never involved, and no DAG was projected.
