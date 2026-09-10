# groups/agent — one admitted run, one Agentman capsule

```
a trigger → devman run agent → dagu enqueue → the llm queue
          → devman agent → agentman run --request → a receipt
```

**devman decides when a capsule runs, how many run at once, what credentials it
gets, and how long it lives. Agentman decides what one model invocation is
allowed to be.** This group is the whole of the boundary on devman's side, and
it is deliberately narrow: the request it builds carries references and no
policy field, so there is no field through which a capsule could be widened.

The versioned machine boundary is `agentman.devman/v1`, checked into the
Agentman repository at `contracts/devman-agentman/v1/`. devman implements it in
`src/devman/agent.py`.

## What this group ships

| Workflow | Queue | Schedule | Retry |
|---|---|---|---|
| `agent` | `llm` | **none** — see below | **none** — see below |

## What the adopting repository must define

**One devenv task, and it is the only thing this group asks of a task graph:**

```nix
tasks."agent:capsule".exec = ''
  set -eu
  devman agent \
    --capsule     "$AGENT_CAPSULE" \
    --timeout-s   "$AGENT_TIMEOUT_S" \
    --memory-mb   "$AGENT_MEMORY_MB" \
    --secret      anthropic:ANTHROPIC_API_KEY
'';
```

`devman` is on `PATH` from the NixOS module, and `agentman` must be on the
step's PATH — the adopting repository provides it along with any other external
tool its task needs. **A doctor asks its own PATH and not this step's** (023 P1),
so the adapter probes for `agentman` itself and names it when it is missing,
rather than failing later inside a pipe.

## How a repository identifies its capsule

**By name, in `AGENT_CAPSULE`, and the repository's own `agentman.toml` resolves
it.** devman never reads a `capsule.toml`. It passes a name and an absolute
repository path; Agentman composes the capsule from that repository's selection
and refuses a name that repository does not own.

The parameter's default is `review`. A repository that wants another one passes
it at the trigger:

```bash
devman run agent AGENT_CAPSULE=changelog
```

## How the request is built, and what is in it

`devman agent` writes one strict `agentman.devman/v1` request and invokes
`agentman run --request <file>` **exactly once**.

| Field | Where it comes from |
|---|---|
| `version` | the constant `agentman.devman/v1` |
| `repository` | `$DEVMAN_PROJECT_DIR`, absolute, which the projection wrote and the trigger passed |
| `capsule` | `--capsule` |
| `backend` | `--backend`, and only `fake` — see the policy below |
| `run_id` | `$DAG_RUN_ID` — see the identity note below |
| `limits` | `--timeout-s`, `--memory-mb`, `--cpu-seconds` |
| `secrets` | the logical half of each `--secret LOGICAL:ENVVAR` |

**A file, not stdin, and devman creates and removes it.** `agentman run` takes a
path, so a file is the entrypoint's own shape rather than a devman preference.
It is created with `mkstemp` at mode 0600 under `.devman/.runs/agent/` — which
the plane created, and which git and the watcher both ignore, so writing there
cannot fire a run — and it is removed in a `finally`. **It holds no credential
value**, only symbolic names.

**The request has no queue, capability, filesystem, network, write-tier,
retrieval, extractor or prompt field.** That absence is the guarantee. Adding
one needs a new contract version and an ownership decision on both sides.

## How the plane's run ID reaches Agentman

**Dagu 2.15.0 calls it `DAG_RUN_ID`. The contract calls it `DAGU_RUN_ID`.**

Measured on the pin: a step's environment holds `DAG_RUN_ID`, `DAG_NAME`,
`DAG_RUN_STEP_NAME` and the three log-file paths, and a grandchild of the step's
shell inherits every one of them. The names beginning `DAGU_` are only
`DAGU_HOME`, `DAGU_OUTPUT_FILE` and `DAGU_EXECUTABLE` — **there is no
`DAGU_RUN_ID` in a step**.

`src/devman/agent.py` is the single place that maps one spelling to the other.
Neither side carries the other's name, and Agentman still enforces its own rule:
a missing variable is an infrastructure result, a mismatch is a usage result.

**The id is not a parameter**, so no trigger can fill it with an id that is not
this run's.

## How the workflow selects the fake backend in tests

`--backend fake`. **It is the only override devman authorises, and the allowlist
is one name** (`agent.BACKEND_ALLOWLIST`).

A repository states its backend in its own `agentman.toml`, and that is
composition — Agentman's, not the plane's. The only change devman permits is the
one that cannot widen anything: `fake` reaches no network and spends no money.
An override to a real backend would let a workflow parameter decide what a run
costs, which is the opposite of a narrowing. Anything else is refused as a usage
error before the request file exists.

## How the workflow gets its result without a second model invocation

**Agentman prints one JSON `DevmanAgentmanResult` and `devman agent` reprints
it.** There is no second call, and Agentman's own bounded repair loop lives
inside that single invocation.

