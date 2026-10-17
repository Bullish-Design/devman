# 047 — devman, from scratch: a Dagu-native reactive runner

**Status:** the charter, 2026-10-15. It is the only concept devman follows. It
replaces every earlier concept, proposal and plan: 006, 007, 025, 038, 041, 044
and 046 (option C). Those stay in `.scratch/` as history only. Owner rulings
taken in session. Evidence: `SPIKES.md` and
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
| R13 | **Workflow content is overlay content. The required Dagu base is package content.** | F2 and F3 (project 048) show that an editable base can remove required events or set an undefined queue. The packaged base owns `handler_on.exit` and `devman.task`. It keeps history for seven days. The overlay holds workflows, examples and their README. |
| R12 | **No migration.** Old registry roots, generations and compatibility data are deleted. | devman has one user and nothing worth carrying. |

### 2.1 The boundary test

One question decides where a file lives: **would this still be true for someone
else who cloned the repository?**

- **Yes:** it is the project. It stays in the repository, tracked. Example: a
  `base:check` task in `devenv.nix`.
- **No, it is true for this user or this machine:** it goes central, under
  `~/.config/devman`, and reaches the repository as a link with its own
  `.git/info/exclude` line. Example: the workflow that runs that task at 3am.

Never decide this per file type. Every placement applies this one rule. It was
first stated in 025 §P0, after the question was argued five times. R2 and R3
are applications of it.

## 3. The files

### 3.1 What the owner writes

```
~/.config/devman/                  the central overlay (a git repository)
  projects.toml                    the one manifest (§4)
  workflows/<project>/<name>.yaml  workflows for one project only
  library/workflows/<name>.yaml    shared workflows a project can take
```

```
devman/                            this repository (the mechanism)
  dagu/config.yaml                 queues and paths (a template; Nix fills it)
  dagu/guard.sh                    the checkout guard (§5.1)
  src/devman/base.yaml             required Dagu base template
```

The overlay contains workflow content (ruling R13). An edit to a workflow is
live: the watcher recompiles it. The packaged base holds the required handler
and action. Compile fills its three machine tokens (`@bash@`, `@devman@`,
`@stateDir@`) and writes `~/.local/state/devman/base.yaml`, which `config.yaml`
names as the base config. Compile validates the candidate before publication.

### 3.2 What devman writes

```
~/.local/state/devman/
  dags/<project>/<project>.<name>.yaml   compiled files. Dagu's dags_dir
  runs/<project>/                        run logs. Each compiled file's log_dir
  events.jsonl                           every event and what the router did
  compile.json                           the last compile result per project
```

Dagu keeps its own state in `DAGU_HOME` (`~/.local/share/dagu`). The compiled
header sets `log_dir` to `runs/<project>/`, so each project's run logs sit in
one directory that linkman can link (§6). devman writes no run metadata of its
own; the run index stays in Dagu.

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
- A workflow name must match `[A-Za-z0-9][A-Za-z0-9_-]*`. It has no dot, so the
  DAG name `<project>.<workflow>` splits at the last dot.
- An unknown key refuses the project. Two projects with one `path` are both
  refused. A `done`/`failed` cycle refuses the project.
- `take` names library workflows. A file in `workflows/<project>/` with the
  same name replaces the library file for that project. There are two levels
  only: the project, then the library.
- `on` maps an event to a workflow. `event` is an open string. `match` is a
  glob against the event's subject. A file event's subject is a path relative
  to the project. A ref event's subject is a ref name. `run` names a workflow
  that the project has.
- `match` takes a glob or a list of globs. `exclude` is an optional list of
  globs. There is no brace expansion.

## 5. Compile

`devman compile [project…]` turns the manifest and the sources into files in
`dags/`. The watcher (§7) runs it when `projects.toml`, `workflows/` or the
library changes. A person can run it by hand.

For each project, compile does this:

0. **Base.** Fill the tokens of the packaged `src/devman/base.yaml`. Check the
   required handler and action, seven-day retention, and absence of a base
   queue. Validate the candidate base and compiled DAGs with a temporary Dagu
   config. Publish `<state>/base.yaml` only after validation.
