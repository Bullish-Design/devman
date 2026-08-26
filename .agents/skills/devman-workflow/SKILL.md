---
name: devman-workflow
description: Author or change a devman workflow — a repository's own .devman/workflows/ file, a group workflow, or a triggers.toml mapping. Holds the decision tree, the file rules, the parameter and queue conventions, the loop-break and schedule mechanics, and the test loop that proves a new workflow works.
auto_trigger:
  keywords: ["new workflow", "add a workflow", "write a workflow", "devman workflow", "dagu yaml", "override a workflow", "devman show", "shadow a workflow", "workflow group", "triggers.toml", "format on save", "schedule a workflow", "cross-repo workflow", "DEVMAN_SELF_DIR", "dag.run", "queue light normal heavy exclusive", "preconditions", "handler_on", "metadata.jsonl"]
---

# devman-workflow — authoring a workflow

Read the `devman` skill first for the model and the CLI. This one is the
procedure.

**A workflow is a plain Dagu YAML file with no devman-specific key in it.** The
plane adds a generated header at projection time and reads nothing else.

---

## 0. First decide whether it should be a workflow at all

Answer these before writing a line. A "yes" to any of them means **stop**, and
say why (`PROPOSAL.md` §12):

1. Does an editor already do this synchronously? LSP diagnostics and
   format-in-buffer land next to the cursor in tens of milliseconds; the plane's
   round trip after a content change is 1.44 s and lands in a log file.
2. Is it irreversible outside this machine? Publishing, tagging, deploying.
3. Does it write **tracked source** with nobody present? Dependency updates, code
   generation, autofix beyond formatting. A formatter is the single exception,
   and it is bounded three ways: one glob, a content hash, its own group.
4. Could it succeed while doing nothing? `devenv test` exits 0 having tested
   nothing in 30 of 58 repositories, which is why the rung that ran it was
   deleted.
5. Does it need a fact the repository did not state — another project's path, an
   absolute path, a per-project schedule offset?
6. Is it a second implementation of a task the repository already has? Running
   `pytest` directly rather than calling the repository's own test task drifts,
   and drifts silently because both keep passing.
7. Will anybody read its output? A report produced 54 times is a report produced
   zero times.
8. Is it expensive **and** scheduled? **A scheduled run bypasses its queue.**
   Nothing throttles the scheduled set.

## 1. Then decide where it goes

```
Does one repository want it?
├── yes → <repo>/.devman/workflows/<name>.yaml            → §3
└── no, a second repository wants the SAME file
    ├── and taking it costs a task name or an unasked-for write
    │                                     → a new group under groups/       → §8
    └── otherwise → add it to an existing group                             → §8

Replacing a workflow a group already ships?
    → shadow it: same file name in <repo>/.devman/workflows/               → §2
```

**§16's promotion rule: a group begins when a *second* repository wants the same
file.** One repository wanting something is that repository's own file. Do not
create a group for a language — a language differs in what a task *is*, and
`devenv.nix` already holds that.

**§3's group rule: a group exists when taking it costs the repository something
it cannot decline any other way** — a task name it must define, or a write to its
own files it did not ask for. What fires a workflow is not the test; what it
touches is. A nightly housekeeping workflow may ride in a general group, because
it writes only under `.devman/.runs/`.

---

## 2. Override a workflow a group ships

Resolution layers by group in the order the repository lists them, and
`.devman/workflows/` is the last layer. **Shadowing is whole-file, never a field
merge.**

```bash
devman show test > .devman/workflows/test.yaml   # start from what runs today
$EDITOR .devman/workflows/test.yaml
devenv shell -- true                             # re-project
devman show test                                 # confirm the source it now reads
devman run test
```

`devman show` prints the **source** file on stdout — never the generated
projection — and everything about where it came from on stderr, so the redirect
round-trips.

`devman doctor` reports every override and how far it has drifted from the group
file it shadows. That is a report, not a complaint.

**To be rid of a workflow, do not take its group.** There is no per-workflow Nix
option and there will not be one (§7.4).

---

## 3. Write a repository's own workflow

```yaml
# .devman/workflows/smoke.yaml
# Why this file exists, and what it costs the repository.
queue: light
steps:
  - name: smoke
    run: devenv tasks run -v my:smoke
```

```nix
# devenv.nix
tasks."my:smoke".exec = "pytest -m smoke";
```

```bash
devenv shell -- true          # register the override and re-project
devman show smoke             # confirm
devman run smoke
```

