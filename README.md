# devman

The development automation plane.

> **devman installs one Dagu control plane per machine, and gives every
> devenv-managed repository a shared automation contract through one Nix flake.**

Dagu orchestrates. devenv executes. devman is the contract between them, and
executes nothing itself.

## Status

**Stages 1, 2 and 3 are shipped**, and the plane runs on the development
machine. Stage 4 — higher-level automation — is not started.

| Stage | What it delivered |
|---|---|
| 1 | the flake: `nixosModules.default` (one Dagu user service, queues, ports, state paths), `modules/devenv.nix` (the repo interface), the `base` and `python` groups, hash-guarded registration in `enterShell` |
| 2 | the plane turned on: automatic registration, the registry schema, queues and their limits, the `.devman/` run-state layout, whole-file shadowing, and a cross-repo workflow — six projects adopted |
| 3 | reactivity: the `devman` CLI, one `watchexec` user service reading the registry, the `python-format` trigger group, and log retention |

Six projects and 19 DAGs are registered on that machine (`STAGE_3_LOG.md`, S12).

## How a repository adopts it

Two files. First, the input and the import in `devenv.yaml`:

```yaml
inputs:
  devman:
    url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"

imports:
  - devman/modules
```

Pin with `git+https` and an explicit `rev`. That form records `rev` and
`narHash` in `devenv.lock`; `git+file` records neither and follows the branch
head silently.

Then three lines in `devenv.nix`, plus the task names the groups call:

```nix
devman = {
  enable = true;
  project = "observantic";
  groups = [ "python" ];
};
```

The example is `observantic`'s, unedited. `project` is stated, never inferred
from the directory name, so renaming the checkout keeps the run history.

A workflow is a Dagu YAML file with no devman-specific key in it. Groups layer
by directory; a repository overrides one by shadowing the file name. Stage 2
measured **one override in eighteen workflows** across five adopted repositories
(`STAGE_2_LOG.md`, S14).

## The contract

**Four global names, and the list is closed** (`CONCEPT.md` §7.1). The machine
states all four once, so no workflow repeats them:

| Name | Whose field | Where the machine states it |
|---|---|---|
| the queue names — `light` `normal` `heavy` `gpu` `exclusive` | Dagu's `queue:` | `config.yaml`, with each limit |
| `DEVMAN_PROJECT_DIR` | a variable name | `base.yaml`; the trigger supplies the value |
| `DEVMAN_SELF_DIR` | a variable name | `base.yaml`'s exit handler, as a fallback |
| the `.devman/.runs/` path shape | Dagu's `log_dir:` | `base.yaml` |

Everything else belongs to the repository: task names, workflow names, and every
line of every workflow file.

## Commands

| Command | Does |
|---|---|
| `devman run <workflow>` | trigger a workflow in the current project |
| `devman show <workflow>` | print the resolved file, to start an override |
| `devman doctor` | diagnose the plane, and report shadowed files and their drift |

`devman watch` is the fourth subcommand and it is not a fourth command: it is
the watcher service's entry point, run by systemd rather than by a person.

## Reactivity

A repository reacts to a save by taking a group whose `triggers.toml` maps globs
to workflow names. Taking that group is the whole opt-in; not taking it is the
whole opt-out. One `watchexec` user service reads the registry and watches only
the repositories that declare triggers.

`groups/python-format/README.md` is the worked example: `"**/*.py" = "format"`,
one workflow, and a content-hash precondition that stops the workflow from
chasing its own writes. The watcher also ignores `.devman/.runs/`, because
without that ignore one save produced 107 dispatches and 60 runs
(`STAGE_3_LOG.md`, S8).

## Layout

```
nix/            the machine interface — NixOS module, the Dagu package, the CLI package, tests
modules/        the repo interface — devenv.nix, the name is required
groups/         workflow content: base, python, python-format
src/devman/     the CLI — run, show, doctor, watch
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
| [`FINDINGS.md`](.scratch/projects/006-automation-plane/FINDINGS.md) | the five investigations, all closed |

Every non-obvious line in this repository has a measurement behind it. The stage
logs hold those measurements — the answer, the versions, the exact command, the
evidence, and what the charter had to change. Read the log before you change a
line that looks redundant.

`.scratch/projects/001`–`005` are earlier attempts to define devman. They are
superseded and carry no authority.

## Development

```bash
devenv shell
```
