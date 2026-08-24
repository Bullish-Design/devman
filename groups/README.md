# groups/ — workflow content

A **group** is a directory of workflow files that a repository inherits by name.
It is the only thing devman ships that is content rather than mechanism.

```
groups/<group>/
├── README.md            what taking this group costs a repository
├── triggers.toml        optional: <glob> = <workflow>
└── workflows/*.yaml     one Dagu file per workflow
```

A repository takes a group by naming it:

```nix
devman.groups = [ "base" "format" ];
```

**Each group documents itself.** This file is the index and the rules that hold
across all of them. What a particular group ships, and what it asks a repository
to define, is in that group's own `README.md`.

## The groups in this repository

| Group | README | State |
|---|---|---|
| `base` | [`base/README.md`](base/README.md) | shipped — the default |
| `format` | [`format/README.md`](format/README.md) | shipped — opt-in |
| `release` | [`release/README.md`](release/README.md) | shipped — opt-in |
| `python` | [`python/README.md`](python/README.md) | **tombstone** |
| `python-format` | [`python-format/README.md`](python-format/README.md) | **tombstone** |

## How a group reaches a repository

**Resolution is whole-file, in the order the repository lists its groups**, and
the repository's own `.devman/workflows/` is the last layer (§7.3):

```
groups[0] → groups[1] → … → <repo>/.devman/workflows/
```

A later layer shadowing an earlier one replaces the **whole file**. There is no
field merge, because the result would be hard to predict from either file alone.

Resolution happens at **evaluation time**, in `modules/devenv.nix`. The outcome —
which file won, and what it displaced — is recorded in the registry entry, which
is what `devman show` prints and what `devman doctor` diffs against.

**To be rid of a workflow, do not take its group.** There is no per-workflow Nix
option and there will not be one (§7.4): an inherited workflow that nothing
triggers costs nothing.

## What a group may contain

| May | May not |
|---|---|
| Dagu YAML with no devman-specific key | a project name |
| a `queue:` name | an absolute path |
| a `schedule:` expression | a `handler_on:` block |
| a `triggers.toml` mapping globs to workflow names | a top-level `name:` |
| a task name in its own namespace | `working_dir:` or `log_dir:` — the projection writes both |

**A group names a task and never a tool.** `base` calls `base:check`, never
`ruff`. The task namespace is the group's own name, which is what "group-local
convention" means made literal — and devenv requires `namespace:name` anyway.

**Taking a group is an agreement to define that group's task names.** A group's
README states which. A repository that cannot honour a name does not define it,
and the workflow then fails loudly with devenv's own `no such task`.

## When a group should exist

Two rules, and both have to hold.

> **§16 — a group begins when a *second* repository wants the same file.**

One repository wanting something is that repository's own
`.devman/workflows/` file. Promotion costs nothing later, because the workflow
names a task and the task names the tool.

> **§3 — a group exists when taking it costs the repository something it cannot
> decline any other way**: a task name it must define, or a write to its own
> files it did not ask for.

**What fires a workflow is not the test; what it touches is.** A workflow that
fires itself on a schedule and writes only under `.devman/.runs/` — which the
plane created, and which git and the watcher both ignore — may ride in a general
group. A workflow that rewrites the developer's source may not.

**A language is not a reason for a group.** A language differs in what a task
*is*, and `devenv.nix` already holds that. Once a workflow is one step calling
one task, a language group's whole content is a namespace prefix — the file is
identical in every group, so §16's promotion rule cannot be satisfied by it.

## Deleting a group

**A deleted group becomes a tombstone, not a deletion.**

`modules/devenv.nix` throws on an unknown group, and the throw is an
**evaluation** failure: a repository that re-pins to a rev where its group is
gone could not enter its shell at all. That is a flag day, not a migration.

A directory that ships no `workflows/` evaluates and projects nothing, so a stale
pin keeps working and the repository renames its group when it is next edited.

| A tombstone must | A tombstone must not |
|---|---|
| hold at least one file — git cannot carry an empty directory, and a tombstone that vanishes on `git+https` is not a tombstone | hold a `triggers.toml` |

A `triggers.toml` in a tombstone keeps firing a workflow the repository no longer
projects: the registry carries the mapping, `devman doctor` prints it without
objecting, and every matching save forks a `devman run` that refuses with exit 1.

Remove the directory one full rollout after every repository has re-pinned.

## Adding or changing a group workflow

Read `.agents/skills/devman-workflow/SKILL.md`. The short form:

- One workflow, one step, one `devenv tasks run -v <group>:<name>`. Order belongs
  to the repository's devenv task graph, never to a Dagu file.
- `-v` is load-bearing. Without it devenv captures the task's stdout and prints
  none of it, on the success path and the failure path alike.
- No bashisms. A step does not run under the shell you expect.
- **Every taker of the group pays for the change.** State what the group asks of
  a repository in that group's `README.md`, in the same commit.
- `nix build .#checks.<system>.groups-validate` runs `dagu validate` over every
  file here. It must pass.

## What must never be shipped in a group

`PROPOSAL.md` §12, in full. The short form: anything an editor already does
synchronously; anything irreversible outside this machine; anything that writes
tracked source with nobody present; anything whose success is indistinguishable
from doing nothing; anything needing a fact the repository did not state; a
second implementation of a task the repository already has; anything whose output
nobody reads; and anything expensive on a schedule — **a scheduled run bypasses
its queue**.