The adapter reads the last line of stdout that parses as a JSON object — a
dependency's warning ahead of it is not a reason to lose a run's verdict — and
then checks it, field by field: the contract version, that no unknown field is
present, that the run id and capsule are this run's, that the classification is
one of the five, and that both exit codes are 0..3. **A process that exits 0 and
prints something devman cannot read has not reported a clean result. It has
reported nothing**, and that is an infrastructure finding.

## Secrets

**Symbolic names only, at every layer.**

| Layer | Shape | Grammar |
|---|---|---|
| the capsule | `{ name = "anthropic", environment = "ANTHROPIC_API_KEY" }` | `^[a-z][a-z0-9_.-]*$` → `^[A-Z][A-Z0-9_]*$` |
| the workflow | `secrets: [{name, provider: env, key}]` | Dagu's, which additionally forbids a `DAGU_` prefix |
| the task | `--secret anthropic:ANTHROPIC_API_KEY` | both of the above, checked before a request exists |

**Dagu resolves the value onto the step and devman narrows it to the child.**
The adapter builds the Agentman process's environment **up from empty** rather
than filtering this one down: `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`,
`TERM`, `DEVMAN_PROJECT_DIR`, `DAGU_RUN_ID`, and then exactly the variables
`--secret` named. That is what makes it an allowlist. A second secret the
workflow declares, for another purpose, does not reach Agentman unless the task
names it — and Agentman refuses a logical name the capsule did not declare, so a
request can narrow the capsule's set and never widen it.

**A declared secret with no value is refused before the child starts**, as an
infrastructure result, naming the pair. Dagu's own block already fails a run
whose provider has no value; this catches the case where the task named a pair
the block does not declare, which Dagu has no way to notice.

**Masking covers the exact value and nothing else.** Measured on the pin: a step
echoing `$TOKEN` logged `*******`; the same step echoing its first five
characters logged them in clear. `devman agent` redacts its own diagnostic to
the same limit **on purpose**, so devman's output is not safer than the log
beside it and nobody concludes the log is safe. **The rule that actually holds
is that a step must not print a fragment of a credential.**

**A value never enters** the request file, a prompt, a workflow parameter, a
queue identifier, a receipt, a chat, an extractor artifact, a test report, or a
committed fixture. The child's environment is a local dictionary and is never
written anywhere.

**Cleanup.** The request file is removed in a `finally`, so it goes on success,
on failure, on timeout and on cancellation alike. The environment dictionary
dies with the process. Nothing is persisted to be cleaned up later.

## Resource limits, cancellation, and timeout

**Dagu cancels with `SIGTERM`, to the whole process group.** Measured: a
grandchild of the step's shell received signal 15 about 53 ms after `dagu stop`,
and the daemon logged `stop-mode=graceful signal=terminated
allow-override=true`. The Agentman child and its backend do receive it. The
adapter is deliberately **not** put in a new session, because a new session
would put the child outside the group that gets the signal — turning a working
cancellation into an orphan holding an API connection. The run records
`Aborted`.

**Dagu never escalates to `SIGKILL`, and this is the finding that matters.**
Measured over 75 s against a child that ignores `SIGTERM`: Dagu re-sent
`SIGTERM` every 5 s (`max-cleanup-time=5s`, the default) and the DAG never
finished at all. **So the plane cannot bound an Agentman run's lifetime, and
`devman agent` must.** `--timeout-s` is enforced in the adapter — `SIGTERM`,
five seconds, then `SIGKILL` — which is the escalation the daemon lacks. It is
not decoration, and removing it removes the only bound there is.

`--memory-mb` and `--cpu-seconds` are `RLIMIT_AS` and `RLIMIT_CPU`, applied in
the forked child before `exec`, so they bind Agentman and everything it starts.
`RLIMIT_CPU` is processor seconds and not wall clock: a process blocked on a
socket burns no CPU and would never reach it, which is why `--timeout-s` exists
beside it rather than instead of it.

**A cancelled or timed-out run can leave a receipt**, because Agentman may have
written one before the signal arrived. The adapter never deletes one and never
retries over one.

## Receipts

`.devman/.runs/receipts/agentman-<run id>.json`, which is the path shape §9.2
reserves and tier A's agent surface.

**devman trusts a `missing_receipt: true` and checks a `false`**, because the
direction that can hide a failure is the one worth checking. Three things must
hold, and each can fail on its own:

- the file exists;
- it is inside the repository this run targeted — a receipt written elsewhere
  proves work in the wrong tree, which is §9.2's wrong-directory failure wearing
  a receipt;
- its `run` field equals this run's id, which is what correlates the artifact
  with `DAG_RUN_ID` rather than with a file that happens to be there.

A failure rewrites `exit_code` to 2 and the classification to `missing_receipt`,
and **leaves `agentman_exit_code` untouched**, so the process result and the
integration finding stay distinguishable.

