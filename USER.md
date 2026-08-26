# USER.md — the devman user guide

devman is a **development automation plane**. One Dagu control plane runs per
machine. Every devenv-managed repository joins it through one Nix flake.

**Dagu orchestrates. devenv executes. devman is the contract between them.**
devman itself executes nothing.

This file is how to use the plane. [`README.md`](README.md) is the shape of it.

> **This guide describes the mechanism, not the content.** Which workflows exist,
> and which task names they ask you to define, is in each group's own README —
> start at [`groups/README.md`](groups/README.md).

---

## 1. Prerequisites

| Need | Why |
|---|---|
| **NixOS**, with `services.devman-dagu.enable = true` | the Dagu user service, the queues, the `devman` CLI and the watcher all ship from `nixosModules.default` |
| **devenv** in every repository that joins | a workflow step runs `devenv tasks run` |
| **git** | registration writes one ignore rule to `.git/info/exclude` |

The machine side installs itself. Check it:

```bash
systemctl --user status dagu
devman doctor
```

`devman doctor` prints the project count, the workflow count, and any findings.
A healthy plane ends with `Nothing to report.`

The web UI is on `http://127.0.0.1:8080` by default. It binds loopback, because
the plane runs one developer's own checkouts.

---

## 2. Adopt a repository

### 2.1 `devenv.yaml` — the input and the import

```yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"

imports:
  - devman/modules
```

**Pin local consumers with `git+file:`.** It records `rev` and `narHash` in
`devenv.lock`, just as `git+https:` does, but reads committed files only. Use
`path:` only for the repository under active edit.

The import path is `devman/modules`, not `devman/modules/devenv.nix`. devenv
resolves `<input>/<subdir>` and then looks for `devenv.nix` inside it.

### 2.2 `devenv.nix` — three keys

```nix
devman = {
  enable  = true;
  project = "myproject";
  groups  = [ "base" ];
};
```

| Key | Rule |
|---|---|
| `enable` | required to join |
| `project` | **required, and stated rather than inferred.** Identity that defaulted to the directory name would break on a rename: the repository would re-register as new and lose its run history |
| `groups` | the groups this repository inherits, in precedence order. `[ ]` is legal — the repository then has only its own `.devman/workflows/` |