### The rules, each forced by a measurement

| Rule | What breaks otherwise |
|---|---|
| **No top-level `name:`** | `dagu validate` fails: "entrypoint document must not define name". A DAG's identity is its file name |
| **No `working_dir:`, no `log_dir:`** | the projection writes both, per project. State them only for a cross-repo workflow (§7) |
| **No `handler_on:`** | Dagu inherits `base.yaml` **whole-field**, so any handler replaces the machine's exit handler. The run then writes **no** `metadata.jsonl` line at all — silently, with a clean `dagu status` and correct logs |
| **`queue:` is required in practice** | a DAG naming none inherits `light` from `base.yaml`. State the one you mean |
| **One step, one `devenv tasks run -v`** for a default-shaped workflow | order belongs to the devenv task graph. A second step re-states a dependency devenv already declares |
| **`-v` on every `devenv tasks run`** | without it devenv captures the task's stdout and prints none of it, on the success path and the failure path alike. A step running `ruff check .` writes a log holding `{}`. `--show-output` documents itself as equivalent and is not |
| **No bashisms** | a step does not run under the shell you expect. `$EPOCHREALTIME` failed once for exactly this reason. `date +%s%N` is the POSIX replacement |
| **Handle failure explicitly** | Dagu runs a step's script with `set -e` already on — a step printing `$-` reports `ehuB`. A bare failing command aborts the script at that line, so the rest never runs. Use `\|\| rc=$?` when you need the script to finish |

### Composing work: use the task graph, not more steps

```nix
tasks."base:test".after  = [ "base:check" ];
tasks."base:check".after = [ "python:lint" "python:typecheck" ];
```

A task with only `after` needs no `exec`: it runs its dependencies and then does
nothing itself, and a failure in a dependency still fails the run. **Siblings in
an `after` list run concurrently**, so a failing task does not stop the others.
Chain the edges when you want fail-fast.

**What one step costs, stated plainly.** Dagu's per-step status is lost: the run
shows `test: failed` and the failing devenv task is named in the step's `.err`
file, the DAG-level log, and Dagu's own recorded `error` field. It appears **0
times** in the `.out` file on devenv 2.1.2.

---

## 4. Parameters

```yaml
params:
  - DEVMAN_PROJECT_DIR: ""
  - KEEP_DAYS: "7"
  - TARGET: observantic
```

| Rule | Why |
|---|---|
| **Declare `DEVMAN_PROJECT_DIR: ""` first, or declare no parameters at all** | Dagu rejects a parameter a DAG did not declare, and `devman run` always passes the directory variable |
| **Every parameter needs a real default** | `devman run` refuses a parameter that would be empty. An agent run with an empty prompt is a run nobody asked for |
| **A default that names a registered project is filled with that project's path** | that is how a workflow points at another repository without holding an absolute path (criterion 10) |
| **A cross-repo workflow declares `DEVMAN_SELF_DIR` instead** | see §7 |

The block is about **how the DAG is triggered**, not about what its steps do.
Dropping a step does not drop the parameter block.

Override at the prompt:

```bash
devman run maintain KEEP_DAYS=30
devman run bench-entry TARGET=pyjutsu RUNS=40
```

A step reads a parameter as an ordinary environment variable — `$KEEP_DAYS`. Use
`set -u` so a broken hand-off is loud.

---

## 5. Queues

| Queue | Limit | Say it when |
|---|---|---|
| `light` | 4 | seconds of work, no build |
| `normal` | 2 | the suite; minutes. Also a workflow that fans out into child runs |
| `heavy` | 1 | a build that wants the machine |
| `gpu` | 1 | one caller at a time on the GPU. Naming it for anything else misdeclares it |
| `exclusive` | 1 | this must not overlap with other exclusive work — long, non-deterministic, reads a tree another run may rewrite |

`heavy` says "this costs a lot of machine". `exclusive` says "this must not
overlap". `gpu` names a resource. All three are limit 1 on this machine; **say
the one that is true.** `.devman/workflows/gitman-commit-message.yaml` is the
worked example: it calls a local model server holding weights in one GPU's VRAM,
so it names `gpu` — `exclusive` would serialize it against every other exclusive
workflow in the plane for a reason that has nothing to do with the GPU.

**A queue name is a one-way door.** Dagu accepts a queue that does not exist
silently, and gives that name a queue of its own at **concurrency 1**. A typo
therefore serialises a workflow rather than freeing it — a misspelt `light` runs
one at a time instead of four, beside every other file carrying the same
misspelling. Nothing says so at run time. `devman doctor` checks the names.

