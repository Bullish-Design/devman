# 022 — Phase 5, the devman half: evidence and decisions

Dated 2026-09-08. Every entry has the shape the plane's stage logs use: **the
answer, the versions, the exact command, the evidence, the charter impact, and
what it left on the machine.**

Versions throughout: `dagu 2.15.0` (`nix/dagu.nix`), `devenv 2.2.2`, the
Agentman contract `agentman.devman/v1` at
`~/Documents/Projects/agentman/contracts/devman-agentman/v1/`.

---

## M1 — Dagu sets `DAG_RUN_ID`, and there is no `DAGU_RUN_ID` in a step

**Answer.** The Agentman contract requires `DAGU_RUN_ID` in the Agentman
process. **Dagu 2.15.0 does not set it.** A step's environment holds
`DAG_RUN_ID`, and the names beginning `DAGU_` are only `DAGU_HOME`,
`DAGU_OUTPUT_FILE` and `DAGU_EXECUTABLE`.

**Command.** A DAG with `log_dir` in `/tmp`, one step, its own `DAGU_HOME`:

```yaml
steps:
  - name: show
    run: |
      env | grep '^DAG_'
      sh -c 'echo "grandchild sees: [$DAG_RUN_ID]"'
```

```
dagu start --dagu-home /tmp/devman-p5-probe/home --run-id probe-run-0004 probe.yaml
```

**Evidence.**

```
DAG_RUN_ID=probe-run-0004
DAG_NAME=probe
DAG_RUN_STEP_NAME=show
DAG_RUN_LOG_FILE=…   DAG_RUN_STEP_STDOUT_FILE=…   DAG_RUN_STEP_STDERR_FILE=…
DAG_RUN_WORK_DIR=…   DAG_DOCS_DIR=…               DAG_WIKI_DIR=…
grandchild sees: [probe-run-0004]
```

The grandchild line is the one that matters: it is a `sh -c` Dagu cannot
template, so `DAG_RUN_ID` is a **real inherited environment variable** and not a
substitution in the step's script. A `devenv tasks run` between the step and the
adapter therefore passes it through.

**Charter impact.** None. It is an integration fact, not a plane-wide name.

**Decision.** `src/devman/agent.py` is the single place that maps `DAG_RUN_ID` →
`DAGU_RUN_ID`. Neither side carries the other's spelling, and the id is **not** a
workflow parameter — a parameter could be filled with an id that is not this
run's.

**Left on the machine.** Nothing; `/tmp/devman-p5-probe`.

---

## M2 — Dagu cancels with `SIGTERM`, to the whole process group

**Answer.** `SIGTERM`. The step's shell, and its grandchildren, receive it.

**Command.** A step starting a Python child that logs the signals it receives,
then `dagu stop --run-id …` from another process 13 s later.

**Evidence.** The daemon:

```
msg="Stopping running child processes" stop-mode=graceful signal=terminated
    allow-override=true max-cleanup-time=30s
msg="Requesting step stop" stop-mode=graceful signal=terminated step=hold
msg="All child processes have been terminated"
msg="DAG run finished" status=aborted
```

The child:

```
shell      pid=3700836 pgid=3700836 child=3700838
grandchild pid=3700838 ppid=3700836 pgid=3700836 START     t=…206.842
grandchild pid=3700838 pgid=3700836 got=SIGTERM           t=…219.485
```

`dagu stop` was issued at `…219.432`. **53 ms**, to a grandchild sharing the
step's process group. A cancelled run records `Aborted`.

`allow-override=true` is the step-level `signal_on_stop` key, which
`dagu schema dag` documents as "Signal to send when stopping this step. If
empty, uses same signal as parent process."

**Decision.** `agent.invoke()` installs a `SIGTERM` handler that terminates the
child, and the adapter is deliberately **not** given
`start_new_session=True` — a new session would put Agentman outside the group
that gets the signal, turning a working cancellation into an orphan holding an
API connection. `test_the_adapter_stays_in_dagus_process_group` asserts the
absence, because the absence is the property.

---

## M3 — Dagu never escalates to `SIGKILL`

