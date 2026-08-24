# USER.md — the devman user guide

devman is a **development automation plane**. One Dagu control plane runs per
machine. Every devenv-managed repository joins it through one Nix flake, and gets
the same small set of workflows.

**Dagu orchestrates. devenv executes. devman is the contract between them.**
devman itself executes nothing.

Read [`README.md`](README.md) for the shape of the whole thing. This file is how
to use it.

---

## 1. Prerequisites

| Need | Why |
|---|---|
| **NixOS**, with `services.devman-dagu.enable = true` | the Dagu user service, the queues, the `devman` CLI and the watcher all ship from `nixosModules.default` |
| **devenv** in every repository that joins | every workflow step runs `devenv tasks run` |
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

Four edits, in two files, once per repository.

### 2.1 `devenv.yaml` — the input and the import

```yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"

imports:
  - devman/modules
```

**Pin with `git+https` and an explicit `rev`.** That form records `rev` and
`narHash` in `devenv.lock`. `git+file` records neither and follows the branch
head silently, so a local checkout is never pinned.

The import path is `devman/modules`, not `devman/modules/devenv.nix`. devenv
resolves `<input>/<subdir>` and then looks for `devenv.nix` inside it.

### 2.2 `devenv.nix` — three keys and two tasks

```nix
devman = {
  enable  = true;
  project = "myproject";
  groups  = [ "base" ];
};

tasks."base:check".exec = "ruff check .";
tasks."base:test".exec  = "pytest";
```

| Key | Rule |
|---|---|
| `enable` | required to join |
| `project` | **required, and stated rather than inferred.** Identity that defaulted to the directory name would break on a rename: the repository would re-register as new and lose its run history |
| `groups` | defaults to `[ "base" ]`. `[ ]` is legal — the repository then has only its own `.devman/workflows/` |

