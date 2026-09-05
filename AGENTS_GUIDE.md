# AGENTS_GUIDE.md — working in the devman repository

Read [`AGENTS.md`](AGENTS.md) first: it holds the law. This file holds the map,
the mechanisms, and the operations.

Read [`USER.md`](USER.md) for the developer-facing view of the same system.

---

## 1. The model in one page

```
a save             → watchexec ─┐
a commit / a push  → git hook   ─┼→ devman run → dagu enqueue → Dagu → devenv tasks run
a developer        → a prompt   ─┤
a cron expression  → the daemon ─┘   (schedule: bypasses the queue)
```

**`devman run` is the layer, not always a process.** The watcher's dispatcher
calls `run.trigger()` in its own process; the other three arrows are the
command. One implementation either way (012, RESULT.md §3.1).

**HOW LONG A SAVE TAKES, AND WHERE THE TIME GOES.** About 2.4 s from the write
to the formatter's own write, and **most of it is one timer**:

| | |
|---|---:|
| watchexec — inotify plus a 50 ms debounce | 72 ms |
| `devman watch --dispatch` — resolve, refuse, `dagu enqueue` | 217 ms |
| **Dagu's queue drain ticker — a 3.000 s period, so a mean wait of** | **1,500 ms** |
| the run starting, then `devenv tasks run` | ≈540 ms |

**The ticker has no configuration key in Dagu 2.15.0; the period is compiled
in.** Do not go looking for one, and do not set anything under `scheduler:` in
`config.yaml` expecting to move it — `lock_retry_interval` and its neighbours
are about locks and zombies, not the drain.

A wait longer than 3 s means the run's queue was at its `max_concurrency`. That
is the limit doing what it says. **Whether the limit is the right number is a
different question, and nobody has measured it** — the five values are a Nix
option default in `nix/nixos-module.nix`, chosen without a core count, and they
are the same on every machine. Do not raise one to make a wait go away.

Measured over n=50 controlled runs and 494 recorded ones:
`.scratch/projects/012-dagu-call-performance/RESULT.md` §2, and §2.4 for which
part of the delay is structural and which part is Dagu's loop.

| Layer | Owns | Never |
|---|---|---|
| **Dagu** | the run: order, queues, retries, history, the web UI | knows what a project is |
| **devenv** | the implementation of one task in one repository | knows what a workflow is |
| **devman** | the contract: registration, projection, resolution, refusal | executes anything itself |

**devman never parses a workflow to understand it.** Three things read a
workflow's text and each is bounded: `dagu validate` in `doctor`, the
`DEVMAN_PROJECT_DIR` cross-repo rule, and the `params:` block a trigger must
fill. Nothing rewrites a file at projection time except the generated header.

---

## 2. Repository map

| Path | What it is |
|---|---|
| `nix/nixos-module.nix` | the **machine** interface — one Dagu user service, the queues, `config.yaml`, `base.yaml`, the watcher unit, the CLI on PATH |
| `nix/dagu.nix` | the Dagu package. nixpkgs ships none; both interfaces call this one file |
| `nix/devman-cli.nix` | the CLI package. Ships from the NixOS module **only** |
| `nix/renderer.nix` | the projection renderer, `devman-project`. The same source, built under the **consuming repository's** nixpkgs so the shell-entry guard can see its store path (§3.1's second exception) |
| `nix/tests/dagu-service.nix` | a NixOS VM test: the unit starts, a projected DAG is discovered, a run lands its logs in the right project |
| `modules/devenv.nix` | the **repo** interface — three options, the `enterShell` guard, §7.3 resolution at evaluation time, and `planFile`. **The projection itself is `src/devman/project.py`**, not shell: it was shell until project 009 stage 3, and four findings were symptoms of that one duplication |
| `groups/` | workflow **content**, one directory per group. `groups/README.md` is the mechanism and the index; each group's own README says what taking it costs |
| `src/devman/` | the CLI: `cli`, `run`, `show`, `doctor`, `watch`, `registry`, `workflow`, and `project` — the projection, which the devenv module runs at shell entry |
| `tests/` | the Python test layer. `tests/README.md` says what it protects and what it refuses to test |
| `.devman/workflows/` | this repository's own workflows. `.devman/workflows/README.md` documents them |
| `.scratch/projects/006-automation-plane/` | the charter and stage logs 1–6 |
| `.scratch/projects/007-standard-workflows/` | the standard-set proposal, plan, open questions and stage log 7 |