**Answer.** It does not. It re-sends `SIGTERM` on a 5 s period, indefinitely.
**A process that ignores `SIGTERM` is never killed and the DAG never finishes.**

**Command.** The same shape as M2, with a child whose `SIGTERM` handler does
nothing, observed for 75 s. `max_clean_up_time_sec` was left unset, so the log
shows the **default**.

**Evidence.**

```
10:21:00.471  Stopping running child processes  … max-cleanup-time=5s
10:21:04.777  Stopping running child processes  … max-cleanup-time=5s
10:21:09.776  Stopping running child processes  … max-cleanup-time=5s
… fifteen more, every 5.000 s …
```

The child logged one `IGNORED sig=15` and nothing after it. **There is no
`DAG run finished` line at all**, and no `SIGKILL`.

`dagu schema dag` describes `max_clean_up_time_sec` as "Maximum time in seconds
to spend cleaning up … before forcing shutdown. If exceeded, processes will be
killed." **The documentation says it kills; the measurement says it does not.**
Where the two disagree, the measurement governs (`tests/README.md` rule 4).

**Charter impact.** This is the finding that shapes the adapter. **The plane
cannot bound an Agentman run's lifetime.** `--timeout-s` in `devman agent` is
`SIGTERM`, five seconds, then `SIGKILL` — the escalation the daemon lacks — and
it is not decoration. Removing it removes the only bound there is.

---

## M4 — masking covers the exact value, and nothing else

**Answer.** Dagu replaces the exact resolved value with `*******`. **A partial
value is not masked.**

**Command.** One DAG with `secrets: [{name: PROBE_TOKEN, provider: env,
key: PROBE_SOURCE}]`, run with `PROBE_SOURCE=sekrit-value-12345`.

**Evidence.**

```
token=[*******]              ← echo "$PROBE_TOKEN"
len=18                       ← the true value reached the step
first5=sekri                 ← echo the first five characters: IN CLEAR
```

and, before any step ran: `msg="Resolving secrets" count=1`.

**Charter impact.** §9.4 is amended. It claimed masking without stating its
limit, and the limit is the part a workflow author has to know.

**Decision.** `agent.redact()` masks exact values only, **on purpose**, so
devman's diagnostic is not safer than the log beside it and nobody concludes the
log is safe. The rule that holds is the one `groups/agent/README.md` states: a
step must not print a fragment of a credential.
`test_the_diagnostic_masks_an_exact_secret_value` asserts both halves.

---

## M5 — a secret named with a `DAGU_` prefix cannot resolve

**Answer.** `dagu validate` refuses it.

**Evidence.**

```
Error: Validation failed for tests/fixtures/dagu/secrets-dagu-prefix.yaml
- field 'secrets': secret "DAGU_TOKEN" must not start with DAGU_
```