Two optional keys exist: `registryDir` (must match the machine's) and
`installClient` (puts the Dagu client on this shell's PATH, default true).

### 2.3 Enter the shell once

```bash
devenv shell -- true
```

That registers the repository. **There is no `devman register`, and there will
never be one** — registration has exactly one path, so nothing can drift from it.

The hook is guarded by a content hash, so the second entry and every entry after
it cost about 0.3 ms.

### 2.4 Confirm

```bash
devman show          # what this project projects, and where each file came from
devman run check     # trigger the fast rung
devman doctor        # the plane's own health
```

### 2.5 What registration creates

```
<repo>/.devman/workflows/     your own workflow files — TRACKED
<repo>/.devman/.runs/logs/      each step's stdout and stderr
<repo>/.devman/.runs/reports/   what a run left behind for a person to read
<repo>/.devman/.runs/artifacts/ what a run built
<repo>/.devman/.runs/metadata.jsonl  one line per run: dag, id, status, log path
```

`.devman/.runs/` is added to `.git/info/exclude`, never to `.gitignore` — that
file may be a read-only store symlink, and writing to it would dirty the tree the
rule exists to keep clean.

**`.devman/` is yours.** devman reserves two names inside it — `workflows/` and
`.runs/` — and never reads, writes or inspects anything else there.

---

## 3. The standard set

**One workflow runs exactly one `devenv tasks run`.** The workflow names the
rung; your devenv task graph decides what that rung pulls in.

| Workflow | Group | Queue | Fired by | Runs |
|---|---|---|---|---|
| `check` | `base` | `light` (4) | you; a post-commit hook | `base:check` |
| `test` | `base` | `normal` (2) | you; a pre-push hook | `base:test` |
| `maintain` | `base` | `light` (4) | the schedule, `5 0 * * *` | nothing of yours |
| `format` | `format` | `light` (4) | the watcher, on a `.py` save | `format:fmt` |
| `release` | `release` | `heavy` (1) | you | `release:build`, behind a gate |

The ladder has two rungs and no third:

| | `check` | `test` |
|---|---|---|
| Budget | ≤ 5 s warm | ≤ 5 min |
| What it tells you | this tree does not lint, or does not typecheck | the suite passes |

**A budget is guidance, not a check.** Nothing notices a `check` that grows to
four minutes.

### Composing rungs

Do not add steps to a workflow. Add edges to your task graph, in `devenv.nix`,
where you can also run them by hand:

```nix
tasks."base:check".after = [ "python:lint" "python:typecheck" ];
tasks."base:test".after  = [ "base:check" ];
```

A task with only `after` needs no `exec`: it runs its dependencies and then does
nothing itself, and a failure in a dependency still fails the run. That is how a
repository honours two groups' names with one command body.

**Siblings in an `after` list run concurrently**, so a failing task does not stop
the others. If you want fail-fast ordering, chain the `after` edges.

### If you cannot honour a task name

**Do not define it.** `devman run check` then fails loudly with devenv's own
`no such task`. Never write `base:check = true`: a workflow that reports success
having checked nothing is the one failure the whole design exists to avoid.

---

## 4. Run a workflow

```bash
devman run check                      # in the current repository
devman run test --project siteman     # from anywhere, by name
devman run maintain KEEP_DAYS=30      # pass a declared parameter
devman run check --print              # print the trigger, enqueue nothing
```

`devman run` resolves the project from the current directory, exports
`DEVMAN_PROJECT_DIR`, passes it as a parameter, and calls `dagu enqueue`.

**It enqueues; it never starts.** `dagu start` ignores queues entirely. Queue
names are the plane's whole lever on concurrency, so `devman run` has no `--now`
and must never grow one.

**It refuses rather than enqueueing a run that would write to the wrong place.**
Every refusal names the file and the field. See §8.

---

## 5. Read what happened

```bash
tail -3 .devman/.runs/metadata.jsonl              # dag, run id, status, log path
ls -t .devman/.runs/reports/ | head               # what a run left for you
ls .devman/.runs/logs/<project>-<workflow>/       # each step's own output
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

---

## 6. Change what a workflow does

### 6.1 Override one file

Resolution layers by group in the order you list them, and your own
`.devman/workflows/` is the last layer. Shadowing is **whole-file**, never a
field merge.

```bash
devman show test > .devman/workflows/test.yaml    # start from what runs today
$EDITOR .devman/workflows/test.yaml
devenv shell -- true                              # re-project
devman show test                                  # confirm
```

`devman show` prints the file on stdout and everything about where it came from
on stderr, so the redirect stays exact.

**An edit needs one shell entry to reach Dagu.** The projection is a generated
copy, not a symlink. The shell-entry guard compares your override's body against
the tail of its projection, so it notices an edit in place — but only at shell
entry.

`devman doctor` reports every override and how far it has drifted from the group
file it shadows.

### 6.2 Write a new workflow

Put a Dagu YAML file in `.devman/workflows/<name>.yaml`. It is a plain Dagu file
with no devman-specific key in it.

```yaml
# .devman/workflows/smoke.yaml
queue: light
steps:
  - name: smoke
    run: devenv tasks run -v my:smoke
```

Five rules, each of them forced by a measurement:

1. **No top-level `name:`.** `dagu validate` fails — "entrypoint document must
   not define name". A DAG's identity is its file name.
2. **No `working_dir:` and no `log_dir:`.** The projection writes both, per
   project. State one only for a cross-repository workflow (§6.4).
3. **Declare `DEVMAN_PROJECT_DIR: ""` first if you declare any parameter at
   all.** Dagu rejects a parameter a DAG did not declare, and `devman run` always
   passes the directory variable. Declare none, or declare that one first.
4. **Every declared parameter needs a real default.** `devman run` refuses a
   parameter that would be empty. A default that names a registered project is
   filled with that project's path, which is how a workflow points at another
   repository without holding an absolute path.
5. **No `handler_on:`.** Dagu inherits `base.yaml` whole-field, so defining any
   handler replaces the machine's exit handler — and the run then writes **no**
   `metadata.jsonl` line at all, silently, with a clean `dagu status`.

Then `devenv shell -- true` and `devman run smoke`.

Agents: the full checklist is `.agents/skills/devman-workflow/SKILL.md`.

### 6.3 Choose a queue

| Queue | Limit | Say it when |
|---|---|---|
| `light` | 4 | seconds of work, no build |
| `normal` | 2 | the suite; minutes |
| `heavy` | 1 | a build that wants the machine |
| `gpu` | 1 | one caller at a time on the GPU |
| `exclusive` | 1 | this must not overlap with other exclusive work — long, non-deterministic, reads a tree another run may rewrite |

`heavy` says "this costs a lot of machine". `exclusive` says "this must not
overlap with other exclusive work". `gpu` names a resource. All three are limit 1
on this machine; say the one that is true, because `exclusive` would serialize a
GPU run against every other exclusive workflow for a reason that has nothing to
do with the GPU.

**A queue name is a one-way door.** Dagu accepts a queue that does not exist
silently and applies no limit at all, so a typo is unobservable at run time.
`devman doctor` checks the names for you.

### 6.4 A workflow that triggers other repositories' workflows

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
  - OBSERVANTIC_DIR: observantic

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

`devman run` enforces both halves of this rule and refuses if either is missing.
The worked example is `.devman/workflows/stack-validate.yaml`.

---

## 7. Opt into more

### Format on save

```nix
groups = [ "base" "format" ];
tasks."format:fmt".exec = "ruff format .";
```

Saving a `.py` file now fires `format`. One `watchexec` user service reads the
registry and watches only the repositories that declare triggers.

The loop is stopped by a **content hash** in the workflow's step-level
precondition, not by a timer — so your own edit one second after the formatter
wrote still fires. The watcher also ignores `.devman/.runs/`.

Taking the group is the whole opt-in. Not taking it is the whole opt-out.

### Build a release behind a gate

```nix
groups = [ "base" "release" ];
tasks."release:build".exec = "uv build --out-dir .devman/.runs/artifacts";
```

`devman run release` refuses unless the tree is clean **and** this project's last
recorded `test` succeeded. A refused release reports `Failed`, on purpose.

**It builds. It does not publish.** Pushing a tag or uploading a wheel is
irreversible and wants a credential; a repository that wants that adds the step
to its own shadowing copy.

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

**It is not a gate.** `devman run` enqueues and returns, so the commit is not
blocked. It also costs about 20 ms on every shell entry, forever.

### Run something on a schedule

`maintain` already runs nightly in every repository that takes `base`. For your
own workflow, use Dagu's own `schedule:` key in your own file:

```yaml
schedule: "5 0 * * *"
queue: light
```

> **A scheduled run does not pass through its queue.** 58 DAGs sharing one
> schedule all started at once with queue depth 0. **Nothing throttles the
> scheduled set**, so schedule only work that is cheap by construction.

To opt out of `maintain`'s schedule, shadow the file and leave the key out.

---

## 8. Troubleshooting

Start here, always:

```bash
devman doctor
```

It reports: files that fail `dagu validate`, queue names the machine does not
declare, a literal `${DEVMAN_PROJECT_DIR}` directory, overrides that have drifted
from what they shadow, stale registry entries, ageing runs, projection mismatches,
`handler_on` blocks that would silence `metadata.jsonl`, cross-repo rule
violations, triggers pointing at workflows nobody projects, and what the watcher
last fired. `devman doctor --prune` removes stale entries; they restore
themselves the next time that repository's shell is entered.

### Common refusals, and what each one means

| Message | Cause | Fix |
|---|---|---|
| `no project named 'X'` | never registered, or renamed | enter that repository's shell once |
| `is not inside a registered repository` | you are outside every registered path | enter the shell, or pass `--project` |
| `refusing to resolve 'X' from this directory` | you are in a checkout **inside** a registered one — a linked worktree or a submodule | give it a distinct `devman.project` and enter its shell, or pass `--project` |
| `the DAG named X points at …` | two projects render the same flat `<project>-<workflow>` name | rename one project or one workflow, then re-enter both shells |
| `these declared parameters have no value` | a parameter with an empty default | give it a real default, or pass `NAME=VALUE` |
| `DEVMAN_PROJECT_DIR would be empty` | the directory variable would not resolve | the registered path is gone — `devman doctor --prune` |
| `it triggers other workflows and defines DEVMAN_PROJECT_DIR for itself` | §6.4's rule | use `DEVMAN_SELF_DIR` and `with.params` |
| `× Invalid task name: check` | devenv requires `namespace:name` | write `base:check`, not `check` |
| `no such task` from devenv | you took a group and did not define its task | define it, or drop the group |

### The failure that is not an error

**A green run is not evidence that the trigger was right.** A run that got the
parameter and not the environment succeeds and writes its logs into a directory
named literally `${DEVMAN_PROJECT_DIR}` in whatever tree the daemon started in.
`devman run` prevents this and `devman doctor` checks for the leftovers. If you
enqueue by hand, check where the logs landed.

### Nothing happens when I save a file

1. Does the repository take a group with a `triggers.toml`? `devman show` lists
   the groups.
2. Does the glob match? It is matched against a path relative to the repository
   root.
3. Did the precondition skip the step? A skipped step reports `Succeeded`. If you
   widened a glob without widening the hash in the same edit, every run will skip
   forever and nothing will say so.
4. `systemctl --user status devman-watch`.

### My override does not seem to run

The projection is a generated copy. Run `devenv shell -- true`, then
`devman show <workflow>` to confirm.

---

## 9. Where else to look

| Path | What |
|---|---|
| `groups/base/README.md` | the two task names, the two rungs, `maintain`, hooks, schedules |
| `groups/format/README.md` | reactivity, the loop break, the widening rule |
| `groups/release/README.md` | the policy gate and what it cannot check |
| `.devman/workflows/README.md` | this repository's own workflows, and hand-triggering as a specification |
| `.scratch/projects/006-automation-plane/CONCEPT.md` | the charter |
| `.scratch/projects/007-standard-workflows/PROPOSAL.md` | the standard set, and what must never become a workflow |
