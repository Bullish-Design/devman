# devman

The development automation plane.

> **devman installs one Dagu control plane per machine, and gives every
> devenv-managed repository a shared automation contract through one Nix flake.**

Dagu orchestrates. devenv executes. devman is the contract between them, and
executes nothing itself.

## Status

**Stages 1 to 7 are shipped**, and the plane runs on the development machine.

| Stage | What it delivered |
|---|---|
| 1 | the flake: `nixosModules.default` (one Dagu user service, queues, ports, state paths), `modules/devenv.nix` (the repo interface), the first groups, hash-guarded registration in `enterShell` |
| 2 | the plane turned on: automatic registration, the registry schema, queues and their limits, the `.devman/` run-state layout, whole-file shadowing, and a cross-repo workflow |
| 3 | reactivity: the `devman` CLI, one `watchexec` user service reading the registry, the trigger group, and log retention |
| 4 | work worth doing: a review workflow, `base/maintain`, the `release` group with a policy gate, and this repository's own agent-review and benchmark-campaign workflows |
| 5 | the refusals: a checkout inside a checkout, a flat DAG name two projects claim, and the timer that silently never schedules a new project |
| 6 | the projection became a **generated** file per project, so Dagu's own scheduler can fire a workflow without a trigger to fill in the directory |
| 7 | the standard set: nine workflows in four groups became **five in three**, the ladder became two rungs, `devman doctor` moved into one nightly plane report, and the plane went from 6 registered repositories to 53 |

**53 projects and 167 DAGs are registered on that machine**, with `devman doctor`
clean.

**No stage added machinery.** The contract is still four global names, the CLI is
still three commands, the repo interface is still three keys, and the queue list
is still five. Every deliverable is a file.

## What the plane does for you

| Run | What you get afterwards |
|---|---|
| `devman run check` | the fast check, as an exit code — no build, no tests |
| `devman run test` | the suite, as an exit code |
| `devman run release` | `.devman/.runs/reports/release-<run id>.md`, and a **refusal** unless the tree is clean and this project's last recorded `test` succeeded |
| `devman run maintain` | old reports pruned, artifacts counted, and one report — nightly, without you asking |

Every run appends one line to that repository's `.devman/.runs/metadata.jsonl`,
on the success path and the failure path alike. **A workflow's job is to leave
enough behind that you can see what it did without running it again** — nothing
in the plane checks whether a run did the *right* thing, and nothing is going to.

## How a repository adopts it

Two files, then two task lines.

First, the input and the import in `devenv.yaml`:

```yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"

imports:
  - devman/modules
```

Pin with `git+https` and an explicit `rev`. That form records `rev` and `narHash`
in `devenv.lock`; `git+file` records neither and follows the branch head
silently.

Then three keys in `devenv.nix`:

```nix
devman = {
  enable  = true;
  project = "observantic";
  groups  = [ "base" ];
};
```

`project` is stated, never inferred from the directory name, so renaming the
checkout keeps the run history.

And the two task names `base` calls:

```nix
tasks."base:check".exec = "ruff check .";
tasks."base:test".exec  = "pytest";
```

Enter the shell once and the repository is registered. There is no `devman
register` and there never will be — registration has exactly one path (§5.2).

A workflow is a Dagu YAML file with no devman-specific key in it. Groups layer by
directory; a repository overrides one by shadowing the file name.

## The standard set

**One workflow runs exactly one `devenv tasks run`.** The workflow names the
rung; the repository's devenv task graph decides what that rung pulls in. That
one rule is why there are three groups instead of six, and why criterion 14 — the
task graph exists once — now holds by construction rather than by everyone's
care.

| Group | Workflows | Tasks it asks for | Who takes it |
|---|---|---|---|
| `base` | `check`, `test`, `maintain` | `base:check`, `base:test` | every repository — it is the default |
| `format` | `format` | `format:fmt` | opt-in: saving a `.py` file reformats it |
| `release` | `release` | `release:build` | opt-in: build an artifact behind a policy gate |

**A group exists when taking it costs the repository something it cannot decline
any other way** — a task name it must define, or a write to its own files it did
not ask for. What fires a workflow is not the test; what it touches is.
`maintain` fires itself nightly and still rides in `base`, because it writes only
under `.devman/.runs/`.

**There are no ecosystem groups.** A language differs in what a task *is*, and
`devenv.nix` already holds that. `groups/python/` and `groups/python-format/` are
tombstones: empty directories that let a stale pin keep evaluating.

## Commands

| Command | Does |
|---|---|
| `devman run <workflow>` | trigger a workflow in the current project |
| `devman show <workflow>` | print the resolved file, to start an override |
| `devman doctor` | diagnose the plane, and report shadowed files and their drift |

`devman watch` is the fourth subcommand and it is not a fourth command: it is the
watcher service's entry point, run by systemd rather than by a person.

```bash
devman run test                    # in the current repository
devman run test --project siteman  # from anywhere, by name
devman run maintain KEEP_DAYS=30   # a parameter
devman show test                   # what would run
devman show                        # every workflow this project projects
devman doctor --prune              # reconcile stale registry entries
```

## The contract

**Four global names, and the list is closed** (`CONCEPT.md` §7.1). The machine
states all four once, so no workflow repeats them:

| Name | Whose field | Where the machine states it |
|---|---|---|
| the queue names — `light` `normal` `heavy` `gpu` `exclusive` | Dagu's `queue:` | `config.yaml`, with each limit |
| `DEVMAN_PROJECT_DIR` | a variable name | the generated projection header |
| `DEVMAN_SELF_DIR` | a variable name | the same header, for a cross-repo workflow |
| the `.devman/.runs/` path shape | Dagu's `log_dir:` | the same header |

Everything else belongs to the repository: task names, workflow names, and every
line of every workflow file.

**`.devman/` belongs to the repository too.** devman reserves two names inside
it — `workflows/` and `.runs/` — and never reads, writes or inspects anything
else there. A whitelist that refused unknown entries was removed at stage 7,
because a directory the repository already owned is not the place to make an
exception (R-9).

## Reactivity

A repository reacts to a save by taking a group whose `triggers.toml` maps globs
to workflow names. Taking that group is the whole opt-in; not taking it is the
whole opt-out. One `watchexec` user service reads the registry and watches only
the repositories that declare triggers.

`groups/format/README.md` is the worked example: `"**/*.py" = "format"`, one
workflow, and a content-hash precondition that stops the workflow from chasing
its own writes. The watcher also ignores `.devman/.runs/`, because without that
ignore one save produced 107 dispatches and 60 runs (`STAGE_3_LOG.md`, S8).

## Schedules

`maintain` carries `schedule: "5 0 * * *"` and `plane-report` carries
`schedule: "20 0 * * *"`. Both are Dagu's own key, and both work only because the
projection is generated per project: each copy states its own `working_dir`,
`log_dir` and directory variable, so the daemon needs nothing from a trigger.

> **A scheduled run does not pass through its queue.** 58 DAGs sharing one
> `schedule:` all started at once with queue depth 0, and two DAGs on `exclusive`
> — limit 1 — both started in the same second. **Nothing throttles the scheduled
> set**, so anything scheduled must be cheap by construction (`STAGE_7_LOG.md`,
> S-1).

## Layout

```
nix/            the machine interface — NixOS module, the Dagu package, the CLI package, tests
modules/        the repo interface — devenv.nix, the name is required
groups/         workflow content: base, format, release (python and python-format are tombstones)
src/devman/     the CLI — run, show, doctor, watch
.devman/        this repository's own workflows, including the machine-wide plane-report
```

Machine-side state lives in `~/.local/share/devman/`: `projects/<project>/` holds
each repository's identity and its projected workflows, and `dags/` holds Dagu's
flat view of them. Everything there is reconstructable by re-entering every
registered repository's shell.

Run output stays with the checkout that produced it, in `<repo>/.devman/` —
`workflows/` tracked, `.runs/` ignored.

## The design is written down

| Path | What |
|---|---|
| [`CONCEPT.md`](.scratch/projects/006-automation-plane/CONCEPT.md) | the charter — the model, the contract, the criteria, the sharp edges |
| [`STAGE_1_LOG.md`](.scratch/projects/006-automation-plane/STAGE_1_LOG.md) | what building the two modules measured |
| [`STAGE_2_LOG.md`](.scratch/projects/006-automation-plane/STAGE_2_LOG.md) | what turning the plane on measured |
| [`STAGE_3_LOG.md`](.scratch/projects/006-automation-plane/STAGE_3_LOG.md) | what making the plane react measured |
| [`STAGE_4_LOG.md`](.scratch/projects/006-automation-plane/STAGE_4_LOG.md) | what giving the plane work to do measured |
| [`STAGE_5_LOG.md`](.scratch/projects/006-automation-plane/STAGE_5_LOG.md) | the refusals, and what each one cost |
| [`STAGE_6_LOG.md`](.scratch/projects/006-automation-plane/STAGE_6_LOG.md) | the generated projection |
| [`PROPOSAL.md`](.scratch/projects/007-standard-workflows/PROPOSAL.md) | the standard workflow set — the one-step rule, the group rule, and eight things that must never become a workflow |
| [`STAGE_7_LOG.md`](.scratch/projects/007-standard-workflows/STAGE_7_LOG.md) | the rollout to 53 repositories, measured batch by batch |
| [`FINDINGS.md`](.scratch/projects/006-automation-plane/FINDINGS.md) | the five investigations, all closed |

Every non-obvious line in this repository has a measurement behind it. The stage
logs hold those measurements — the answer, the versions, the exact command, the
evidence, and what the charter had to change. Read the log before you change a
line that looks redundant.

`.scratch/projects/001`–`005` are earlier attempts to define devman. They are
superseded and carry no authority.

## For people and for agents

| Reader | File |
|---|---|
| a developer adopting or using the plane | [`USER.md`](USER.md) |
| an agent working in this repository | [`AGENTS.md`](AGENTS.md), then [`AGENTS_GUIDE.md`](AGENTS_GUIDE.md) |
| an agent writing or changing a workflow | `.agents/skills/devman-workflow/SKILL.md` |
| an agent adopting a repository into the plane | `.agents/skills/devman-adopt/SKILL.md` |

## Development

```bash
devenv shell
```
