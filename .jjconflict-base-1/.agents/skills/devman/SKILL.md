---
name: devman
description: Entry point for all devman work — the Dagu automation plane. Use it to run, inspect and diagnose workflows in any registered repository, and to route to the devman-workflow and devman-adopt sub-skills for authoring a workflow or joining a repository to the plane.
auto_trigger:
  keywords: ["devman", "devman run", "devman doctor", "devman show", "dagu", "dagu enqueue", "automation plane", "workflow group", "base:check", "base:test", "format:fmt", "release:build", "DEVMAN_PROJECT_DIR", "DEVMAN_SELF_DIR", ".devman/workflows", ".devman/.runs", "triggers.toml", "plane report", "devenv tasks run"]
---

# devman — the coordinator

devman is a **development automation plane**. One Dagu control plane runs per
machine. Every devenv-managed repository joins through one Nix flake and inherits
a small, shared set of workflows.

**Dagu orchestrates. devenv executes. devman is the contract between them.**
devman executes nothing itself and never parses a workflow to understand it.

## Route

| Ask | Go to |
|---|---|
| write or change a workflow, a group, or a trigger mapping | the `devman-workflow` skill |
| bring a repository into the plane, or fix a repository that will not register | the `devman-adopt` skill |
| run, inspect, diagnose | stay here |
| change the plane itself — `modules/`, `nix/`, `src/devman/` | the devman repository's `AGENTS.md` and `AGENTS_GUIDE.md` |

## How the plane behaves

**These are properties, not permissions.** Each one is measured. Knowing them
saves an afternoon; each is followed by the symptom you see when you forget it.

**Work runs inside the devenv shell.** Batch commands into one
`devenv shell -- …`. A bare `uv`, `python`, `pytest` or `ruff` picks up whatever
is on `PATH`, which is usually a different version from the one the workflow
runs.

**`devman run` enqueues.** `dagu start` executes immediately and ignores the
queue, so two DAGs on `exclusive` both start. Use `devman run` and the queue
applies.

**A green run tells you the steps passed, not that the run happened where you
meant.** A run that got its parameter and not its environment succeeds and writes
its logs into a directory named literally `${DEVMAN_PROJECT_DIR}`. Check where
the logs landed.

**A run that reports success while producing an incorrect result is the failure
worth designing against** — the wrong output, the wrong script, the right work in
the wrong directory. Prefer a loud refusal to a silent default, and prefer a
check that can fail to one that cannot. This is about correctness. Whether a
correct result should have been reviewed first is a tier question — see
**Categorising a workflow's writes** below.

**The plane holds no project fact.** No absolute path in a workflow file, no
project name in the machine module, no per-project Nix option. A workflow that
needs another project's path takes it as a parameter whose default is a project
*name*, and the trigger resolves it.

**The registry is derived; the repository is canonical.** Read
`~/.local/share/devman/` freely. It is rewritten by entering a shell, and pruned
by `devman doctor --prune`.

**Exit codes:** `0` ok · `1` finding · `2` usage. `devman doctor` exits 1 when it
has findings. That is a finding, not a crash.

## Groups — the mechanism

devman ships the mechanism. **The content documents itself**: read
`groups/README.md` for the index, and each group's own `README.md` for what it
ships and what it asks a repository to define. Check rather than recall which
workflows exist.

```nix
devman.groups = [ "base" "format" ];    # precedence order
```

- **Resolution is whole-file**, in the order the repository lists its groups,
  with the repository's own `.devman/workflows/` as the last layer. No field
  merge.
- **Taking a group is an agreement to define that group's task names.** The
  namespace is the group's own name; devenv requires `namespace:name`.
- **Taking a group is the whole opt-in; not taking it is the whole opt-out.**
  There is no per-workflow Nix option, because an inherited workflow nothing
  triggers costs nothing.
- **One workflow runs one `devenv tasks run`.** The workflow names the rung; the
  repository's devenv task graph decides what that rung pulls in.