`.scratch/projects/001`–`005` are superseded and carry no authority.

---

## 3. The source files, and what each one is responsible for

| File | Responsible for |
|---|---|
| `src/devman/cli.py` | the argument surface. Three commands plus `watch`. `--registry` and `--dagu-home` are global flags, not `DEVMAN_*` variables, because Dagu passes every `DEVMAN_*` through to a run |
| `src/devman/registry.py` | reading `~/.local/share/devman/`. Resolves a directory to a project, refuses a checkout inside a checkout, detects a flat DAG name two projects claim |
| `src/devman/workflow.py` | the only YAML reading there is: `params()`, `triggers_other_dags()`, `holds_project_dir()`, `handlers()`, `queues()` |
| `src/devman/run.py` | the one place that triggers a workflow. Resolves, refuses, exports, enqueues |
| `src/devman/show.py` | prints the **source** file, never the generated projection, so `devman show x > .devman/workflows/x.yaml` round-trips |
| `src/devman/doctor.py` | thirteen checks over the whole plane |
| `src/devman/watch.py` | the watcher's entry point. Reads the registry, execs watchexec, dispatches one batch of events |

### `devman run`'s refusals, and why each exists

| Refusal | The failure it prevents |
|---|---|
| the file does not load | `dagu ls` lists a DAG that cannot load with no indication at all |
| the `dags/` link points elsewhere | two projects render one flat name; the run executes another project's file, in this project's directory, and reports success |
| a cross-repo parent holds `DEVMAN_PROJECT_DIR` | every child runs in the parent's directory, successfully and silently |
| a cross-repo parent declares no `DEVMAN_SELF_DIR` | the same, from the other side |
| the directory variable would be empty or is not a directory | Dagu creates a directory named literally `${DEVMAN_PROJECT_DIR}` and reports success |
| a declared parameter has no value | the run does something nobody asked for |

`run.py` also clears `SHELL` in the child environment. Dagu resolves a step's
shell from `$SHELL` and falls back to `default_shell` only when it is unset — so
without that line every step runs under the login shell of whoever triggered it.

### `devman doctor`'s checks

`plane` · `queues` · `load` (a `dagu validate` per projected file) · `queue names`
· `literal ${DEVMAN_PROJECT_DIR} directories` · `drift` (an override against what
it shadows) · `stale entries` · `ageing runs` · `projection` · `handlers` ·
`cross-repo` · `trigger targets` · `watcher`.

It exits 1 when it has findings. `--prune` removes stale entries; they restore
themselves at the next shell entry, which is what makes pruning safe.

**`check_load` is the cost.** Measured across the whole rollout at **87.6 ms per
projected file**, flat from 6 projects to 54 — about 15 s at 169 workflows. If it
passes 30 s the answer is a `--project` scope, not a heavier queue.

---

## 4. The registry

```
~/.local/share/devman/
├── projects/<project>/metadata.json          # schema 4: identity, path, groups,
│   │                                         # local, workflows, triggers, plan
├── projects/<project>/triggers.toml          # a copy of the repo's own layer,
│   │                                         # so the guard can compare it
│   └── workflows/<workflow>.yaml             # the GENERATED projection
└── dags/<project>.<workflow>.yaml -> ../projects/<project>/workflows/<workflow>.yaml
```

