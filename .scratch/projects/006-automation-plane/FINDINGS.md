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