- A group earns its existence when taking it costs the repository something it
  cannot decline any other way: a task name it must define, or a write to its own
  files it did not ask for.
- A directory under `groups/` with no `workflows/` is a **tombstone** — a group
  that was deleted, kept so a stale pin still evaluates. It projects nothing and
  throws nothing.

```bash
devman show          # the groups this project takes, and where each file came from
```

## Commands

```bash
devman run <workflow>                 # trigger in the current project
devman run <workflow> --project NAME  # from anywhere
devman run <workflow> NAME=VALUE      # pass a declared parameter
devman run <workflow> --print         # print the trigger, enqueue nothing
devman show                           # every workflow this project projects
devman show <workflow>                # the resolved file, to start an override
devman show <workflow> --path         # just the path
devman doctor                         # the whole plane
devman doctor --prune                 # remove stale registry entries
```

`devman watch` is the watcher service's entry point. systemd runs it. A person
does not.

**Registration has one path — entering the shell.** There is no `register` or
`unregister` command, and `doctor` reports what a `list` or `status` command
would have shown.

## Read what a run did

```bash
tail -3 .devman/.runs/metadata.jsonl          # dag, run id, status, log path
ls -t .devman/.runs/reports/ | head           # what a run left for a person
ls .devman/.runs/logs/<project>_<workflow>/   # each step's own output
```

**Read the `.err` file first when a run fails.** On devenv 2.1.2 the task's own
output goes to stdout and devenv's ledger — which names the failing task — goes
to stderr, and Dagu files the two separately. The failing name also lands in
Dagu's recorded `error` field, which is what the web UI shows. devenv 2.2.0 puts
both streams on stderr.

| Status | Means |
|---|---|
| `succeeded` | every step ran and passed |
| `failed` | a step exited non-zero |
| `partially_succeeded` | a step failed under `continue_on: {failure: true}` |
| `aborted` | cancelled, **or** a DAG-level precondition was not met |

## Diagnose

`devman doctor` first, always. **21 checks** — projection and validation, queue
names, a literal `${DEVMAN_PROJECT_DIR}` directory, overrides that drifted from
what they shadow, stale entries, ageing runs, `handler_on` blocks that would
silence `metadata.jsonl`, cross-repo shape, fan-out bounds, declared writes,
local library sources and what they resolve to, triggers pointing at workflows
nobody projects, and what the watcher last fired.

| Symptom | Cause | Fix |
|---|---|---|
| `no project named 'X'` | never registered, or renamed | enter that repository's shell once |
| `is not inside a registered repository` | outside every registered path | enter the shell, or pass `--project` |
| `refusing to resolve 'X' from this directory` | a worktree or submodule **inside** a registered checkout | give it a distinct `devman.project`, or pass `--project` |
| `the DAG named X points at …` | two projects claim one DAG name | enter the repository's shell to re-project it |
| `these declared parameters have no value` | an empty default | give it a real default, or pass `NAME=VALUE` |
| `no such task` from devenv | a group's task name is not defined | define it, or drop the group |
| `× Invalid task name: check` | devenv requires `namespace:name` | write `<group>:<name>` |
| an override does not run | the projection is a generated copy | `devenv shell -- true`, then `devman show <workflow>` |
| a save fires nothing | no `triggers.toml` group, glob mismatch, or the hash precondition skipped | check `devman show` for the groups, then `systemctl --user status devman-watch` |

Machine side:

```bash
systemctl --user status dagu devman-watch
export DAGU_HOME=~/.local/share/dagu && dagu ls
```

The web UI is `http://127.0.0.1:8080`.

## The shared names

| Name | Whose field |
|---|---|
| the queue names — `light` `normal` `heavy` `gpu` `exclusive` | Dagu's `queue:` |
| `DEVMAN_PROJECT_DIR` | the project a run targets |
| `DEVMAN_SELF_DIR` | a cross-repo workflow's own directory |
| the `.devman/.runs/` path shape | Dagu's `log_dir:` |

Everything else belongs to the repository. **Adding a name here changes the
charter**, because every repository inherits it at once. Weigh it that way.