- `dags/` is Dagu's flat view; `projects/` is devman's.
- A DAG is keyed by its file's base name, so `<project>.<workflow>` is what
  `dagu ls`, the scheduler and `dagu enqueue` all agree on.
- **`<project>-<workflow>` is not injective.** `devman-b` + `check` and `devman`
  + `b-check` render the same name. `registry.dag_link_fault` is what catches it.
- **The registry is derived and the repository is canonical.** Everything there
  is reconstructable by re-entering every registered repository's shell.
- **Nothing walks the disk looking for repositories.** §15.1 forbids it. Reading
  devman's own registry is not scanning.

### The generated projection

Since stage 6 each projected file is the source body with a header:

```yaml
# devman: generated projection — do not edit.
# Edit the source and re-enter the shell:
#   /nix/store/…-devman-base-check.yaml
env:
  - DEVMAN_PROJECT_DIR: /home/you/project
working_dir: /home/you/project
log_dir: /home/you/project/.devman/.runs/logs
<the source body, unchanged>
```

**The header adds; it never overwrites.** A body that states its own
`working_dir`, `log_dir` or `env:` keeps them — which is how a cross-repo
workflow gets `DEVMAN_SELF_DIR` instead.

This is what lets Dagu's own scheduler fire a workflow: the daemon has one
environment for the whole machine and nothing to fill in.

### The shell-entry guard

`enterShell` must be **idempotent** (devenv runs the hook twice per shell) and
must **fork nothing** on the common path (its cost is charged twice, on the
critical path of every shell).

It compares the rendered `metadata.json` against the one on disk, and each
override's body against the **tail** of its projection. The tail test is a slice,
not `${var%pattern}`: the pattern form costs 5.6 ms per firing over five
overrides, the slice costs 0.76 ms.

**The branch that writes cannot report.** devenv discards the capture
subprocess's output, and that firing is the one that performs the write. There is
no `devman: registered` line and there cannot be one.

---

## 5. Operations

Everything runs inside the devenv shell.

```bash
devenv shell                       # interactive
devenv shell -- <cmd>              # one command; also re-projects
```

These are the task names **this repository** defines, because devman adopts
itself. They come from the groups it takes; see `devenv.nix` and
`groups/README.md`.

| Task | Command |
|---|---|
| lint | `devenv tasks run -v base:check` |
| the suite | `devenv tasks run -v base:test` |
| the Python tests, fast | `devenv tasks run -v base:unit` |
| format | `devenv tasks run -v format:fmt` |
| validate every shipped workflow | `nix build .#checks.x86_64-linux.groups-validate` |
| the Python tests, hermetically | `nix build .#checks.x86_64-linux.python-tests` |
| the machine module, in a VM | `nix build .#checks.x86_64-linux.dagu-service` |
| the plane's health | `devman doctor` |
| re-project after editing a group file or an override | `devenv shell -- true` |
| what a project projects | `devman show` |
| what one workflow resolves to | `devman show <workflow>` · `devman show <workflow> --path` |
| trigger without enqueueing | `devman run <workflow> --print` |

**`devman doctor` must exit 0 before committing a change to `modules/`,
`groups/`, `nix/` or `src/devman/`.**

### Talking to Dagu directly

The plane's Dagu home is `~/.local/share/dagu`. `devman run` states
`--dagu-home` rather than inheriting one, because an unset `DAGU_HOME` makes
`dagu` build a fresh home and seed five example DAGs.

```bash
export DAGU_HOME=~/.local/share/dagu
dagu ls
dagu status <project>.<workflow>
systemctl --user status dagu devman-watch
```

**Never use `dagu start`.** It ignores queues entirely.

---

## 6. Editing rules, by area

### A group workflow (`groups/*/workflows/*.yaml`)

- One step, one `devenv tasks run -v <group>:<name>`. Adding a second step needs
  an argument against `PROPOSAL.md` §1.1.