## Exit codes

| Agentman | devman `exit_code` | Classification | Means |
|---:|---:|---|---|
| 0 | 0 | `clean` | a validated result with nothing to decide |
| 1 | 1 | `finding` | a validated result that needs a person |
| 2 | 2 | `infrastructure` | no validated result, or execution failed |
| 3 | 3 | `usage` | an invalid capsule or an invalid request |
| 0 or 1 | **2** | `missing_receipt` | the process claimed success and proved nothing |

**The last row is not success, and that is rule 4 in one line.** A run that
reports success while producing no proof is the failure this design exists to
prevent.

A devman-side failure that never reached Agentman — a malformed request, an
unauthorised backend, a missing secret, a startup failure, a timeout, a
cancellation — is reported in **the same v1 document**, with the cause in
`diagnostic` and `missing_receipt: true`. There is no second envelope: giving a
caller two schemas and a reason to guess which one it has is worse than one
schema that says what happened.

## Retry policy

**The plane retries nothing, and `agent.yaml` states no `retry_policy`.**

| Failure | Retried | Why |
|---|---|---|
| queue admission | n/a | Dagu holds the run in the queue; there is no refusal to retry |
| malformed request | **no** | deterministic — it fails the same way |
| unauthorised backend or capsule | **no** | deterministic |
| missing secret | **no** | a person must supply it |
| process startup failure | **no** | `agentman` is absent; a retry hides a broken machine |
| timeout | **no** | the model was already invoked and billed |
| cancellation | **no** | a person asked it to stop |
| Agentman exit 2 | **no** | the call was made and paid for |
| Agentman exit 3 | **no** | usage — deterministic |
| missing receipt | **no** | the call was made; a retry pays twice and may overwrite |

020 §4.5 is the reason: a queue bounds concurrency and **nothing bounds spend**.
A retry loop against a paid API is the one failure in this design that a person
pays for in money. Every failure above is either deterministic — where a retry
fails identically — or post-invocation, where a retry pays twice. A person
re-runs `devman run agent`.

**A run that has produced a receipt is never repeated automatically.** There is
one `Popen` in `agent.invoke()` and no path back to it.

## What this group cannot do, structurally

The adapter cannot widen **capabilities, filesystem access, network access,
write tier, retrieval, extractors, backend permissions, or secret scope**. Not
by policy — by construction: the v1 request has no field for any of them, the
backend allowlist is one offline name, and the child's environment is built up
from empty rather than filtered down.

## What taking this group costs a repository

**1. A queue name every repository already inherits.** `llm`, concurrency 2, and
that limit stands in for a vendor's quota rather than this machine's cores. It
is a stated bound and not a measurement (charter §7.1 as amended by 022).

**2. A secret the machine must supply.** `agent.yaml` declares
`ANTHROPIC_API_KEY` through Dagu's `secrets:` block with `provider: env`. **If
the Dagu user service has no such variable, every run of this workflow fails
before its first step**, naming the secret and the provider. That is the
designed behaviour and it is still a cost: taking this group means putting a
credential on the machine. A repository whose capsule declares a different
secret shadows this file in its own `.devman/workflows/agent.yaml` — resolution
is whole-file (§7.3), so it copies the file to change the block.

**3. `agentman` on the step's PATH.** The repository provides it. Nothing in
this flake installs it.

**4. A devenv task named `agent:capsule`.** Above.

**5. Money, with no ceiling in this design.** The queue bounds how many run at
once. Nothing bounds spend, and the capsule's own `[budget]` is Agentman's bound
per run rather than the plane's bound per day. A trigger that fires often is a
bill that grows, and no part of devman will notice.

**6. `writes.toml` covers devman's writes only.** What the capsule writes is
governed by that capsule's own `[writes]` tier, which Agentman enforces before
the backend starts. A repository selecting a capsule that edits tracked source
narrows this group's declaration in its own `.devman/writes.toml`.

## Why there is no schedule, and what would carry one

020's measurement, re-run on the pin for this project: two DAGs naming a
`max_concurrency: 1` queue, both under `schedule: "* * * * *"`, started **four
overlapping runs inside 0.4 s**, and the scheduler logged "Dispatching planned
run" with no admission line. `dagu schema config` sets
`additionalProperties: false` and its `SchedulerDef` holds no queue-routing key,
so no configuration repairs it.

**An LLM call is metered outside this machine, so an ungated fan-out is not a
slower run — it is `429` across every repository at once.** This workflow is
therefore triggered and never scheduled, and every trigger reaches Dagu through
`devman run`, which always enqueues.

A genuinely periodic Agentman workload is 020's Option B: one cheap dispatcher
DAG carrying the `schedule:`, whose steps are `action: dag.enqueue` against the
real workflows. It is the shape to build when something needs it, and it is not
built here, because a workflow nobody fires is a workflow nobody reads.