1. **Resolve** each workflow: the project's own file, else the library file.
2. **Render** the file. Prepend a header: `working_dir`, `log_dir`, `shell`
   (the guard, §5.1), `env:
   DEVMAN_PROJECT_DIR`, `group: <project>` and `labels: project=<project>`, and
   `params:` `DEVMAN_EVENT` and `DEVMAN_SUBJECT` with empty defaults. The header
   never sets `name:`. The manifest always sets `working_dir`; a source that
   sets it is refused. For `group` and `labels`, the source wins. Top-level
   `env`, `log_dir` and `shell`, and `handler_on.exit`, belong to the header and
   the base: a source that sets one is refused (ruling Q8). A source with its
   own `params:` must declare both event parameters. Each source must name a
   queue that Dagu config defines.
3. **Validate** each changed file with `dagu validate`.
4. **Publish** each changed file by atomic rename into
   `dags/<project>/`. Delete the files of workflows the project no longer has.
5. **Record** the result in `compile.json`.

**Compile refuses a project, and changes none of its files, when:**

- a global compile input is invalid, such as a missing `DEVMAN_GUARD` (compile
  records the refusal and exits 1);
- its `path` does not exist or is not a directory. Compile tests it read-only
  and never creates it, because Dagu creates a missing `working_dir` and the
  run then succeeds in an empty directory;
- a source sets a header-owned key (above), or omits `queue:`, or names a
  non-string, empty or unconfigured queue (Dagu runs an undefined queue at once,
  with no limit; findings F1 and F3 in project 048);
- the packaged base is invalid or lacks `handler_on.exit` or `devman.task`
  (finding F2 in project 048); compile keeps the active base and DAG files;
- a `take` entry or an `on.run` entry names a workflow that does not exist;
- any of its rendered files fails `dagu validate`;
- `workflows/<project>/` exists but the project has no manifest entry (this
  refuses the orphan directory).

A project that left the manifest loses its `dags/<project>/` directory at the
next full compile. Its `runs/<project>/` stays.

A refusal is per project, so one broken project does not block the others. A
refusal is loud: compile exits non-zero, writes the reason to
`compile.json`, and `devman status` shows it. The project keeps its previous
files. Any project refusal or orphan makes the global compile state red.

`compile.json` version 2 records that global state and the input digest from the
last full green compile. `status` and `doctor` compare the live inputs with that
digest. A changed input stays stale until a full compile succeeds. A global
failure keeps the last good DAG files and digest. A partial compile never
advances the digest. See PLAN A.3 and finding F4 in project 048.

One validated reader serves every command that reads `compile.json`. A
missing file is an initial condition: the next full compile starts fresh. A
malformed file is an error, never an initial condition: compile refuses it and
leaves the file and every published file unchanged, and status, show, doctor
and the router name the malformed field's path. Malformed data never counts as
green health.

### 5.1 The checkout guard

Compile checks `path` only at compile time. A checkout that vanishes later
gives green runs that did nothing. So the compiled header sets the DAG shell to
`dagu/guard.sh`. A `shell:` in `base.yaml` does not reach a step on Dagu 2.20.1
(measured in Stage 7: the step ran under `$SHELL`), so the header owns it. The
guard fails a step when `DEVMAN_PROJECT_DIR` has neither
`.git` nor `.jj`. The router also refuses an event for a missing path. A step
with its own `shell:` opts out, and so do built-in action steps.

**Why a header, and not Dagu workspaces.** A `workspace=<project>` label plus
`workspaces/<project>/base.yaml` can set the same values without rendering, and
this works on 2.15.0. Dagu plans to remove workspaces in v3.0 (RFC 003). A
four-line header works on every version.

## 6. The repository view

linkman makes two links in each repository:

| Link | Target | Shows |
|---|---|---|
| `<repo>/.devman/workflows` | `~/.local/state/devman/dags/<project>/` | the exact files Dagu runs, header included. The header names the source file |
| `<repo>/.devman/runs` | `~/.local/state/devman/runs/<project>/` | the run logs of this project's workflows |

Both are machine-local views, so linkman also adds them to
`.git/info/exclude`. Dagu's `hist_retention_days` prunes the logs.

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

1. matches the event against the project's `on` entries, as `compile.json`
   records them;
2. enqueues each matched workflow once, however many subjects match, with
   `dagu enqueue` on the absolute path of the compiled file, and passes
   `DEVMAN_EVENT` and `DEVMAN_SUBJECT` as parameters (`DEVMAN_` is a reserved
   parameter prefix);
3. appends one line to `events.jsonl`: the event, the matches, and the run IDs
   or the refusal.

