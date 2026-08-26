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

## The law

1. **Run everything inside the devenv shell.** Never invoke bare `uv`, `python`,
   `pytest` or `ruff`. Batch commands into one `devenv shell -- …`.
2. **`devman run` enqueues; it never starts.** `dagu start` ignores queues
   entirely. Never suggest it, and never add a `--now`.
3. **A green run is not proof the trigger was right.** A run that got the
   parameter and not the environment succeeds and writes its logs into a
   directory named literally `${DEVMAN_PROJECT_DIR}`. Check where the logs
   landed.
4. **A successful run that did the wrong thing is the failure this design exists
   to prevent.** Prefer a loud refusal to a silent default. Never make a check
   pass by making it check nothing — a task whose body is `true` is forbidden.
5. **The plane never learns a project fact.** No absolute path in a workflow
   file, no project name in the machine module, no per-project Nix option.
6. **The registry is derived; the repository is canonical.** Read
   `~/.local/share/devman/` freely. Write to it only by entering a shell, or with
   `devman doctor --prune`.
7. **Exit codes:** `0` ok · `1` finding · `2` usage. `devman doctor` exits 1 when
   it has findings; that is a finding, not a crash.

## Groups — the mechanism

devman ships the mechanism. **The content documents itself**: read
`groups/README.md` for the index, and each group's own `README.md` for what it
ships and what it asks a repository to define. Never state from memory which
workflows exist — check.

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
- **One workflow runs exactly one `devenv tasks run`.** The workflow names the
  rung; the repository's devenv task graph decides what that rung pulls in.
- A group exists when taking it costs the repository something it cannot decline
  any other way: a task name it must define, or a write to its own files it did
  not ask for.
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

**There is no `list`, no `status`, no `register` and no `unregister`, and there
never will be.** Registration has exactly one path — entering the shell — and the
rest is what `doctor` reports.

## Read what a run did

```bash
tail -3 .devman/.runs/metadata.jsonl          # dag, run id, status, log path
ls -t .devman/.runs/reports/ | head           # what a run left for a person
ls .devman/.runs/logs/<project>_<workflow>/   # each step's own output
```

**Read the `.err` file, not the `.out` file, when a run fails.** On devenv 2.1.2
the task's own output goes to stdout and devenv's ledger — which names the failing
task — goes to stderr, and Dagu files the two separately. The failing name also
lands in Dagu's recorded `error` field, which is what the web UI shows. devenv
2.2.0 puts both streams on stderr.

| Status | Means |
|---|---|
| `succeeded` | every step ran and passed |
| `failed` | a step exited non-zero |
| `partially_succeeded` | a step failed under `continue_on: {failure: true}` |
| `aborted` | cancelled, **or** a DAG-level precondition was not met |

## Diagnose

`devman doctor` first, always. Thirteen checks: files that fail `dagu validate`,
undeclared queue names, a literal `${DEVMAN_PROJECT_DIR}` directory, overrides
that drifted from what they shadow, stale entries, ageing runs, projection
mismatches, `handler_on` blocks that would silence `metadata.jsonl`, cross-repo
rule violations, triggers pointing at workflows nobody projects, and what the
watcher last fired.

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

## The four global names, and the list is closed

| Name | Whose field |
|---|---|
| the queue names — `light` `normal` `heavy` `gpu` `exclusive` | Dagu's `queue:` |
| `DEVMAN_PROJECT_DIR` | the project a run targets |
| `DEVMAN_SELF_DIR` | a cross-repo workflow's own directory |
| the `.devman/.runs/` path shape | Dagu's `log_dir:` |

Everything else belongs to the repository. **Adding a fifth name is a charter
change, not an implementation detail.**

**`.devman/` belongs to the repository.** devman reserves `workflows/` and
`.runs/` inside it and never touches anything else there.

## What must never become a workflow

Say no, and point at `PROPOSAL.md` §12:

1. anything an editor already does synchronously — LSP diagnostics, format-in-buffer
2. anything irreversible outside this machine — publishing, tagging, deploying
3. anything that writes tracked source with nobody present — dependency updates,
   code generation. A formatter in its own group — one glob, a content hash —
   is the single bounded exception
4. anything whose success is indistinguishable from doing nothing
5. anything needing a fact the repository did not state
6. a second implementation of a task the repository already has
7. anything whose output nobody reads — 54 identical nightly reports is zero reports
8. anything expensive, on a schedule — **a scheduled run bypasses its queue**

---

_The design is written down. `.scratch/projects/006-automation-plane/CONCEPT.md`
is the charter; `007-standard-workflows/PROPOSAL.md` amends it; the stage logs
hold the measurement behind every non-obvious line. Read the log before changing
a line that looks redundant._
