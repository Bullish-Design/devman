# FINDINGS — Investigation A, the Dagu capability audit

Answers to `KICKOFF_PROMPT.md` §1 (A1–A5), reported in the §5 shape.

**Version under test:** Dagu **2.15.0**, installed from the upstream release
tarball by `nix/dagu.nix`.
**Instance:** `DAGU_HOME=<repo>/.devenv/state/dagu`, started by `devenv up -d`
as `processes.dagu` (`dagu start-all`).
**Date:** 2026-08-21.
**Source read alongside the runs:** `git clone --depth 1 --branch v2.15.0
https://github.com/dagu-org/dagu.git /tmp/dagu-src`.

Every answer below pairs a schema claim with a run that proves it.

---

## E0 — Environment findings carried forward

These were measured in an earlier session. They are recorded here so the
reconciliation pass has one place to look.

### E0.1 — Dagu is absent from nixpkgs at every version

**Answer:** absent.
**Tested:** the machine's pinned nixpkgs and `github:NixOS/nixpkgs/nixos-unstable`, 2026-08-21.
**Command:**

```
nix eval --raw github:NixOS/nixpkgs/nixos-unstable#dagu.version
```

**Evidence:**

```
error: flake '...' does not provide attribute '...dagu.version'
```

**Charter impact:** **changes §4.** The plane must carry its own Dagu package.
It now does — `nix/dagu.nix`, one expression that both the devenv module and the
future NixOS module call, which is §3.1 applied to the one package both
interfaces need.

### E0.2 — Dagu 2.15.0 cannot be built from source on this machine today

**Answer:** no, for two independent reasons.
**Tested:** 2.15.0 at tag `v2.15.0`, 2026-08-21.
**Evidence:** `go.mod` declares `go 1.27.0` and nixpkgs ships 1.26.4; and the
web UI is a pnpm/webpack build whose output is not committed
(`internal/service/frontend/assets/` holds only a `.gitkeep` at the tag). The
package installs the upstream release tarball instead, pinned to the tag with
sha256 sums taken from the release's own `checksums.txt`.

**Charter impact:** **none.** No feature is lost — `.goreleaser.yaml` builds
`./cmd` with `CGO_ENABLED=0`, no build tags, and no edition gating, and the
release binary serves the full web UI bundle. Note the constraint so a later
pass can revisit when nixpkgs has Go 1.27.

---

## A1 — Per-DAG queues

**Answer:** **yes.** A DAG names a queue with the top-level `queue:` key. The
concurrency limit is set centrally in the instance config, never in the DAG. A
concurrency-1 queue serializes strictly, across *different* DAGs. An undefined
queue name is accepted **silently**.

**Tested:** dagu 2.15.0, on 2026-08-21.

### The schema

`internal/cmn/schema/dag.schema.json` — the DAG side is a name only:

```json
"queue": {
  "type": "string",
  "description": "Name of the queue to assign this DAG to. If not specified,
    defaults to the DAG name. Used with global queue configuration to control
    concurrent execution across multiple DAGs."
}
```

The DAG cannot set its own limit. `max_active_runs` is the only per-DAG
concurrency field left and it is dead:

```json
"max_active_runs": {
  "deprecated": true,
  "description": "DEPRECATED: This field is ignored for local (DAG-based)
    queues. For concurrency control, define a global queue in config and use
    the 'queue' field."
}
```

`internal/cmn/schema/config.schema.json` — the limit lives in the instance
config, under `queues.config[]`:

```json
"QueueDef": {
  "additionalProperties": false,
  "properties": {
    "name":            {"type": "string"},
    "max_active_runs": {"description": "Deprecated: use max_concurrency instead."},
    "max_concurrency": {"description": "Maximum concurrent runs for this queue."}
  }
}
```

**This is exactly the split §7.1 asserts:** the machine sets what a queue costs,
the workflow names one.

### Proof that a concurrency-1 queue serializes

`$DAGU_HOME/config.yaml`:

```yaml
queues:
  enabled: true
  config:
    - name: light
      max_concurrency: 4
    - name: exclusive
      max_concurrency: 1
```

Three **distinct** DAGs, each `queue: exclusive`, each sleeping 5 seconds:

```yaml
# a1_excl_x.yaml  (also _y, _z)
queue: exclusive
steps:
  - name: work
    run: |
      echo "START x $(date +%s.%N)"
      sleep 5
      echo "END x $(date +%s.%N)"
```

**Command:**

```
for n in x y z; do dagu enqueue a1_excl_$n; done
sleep 30
for n in x y z; do dagu status a1_excl_$n; done
```

**Evidence:**

```
START x 1787362628.197337136
END   x 1787362633.204267549
START y 1787362634.213516789     <- starts 1.0s after x ends
END   y 1787362639.225966403
START z 1787362640.212224124     <- starts 1.0s after y ends
END   z 1787362645.230370629
```

