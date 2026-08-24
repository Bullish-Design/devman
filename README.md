# devman

The development automation plane.

> **devman installs one Dagu control plane per machine, and gives every
> devenv-managed repository a shared automation contract through one Nix flake.**

Dagu orchestrates. devenv executes. devman is the contract between them, and
executes nothing itself.

## The model

```
a save             → watchexec ─┐
a commit / a push  → git hook   ─┼→ devman run → dagu enqueue → Dagu → devenv tasks run
a developer        → a prompt   ─┤
a cron expression  → the daemon ─┘
```

| Layer | Owns | Never |
|---|---|---|
| **Dagu** | the run: order, queues, retries, history, the web UI | knows what a project is |
| **devenv** | the implementation of one task in one repository | knows what a workflow is |
| **devman** | registration, projection, resolution, refusal | executes anything itself |

**devman never parses a workflow to understand it.** A workflow is portable Dagu
YAML with no devman-specific key in it. devman reads three bounded things: that
the file loads, the `params:` a trigger must fill, and whether a file holds the
directory variable it passes to its children.

## The two interfaces

| Interface | File | Serves |
|---|---|---|
| the machine | `nixosModules.default` | one Dagu user service, the queues, the state paths, the ports, the watcher, the `devman` CLI |
| the repository | `modules/devenv.nix` | three Nix options, registration, and §7.3's resolution |

They share **text only** — the queue names, two variable names, and a path
shape. Each takes `pkgs` from its own side, so one flake serves two nixpkgs
without either constraining the other. `nix/dagu.nix` is the one measured
exception: nixpkgs packages no Dagu at any version, so both call the same file.

**The machine never learns a project fact.** No project names, no per-project
options, no absolute paths. That constraint is what everything else bends around.

## How a repository adopts it

Two files, then the task names the groups you take ask for.

```yaml
# devenv.yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"

imports:
  - devman/modules
```