- No top-level `name:`, no `working_dir:`, no `log_dir:`, no `handler_on:`.
- `queue:` stays — it is the one thing that genuinely varies.
- `-v` is load-bearing. Without it devenv captures the task's stdout and prints
  none of it, on both paths.
- No bashisms. A step does not run under the shell you expect; `$EPOCHREALTIME`
  failed once for exactly this reason.
- Every taker of the group pays for the change. Say what the group asks of a
  repository in that group's `README.md`, in the same commit.

### A group's `triggers.toml`

- `<glob> = <workflow>`, matched against a path relative to the repository root.
- **Widening a glob requires widening the workflow's hash in the same edit.**
  Otherwise the new language's saves fire a run whose precondition is never true,
  which reports `Succeeded` with a skipped step. Nothing checks this.
- A tombstone group must never hold one.

### `modules/devenv.nix`

- Anything in `enterShell` costs every shell entry, twice. Measure it. Criterion
  7's budget is 10 ms for the whole module.
- Anything that forks belongs in `projectScript`, which runs only when the guard
  says the entry changed.
- `metadata.json` is written **last**, so an interrupted projection leaves an
  entry that does not match and is retried.

### `nix/nixos-module.nix`

- It must never learn a project fact. No project names, no per-project options.
- A queue rename is a migration across every workflow that names it. Dagu accepts
  an undeclared name silently and gives it concurrency 1, so a missed file
  serialises rather than runs free.

### `src/devman/`

- Every refusal names the file and the field.
- Read the registry; do not write it, except through `doctor --prune`.
- ruff with `E,F,I,N,W,UP,B,C4,SIM`, line length 88, target py313. `.scratch/` is
  excluded.

---

## 7. Traps, all of them measured

| Trap | What happens |
|---|---|
| `handler_on:` in a workflow | replaces `base.yaml`'s exit handler whole-field. The run writes **no** `metadata.jsonl` line, with a clean `dagu status` and correct logs |
| a DAG-level `preconditions:` | an unmet one records `Aborted` — the same status a cancelled run gets. Use a step-level one |
| a queue name that does not exist | accepted silently, at concurrency 1 — shared by every workflow naming it, so a typo serialises rather than frees |
| `schedule:` on anything expensive | a scheduled run **bypasses the queue**. 58 concurrent `devman doctor` runs measured 139 s each against 14.3 s alone |
| a bare failing command in a step | Dagu runs a step's script with `set -e` already on (`$-` reports `ehuB`). The rest of the step never runs. Use `|| rc=$?` |
| a top-level `name:` | `dagu validate` fails: "entrypoint document must not define name" |
| `type: build` for a formatter | it cannot declare one path as both input and output. Rejected at run time; `dagu validate` does not catch it |
| a parameter Dagu did not declare | rejected. Declare `DEVMAN_PROJECT_DIR: ""` first, or declare none |
| editing an override without re-entering the shell | the previous version runs, silently, with `doctor` reporting nothing wrong |
| `devenv test` as a rung | exits 0 having tested nothing in 30 of 58 repositories |
| a git worktree inside a registered checkout | it never registers, so `devman run` typed inside it would target the outer project. `run` refuses instead |

---

## 8. Where the evidence lives

| Question | Read |
|---|---|
| why is this line here at all? | the stage log entry its comment cites |
| what is the design? | `.scratch/projects/006-automation-plane/CONCEPT.md` |
| why five workflows and not nine? | `.scratch/projects/007-standard-workflows/PROPOSAL.md` |
| what is still unsettled? | `.scratch/projects/007-standard-workflows/OPEN_QUESTIONS.md` |
| what did the rollout to 53 repositories measure? | `.scratch/projects/007-standard-workflows/STAGE_7_LOG.md` |
| what did the five investigations find? | `.scratch/projects/006-automation-plane/FINDINGS.md` |

A stage log entry has a fixed shape: **the answer, the versions, the exact
command, the evidence, the charter impact, and what the entry left on the
machine.** Write new entries in that shape.
