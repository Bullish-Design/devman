# 047 — devman, from scratch: a Dagu-native reactive runner

**Status:** concept, 2026-10-15. Owner rulings taken in session. Supersedes
`046-one-registry/PLAN.md` (option C). Evidence: `SPIKES.md` and
`DAGU_RELEASES.md` in this directory.

## 1. What devman is

devman is a friendly way to run Dagu workflows across the owner's
repositories. It does three things:

1. It **compiles** central workflow sources into files that Dagu runs, one
   project at a time, and keeps them current.
2. It **routes events** to workflows. A save, a commit, a finished run or any
   other event becomes a queued Dagu run.
3. It **shows** each repository what runs in it, when, and with what result.

Dagu does everything else: scheduling, queues, execution, history, the web
interface (UI), retries, notifications and agent steps. **If Dagu has a
feature, devman uses it and does not rebuild it.**

devman does not link files into repositories. linkman owns every link,
including the repository view in §6.

## 2. Rulings

| # | Ruling | Why |
|---|---|---|
| R1 | Dagu stays, pinned at **2.20.1**. Everything else is open. | 2.17.0 sends scheduled runs through queues. 2.17.2 allows a read-only DAG directory. 2.16.6 reloads base config live. |
| R2 | **One central manifest:** `~/.config/devman/projects.toml`. A repository tracks nothing devman-specific. | Which workflows run in a checkout is a fact about this machine, not about the project (boundary test, 025 §P0). |
| R3 | **Workflows are central and visible in the repository**, not tracked there. | The owner wants to read what runs from the repository itself. |
| R4 | **An explicit list** registers a project. One table in `projects.toml` per project. | No shell-entry registration, no discovery, no stale entries. |
| R5 | **Live compile** into one stable DAG directory, by atomic rename per file. No generations, no pointer, no reload adapter. | `SPIKES.md` spike 1: Dagu applies a per-file change on the next tick with no restart. It does not follow a repointed directory symlink. |
| R6 | **Sharing uses Dagu actions** in `base.yaml`, plus a small library of short workflow files. | Each project file stays short and complete. Dagu validates action input. |
| R7 | **Steps prefer repository tasks.** Library workflows call repository tasks. A project workflow may run any command. | Shared workflows stay portable. Project workflows stay free. |
| R8 | **Events are pluggable through one command,** `devman emit`. Anything that can run a command is an event source. | No plugin API to maintain. |
| R9 | **Agent work is Dagu-native:** `harness.run`, `git.worktree.*`, `human.task`. No Agentman. | `SPIKES.md` spike 3: a real `claude` call worked in a linked work tree. |
| R10 | **Safety is minimal:** correctness refusals only. No write tiers, no reload gate. | The owner's ruling. A refusal still beats a silent wrong result (property 4). |
| R11 | **Home Manager installs devman:** the CLI, the Dagu user service and the watcher user service. No NixOS module. | A devman change needs no system rebuild. This matches the 045 toolbelt. |
| R12 | **No migration.** Old registry roots, generations and compatibility data are deleted. | devman has one user and nothing worth carrying. |

## 3. The files

### 3.1 What the owner writes

```
~/.config/devman/                  the central overlay (a git repository)
  projects.toml                    the one manifest (§4)
  workflows/<project>/<name>.yaml  workflows for one project only
```

```
devman/                            this repository
  library/<name>.yaml              shared workflows a project can take
  dagu/base.yaml                   shared actions, handlers, defaults
  dagu/config.yaml                 queues and paths (a template; Nix fills it)
```

### 3.2 What devman writes

```
~/.local/state/devman/
  dags/<project>/<project>.<name>.yaml   compiled files. Dagu's dags_dir
  events.jsonl                           every event and what the router did
  compile.json                           the last compile result per project
```

Dagu keeps its own state in `DAGU_HOME` (`~/.local/share/dagu`), including run
logs. devman writes no run metadata of its own.

The subdirectory per project matters. Under `recursive: true`, two files with
one base name in two subdirectories make Dagu report "No DAGs found". The
`<project>.` prefix makes every base name unique. The subdirectory gives
linkman one directory to link (§6).