**`exclusive` does not give a run the machine.** Dagu's queues are independent, so
`light`, `normal` and `heavy` runs proceed beside an exclusive one. The plane can
serialize a class; it cannot quiesce a host.

---

## 6. Schedules

Use Dagu's own `schedule:` key, in the file:

```yaml
schedule: "5 0 * * *"
queue: light
```

This works only because the projection is a **generated** file per project: each
copy states its own `working_dir`, `log_dir` and directory variable, so the
daemon needs nothing from a trigger. Before stage 6 a scheduled run produced a
directory named literally `${DEVMAN_PROJECT_DIR}`.

> **A scheduled run does not pass through its queue.** Measured: 58 DAGs sharing
> one `schedule:` all started at once with queue depth 0, and two DAGs on
> `exclusive` — limit 1 — both started in the same second. The same 58 put
> through `dagu enqueue` never exceeded 4 and drained in 311 s. **Nothing
> throttles the scheduled set.**

So: **schedule only work that is cheap by construction.** 54 repositories firing
one cheap DAG at 00:05 costs 2 seconds. 58 concurrent `devman doctor` runs
measured 139 s each against 14.3 s alone.

**Never put a stagger in a group file.** A group file is shared, so an offset
written there gives every repository the same offset — and a per-repository
offset is a project fact held outside the project.

**A schedule in a group file is opted out of by shadowing the file** and leaving
the key out, or by not taking the group.

### When a timer is right instead

A systemd user timer is the answer when the schedule belongs to one repository:

```ini
[Service]
Type=oneshot
ExecStart=/run/current-system/sw/bin/devman run test --project siteman
```

`--project` is what makes this work from a timer, which has no working directory
in any repository. **A timer holds project names and drifts in two directions,
and only one tells you:** a renamed project makes the unit fail loudly; a newly
adopted project is simply never scheduled, silently.

---

## 7. A workflow that triggers other repositories' workflows

**The one rule: the parent must not hold `DEVMAN_PROJECT_DIR`.** A parent exports
its parameters into every child's environment, and that environment outranks the
child's own `params:`, its `env:` block, and even an explicit `with.params`. A
parent holding the name drags every child into its own directory — the children
run, succeed, and do the work in the wrong place, and nothing reports it.

```yaml
params:
  - DEVMAN_SELF_DIR: ""
  - OBSERVANTIC_DIR: observantic     # a project NAME; the trigger resolves it
  - SITEMAN_DIR: siteman

working_dir: ${DEVMAN_SELF_DIR}
log_dir: ${DEVMAN_SELF_DIR}/.devman/.runs/logs

queue: normal
type: chain
steps:
  - name: observantic-check
    action: dag.run
    with:
      dag: observantic-check
      params:
        DEVMAN_PROJECT_DIR: ${OBSERVANTIC_DIR}
```

- `working_dir` and `log_dir` are stated **here**, because the header's copies
  name `DEVMAN_PROJECT_DIR` — the name this file must not hold. An unset variable
  is not an error in Dagu: it creates a directory of that literal name and
  carries on.
- Each target is a parameter whose default is a **project name**, so the file
  holds no absolute path.
- The child DAG's name is `<project>.<workflow>`.
- **Such a workflow belongs to `devman`** (§11): a workflow spanning several
  projects belongs to none of them. It can never be a group file, because a group
  file naming another project would hold a project fact.

`devman run` enforces both halves and refuses when either is missing. The worked
example is `devman/.devman/workflows/stack-validate.yaml`.

---

## 8. A group workflow

Only when a **second** repository wants the same file. Adding one charges every
taker of that group.

```
groups/<group>/
├── README.md                # what taking this group costs a repository
├── triggers.toml            # optional: <glob> = <workflow>
└── workflows/<name>.yaml
```

Extra rules on top of §3:

| Rule | Why |
|---|---|
| **The workflow names a task; the task names the tool** | a group calls `<group>:check`, never `ruff`. Then `black`, `ruff format` or a script all fit without the file changing |
| **The task namespace is the group's own name** | devenv requires `namespace:name`, so a group-local convention is literal |
| **No project name, no absolute path, no per-repository offset** | the machine never learns a project fact |
| **Document the cost in that group's `README.md`, in the same commit** | taking a group is an agreement to define its task names |
| **A group whose workflows are deleted becomes a tombstone, not a deletion** | `modules/devenv.nix` throws on an unknown group, and the throw is an **evaluation** failure: a repository re-pinning to a rev where its group is gone could not enter its shell at all. A directory with no `workflows/` evaluates and projects nothing, so a stale pin keeps working. It must hold at least one file — git cannot carry an empty directory — and **must not** hold a `triggers.toml` |