So "why did this run?" always has an answer in one file.

**Event sources at the start:**

| Event | Source |
|---|---|
| `save` | the watcher: one `watchexec` over the paths of projects that have a `save` entry. It ignores `.git .jj .devenv .direnv .venv node_modules __pycache__ .gitman .worktrees .devman`, compiles at start, and recompiles when `projects.toml`, `workflows/` or `library/` change |
| `commit`, `land` | a jj or git hook that linkman installs; it calls `devman emit` |
| `done`, `failed` | the packaged `handler_on.exit` maps the run status and calls `devman emit` detached, and always exits 0. The subject is the workflow name |
| schedule | Dagu's own `schedule:`. Since 2.17.0 it passes through the queue |
| external | a Dagu webhook on the workflow, or `devman emit` from any script |

A new event source needs no change to devman. It calls `devman emit` with a new
event name, and a manifest entry matches it.

`devman run <workflow>` is a manual event: `devman emit manual --subject
<workflow>`, matched implicitly to that workflow.

## 8. Sharing

Two mechanisms, each for one job:

- **Actions** in the packaged `src/devman/base.yaml` hold required behavior.
  The reserved `devman.task` action runs `devenv tasks run -v <task>` and names
  the failing task on stderr. A workflow cannot replace that action.
- **Library workflows** in the overlay's `library/workflows/` are short files
  that call actions:

```yaml
# library/workflows/check.yaml
queue: light
steps:
  - action: devman.task
    with: { task: base:check }
```

`format` keeps no loop receipt, because `format:fmt` is idempotent. `release`
runs the test as its first step and builds without publishing.

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
- a user service that runs `dagu start-all` with the generated `config.yaml`,
  which names the compiled `base.yaml` (§3.1);
- a user service that runs the watcher.

`config.yaml` sets `paths.dags_dir` to `~/.local/state/devman/dags`, turns on
recursive discovery, and defines every queue. Since 2.17.0 a scheduled run
waits in its queue only when the config defines that queue.

The package ships the required base template and guard. The overlay holds
workflow content, examples and its README (R13). `DEVMAN_LIBRARY` only replaces
workflow content for tests.

The package is a Python project (`pyproject.toml`, `uv.lock`) built for Nix with uv2nix. The interpreter comes from nixpkgs. The uv2nix inputs live in `flake.nix` only. Decided 2026-10-15 (PLAN Q12).

nix-meta pins devman once. A repository pins nothing.

## 11. The CLI

The CLI uses Typer: one typed function per command (PLAN Q11, decided 2026-10-15).

| Command | Does |
|---|---|
| `devman compile [project…]` | §5 |
| `devman emit <event> …` | §7 |
| `devman run <workflow>` | a manual event |
| `devman status [project]` | §6 |
| `devman show <workflow>` | prints the compiled file and its source path |
| `devman doctor` | checks the services, the Dagu version, that `dags/` matches the last compile, and that every action a library workflow names exists in the packaged base |

`status` and `doctor` also report a refused global compile, unreadable input,
or changed input. A version 1 state needs a full compile before health is green.
Malformed state never counts as green: `status` and `show` exit 2 with the
malformed field's path, and `doctor` reports it under `compile clean`.

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
| M7 | Does a running Dagu reread a changed `base.yaml` without a restart? Yes: the next run uses it. | §5 (compile writes `base.yaml`, restarts nothing) |

All seven are measured on 2.20.1. The answers are in `MEASUREMENTS.md`, and
`PLAN.md` §B folds them into the sections above.

## 14. Open questions for the owner

1. ~~Run output~~ — decided 2026-10-15: logs live under
   `~/.local/state/devman/runs/<project>/`, linked into `<repo>/.devman/runs`.
2. ~~Removing the tracked manifests~~ — done 2026-10-15 with
   `remove-manifests.sh`: 60 repositories pushed. testee was skipped, because
   its local `main` holds one unpushed commit. forgelab is archived. The
   central `common/devlayer.nix` no longer imports the devman link module,
   which read the manifest; existing links stay until linkman takes over.
3. ~~Charter timing~~ — decided 2026-10-15: this concept is the only charter,
   now.
4. ~~Plan questions Q1 to Q10~~ — decided 2026-10-15; see `PLAN.md` §E. The
   recommendations stand, except Q7: the library lives in the central overlay
   (R13). Q8: a source with a top-level `env` is refused.