## 4. The manifest

```toml
# ~/.config/devman/projects.toml

[devman]
path = "~/Documents/Projects/devman"
take = ["check", "test", "format"]          # library workflows

[[devman.on]]
event = "save"
match = "**/*.py"
run   = "format"

[[devman.on]]
event = "land"
match = "main"
run   = "check"

[gitman]
path = "~/Documents/Projects/gitman"
take = ["check", "test"]
```

- The table key is the project name. It must match
  `[A-Za-z0-9][A-Za-z0-9._-]*`.
- `take` names library workflows. A file in `workflows/<project>/` with the
  same name replaces the library file for that project. There are two levels
  only: the project, then the library.
- `on` maps an event to a workflow. `event` is an open string. `match` is a
  glob against the event's subject. A file event's subject is a path relative
  to the project. A ref event's subject is a ref name. `run` names a workflow
  that the project has.

## 5. Compile

`devman compile [project…]` turns the manifest and the sources into files in
`dags/`. The watcher (§7) runs it when `projects.toml`, `workflows/` or the
library changes. A person can run it by hand.

For each project, compile does this:

1. **Resolve** each workflow: the project's own file, else the library file.
2. **Render** the file. Prepend a header: `working_dir`, `env:
   DEVMAN_PROJECT_DIR`, `group: <project>` and `labels: project=<project>`. The
   header adds keys and never overwrites a key the source sets.
3. **Validate** each changed file with `dagu validate`.
4. **Publish** each changed file by atomic rename into
   `dags/<project>/`. Delete the files of workflows the project no longer has.
5. **Record** the result in `compile.json`.

**Compile refuses a project, and changes none of its files, when:**

- its `path` does not exist or is not a directory;
- a `take` entry or an `on.run` entry names a workflow that does not exist;
- any of its rendered files fails `dagu validate`;
- `workflows/<project>/` exists but the project has no manifest entry (this
  refuses the orphan directory).

A refusal is per project, so one broken project does not block the others. A
refusal is loud: compile exits non-zero, writes the reason to
`compile.json`, and `devman status` shows it. The project keeps its previous
files, and status says they are stale.

**Why a header, and not Dagu workspaces.** A `workspace=<project>` label plus
`workspaces/<project>/base.yaml` can set the same values without rendering, and
this works on 2.15.0. Dagu plans to remove workspaces in v3.0 (RFC 003). A
four-line header works on every version.

## 6. The repository view

linkman links `<repo>/.devman/workflows` to
`~/.local/state/devman/dags/<project>/`. The repository then shows the exact
files that Dagu runs, header included. The header names the source file.

`devman status`, run in a repository, prints for each workflow:

- its source (project or library);
- its triggers and its schedule;
- its queue;
- the last run, its time and its result (read from Dagu);
- a compile refusal or staleness, if any.

The Dagu UI groups the same workflows by `group: <project>`.

## 7. Events

`devman emit <event> [--project P] [--subject S] [key=value…]` is the one
entry point. When `--project` is missing, the router finds the project whose
`path` contains the current directory.

The router:

1. matches the event against the project's `on` entries;
2. enqueues each match with `dagu enqueue`, and passes the event fields as
   parameters;
3. appends one line to `events.jsonl`: the event, the matches, and the run IDs
   or the refusal.

So "why did this run?" always has an answer in one file.

**Event sources at the start:**

| Event | Source |
|---|---|
| `save` | the watcher: one `watchexec` over the listed project paths |
| `commit`, `land` | a jj or git hook that linkman installs; it calls `devman emit` |
| `done`, `failed` | Dagu's `handler_on` in `base.yaml` calls `devman emit` |
| schedule | Dagu's own `schedule:`. Since 2.17.0 it passes through the queue |
| external | a Dagu webhook on the workflow, or `devman emit` from any script |

A new event source needs no change to devman. It calls `devman emit` with a new
event name, and a manifest entry matches it.

`devman run <workflow>` is a manual event: `devman emit manual --subject
<workflow>`, matched implicitly to that workflow.

## 8. Sharing

Two mechanisms, each for one job:

- **Actions** in `dagu/base.yaml` hold shared steps. Example: `devman.task`
  runs `devenv tasks run -v <task>` and names the failing task on stderr.
- **Library workflows** in `library/` are short files that call actions:

```yaml
# library/check.yaml
queue: light
steps:
  - action: devman.task
    with: { task: base:check }
```

A multi-step shared workflow can become a Dagu action package
(`source:target@version`) later. It runs in its own work directory, so the
project directory must arrive as a parameter. Start without packages.

**Fleet upkeep is one workflow, not one per project.** It lives in
`workflows/devman/` and loops over the project list. It replaces 44 nightly
copies of `maintain`. Its report succeeds when it runs. A finding goes to a
notification, not to the run's exit status.

## 9. Agent work

An agent workflow is ordinary Dagu:

1. `git.worktree.add` on a new branch;
2. `harness.run` with a provider, a model, and a cost cap such as
   `max-budget-usd`;
3. a step that commits the result to the branch;
4. `human.task` for review. Since 2.17.0 it can send feedback and rewind;
5. `git.worktree.remove`.

Step 3 is required. `SPIKES.md` showed that `remove` with `force: true` deletes
uncommitted output. The branch is the lane. A person lands it, with gitman or
by hand.

Dagu does not report agent cost. The cap comes from the CLI flag.

## 10. Install

The devman flake exports one Home Manager module. It installs:

- the `devman` CLI;
- Dagu 2.20.1, built by `nix/dagu.nix`;
- a user service that runs `dagu start-all` with the generated `config.yaml`
  and `base.yaml`;
- a user service that runs the watcher.

`config.yaml` sets `paths.dags_dir` to `~/.local/state/devman/dags`, turns on
recursive discovery, and defines every queue. Since 2.17.0 a scheduled run
waits in its queue only when the config defines that queue.

nix-meta pins devman once. A repository pins nothing.

## 11. The CLI

| Command | Does |
|---|---|
| `devman compile [project…]` | §5 |
| `devman emit <event> …` | §7 |
| `devman run <workflow>` | a manual event |
| `devman status [project]` | §6 |
| `devman show <workflow>` | prints the compiled file and its source path |
| `devman doctor` | checks the services, the Dagu version, and that `dags/` matches the last compile |

## 12. What goes

Everything not named above. In particular:

- the registry, the compatibility registry and its writer, generations, the
  active pointer, the reload adapter and its markers;
- `mkRegistry`, the store-path registry and the NixOS module;
- `devman_link`, `devman_contract`, `central.py` and `excludes.py` (linkman's job);
- `.devman/project.toml` and `.devman/triggers.toml` in every repository;
- groups, policies, shadowing beyond two levels, `writes.toml` and the write tiers;
- `agent.py` and the Agentman contract;
- per-repository run metadata, `maintain` per project, and most of `doctor`.

The stage logs and the old charters stay in `.scratch/` as history.

## 13. Open measurements

Measure each one before the code depends on it:

| # | Question | Decides |
|---|---|---|
| M1 | On 2.20.1, does a scheduled run of a DAG with `queue: light` wait in the queue? | R1, §10 |
| M2 | On 2.20.1, what does a run do when `working_dir` does not exist? It must fail, not succeed. | §5 refusals |
| M3 | Does a `handler_on` in `base.yaml` reach every DAG, and can it call `devman emit` without blocking the run? | §7 `done`/`failed` |
| M4 | Does recursive discovery accept `dags/<project>/` subdirectories when linkman links one of them into a repository? | §3.2, §6 |
| M5 | How much does one `watchexec` cost over 33 repositories? | §7 `save` |
| M6 | Does `dagu enqueue` take parameters and a run name, so the router can pass event fields? | §7 |

## 14. Open questions for the owner

1. Run output: Dagu's own log directory only (this concept), or a copy under
   `<repo>/.devman/`?
2. Removing `.devman/project.toml` and `.devman/triggers.toml` is a tracked
   edit in about 33 repositories. One lane per repository, or one fleet
   script?
3. Does this concept replace 006, 007 and 025 as the charter now, or after the
   code ships?