### `triggers.toml` — making a group reactive

```toml
"**/*.py" = "format"
```

- The glob is matched against a path relative to the repository root; the
  workflow is a name the same repository projects.
- It is **group content**, resolved at evaluation time, whole-file, in the order
  the repository lists its groups, and recorded in the registry entry. The
  watcher reads the entry and nothing else.
- TOML rather than Nix: `builtins.fromTOML (builtins.readFile …)` is tracked by
  devenv's evaluation cache, and a mapping that decides what happens on a save
  must not go stale silently. It is also inert data — a `.nix` file would let a
  group evaluate arbitrary Nix in every repository that takes it.

> **The widening rule.** Adding a glob requires widening the workflow's content
> hash in the **same edit**. A glob whose files the hash does not cover fires a
> run whose precondition is never true, so the new language's saves produce a run
> that skips and never formats. That failure is silent: the run reports
> `Succeeded` with a skipped step, which is exactly the status a correct
> loop-break produces. **Nothing in the plane checks it.**

### Breaking the write-fires-the-watcher loop

A workflow that rewrites files its own trigger watches needs a **step-level**
precondition comparing a content hash:

```yaml
steps:
  - id: fmt
    name: format
    preconditions:
      - condition: |
          test "$(find . -name '*.py' -not -path './.devenv/*' -not -path './.git/*' -print0 \
            | sort -z | xargs -0r sha256sum | sha256sum)" != "$(cat .devman/.runs/.format.hash 2>/dev/null)"
    run: |
      devenv tasks run -v format:fmt
      find . -name '*.py' -not -path './.devenv/*' -not -path './.git/*' -print0 \
        | sort -z | xargs -0r sha256sum | sha256sum > .devman/.runs/.format.hash
```

- **A hash, not a timer.** Edit the file a second after the formatter wrote it
  and the hash differs, so the work runs. A suppression window would swallow that
  edit and would still pass a naive "one save, one run" test.
- **Step-level, not DAG-level.** An unmet DAG-level precondition records
  `Aborted` — the same status a cancelled run gets. A step-level one gives
  `Succeeded` with the step skipped.
- **`type: build` cannot be used.** It cannot declare one path as both input and
  output, and a formatter is exactly that. Dagu rejects it at run time and
  `dagu validate` does not catch it.
- The hash file lives under `.devman/.runs/`, which the watcher ignores, so
  writing it is not itself an event.
- Dagu skips **after** enqueueing, so the loop terminates with one run that
  formats and one run that skips.

---

## 9. Gates, reports and artifacts

### A gate fails; it does not skip

A precondition that skips records `Succeeded`, which is right for a self-stopping
loop and **wrong for a refusal**. A release that is refused and reports success is
the failure the whole design exists to prevent. Write the gate as an ordinary
step that reports what it found and then exits 1.

```yaml
steps:
  - id: gate
    name: gate
    run: |
      set -u
      report=".devman/.runs/reports/release-${context.run.id}.md"
      refused=0
      ...
      cat "$report"
      [ "$refused" = 0 ] || { echo "the policy refused. See $report" >&2; exit 1; }
```

### Where output goes

| Directory | For | Pruned by |
|---|---|---|
| `.devman/.runs/reports/` | what a person reads afterwards | `maintain`, older than `KEEP_DAYS` |
| `.devman/.runs/artifacts/` | what a run built | **nothing.** Counted, never deleted |
| `.devman/.runs/logs/` | each step's stdout and stderr | the machine's `hist_retention_days`, per DAG, when that DAG runs |
| `.devman/.runs/metadata.jsonl` | one line per run: dag, id, status, log path | nothing owns it, so it survives retention |

All four are created at registration and git-ignored. A step addresses them
relatively — `working_dir` is already the project — or through
`$DEVMAN_PROJECT_DIR`.

### Context variables Dagu supplies

`${context.run.id}` · `${context.dag.name}` · `${context.attempt.started_at}`

`${context.dag.name}` is `<project>.<workflow>`, which is how a workflow derives
its own project name without holding one: strip the last hyphenated component.
**That derivation assumes the workflow's own file name contains no hyphen.**