```nix
# devenv.nix
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
| `groups` | which groups this repository inherits, in precedence order. `[ ]` is legal — the repository then has only its own `.devman/workflows/` |

Pin with `git+https` and an explicit `rev`. That form records `rev` and `narHash`
in `devenv.lock`; `git+file` records neither and follows the branch head
silently.

Then enter the shell once. **That is the only registration path there is** —
there is no `devman register` and there never will be, so nothing can drift from
it.

Each group states in its own `README.md` which task names it calls. See
[`groups/README.md`](groups/README.md).

## Commands

| Command | Does |
|---|---|
| `devman run <workflow>` | trigger a workflow in the current project |
| `devman show <workflow>` | print the resolved file, to start an override |
| `devman doctor` | diagnose the plane, and report shadowed files and their drift |

`devman watch` is the fourth subcommand and it is not a fourth command: it is the
watcher service's entry point, run by systemd rather than by a person.

There is no `list`, no `status`, no `register` and no `unregister`. Registration
is automatic and has no manual path; the rest is what `doctor` reports.

## The contract

**Four global names, and the list is closed** (`CONCEPT.md` §7.1). The machine
states all four once, so no workflow repeats them:

| Name | Whose field | Where the machine states it |
|---|---|---|
| the queue names — `light` `normal` `heavy` `gpu` `exclusive` | Dagu's `queue:` | `config.yaml`, with each limit |
| `DEVMAN_PROJECT_DIR` | the project a run targets | the generated projection header |
| `DEVMAN_SELF_DIR` | a cross-repo workflow's own directory | the same header |
| the `.devman/.runs/` path shape | Dagu's `log_dir:` | the same header |

Everything else belongs to the repository: task names, workflow names, and every
line of every workflow file. **Adding a fifth name is a charter change, not an
implementation detail.**

**`.devman/` belongs to the repository too.** devman reserves two names inside
it — `workflows/` and `.runs/` — and never reads, writes or inspects anything
else there.

## Resolution and projection

A workflow name resolves through the groups a repository lists, in order, and
then through the repository's own `.devman/workflows/`:

```
groups[0] → groups[1] → … → <repo>/.devman/workflows/
```

**Shadowing is whole-file, never a field merge.** `devman show <workflow>` prints
the winner on stdout and where it came from on stderr, so
`devman show x > .devman/workflows/x.yaml` round-trips exactly.

Resolution happens at evaluation time. The **projection** then writes one
generated file per workflow into the registry: the source body, unchanged, under
a header stating that project's `working_dir`, `log_dir` and directory variable.

The header adds; it never overwrites. That is what lets Dagu's own scheduler fire
a workflow — the daemon has one environment for the whole machine and nothing to
fill in.

**An edit reaches Dagu at the next shell entry.** The shell-entry guard compares
each override's body against the tail of its projection, so it notices an edit in
place and not only an add or a remove.

## Reactivity

A repository reacts to a save by taking a group whose `triggers.toml` maps globs
to workflow names. **Taking that group is the whole opt-in; not taking it is the
whole opt-out.**

One `watchexec` user service reads the registry and watches only the
repositories that declare triggers. It ignores `.devman/.runs/`, because without
that ignore one save produced 107 dispatches and 60 runs.

A workflow that rewrites files its own trigger watches needs a **step-level**
content-hash precondition. A hash rather than a timer: your own edit one second
after the write still fires.

## Schedules

Use Dagu's own `schedule:` key, in the workflow file. It works because the
projection is generated per project.

> **A scheduled run does not pass through its queue.** 58 DAGs sharing one
> `schedule:` all started at once with queue depth 0, and two DAGs on
> `exclusive` — limit 1 — both started in the same second. **Nothing throttles
> the scheduled set**, so anything scheduled must be cheap by construction.

## Refusals

The plane's habit is to be loud rather than to guess, because **a successful run
that did the wrong thing is the failure it exists to prevent.** `devman run`
refuses, naming the file and the field, when:

- the resolved file does not load
- two projects render one flat `<project>-<workflow>` DAG name
- a cross-repo parent holds `DEVMAN_PROJECT_DIR`, or declares no `DEVMAN_SELF_DIR`
- the directory variable would be empty, or is not a directory
- a declared parameter has no value
- the caller stands in a checkout **inside** a registered checkout

## Layout

```
nix/            the machine interface — NixOS module, the Dagu package, the CLI package, tests
modules/        the repo interface — devenv.nix, the name is required
groups/         workflow content, one directory per group — see groups/README.md
src/devman/     the CLI — run, show, doctor, watch
.devman/        this repository's own workflows — see .devman/workflows/README.md
```

Machine-side state lives in `~/.local/share/devman/`: `projects/<project>/` holds
each repository's identity and its projected workflows, and `dags/` holds Dagu's
flat view of them.

**The registry is derived and the repository is canonical.** Everything there is
reconstructable by re-entering every registered repository's shell, which is what
makes `devman doctor --prune` safe.

Run output stays with the checkout that produced it, in `<repo>/.devman/` —
`workflows/` tracked, `.runs/` ignored.

## What ships

devman is the mechanism. The content documents itself:

| Where | What |
|---|---|
| [`groups/README.md`](groups/README.md) | the group mechanism, and an index of the groups this repository ships |
| [`.devman/workflows/README.md`](.devman/workflows/README.md) | devman's own workflows, including the machine-wide plane report |

## Status

**Stages 1 to 7 are shipped.**

| Stage | What it delivered |
|---|---|
| 1 | the flake: the two module interfaces, the first groups, hash-guarded registration in `enterShell` |
| 2 | the plane turned on: automatic registration, the registry schema, queues, the `.devman/` run-state layout, whole-file shadowing |
| 3 | reactivity: the `devman` CLI, one `watchexec` user service reading the registry, and log retention |
| 4 | work worth doing: reports, housekeeping, a policy gate, and this repository's own agent and benchmark workflows |
| 5 | the refusals: a checkout inside a checkout, a flat DAG name two projects claim, a timer that silently never schedules a new project |
| 6 | the projection became a **generated** file per project, so Dagu's own scheduler can fire a workflow |
| 7 | the standard set: fewer workflows in fewer groups, the one-step rule, one nightly plane report instead of one per repository, and a rollout past 50 repositories |

**No stage added machinery.** The contract is still four global names, the CLI is
still three commands, the repo interface is still three keys, and the queue list
is still five. Every deliverable is a file.

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
| [`STAGE_7_LOG.md`](.scratch/projects/007-standard-workflows/STAGE_7_LOG.md) | the rollout, measured batch by batch |
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
