# devman's own workflows

`.devman/workflows/` is the last layer of §7.3's resolution: a file here shadows
every group's file of the same name. This directory is **tracked**, because it is
canonical state (§9.2). `.devman/.runs/` beside it is not.

devman registers itself like any other project (criterion 16), so a workflow that
belongs to no project — or to the machine — is simply one of its own files (§11).

| File | Queue | Trigger | What it is |
|---|---|---|---|
| `plane-report.yaml` | `light` | `schedule: 20 0 * * *` | `devman doctor` over the whole plane, once a night, for the machine |
| `stack-validate.yaml` | `normal` | manual | a cross-repository workflow: it triggers other projects' `check` and runs no command itself |
| `agent-review.yaml` | `exclusive` | manual | an agent reviews a commit and leaves the answer in `.runs/reports/` |
| `bench-entry.yaml` | `exclusive` | manual | a benchmark campaign over a named other project's shell-entry cost |
| `gitman-commit-message.yaml` | `gpu` | manual | drafts a commit message from the staged diff on the local GPU (`llgym serve` + pydantic-ai), for `gitman save -m "$(cat …)"` |

**None of these is a group, and two of them never can be** (`PROPOSAL.md` §11):

- `stack-validate` names specific DAGs — `observantic-check`, `siteman-check`. A
  group file cannot name another project without holding a project fact, which
  §4 forbids.
- `bench-entry` measures a *named other* project. A per-repository benchmark
  campaign is meaningless at 53.
- `plane-report` reads the whole registry, so its report is about the machine.
  A group file shipping it would run it once per repository — which is exactly
  what stage 7 removed from `base/maintain`.
- `agent-review` and `gitman-commit-message` are **not yet** groups: one
  repository carries `claude-code` and `codex-cli` in its packages, and one
  machine holds the GPU the second one calls. Promotion costs nothing when a
  second repository wants the file, because the workflow names a task and the
  task names the tool (§7.1). It also needs §9.4 — the untested secrets path —
  to fire once for real, and a group is the wrong place to prove an untested
  path.

**The two agent workflows name two different queues, and the difference is the
point.** `agent-review` says `exclusive`: it is long and non-deterministic and
reads a tree another run may be rewriting. `gitman-commit-message` says `gpu`:
its sharper constraint is the resource — a local model server holding weights in
one GPU's VRAM. Saying `exclusive` there would serialize it against every other
exclusive workflow for a reason that has nothing to do with the GPU.

## Triggering

```bash
devman run check                     # in any registered repository
devman run stack-validate            # here — the cross-repo one
devman run plane-report              # here — the machine-wide one
devman run agent-review AGENT_REF=HEAD~3
devman run bench-entry TARGET=pyjutsu RUNS=40

llgym serve --n-gpu-layers 30        # in llgym's own shell, once
devman run gitman-commit-message     # then read the file it names
```

**The plane calls a long-running process; it never supervises one.** That is the
same rule `processes.dagu`'s note in `devenv.nix` states for Dagu itself. If
nothing answers on `GPU_LLM_BASE_URL`, the step fails with that reason rather
than hanging.

`devman run` resolves the project from the current directory, exports
`DEVMAN_PROJECT_DIR`, passes it as a parameter, and enqueues. For
`stack-validate` it does the other two things this file used to ask a person to
do: it sets `DEVMAN_SELF_DIR` instead, because the file declares that parameter,
and it fills `OBSERVANTIC_DIR` and `SITEMAN_DIR` from the registry, because each
one's default names a registered project.

**It refuses rather than enqueueing a run that would write to the wrong place.**
A directory variable that would be empty, a path that is not a directory, a
parameter nothing fills, a parent that holds `DEVMAN_PROJECT_DIR`, a flat DAG
name two projects both claim — each is a refusal naming the file and the field.
That is what would have prevented the literally-named `${DEVMAN_PROJECT_DIR}`
directory this repository committed once (`STAGE_2_LOG.md`, S15).

## Editing one of these

The projection is a **generated copy** since stage 6, not a symlink. An edit
reaches Dagu at the next shell entry:

```bash
$EDITOR .devman/workflows/plane-report.yaml
devenv shell -- true          # re-project
devman show plane-report      # confirm what would run
```

The shell-entry guard compares each override's body against the tail of its
projection, so it notices an edit in place and not only an add or a remove.
Between stage 6 and stage 7 it did not, and the run that followed an edit
executed the previous version, silently, with `doctor` reporting nothing wrong
(`STAGE_7_LOG.md`, S-5a).

## Triggering by hand, which is still the specification

The section below is what `devman run` does, written out. It stays because the
conventions are forced by measurement rather than taste, and because a CLI that
hides them would leave nobody able to check them.

**Use `enqueue`, never `start`.** `dagu start` ignores queues entirely — two DAGs
naming `exclusive` ran 6 ms apart under `start` and serialized strictly under
`enqueue` (A6, A1). Queue names are the plane's only lever on concurrency.

**Export the variable *and* pass it as a parameter.** `working_dir` reads the
parameter and `log_dir` reads the enqueuing process's environment; one is not a
substitute for the other (A3). Miss the export and the run still succeeds — and
writes its logs into a directory named literally `${DEVMAN_PROJECT_DIR}` in
whatever tree the daemon started in. A green run is not evidence the trigger was
right; check where the logs landed.

### An ordinary, single-project workflow

```bash
REG=~/.local/share/devman
dir=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["path"])' \
        "$REG/projects/observantic/metadata.json")

DEVMAN_PROJECT_DIR="$dir" \
  dagu enqueue observantic-check -- DEVMAN_PROJECT_DIR="$dir"
```

The DAG's name is `<project>.<workflow>`, which is what `dagu ls`, the scheduler
and `enqueue` all agree on (S1).

### A cross-repository workflow

Different, and the difference is the whole of §11. The parent must **not** hold
`DEVMAN_PROJECT_DIR`: a parent exports its parameters into every child's
environment, and that environment outranks the child's own `with.params`. So the
parent names its own directory `DEVMAN_SELF_DIR`, and each target project arrives
as its own parameter — because criterion 10 forbids an absolute path in a
workflow file, and only the registry knows where a project sits.

```bash
REG=~/.local/share/devman
p() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["path"])' \
        "$REG/projects/$1/metadata.json"; }

env -u DEVMAN_PROJECT_DIR \
  DEVMAN_SELF_DIR="$(p devman)" \
  dagu enqueue devman-stack-validate -- \
    DEVMAN_SELF_DIR="$(p devman)" \
    OBSERVANTIC_DIR="$(p observantic)" \
    SITEMAN_DIR="$(p siteman)"
```

`env -u DEVMAN_PROJECT_DIR` is deliberate: if the calling shell happens to export
it, the children inherit it and every one of them runs in the wrong directory,
successfully and silently.

`devman run` also clears `SHELL`, which is a third thing baked at enqueue time.
Dagu resolves a step's shell from `$SHELL` and falls back to the instance's
`default_shell` only when `$SHELL` is unset. Without that, every step would run
under the login shell of whoever triggered it (`STAGE_4_LOG.md`, S13).
