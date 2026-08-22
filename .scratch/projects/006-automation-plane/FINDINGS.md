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