### Reading `metadata.jsonl` from a step

Match the **full** string, anchored:

```sh
want="\"dag\":\"${me%-*}-test\""
last=$(grep -hF "$want" .devman/.runs/metadata.jsonl 2>/dev/null | tail -1)
case "$last" in *'"status":"succeeded"'*) ... esac
```

A suffix match is not enough: matching `-validate` also matched
`devman-stack-validate` and reported a different workflow's success as this one's.
And `"status":"succeeded"` is matched in full because
`"status":"partially_succeeded"` contains it as a substring.

---

## 10. Validate and prove it works

```bash
# 1. every shipped group file loads
export HOME=$TMPDIR DAGU_HOME=$TMPDIR/dagu && mkdir -p "$DAGU_HOME"
dagu validate groups/base/workflows/check.yaml

# or, for the whole set:
nix build .#checks.x86_64-linux.groups-validate

# 2. project it
devenv shell -- true

# 3. see what would run, and what would be enqueued
devman show <workflow>
devman run <workflow> --print

# 4. run it
devman run <workflow>

# 5. read what it did
tail -1 .devman/.runs/metadata.jsonl
ls -t .devman/.runs/reports/ | head -3
ls .devman/.runs/logs/<project>_<workflow>/

# 6. the whole plane still healthy
devman doctor
```

**Never use `dagu dry`.** It creates `log_dir`, so it reproduces the
literally-named `${DEVMAN_PROJECT_DIR}` directory this repository committed once.

**Never use `dagu start`.** It ignores queues entirely.

**An edit reaches Dagu only at the next shell entry.** The projection is a
generated copy, not a symlink. The shell-entry guard compares an override's body
against the tail of its projection, so it notices an edit in place — but only
when the shell is entered.

### Proving a scheduled workflow

Do not wait for midnight to find out it is broken. Run it by hand first, then
confirm the daemon can fire it: the projected copy must carry `working_dir`,
`log_dir` and the `env:` header. Check the run record's `trigger` field is
`scheduler` the morning after.

### Proving a reactive workflow

Save a matching file once and confirm exactly one run formats. Save again with no
change and confirm the next run **skips** — that is the loop break working. A run
that skips forever means the hash does not cover the glob.

---

## 11. Checklist before you commit

- [ ] It is not one of §0's eight refusals.
- [ ] It is in the right place: repository file, existing group, or a new group
      justified by a **second** repository wanting the same file.
- [ ] No top-level `name:`, no `working_dir:`, no `log_dir:` (unless cross-repo),
      no `handler_on:`.
- [ ] `queue:` states the honest name, spelled correctly.
- [ ] `params:` declares `DEVMAN_PROJECT_DIR: ""` first, or declares nothing.
- [ ] Every parameter has a real default.
- [ ] Every `devenv tasks run` carries `-v`.
- [ ] No bashisms; failures handled, because `set -e` is already on.
- [ ] No absolute path, no other project's name, no per-project offset.
- [ ] A cross-repo workflow uses `DEVMAN_SELF_DIR` and states its own directories.
- [ ] A new glob widened the hash in the same edit.
- [ ] A header comment says **why the file exists and what it costs**, and cites
      the measurement if there is one.
- [ ] A group change updated that group's `README.md` in the same commit.
- [ ] `dagu validate` passes, `devman show` resolves, `devman run` succeeds, and
      `devman doctor` exits 0.

---

## 12. Worked examples in the tree

| File | Shows |
|---|---|
| `groups/base/workflows/check.yaml` | the minimal one-step workflow |
| `groups/base/workflows/maintain.yaml` | a schedule, parameters, and a report |
| `groups/format/workflows/format.yaml` | a step-level hash precondition |
| `groups/release/workflows/release.yaml` | a gate that fails, and reading `metadata.jsonl` |
| `.devman/workflows/stack-validate.yaml` | the cross-repository shape |
| `.devman/workflows/plane-report.yaml` | `\|\| rc=$?` around a command that fails on purpose |
| `.devman/workflows/agent-review.yaml` | free-text parameters with real defaults, `exclusive` |
| `.devman/workflows/bench-entry.yaml` | a parameter whose default is another project's name |
| `.devman/workflows/gitman-commit-message.yaml` | naming `gpu` for a resource, and calling a server the plane does not supervise |

Each carries a header comment explaining every non-obvious line. Read it before
copying the file.