**`.devman/` belongs to the repository.** devman reserves `workflows/` and
`.runs/` inside it and touches nothing else there.

## Choosing what to automate

**These are the questions worth asking, with what each one costs when the answer
goes the wrong way.** Most have a workaround; two rarely do. Judge the case, and
write the reasoning into the workflow file so the next reader can weigh it again.

**Two that rarely have a good answer:**

- **Is it irreversible outside this machine?** Publishing a wheel, pushing a tag,
  deploying. A plane that can publish is a plane whose bug reaches other people.
  `release` builds and does not publish, on purpose.
- **Could it succeed while doing nothing?** `devenv test` exited 0 having tested
  nothing in 30 of 58 repositories, and nothing noticed for a month. If a run
  cannot fail when it does nothing, add the assertion that lets it — `pytest`
  already exits 5 on zero collected.

**One that is usually a smell:**

- **Does it re-implement a task the repository already has?** Calling `pytest`
  directly rather than the repository's own test task drifts, and drifts
  silently, because both keep passing.

**Five that are trade-offs. Know the number, then decide:**

| Question | The measurement | When it is still worth it |
|---|---|---|
| Does an editor already do this synchronously? | the plane's round trip after a save is 1.44 s and lands in a log file; an LSP answer is tens of ms and lands at the cursor | the work is too slow for a keystroke, or must run when no editor is open |
| Does it need a fact the repository did not state? | an unset variable is not an error in Dagu — it creates a directory of that literal name and carries on | the fact can be a parameter with a real default, or a project name the trigger resolves |
| Will anybody read its output? | 54 identical nightly reports is one report nobody opens | the output is read by a command rather than a person, or only appears when something is wrong |
| Is it expensive **and** scheduled? | **a scheduled run does not pass through its queue** — 58 scheduled DAGs started at once with queue depth 0, while 58 enqueued never exceeded 4 | the work is cheap by construction, or it is triggered rather than scheduled. See `.scratch/projects/020-scheduling-metered-work/` |
| Is it expensive **and** fanned out by a parent? | `dag.run` executes the child in place and bypasses the queue; `dag.enqueue` respects it but returns immediately, so the parent never learns the child failed | the parent does not need the child's verdict — a dispatcher does not, a verifier does |

## Categorising a workflow's writes

**Every workflow that writes falls into one of three tiers** (project 015). The
tier says where the write lands, and it is a useful thing to state even when
nothing enforces it.

| Tier | What it covers | Where it lands |
|---|---|---|
| `free` | a file that did not exist, and agent surface — `.agents/**`, `docs/**`, notes, a tool's own hidden directory (`.devman/`, `.loci/`, `.gitman/`) | the working tree, directly |
| `lane` | an edit to an existing tracked source file — dependency updates, code generation, autofix | a `gitman` lane, for a person to merge when they choose |
| `insitu` | an idempotent normalisation of a file the workflow's own trigger watched. `format` is the only holder | the working tree, directly |

**An unattended write to trunk has no tier**, and that is the one shape to keep
out of a workflow: the change appears in somebody's `git status` the next
morning with nothing to explain it. A lane carries a name and a diff instead.

**`insitu` is narrow on purpose.** It adds no content and a second run changes
nothing. Its three bounds are its entry price: its own opt-in group, a content
hash, and a fixpoint. Code generation, dependency updates and autofix beyond
formatting are none of those things — they are `lane`.

**Declare the tier in `writes.toml`**, beside `triggers.toml`, one table per
workflow with `tier` and `paths`. `devman doctor` reads it. The declaration
cannot prove a workflow writes what it says; it makes the claim legible, which
is the difference between a reviewer reading a shell script and `doctor` reading
a set.

---

_The design is written down. `.scratch/projects/006-automation-plane/CONCEPT.md`
is the charter; `007-standard-workflows/PROPOSAL.md` amends it; the stage logs
hold the measurement behind every non-obvious line. Read the log before changing
a line that looks redundant._