`dagu schema config`'s `secretRef` carries `"name": {..., "not": {"pattern":
"^DAGU_"}}`, so it is a schema rule and not an accident.

**Decision.** `agent.parse_secret()` refuses the same name one layer earlier, so
the message names the reason rather than a schema. The fixture is checked in.

---

## M6 — the scheduler does not enqueue

Recorded in full in
[`../020-scheduling-metered-work/RESULT.md`](../020-scheduling-metered-work/RESULT.md).
Two settled forms: `dagu schema config` sets `additionalProperties: false` and
its `SchedulerDef` has no queue-routing key, and two DAGs on a
`max_concurrency: 1` queue under `schedule:` produced four overlapping runs in
0.4 s with no admission line. `groups/agent/` therefore ships no `schedule:`.

---

# The decisions this evidence supports

## D1 — the request is a translation boundary and carries no policy

The v1 request holds `version`, `repository`, `capsule`, `backend`, `run_id`,
`limits` and `secrets`. **It has no capability, filesystem, network, write-tier,
retrieval, extractor, prompt or queue field, and the absence is the guarantee**:
devman cannot widen a capsule because there is no field through which a widening
could travel. `test_the_request_carries_no_policy_field` asserts the exact set.

**Agentman's v1 is sufficient for devman as it stands, and is adopted
unchanged.** No version bump was needed.

## D2 — by file, created and removed by devman

`agentman run --request <path>` takes a path, so a file is the entrypoint's own
shape. devman creates it with `mkstemp` at mode 0600 under
`.devman/.runs/agent/` — created by the plane, ignored by git and by the
watcher, so writing there cannot fire a run — and removes it in a `finally`,
which covers success, failure, timeout and cancellation alike. **It holds no
credential value.**

## D3 — a backend override may only narrow, and the allowlist is one name

`BACKEND_ALLOWLIST = ("fake",)`. A repository states its backend in its own
`agentman.toml`, which is composition. The only override devman authorises is
the one that cannot widen anything: `fake` reaches no network and spends no
money. An override to a real backend would let a workflow parameter decide what
a run costs, which is the opposite of a narrowing.

## D4 — limits belong in the request AND are enforced by devman

They are declarations in v1 and Agentman validates their shape without pretending
to enforce them. **M3 is why devman must actually enforce them.**
`--timeout-s` is wall clock, in `agent.invoke()`, with a real kill.
`--memory-mb` and `--cpu-seconds` are `RLIMIT_AS` and `RLIMIT_CPU`, applied in
the forked child before `exec` so they bind Agentman and everything it starts.
`RLIMIT_CPU` is processor seconds, not wall clock: a process blocked on a socket
burns no CPU and would never reach it, which is why the wall-clock bound exists
beside it rather than instead of it.

## D5 — no second envelope

Every outcome is a v1 `DevmanAgentmanResult`, including the ones that never
reached Agentman. The cause goes in `diagnostic`, which the schema gives 8192
characters for exactly this, and `missing_receipt` is true because no validated
work was proven. Giving a caller two schemas and a reason to guess which one it
has is worse than one schema that says what happened. A devman refusal reports
`3`/`usage` when it is deterministic and `2`/`infrastructure` when the machine is
at fault.

## D6 — devman checks the receipt rather than reading Agentman's answer back

**Trust a `missing_receipt: true`; check a `false`.** The direction that can hide
a failure is the one worth checking. Three things must hold and each can fail on
its own: the file exists; it is inside the repository this run targeted — a
receipt written elsewhere is §9.2's wrong-directory failure wearing a receipt;
and its `run` field equals this run's id, which is what correlates the artifact
with `DAG_RUN_ID`. A failure rewrites `exit_code` to 2 and leaves
`agentman_exit_code` untouched.

## D7 — the plane retries nothing

Every failure is either deterministic — a malformed request, an unauthorised
backend, a missing secret, a missing `agentman`, exit 3 — where a retry fails
identically; or post-invocation — a timeout, a cancellation, exit 2, a missing
receipt — where the model was already billed. 020 §4.5: a queue bounds
concurrency and nothing bounds spend. `agent.yaml` states no `retry_policy` and
`agent.invoke()` has one `Popen` with no path back to it. The table is in
`groups/agent/README.md`.

## D8 — `devman agent` is §10's fourth command

Amended into the charter with its reason. The first three are *about* the plane;
this one runs *inside* it, as the step of `groups/agent/`'s workflow. It is not
a devenv task because the translation is not one repository's implementation —
leaving it to each adopter would put the secret allowlist, the process bound, the
receipt check and the exit-code mapping in 54 devenv files that drift. It is not
shell in the workflow because law 7 says core logic is Python, and none of those
five things is testable in a Dagu step's shell.

---

# The unresolved dependency, stated rather than invented

**Nothing here is blocked.** Both questions the Agentman implementation note left
open for devman — the cancellation signal and the secret-manager mapping — are
answered above by primary measurement (M2, M3, M4, M5) rather than by an
interface devman invented.

**What is genuinely not proven: a live Claude run.** Every test uses
`tests/fixtures/fake_agentman.py`, a real subprocess with no network and no
credential. The end-to-end path through a real `agentman` binary, a real Dagu
service and a real key has not been run, and this project does not claim it.
`groups/agent/README.md` states what a repository must supply before it can be.