Two optional keys exist: `registryDir` (must match the machine's) and
`installClient` (puts the Dagu client on this shell's PATH, default true).

### 2.3 Define the task names your groups call

**Taking a group is an agreement to define that group's task names.** Each
group's README states which, and what each one is expected to mean.

```nix
tasks."<group>:<name>".exec = "the command";
```

The namespace is the group's own name. **devenv requires `namespace:name`** — an
un-namespaced task is an evaluation error.

**If a repository cannot honour a name, it does not define it.** The workflow
then fails loudly with devenv's own `no such task`. Never satisfy a name with
something that does nothing: a workflow reporting success having checked nothing
is the one failure this whole design exists to avoid.

### 2.4 Enter the shell once

```bash
devenv shell -- true
```

That registers the repository. **There is no `devman register`, and there will
never be one** — registration has exactly one path, so nothing can drift from it.

The hook is guarded by a content hash, so every entry after the first costs about
0.3 ms. It also prints nothing on success, by design: devenv runs the hook twice
and discards the output of the firing that performs the write.

### 2.5 Confirm

```bash
devman show          # what this project projects, and where each file came from
devman run <workflow>
devman doctor        # the plane's own health
```

### 2.6 What registration creates

```
<repo>/.devman/workflows/            your own workflow files — TRACKED
<repo>/.devman/.runs/logs/           each step's stdout and stderr
<repo>/.devman/.runs/reports/        what a run leaves for a person to read
<repo>/.devman/.runs/artifacts/      what a run builds
<repo>/.devman/.runs/metadata.jsonl  one line per run: dag, id, status, log path
```

`.devman/.runs/` is added to `.git/info/exclude`, never to `.gitignore` — that
file may be a read-only store symlink, and writing to it would dirty the tree the
rule exists to keep clean.

**`.devman/` is yours.** devman reserves two names inside it — `workflows/` and
`.runs/` — and never reads, writes or inspects anything else there.

---

## 3. Run a workflow

```bash
devman run <workflow>                      # in the current repository
devman run <workflow> --project NAME       # from anywhere
devman run <workflow> NAME=VALUE           # pass a declared parameter
devman run <workflow> --print              # print the trigger, enqueue nothing
```

`devman run` resolves the project from the current directory, exports
`DEVMAN_PROJECT_DIR`, passes it as a parameter, and calls `dagu enqueue`.

**It enqueues; it never starts.** `dagu start` ignores queues entirely. Queue
names are the plane's whole lever on concurrency, so `devman run` has no `--now`
and must never grow one.

**It refuses rather than enqueueing a run that would write to the wrong place.**
Every refusal names the file and the field. See §8.

---

## 4. Read what happened

```bash
tail -3 .devman/.runs/metadata.jsonl              # dag, run id, status, log path
ls -t .devman/.runs/reports/ | head               # what a run left for you
ls .devman/.runs/logs/<project>_<workflow>/       # each step's own output
```

**Read the `.err` file, not the `.out` file, when a run fails.** On devenv 2.1.2
your task's own output goes to stdout and devenv's task ledger — which names the
task that failed — goes to stderr, and Dagu files the two separately. The failing
task name also lands in Dagu's own recorded `error` field, which is what the web
UI shows. devenv 2.2.0 puts both streams on stderr.

Status strings you will see in `metadata.jsonl`:

| Status | Means |
|---|---|
| `succeeded` | every step ran and passed |
| `failed` | a step exited non-zero |
| `partially_succeeded` | a step failed under `continue_on: {failure: true}` |
| `aborted` | cancelled, **or** a DAG-level precondition was not met |

**A green run is not proof the trigger was right.** A run that got the parameter
and not the environment succeeds and writes its logs into a directory named
literally `${DEVMAN_PROJECT_DIR}`. `devman run` prevents this; `devman doctor`
checks for the leftovers. If you ever enqueue by hand, check where the logs
landed.

---

## 5. Change what a workflow does

### 5.1 Override one file

Resolution layers by group in the order you list them, and your own
`.devman/workflows/` is the last layer. Shadowing is **whole-file**, never a
field merge.

```bash
devman show <workflow> > .devman/workflows/<workflow>.yaml   # start from what runs today
$EDITOR .devman/workflows/<workflow>.yaml
devenv shell -- true                                         # re-project
devman show <workflow>                                       # confirm
```

`devman show` prints the file on stdout and everything about where it came from
on stderr, so the redirect stays exact.

**An edit needs one shell entry to reach Dagu.** The projection is a generated
copy, not a symlink. The shell-entry guard compares your override's body against
the tail of its projection, so it notices an edit in place — but only at shell
entry.

`devman doctor` reports every override and how far it has drifted from the group
file it shadows. That is a report, not a complaint.

### 5.2 Write a new workflow

Put a Dagu YAML file in `.devman/workflows/<name>.yaml`. It is a plain Dagu file
with no devman-specific key in it.

```yaml
# .devman/workflows/smoke.yaml
queue: light
steps:
  - name: smoke
    run: devenv tasks run -v my:smoke
```

Five rules, each forced by a measurement:

1. **No top-level `name:`.** `dagu validate` fails — "entrypoint document must
   not define name". A DAG's identity is its file name.
2. **No `working_dir:` and no `log_dir:`.** The projection writes both, per
   project. State them only for a cross-repository workflow (§5.4).
3. **Declare `DEVMAN_PROJECT_DIR: ""` first if you declare any parameter at
   all.** Dagu rejects a parameter a DAG did not declare, and `devman run` always
   passes the directory variable. Declare none, or declare that one first.
4. **Every declared parameter needs a real default.** `devman run` refuses a
   parameter that would be empty. A default that names a registered project is
   filled with that project's path, which is how a workflow points at another
   repository without holding an absolute path.
5. **No `handler_on:`.** Dagu inherits the machine's `base.yaml` whole-field, so
   defining any handler replaces the exit handler — and the run then writes
   **no** `metadata.jsonl` line at all, silently, with a clean `dagu status`.

Two more that bite in practice:

- **`-v` on every `devenv tasks run`.** Without it devenv captures the task's
  stdout and prints none of it, on the success path and the failure path alike.
- **Dagu runs a step's script with `set -e` already on.** A bare failing command
  aborts the script at that line, so the rest never runs. Use `|| rc=$?` when the
  script must finish.

Then `devenv shell -- true` and `devman run smoke`.

**Prefer the task graph to a second step.** Order belongs in `devenv.nix`, where
you can also run it by hand:

```nix
tasks."my:test".after = [ "my:check" ];
```

A task with only `after` needs no `exec`: it runs its dependencies and then does
nothing itself, and a failure in a dependency still fails the run. **Siblings in
an `after` list run concurrently**, so chain the edges when you want fail-fast.

Agents: the full checklist is `.agents/skills/devman-workflow/SKILL.md`.

### 5.3 Choose a queue

| Queue | Limit | Say it when |
|---|---|---|
| `light` | 4 | seconds of work, no build |
| `normal` | 2 | minutes; also a workflow that fans out into child runs |
| `heavy` | 1 | a build that wants the machine |
| `gpu` | 1 | one caller at a time on the GPU |
| `exclusive` | 1 | this must not overlap with other exclusive work — long, non-deterministic, reads a tree another run may rewrite |

`heavy` says "this costs a lot of machine". `exclusive` says "this must not
overlap". `gpu` names a resource. All three are limit 1 on this machine; say the
one that is true.

**A queue name is a one-way door.** Dagu accepts a queue that does not exist
silently, and gives that name a queue of its own at concurrency 1. So a typo
does not free a workflow, it serialises one: a misspelt `light` runs one at a
time instead of four, beside every other file carrying the same misspelling.
Nothing says so at run time. `devman doctor` checks the names for you.

**`exclusive` does not give a run the machine.** Dagu's queues are independent,
so `light`, `normal` and `heavy` runs proceed beside an exclusive one.

### 5.4 A workflow that triggers other repositories' workflows

The parent must **not** hold `DEVMAN_PROJECT_DIR`. A parent exports its
parameters into every child's environment, and that environment outranks the
child's own `with.params` — so a parent holding the name drags every child into
its own directory, successfully and silently.

So the parent names its own directory `DEVMAN_SELF_DIR`, states its own
`working_dir` and `log_dir`, and takes each target as a parameter whose default
is a **project name**:

```yaml
params:
  - DEVMAN_SELF_DIR: ""
  - TARGET_DIR: someproject

working_dir: ${DEVMAN_SELF_DIR}
log_dir: ${DEVMAN_SELF_DIR}/.devman/.runs/logs

queue: normal
type: chain
steps:
  - name: target-check
    action: dag.run
    with:
      dag: someproject-check
      params:
        DEVMAN_PROJECT_DIR: ${TARGET_DIR}
```

`devman run` enforces both halves of this rule and refuses if either is missing.
A workflow spanning several projects belongs to none of them, so it belongs to
devman's own `.devman/workflows/`.

---

## 6. Opt into more

**Taking a group is the whole opt-in; not taking it is the whole opt-out.** There
is no per-workflow Nix option, because an inherited workflow you never trigger
costs nothing.

```nix
groups = [ "base" "format" ];
```

Read that group's README before adding it. A group exists precisely when taking
it costs you something you cannot decline any other way — a task name you must
define, or a write to your own files you did not ask for. See
[`groups/README.md`](groups/README.md).

### React to a save

A group whose `triggers.toml` maps globs to workflow names makes this repository
reactive. One `watchexec` user service reads the registry and watches only the
repositories that declare triggers.

A workflow that rewrites files its own trigger watches breaks the loop with a
**step-level content-hash precondition** — a hash rather than a timer, so your
own edit one second after the write still fires. The watcher also ignores
`.devman/.runs/`.

> **Widening a glob requires widening that workflow's hash in the same edit.**
> Otherwise the new files fire a run whose precondition is never true, and the run
> reports `Succeeded` with a skipped step — the same status a correct loop-break
> produces. Nothing checks this.

### Run something on a commit

The hook is yours, through devenv's `git-hooks` module:

```bash
devenv inputs add git-hooks github:cachix/git-hooks.nix --follows nixpkgs
```

```nix
git-hooks.hooks.devman-check = {
  enable = true;
  name = "devman check";
  entry = "devman run check";
  stages = [ "post-commit" ];
  pass_filenames = false;
  always_run = true;
};
```

- **It is not a gate.** `devman run` enqueues and returns, so the commit is not
  blocked and the workflow starts a second or two later. To stop a bad commit,
  use a `pre-commit` hook that runs the task directly.
- **The run reads the tree it finds**, which is the tree after the commit.
- **It costs a devenv input** — about 20 ms on every shell entry — and a
  generated `.pre-commit-config.yaml` in the working tree.

### Run something on a schedule

Use Dagu's own `schedule:` key, in the workflow file:

```yaml
schedule: "5 0 * * *"
queue: light
```

This works because the projection is generated per project: each copy states its
own `working_dir`, `log_dir` and directory variable, so the daemon needs nothing
from a trigger.

> **A scheduled run does not pass through its queue.** 58 DAGs sharing one
> schedule all started at once with queue depth 0. **Nothing throttles the
> scheduled set**, so schedule only work that is cheap by construction.

To opt out of a schedule a group ships, shadow the file and leave the key out.

**When a timer is right instead.** A systemd user timer is the answer when the
schedule belongs to one repository rather than to a group:

```ini
[Service]
Type=oneshot
ExecStart=/run/current-system/sw/bin/devman run <workflow> --project <name>
```

`--project` is what makes this work from a timer, which has no working directory
in any repository. **A timer holds project names and drifts in two directions,
and only one tells you:** a renamed project makes the unit fail loudly; a newly
adopted project is simply never scheduled, silently.

---

## 7. Housekeeping

| Directory | Pruned by |
|---|---|
| `.devman/.runs/logs/` | the machine's `hist_retention_days` — **per DAG, and only when that DAG runs** |
| `.devman/.runs/reports/` | whatever your groups ship for it |
| `.devman/.runs/artifacts/` | **nothing.** Remove them by hand |
| `.devman/.runs/metadata.jsonl` | nothing owns it, so it survives retention |

The per-DAG rule is the one to remember: a repository whose workflows never run
keeps its log tree forever. A cheap nightly run is what makes retention fire at
all.

---

## 8. Troubleshooting

Start here, always:

```bash
devman doctor
```

It reports: files that fail `dagu validate`, queue names the machine does not
declare, a literal `${DEVMAN_PROJECT_DIR}` directory, overrides that have drifted
from what they shadow, stale registry entries, ageing runs, projection
mismatches, `handler_on` blocks that would silence `metadata.jsonl`, cross-repo
rule violations, triggers pointing at workflows nobody projects, and what the
watcher last fired.

`devman doctor --prune` removes stale entries; they restore themselves the next
time that repository's shell is entered.

### Common refusals, and what each one means

| Message | Cause | Fix |
|---|---|---|
| `no project named 'X'` | never registered, or renamed | enter that repository's shell once |
| `is not inside a registered repository` | you are outside every registered path | enter the shell, or pass `--project` |
| `refusing to resolve 'X' from this directory` | you are in a checkout **inside** a registered one — a linked worktree or a submodule | give it a distinct `devman.project` and enter its shell, or pass `--project` |
| `the DAG named X points at …` | two projects claim one DAG name | enter the repository's shell to re-project it (§9.2) |
| `these declared parameters have no value` | a parameter with an empty default | give it a real default, or pass `NAME=VALUE` |
| `DEVMAN_PROJECT_DIR would be empty` | the directory variable would not resolve | the registered path is gone — `devman doctor --prune` |
| `it triggers other workflows and defines DEVMAN_PROJECT_DIR for itself` | §5.4's rule | use `DEVMAN_SELF_DIR` and `with.params` |
| `devman: group 'X' does not exist` | a group name that is not in `groups/` | fix the name; a deleted group leaves a tombstone that does **not** throw |
| `× Invalid task name: check` | devenv requires `namespace:name` | write `<group>:<name>` |
| `no such task` from devenv | you took a group and did not define its task | define it, or drop the group |

### Nothing happens when I save a file

1. Does the repository take a group with a `triggers.toml`? `devman show` lists
   the groups.
2. Does the glob match? It is matched against a path relative to the repository
   root.
3. Did the precondition skip the step? A skipped step reports `Succeeded`. If a
   glob was widened without widening the hash, every run skips forever and
   nothing says so.
4. `systemctl --user status devman-watch`.

### My override does not seem to run

The projection is a generated copy. Run `devenv shell -- true`, then
`devman show <workflow>` to confirm.

### My task cannot find its tool

**The task runner's PATH is not the interactive shell's PATH**, in both
directions. A tool the shell finds may be missing in a task, and a module a task
imports may be missing in the shell. Prove the task, not the shell:

```bash
devenv tasks run -v <group>:<name>
```

---

## 9. Where else to look

| Path | What |
|---|---|
| [`groups/README.md`](groups/README.md) | the group mechanism, and an index of the groups this flake ships |
| [`.devman/workflows/README.md`](.devman/workflows/README.md) | devman's own workflows |
| `.scratch/projects/006-automation-plane/CONCEPT.md` | the charter |
| `.scratch/projects/007-standard-workflows/PROPOSAL.md` | the standard set, and what must never become a workflow |