Strictly one at a time, and the DAGs are unrelated to each other. This is
**success criterion 12** ("two workflows naming the `exclusive` queue
serialize") satisfied at the level the charter asks for.

### Control — the limit is a real number, not blanket serialization

The same three-DAG shape on `queue: light` (`max_concurrency: 4`):

```
START x 1787362669.206083164
START z 1787362669.219368857
START y 1787362669.225121304     <- all three within 20ms
END   x 1787362674.213874975
END   z 1787362674.226946154
END   y 1787362674.232336135
```

All three overlapped. The queue enforces the configured number, not a fixed one.

### An undefined queue is silent

```yaml
# a1_ghost2.yaml
queue: no_such_queue
steps:
  - name: work
    run: echo ghost-ran
```

**Command:**

```
dagu validate $DAGU_HOME/dags/a1_ghost2.yaml; echo "exit=$?"
dagu enqueue a1_ghost
dagu status a1_ghost
```

**Evidence:**

```
exit=0                       <- validate prints nothing and succeeds
...msg="Enqueued dag-run" dag=a1_ghost run-id=034BJ0T2ZcB7jWT8PtRQxD
      ghost-ran
Result: Succeeded
```

No error, no warning, and nothing in `logs/admin/`. The run simply proceeds
outside any governed queue. **A typo in a queue name silently removes the
concurrency limit** rather than failing the run.

**Charter impact:** **none** for §7.1 — per-DAG queue names and central limits
both work as assumed, and §7.1's "it is Dagu's own field, not a devman word for
it" is literally true.

One addition for **§15.4**, which currently treats queue names only as a
rename-migration hazard: a *misspelled* queue name is not a migration problem,
it is an invisible one. Since Dagu will not catch it, `devman doctor` (§10)
should check every resolved workflow's `queue:` against the queue list the
machine module declares. That is a `doctor` check, not a new contract key.

---

## A2 — `working_dir` interpolation

**Answer:** **yes, at run time.** But the charter's spelling is wrong, and the
charter's proposed *source* for the variable does not work under a daemon.
Two other sources do, and both are per-run.

**Tested:** dagu 2.15.0, on 2026-08-21.

### The field is `working_dir`, not `workingDir`

The DAG schema sets `"additionalProperties": false` and spells the key
`working_dir`. camelCase is rejected outright:

**Command:**

```
dagu validate a2-camel        # file contains `workingDir: /tmp/devman-a2/projA`
```

**Evidence:**

```
Error: Validation failed for a2-camel
- failed to process document 0: decoding failed due to the following error(s):
  'spec.dag' has invalid keys: workingDir; use snake_case keys (workingDir -> working_dir)
```

The whole schema is snake_case. §7.2's example YAML is not loadable as written.

### Interpolation works, and it works at run time

One file, run twice against two different project directories, with **no
restart and no edit**:

```yaml
# a2-env.yaml
working_dir: ${DEVMAN_PROJECT_DIR}
steps:
  - id: show
    run: |
      echo "pwd=$(pwd)"
      echo "var=${DEVMAN_PROJECT_DIR}"
```

**Command:**

```
DEVMAN_PROJECT_DIR=/tmp/devman-a2/projA dagu start a2-env
DEVMAN_PROJECT_DIR=/tmp/devman-a2/projB dagu start a2-env
```

**Evidence:**

```
pwd=/tmp/devman-a2/projA
var=/tmp/devman-a2/projA
pwd=/tmp/devman-a2/projB
var=/tmp/devman-a2/projB
```

**Run time, definitively.** Load time would have pinned one value.

### The catch — Dagu filters the process environment

The first attempt at the run above produced this instead:

```
pwd=/home/andrew/.../special-dragon/${DEVMAN_PROJECT_DIR}
var=
```

An unresolved variable is **not an error**. It is kept as a literal path
segment and resolved relative to the caller's directory.

The cause is an allowlist in `internal/cmn/config/env.go`:

```go
var defaultWhitelist = map[string]bool{}

var defaultPrefixes = []string{
	strings.ToUpper(AppName) + "_", // "DAGU_"
	"DAG_",
	"LC_",
	"KUBERNETES_",
}
```

`DEVMAN_PROJECT_DIR` matches nothing, so it never reaches the DAG. Adding it to
the instance config fixes it:

```yaml
env_passthrough:
  - DEVMAN_PROJECT_DIR
env_passthrough_prefixes:
  - DEVMAN_
```

### The important part — the process environment is per *instance*, not per project

The runs above used `dagu start`, which executes in the CLI process and
therefore inherits the caller's environment. The real deployment enqueues to the
daemon. There, the caller's environment is irrelevant:

**Command:**

```
DEVMAN_PROJECT_DIR=/tmp/devman-a2/projA dagu enqueue a2-env
dagu status a2-env
```

**Evidence:**

```
pwd=/home/andrew/.../special-dragon/${DEVMAN_PROJECT_DIR}
var=
```

The variable resolved against the **daemon's** environment, which does not have
it. This is A2's "load time is a different design" concern in a different shape:
a variable supplied through Dagu's service environment is **one value per Dagu
instance**, and §4 puts one instance on the machine. It can never be per
project.

### Two sources that *are* per project

**1. `params`, overridden at trigger time.** This survives the daemon path:

```yaml
# a2-param.yaml
params:
  - DEVMAN_PROJECT_DIR: /tmp/devman-a2/projA
working_dir: ${DEVMAN_PROJECT_DIR}
steps:
  - id: show
    run: echo "pwd=$(pwd)"
```

**Command:**

```
dagu enqueue a2-param -- DEVMAN_PROJECT_DIR=/tmp/devman-a2/projB
dagu status a2-param
```

**Evidence:**

```
...msg="Enqueued dag-run" dag=a2-param params="[DEVMAN_PROJECT_DIR=/tmp/devman-a2/projB]"
      pwd=/tmp/devman-a2/projB
Result: Succeeded
```

**2. The DAG's own `env:` block.** Works, but the value is then baked into the
file — so a *shared group file* cannot use it, only a per-project projection
could.

```yaml
# a2-dagenv.yaml
env:
  - DEVMAN_PROJECT_DIR: /tmp/devman-a2/projB
working_dir: ${DEVMAN_PROJECT_DIR}
```

```
pwd=/tmp/devman-a2/projB
```

### Which other fields interpolate

```yaml
# a2-fields.yaml
working_dir: ${DEVMAN_PROJECT_DIR}
env:
  - DERIVED: ${DEVMAN_PROJECT_DIR}/.devman
steps:
  - name: step-name-with-hyphen
    working_dir: ${DEVMAN_PROJECT_DIR}/nested
    run: echo "step_pwd=$(pwd)"
  - name: in_run
    run: echo "in_run=${DEVMAN_PROJECT_DIR}"
  - name: in_env
    run: echo "in_env=$DERIVED"
```

**Evidence:**

```
step_pwd=/tmp/devman-a2/projA/nested
in_run=/tmp/devman-a2/projA
in_env=/tmp/devman-a2/projA/.devman
```

DAG `working_dir`, **step** `working_dir`, `run`, and `env` all interpolate, and
`env` entries may derive from one another. The schema documents the accepted
forms as `${env.NAME}`, `${NAME}`, `$NAME`, shell-style expressions, and
command substitution.

### Charter impact

**changes §7.2**, on three points:

1. **Spelling.** `workingDir:` must become `working_dir:`. The whole schema is
   snake_case, and camelCase fails to load. Cosmetic, but every example in the
   charter is currently invalid.
2. **The source of the variable.** §7.2 says "the machine module sets
   `DEVMAN_PROJECT_DIR` per project from the registry". Under one daemon (§4)
   that is impossible — the service environment holds one value for the whole
   instance. **The variable must be passed as a `params` override at trigger
   time**, by whatever invokes the workflow (`devman run`, a hook, a watcher).
   The machine module's job becomes declaring the passthrough allowlist, not
   supplying the value.
3. **`env_passthrough` is mandatory.** Any `DEVMAN_*` variable is filtered out
   by default, and an unresolved variable **fails silently** as a literal path
   segment rather than erroring. The machine module must set
   `env_passthrough_prefixes: [DEVMAN_]`.

**§7.2's headline claim survives, and it is the one that mattered:** one group
file, unedited, serves every repo that takes the group. **"devman never parses a
workflow" stands** — the path arrives as a parameter, so nothing rewrites the
file. Point 2 changes *who supplies* the value, not whether the file is
portable.

---

## A3 — Per-run log destination

**Answer:** **yes** — a run's logs and artifacts can be written under the
triggering project's `.devman/.runs/`, and the §12.1 measurement passes. But
`log_dir` interpolates from a **different** source than `working_dir` does, and
run history is **not** relocatable at all.

**Tested:** dagu 2.15.0, on 2026-08-21.

### Both directories are per-DAG fields

`internal/cmn/schema/dag.schema.json`:

```json
"log_dir": {
  "type": "string",
  "description": "Base directory for storing logs. Defaults to
    ${HOME}/.local/share/logs if not specified."
},
"artifacts": {
  "additionalProperties": false,
  "properties": {
    "enabled": {"description": "Enable per-DAG-run artifact storage."},
    "dir":     {"description": "Base directory for storing artifacts for this
                 DAG. Defaults to the global artifact_dir when omitted."}
  }
}
```

Per DAG, not only per instance. The instance-wide `log_dir` and `artifact_dir`
in `config.schema.json` are defaults.

### The §12.1 measurement — one file, two projects

```yaml
# a3_combined.yaml
params:
  - DEVMAN_PROJECT_DIR: /tmp/devman-a2/projA
working_dir: ${DEVMAN_PROJECT_DIR}
log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs
steps:
  - name: emit
    run: |
      echo "cwd=$(pwd)"
      echo "err" 1>&2
```

**Command:**

```
for P in projA projB; do
  DEVMAN_PROJECT_DIR=/tmp/devman-a2/$P \
    dagu enqueue a3_combined -- DEVMAN_PROJECT_DIR=/tmp/devman-a2/$P
done
find /tmp/devman-a2 -type f
```

**Evidence:**

```
projA/.devman/.runs/logs/a3_combined/dag-run_20260822_014552Z_034BJC61.../dag-run_....log
projA/.devman/.runs/logs/a3_combined/dag-run_20260822_014552Z_034BJC61.../run_.../emit....out
projA/.devman/.runs/logs/a3_combined/dag-run_20260822_014552Z_034BJC61.../run_.../emit....err
projB/.devman/.runs/logs/a3_combined/dag-run_20260822_014600Z_034BJCIl.../dag-run_....log
projB/.devman/.runs/logs/a3_combined/dag-run_20260822_014600Z_034BJCIl.../run_.../emit....out
projB/.devman/.runs/logs/a3_combined/dag-run_20260822_014600Z_034BJCIl.../run_.../emit....err
```

**One unedited file, two projects, logs under each project's own
`.devman/.runs/`.** This is the §12.1 spike, and it passes.

Artifacts behave the same way. With `artifacts.enabled: true` and
`artifacts.dir` set alongside:

```
projB/.devman/.runs/artifacts/a3_artifacts/dag-run_20260822_014653Z_034BJDde.../reports/report.md
```

### `log_dir` takes the process environment ONLY

This is the trap. `working_dir` accepts the variable from three sources;
`log_dir` accepts it from **one**.

| source of `DEVMAN_PROJECT_DIR` | `working_dir` | `log_dir` / `artifacts.dir` |
|---|---|---|
| Dagu process environment (via `env_passthrough`) | resolves | **resolves** |
| `params`, including a trigger-time override | resolves | **stays literal** |
| the DAG's own `env:` block | resolves | **stays literal** |

**Command (params only, no environment variable):**

```
env -u DEVMAN_PROJECT_DIR dagu enqueue a3_artifacts -- DEVMAN_PROJECT_DIR=/tmp/devman-a2/projA
dagu status a3_artifacts
```

**Evidence:**

```
├─log: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/a3_artifacts/dag-run_...
```

Dagu then **creates a directory literally named `${DEVMAN_PROJECT_DIR}`**,
relative to the working directory of the process that resolved the DAG:

```
$ find '<repo>/${DEVMAN_PROJECT_DIR}' -type f
${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/a3_artifacts/.../dag-run_....log
${DEVMAN_PROJECT_DIR}/.devman/.runs/artifacts/a3_artifacts/.../reports/report.md

$ git status --porcelain
?? ${DEVMAN_PROJECT_DIR}/
```

**An unresolved log path is silent, and it dirties the repository.** No error,
no warning, exit 0. Because the resolving process is often the daemon, whose
working directory is wherever it was started, this litters an unrelated tree.

The practical consequence: **a trigger must export `DEVMAN_PROJECT_DIR` in its
own environment *and* pass it as a param.** The environment reaches `log_dir`,
the param reaches `working_dir`. That is what the passing measurement above
does. One is not a substitute for the other.

### What Dagu writes, and what a workflow must write itself

**Dagu writes,** under `log_dir`:

- one DAG-run log per run
- per step, `.out` and `.err` (`log_output: separate`), or one `.log`
  (`log_output: merged`)

**Dagu writes,** under `artifacts.dir`, when `artifacts.enabled: true`: whatever
a step declares through `stdout.artifact`, `stderr.artifact`, or the
`artifact.write` / `artifact.read` / `artifact.list` actions. Steps read the
resolved location as `${context.paths.artifacts_dir}`.

**A workflow must write for itself:** §9.2's `reports/` and `metadata.json`.
Dagu keeps its own run record, but not where §9.2 wants it — see below.

### Run history is separable from logs, and is machine-side only

Run history lives under `data_dir`, inside `DAGU_HOME`, and **no per-DAG field
relocates it**:

```
$DAGU_HOME/data/dag-runs/a3_combined/dag-runs/2026/08/22/
  dag-run_20260822_014552Z_034BJC61pnn47kjB8ep8aX/
    a_20260822_014552_337Z_978d0f/
      dag.json        <- the DAG spec as executed
      status.jsonl    <- the run record
```

The record is rich, and it stores the resolved log paths:

```json
{"name":"a3_combined","dagRunId":"034BJC61pnn47kjB8ep8aX","status":4,
 "nodes":[{"step":{"name":"emit"},
   "stdout":"/tmp/devman-a2/projA/.devman/.runs/logs/.../emit....out",
   "stderr":"/tmp/devman-a2/projA/.devman/.runs/logs/.../emit....err",
   "workingDir":"/tmp/devman-a2/projA",
   "startedAt":"2026-08-21T21:45:53-04:00","status":4}], ...}
```

So history and logs are **fully separable** — but only in one direction. Logs
follow the project; history stays on the machine.

### Charter impact

**changes §9.2**, on two points:

1. **The two-location layout survives.** Logs and artifacts do land in
   `<repo>/.devman/.runs/`, from one shared group file. §9.2's core claim holds
   and §12.1 passes.
2. **`metadata.json` cannot come from Dagu's run store.** §9.2 lists
   `.devman/.runs/<run-id>/metadata.json` beside the logs. Dagu's own record is
   machine-side under `data_dir` and no per-DAG field moves it. Either a
   workflow writes `metadata.json` itself, or `devman doctor` projects it out of
   Dagu's history. Say which; do not leave it implied.

One addition for **§8.1 and §9.2**: the machine module must set
`env_passthrough_prefixes: [DEVMAN_]`, and every trigger must export
`DEVMAN_PROJECT_DIR` as well as pass it. A trigger that forgets the environment
variable does not fail — it writes a directory named `${DEVMAN_PROJECT_DIR}`
into whatever tree the daemon was started in. **`devman doctor` should look for
that directory**; it is the visible symptom of a broken trigger.

---

## A4 — DAG-to-DAG triggering

**Answer:** **yes for triggering, waiting, failure, and results — but NO for the
one thing §11 relies on.** A child DAG does *not* reliably run with its own
`working_dir`. When the parent defines a variable of the same name, the
parent's value wins, and **not even an explicit `with.params` override can
defeat it.**

**Tested:** dagu 2.15.0, on 2026-08-21.

### The three sub-questions that pass

**Trigger by name and wait — yes.** `action: dag.run`, `with.dag`:

```yaml
steps:
  - id: child
    action: dag.run
    with:
      dag: a4_child
```

It is synchronous. The parent step ends when the child ends.

**Failure propagates — yes, with the exact exit status.**

```
dagu start a4_parent_fail     # child runs `exit 3`
```

```
├─child (0s) [failed]
│ └─error: exit status 3
└─after [aborted]
Result: Failed
Error: failed to execute the dag-run a4_parent_fail (...): exit status 3
```

The downstream step aborted rather than running.

**The parent can read the child's result — yes.** The child publishes with
`stdout.outputs`; the parent reads `${<step_id>.outputs.<name>}`:

```yaml
# child
    stdout:
      outputs:
        fields:
          verdict: {decode: json, select: .verdict}
# parent
  - id: after
    run: echo "PARENT read child verdict=${child.outputs.verdict}"
```

```
PARENT read child verdict=child-ok
```

The `dag.run` step's own stdout is a JSON summary:

```json
{"name":"a4_child","dagRunId":"BBZFdtwPDzwCfBCzYosWi5RXM8V3eyr61JqJ2EomSTi9",
 "params":"DEVMAN_PROJECT_DIR=/tmp/devman-a2/projB",
 "outputs":{},"outputValues":{"verdict":"child-ok"},"status":"succeeded"}
```

Note the reference form. `${steps.<id>.outputs.<name>}` is **only** for
declared step outputs; for a `dag.run` step it is `${<id>.outputs.<name>}`. The
wrong form is not an error — it reaches the shell verbatim and fails there
(`zsh:1: bad substitution`).

### The sub-question that fails

**The child inherits the parent's variable.** The same child file, run two ways:

**Command:**

```
dagu start a4_child            # standalone
dagu start a4_parent           # parent's own param is /tmp/devman-a2/projA
```

**Evidence:**

```
standalone        CHILD cwd=/tmp/devman-a2/projB     <- its own default param
under the parent  resolved cwd = /tmp/devman-a2/projA <- the PARENT's value
```

The child's stored spec is untouched — it still reads `queue: exclusive`,
`workingDir: ${DEVMAN_PROJECT_DIR}`, and
`defaultParams: DEVMAN_PROJECT_DIR="/tmp/devman-a2/projB"`. Only the
*resolution* is wrong. The parent exports its parameters into the child's
process environment, and that environment outranks the child's own definitions.

**Three defences were tried. All three failed:**

| the child's defence | resolved cwd | wanted |
|---|---|---|
| its own `params:` default | `/tmp/devman-a2/projA` | projB |
| its own `env:` block | `/tmp/devman-a2/projA` | projB |
| the parent's explicit `with.params: DEVMAN_PROJECT_DIR: .../projB` | `/tmp/devman-a2/projA` | projB |

The third is the surprising one. The parameter is passed, recorded, and
visible — and still loses:

```
└─subdag: DBoCSJmAfrEAytDpFuVLv5iHxceA9iRt2W1jaHgF2m2j [DEVMAN_PROJECT_DIR="/tmp/devman-a2/projB"]
   ...resolved cwd = /tmp/devman-a2/projA
```

This contradicts upstream's own documentation, `skills/dagu/references/steptypes.md`:

> Sub-DAGs do not inherit parent env vars. Pass values explicitly via `with.params`.

### It is a name collision, and that is what makes it fixable

One parent, two children, run in the same DAG:

```yaml
# a4_parent_diag.yaml — parent's own param is DEVMAN_PROJECT_DIR=.../projA
steps:
  - id: same_name        # child uses DEVMAN_PROJECT_DIR, default .../projB
    action: dag.run
    with: {dag: a4_child_diag, params: {DEVMAN_PROJECT_DIR: /tmp/devman-a2/projB}}
  - id: distinct_name    # child uses CHILD_DIR, default .../projB
    action: dag.run
    with: {dag: a4_child_distinct}
    depends: [same_name]
```

**Evidence:**

```
a4_child_diag        resolved cwd = /tmp/devman-a2/projA    <- collided
a4_child_distinct    resolved cwd = /tmp/devman-a2/projB    <- correct
```

Only the *shared name* breaks. So the fix is to stop sharing it at the parent.

### The fix, measured

A cross-repo parent that never defines `DEVMAN_PROJECT_DIR` at all:

```yaml
# a4_parent_clean.yaml — no params, no env, no working_dir
steps:
  - id: lib_a
    action: dag.run
    with: {dag: a4_child_diag}      # pins its project via params
  - id: lib_b
    action: dag.run
    with: {dag: a4_child_env}       # pins its project via env:
    depends: [lib_a]
```

**Command:**

```
env -u DEVMAN_PROJECT_DIR dagu start a4_parent_clean
```

**Evidence:**

```
a4_child_diag    resolved cwd = /tmp/devman-a2/projB
a4_child_env     resolved cwd = /tmp/devman-a2/projB
Result: Succeeded
```

**Both children resolved their own project correctly.** §11's goal is reachable.

### One more thing — a child's history nests under the parent

A child run is not an independent run of that DAG. It is stored beneath the
parent's record:

```
data/dag-runs/a4_parent/dag-runs/2026/08/22/dag-run_<parent-id>/
  sub/<child-run-id>/a_.../{dag.json,status.jsonl}
```

There is no `data/dag-runs/a4_child/` directory at all. `status.jsonl` carries
`"parent": {"name": "a4_parent", "id": "..."}`.

### Charter impact

**changes §11**, and it is the sentence at the centre of it. §11 says:

> Its steps trigger other projects' workflows rather than running commands, so
> it resolves nothing itself — each triggered workflow already carries its own
> project's `workingDir` (§7.2). Nothing needs a path.

**"Already carries its own project's `working_dir`" is false as written**, and
would have been false in exactly the configuration the charter specifies: §7.2
mandates one variable name for every workflow, and §11's parent is itself a
registered devman project, so it would carry `DEVMAN_PROJECT_DIR` too. Every
parent-child pair in the design collides, and the collision is silent — the
child runs, succeeds, and does the work in the wrong directory.

**What to do instead — add one rule to §11:**

> A cross-repo workflow must not define `DEVMAN_PROJECT_DIR`, in `params`, in
> `env:`, or in `working_dir`. It names other workflows and nothing else.

That keeps §11's conclusion ("nothing needs a path") intact and costs one
sentence. But it does mean **a cross-repo workflow is not shaped like an
ordinary workflow** — it cannot carry §7.2's standard `working_dir` line. §11
currently claims a cross-repo workflow is "simply one of devman's own files";
after this it is one of devman's own files *of a second shape*. Say so.

Two consequences worth recording while the charter is open:

- **§10 — `devman doctor` should check this.** A parent that defines the
  variable is a silent misconfiguration Dagu will not report. It is mechanically
  detectable: any workflow containing `action: dag.run` must not also mention
  `DEVMAN_PROJECT_DIR`.
- **§9.2 — a child's run history goes to the parent's tree**, not the child
  project's. Child *logs* still follow `log_dir` and land in the child project;
  only the history record nests. §9.2 should not promise that a cross-repo run
  appears in each participating project's run history.

---

## A5 — Unknown keys, and DAG discovery

**Answer:** unknown top-level keys are **rejected**. Discovery is a **directory
scan**, and a new DAG needs **no restart** — but subdirectories and symlinks are
both off by default.

**Tested:** dagu 2.15.0, on 2026-08-21.

### Unknown top-level keys are rejected

`dag.schema.json` sets `"additionalProperties": false`, and the loader enforces
it.

**Command:**

```
dagu validate $DAGU_HOME/dags/a5_unknown.yaml    # file has an `x-devman:` block
dagu start a5_unknown
```

**Evidence:**

```
Error: Validation failed for .../a5_unknown.yaml
- failed to process document 0: decoding failed due to the following error(s):
  'spec.dag' has invalid keys: x-devman

Error: failed to load DAG from a5_unknown: failed to process document 0:
  decoding failed due to the following error(s):
  'spec.dag' has invalid keys: x-devman
```

A hard load failure, not a warning. **If devman ever needs per-workflow
metadata, a sidecar file is the only option** — the DAG file cannot carry it.

**Charter impact: none.** §7.2 already removed `x-devman`. This records what it
would cost to bring one back.

### A top-level `name:` is rejected by `validate`

Found while testing the above, and worth recording because most upstream
examples include it.

**Command:**

```
dagu validate $DAGU_HOME/dags/a2-env.yaml    # file starts with `name: a2-env`
```

**Evidence:**

```
Error: Validation failed for .../a2-env.yaml
- entrypoint document must not define name
```

Removing the `name:` key makes `validate` pass silently. `start` and `enqueue`
tolerate it, so the three commands disagree. **A DAG's identity is its file
name**, which is what `ls` reports and what every command resolves. This
*confirms* §7.2's "the directory names the group; the file names the workflow" —
and means group files should carry no `name:` key at all.

### Step `id` values may not contain a hyphen

```
Error: ... invalid step ID format: must match ^[a-zA-Z][a-zA-Z0-9_]*$
  (use '_' instead of '-') (value: step-wd)
```

Step `name:` accepts hyphens; step `id:` does not. Only `id:` participates in
`${<id>.outputs.<name>}` references, so a step whose result another step reads
must use an underscore.

### Discovery is a directory scan, and needs no restart

The daemon had been running for 978 seconds when a brand-new file was dropped
into `dags/`:

**Command:**

```
pgrep -af "dagu start-all"        # pid 1771311, uptime 978s
cat > $DAGU_HOME/dags/a5_brandnew.yaml <<'EOF'
steps:
  - id: fresh
    run: echo "brand new DAG, no restart"
EOF
dagu ls | grep brandnew
dagu enqueue a5_brandnew
dagu status a5_brandnew
```

**Evidence:**

```
uptime_seconds=978
a5_brandnew                        <- listed immediately
run-id=034BJM1gtkJ2n20Aiyf1qt
      brand new DAG, no restart
Result: Succeeded
```

The **already-running** daemon executed it. Dagu logs `Rebuilding DAG
definition index` when the directory changes. **§5.2's assumption is correct:
registration can add a project's workflows without restarting the service.**

### But subdirectories and symlinks are off by default

`config.schema.json`:

```json
"DAGDiscoveryDef": {
  "recursive": {"default": false, "description": "Discover DAG definitions in subdirectories."},
  "symlinks":  {"default": false, "description": "Include file symlinks in recursive DAG
     discovery and allow file symlinks whose targets are outside the configured DAG directory."}
}
```

With both unset, a symlinked DAG and a DAG in a subdirectory are **not listed**:

```
$ dagu ls | grep symlink
NOT LISTED
$ dagu ls | grep a5_nested
(nothing)
```

A symlinked DAG is nonetheless **runnable by name**, which is a trap:

```
$ dagu start a5_symlink
      from a symlinked group file
Result: Succeeded
```

So listing, the web UI, and the scheduler ignore it while `start` accepts it.

Setting both knobs fixes both cases:

```yaml
dag_discovery:
  recursive: true
  symlinks: true
```

```
$ dagu ls | grep -E "symlink|nested"
a5_nested
a5_symlink
```

**Charter impact:** **changes §5.2 / §9.2**, in one sentence. §9.2 projects
workflows into `~/.local/share/devman/projects/<project>/workflows/*.yaml`.
Whether that projection is a **copy** or a **symlink into the Nix store**, and
whether projects get one directory each, both depend on these two knobs. The
machine module must set `dag_discovery.recursive: true` and
`dag_discovery.symlinks: true` if the projection uses per-project subdirectories
or symlinks — which §9.2's layout does. Neither is on by default, and neither
failure mode announces itself.

---

## Summary — every `changes §N` and `kills §N`

Nothing in Investigation A **kills** a section. Four sections change.

| ID | Assumption | Supported | Charter impact |
|---|---|---|---|
| A1 | a DAG can name a queue | **yes** | none |
| A1 | the limit is set centrally | **yes** | none |
| A1 | a concurrency-1 queue serializes | **yes** | none |
| A1 | an undefined queue is caught | **no — silent** | changes §15.4 |
| A2 | `workingDir` interpolates | **yes**, as `working_dir` | changes §7.2 |
| A2 | it resolves at run time | **yes** | none |
| A2 | the machine module sets it per project | **no** | changes §7.2 |
| A3 | logs can go to the project | **yes** | none |
| A3 | `log_dir` takes the same variable source | **no** | changes §9.2 |
| A3 | run history follows the logs | **no** | changes §9.2 |
| A4 | one DAG triggers another and waits | **yes** | none |
| A4 | failure propagates | **yes** | none |
| A4 | the parent reads the child's result | **yes** | none |
| A4 | **the child keeps its own `working_dir`** | **no** | **changes §11** |
| A5 | unknown top-level keys | rejected | none |
| A5 | discovery needs no restart | **yes** | none |
| A5 | subdirectories and symlinks are found | **no — off by default** | changes §5.2, §9.2 |

### The list, by section

- **changes §7.2** — three edits. Spell the key `working_dir`, not `workingDir`;
  camelCase fails to load. The per-project value must arrive as a **`params`
  override at trigger time**, because a variable in Dagu's service environment
  holds one value for the whole instance. And the machine module must set
  `env_passthrough_prefixes: [DEVMAN_]`, or the variable never reaches a DAG.
  *§7.2's headline claims survive: one group file serves every repo, and devman
  still never parses a workflow.*

- **changes §9.2** — three edits. A trigger must export `DEVMAN_PROJECT_DIR` in
  its environment **as well as** pass it as a param, because `log_dir` reads only
  the process environment while `working_dir` reads only params. `metadata.json`
  cannot come from Dagu's run store, which is machine-side and not relocatable —
  say whether a workflow writes it or `doctor` projects it. And a cross-repo
  run's child history nests under the parent, so it does not appear in each
  participating project's history.

- **changes §11** — one added rule. *A cross-repo workflow must not define
  `DEVMAN_PROJECT_DIR`, in `params`, in `env:`, or in `working_dir`.* Without it
  the parent's value silently overrides every child's, and the work runs in the
  wrong directory. With it, §11's conclusion holds. Note the consequence: a
  cross-repo workflow is a second shape of file, not an ordinary one.

- **changes §5.2** — one sentence. The machine module must set
  `dag_discovery.recursive: true` and `dag_discovery.symlinks: true` if the
  projection uses per-project subdirectories or symlinks. Both default to off.

- **changes §15.4** — one addition. Queue names are not only a rename hazard. A
  *misspelled* queue name is accepted silently and runs the workflow with no
  concurrency limit at all. `devman doctor` should check every resolved
  workflow's `queue:` against the machine module's queue list.

- **changes §4** — already applied. nixpkgs packages no Dagu, so the plane
  carries `nix/dagu.nix`. See E0.1.

### Two things `devman doctor` must check, both from this investigation

Neither failure produces an error from Dagu, and both are mechanically
detectable:

1. **A workflow containing `action: dag.run` that also mentions
   `DEVMAN_PROJECT_DIR`** — the A4 collision. Silent wrong-directory execution.
2. **A directory literally named `${DEVMAN_PROJECT_DIR}`** anywhere the daemon
   might have been started — the A3 symptom of a trigger that passed the param
   but forgot the environment variable.

### Where this leaves planning

`KICKOFF_PROMPT.md` §6 item 1 is satisfied: every A-series assumption has a
yes/no with evidence. No section is killed, so the charter's shape stands and
Investigations B, C, and D may proceed once the four `changes §N` above are
reconciled into `CONCEPT.md`.

Per §7 of the kickoff, **A4's "no" is reported without being worked around.**
The one-rule fix in A4 is measured and recorded, not applied — reconciling it is
the later pass's decision.

---

## A6 — Alternatives considered, and why three of the four changes are forced

Added after A1–A5, to answer a direct question: is the recorded design the best
available, or is there a cleaner one? Each alternative below was **run**, not
reasoned about. One of them improves on what A4 recorded; the rest are closed
off by measurement.

**Tested:** dagu 2.15.0, on 2026-08-21.

### The tempting simplification: carry no variable at all

Every one of A2, A3 and A4's problems comes from the same source — the design
carries a project path in a variable. Dagu appears to offer three ways to avoid
that. **All three fail.**

**1. Let `working_dir` default to the DAG file's own directory.** The schema
promises this: *"Defaults to the directory containing the DAG file."* If each
project's workflow files physically lived in that project, no variable would be
needed. But `dags_dir` is a single directory (`dags` is deprecated, and there is
no list form), so the files must be reached by link.

**Command:**

```
ln -sfn /tmp/devman-a2/projA/.devman/workflows/h1_defaults.yaml $DAGU_HOME/dags/
dagu start h1_defaults        # file has no working_dir at all
```

**Evidence:**

```
cwd=/home/andrew/.../special-dragon/.devenv/state/dagu/dags
```

The default is the **symlink's** directory, not the target's. And a *directory*
symlink is not followed at all, even with `dag_discovery.symlinks: true` — that
option covers file symlinks only:

```
$ ln -sfn /tmp/devman-a2/projB/.devman/workflows $DAGU_HOME/dags/projB
$ dagu ls | grep h2
not listed
```

**2. Use a relative `working_dir`.** Both the schema and the generated
`base.yaml` say relative paths resolve *"against DAG file location"*.

**Command:**

```
# $DAGU_HOME/dags/nest/h3_rel.yaml, working_dir: ../../../../../tmp/devman-a2/projA
dagu start nest/h3_rel
```

**Evidence:**

```
cwd=/home/andrew/.../special-dragon/tmp/devman-a2/projA
```

It resolved against the **process working directory**, not the DAG file. The
documentation is wrong. A relative `working_dir` is unusable for this purpose.

**3. Give each project its own instance config at trigger time.** `enqueue`
accepts `-c/--config`, and it does work — with no variable anywhere:

```
$ printf 'log_dir: /tmp/devman-a2/projB/.devman/.runs/logs\n' > cfg/projB.yaml
$ dagu enqueue --config cfg/projB.yaml t5_cfg
├─log: /tmp/devman-a2/projB/.devman/.runs/logs/t5_cfg/dag-run_.../dag-run_....log
Result: Succeeded
```

But `--config` **replaces** the instance config rather than merging with it —
the `auth.mode: none` set in the shared config was lost, and the queue
definitions would be too. It also still leaves `working_dir` needing a param.
A per-project config file to maintain, and no fewer mechanisms. **Not better.**

### Why the dual env-var + param requirement is forced, not clumsy

A3 concluded that a trigger must **export** `DEVMAN_PROJECT_DIR` (for `log_dir`)
*and* **pass it as a param** (for `working_dir`). One mechanism would do if the
trigger used `dagu start` instead of `dagu enqueue`, because a locally executed
run resolves both fields in the caller's own process.

That would cost queues. **Measured:**

**Command:**

```
dagu start a1_excl_x &        # both DAGs declare queue: exclusive
dagu start a1_excl_y &        # max_concurrency: 1
wait
```

**Evidence:**

```
START x 1787364543.990688281
START y 1787364544.295752367     <- 0.3s later, while x is still running
END   x 1787364549.002072628
END   y 1787364549.307689935
```

**`dagu start` ignores the queue entirely.** Only `enqueue` is governed —
compare A1, where the same two DAGs serialized strictly under `enqueue`.

Since §7.1 makes queue names the plane's *only* global vocabulary, and success
criterion 12 requires that two workflows naming `exclusive` serialize, **the
trigger must use `enqueue`**. The dual mechanism follows from wanting queues at
all. It is not an accident of the design and there is no cleaner route to it.

The practical cost is small: `devman run` is the one place that triggers a
workflow, so both mechanisms live in one implementation.

| trigger | queue enforced | one exported variable is enough |
|---|---|---|
| `dagu start` | **no** | yes |
| `dagu enqueue` | **yes** | no — needs the variable *and* the param |

### A better fix for A4 than the one recorded above

A4 recorded this rule:

> A cross-repo workflow must not define `DEVMAN_PROJECT_DIR`, in `params`, in
> `env:`, or in `working_dir`.

That works, but it makes a cross-repo workflow **a second shape of file** — it
may not carry §7.2's standard `working_dir` line, so it cannot run local steps
in its own directory. There is a cleaner fix, and it is measured.

The A4 collision is purely a **name** collision. Once the names differ,
`with.params` works exactly as upstream documents it. One parent, one run:

```yaml
# t2_parent.yaml — the parent names its OWN directory with a second variable
params:
  - DEVMAN_SELF_DIR: /tmp/devman-a2/projA
working_dir: ${DEVMAN_SELF_DIR}
steps:
  - id: self
    run: echo "PARENT cwd=$(pwd)"
  - id: child_default                       # child keeps its own project
    action: dag.run
    with: {dag: a4_child_diag}
  - id: child_directed                      # parent directs this one
    action: dag.run
    with:
      dag: a4_child_diag
      params: {DEVMAN_PROJECT_DIR: /tmp/devman-a2/projA}
```

**Command:**

```
env -u DEVMAN_PROJECT_DIR dagu start t2_parent
```

**Evidence:**

```
PARENT cwd=/tmp/devman-a2/projA                                    <- parent's own dir works
params=DEVMAN_PROJECT_DIR=/tmp/devman-a2/projB   cwd=.../projB     <- undirected child kept its own
params=DEVMAN_PROJECT_DIR=/tmp/devman-a2/projA   cwd=.../projA     <- directed child obeyed the parent
Result: Succeeded
```

All three behaviours at once. **This restores `with.params` as a working way for
a parent to direct a child**, which A4 had recorded as broken — it is not broken,
it is shadowed.

**Recommended over A4's rule:**

> `DEVMAN_PROJECT_DIR` names **the project a run targets**, and is set only by
> whatever triggers the run. A workflow that triggers other workflows must not
> hold that name itself; if it needs its own directory for local steps, it uses
> a second name. A parent directs a child with `with.params`.

This keeps the contract at one name for the common case, keeps cross-repo
workflows ordinary files, and gains the ability to point a child at a different
project — which §11's "synchronized releases" and "coordinated migrations" will
want.

### Charter impact

**changes §11** — same section as A4, better rule. Supersedes A4's "must not
define" wording with the role-based rule above.

**No change to the §7.2 / §9.2 conclusions.** The dual mechanism is forced by
the decision to have queues at all, and the three variable-free alternatives are
each closed off by a measurement.

### Still open, and deliberately not explored

- **Triggering over Dagu's HTTP API rather than the CLI.** That is D7's
  question, and the answer may differ from the CLI's on both env and params.

---

## A7 — How many Dagu instances, and what that does and does not fix

An earlier draft of A6 claimed that "one instance per user rather than per
machine" would remove A3's split between `log_dir` and `working_dir`. **That was
wrong on two counts, and both are now measured.** This section replaces it.

**Tested:** dagu 2.15.0, on 2026-08-21, with a second instance on
`DAGU_HOME=/tmp/devman-a2/dagu2`.

### Which process resolves which field

This is the fact everything else follows from:

| field | resolved by | so its value comes from |
|---|---|---|
| `log_dir`, `artifacts.dir` | the process that **enqueues** | the **trigger's** environment |
| `working_dir` | the process that **executes** | the **daemon's** environment, or params |

**Proof, second half.** A daemon started with the variable in *its own*
environment, then triggered from a shell with the variable unset and no params:

```
DAGU_HOME=$H2 DEVMAN_PROJECT_DIR=/tmp/devman-a2/projB dagu start-all &
env -u DEVMAN_PROJECT_DIR DAGU_HOME=$H2 dagu enqueue p2_wdonly
```

```
cwd=/tmp/devman-a2/projB
Result: Succeeded
```

The daemon supplied `working_dir`. **No param was needed.**

**Proof, first half.** The same daemon, same clean trigger, but with `log_dir`
also written as `${DEVMAN_PROJECT_DIR}/...`:

```
├─log: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/p1_noparams/...
Result: Failed
```

```
level=ERROR msg="Failed to execute DAG" queue=exclusive err="...
  failed to create/open log file ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/...:
  no such file or directory"
```

**The daemon having the variable did not help.** The literal string was baked in
at enqueue time by the CLI, stored in the queue entry, and the daemon merely
opened what it was handed — and failed.

### What follows

**"Per user" is not a distinct option for a single-user machine.** One user
means one daemon means one environment, exactly as "per machine" does. It
changes nothing about A2 or A3.

**"Per project" is the option that would change something — and it changes
almost nothing.** A daemon per project would supply `working_dir` from its own
environment, so the trigger could drop the param. It would **not** fix
`log_dir`, because that is resolved by the trigger no matter how many daemons
exist. So the trade is:

| | machine-wide instance | per-project instance |
|---|---|---|
| trigger exports `DEVMAN_PROJECT_DIR` | required (for `log_dir`) | **still required** |
| trigger passes it as a param | required (for `working_dir`) | not required |
| daemons to supervise | 1 | one per project |
| ports to allocate | 1 set | one set per project |

The measured cost of a second instance is not only process count. Two instances
collide on fixed ports until told otherwise:

```
Error: failed to initialize coordinator: failed to create listener on
  127.0.0.1:50055: listen tcp 127.0.0.1:50055: bind: address already in use
```

A per-project instance needs `port`, `coordinator.port`,
`coordinator.health_port`, and `scheduler.port` assigned per project — four
allocations each — and it would break §7.1 outright, because a queue's
concurrency limit is per instance. Ten project daemons each holding
`exclusive: max_concurrency 1` give ten concurrent "exclusive" runs, not one.
**Success criterion 12 cannot hold under per-project instances.**

**Conclusion: no instance arrangement removes the dual mechanism.** §4's
one-per-machine choice stands, and it stands for a stronger reason than the
charter gives — machine-wide queues are only meaningful in a machine-wide
instance.

### What "per user" *does* decide, and it is worth deciding on purpose

The per-machine / per-user question is real, but it is about **which identity
the service runs as**, not about environments or A3. It matters because §6
routes every step through `devenv tasks run`, which needs a developer's own
context:

| runs as | reaches |
|---|---|
| a system service (root or a `dagu` user) | needs explicit plumbing for `$HOME`, the Nix profile, `~/.cache`, git credentials, SSH agent, direnv |
| a systemd **user** service | all of the above, already correct, because it is you |

A workflow step that runs `devenv tasks run test` in a repository under
`~/Documents/Projects/` wants the second. It also makes §9.4's secret injection
a user-scope problem rather than a system-scope one, and puts `DAGU_HOME` at
`~/.local/share/dagu` next to §9.2's registry rather than in `/var/lib`.

**Charter impact:** **changes §4.** §4 says "One Dagu instance per machine or
user" and leaves the choice open. Investigation A gives a reason to close it:
the module should define a **systemd user service**, because every workflow step
runs a developer's own `devenv` in a developer's own checkout. Say so, and drop
"or user" as an undecided alternative — it is the decision, not an option.

This is a §4 wording change with a real consequence for Investigation B, which
builds `nixosModules.default`: the module writes `systemd.user.services.dagu`,
not `systemd.services.dagu`.

---
---

# Investigation E — the Dagu capability sweep

Answers to `INVESTIGATION_E_PROMPT.md`. The question is the inverse of
Investigation A's: **what does Dagu already do that the charter is planning to
build itself?**

Same instance, same version. `E0` above predates this investigation and is
unrelated to the `E1`–`E8` numbering the prompt asks for.

**Version under test:** Dagu **2.15.0**.
**Instance:** `DAGU_HOME=<repo>/.devenv/state/dagu`, the `devenv up -d` daemon.
**Date:** 2026-08-21.
**Source read alongside the runs:** `.devman/context/.vend/dagu`, tag `v2.15.0`.

---

## E1 — Does Dagu already break the write-loop?

**Bucket:** **replaces.**

**Answer:** **yes, twice over.** Dagu skips work whose inputs are unchanged by
two independent mechanisms, both content-hash based, and both honoured under
`enqueue`. §8.1's `generation.json` is a token Dagu already keeps.

**Tested:** dagu 2.15.0, on 2026-08-21.

### Mechanism 1 — `type: build` skips the step and does not touch the output

A build step declares `inputs:` and `outputs:`. Dagu hashes the recipe, the
input contents, and the current output, and reuses a matching materialization.

```yaml
# e1_build.yaml
type: build
working_dir: /tmp/devman-e/e1
steps:
  - id: compile
    inputs:
      - name: source
        path: source.c
    outputs:
      - name: binary
        path: app.bin
    run: |
      echo "COMPILE RAN" >> /tmp/devman-e/e1/compile.trace
      cat "${inputs.source}" > "${outputs.binary}"
```

**Command:**

```
dagu start e1_build            # twice, with no edit in between
stat -c 'app.bin inode=%i mtime=%.9Y' app.bin
```

**Evidence:**

```
run 1  └─build: execute (manifest_missing) - no prior successful materialization
       app.bin inode=26954567 mtime=1787367362.568694973
run 2  └─build: reuse (matched) - recipe, inputs, and output match the committed
                manifest; producer: e1_build:034BKurWdFotyilj5Z7x4X
       app.bin inode=26954567 mtime=1787367362.568694973
```

**Same inode, same nanosecond mtime.** On reuse Dagu does not write the output
at all. **A watcher sees no event, so the loop terminates without any token.**
Editing the input restores execution:

```
└─build: execute (input_changed) - declared input content changed
```

**It survives `enqueue`.** Three consecutive `dagu enqueue e1_build` runs:

```
enqueue 1  └─build: execute (recipe_changed) - the step recipe changed
enqueue 2  └─build: reuse (matched) ...
enqueue 3  └─build: reuse (matched) ...
```

**But reuse is per execution path.** The first `enqueue` after a local `start`
re-executes with `recipe_changed`, and the first `start` after an `enqueue` does
the same. Each switch costs exactly one re-execution, then reuse resumes. An
unrelated variable in the caller's environment does **not** invalidate it —
`env_passthrough` filters it out before it reaches the recipe digest. So a plane
that always triggers the same way (A6: always `enqueue`) gets stable reuse.

**Dagu's token, on disk.** `$DAGU_HOME/data/materializations/manifests/<key>.json`:

```json
{"schemaVersion":1,"dagName":"e1_build","stepId":"compile",
 "recipeDigest":"sha256:db44f0e5...","fingerprint":"sha256:1f49f9b0...",
 "inputs":[{"name":"source","path":"/tmp/devman-e/e1/source.c","size":22,
            "digest":"sha256:3970d2e7..."}],
 "output":{"name":"binary","path":"/tmp/devman-e/e1/app.bin","size":22,
           "digest":"sha256:3970d2e7..."},
 "producerRun":{"name":"e1_build","id":"034BKw0N5EphIzm0si0Fpx"}}
```

That is §8.1's `generation.json`, field for field — "a note saying *I did
that*". It is machine-side under `data_dir`, not repo-side.

### The one thing `type: build` cannot express — an in-place rewrite

§8.1's example is a formatter that rewrites `foo.py`. A build step may not
declare one path as both input and output.

**Command:**

```
dagu validate $DAGS/e1_inplace.yaml   # input path == output path == foo.py
dagu start e1_inplace
```

**Evidence:**

```
validate exit=0                       <- validate does NOT catch it
Error: failed to execute the dag-run e1_inplace (...): step format declares the
  same path as input and output: /tmp/devman-e/e1/foo.py
```

A fourth documentation/behaviour gap: `validate` passes a DAG the runtime
rejects. So `type: build` covers `source → artifact`, and not `format in place`.

### Mechanism 2 — `preconditions`, which do cover the in-place case

A DAG-level or step-level precondition runs a command before the work. Command
form is real shell, including `$()`.

```yaml
# e1_hashskip_param.yaml — the devman shape: one shared file, per-project param
params:
  - DEVMAN_PROJECT_DIR: /tmp/devman-e/projA
working_dir: ${DEVMAN_PROJECT_DIR}
preconditions:
  - condition: 'test "$(sha256sum foo.py | cut -d" " -f1)" != "$(cat .lasthash 2>/dev/null)"'
steps:
  - id: fmt
    run: |
      echo "RAN in $(pwd)" >> hash.trace
      sha256sum foo.py | cut -d' ' -f1 > .lasthash
```

**Command:**

```
for i in 1 2; do for P in projA projB; do
  dagu enqueue e1_hashskip_param -- DEVMAN_PROJECT_DIR=/tmp/devman-e/$P
done; done
```

**Evidence:**

```
pass1 projA -> Result: Succeeded
pass1 projB -> Result: Succeeded
pass2 projA -> Result: Aborted      <- unchanged, skipped
pass2 projB -> Result: Aborted
projA: RAN in /tmp/devman-e/projA
projB: RAN in /tmp/devman-e/projB
```

**The precondition is evaluated by the daemon in the param-supplied
`working_dir`**, so one shared group file skips correctly per project. This is
the exact configuration §7.2 mandates, and it works.

Both properties §8.1 asks for, measured on the single-project file:

```
run 1  no stored hash        Result: Succeeded   trace=1
run 2  unchanged (start)     Result: Aborted     trace=1   <- own write does not re-fire
run 3  unchanged (enqueue)   Result: Aborted     trace=1
run 4  user edits foo.py     Result: Succeeded   trace=2   <- your own edit still fires
```

Run 4 is the property §8.1 chose hashes for over a suppression window. It holds.

### Use the step-level form, not the DAG-level form

A DAG-level precondition that is not met records the run as **Aborted**, which
is `ir.Status` 3 — the same code a cancelled run gets. There is no DAG-level
"skipped" status:

```go
// internal/ir/status.go
NotStarted Status = iota   // 0
Running                    // 1
Failed                     // 2
Aborted                    // 3
Succeeded                  // 4
```

A **step-level** precondition is different. `NodeStatus` does have `NodeSkipped
= 5`:

```
run 2  └─fmt [skipped]
       Result: Succeeded
       dag status: 4   nodes: [('fmt', 5)]
```

**Step-level gives `Succeeded` with the step marked skipped; DAG-level gives
`Aborted`.** A plane built on the DAG-level form would fill its history with
runs that look like failures. Use the step-level form.

The reason for the skip is machine-readable either way. The run record names the
condition that was not met:

```json
"preconditions":[{"condition":"test \"$(sha256sum foo.py ...)\" != ...",
                  "error":"condition was not met: exit status 1"}]
```

### `skip_if_successful` is not this, and is a dead end

The schema says it skips a run when the DAG already succeeded since the last
scheduled time, and that "Manual triggers always run regardless".

**Command:**

```
# e1_skipsucc.yaml: schedule "*/5 * * * *", skip_if_successful: true
dagu start e1_skipsucc; dagu start e1_skipsucc; dagu enqueue e1_skipsucc
```

**Evidence:**

```
Result: Succeeded
Result: Succeeded
Result: Succeeded
trace=3          <- never skipped
```

It governs the scheduler only, and neither `start` nor `enqueue` is suppressed.
It is also time-window based, which is what §8.1 explicitly rejected. Closed.

### Charter impact

**deletes §8.1.**

§8.1 is titled "Loop-breaking is plane infrastructure" and makes the plane own a
token format, a writer, and a trigger-side check. **Dagu owns all three
already.** The charter should drop:

- `generation.json` as a plane-defined artifact — Dagu's build manifest is the
  same object, and the precondition form needs only a file whose name and format
  are the workflow's own business.
- the `generation.json` line in **§9.2**'s `.devman/.runs/` layout.
- "the plane owns the fix once, so no repo implements it again" as *machinery*.
  It stays true as *content*: a group workflow that writes files carries the
  precondition, and every repo taking that group inherits it (§7.2). That is the
  same guarantee, delivered by the mechanism the charter already chose for
  everything else.

What survives §8.1, and is worth keeping as one paragraph of authoring guidance:
the rule that a workflow writing inside its own trigger's watch scope must
declare that, and the reason hashes beat a timer.

**Three costs to record, none of which restore the section:**

1. **The check moved from the trigger to the run.** §8.1 skips before anything
   is enqueued. Dagu skips after. A skipped run still consumes a queue slot and
   writes a history record, so a chattering watcher on `queue: exclusive`
   (`max_concurrency: 1`) can still queue behind itself. If that matters, it is a
   trigger-side debounce question, not a loop-breaking one.
2. **`type: build` cannot format in place**, and `validate` does not say so.
3. **Dagu's build manifest is machine-side**, under `data_dir`. §9.3 already
   requires that everything there be reconstructable, and it is — a lost manifest
   causes one re-execution, not a wrong result.

**One sentence, and then stopping as §1 requires:** `devman doctor` could read
`data/materializations/manifests/` to explain why a workflow did no work. That is
a reconciliation decision, not this session's.

---

## E2 — What actually invokes Dagu?

**Bucket:** **answers** — §8's open mechanism, and D7.

**Answer:** **six surfaces, and only one of them can serve devman.** Dagu has a
rich trigger surface, and every HTTP-side member of it is queue-governed and
accepts parameters. But **every HTTP surface resolves `log_dir` in the server
process**, so none of them can put a run's logs under the project that triggered
it. §8's trigger must stay a **local process that runs `dagu enqueue`**.

**Tested:** dagu 2.15.0, on 2026-08-21, against a second instance on port 8090
with `auth.mode: builtin` (the first instance runs `auth.mode: none`).

### The surfaces

| Surface | Queue-governed | Arbitrary params | Notes |
|---|---|---|---|
| `dagu start` | **no** (A6) | yes | local process |
| `dagu enqueue` | **yes** | yes | local process |
| `POST /api/v1/dags/{f}/start` | no | yes | server process |
| `POST /api/v1/dags/{f}/start-sync` | no | yes | server process, blocks |
| `POST /api/v1/dags/{f}/enqueue` | **yes** | yes | server process |
| `POST /api/v1/webhooks/{f}` | **yes** | **no** | server process, token/HMAC |
| MCP `dagu_execute` at `/mcp` | **yes** (`action=enqueue`) | yes | server process |
| `schedule:` | **yes** | defaults only | Dagu's own cron |

The HTTP `enqueue` body carries more than the CLI does:

```
params  dagRunId  dagName  profile  queue  singleton  noReuse  labels  tags
```

`queue` overrides the DAG's own queue at trigger time. `singleton` and `noReuse`
have **no CLI equivalent** — `dagu enqueue --help` lists `--params`, `--queue`,
`--profile`, `--labels`, `--no-reuse`, `--run-id`, `--name`, `--trigger-type`,
and `--default-working-dir`, and no `--singleton`.

### The finding that decides §8 — HTTP cannot write logs to the project

A7 established that `log_dir` is resolved by **the process that enqueues**, from
that process's environment. Over HTTP that process is the server, and a server
has one environment. Measured with the exact devman shape:

```yaml
# e2_probe.yaml
params:
  - DEVMAN_PROJECT_DIR: /tmp/devman-e/projA
working_dir: ${DEVMAN_PROJECT_DIR}
log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs
queue: exclusive
```

**Command:**

```
curl -s -X POST 'http://127.0.0.1:8080/api/v1/dags/e2_probe/enqueue' \
  -H 'Content-Type: application/json' \
  -d '{"params":"DEVMAN_PROJECT_DIR=/tmp/devman-e/projB"}'
```

**Evidence:**

```
{"dagRunId":"034BL5NBzkU7ClyfTYLFr6"}

├─log: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/e2_probe/dag-run_.../dag-run_....log
└─probe (0s) [succeeded]
Result: Succeeded

$ cat '<repo>/${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/e2_probe/.../probe....out'
cwd=/tmp/devman-e/projB           <- working_dir DID resolve, from the param
$ git status --porcelain
?? ${DEVMAN_PROJECT_DIR}/         <- and the log path did not
```

**`working_dir` resolved and `log_dir` did not, in the same run.** Dagu created
a directory literally named `${DEVMAN_PROJECT_DIR}` inside the daemon's working
directory — this repository — and dirtied the tree. This is exactly the A3
symptom, and over HTTP it is **not avoidable**: there is no per-request
environment to supply the variable from.

So the choice is a real one, and it is forced:

- **local `dagu enqueue`** — logs land in the project (A3 measured it), the
  trigger exports the variable and passes the param.
- **any HTTP surface** — logs land in one machine-wide place, and §9.2's
  "run output stays with the checkout that produced it" is lost.

### Webhooks — real, queue-governed, and narrow

**They require `auth.mode: builtin`.** With the instance's `auth.mode: none`,
every webhook endpoint returns 401:

```
$ curl -X POST 'http://127.0.0.1:8080/api/v1/dags/e2_probe/webhook' -d '{}'
{"code":"unauthorized","message":"Webhook management is not enabled"}
```

The gate is the store, not the role — `internal/service/frontend/api/v1/webhooks.go`:

```go
if a.authService == nil || !a.authService.HasWebhookStore() {
    return &Error{ ... Message: "Webhook management is not enabled" ... }
}
```

and the webhook store is only constructed on the builtin-auth path
(`internal/service/frontend/file/stores.go`). So webhooks cost the plane a user
store, a token secret, and an encryption key.

**They are queue-governed.** Two webhook calls fired concurrently at a DAG with
`queue: exclusive` (`max_concurrency: 1`), each sleeping 4 seconds:

```
START 1787367943.820990798    END 1787367947.837747818
START 1787367949.811342117    END 1787367953.823032498     <- starts 2.0s after the first ends
```

Strictly serialized. **Unlike `dagu start`, a webhook run goes through the
queue** — the API description says so ("The DAG run is enqueued and the endpoint
returns immediately") and the run confirms it.

**They cannot carry arbitrary parameters.** `WebhookRequest` has two fields:

```yaml
WebhookRequest:
  properties:
    dagRunId:   # optional idempotency key
    payload:    # arbitrary JSON, passed as WEBHOOK_PAYLOAD
```

The payload does arrive as a **parameter**, not only an environment variable —
`buildWebhookRuntimeParams` builds the string `WEBHOOK_PAYLOAD="..."
WEBHOOK_HEADERS="..."`, and the run history shows it in the `PARAMS` column:

```
e2_hook  01a0276e-...  Succeeded  4s  WEBHOOK_PAYLOAD={"n":1,"project":"/tm...
```

But the names are fixed. A webhook cannot set `DEVMAN_PROJECT_DIR`.

**And the payload cannot be turned into a path.** A2 recorded the schema's claim
that interpolation accepts "shell-style expressions and command substitution".
For `working_dir` that is **false**:

```yaml
working_dir: $(cat /tmp/devman-e/wdfile)      # file holds /tmp/devman-e/projB
```

```
cwd=<...>/.vend/dagu/$(cat /tmp/devman-e/wdfile)
```

Backticks behave the same way:

```yaml
working_dir: "`cat /tmp/devman-e/wdfile`"
```

```
cwd=/tmp/devman-e/dagu2/dags/`cat /tmp/devman-e/wdfile`
```

Both are kept literal, and Dagu creates the directory. **A fifth
documentation/behaviour gap.** So a webhook payload cannot be parsed into
`working_dir`, because nothing runs before the working directory is resolved.

### MCP is a full trigger surface

The server logs `MCP route configured path=/mcp` at startup. Three tools, after
the standard initialize handshake:

```
- dagu_change  : Validate and optionally apply DAG definition or Markdown Wiki changes
- dagu_execute : Run control entry point. action=start or enqueue ... retry and stop
- dagu_read    : Read DAG specs, Wiki pages, DAG-run details, logs, list views
```

`dagu_execute` takes the full enqueue vocabulary — `params` as a JSON string,
`queue`, `singleton`, `noReuse`, `labels`, plus `spec` for an **inline DAG**
never written to `dags_dir`. It is the HTTP path, so the `log_dir` constraint
applies unchanged.

### `singleton` is the debounce E1 said was missing

E1 noted that a Dagu-side skip still consumes a queue slot. `singleton` fixes
that at the trigger. Three enqueues of a 4-second `exclusive` DAG, 0.3s apart:

```
{"dagRunId":"034BLCz8b2uCSP0WbRN4NT"}                                  http=200
{"code":"already_exists","message":"DAG e2_hook is already in queue"}  http=409
{"code":"already_exists","message":"DAG e2_hook is already running"}   http=409
```

One run. It distinguishes "already in queue" from "already running". **It is not
available from the CLI**, so a local trigger cannot use it without going through
the server — and going through the server costs the log path.

### Charter impact

**changes §8**, and it closes **D7**.

§8 draws `filesystem change → watchexec → Dagu` and `commit / push → hook →
Dagu` and leaves the arrow undefined. Define it:

> **A trigger is a local process that runs `dagu enqueue`**, with
> `DEVMAN_PROJECT_DIR` exported in its environment and passed as a parameter
> (A3, A6). Dagu's HTTP, webhook, and MCP surfaces are real and queue-governed,
> but they resolve `log_dir` in the server process, so a run triggered through
> them cannot write its logs into the project that triggered it.

Two consequences for §8's table, which currently says only "watchexec, hooks:
detect that something happened":

- The trigger layer is **not** a thin detector. It resolves the project, exports
  a variable, passes a parameter, and — if debouncing is wanted — implements it,
  because `singleton` is HTTP-only. That is §10's `devman run` doing the work,
  which is consistent with §10's "`devman run` triggers a workflow", but §8
  should stop implying the detector talks to Dagu directly.
- **Triggers stay plane machinery.** They are not group content. The prompt asked
  which; the answer is machinery, because the mechanism is fixed by A3 and cannot
  vary per group.

**One sentence, and then stopping as §1 requires:** if the plane ever wants
webhook or MCP triggering (a CI push, an agent), §9.2 would have to give up
per-project logs for those runs, or accept them under the machine-wide default.
That is a reconciliation decision.

---

## E3 — Whose job are secrets?

**Bucket:** **replaces**, for half of §9.4.

**Answer:** **Dagu resolves secrets itself.** A DAG names a secret with a
provider and a key; Dagu resolves it at run time, injects it as an environment
variable, **masks it in logs**, and **fails the run loudly if it is missing**.
The `file` provider reads exactly what a NixOS secret manager produces. §9.4's
injection path is not needed for the file case, and its "never carries a value"
rule becomes Dagu's own field rather than a devman convention.

**Tested:** dagu 2.15.0, on 2026-08-21.

### The schema

`dag.schema.json`, `secretRef`. A DAG-level `secrets:` array, one entry per
variable:

```json
"name":     {"pattern": "^[A-Za-z_][A-Za-z0-9_]*$", "not": {"pattern": "^DAGU_"},
             "description": "Environment variable name that will receive the secret value."},
"provider": {"description": "Secret provider identifier (e.g., env, file, custom providers)."},
"key":      {"description": "Provider-specific key or identifier used to look up the secret."},
"ref":      {"description": "Workspace-local registry reference for a team-managed secret."},
"options":  {"description": "Provider-specific configuration options."}
```

> "The resolved value is injected as an environment variable **and masked in
> logs/output**."

An entry is either `ref` alone or `provider` + `key`. `config.schema.json` adds
instance-level client defaults for `vault`, `kubernetes`, `aws`, `gcp`, `azure`,
and `alibaba` — addresses, regions, tokens. There is **no instance-level default
for `env` or `file`**, which are the two that need none.

### It works, and the value is real

```yaml
# e3_secrets2.yaml
secrets:
  - name: FROM_ENV
    provider: env
    key: E3_RAW_TOKEN
  - name: FROM_FILE
    provider: file
    key: /tmp/devman-e/e3/token.txt
steps:
  - id: show
    run: |
      printf '%s' "$FROM_ENV"  > /tmp/devman-e/e3/out_env.txt
      printf '%s' "$FROM_FILE" > /tmp/devman-e/e3/out_file.txt
      echo "lengths: env=${#FROM_ENV} file=${#FROM_FILE}"
```

**Command:**

```
E3_RAW_TOKEN=s3cr3t-from-env dagu start e3_secrets2
```

**Evidence:**

```
lengths: env=15 file=16
out_env=[s3cr3t-from-env]  out_file=[s3cr3t-from-file]
```

### Masking is real, and it is the capability §9.4 does not have

The same values printed straight to stdout:

```
FROM_ENV=[*******]
FROM_FILE=[*******]
```

The step receives the true value — it wrote the true value to a file in the same
run — and the log holds `*******`. §9.4 currently injects secrets as ordinary
environment variables, which any step can echo into a log that lands in
`<repo>/.devman/.runs/` and, from there, into a screenshot or a bug report.
**Dagu masks them; a plain environment variable is not masked.**

### `provider: env` bypasses the `env_passthrough` allowlist

A2 found that `DEVMAN_*` variables are filtered out of a DAG unless the instance
config allowlists them. `E3_RAW_TOKEN` is **not** allowlisted. In the run above:

```
FROM_ENV=[*******]              <- resolved
RAW_passthrough=[<unset>]       <- the same variable, filtered out
```

**The `secrets:` block is a second, explicit passthrough channel**, declared per
DAG instead of per instance. A workflow can reach a variable the allowlist hides.

### A missing secret is a hard failure — unlike a missing path variable

This is the sharpest contrast with A2 and A3, where an unresolved `${VAR}`
silently became a literal directory name.

**Command:**

```
E3_RAW_TOKEN=s3cr3t-from-env dagu enqueue e3_secrets2     # the DAEMON lacks the variable
```

**Evidence:**

```
Result: Failed

level=ERROR msg="Failed to initialize DAG execution" err="failed to resolve
  secrets: failed to resolve secret \"FROM_ENV\" from provider \"env\":
  environment variable \"E3_RAW_TOKEN\" is not set"
```

The run fails before any step, and names the secret and the provider.

It also settles which process resolves a secret. **Secrets are resolved by the
process that executes**, like `working_dir` and unlike `log_dir` (A7). Under
`enqueue` that is the daemon, so `provider: env` reads the **daemon's**
environment — one value per instance. For a *secret* that is correct, because a
machine's `GITHUB_TOKEN` genuinely is one value per machine. A2's "one value per
instance" objection does not apply here.

### `provider: file` reads what a NixOS secret manager writes

**Command:**

```
install -m 0400 token.txt token0400.txt     # what agenix / sops-nix produce
# e3_file.yaml: provider file, key /tmp/devman-e/e3/token0400.txt
dagu enqueue e3_file
```

**Evidence:**

```
len=16 value_in_log=*******
Result: Succeeded
written value=[s3cr3t-from-file]
```

A 0400 file read by the daemon, masked in the log, delivered whole to the step.
**The NixOS module does not have to inject anything.** It has to make the file
exist, which is what a secret manager already does.

### Charter impact

**changes §9.4.** The section reads:

> The NixOS module reads values from the machine's secret manager and injects
> them into Dagu's environment; Dagu passes them to devenv, devenv to the task.

Both halves are now optional, and the choice is real:

| | what the module does | what the workflow says | portable across machines |
|---|---|---|---|
| `provider: env` | sets the variable in the Dagu **user service** environment (A7) | `provider: env`, `key: GITHUB_TOKEN` | **yes** |
| `provider: file` | nothing — the secret manager already wrote the file | `provider: file`, `key: /run/agenix/github-token` | **no** — the path is machine-specific |

**What §9.4 should keep:** "A workflow references a symbolic name and never
carries a value." That rule is now Dagu's own field, not a devman convention,
which is the same win §7.1 claims for `queue:`.

**What §9.4 should add:** Dagu masks a resolved secret in logs and output, and
fails the run when one is missing. Neither is true of a plain injected
environment variable, so `secrets:` is strictly better than the current wording
even when the module still sets the value.

**What §9.4 should decide:** `provider: env` keeps §9.4's injection path and
stays portable. `provider: file` deletes the injection path but writes a
machine-specific absolute path into a workflow, which collides with §9.1 ("never
commit a developer's absolute path") and with §7.2's one-file-serves-every-repo
claim. **`provider: env` is the one that fits the charter as written**; the
module's job shrinks from "inject into Dagu's environment" to "set these
variables on the user service", which is the same thing said more precisely.

**One sentence, and then stopping as §1 requires:** the `ref:` form points at a
workspace-local managed secret registry, which would remove the path problem
from `provider: file` — it is not exercised here and is worth one look during
reconciliation. See also E4: if a `secrets:` block can live in `base.yaml`, the
machine can declare the whole vocabulary once.

---

## E4 — How much can the machine set once?

**Bucket:** **replaces** — most of what §7.2's example workflow contains.

**Answer:** **all of it.** `working_dir`, `log_dir`, `queue`, `env`, retention,
`secrets`, step `defaults`, and `preconditions` all inherit from `base.yaml`,
and the two interpolations keep the sources A3 measured — `log_dir` from the
trigger's environment, `working_dir` from the parameter. A group workflow file
reduces to `steps:`.

**Tested:** dagu 2.15.0, on 2026-08-21. `base.yaml` was replaced for the
measurement and restored afterwards.

### The base config

`config.schema.json`: `base_config` is one path, and the instance resolves it to
`$DAGU_HOME/base.yaml`. The shipped file states the rule at the top:

```
# Values defined here are inherited by ALL DAGs.
# Individual DAGs can override any setting.
# Environment variables (env:) are additive — DAG env vars append to these.
```

It ships `type`, `overlap_policy`, `log_output`, `hist_retention_days`,
`max_clean_up_time_sec`, `max_active_steps`, `max_output_size`, and
`catchup_window` active, and documents `working_dir`, `log_dir`, `queue`, `env`,
`dotenv`, `defaults`, `secrets`, `handler_on`, `smtp`, `otel`, and `run_config`
as commented examples.

### The measurement — a two-line workflow serving two projects

`base.yaml`, the machine's file:

```yaml
type: graph
log_output: separate
hist_retention_days: 7
max_active_steps: 10
working_dir: ${DEVMAN_PROJECT_DIR}
log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs
queue: exclusive
env:
  - DEVMAN_FROM_BASE: base-was-here
defaults:
  timeout_sec: 300
secrets:
  - name: GITHUB_TOKEN
    provider: file
    key: /tmp/devman-e/e3/token.txt
```

`e4_minimal.yaml`, the whole workflow:

```yaml
steps:
  - id: probe
    run: echo "cwd=$(pwd)"
```

**Command:**

```
for P in projA projB; do
  DEVMAN_PROJECT_DIR=/tmp/devman-e/$P \
    dagu enqueue e4_minimal -- DEVMAN_PROJECT_DIR=/tmp/devman-e/$P
done
```

**Evidence:**

```
├─log: /tmp/devman-e/projA/.devman/.runs/logs/e4_minimal/dag-run_.../dag-run_....log
      cwd=/tmp/devman-e/projA
├─log: /tmp/devman-e/projB/.devman/.runs/logs/e4_minimal/dag-run_.../dag-run_....log
      cwd=/tmp/devman-e/projB
```

**No `queue`, no `working_dir`, no `log_dir`, no `params`, no `env` in the
workflow**, and both projects got their own working directory and their own log
tree. The §12.1 spike passes with the workflow file holding nothing but steps.

### Field by field

| Field | Inherits from `base.yaml` | Merge rule | Notes |
|---|---|---|---|
| `working_dir` | **yes** | DAG replaces | `${DEVMAN_PROJECT_DIR}` resolves from the **param** |
| `log_dir` | **yes** | DAG replaces | resolves from the **trigger's environment** |
| `queue` | **yes** | DAG replaces | and it is enforced — see below |
| `env` | **yes** | **additive** | base and DAG values both present |
| `hist_retention_days` | **yes** | DAG replaces | §16's retention question |
| `secrets` | **yes** | DAG replaces | see E3 |
| `defaults` (step settings) | **yes** | DAG replaces | `timeout_sec`, `retry_policy`, `continue_on`, `repeat_policy` |
| `preconditions` | **yes** | **DAG replaces** | not additive — see below |

**A queue set in base is a real queue.** Three DAGs, none naming a queue, with
`queue: exclusive` (`max_concurrency: 1`) in `base.yaml`:

```
START p 1787368363.203159418   END p 1787368367.213481638
START q 1787368369.213933262   END q 1787368373.224388492
START r 1787368375.193132198   END r 1787368379.202318046
```

Strictly serialized. **Success criterion 12 can be satisfied without a workflow
naming a queue at all.**

**Overrides work, and `env` is additive.** A DAG setting `queue: light`,
`working_dir: /tmp/devman-e/projB`, and its own `env:`:

```
├─log: /tmp/devman-e/projA/.devman/.runs/logs/e4_override/...   <- base's log_dir
      cwd=/tmp/devman-e/projB                                   <- the DAG's working_dir
      from_base=base-was-here  from_dag=dag-was-here            <- both env values
```

**`preconditions` are replaced, not merged.** With `condition: "false"` in
`base.yaml`:

```
DAG with no preconditions      Result: Aborted     <- base's applied
DAG with condition: "true"     Result: Succeeded   <- base's was replaced, not ANDed
```

So a base-level precondition is a machine-wide gate that any workflow silently
switches off by declaring one of its own. E1's loop-breaking precondition
therefore belongs in the workflow, not in `base.yaml`.

### Charter impact

**changes §7.2, and shortens §7.1.**

§7.2's example workflow is:

```yaml
queue: light
workingDir: ${DEVMAN_PROJECT_DIR}
steps: ...
```

A2 already corrected the spelling. E4 removes both remaining lines. **The
portable part of every group workflow is machine state, not file content**, so
§7.2's "one group file, unedited, serves every repo" gets cheaper rather than
harder: there is less in the file that could be wrong.

Three specific edits:

1. **`working_dir` and `log_dir` move to `base.yaml`.** The machine module writes
   them once. A workflow that needs a different directory still overrides.
2. **§7.1's "queue names are the entire shared vocabulary" is already false, and
   E4 makes the true list visible.** The machine and every workflow must agree
   on: the queue names, **the variable name `DEVMAN_PROJECT_DIR`** (A2), and
   **the `.devman/.runs/` path shape** (A3). E4's contribution is that all three
   can be stated in one machine-written file instead of repeated in every
   workflow — which is the outcome §7.1 wanted, reached by a different route.
3. **A default queue is possible.** §7.1 says "a workflow names one". It may now
   say "a workflow names one when it wants something other than the default",
   which makes success criterion 3 ("a repo may take no groups at all") cheaper
   and removes A1's silent-typo hazard for every workflow that names nothing.

**And it settles part of §16.** Retention — "Lean: 7 days for logs and
artifacts, keep `metadata.json` indefinitely" — has a Dagu field,
`hist_retention_days`, settable once in `base.yaml`. It governs Dagu's **run
history**, not the log files under `log_dir`, so the log half of §16's lean still
needs an owner.

**One sentence, and then stopping as §1 requires:** because `base.yaml` is one
machine-wide file, a `secrets:` block placed there grants every workflow on the
machine every secret — which is the cost of E3's tidiest answer, and a
reconciliation decision.

---

## E5 — Can Dagu diagnose a wedged plane?

**Bucket:** **answers** — §15.3's one condition, and part of §10.

**Answer:** **a wedged queue explains itself; a failed-to-load DAG does not.**
Dagu's queue API states, per waiting item, why it is not running. `doctor` should
read it rather than reimplement it. But `dagu ls` lists a DAG that cannot load
with no indication, so `doctor` must run `dagu validate` per file. Zombie
detection exists with documented knobs, and I could not observe it firing.

**Tested:** dagu 2.15.0, on 2026-08-21.

### A stuck queue explains itself — read it, do not reimplement it

Four runs enqueued to `exclusive` (`max_concurrency: 1`), each sleeping 20s.

**Command:**

```
curl -s http://127.0.0.1:8080/api/v1/queues
curl -s http://127.0.0.1:8080/api/v1/queues/exclusive/items
```

**Evidence:**

```json
{"queues":[{"name":"exclusive","type":"global","maxConcurrency":1,
  "runningCount":1,"queuedCount":3,
  "running":[{"dagRunId":"e5run1","name":"e5_slow","statusLabel":"running",
              "queuedAt":"...23:17:12-04:00","startedAt":"...23:17:13-04:00",
              "triggerType":"manual","workerId":"local"}]}]}
```

```json
{"items":[{"dagRunId":"e5run2","name":"e5_slow","statusLabel":"queued",
  "conditions":[
    {"type":"Runnable","status":"False","reason":"MaxConcurrencyReached",
     "message":"The DAG-run cannot start because the queue active-run concurrency limit has been reached."},
    {"type":"ConcurrencyReady","status":"False","reason":"MaxConcurrencyReached",
     "message":"The queue active-run concurrency limit has been reached."}],
  "queuedAt":"...","triggerType":"manual"}]}
```

**Each waiting item carries a machine-readable reason and a human message.**
§15.3 requires that `devman doctor` diagnose a wedged plane. For the
shared-availability failure §15.3 actually names — one queue blocking every
repo — Dagu already produces the diagnosis, including which run is holding the
slot and since when.

`dagu ps` is the CLI view, and it names the queue:

```
DAG      RUN_ID  ATTEMPT  STARTED               GROUP      FRESH
e5_slow  e5run1  735166   2026-08-22T03:17:13Z  exclusive  yes
```

`GROUP` is the queue. `FRESH` is the process-liveness heartbeat.

Also available and read-only: `GET /health` (`{"status":"healthy","uptime":6057,
"version":"2.15.0"}`), `GET /metrics` (Prometheus text, including
`dagu_dag_run_duration_seconds` per DAG and `dagu_cache_entries_total`), and
`GET /audit`. The `audit`, `event_store`, and `monitoring` config blocks are
retention and interval settings only — `audit.retention_days` 7,
`event_store.retention_days` 1, `monitoring.interval` 5s — and all three default
to enabled.

### A DAG that failed to load is invisible to `ls`

**Command:**

```
# e5_broken.yaml carries a top-level `x-not-a-key`
dagu ls | grep e5_broken
dagu start e5_broken
dagu validate $DAGS/e5_broken.yaml
```

**Evidence:**

```
e5_broken                                  <- listed, no error column, no warning

Error: failed to load DAG from e5_broken: 'spec.dag' has invalid keys: x-not-a-key

Error: Validation failed for .../e5_broken.yaml
- 'spec.dag' has invalid keys: x-not-a-key
```

`dagu ls` has one column, `NAME`, and lists the file regardless. So **the
projection can contain a DAG that can never run, and nothing reports it until
someone triggers it.** `dagu validate` is the check, and its exit code is usable:

```
dagu validate <broken>  → exit 1, message on stderr
dagu validate <good>    → exit 0, prints nothing at all
```

**`devman doctor` should run `dagu validate` over every projected file.** That is
one exec per workflow, and it is the only way to see a load failure.

### `--show-unresolved` sees the A3 trap — but only in a spelling that breaks `log_dir`

`dagu validate --show-unresolved` reports references that had no value:

```
msg="${env.SOME_OPERATOR_VAR} was left unchanged because env.SOME_OPERATOR_VAR had
     no value when steps[0].run[0].cmd_with_args was evaluated." reason=unknown_env_binding
msg="${context.paths.artifacts_dir} was left unchanged ..." reason=namespace_unavailable
```

It reports the `${env.NAME}` and `${namespace.x}` forms. It reports **nothing**
for the bare `${NAME}` form, which is the form every A2/A3 example uses:

```
# e5_unres.yaml: working_dir ${DEVMAN_PROJECT_DIR}, run echo ${NOT_DEFINED_ANYWHERE}
$ env -u DEVMAN_PROJECT_DIR dagu validate --show-unresolved $DAGS/e5_unres.yaml
$ echo $?
0            <- silent
```

Switching to `${env.DEVMAN_PROJECT_DIR}` makes validation see it:

```
msg="${env.DEVMAN_PROJECT_DIR} was left unchanged because env.DEVMAN_PROJECT_DIR had
     no value when working_dir was evaluated." reason=unknown_env_binding
```

**But that spelling breaks `log_dir`.** The same DAG, triggered with the variable
exported *and* passed:

```
├─log: ${env.DEVMAN_PROJECT_DIR}/.devman/.runs/logs/e5_envform/...
      cwd=/tmp/devman-e/projB
```

`working_dir` resolved from the param; `log_dir` stayed literal, and Dagu created
the directory. **`log_dir` understands only the bare `${NAME}` form.** So:

| spelling | `working_dir` | `log_dir` | visible to `validate --show-unresolved` |
|---|---|---|---|
| `${NAME}` | resolves | **resolves** | **no** |
| `${env.NAME}` | resolves | **stays literal** | **yes** |

**Neither spelling gives both.** The plane must use `${NAME}` (A3), and therefore
cannot use `validate` to catch the unresolved case. A6's recommendation stands:
`doctor` looks for the directory named `${DEVMAN_PROJECT_DIR}` instead.

### Zombie detection — documented, not observed

The knobs are real (`config.schema.json`, `SchedulerDef` and `ProcDef`):

```
scheduler.zombie_detection_interval   default 45s   ("0" disables)
scheduler.failure_threshold           default 3     consecutive stale checks
proc.stale_threshold                  default 90s
proc.heartbeat_interval               default 5s
```

So a run whose agent dies stays visible as running for **at least 90 seconds**,
and up to roughly three detection intervals beyond that.

**Command:**

```
dagu enqueue e5_zombie -r zrun1      # step is `sleep 120`
kill -9 <matched agent pid>
```

**Evidence:**

```
t+4s    e5_zombie  zrun1  light  FRESH=yes     Status: Running
t+45s   e5_zombie  zrun1  light  FRESH=yes     Status: Running
t+100s  e5_zombie  zrun1  light  FRESH=yes     Status: Running
t+205s  No running processes                   Result: Succeeded
```

**Report what happened:** the run cleared and was recorded **Succeeded**, so I did
not produce a durable zombie and **the detection path is unverified**. What is
established is the window: `dagu ps` reports `FRESH=yes` for a run whose agent is
gone, for at least 90 seconds. A `doctor` that reads `FRESH` must say "not yet
stale", not "healthy".

### Charter impact

**changes §10**, and it satisfies **§15.3** for the failure §15.3 names.

§10 gives `devman doctor` one line: "diagnose the plane, and report shadowed
files and their drift". Name what it reads rather than computes:

| symptom | source | reimplement? |
|---|---|---|
| a wedged queue | `GET /queues`, `GET /queues/{name}/items` `conditions` | **no** |
| what holds the slot, and since when | the same, `running[]` with `startedAt` | **no** |
| a run whose process is gone | `dagu ps` `FRESH`, after 90s | **no** |
| the plane is up at all | `GET /health` | **no** |
| a DAG that failed to load | `dagu validate` per file, exit 1 | **yes — one exec per workflow** |
| a misspelled queue name (A1) | nothing in Dagu | **yes** |
| an unresolved `${DEVMAN_PROJECT_DIR}` (A3) | nothing usable — see the table above | **yes** |
| shadowed files and their drift (§15.6) | nothing in Dagu | **yes** |

**§15.3's condition is met** for the shared-availability failure it names. That
was the accepted risk's one requirement, and the diagnosis is a `GET` away.

**One sentence, and then stopping as §1 requires:** three of the four things
`doctor` must compute itself are file checks over the projection, not queries
against a running Dagu, which suggests `doctor` works without the daemon and
degrades when it is absent — a design note for whoever writes §10.

---

## E8 — Is there a cleaner per-project mechanism than A2 and A3 found?

**Bucket:** **answers** — the last open route to simplifying §7.2.

**Answer:** **no.** A runtime profile carries a per-run value into `working_dir`
and **not** into `log_dir`, exactly like `params` does. A6's dual mechanism —
export the variable *and* pass it — stays forced. But a profile is a
Dagu-native **name → values registry**, and it can replace the *param* half; and
a per-project `.env` is a real per-project channel for everything that is not a
path field.

**Tested:** dagu 2.15.0, on 2026-08-21.

### `dagu profile` is a registry inside Dagu

```
dagu profile create|delete|enable|disable|list|show
dagu profile set-var <profile> <key> <value>
dagu profile set-secret <profile> <key> <value>
dagu profile delete-key
```

**Command:**

```
dagu profile create proj-a --description "project A"
dagu profile set-var proj-a DEVMAN_PROJECT_DIR /tmp/devman-e/projA
dagu profile create proj-b --description "project B"
dagu profile set-var proj-b DEVMAN_PROJECT_DIR /tmp/devman-e/projB
dagu profile list
```

**Evidence:**

```
NAME    STATUS  PROTECTED  VARIABLES  SECRETS  DESCRIPTION
proj-a  active  false      1          0        project A
proj-b  active  false      1          0        project B
```

**Names are lowercase only** — `^[a-z0-9][a-z0-9._-]*$`, max 128
(`internal/profile/profile.go`). `dagu profile create projA` fails:

```
Error: invalid profile name: "projA"
```

§9.1 says identity "defaults to the repo's directory name". A directory named
`Pyjutsu` cannot be a profile name unchanged.

### The measurement — a profile reaches one field, not both

```yaml
# e8_profile.yaml
working_dir: ${DEVMAN_PROJECT_DIR}
log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs
steps:
  - id: probe
    run: echo "cwd=$(pwd) var=${DEVMAN_PROJECT_DIR:-<unset>}"
```

**Command:** the variable exported as **projA**, the profile naming **projB**,
and no `params` at all:

```
DEVMAN_PROJECT_DIR=/tmp/devman-e/projA dagu enqueue --profile proj-b e8_profile
```

**Evidence:**

```
├─log: /tmp/devman-e/projA/.devman/.runs/logs/e8_profile/...   <- the ENVIRONMENT won
      cwd=/tmp/devman-e/projB var=/tmp/devman-e/projB          <- the PROFILE won
```

**One run, two different projects.** A profile is applied by the process that
**executes**, so it behaves as `params` does in A3's table:

| source of `DEVMAN_PROJECT_DIR` | `working_dir` | `log_dir` |
|---|---|---|
| trigger's process environment | resolves | **resolves** |
| `params` (A3) | resolves | stays literal |
| the DAG's own `env:` (A3) | resolves | stays literal |
| **`--profile` (E8)** | **resolves** | **stays literal** |

With the variable removed from the trigger's environment entirely, the log path
stays literal and Dagu creates the directory in the daemon's tree — the A3
symptom again:

```
└─stdout: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/e8_profile/.../probe....out
      cwd=/tmp/devman-e/projB
Result: Succeeded
$ ls -d '<repo>/${DEVMAN_PROJECT_DIR}'
<repo>/${DEVMAN_PROJECT_DIR}
```

**So the answer to E8's question is no.** A7 already proved no instance
arrangement removes the split; E8 proves no *trigger-side* mechanism does
either. `log_dir` is resolved by the enqueuing process, full stop.

### `--default-working-dir` is ignored under `enqueue`

`dagu enqueue --help` advertises `--default-working-dir`, "Default working
directory for DAGs without explicit workingDir". On a DAG that declares none:

**Command:**

```
dagu enqueue --default-working-dir /tmp/devman-e/projB e8_dwd
dagu start   --default-working-dir /tmp/devman-e/projB e8_dwd
```

**Evidence:**

```
enqueue  cwd=<repo>/.devenv/state/dagu/dags        <- flag had no effect
start    cwd=/tmp/devman-e/projB                   <- flag worked
```

Same split as `dagu start` vs `enqueue` everywhere else: the flag is resolved by
the executing process, and under `enqueue` that is the daemon, which never sees
it. **A6 proved the trigger must use `enqueue` to get queues, so this flag is
unusable for the plane.**

### `dotenv` is a real per-project channel — for everything except the paths

`dotenv` files load relative to `working_dir`, and `.env` is loaded by default.

**Command:**

```
echo "DEVMAN_DOTENV_MARK=hello-from-projB" > /tmp/devman-e/projB/.env
# e8_dotenv.yaml: working_dir ${DEVMAN_PROJECT_DIR}, dotenv .env
DEVMAN_PROJECT_DIR=/tmp/devman-e/projB dagu enqueue e8_dotenv -- DEVMAN_PROJECT_DIR=/tmp/devman-e/projB
```

**Evidence:**

```
cwd=/tmp/devman-e/projB fromdotenv=hello-from-projB
```

**A file in the repository supplies per-project values to a shared group
workflow, under `enqueue`, with nothing in the workflow naming the project.** It
cannot supply `working_dir` — the file is found *through* `working_dir` — and it
cannot supply `log_dir`, which is resolved before the run. For everything else it
works.

### `consts` and `run_config` are not this

- `consts` — "Ordered immutable values available through `${consts.name}`". String,
  number, or boolean literals in the file. No per-run variance. Not applicable.
- `run_config` — `disable_param_edit` and `disable_run_id_edit`, which control
  what the **web UI** lets a user change when starting a run. Not applicable.

### Charter impact

**none** — and that is the finding. §7.2 and §9.2 keep A6's dual mechanism, and
the last plausible route to removing it is now closed by measurement rather than
by argument.

Two things worth carrying into reconciliation, each one sentence, as §1 requires:

- **A profile can replace the `params` half of the trigger.** `--profile pyjutsu`
  instead of `-- DEVMAN_PROJECT_DIR=/home/andrew/...` puts the path in Dagu's own
  state keyed by project identity, which is §9.1's rule implemented by Dagu — at
  the cost of a second registry to keep in step with §9.2's, and lowercase names.
- **`dagu profile set-secret` scopes a secret to a project**, which is the
  per-project answer E3 and E4 could not give, since a `secrets:` block in
  `base.yaml` grants every workflow every secret.

---

## E6 — Could `git_sync` replace the projection?

**Bucket:** **answers** — no.

**Answer:** **no.** `git_sync` syncs **one** repository, one branch, one
subdirectory, into the single `dags_dir`. §9.2's projection needs N project
repositories. It also requires a network remote with token or SSH credentials,
and it defaults to **pushing DAG edits back**.

**Tested:** dagu 2.15.0, on 2026-08-21.

### The schema is singular

`config.schema.json`, `GitSyncDef` — an **object**, not an array:

```
enabled  repository  branch  path  auth  auto_sync  push_enabled  commit
```

One `repository`, one `branch`, one `path`. A6 already established that
`dags_dir` is a single directory with no list form. So the most Dagu can do is
mirror one repository into the one DAG directory.

That is the wrong shape for §9.2 twice over: the plane has many project
repositories, and §5.1's rule is that "the repo supplies its own location at
registration, so nothing has to go looking". A single central repository of
workflows is the **central config every repo edits** that §4 exists to prevent.

### It needs a network remote

**Command:**

```yaml
git_sync:
  enabled: true
  repository: /tmp/devman-e/gitrepo.git    # a local bare repo
  branch: master
  path: workflows
  auth: {type: token, token: dummytoken}
```

**Evidence:**

```
Repository:  /tmp/devman-e/gitrepo.git
Status:      error
Last Error:  network error during clone: Get "https:///tmp/devman-e/gitrepo.git.git/info/refs
             ?service=git-upload-pack": http: no Host in request URL
```

With no `auth` block at all it fails earlier:

```
Last Error:  validation error for auth.token: token is required for token auth
```

The path is rewritten as an HTTPS URL. **A local path is not a valid
repository**, so the plane could not sync a checkout that is already on disk —
which is the only thing §9.2 has.

### It treats `dags_dir` as a working copy, and pushes by default

`dagu sync` has `status`, `pull`, `publish`, `discard`, `delete`, and `cleanup`.
With sync enabled, the DAGs already in `dags_dir` were reported against the
remote:

```
Sync Item Status Counts:
  Synced:    0
  Modified:  0
  Untracked: 4
  Conflict:  0
```

`push_enabled` **defaults to true**. So an instance with `git_sync` on will
commit and push DAG changes made through the UI. §9.3 requires that everything
under the machine's Dagu state be reconstructable and disposable; a Dagu that
pushes to a repository has made its own state canonical, which inverts §5.1.

### Charter impact

**none.** §9.2's projection and §5.2's registration stand, and the tension §6
anticipated with §5.1 does not arise, because the mechanism does not fit.

**One sentence, and then stopping as §1 requires:** `git_sync` is the right shape
for a team with one shared workflow repository, which is a different product from
one plane serving many independently-owned checkouts — worth recording as a
non-goal rather than an option.

---

## E7 — Does Dagu already have a registry concept?

**Bucket:** **answers** — partly, and only on the query side.

**Answer:** **Dagu has labels, and they answer the selection half of §5 and
§7.2 — but only through the API, not the CLI.** `labels` are key-value pairs
that can be filtered on; `group` is a UI-only display string. Neither resolves an
identity to a path, so devman's registry is not duplicating Dagu.

**Tested:** dagu 2.15.0, on 2026-08-21.

### What each field is

- **`labels`** — string, map, or array. `"env=prod team=platform"` or
  `{devman_project: pyjutsu}`. Key-value, and queryable.
- **`tags`** — **deprecated**, an alias for `labels`. Do not use it.
- **`group`** — "An organizational label used to group related DAGs together.
  Useful for categorizing DAGs in the UI". A display string, nothing more.
- **`dag_discovery`** — `recursive` and `symlinks`, both off by default (A5).

### Labels are filterable, from the API only

```yaml
# e7_labelled.yaml
group: pyjutsu
labels:
  devman_project: pyjutsu
  devman_group: python
```

**Command:**

```
curl -s --get 'http://127.0.0.1:8080/api/v1/dags' --data-urlencode 'labels=devman_group=python'
curl -s 'http://127.0.0.1:8080/api/v1/dags/labels'
```

**Evidence:**

```
labels=devman_project=pyjutsu   count: 1
labels=devman_group=python      count: 2

{"labels":["devman_group","devman_group=python","devman_project",
           "devman_project=other-repo","devman_project=pyjutsu"]}
```

**The CLI cannot do it.** `dagu ls --help`: "Optional pattern filters by DAG name
or file name (substring match)". Its flags are `--next`, `--last`, `--history`,
`--sort-last`, `--reverse`. There is no `--label`, and `ls` prints one column,
`NAME` — neither labels nor group are displayed.

### What this does and does not give the plane

**Gives:** if projected workflows carry `devman_project` and `devman_group`
labels, "every workflow of project X" and "every workflow from group Y" become
one API call, and the web UI can group by them. That is §7.3's resolution result
made visible without devman parsing anything — the labels are added by the
projection, not by the group file author.

**Does not give:** an identity-to-path mapping. §5's registry exists to answer
"where is `pyjutsu` checked out", and no Dagu field holds that. E8's `dagu
profile` is closer — it maps a name to values — but it is a second store to keep
in step, not a replacement.

**A caution.** §7.2 says a workflow is "Dagu configuration from the first line to
the last" with "no devman-specific key anywhere in the file". A `devman_project`
label is a Dagu key holding a devman word. It stays inside the rule only because
the **projection** writes it and the group file does not.

### `errors` — an extra discovery signal E5 did not have

`GET /api/v1/dags` returns an `errors` array alongside the DAG list:

```json
{"errors":["DAG discovery failed: a5_symlink.yaml: DAG file symlink resolves
  outside the configured DAG directory; enable dag_discovery.symlinks to load
  it: external DAG file symlinks are disabled"], "labels":[...]}
```

It reports files that could not be **discovered**. It does **not** report files
that fail to **load**: `e5_broken.yaml` appeared in the same response as an
ordinary DAG among 70. So E5's conclusion stands — `doctor` still runs
`dagu validate` per file — but this array is a cheaper first check.

### The instance config needs a restart, and says the opposite

Found while measuring the above, and it belongs to §5.2. The instance config sets
`dag_discovery.symlinks: true`, the CLI honours it, and the running server does
not:

```
CLI:     dagu ls | grep -c a5_symlink   →  1
CLI:     dagu start a5_symlink          →  Result: Succeeded
Server:  GET /api/v1/dags               →  "...enable dag_discovery.symlinks to load it"
```

**The error names the knob that is already set.** The cause is startup order:

```
server started   Fri Aug 21 21:36:04 2026
config.yaml      mtime 2026-08-21 21:53:04
```

Reproduced deliberately on the second instance — add the knob to a running
server's config, change nothing else:

```
before knob, running server   errors: ['DAG discovery failed: e7_linked.yaml ...']
after  knob, no restart       errors: ['DAG discovery failed: e7_linked.yaml ...']
CLI, no restart               dagu ls | grep -c e7_linked  →  1
after  knob, with restart     errors: None
```

**A5 established that a new DAG file needs no restart. An instance config change
does**, and the CLI and the server disagree in the meantime.

### Charter impact

**changes §5.2**, one sentence added to A5's.

A5 already requires the machine module to set `dag_discovery.recursive: true` and
`dag_discovery.symlinks: true`. Add: **changing the instance config requires
restarting the Dagu service**, and until it is restarted the CLI and the server
disagree, with the server reporting an error that names a setting that is
already present. A machine module that writes `config.yaml` must restart the
service in the same activation, or §9.3's "rebuild is inconvenient, not
catastrophic" becomes "the plane half-works and blames your config".

**One sentence, and then stopping as §1 requires:** `devman doctor` can detect
this exactly — compare `config.yaml`'s mtime against the service start time.

### E4 addendum — `handler_on` inherits too, and it can write §9.2's `metadata.json`

Measured during the reconciliation pass, on 2026-08-22, because §9.2's
`metadata.json` owner turned on it.

`base.yaml`:

```yaml
working_dir: ${DEVMAN_PROJECT_DIR}
log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs
handler_on:
  exit:
    run: |
      mkdir -p "$DEVMAN_PROJECT_DIR/.devman/.runs"
      printf '{"dag":"%s","run_id":"%s","status":"%s"}\n' \
        "$DAG_NAME" "$DAG_RUN_ID" "$DAG_RUN_STATUS" \
        >> "$DEVMAN_PROJECT_DIR/.devman/.runs/metadata.jsonl"
```

Two workflows, each holding nothing but `steps:` — one succeeding, one `exit 3`.

**Command:**

```
DEVMAN_PROJECT_DIR=/tmp/devman-e/projA dagu enqueue r1_meta     -- DEVMAN_PROJECT_DIR=/tmp/devman-e/projA
DEVMAN_PROJECT_DIR=/tmp/devman-e/projA dagu enqueue r1_metafail -- DEVMAN_PROJECT_DIR=/tmp/devman-e/projA
```

**Evidence:**

```
{"dag":"r1_meta","run_id":"034BMd0JlZC0Cpe1gYRMFJ","status":"succeeded"}
{"dag":"r1_metafail","run_id":"034BMdTBawo91O9mgnEBK4","status":"failed"}
```

**A machine-written exit handler produces a per-project run record for every
run, on both the success and the failure path, with no workflow carrying
anything.** `$DEVMAN_PROJECT_DIR` resolves in the handler because the handler
runs in the executing process, the same source `working_dir` uses (A7). This
gives A3's open question — "either a workflow writes `metadata.json` itself, or
`devman doctor` projects it out of Dagu's history" — a third and better answer.

**Charter impact:** **changes §9.2**, in the direction A3 asked to be made
explicit.

---

## Tier 3 — the catalogue

Real capability in 2.15.0. **Nothing here was spiked**, and nothing here asks the
charter for a decision now. Descriptions are the schema's own, condensed. Stage
numbers refer to §13.

| Capability | What it is | Stage |
|---|---|---|
| `type: agent` + `tasks:` | "Goals an agent DAG must satisfy before it concludes successfully"; the LLM chooses step order | 4 — agent workflows |
| `llm:` + `action: chat.completion` | DAG-level LLM defaults inherited by chat steps; providers anthropic, openai, gemini, openrouter, zai, local | 4 |
| `harness:` / `harnesses:` | Defaults and reusable definitions for `action: harness.run`, which drives external coding-agent CLIs — aider, amp, claude, cline, codex, copilot, cursor, droid, gemini, goose, opencode, qwen | 4 — this repo already ships `claude-code` and `codex-cli` |
| `opencode:` (config) | "Process-local managed OpenCode service configuration" | 4 |
| MCP at `/mcp` | `dagu_read`, `dagu_change`, `dagu_execute`; measured in E2 | 4 — an agent triggering the plane |
| `worker:` / `coordinator:` (config) | Worker and coordinator services for distributed execution; gRPC dispatch, heartbeats, log and artifact streaming | later — §9.1's "future remote worker" |
| `worker_selector:` | Map of worker label key-values, or the string `"local"` to force local execution | later |
| `remote_nodes:` (config) | "List of remote node connections for distributed monitoring" | later |
| `dagu context` | `add`, `list`, `remove`, `test`, `update`, `use` — CLI contexts for local and remote Dagu servers | later |
| `default_execution_mode` | `local` runs on the server process, `distributed` dispatches to workers | later |
| step `dependencies:` | Files staged to a **distributed worker** beside the DAG; local execution does not stage them | later — pairs with `worker:` |
| `human.task` / `dagu human-task complete` | A step that waits for a person; the DAG enters `Waiting` | 4 — policy gating |
| `container:` / `kubernetes:` | DAG-level defaults for containerized steps, overridable per step | isolation |
| `registry_auths:` | Docker registry credentials, or a whole `DOCKER_AUTH_CONFIG` | isolation |
| `resources:` | "CPU and memory limits requested for this DAG run"; warns and continues where unenforceable | isolation |
| `retry_policy:` / `repeat_policy:` / `continue_on:` | Per DAG, per step, and settable once in `defaults:` (E4) | reliability |
| `handler_on:` | Lifecycle hooks — `init`, `success`, `failure`, `abort`, `exit`, `wait`; each is a full step | reliability |
| `otel:` | OpenTelemetry tracing of DAG execution | reliability |
| `tools:` | "DAG-level CLI tool dependencies installed on the worker before any step runs" | reliability — note the overlap with devenv (§6) |
| `smtp:` / `error_mail:` / `info_mail:` / `mail_on:` | SMTP with OAuth for Microsoft, Google service account, and Google refresh token; mail on failure, success, or wait | notification |
| `permissions:` / `auth:` / `ip_access:` / `tls:` / `tunnel:` | UI and API permissions, RBAC roles, client-IP filtering, TLS, and a Tailscale tunnel | exposure |
| `actions:` | "Reusable custom action definitions"; merged between base config and DAG, duplicates rejected | — a shared-vocabulary mechanism inside Dagu |
| `step_types:` | **Deprecated**; use `actions:` | — |
| `schedule:` | Cron, **profile-scoped cron entries**, and one-off RFC 3339 timestamps | — pairs with E8's profiles |
| `overlap_policy:` | `skip`, `all`, `latest` — what a catchup run does when the DAG is still running | — |
| `catchup_window:` | Replay window for scheduled runs missed during downtime; `base.yaml` ships `"6h"` | — |
| `terminal:` (config) | Web-based terminal in the UI | exposure |

Two entries in that table touch the charter and are **not** followed up here, as
§1 requires:

- **`tools:` installs CLI dependencies**, which is devenv's job under §6. A group
  workflow that used it would put the same dependency in two places.
- **`actions:`** is Dagu's own mechanism for a shared vocabulary that is more than
  a queue name. §7.1 argues the vocabulary should stay at queue names; `actions:`
  is what a future argument for more would use.

---

## Summary — Investigation E, every `deletes §N` and `changes §N`

Investigation E **deletes one section** and changes four. Nothing is killed.
This extends Investigation A's summary above; the two lists together are the
whole reconciliation input.

| ID | Question | Bucket | Charter impact |
|---|---|---|---|
| E1 | does Dagu break the write-loop? | **replaces** | **deletes §8.1** |
| E2 | what invokes Dagu? | answers | **changes §8**, closes D7 |
| E3 | whose job are secrets? | **replaces** (half) | **changes §9.4** |
| E4 | how much can the machine set once? | **replaces** | **changes §7.2**, shortens §7.1 |
| E5 | can Dagu diagnose a wedged plane? | answers | **changes §10**, satisfies §15.3 |
| E6 | could `git_sync` replace the projection? | answers | none |
| E7 | does Dagu have a registry concept? | answers | **changes §5.2** |
| E8 | a cleaner per-project mechanism? | answers | none — A6's dual mechanism stands |

### The one deletion

- **deletes §8.1** — "Loop-breaking is plane infrastructure" describes a token
  Dagu already keeps. `type: build` reuse leaves an unchanged output byte- and
  mtime-identical, so a watcher sees no event and no token is needed at all; a
  step-level `preconditions` hash check covers the in-place case §8.1 actually
  describes, works from one shared group file with a per-project parameter, and
  keeps the property §8.1 chose hashes for — **your own edit still fires**. Drop
  `generation.json` from §8.1 and from §9.2's `.devman/.runs/` layout. Keep one
  paragraph of authoring guidance in the group that needs it. Costs: the skip
  happens after enqueue rather than before, `type: build` cannot rewrite a file
  in place, and Dagu's manifest is machine-side.

### The changes

- **changes §8** — name the mechanism §8 leaves open. **A trigger is a local
  process that runs `dagu enqueue`**, exporting `DEVMAN_PROJECT_DIR` and passing
  it as a parameter. Dagu's HTTP, webhook, and MCP surfaces are real, accept
  parameters, and are queue-governed, but all three resolve `log_dir` in the
  server process, so a run they start cannot write its logs into the project.
  Triggers are plane machinery, not group content. This closes **D7**.

- **changes §7.2, shortens §7.1** — `working_dir`, `log_dir`, `queue`, `env`,
  retention, `secrets`, and step `defaults` all inherit from `base.yaml`, with
  both interpolations keeping the sources A3 measured. A group workflow can be
  `steps:` and nothing else. §7.1's "queue names are the entire shared
  vocabulary" is already false — the true list is queue names, the variable name
  `DEVMAN_PROJECT_DIR`, and the `.devman/.runs/` path shape — and E4's
  contribution is that the machine can state all three once instead of every
  workflow repeating them. A default queue in `base.yaml` also removes A1's
  silent-typo hazard for every workflow that names none.

- **changes §9.4** — Dagu resolves secrets itself. A DAG-level `secrets:` block
  names a provider and a key; Dagu injects the value, **masks it in logs**, and
  **fails the run with a named error when it is missing**. Neither is true of an
  injected environment variable, so `secrets:` is better than §9.4's wording even
  where the module still supplies the value. Keep `provider: env` — it stays
  portable and keeps §9.4's injection path, shrunk to "set these variables on the
  user service". `provider: file` deletes the injection path but writes a
  machine-specific absolute path into a workflow, against §9.1 and §7.2.

- **changes §10** — say what `devman doctor` **reads** rather than computes. A
  wedged queue explains itself: `GET /queues/{name}/items` gives every waiting
  item a reason (`MaxConcurrencyReached`) and a message, and `running[]` names
  what holds the slot and since when. **This satisfies §15.3's one condition** for
  the failure §15.3 names. Four things `doctor` must still compute itself: a DAG
  that fails to load (`dagu ls` lists it silently — run `dagu validate` per file,
  exit 1), a misspelled queue name (A1), an unresolved `${DEVMAN_PROJECT_DIR}`
  (A3 — and `validate --show-unresolved` cannot help, because it sees only the
  `${env.NAME}` spelling, which breaks `log_dir`), and shadowed-file drift
  (§15.6).

- **changes §5.2** — one sentence beyond A5's. **Changing the instance config
  requires restarting the Dagu service.** Until it is restarted the CLI honours
  the new config and the server does not, and the server reports an error naming
  the setting that is already present. A machine module that writes `config.yaml`
  must restart the service in the same activation. A new *DAG file* still needs no
  restart (A5).

### Documentation that is wrong — two more, on top of A's three

Investigation A recorded three places where the schema or `base.yaml` disagrees
with the binary. E adds two:

4. **`dagu validate` passes a `type: build` DAG the runtime rejects.** A step
   declaring one path as both input and output validates clean and fails at run
   time (E1).
5. **`working_dir` performs no command substitution.** A2 recorded the schema's
   claim that interpolation accepts "shell-style expressions and command
   substitution"; `$(...)` and backticks are both kept literal in `working_dir`,
   and Dagu creates the resulting directory (E2).

And one asymmetry that is not documented anywhere: **`log_dir` understands only
the bare `${NAME}` form**, while `working_dir` accepts `${env.NAME}` as well
(E5).

### What Investigation E did not do

Investigations B, C, and D were not started. Tier 3 was catalogued and not
spiked. Nothing in `CONCEPT.md` was edited — every impact above is recorded for
the single reconciliation pass, as §5 of the kickoff requires.

---
---

# Investigation B — one flake, two module interfaces

Answers to `INVESTIGATION_B_PROMPT.md`. The question is whether one flake can
carry a NixOS module and a devenv module at one version, without either
constraining the other's nixpkgs (§3.1, §12.3).

**The answer is yes.** The module does not need to pin its own nixpkgs. §3.1's
anti-drift argument holds as a property, not as a convention.

**Tested:** Nix **2.34.7**, devenv **2.1.2**, on **2026-08-22**.
**devman revision under test:** `f674623df61f039150fb5eb70accaa03eae2cd8a`, on
branch `dagu-devenv-automation-eli5`. Every measurement below used that one
revision.

### The pair that was built

| Path | What it is |
|---|---|
| `nix/nixos-module.nix` | the machine interface — `systemd.user.services.dagu`, `config.yaml`, `base.yaml` |
| `modules/devenv.nix` | the repo interface — `devman.enable`, `project`, `groups`, a hash-guarded registry write in `enterShell` |
| `flake.nix` | gains `nixosModules.default`; `packages` and `overlays` unchanged |

Both take `pkgs` from their **consumer**. Neither reads the devman flake's own
`nixpkgs` input. That input now serves `packages` and `checks` only.

The NixOS module is a stub in size, not in shape: it writes a user service, it
puts `DAGU_HOME` at `~/.local/share/dagu`, its `config.yaml` carries
`env_passthrough_prefixes: [DEVMAN_]` and both `dag_discovery` knobs, its
`base.yaml` carries `working_dir`, `log_dir`, and a default queue, and it
declares `restartTriggers` on both files. It does not project workflows, resolve
groups, or read the registry.

### The four nixpkgs in play

| Name | What it is | Revision |
|---|---|---|
| `machine` | the running machine's tree, from the flake registry | `d407951` (NixOS 26.11.20260705) |
| `unstable` | devman's own flake input | `ffb3c9b` (2026-08-19) |
| `rolling` | this repo's devenv nixpkgs, patched | `ee3d58d` (`cachix/devenv-nixpkgs`) |
| `rolling-src` | the plain tree `rolling` patches | `54ba4bc` (2026-08-16) |

`rolling` is **not a nixpkgs checkout**. It is a wrapper flake: it takes
`nixpkgs-src`, applies patches with `applyPatches`, and exposes the result as
`legacyPackages.<system>`. It therefore has no `nixos/lib/eval-config.nix` at
its root, and reaching its package set needs import-from-derivation:

```
error: cannot build '/nix/store/f2mvh6...-devenv-nixpkgs-patched.drv^out' during
evaluation because the option 'allow-import-from-derivation' is disabled
```

That is why the NixOS half is evaluated against `rolling-src` and the Dagu
package is built against both.

### The scratch flake

`.scratch/projects/006-automation-plane/b-scratch/flake.nix` — imports devman
at the pinned revision, builds a throwaway `nixosConfigurations.<tree>` per
tree, and builds `nix/dagu.nix` per package set. `collide.nix` beside it is B3's
probe. Throwaway repos live at `/tmp/devman-b/proj{A,B,C,D,F,G}`.

---

## B1 — Do both modules evaluate, each under its own nixpkgs?

**Answer:** **yes.** The NixOS module builds a full system toplevel under the
machine's nixpkgs, under `nixos-unstable`, and under the tree the repo's devenv
patches. The devenv module evaluates and registers under the repo's
`devenv-nixpkgs/rolling`. Both from one flake at one revision, and neither
constrains the other.

**Tested:** Nix 2.34.7, devenv 2.1.2, devman `f674623`, on 2026-08-22.

### The NixOS half

**Command:**

```
cd .scratch/projects/006-automation-plane/b-scratch
for t in machine unstable rolling-src; do
  nix build --no-link --print-out-paths \
    ".#nixosConfigurations.$t.config.system.build.toplevel"
done
```

**Evidence:**

```
machine      /nix/store/dkkjs6kyzl9jlxkim8i19mhf5j7nl2r6-nixos-system-nixos-26.11pre-git
unstable     /nix/store/hac6zr8n0y0r7brv6p64sz6dxr9z20xc-nixos-system-nixos-26.11pre-git
rolling-src  /nix/store/hqzdqp8pcp9nbc433dc67bq09jcsr84z-nixos-system-nixos-26.11pre-git
```

Three toplevels, one module file, three different nixpkgs. Nothing was
activated and `/etc/nixos/` was not touched.

The unit the machine's tree produces, read out of the built system:

```
$ cat /nix/store/dkkjs6...-nixos-system-nixos-26.11pre-git/etc/systemd/user/dagu.service
[Unit]
Description=Dagu — devman automation plane
X-Restart-Triggers=/nix/store/fl9j1w1p4pl1sjx0kfmsvf0cbzbssv8w-X-Restart-Triggers-dagu

[Service]
Environment="DAGU_HOME=%h/.local/share/dagu"
ExecStart=/nix/store/2mjbj2imilxj56l8l79z689hz40ram6a-dagu-2.15.0/bin/dagu start-all
ExecStartPre=/nix/store/p3dy65d37rxcffk8mlq6cd5ny38m02zh-dagu-install-config
Restart=on-failure
RestartSec=5
Type=simple

[Install]
WantedBy=default.target
```

`systemd.user.services.<name>.restartTriggers` is accepted, and it renders to
`X-Restart-Triggers` in the unit. §5.2's "must restart in the same activation"
therefore has a mechanism on the user side as well as the system side.

The two generated files:

```
# config.yaml
dag_discovery:
  recursive: true
  symlinks: true
env_passthrough_prefixes:
- DEVMAN_
queues:
  config:
  - max_concurrency: 1
    name: exclusive
  - max_concurrency: 4
    name: light
  enabled: true

# base.yaml
hist_retention_days: 7
log_dir: ${DEVMAN_PROJECT_DIR}/.devman/.runs/logs
queue: exclusive
working_dir: ${DEVMAN_PROJECT_DIR}
```

`pkgs.formats.yaml` passes `${DEVMAN_PROJECT_DIR}` through unaltered, so Dagu's
run-time interpolation (A2, A3) survives Nix generation.

### The devenv half

Three throwaway repos, each with its own `devenv.yaml` pinning
`devenv-nixpkgs/rolling` and importing `devman/modules`.

**Command:**

```
cd /tmp/devman-b/projA && devenv shell -- true
cd /tmp/devman-b/projB && devenv shell -- true
cd /tmp/devman-b/projF && devenv shell -- true
```

**Evidence:**

```
$ cat /tmp/devman-b/registry/projects/projF.json
{
  "groups": [ "base" ],
  "path": "/tmp/devman-b/projF",
  "project": "projF",
  "schema": 1
}
```

One unedited module, three repos, three entries, each carrying its own
run-time path. §7.2's portability claim holds for the repo interface as well as
for a workflow file.

### The proof that neither constrains the other

`projF`'s `devenv.lock` holds **two nixpkgs nodes**, and the root and devman
resolve to different ones:

```
devman.inputs       -> {'nixpkgs': 'nixpkgs'}
nixpkgs      -> NixOS/nixpkgs @ ffb3c9b700e759be2ef13237c9d8f953b32a1e46
nixpkgs_2    -> cachix/devenv-nixpkgs @ ee3d58d53cfcddfc0ae6fc7f04f4fe2a0c7cf0ed
root.inputs.nixpkgs -> nixpkgs_2
```

devman keeps its `nixos-unstable`, the repo keeps its `rolling`, and devenv
neither deduplicates them nor forces one onto the other. The module is
evaluated under `nixpkgs_2` because it takes `pkgs` from the consumer.

**Charter impact:** **none.** §3.1 and §12.3 stand. One clarification worth
adding when §3.1 is next edited: *the modules take `pkgs` from their consumer,
and the flake's own `nixpkgs` input serves `packages` and `checks` only.* That
sentence is what makes the premise a property rather than a hope, and B3 shows
what happens when a module breaks it.

---

## B2 — Does the Dagu package resolve in both?

**Answer:** **yes, in all four package sets, and the binary is byte-identical.**
`nix/dagu.nix` needs no pin of its own.

**Tested:** Nix 2.34.7, devman `f674623`, on 2026-08-22.

**Command:**

```
cd .scratch/projects/006-automation-plane/b-scratch
for t in machine unstable rolling-src; do nix build --no-link --print-out-paths ".#$t"; done
nix build --no-link --print-out-paths --option allow-import-from-derivation true ".#rolling"
```

**Evidence:**

```
machine      /nix/store/2mjbj2imilxj56l8l79z689hz40ram6a-dagu-2.15.0
unstable     /nix/store/80z64fdn6gkgagz7xh2v4mh362hahvqa-dagu-2.15.0
rolling-src  /nix/store/80z64fdn6gkgagz7xh2v4mh362hahvqa-dagu-2.15.0
rolling      /nix/store/80z64fdn6gkgagz7xh2v4mh362hahvqa-dagu-2.15.0
```

Two store paths, and the binaries in them are the same file:

```
$ sha256sum /nix/store/2mjbj2.../bin/dagu /nix/store/80z64f.../bin/dagu
5d8f5986127563269769ad25198cdffc8bd334022e3f3a50759ae74e10d83665  .../2mjbj2.../bin/dagu
5d8f5986127563269769ad25198cdffc8bd334022e3f3a50759ae74e10d83665  .../80z64f.../bin/dagu
```

The reason is the shape of the expression, and the prompt guessed right: it
installs a release tarball. The tarball is a fixed-output derivation, so both
package sets get the **same** `src` store path:

```
src A (machine):  /nix/store/a0k5bnfry03aq2j17hn5pb33qvrhdvkk-dagu_2.15.0_linux_amd64.tar.gz
src B (unstable): /nix/store/a0k5bnfry03aq2j17hn5pb33qvrhdvkk-dagu_2.15.0_linux_amd64.tar.gz
```

The whole difference is the builder:

| | machine | unstable |
|---|---|---|
| stdenv | `stdenv-linux.drv` | `stdenv-linux-no-cc.drv` |
| bash | `5.3p9` | `5.3p15` |

Neither reaches the output, because the binary is statically linked, is copied
rather than compiled, and needs no `patchelf` (E0.2). Each closure is one path
with no runtime dependencies:

```
$ nix path-info -rS /nix/store/2mjbj2...-dagu-2.15.0
/nix/store/2mjbj2imilxj56l8l79z689hz40ram6a-dagu-2.15.0	162144896
```

`doInstallCheck` runs `$out/bin/dagu version` in every one of the four builds,
so "it resolves" means "it ran", not "it evaluated".

**Charter impact:** **none.** §4's "both interfaces call the same file" holds,
and §3.1's anti-drift rule is cheapest exactly where it matters most. Note the
cost so a later pass can decide whether to care: **two store paths mean 155 MB
of identical binary held twice** while the machine's nixpkgs and the repo's
disagree. See B3.

---

## B3 — What breaks first when the two disagree on a shared input?

**Answer:** **it depends on the class of disagreement, and only one of the three
is loud.** A missing attribute is an eval failure on the side that lacks it,
before anything builds, naming the module's own file and line. A *differing*
attribute is silent, and is the one to design against.

**Tested:** Nix 2.34.7, devman `f674623`, on 2026-08-22.

The disagreement is already live in the repository, and it is real: the machine's
tree and `nixos-unstable` differ by 465 top-level attributes.

**Command:**

```
nix eval --impure --json --expr \
  "builtins.attrNames (import /nix/store/ifpab9...-source { system=\"x86_64-linux\"; })"
```

**Evidence:**

```
machine attrs: 27506   unstable attrs: 27905
in unstable, not on the machine: 432   (cronet-go, azure-mcp, bashd, ...)
on the machine, not in unstable:  33   (rust_1_95, julia_19, nim-2_2, ...)
```

### Class 1 — a missing attribute: eval failure, early and loud

`b-scratch/collide.nix` adds one reference to the module, in each direction.

**Command:**

```
nix eval --raw ".#nixosConfigurations.machine-newer-than-machine.config\
.systemd.user.services.dagu-collide.serviceConfig.ExecStart"
```

**Evidence — the module wants something newer than the machine:**

```
error: attribute 'cronet-go' missing
at /home/andrew/.../b-scratch/collide.nix:19:15:
    18|       if direction == "newer-than-machine"
    19|       then "${pkgs.cronet-go}/bin/probe"
      |               ^
```

**Evidence — the module wants something the newer tree removed:**

```
error: attribute 'rust_1_95' missing
Did you mean rust_1_97?
```

Both fail at **evaluation**, on the **consumer** whose tree lacks the
attribute, pointing at the module's own line, before a single derivation is
built. The same probe under the tree that has the attribute succeeds:

```
unstable-newer-than-machine  /nix/store/i78zw8...-cronet-go-150.0.7871.63-1/bin/probe
```

This is the good case. A module that needs a package one consumer lacks tells
that consumer, immediately, by name.

### Class 2 — the same attribute, a different value: silent

Nothing fails. The two sides simply get different software from the same devman
revision.

**Command:**

```
nix eval --raw ".#nixosConfigurations.machine.pkgs.gnused.outPath"
nix eval --impure --raw --option allow-import-from-derivation true \
  --expr '(builtins.getFlake "...").inputs.rolling.legacyPackages.x86_64-linux.gnused.outPath'
```

**Evidence:**

```
NixOS module (machine tree): /nix/store/0hamsiy8hsyfw1hmizbc3bf93ad7fa1v-gnused-4.9
devenv module (rolling):     /nix/store/rxd8p6g4k4s0sx4q1szmzvp9rsmhmfys-gnused-4.10
```

`sed` renders the registry entry in `enterShell` and appears on the service's
`PATH`. It is 4.10 in the repo and 4.9 on the machine, from one module pair at
one revision. Nothing announces it. The same holds for `git` (2.54.0 vs
2.55.0), `python3` (3.13.13 vs 3.14.7), and `bash` (5.3p9 vs 5.3p15).

This is the class §12.3 should have worried about. It does not weaken the
single-flake premise — it is a consequence of the premise working, because each
side gets its own tree on purpose. It sets one design rule: **the shared
vocabulary between the two interfaces must be text, not a package.** Queue
names, `DEVMAN_PROJECT_DIR`, the `.devman/.runs/` path shape, and the registry
schema are all text (E4). `nix/dagu.nix` is the single exception, and B2 shows
it costs 155 MB of duplication and no behaviour difference.

### Class 3 — the module reaches for the flake's own nixpkgs: possible, and today free

A devenv module *can* reach past its consumer. `inputs.devman.inputs.nixpkgs` is
reachable from a devenv module, so pinning is available if it is ever needed.

**Command:** `/tmp/devman-b/projG`, a devenv module referencing both.

**Evidence:**

```
repo   gnused: /nix/store/rxd8p6g4k4s0sx4q1szmzvp9rsmhmfys-gnused-4.10
devman gnused: /nix/store/rxd8p6g4k4s0sx4q1szmzvp9rsmhmfys-gnused-4.10
repo   dagu:   /nix/store/80z64fdn6gkgagz7xh2v4mh362hahvqa-dagu-2.15.0
devman dagu:   /nix/store/80z64fdn6gkgagz7xh2v4mh362hahvqa-dagu-2.15.0
```

Identical today, because devman's `nixos-unstable` (`ffb3c9b`, 2026-08-19) and
the tree `rolling` patches (`54ba4bc`, 2026-08-16) are three days apart. The
divergence that exists is machine-versus-repo, not flake-versus-repo. Recorded
so the escape hatch is known to exist; **do not take it**, because a module that
supplies its own `pkgs` puts a second nixpkgs in every consumer's shell and
returns Class 2's silent divergence to a place the consumer cannot see.

**Charter impact:** **none, and it adds one rule to §3.1.** Say plainly what the
two interfaces are allowed to share: *text, and one package expression.* A
module that reaches for the flake's own nixpkgs breaks the premise that makes
§3.1 work.

---

## B4 — Is `modules/` the right import path?

**Answer:** **yes, with one correction and one warning.** The path is right, but
the file inside it must be named `devenv.nix`; `default.nix` is never consulted.
And a `git+` pin holds over **https** and does **not** hold over **file**.

**Tested:** devenv 2.1.2, Nix 2.34.7, on 2026-08-22.

### The file must be `devenv.nix`

The first attempt shipped `modules/default.nix`, which is what a Nix reader
expects. It fails.

**Command:** `cd /tmp/devman-b/projA && devenv shell -- true`, with
`imports: - devman/modules`.

**Evidence:**

```
error: devman/modules/devenv.nix file does not exist
```

The rule is in devenv's own bootstrap, at
`.devenv/bootstrap/bootstrapLib.nix:91`:

```nix
tryImport =
  resolvedPath: basePath:
  if lib.hasSuffix ".nix" basePath then
    [ (import resolvedPath) ]
  else
    let
      devenvpath = resolvedPath + "/devenv.nix";
      localpath = resolvedPath + "/devenv.local.nix";
    in
    if builtins.pathExists devenvpath then
      [ (import devenvpath) ] ++ lib.optional (builtins.pathExists localpath) (import localpath)
    else
      throw (basePath + "/devenv.nix file does not exist");
```

So `<input>/<subdir>` resolves to `inputs.<input> + /<subdir>` and then looks
for `devenv.nix` inside it, plus an optional `devenv.local.nix`. A path ending
in `.nix` is imported directly instead. `shellij/modules` works because shellij
ships `modules/devenv.nix`; its `modules/default.nix` is a Home-Manager module
and devenv never reads it.

The file was renamed to `modules/devenv.nix` and the import then worked.

### The form holds under a `git+https` pin

**Command:** `/tmp/devman-b/projF`, with

```yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=dagu-devenv-automation-eli5&rev=f674623df61f039150fb5eb70accaa03eae2cd8a"
imports:
  - devman/modules
```

**Evidence:** the shell entered, `dagu` was on `PATH`, the registry entry was
written, and the lock recorded the revision:

```
"locked": {
 "lastModified": 1787376172,
 "narHash": "sha256-kI3thUGphDTNsbXronZcNr5j3mLzeUW66oeA/nIWu0M=",
 "ref": "dagu-devenv-automation-eli5",
 "rev": "f674623df61f039150fb5eb70accaa03eae2cd8a",
 "revCount": 142,
 "type": "git",
 "url": "https://github.com/Bullish-Design/devman"
}
```

§3.2's mandated form works, and it is a real pin.

### But `git+file` silently drops the revision

The obvious development shortcut — pin a local checkout — is not a pin.

**Command:** `/tmp/devman-b/projC`, pinned to `rev=6cc76d2`. A later commit
changed the module's `groups` default to `[ "base" "PIN-TEST" ]`. The pinned
repo's cache was cleared and the shell re-entered.

**Evidence:**

```
$ cat /tmp/devman-b/registry/projects/projC.json
{
  "groups": [ "base", "PIN-TEST" ],   <- from a commit AFTER the pinned rev
  ...
}
```

The lock explains it:

```
"locked":   { "ref": "dagu-devenv-automation-eli5", "type": "git",
              "url": "file:///home/andrew/.paseo/worktrees/..." }
"original": { "ref": "...", "rev": "6cc76d2e201afb6c05597ab6433bfdf1c1b78a44", ... }
```

`original` keeps the revision. `locked` has no `rev` and no `narHash`, so there
is nothing to hold and the input tracks the branch head.

The full matrix, over the same two URLs with and without `flake: false`:

```
file-flake       locked keys: [ref, type, url]                                  rev= ABSENT
file-nonflake    locked keys: [ref, type, url]                                  rev= ABSENT
https-flake      locked keys: [lastModified, narHash, ref, rev, revCount, ...]  rev= 8b85ecc...
https-nonflake   locked keys: [lastModified, narHash, ref, rev, revCount, ...]  rev= 8b85ecc...
```

`flake: true`/`false` makes no difference. The transport does. A `rev`-only
`git+file` URL with no `ref` is worse: devenv discards the revision and
substitutes the branch instead — `"ref": "refs/heads/dagu-devenv-automation-eli5"`.

It is devenv, not Nix. Nix honours the same URL:

```
$ nix flake metadata --json "git+file:///home/.../special-dragon?ref=...&rev=6cc76d2..."
/nix/store/1gx7wsh94p5zkq7d5jgjzb7pdgk9pkpk-source 6cc76d2e201afb6c05597ab6433bfdf1c1b78a44
(no marker — nix honours the pin)
```

The repository was clean at the time of the test, so this is not a dirty-tree
artefact. devenv 2.1.2 was under test; 2.2.2 exists and was not tested.

One more property, confirmed in passing: a `git+file` URL pointing at a **git
worktree** resolves. Nix reads the worktree's `.git` file correctly.

**Charter impact:** **changes §3.2**, in two sentences.

1. The repo interface is `modules/devenv.nix`, not `modules/default.nix`. §3.1's
   shape diagram says `modules/default.nix` and must be corrected. If the flake
   ever wants a Nix-importable `modules/default.nix` as well, it may have one —
   devenv will ignore it.
2. Add the warning §3.2's "pin with `git+`" implies but does not state: **the
   pin holds over `git+https` and not over `git+file`.** A repo developing
   against a local devman checkout tracks the branch head no matter what `rev`
   it writes, and nothing warns it. Use `path:` deliberately for local work, and
   `git+https` with a `rev` everywhere else.

---

## Summary — Investigation B, the single-flake premise

**The premise holds. The module does not need to pin its own nixpkgs.** The
plane ships one flake, and §3.1's anti-drift argument stays a property.

| ID | Question | Answer | Charter impact |
|---|---|---|---|
| B1 | do both modules evaluate under their own nixpkgs? | **yes** | none |
| B2 | does the Dagu package resolve in both? | **yes, byte-identical** | none |
| B3 | what breaks first when the two disagree? | eval failure if absent, **silence if merely different** | none — adds one rule to §3.1 |
| B4 | is `modules/` the right import path? | **yes**, but the file is `devenv.nix` | **changes §3.2** (and §3.1's diagram) |

### The one change

- **changes §3.2, and §3.1's shape diagram** — the repo interface is
  `modules/devenv.nix`. devenv resolves `<input>/<subdir>` to
  `inputs.<input> + /<subdir>` and then requires `devenv.nix` inside it; a
  `default.nix` is never read. And "pin with `git+`" needs a qualifier:
  **`git+https` records `rev` and `narHash` in `devenv.lock`; `git+file`
  records neither and follows the branch head.** A local checkout is therefore
  never pinned, and nothing warns about it.

### Two rules the charter should state, both free

Neither is a change to a claim. Both are the reason the claims hold, and writing
them down is what keeps a later edit from breaking the premise by accident.

1. **The modules take `pkgs` from their consumer.** Not from the flake's own
   `nixpkgs` input, which serves `packages` and `checks` only. This is what
   makes "one flake, two nixpkgs" work: `devenv.lock` carries both trees as
   separate nodes and neither constrains the other. The escape hatch exists —
   `inputs.devman.inputs.nixpkgs` is reachable from a devenv module — and taking
   it would put a second nixpkgs in every consumer's shell.
2. **What the two interfaces share must be text, with one exception.** Queue
   names, `DEVMAN_PROJECT_DIR`, the `.devman/.runs/` path shape, and the
   registry schema are text and cost nothing to share. `nix/dagu.nix` is the
   exception, and B2 measured its price: two store paths, one identical
   155 MB binary, no behaviour difference. Any *other* shared package would pay
   the same duplication with no such guarantee — the machine and the repo differ
   by 465 attributes today, and `sed`, `git`, `python3`, and `bash` all differ in
   version between them, silently.

### What Investigation B did not do

Investigations C and D were not started, as §5 of the prompt requires. Nothing
in `CONCEPT.md` was edited. The machine was not modified: no `nixos-rebuild
switch`, no `/etc/nixos/` edit, and no change to the running Dagu instance. The
test NixOS configurations live in the scratch flake and were built, never
activated.

Three things were seen and deliberately not chased, because each is stage 1 or a
later investigation:

- **NixOS does not restart user services on activation.** `restartTriggers`
  renders `X-Restart-Triggers` into the user unit, so the mechanism §5.2 needs
  exists, but who acts on it for a *user* service on this machine was not
  measured. Stage 1 must answer it, because §5.2 requires the restart to happen
  in the same activation.
- **`enterShell` ran under `devenv shell -- cmd`** in every test here. That is
  Investigation C's C1 and is not recorded as an answer; it was incidental.
- **devenv 2.1.2 is not the current release.** 2.2.2 exists. The `git+file`
  locking result may or may not survive an upgrade.

---

# Investigation C — registration mechanics

**Environment for every C answer unless a section says otherwise.** devenv
2.1.2 (x86_64-linux), Nix 2.34.7, NixOS 26.11.20260705, devman commit
`c9426b6`, on 2026-08-22.

**How the test repos are pinned.** B4 established that `git+file` does not pin
and follows the branch head. This session therefore froze the worktree once,
with `git archive HEAD | tar -x -C /tmp/c-devman-src`, and every test repo
declares `url: "path:/tmp/c-devman-src"`. The frozen tree is `c9426b6` and did
not move while C ran, so mid-session commits could not change a test repo
underneath a measurement. One repo (`/tmp/c-time-git`) uses the `git+https`
form pinned to the same rev, as a control; see C2.

---

## C1 — Does enterShell run on every entry?

**Answer:** **yes.** Every devenv command that gives you an environment runs
`enterShell`, and every one of them registered. No ordinary entry path skips it.
Criterion 17 stands. The commands that do *not* run it — `info`, `eval`,
`build`, `repl`, `search`, `version` — build or inspect the configuration and
never place you in the environment or run repo code, so a repo cannot silently
miss registration through them.

**Tested:** devenv 2.1.2, devman `c9426b6`, on 2026-08-22.

**Method.** `/tmp/c-projA` imports `devman/modules` with
`registryDir = "/tmp/c-registry"`, and adds its own one-line `enterShell` that
appends a marker to `/tmp/c-marker.log`. devenv concatenates every module's
`enterShell` into one script, so the marker and the module's registration hook
are the same script. Before each path the marker log **and** the registry entry
were deleted, so the two columns are independent probes: the marker says the
hook text ran, the registry column says the module's own guard ran and wrote.

**Command:**

```bash
probe() {
  local label="$1"; shift
  rm -f /tmp/c-marker.log /tmp/c-registry/projects/cprojA.json
  ( "$@" ) >/tmp/c-out.log 2>&1; local rc=$?
  ...
}
probe "devenv shell -- true" devenv shell -- true
# ... one probe per row below
```

**Evidence:**

| entry path | rc | `enterShell` runs | registered |
|---|---|---|---|
| `devenv shell -- true` | 0 | **2** | yes |
| `devenv shell`, interactive on a pty | 0 | **2** | yes |
| `devenv shell -- devenv shell -- true` (nested) | 0 | **4** | yes |
| `devenv test` | 0 | **2** | yes |
| `devenv tasks run c:probe` | 0 | **1** | yes |
| `devenv up -d` | 0 | **1** | yes |
| `devenv processes up -d` | 0 | **1** | yes |
| direnv `use devenv`, fresh shell | 0 | **2** | yes |
| direnv, second and third fresh shell | 0 | **2** each | yes each |
| direnv, `cd` out and back in one long-lived shell | 0 | **2** | yes |
| direnv `reload` | 0 | **2** | yes |
| `devenv hook bash` auto-activation | — | via `devenv shell` | yes |
| `devenv info` | 0 | 0 | no |
| `devenv eval devman` | 0 | 0 | no |
| `devenv build packages` | 1 | 0 | no |
| `devenv repl` | 0 | 0 | no |
| `devenv version` / `devenv search` / `devenv gc --help` | 0 | 0 | no |
| `devenv container build shell` | 1 | 0 | no |

`devenv hook bash` is not a separate mechanism. Its generated function ends in
`(cd "$project_dir" && _DEVENV_HOOK_DIR="$project_dir" devenv shell)`, so
auto-activation inherits the `devenv shell` row.

**The direnv rows are the ones that mattered, and they came out clean.** The
worry was a cached env: direnv restoring a saved environment on re-entry and
never re-running `.envrc`. It does not. Deleting `/tmp/c-registry/projects/cprojA.json`
and then re-entering — from a fresh shell, by `cd` out and back inside one
long-lived shell, or by `direnv reload` — re-ran `enterShell` and rewrote the
entry every time:

```
  after first load:   marker=2 reg=cprojA.json
  after cd-out/cd-in: marker=2 reg=cprojA.json
  after direnv reload: marker=2 reg=cprojA.json
```

The single exception is calling `direnv export` twice inside one process with
the environment already loaded, which is a no-op by design and is not an entry.

### enterShell runs twice per `devenv shell`, and it is not a bug in the module

Instrumenting the hook with `$$`, `$PPID` and `/proc/$PPID/comm` showed two
distinct processes running two distinct `.devenv/shell-*.sh` scripts, one the
child of the other, and the child carrying `DEVENV_SKIP_TASKS=1`.

```
MARKER pid=3596842 ppid=3594470 cmdline=[shell -- true] argv0=.../shell-4eb14430df8e8879.sh cmd=.devenv-wrapped
MARKER pid=3594470 ppid=3594459 cmdline=[shell -- true] argv0=.../shell-7ee285ed47d98dda.sh cmd=zsh
```

The reason is in devenv's own source, `devenv/src/devenv/mod.rs:2133`:

```rust
async fn capture_shell_environment(&self) -> Result<HashMap<String, String>> {
    ...
    let script = format!("env -0 > {}", env_path.to_string_lossy());
    ...
    let mut cmd = self.prepare_shell(&Some(script_path...), &[]).await?;
    cmd.env("DEVENV_SKIP_TASKS", "1");
```

devenv runs the **whole shell hook** in a throwaway subprocess whose only
purpose is to snapshot `env`, then runs it again for real.
`run_enter_shell_tasks` calls it, and `main.rs` calls that on the shell, test,
and direnv-export paths. `devenv tasks run` and `devenv up` capture the
environment and stop there, which is why they show 1 rather than 2.

**Two consequences.** Registration is charged twice per entry, which is what C2
measures. And **any side effect in `enterShell` happens twice**, in a subprocess
devenv intends to be observation-only. Registration survives that because the
hash guard makes the second call a no-op, but §5.2 should say so rather than
rely on it.

**Charter impact:** **none for criterion 17 and §5.2's mechanism** — there is
one way in, and every way in takes it. Two additions the charter should carry,
neither a change to a claim:

- §5.2 should state that `enterShell` runs **twice** per `devenv shell` and
  once per `devenv up` / `devenv tasks run`, and that the guard is what makes
  the repeat free. A registration hook that is not idempotent breaks here.
- §5.2's "there is no manual register command" now has a matching operational
  note: to restore a deleted registry, the developer must **enter a shell**,
  not merely `cd` back into a directory whose direnv environment is already
  loaded in the current process.

---

## C2 — What does the guarded no-op cost?

**Answer:** the current guard adds **+23 ms** to a warm `devenv shell -- true`,
because `enterShell` runs twice (C1) and each run forks `sed` and `cat`.
Replacing both with bash builtins drops it to **+4 ms**, which is inside the
noise. Criterion 7's 0.25 s is a separate problem: **bare devenv already costs
231 ms warm on this machine**, so the 0.09 s of headroom the criterion assumes
does not exist, with or without devman.

**Tested:** devenv 2.1.2, devman `c9426b6`, on 2026-08-22, warm cache
(10 warm-up entries per variant, discarded).

**Why the numbers below are paired.** `hyperfine` runs each variant to
completion in turn. This machine's load decayed over the session, so a
sequential run put the drift straight into the comparison — one sweep even
reported the enabled repo as *faster* than the disabled one. Every headline
number here is instead a **paired** measurement: the variants are interleaved
one entry at a time, and the delta is the mean of the per-pair differences,
which cancels drift.

**Command:**

```bash
# /tmp/c-paired.py alternates the variants one entry at a time
N=100 python3 /tmp/c-paired.py \
  "bare_no-devman-input|/tmp/c-time-bare" \
  "off_enable-false|/tmp/c-time-off" \
  "on_current-guard|/tmp/c-time-on" \
  "on_forkfree-guard|/tmp/c-time-fast" \
  "on_current-guard_git+https|/tmp/c-time-git"
```

**Evidence — 100 paired runs, warm:**

```
variant                                          mean      sd   median  runs=100
bare_no-devman-input                            230.9    31.6    238.8
off_enable-false                                250.5    31.2    256.4
on_current-guard                                273.5    35.1    283.5
on_forkfree-guard                               254.9    31.6    263.2
on_current-guard_git+https                      250.0    33.1    257.3

paired delta (off_enable-false)          - (bare) =  +19.63 ms  sd 24.98  95% CI [+14.73, +24.53]
paired delta (on_current-guard)          - (bare) =  +42.63 ms  sd 26.83  95% CI [+37.37, +47.89]
paired delta (on_forkfree-guard)         - (bare) =  +24.02 ms  sd 34.03  95% CI [+17.35, +30.69]
paired delta (on_current-guard_git+https)- (bare) =  +19.06 ms  sd 35.39  95% CI [+12.13, +26.00]
```

Reading the deltas against `off_enable-false`, which is the honest baseline for
"what does registration cost":

| what | cost per warm entry |
|---|---|
| registration, current guard | **+23.0 ms** |
| registration, fork-free guard | **+4.4 ms** |
| importing the module at all, `enable = false` | +19.6 ms |
| using a `path:` input instead of `git+https` | ≈ +23 ms |

Two earlier paired sweeps of the same pair gave +32.2 ms (sd 26.0, n=60) and
+18.7 ms (sd 26.0, n=60) for the current guard, so **+23 ms is the middle of a
+19…+32 ms band** across sweeps. The fork-free guard measured +0.3 ms
(95% CI [−7.1, +7.7], n=60) in the sweep where the current guard measured
+18.7 ms. It is not distinguishable from zero at this sample size.

### Where the cost is

Each firing runs one `sed` and one `cat`. Timed alone, `--shell=none`, 300 runs:

```
sed render (one fork)             2.9 ms ± 0.7 ms
cat registry entry (one fork)     1.5 ms ± 0.7 ms
```

Timed as the guard actually runs it — the whole block, 200 iterations per
sample, 20 samples:

```
current guard x200 (sed + cat)   1.672 s ± 0.050 s     →  8.36 ms per call
fork-free bash guard x200       23.6 ms ± 2.3  ms      →  0.12 ms per call
                                 70.77 ± 7.21 times faster
```

8.36 ms per call × 2 calls per entry = 16.7 ms, against the 23 ms measured
end-to-end; the rest is the two command substitutions' own subshells. **The
comparison itself costs nothing.** The whole cost is the four process forks.

### The cheaper guard

Neither fork is necessary. The template substitution is a bash parameter
expansion, and reading a file into a variable is `$(<file)`, which bash performs
without forking.

```nix
enterShell = ''
  devman_registry="${cfg.registryDir}/projects"
  devman_entry="$devman_registry/${cfg.project}.json"
  devman_tmpl=$(<${entryFile})
  devman_rendered=''${devman_tmpl//@PATH@/$DEVENV_ROOT}

  if [ ! -f "$devman_entry" ] || [ "$(<"$devman_entry")" != "$devman_rendered" ]; then
    mkdir -p "$devman_registry"
    printf '%s\n' "$devman_rendered" > "$devman_entry"
    echo "devman: registered ${cfg.project}"
  fi
'';
```

**This was applied to `modules/devenv.nix` in this session, and the finding is
what justifies it.** The rendered entry is byte-identical to the `sed` version,
and re-entry leaves the file's mtime untouched, so criterion 8 still holds:

```
2026-08-22 08:57:17.172776802 -0400     # after the first entry
2026-08-22 08:57:17.172776802 -0400     # after the second
```

`[` is a bash builtin, so the `-f` test forks nothing either. The remaining
per-entry cost is the two bash string operations, twice.

### Criterion 7 does not survive contact with this machine

The absolute numbers are the uncomfortable part. In one quiet moment, a bare
devenv repo with no devman input at all measured **163.9 ms ± 20.8 ms** (50
runs), which reproduces Spike A's 0.16 s exactly. Under ordinary desktop load,
the same repo measured **230.9 ms** (100 paired runs). Criterion 7 caps
`devenv shell -- true` at 0.25 s warm, and bare devenv is already at 0.23 s.

Neither the module import (+19.6 ms) nor the guarded no-op (+4.4 ms fork-free)
is what puts it over. Ambient machine load is. Spike A's 0.16 s was measured on
a quieter machine than the one that must now hold the criterion.

**Charter impact:** **changes §14, criterion 7.** The criterion must measure a
**delta against the same repo with `devman.enable = false`**, not an absolute
wall-clock number, because the absolute number is dominated by devenv and by
machine load and is not devman's to defend. A concrete replacement: *the module
adds no more than 10 ms to a warm `devenv shell -- true`, measured as a paired
difference against the same repo with `devman.enable = false`.* The fork-free
guard meets that with room to spare; the `sed`-and-`cat` guard does not.

Two further notes for §5.2 and §3.2, both free:

- **`enterShell` must fork nothing.** It runs twice per entry, so every fork is
  charged twice, and this is the one hook on the critical path of every shell
  the developer opens.
- **A `path:` input costs about 23 ms per entry more than `git+https`.** Test
  repos and vendored checkouts pay it; real consumers pinning a published rev
  do not. Worth knowing before a future measurement blames the module for it.

---

## C3 — What state paths does devenv expose in enterShell?

**Answer:** `DEVENV_ROOT`, `DEVENV_DOTFILE`, `DEVENV_STATE`, `DEVENV_PROFILE`
and `DEVENV_RUNTIME` are all set and all documented as read-only. `DEVENV_CMDLINE`,
`DEVENV_TASKS`, `DEVENV_TASK_FILE` and `DEVENV_SKIP_TASKS` are set and
**undocumented**. The registration hook may rely on the first five and must not
rely on the last four.

**Tested:** devenv 2.1.2, devman `c9426b6`, on 2026-08-22.

**Command:** an extra line in the repo's `enterShell`, so the dump is taken from
the module's own vantage rather than from the shell afterwards:

```nix
enterShell = ''
  { echo "--- enterShell vantage, cmdline=[$DEVENV_CMDLINE]"
    env | grep -E "^DEVENV|^IN_NIX_SHELL" | sort; } >> /tmp/c-env.log
'';
```

then `devenv shell -- true`.

**Evidence:** the log holds two blocks, one per firing (C1). The second — the
real shell — is:

```
--- enterShell vantage, cmdline=[shell -- true]
DEVENV_CMDLINE=shell -- true
DEVENV_DOTFILE=/tmp/c-projA/.devenv
DEVENV_PROFILE=/nix/store/yi29ak3165k5bnrxjrp3vs93rm230wad-devenv-profile
DEVENV_ROOT=/tmp/c-projA
DEVENV_RUNTIME=/tmp/devenv-5e57980
DEVENV_STATE=/tmp/c-projA/.devenv/state
DEVENV_TASK_FILE=/nix/store/60aly8aw5zhhyvcz9pxm0clg6jz4him5-tasks.json
DEVENV_TASKS=
IN_NIX_SHELL=impure
```

The first block is identical except that it also carries `DEVENV_SKIP_TASKS=1`.
That is the environment-capture subprocess from C1.

**Documented or incidental.** Checked against devenv's own tree at the rev this
repo locks, `github:cachix/devenv` `5844e78`, file
`docs/src/reference/environment-variables.md`:

| variable | value shape | status |
|---|---|---|
| `DEVENV_ROOT` | the project root | **documented**, read-only, added in 0.2 |
| `DEVENV_DOTFILE` | `$DEVENV_ROOT/.devenv` | **documented**, read-only, added in 0.1 |
| `DEVENV_STATE` | `$DEVENV_DOTFILE/state` | **documented**, read-only, added in 0.1 |
| `DEVENV_RUNTIME` | `/tmp/devenv-<hash>`, or under `$XDG_RUNTIME_DIR` | **documented**, read-only, added in 1.0 |
| `DEVENV_PROFILE` | the store path of the assembled profile | **documented**, read-only, added in 0.5 |
| `DEVENV_CMDLINE` | the devenv subcommand and its arguments | **incidental** — no docs entry; set in `devenv/src/shell_env.rs:49` |
| `DEVENV_TASKS` | empty here | **incidental** — one hit in `src/modules`, none in docs |
| `DEVENV_TASK_FILE` | store path of `tasks.json` | **incidental** — no docs entry |
| `DEVENV_SKIP_TASKS` | `1` in the capture subprocess only | **incidental** — one hit, `src/modules/tasks.nix:448` |

`$DEVENV_STATE` is available, so the answer to the question as the kickoff asked
it is yes. The module uses `$DEVENV_ROOT` and nothing else, which is the most
documented and oldest of the five.

**One temptation to record and refuse.** `DEVENV_SKIP_TASKS` distinguishes the
capture subprocess from the real shell, so a hook could use it to run once per
entry instead of twice. **Do not.** It is undocumented, it exists to serve
devenv's task runner, and a guard that is idempotent needs no such test. The
correct fix for the double cost is the fork-free guard from C2, not a probe of
devenv's internals.

**Charter impact:** **none.** §5.2 relies on `$DEVENV_ROOT` only, which is
documented and stable. One rule the charter should state: **the registration
hook may use `DEVENV_ROOT`, `DEVENV_DOTFILE`, `DEVENV_STATE`, `DEVENV_PROFILE`
and `DEVENV_RUNTIME`, and nothing else from the `DEVENV_*` namespace.**

---

## C4 — Can the module add `.devman/.runs/` to the ignore rules safely?

**Answer:** **`.gitignore` is not safe and `.git/info/exclude` is.** Appending
to `.gitignore` works on two of the three shapes and fails on the third — a
`.gitignore` symlinked into the Nix store is read-only, and the hook prints a
permission error on **every** shell entry, forever, because the guard can never
see its own line. `.git/info/exclude` works on all three, never dirties the
tree, and is the recommendation. devenv is a second writer to `.gitignore`, but
only through `devenv init`, and it appends rather than clobbers.

**Tested:** devenv 2.1.2, git 2.x on NixOS 26.11, devman `c9426b6`, on 2026-08-22.

**Command:** two candidate hooks, run against four repo shapes. Both guard on
the line already being present, and both avoid `grep` for the reason C2 gives.

```bash
# candidate A — .gitignore
line='.devman/.runs/'
gi="$DEVENV_ROOT/.gitignore"
cur=""; [ -f "$gi" ] && cur=$(<"$gi")
if [[ $'\n'"$cur"$'\n' != *$'\n'"$line"$'\n'* ]]; then printf '%s\n' "$line" >> "$gi"; fi

# candidate B — .git/info/exclude
ex=$(git -C "$DEVENV_ROOT" rev-parse --git-path info/exclude 2>/dev/null) || exit 0
case "$ex" in /*) ;; *) ex="$DEVENV_ROOT/$ex" ;; esac
cur=""; [ -f "$ex" ] && cur=$(<"$ex")
if [[ $'\n'"$cur"$'\n' != *$'\n'"$line"$'\n'* ]]; then printf '%s\n' "$line" >> "$ex"; fi
```

**Evidence:**

| repo shape | `.gitignore` | `.git/info/exclude` |
|---|---|---|
| no `.gitignore` | creates it, one line | appends, one line |
| hand-written `.gitignore` | **appends, keeps every existing line** | appends |
| `.gitignore` → `/nix/store/...` symlink | **`Permission denied`** | appends |
| no `.git` at all | creates a `.gitignore` in a non-repo | skips, says so |

The hand-written case is not clobbered:

```
# my ignore file
*.pyc
/build/
.devman/.runs/
```

The symlinked case is:

```
/tmp/c4/hook-gitignore.sh: line 7: /tmp/c4/symlinked/.gitignore: Permission denied
```

and the file is unchanged, so the guard fails the same way on the next entry,
and the next. Both hooks are idempotent on a second run — silent, no second
line — except that the `.gitignore` hook on a store symlink can never become
idempotent.

**A failing write does not stop shell entry.** Worth knowing before deciding how
loud a failure may be. `enterShell` does not run under `set -e`:

```
before-failure
/tmp/c4-fail/.devenv/shell-81d0151e0df9735c.sh: line 2347: /nix/store/...: Permission denied
after-failure
SHELL-ENTERED-OK
rc=0
```

So the symlinked case is noise on every entry, not a broken repo. That makes it
easier to miss, not easier to live with.

**Both mechanisms actually work.** In the hand-written repo, after the rule was
added, `git status --porcelain` reported only `?? .gitignore` — the run
directory itself was ignored.

**And that `?? .gitignore` is the second argument against `.gitignore`.**
`.gitignore` is a *tracked* file. Adding the rule makes the working tree dirty
until the developer commits it. §9.2 adds the ignore rule precisely so that
"an un-ignored `.runs/` turns the first failed run into a dirty tree" — writing
the rule into a tracked file trades one dirty tree for another.

### devenv is a second writer, and a well-behaved one

From devenv's own `devenv/src/commands/init.rs`:

```rust
/// Append to the file (with a leading newline). Used for `.gitignore`
/// so we don't clobber existing ignore entries.
Append,
...
Template { source: "gitignore", target: ".gitignore", on_exists: OnExists::Append },
```

Its bundled template is `.devenv*`, `devenv.local.nix`, `devenv.local.yaml`,
`.direnv`, `.pre-commit-config.yaml`. It is written **only by `devenv init`**,
never at shell entry — no `.gitignore` reference exists anywhere else in
devenv's sources. So the two writers cannot race, but they do both append to one
tracked file, and a developer re-running `devenv init` gets devenv's block
appended a second time.

### One caveat on `.git/info/exclude`: it is not per-checkout in a git worktree

`.git/info/exclude` is per-clone, which is what §9.2 wants — run output belongs
to a working tree. But git treats `info/` as a **common** path, so a linked
`git worktree` shares the main repository's exclude file:

```
$ cd /tmp/c4/wt-linked && git rev-parse --git-path info/exclude
/tmp/c4/wt-main/.git/info/exclude
```

and the linked worktree's private directory has no `info/` of its own
(`commondir gitdir HEAD index logs ORIG_HEAD refs`). Writing the rule from one
worktree therefore writes it for all of them. The rule is `.devman/.runs/`, which
is correct in every worktree of the same repository, so this is harmless — but
it must be stated, because it means "per checkout" is really "per clone".

Using `git rev-parse --git-path info/exclude` rather than a literal
`.git/info/exclude` is what makes the worktree case work at all: in a linked
worktree, `.git` is a **file**, not a directory, so the literal path does not
exist.

**Charter impact:** **changes §9.2.** The sentence "The devenv module adds the
ignore rule at registration" must name the file: **the rule goes in
`.git/info/exclude`, located with `git rev-parse --git-path info/exclude`, not
in `.gitignore`.** Three reasons, in order: `.gitignore` may be read-only, it is
tracked and so the write dirties the tree it is meant to keep clean, and it is
shared with devenv's own `devenv init`. The registry being derived (§9.3) is
what makes a per-clone rule sufficient — a fresh clone re-registers, and
re-registration re-adds the rule.

One cost to accept: a repo with no `.git` gets no ignore rule. That is correct.
There is nothing to ignore.

---

## C5 — Two repos both declaring `project = "test"`. Refuse or replace?

**Answer:** **refuse — but only when the recorded path still exists.** Refuse is
the recommendation for a reason that is not a matter of taste: **replace is
silent and refuse is not**, as a direct consequence of C1's double firing. And
the charter's contradiction resolves in §5's favour: `project` is stated, never
defaulted from the directory name, because §9.1's directory-name default cannot
survive criterion 11.

**Tested:** devenv 2.1.2, devman `c9426b6`, on 2026-08-22.

### What the current module does: replace, silently, on every entry

`/tmp/c5-A` and `/tmp/c5-B` both declare `project = "test"` and share a registry.

**Command:**

```bash
for i in 1 2 3; do for d in A B; do
  (cd /tmp/c5-$d && devenv shell -- true)
  jq -r .path /tmp/c5-registry/projects/test.json
done; done
```

**Evidence:**

```
entry 1 into c5-A: <silent, no write>  registry path = /tmp/c5-A
entry 1 into c5-B: <silent, no write>  registry path = /tmp/c5-B
entry 2 into c5-A: <silent, no write>  registry path = /tmp/c5-A
entry 2 into c5-B: <silent, no write>  registry path = /tmp/c5-B
entry 3 into c5-A: <silent, no write>  registry path = /tmp/c5-A
entry 3 into c5-B: <silent, no write>  registry path = /tmp/c5-B
```

One registry file, `test.json`, whose `path` flips on every shell entry. Every
projection built from it points at whichever repo was entered last. Two
developers, or one developer in two terminals, would see workflows run in the
other repo with no indication that anything is wrong.

### Replace cannot announce itself. Refuse can.

`<silent, no write>` above is not a reporting artefact. The module ends its
write branch with `echo "devman: registered ${cfg.project}"`, and **the
developer never sees it**, not even on a genuine first registration:

```
$ rm -f /tmp/c5-registry/projects/test.json
$ cd /tmp/c5-A && devenv shell -- true 2>&1 | grep -v "out of date" | cat -A
                                    <- nothing at all
$ ls /tmp/c5-registry/projects/
test.json                           <- it registered
```

C1 explains it. The **first** firing is devenv's environment-capture subprocess,
whose stdout is redirected into a temporary `env -0` file and thrown away. That
firing does the write. By the time the **second**, real firing runs, the entry on
disk already matches, so the guard takes the no-op branch and says nothing.
**Every one-shot message a registration hook emits is invisible, on stdout and
on stderr alike.**

A refusal does not have that problem, because refusing means **not writing**.
Both firings reach the same branch, and the second one is the real shell:

```
devman: refusing to register 'test'
devman:   already registered at /tmp/c5-refA, which still exists
devman:   this repo is        /tmp/c5-refB
devman:   set a different devman.project in one of them
```

Printed once, visible, and the registry stayed at `/tmp/c5-refA`.

**This is the argument.** A policy whose interesting case is a *write* announces
itself into a discarded stream. A policy whose interesting case is a *refusal to
write* announces itself to the developer. Choose refuse.

### What distinguishes a move from a collision

Criterion 11 requires that a moved or renamed repo keep its identity, and §9.2
allows one project to be checked out twice. To the registry, "the same project
from a new path" and "two projects sharing a name" look alike — both are an
entry whose `path` differs from `$DEVENV_ROOT`.

**The distinguishing fact is whether the recorded path still exists.** It costs
one `[ -d ]`, which is a bash builtin and forks nothing.

| recorded path | this repo | reading | action |
|---|---|---|---|
| absent from disk | anywhere | the project moved (criterion 11) | **replace** |
| exists, equals `$DEVENV_ROOT` | same | nothing changed, or the groups changed | write if different |
| exists, differs | different | two live checkouts claim one identity | **refuse and report** |

Implemented in a scratch copy of the module and exercised:

```nix
if [ -n "$devman_recorded" ] && [ "$devman_recorded" != "$DEVENV_ROOT" ] \
   && [ -d "$devman_recorded" ]; then
  echo "devman: refusing to register '${cfg.project}'" >&2
  ...
else
  printf '%s\n' "$devman_rendered" > "$devman_entry"
fi
```

Criterion 11, end to end — the repo was moved **and** renamed, then re-entered:

```
$ mv /tmp/c5-refA /tmp/c5-renamed-elsewhere
$ cd /tmp/c5-renamed-elsewhere && devenv shell -- true
  registry path = /tmp/c5-renamed-elsewhere      <- identity kept, entry rewritten
$ cd /tmp/c5-refB && devenv shell -- true
devman: refusing to register 'test'
devman:   already registered at /tmp/c5-renamed-elsewhere, which still exists
  registry path = /tmp/c5-renamed-elsewhere      <- collision still refused
```

The refusal is not fatal: C4 established that `enterShell` runs without `set -e`,
so the repo's shell still opens. The repo simply is not in the plane, which is
the correct outcome for a repo whose identity is already taken.

**Two live checkouts of the genuinely same project also refuse, and that is
correct.** §9.2 says run output belongs to a working tree, and run output is
repo-side and unaffected by this. The registry holds one `path` per project, so
two checkouts cannot both be it. The second checkout must state a distinct
`project`.

**One limit to record.** This test cannot tell a *deleted* repo from an
*unmounted* one. If the recorded path is on a filesystem that is not mounted,
the entry is replaced and the original checkout is dropped from the registry
until it is next entered. Since the registry is derived (§9.3), re-entering
restores it, so the failure is recoverable rather than lossy.

### The charter contradicts itself, and §5 wins

- §5: "`project` is stated, never inferred from the directory name — identity
  that depends on where a checkout sits changes when you rename the directory."
- §9.1: "Identity defaults to the repo's directory name. Registration refuses a
  duplicate."

`modules/devenv.nix` follows §5: `project` is `types.str` with no default, so
omitting it is an evaluation error.

**§5 wins, and criterion 11 is why.** A directory-name default breaks criterion
11 by construction: rename the directory and the default changes, so the repo
re-registers as a new project and loses its run history. §9.1's own next
paragraph — "this is what makes moving a repo … work without editing a
workflow" — argues against §9.1's own default.

§9.1's second sentence survives intact and is the answer to this question:
"registration refuses a duplicate."

**Charter impact:** **changes §9.1.** Delete "Identity defaults to the repo's
directory name", keep "registration refuses a duplicate", and add the test that
makes refusal compatible with criterion 11: **a duplicate is refused only when
the recorded path still exists; a recorded path that is gone means the project
moved, and the entry is replaced.**

Also **changes §5.2**, for a reason C5 discovered rather than assumed: **a
registration hook cannot report anything on the write path**, because devenv
discards the output of the firing that does the write. §5.2 must not promise a
"devman: registered" line. Anything the developer must see has to be on a path
that does **not** write — a refusal, or `devman doctor`.

---

## C6 — A repo is deleted from disk without unregistering. How does the registry notice?

**Answer:** **it does not notice, and Dagu does not either — it recreates the
deleted directory and reports success.** That is worse than a failure. Detection
belongs to `devman doctor`, it costs one `[ -d ]` per entry, it needs no
filesystem scan, and §9.3 makes pruning safe rather than merely cheap: a wrongly
pruned entry restores itself on the repo's next shell entry.

**Tested:** devenv 2.1.2, dagu 2.15.0, devman `c9426b6`, on 2026-08-22.

### The registry after the delete

**Command:**

```bash
# two repos register, then one is deleted from disk
rm -rf /tmp/c6-projY
ls /tmp/c6-reg/projects/
(cd /tmp/c6-projX && devenv shell -- true)
```

**Evidence:**

```
registry after the delete:
c6projX.json
c6projY.json
  c6projY.json still says: {"groups":["base"],"path":"/tmp/c6-projY","project":"c6projY","schema":1}

=== re-entering projX does not notice, and must not ===
registry unchanged: c6projX.json  c6projY.json
```

The entry is intact and points at nothing. Nothing in the registration path can
see it: registration runs in the shell of the repo that is entering, and the
deleted repo will never enter a shell again. Re-entering a *different* repo must
not touch a neighbour's entry, and does not.

### What breaks: nothing, loudly. Dagu recreates the directory.

This was the case worth measuring, and the result is the opposite of the
expected one.

**Command:**

```bash
# $DAGU_HOME/dags/c6_stale.yaml
#   working_dir: /tmp/c6-projGONE
#   steps: [{ name: where, command: "/run/current-system/sw/bin/pwd -P; ls -a .; touch ./sentinel && echo WROTE" }]
rm -rf /tmp/c6-projGONE
[ -e /tmp/c6-projGONE ] && echo "still there" || echo "confirmed deleted"
dagu start c6_stale
ls -la /tmp/c6-projGONE
```

**Evidence:**

```
confirmed deleted
...
└─where (0s) [succeeded]
Result: Succeeded

stdout:
    /tmp/c6-projGONE
    PWD=/tmp/c6-projGONE
    .
    ..
    WROTE

after the run:
.rw-r--r-- 0 andrew 22 Aug 09:07 sentinel
```

**Dagu created the missing `working_dir` and ran the workflow in it.** The run
succeeded. The step's own `ls -a` shows an empty directory — `.` and `..` and
nothing else. The deleted repository's path is now back on disk as an empty
directory containing whatever the workflow wrote.

`dagu validate` does not catch it either:

```
$ dagu validate $DAGU_HOME/dags/c6_stale.yaml >/dev/null 2>&1; echo $?
0
```

So the stale-entry failure mode is: **a scheduled workflow keeps succeeding,
against an empty directory, at the path of a repository that no longer exists.**
Every check E5 gave `doctor` — `dagu validate` per file, the queue `conditions`,
`FRESH` — reports healthy. A build workflow finds no sources and its `check`
step passes vacuously; a workflow that writes finds a writable directory and
writes there.

### Detection is `doctor`'s job, and §9.3 is what makes the fix safe

§15.1 forbids solving registration by scanning the filesystem for repos. **This
is not that.** Reading `~/.local/share/devman/projects/` is reading devman's own
state, and it is O(registered projects), not O(the disk):

```bash
for f in /tmp/c6-reg/projects/*.json; do
  p=$(jq -r .path "$f")
  [ -d "$p" ] && echo "live  $(basename $f) $p" || echo "STALE $(basename $f) $p"
done
```

```
  live  c6projX.json  /tmp/c6-projX
  STALE c6projY.json  /tmp/c6-projY
```

That is the whole check. It cannot be done by registration — registration only
ever sees one repo, the one entering — so it is `doctor`'s (§10, §15.3).

**§9.3's cheap answer is the right one, and it is stronger than "cheap".**
Because the registry is derived and the repository is canonical, pruning a
stale entry **cannot lose anything**. If `doctor` prunes an entry whose path is
temporarily absent — an unmounted disk, a detached external drive — the repo
re-registers the next time its shell is entered, because C1 established that
every entry path registers. So `doctor` may prune automatically, not merely
report. That is a stronger guarantee than §10 currently claims for any other
`doctor` action.

**Charter impact:** **changes §10 and §15.2's neighbourhood; none for §9.3,
which is vindicated.** Three additions:

- §10: `devman doctor` gains a stale-entry check — every registry entry whose
  `path` is not a directory — and may **prune** rather than only report, because
  §9.3 makes pruning non-destructive and C1 makes restoration automatic.
- §10: `doctor` must also unproject the pruned project's workflows. Pruning the
  registry entry alone leaves the projection, and E5's checks all pass on a
  projected DAG whose `working_dir` is gone.
- §7.2 or §9.2 should record the Dagu behaviour that makes this urgent:
  **Dagu creates a missing `working_dir` and succeeds.** It does not fail, and
  `dagu validate` does not flag it. Nothing except this check will ever notice.

There is still **no `devman unregister`**, and none is needed. Criterion 17
survives: the way out is deleting the repository, and `doctor` is what reconciles
the derived state afterwards.

---

## C7 — Does NixOS restart a systemd *user* service on activation?

**Answer:** **yes, on this machine's nixpkgs, and §5.2's requirement is met.**
`switch-to-configuration` visits the user scope, spawns itself as each user
logind lists, and stops-then-starts a user unit whose file changed — which a
`restartTriggers` change is, because it rewrites the `X-Restart-Triggers=` line.
**No extra mechanism is needed.** Investigation B's parenthetical — "NixOS does
not restart user services on activation" — is wrong for nixpkgs
`26.11.20260705.d407951`.

But §5.2's *description of the symptom* is wrong, and that half is a real change.
When the restart does not happen, **nothing reports an error**. The run is
accepted, it runs, and the only trace is a line in the server's own log giving
the wrong concurrency.

**Tested:** nixpkgs `26.11.20260705.d407951` (the tree `nixos-rebuild` uses on
this machine), dagu 2.15.0, devman `c9426b6`, on 2026-08-22. Run in a
throwaway NixOS test VM. **The machine was not modified**: no `nixos-rebuild
switch`, no `/etc/nixos/` edit, and the real Dagu instance was never contacted.

**Command:**

```bash
cd .scratch/projects/006-automation-plane/c-scratch
nix build .#checks.x86_64-linux.c7
```

The scratch flake defines one node importing this repo's
`nix/nixos-module.nix`, plus a **`specialisation`** carrying the only
difference — `services.devman-dagu.queues` gains `light = 4` and `heavy = 2`.
A specialisation rather than a second `nixosConfiguration` is deliberate: the
two generations then differ in exactly one thing, so a restart that happens can
only be the unit file change. The user is `tester` with `linger = true`, so a
user manager exists and logind lists them.

### 1. Does activation act on a user unit at all? Yes.

**Evidence — `switch-to-configuration test`, stdout verbatim:**

```
Checking switch inhibitors... done
activating the configuration...
setting up /etc...
reloading user units for tester...
stopping the following user units: dagu.service
starting the following user units: dagu.service
restarting the following user units: nixos-activation.service
restarting sysinit-reactivation.target
reloading the following units: dbus-broker.service
the following new units were started: sysinit-reactivation.target, systemd-tmpfiles-resetup.service
```

and the VM's journal, from the **user** manager (`systemd[620]`, not PID 1):

```
systemd[620]: Stopping Dagu — devman automation plane...
dagu[712]: level=INFO msg="Received shutdown signal" signal=terminated
systemd[620]: Stopped Dagu — devman automation plane.
systemd[620]: Reexecution requested from client PID 954 ('switch-to-confi')...
systemd[620]: Reloading...
systemd[620]: Starting Dagu — devman automation plane...
systemd[620]: Started Dagu — devman automation plane.
```

The service restarted **inside the activation**, before
`switch-to-configuration` returned:

```
X-Restart-Triggers (A) = /nix/store/sxlpv98vpx8d7yxd4802pn1bj0sc87wc-X-Restart-Triggers-dagu
X-Restart-Triggers (B) = /nix/store/mjscgga9fjv3258kv18kscpvgidwy7f4-X-Restart-Triggers-dagu
unit file changed : True
trigger changed   : True
dagu InvocationID (A) = ec6f3f7baa8148ff8dbedf7b1f5051a9   MainPID (A) = 712
dagu InvocationID (B) = 35a15d12f8da485bbc942ee82aa64032   MainPID (B) = 972
>>> RESTARTED IN THE SAME ACTIVATION: True
config.yaml rewritten: True
```

`config.yaml` was rewritten because the unit's `ExecStartPre` reinstalls it, and
`ExecStartPre` ran because the unit restarted. **The two facts §5.2 needs to
happen together did happen together.**

### 2. Why it works, from the source rather than from the option's existence

`pkgs/by-name/sw/switch-to-configuration-ng/src/main.rs` in the machine's
nixpkgs, 3107 lines. Two things matter.

**`X-Restart-Triggers` is never read by name.** Searching the file finds only
`X-Reload-Triggers`, nine times. `restartTriggers` needs no special handling:
it renders a line into the unit file, the unit file therefore differs between
generations, and the generic "this unit changed → restart it" path fires.
`X-Reload-Triggers` is the one that needs special handling, because it must
downgrade a restart to a reload.

**The user scope runs the same comparison as the system scope.** After the
system units are done, the main path iterates logind's users and re-executes
itself as each one:

```rust
// Reload user units
match logind.list_users() {
    ...
    for (uid, name, user_dbus_path) in users {
        eprintln!("reloading user units for {name}...");
        let status = std::process::Command::new(&myself)
            .uid(uid).gid(gid).env_clear()
            .env("XDG_RUNTIME_DIR", runtime_path)
            .env("__NIXOS_SWITCH_TO_CONFIGURATION_PARENT_EXE", &myself)
            .env("TOPLEVEL", &toplevel).env("OLD_TOPLEVEL", &old_toplevel)
            .env("NIXOS_ACTION", Into::<&'static str>::into(action))
            .spawn()...
```

The child runs `do_user_switch`, which builds `UnitScope::User`
(`etc/systemd/user`, `/etc/systemd/user`) and then calls the **same**
`collect_unit_changes` the system scope calls, with the same
`units_to_stop` / `units_to_start` / `units_to_restart` / `units_to_reload`
maps. That is why the mechanism works and why nothing devman-specific is needed.

**Two boundaries, both from that code.**

- **Only users logind lists.** A user who is neither logged in nor lingering has
  no user manager, so nothing is restarted for them — and nothing was running
  for them either, so there is no divergence. The unit is correct the next time
  they log in. `linger = true` is what makes a headless machine's Dagu both run
  and get restarted; the test VM sets it.
- **Units shadowed by `~/.config/systemd/user` are deferred**, not skipped: pass
  1 filters them by `FragmentPath`, and pass 2 acts once the per-user activation
  (home-manager's `sd-switch`) has removed its copy. A repo-side or
  home-manager-side `dagu.service` would therefore shadow the NixOS one until
  that second pass. Worth knowing; not a problem for §4 as written.

`systemd.user.startServices` does not exist in this nixpkgs — `grep -rn
startServices nixos/` returns nothing. It is a home-manager option, not a NixOS
one, and it is not the mechanism here.

### 3. What the developer sees when the restart does not happen

Built by hand, so the answer exists on record independently of question 1:
generation A's server left running, generation B's `config.yaml` installed
underneath it, then a workflow enqueued to the queue only generation B knows.

```yaml
# generation A's config.yaml — what the server is running
queues:
  config:
  - max_concurrency: 1
    name: exclusive
  enabled: true

# generation B's config.yaml — what is on disk
queues:
  config:
  - max_concurrency: 1
    name: exclusive
  - max_concurrency: 2
    name: heavy
  - max_concurrency: 4
    name: light
  enabled: true
```

```
$ dagu enqueue c7probe --run-id c7run1        # c7probe declares `queue: light`
level=INFO msg="Enqueued dag-run" dag=c7probe run-id=c7run1 params=[]     rc=0

$ dagu status c7probe
Status: Running                                                          rc=0

$ dagu ps
DAG      RUN_ID  ATTEMPT  STARTED               GROUP  FRESH
c7probe  c7run1  5ec7e2   2026-08-22T13:18:51Z  light  yes
```

**Everything reports success.** No error, no warning, no non-zero exit, and
`dagu ps` even prints `GROUP=light` as though the queue were real. The single
trace of the divergence is one line in the server's own log:

```
level=INFO msg="Processing batch of items" queue=light count=1 max-concurrency=1 alive=0
```

**`max-concurrency=1`.** The queue was configured for 4. After a restart, the
same DAG, the same command, the same config file on disk:

```
level=INFO msg="Processing batch of items" queue=light count=1 max-concurrency=4 alive=1
```

So the failure mode of a missed restart is not an error message — it is **a
queue silently running at the wrong concurrency**, at `INFO` level, in a log
nobody reads. That is §15.4's "a misspelled queue is not a migration problem, it
is an unobservable one", arriving by a second route: a queue that is spelled
correctly and simply has not reached the server yet.

### 4. What the charter must change

**Charter impact:** **changes §5.2**, in two places, and **none for §4** or the
module.

- **The requirement is met, not merely stated.** §5.2's "a machine module that
  rewrites `config.yaml` must restart the service in the same activation" is
  satisfied by `restartTriggers` alone, on nixpkgs 26.11.20260705. §5.2 should
  say so and name the nixpkgs revision the answer was measured on, because it is
  a property of `switch-to-configuration`, not of NixOS in general — and
  Investigation B's note assuming otherwise should be struck.
- **The symptom description is wrong.** §5.2 says the CLI "honours the new
  config while the server does not — reporting an error that names the very
  setting you already added". Measured: **no error is reported at all.** The
  enqueue succeeds, the run runs, and the queue silently takes a concurrency the
  developer did not configure. Replace the sentence with the measured symptom.
- **§4 or §5.2 should require `users.users.<name>.linger = true`** for the user
  that owns the plane, or state that the plane is only live while that user is
  logged in. The restart mechanism reaches exactly the users logind lists.

**`kills §5.2` was a live outcome and did not happen.** The guarantee holds.

---

## Summary — Investigation C, registration mechanics

**`enterShell` is a sound place to put the only way into the registry.** No
ordinary entry path skips it, the guarded no-op is free once it stops forking,
and §5.2's activation requirement turned out to be met rather than broken.
Criterion 17 stands.

Four things the charter did not know, and three of them are the reason a claim
has to change:

1. **`enterShell` runs twice per `devenv shell`**, the first time in a
   subprocess devenv uses only to snapshot `env` and then discards. Every side
   effect happens twice, and **every message printed on the write path is
   invisible**.
2. **Dagu creates a missing `working_dir` and reports success.** A stale
   registry entry never fails; it litters.
3. **A missed `config.yaml` restart reports no error.** It silently runs a queue
   at the wrong concurrency.
4. **NixOS does restart a systemd user service on activation**, on this
   machine's nixpkgs. B's note to the contrary is wrong.

| ID | Question | Answer | Charter impact |
|---|---|---|---|
| C1 | does `enterShell` run on every entry? | **yes** — every path that gives an environment fires it and registers | **changes §5.2** (additions; the claim and criterion 17 stand) |
| C2 | what does the guarded no-op cost? | **+23 ms** as written, **+4 ms** fork-free | **changes §14, criterion 7** |
| C3 | what state paths does devenv expose? | five documented, four incidental; `$DEVENV_STATE` is set | none |
| C4 | can the ignore rule be added safely? | **not via `.gitignore`** — use `.git/info/exclude` | **changes §9.2** |
| C5 | duplicate `project` — refuse or replace? | **refuse**, when the recorded path still exists | **changes §9.1**, **changes §5.2** |
| C6 | how does the registry notice a deleted repo? | **it does not, and neither does Dagu** — `doctor`'s job, and pruning is safe | **changes §10**, **changes §7.2/§9.2** |
| C7 | does activation restart a user service? | **yes** — §5.2's requirement is met | **changes §5.2** (twice), **changes §4** |

### The timing number, with its spread

100 paired runs, warm cache, interleaved one entry at a time so machine drift
cancels. devenv 2.1.2, devman `c9426b6`, 2026-08-22.

| variant | mean | sd | delta vs `enable = false` |
|---|---|---|---|
| bare devenv repo, no devman input | 230.9 ms | 31.6 | — |
| module imported, `devman.enable = false` | 250.5 ms | 31.2 | — |
| **registered, current `sed`+`cat` guard** | **273.5 ms** | 35.1 | **+23.0 ms** |
| **registered, fork-free bash guard** | **254.9 ms** | 31.6 | **+4.4 ms** |

95% CI against the bare baseline: current guard `[+37.4, +47.9]`, fork-free
`[+17.4, +30.7]`, `enable = false` `[+14.7, +24.5]`. Two earlier paired sweeps
of n=60 put the current guard's cost at +32.2 ms and +18.7 ms, so **+23 ms is
the middle of a +19…+32 ms band**. Component cost, 200 iterations per sample:
current guard **8.36 ms per call**, fork-free guard **0.12 ms per call**, 71×.

**Criterion 7's 0.25 s is not devman's to defend.** A bare devenv repo measured
163.9 ms on a quiet machine — Spike A's 0.16 s, reproduced exactly — and
230.9 ms under ordinary desktop load. The criterion must become a delta.

### The two recommendations the kickoff asked for

**C5 — refuse.** Refuse a duplicate only when the recorded path still exists on
disk; a recorded path that is gone means the project moved, and the entry is
rewritten. The argument is not symmetry with §9.1: it is that **replace cannot
announce itself**. devenv discards the output of the firing that performs the
write, so a replacing registration is silent by construction, while a refusing
one prints from the real shell. Measured both ways.

**C7 — no mechanism is needed.** `systemd.user.services.<name>.restartTriggers`
is sufficient on nixpkgs 26.11.20260705. It rewrites the unit file;
`switch-to-configuration` spawns itself per logind user and runs the same
`collect_unit_changes` the system scope runs; the unit stops and starts inside
the activation. The candidates the kickoff listed — `systemd.user.startServices`
(does not exist in NixOS), `reloadTriggers`, a path unit, a user activation
hook, a re-readable `config.yaml` — are all unnecessary. **One requirement
does follow:** `users.users.<name>.linger = true`, because the restart reaches
exactly the users logind lists.

### Every `changes §N` and `deletes §N` in one place

- **changes §5.2 — `enterShell` runs twice.** Once in devenv's environment-capture
  subprocess (`devenv/src/devenv/mod.rs`, `capture_shell_environment`), once for
  real. `devenv up` and `devenv tasks run` fire it once. State that the hash
  guard is what makes the repeat free, and that a hook which is not idempotent
  breaks here. (C1)
- **changes §5.2 — the hook must fork nothing.** It is on the critical path of
  every shell the developer opens and its cost is charged twice. (C1, C2)
- **changes §5.2 — a registration hook cannot report on the write path.** Drop
  any promise of a "devman: registered" line: the firing that writes has its
  stdout and stderr discarded, and the firing the developer sees takes the no-op
  branch. Anything the developer must see has to be on a non-writing path — a
  refusal, or `devman doctor`. (C5)
- **changes §5.2 — restoring a deleted registry means entering a shell**, not
  `cd`-ing back into a directory whose direnv environment is already loaded in
  the current process. (C1)
- **changes §5.2 — the activation requirement is met.** `restartTriggers` alone
  restarts the user service in the same activation on nixpkgs
  `26.11.20260705.d407951`. Name the revision; it is a property of
  `switch-to-configuration`, not of NixOS in general. Strike B's note assuming
  otherwise. (C7)
- **changes §5.2 — the symptom description is wrong.** A missed restart does
  **not** report "an error that names the very setting you already added". It
  reports nothing: the enqueue succeeds, the run runs, and the queue silently
  takes the wrong concurrency — `max-concurrency=1` where 4 was configured. (C7)
- **changes §14, criterion 7.** Measure a **delta against the same repo with
  `devman.enable = false`**, not an absolute wall-clock number. Proposed: *no
  more than 10 ms added to a warm `devenv shell -- true`, as a paired
  difference*. Bare devenv already sits at 0.23 s under load, so the absolute
  0.25 s cap is not a statement about devman. (C2)
- **changes §9.1.** Delete "Identity defaults to the repo's directory name" — it
  breaks criterion 11 by construction, and §5 already says the opposite. Keep
  "registration refuses a duplicate", and add the test that makes refusal
  compatible with criterion 11: **refuse only when the recorded path still
  exists**. (C5)
- **changes §9.2 — name the ignore file.** The rule goes in
  **`.git/info/exclude`**, located with `git rev-parse --git-path info/exclude`,
  not in `.gitignore`. `.gitignore` may be a read-only store symlink, it is
  tracked so writing to it dirties the tree it exists to keep clean, and devenv
  writes to it too (`devenv init`, appending). One accepted cost: a repo with no
  `.git` gets no rule, which is correct. One caveat: git treats `info/` as a
  common path, so a linked `git worktree` shares its main repository's exclude
  file — "per checkout" is really "per clone". (C4)
- **changes §7.2 or §9.2 — record what Dagu does with a missing `working_dir`.**
  **It creates the directory and succeeds.** `dagu validate` exits 0. A workflow
  projected from a stale registry entry keeps passing, in an empty directory, at
  the path of a repository that no longer exists. (C6)
- **changes §10 — `doctor` gains a stale-entry check**, and may **prune** rather
  than only report. Every registry entry whose `path` is not a directory is
  stale; the check is O(registered projects) and reads only devman's own state,
  so §15.1's ban on scanning does not apply. §9.3 is what makes pruning safe: a
  wrongly pruned entry restores itself on the repo's next shell entry. `doctor`
  must also unproject the pruned project's workflows. (C6)
- **changes §4 (or §5.2) — require `users.users.<name>.linger = true`** for the
  user that owns the plane, or state that the plane is live only while that user
  is logged in. `switch-to-configuration` reaches exactly the users logind
  lists. (C7)

**Nothing in C `deletes` or `kills` a section.** `kills §5.2` was a live outcome
on C7 and did not happen.

### One rule the charter should state, free

**The registration hook may use `DEVENV_ROOT`, `DEVENV_DOTFILE`, `DEVENV_STATE`,
`DEVENV_PROFILE` and `DEVENV_RUNTIME`, and nothing else from the `DEVENV_*`
namespace.** Those five are documented and read-only in
`docs/src/reference/environment-variables.md`. `DEVENV_CMDLINE`, `DEVENV_TASKS`,
`DEVENV_TASK_FILE` and `DEVENV_SKIP_TASKS` are set and undocumented.
`DEVENV_SKIP_TASKS` in particular is a tempting way to tell the capture
subprocess from the real shell and must not be used: an idempotent guard needs
no such test. (C3)

### What was changed, and why

`modules/devenv.nix` — **the guard no longer forks.** `sed` and `cat` are
replaced with a bash parameter expansion and `$(<file)`. C2 measured the old
form at +23 ms per warm entry and the new one at +4 ms, and the rendered entry
is byte-identical. The refuse-on-collision logic from C5 was written and
exercised in a **copy** under `/tmp/c5-devman` and deliberately **not** applied
to the module: it is a §9.1 change that the reconciliation pass should approve
first.

`.scratch/projects/006-automation-plane/c-scratch/` — a throwaway flake and
NixOS test for C7. It builds a VM, activates a specialisation inside it, and
never touches the machine.

### What Investigation C did not do

- **Investigation D was not started**, as §5 of the prompt requires. D6 in
  particular — the `.devman/` collision survey — was left alone.
- **`CONCEPT.md` was not edited.** Every contradiction is recorded above and
  left for the reconciliation pass, which now owes the charter both B's changes
  and C's.
- **The machine was not modified.** No `nixos-rebuild switch`, no `/etc/nixos/`
  edit, no writes to `~/.local/share/devman/`, no contact with the running Dagu
  instance. Every registry in C is under `/tmp`. C7 ran in a test VM, and the
  separate Dagu used for C6 ran under `DAGU_HOME=/tmp/c6-dagu`.
- **devenv 2.2.2 was tested after all**, once the package could be substituted
  from `devenv.cachix.org` rather than compiled. **Every C1 and C2 result
  reproduces unchanged**, including the double firing and the silent
  registration. See the C1-C2 addendum above. The first attempt began compiling
  devenv from source, saturated the machine, and was corrupting C2's timings; it
  was stopped, and the second attempt used `--max-jobs 0` so nix would refuse to
  build locally.
- **The not-logged-in user was reasoned about, not run.** C7's VM used
  `linger = true`. That a non-lingering user's service is neither running nor
  restarted follows from `logind.list_users()` in the source, and was not
  measured in a VM of its own.

---

## C1–C2 addendum — do the answers survive devenv 2.2.2?

**Answer:** **yes, all of them, unchanged.** The entry matrix is identical, the
double firing is identical, and the cost of the guard is the same within noise.
The charter does not need to name a devenv version.

**Tested:** devenv **2.2.2+b8030c5**, devman `c9426b6`, on 2026-08-22, against
the same `/tmp` repos C1 and C2 used.

**Command:** the package was **substituted, never built**, so it could not
contaminate the timings the way the earlier source build did:

```bash
nix build --no-link --print-out-paths 'github:cachix/devenv/v2.2.2#devenv' \
  --max-jobs 0 \
  --extra-substituters https://devenv.cachix.org \
  --extra-trusted-public-keys devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw=
```

`--max-jobs 0` is the guard: nix refuses to build locally, so the command either
downloads or fails fast. It downloaded. Result:
`/nix/store/cvz3j052k1z95pscj1w2iki187ywfcjw-devenv-wrapped-2.2.2`.

### C1 — the entry matrix is unchanged

| entry path | 2.1.2 | **2.2.2** | registered |
|---|---|---|---|
| `devenv shell -- true` | 2 | **2** | yes |
| `devenv shell`, interactive on a pty | 2 | **2** | yes |
| `devenv test` | 2 | **2** | yes |
| `devenv tasks run` | 1 | **1** | yes |
| `devenv up -d` | 1 | **1** | yes |
| direnv `use devenv`, fresh shell | 2 | **2** | yes |
| `devenv info` / `eval` / `build` | 0 | **0** | no |

**The double firing is not a 2.1.2 quirk.** `capture_shell_environment` behaves
the same way in 2.2.2, so C1's two additions to §5.2 stand, and so does C5's
argument that a registration hook cannot report on the write path — re-checked
directly:

```
$ rm -f /tmp/c5-registry/projects/test.json
$ cd /tmp/c5-A && devenv shell -- true 2>&1 | grep -v "out of date" | cat -A
                                    <- nothing at all
  registry written? test.json
```

### C2 — the cost is the same within noise

80 paired runs, warm, interleaved.

| variant | mean | sd | delta vs `enable = false` |
|---|---|---|---|
| bare devenv repo, no devman input | 232.7 ms | 25.7 | — |
| module imported, `devman.enable = false` | 259.3 ms | 26.8 | — |
| registered, current `sed`+`cat` guard | 280.5 ms | 30.2 | **+21.3 ms** |
| registered, fork-free bash guard | 256.1 ms | 26.7 | **−3.2 ms** |

Against 2.1.2's +23.0 ms and +4.4 ms. Both are the same measurement to within
the spread. The fork-free guard landing 3 ms *below* the disabled baseline is
noise, not a speed-up: its 95% CI against bare is `[+16.6, +30.3]` and the
disabled baseline's is `[+21.1, +32.1]`, and those overlap. **The honest
statement is that the fork-free guard is not distinguishable from zero on
either devenv version.**

**Charter impact:** **none, and it removes a caveat.** C1's and C2's findings
are not version-specific across 2.1.2 → 2.2.2, so §5.2 and criterion 7 need no
devenv version qualifier. The `--max-jobs 0` substitution recipe above is worth
keeping: it is how to test a devenv upgrade without a two-hour Rust build.

---

# Investigation D — the smaller open questions

**Environment for every D answer unless a section says otherwise.** devenv
2.1.2, dagu 2.15.0, Nix 2.34.7, NixOS 26.11.20260705, devman commit `c9426b6`,
on 2026-08-22. The machine was surveyed read-only; nothing under
`~/Documents/Projects` was modified.

**The survey population**, which D4 and D6 both rest on: **71 project
directories** under `~/Documents/Projects`, of which **67 are git repositories**,
plus **6 git worktrees** under `~/.paseo/worktrees`.

---

## D1 — Does anything else claim `~/.local/share/devman/`?

**Answer:** **the directory is free; the name is not.** Nothing claims
`~/.local/share/devman/` — it does not exist. But **devman 0.2.0 is installed on
this machine right now**, it owns the `devman` command, and it claims
`~/.config/devman/` and `~/.cache/devman/`. The lean is confirmed for the
registry root and overturned for everything around it.

**Tested:** on 2026-08-22.

**Command:**

```bash
ls -d ~/.local/share/devman; command -v devman
```

**Evidence:**

```
"/home/andrew/.local/share/devman": No such file or directory (os error 2)
/etc/profiles/per-user/andrew/bin/devman
```

The registry root is unclaimed. Its neighbours in `~/.local/share/` are
`devenv`, `direnv`, `nix`, `repoman`, `uv`, and about twenty desktop
directories. No collision, and `XDG_DATA_HOME` is unset, so the path resolves as
the charter assumes.

**The binary is the problem.** `/etc/profiles/per-user/andrew/bin/devman`
resolves to `/nix/store/i1cpdmw9w0hflws2fzm544r2v1scxkd5-devman-0.2.0`, a Python
Typer CLI installed through this user's Home-Manager or system profile:

```
 Usage: devman [OPTIONS] COMMAND [ARGS]...
 🧰 Manage devman workspaces

╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ up         Ensure workspace dependencies are configured.                     │
│ down       Stop services started by devman.                                  │
│ switch     Switch to a different workspace by name or query.                 │
│ bootstrap  Bootstrap tmux, Claude, and Neovim integrations for the current   │
│            workspace.                                                        │
│ doctor     Return availability of external tools.                            │
│ init       Initialize a .devman workspace layout.                            │
│ index      Manage workspace index                                            │
╰──────────────────────────────────────────────────────────────────────────────╯
```

**`devman doctor` and `devman init` already exist, with different meanings.**
§10's deferred CLI plans `devman doctor` for diagnosing the plane; 0.2.0's
`doctor` reports "availability of external tools". §3.3 says the current source
is deleted, but **the installed binary is not** — deleting a repository does not
uninstall a profile.

Its own state paths, from `models/system.py:12` and `:44`:

```python
Path.home() / ".config" / "devman" / "system.toml"
Path.home() / ".cache" / "devman"
```

Neither directory exists on disk today, so 0.2.0 has been installed but never
run here. **`~/.local/share/` is not among them**, which is why the registry
root survives.

**Charter impact:** **confirms §16's lean for the registry root; changes §10 and
§3.3.**

- §16's "confirm nothing else claims `~/.local/share/devman/`" — **confirmed**,
  and the question can be closed.
- **§10 must state that the `devman` command name is already taken** on at least
  this machine, by a CLI whose `doctor` and `init` mean something else. The new
  CLI either replaces 0.2.0 in the profile, or it needs a different name.
  Shipping both puts two different `devman doctor` commands on one `PATH`, and
  which one wins depends on profile order.
- **§3.3 should say "the source is deleted, the installed binary is not."**
  Stage 1 needs an explicit step to remove `devman-0.2.0` from this user's
  profile, or the first `devman doctor` a developer runs is the old one.

---

## D2 — Do ecosystem groups ship in this flake, or separately?

**Answer:** **in this flake. Confirmed, and C2 gives the lean a measured
argument it did not have.** A separate groups flake would be a second devenv
input in every consuming repo, and C2 measured what a devenv input costs.

**Tested:** derived from B2, B4 and C2; no new measurement.

**Evidence.** C2's paired timings isolate the cost of *having an input* from the
cost of *using it*:

| variant | delta vs a bare devenv repo |
|---|---|
| module imported, `devman.enable = false` | **+19.6 ms** (2.1.2), **+26.6 ms** (2.2.2) |
| registered, fork-free guard | +24.0 ms / +23.4 ms |

**Roughly 20 ms of the plane's per-entry cost is the input itself**, before
registration does anything. A separate `devman-groups` flake would add a second
input to `devenv.yaml` in every repo that takes a group, and repeat that cost on
every shell entry, forever, in exchange for decoupling group churn from plane
releases.

Two further reasons from B:

- **B4:** an import is `<input>/<subdir>` resolved to a path containing
  `devenv.nix`. A groups flake would need its own `devenv.nix` shim purely to be
  importable, or the repo imports group YAML by path and skips the flake — in
  which case the flake bought nothing.
- **B's rule 2:** what the two interfaces share must be text. Groups **are**
  text — Dagu YAML — and text costs nothing to share inside one flake. The one
  shared *package*, `nix/dagu.nix`, already pays for two store paths (B2). A
  second flake would add a second lock file and a second rev to keep aligned,
  which is precisely the drift §3.1 exists to prevent.

**Charter impact:** **none.** §16's lean stands: in-repo until a third party
wants to publish a group. Add the measured number as the reason — **a second
flake input costs about 20 ms on every shell entry in every repo that takes it**
— so the decision is not merely a matter of taste, and so a future proposal to
split the flake has to argue against a number.

---

## D3 — Should the machine module manage a Dagu it did not install?

**Answer:** **no. Confirmed, and the conflict is loud rather than silent**,
which is what makes "own the service, document the conflict" safe. Measured
against a real foreign Dagu that is running on this machine right now.

**Tested:** dagu 2.15.0, on 2026-08-22.

**There is a foreign Dagu on this machine, and it is this repo's own.**
`devenv.nix` line 44:

```nix
env.DAGU_HOME = daguHome;
processes.dagu.exec = "dagu start-all";
```

Started by `devenv up`, running as pid 1771311 with
`DAGU_HOME=<worktree>/.devenv/state/dagu`, holding two ports:

```
LISTEN 127.0.0.1:50055   users:(("dagu",pid=1771311,fd=4))
LISTEN 127.0.0.1:8080    users:(("dagu",pid=1771311,fd=12))
```

**Command:** start a second instance with a disposable `DAGU_HOME`, exactly as
the NixOS module's unit would:

```bash
DAGU_HOME=/tmp/d3-dagu dagu start-all
```

**Evidence:**

```
level=INFO msg="Coordinator initialization" bind-address=127.0.0.1 advertise-address=server port=50055
Error: failed to initialize coordinator: failed to create listener on 127.0.0.1:50055:
       listen tcp 127.0.0.1:50055: bind: address already in use
exit=1
```

The original instance was **untouched** — still listening, still the same pid.

**Three things this establishes.**

1. **The conflict announces itself.** It fails on the *coordinator* port 50055
   before it ever reaches the web port, with a named port and a named error, and
   exits non-zero. Under the module's `Restart=on-failure`, `systemctl --user
   status dagu` shows it immediately. §15.4's "a typo is invisible" problem does
   not apply here.
2. **A separate `DAGU_HOME` is not enough to coexist.** The second instance had
   its own state directory and still could not start. Ports, not state, are the
   scarce resource, and the module exposes no port option today.
3. **A retry loop is the one rough edge.** `Restart=on-failure` with
   `RestartSec=5` retries a conflict that will never resolve on its own, writing
   to the journal every five seconds. The module should either cap it
   (`StartLimitBurst`) or treat a bind failure as fatal.

Note the second instance **created example DAGs in the new `DAGU_HOME` before
failing** ("Creating example DAGs for first-time users"). A failed start is not
a no-op on disk.

**Charter impact:** **confirms §16's lean; changes §4.**

- §16's "should the machine module manage a Dagu it did not install?" —
  **no, confirmed**, and the question can be closed. The module owns the
  service.
- **§4 should document the conflict concretely**: the collision is a port
  collision on **50055 and 8080**, not a state collision, and it is reported
  clearly. Two consequences worth stating: give the module a **port option** so
  a developer running a project-local Dagu can move one of them, and **bound the
  restart loop** so an unresolvable bind failure does not fill the journal.
- **This repo's own `devenv.nix` is the first thing stage 1 must reconcile**,
  since criterion 16 says devman adopts itself and the repo currently starts a
  competing instance through `processes.dagu`.

---

## D4 — Which ecosystem groups first?

**Answer:** **Python and Nix. Confirmed emphatically**, and Rust and TypeScript
are not "on demand" so much as absent — there is no demand to be had.

**Tested:** read-only survey of 71 project directories, on 2026-08-22.

**Command:**

```bash
for f in flake.nix devenv.nix pyproject.toml package.json Cargo.toml go.mod; do
  printf '  %-16s %s\n' "$f" "$(find ~/Documents/Projects -maxdepth 2 -name "$f" | wc -l)"
done
```

**Evidence:**

| marker | repos carrying it | share of 71 |
|---|---|---|
| `devenv.nix` | **57** | 80% |
| `pyproject.toml` | **52** | 73% |
| `flake.nix` | **24** | 34% |
| `package.json` | 1 | 1% |
| `Cargo.toml` | 1 | 1% |
| `go.mod` | 0 | 0% |

**Python and Nix cover the population; nothing else registers.** Two readings
worth recording:

- **`devenv.nix` at 80% is the more important number than either language.**
  It is the highest-coverage marker in the population, which is what makes §5's
  "three lines plus the repo's own primitives" plausible — most repos already
  have the primitives. It also means the `base` group, not the language groups,
  is where the leverage is.
- **A TypeScript or Rust group would serve one repository each.** That is not a
  group, it is a repo's own `.devman/workflows/`, which §7.4 already allows.

**Charter impact:** **none.** §16's lean stands. Sharpen the wording: not
"Rust and TypeScript on demand" but **"one repo each today, so they are
`.devman/workflows/` content until a second repo wants the same file."** That
is the same rule §7.3 already uses for promotion, applied to itself.
