# devman's own workflows

`.devman/workflows/` is the last layer of §7.3's resolution: a file here shadows
every group's file of the same name. This directory is **tracked**, because it
is canonical state (§9.2). `.devman/.runs/` beside it is not.

devman registers itself like any other project (criterion 16), so a cross-repo
workflow is simply one of its own files (§11).

| File | What it is |
|---|---|
| `stack-validate.yaml` | a cross-repository workflow: it triggers other projects' `check` and runs no command itself |

## Triggering, by hand, until `devman run` exists

§10 defers the CLI to stage 3 and says to prove the conventions by hand first.
Both conventions below are forced by measurement, not taste.

**Use `enqueue`, never `start`.** `dagu start` ignores queues entirely — two
DAGs naming `exclusive` ran 0.3 s apart under `start` and serialized strictly
under `enqueue` (A6, A1). Queue names are the plane's only lever on concurrency.

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

The DAG's name is `<project>-<workflow>`, which is what `dagu ls`, the scheduler
and `enqueue` all agree on (S1).

### A cross-repository workflow

Different, and the difference is the whole of §11. The parent must **not** hold
`DEVMAN_PROJECT_DIR`: a parent exports its parameters into every child's
environment, and that environment outranks the child's own `with.params`. So the
parent names its own directory `DEVMAN_SELF_DIR`, and each target project
arrives as its own parameter — because criterion 10 forbids an absolute path in
a workflow file, and only the registry knows where a project sits.

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

`env -u DEVMAN_PROJECT_DIR` is deliberate: if the calling shell happens to
export it, the children inherit it and every one of them runs in the wrong
directory, successfully and silently.

**Resolving each parameter from the registry is what `devman run` will do**
(§10). Writing it out here is the point of proving the convention by hand: the
CLI's job is now specified by an example rather than by a paragraph.
