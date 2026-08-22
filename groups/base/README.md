# base — the group every repository takes by default

`devman.groups = [ "base" ]` is the default, because `devenv.nix` is the
highest-coverage marker in the surveyed repositories — 57 of 71 (D4). This group
therefore holds the leverage, and it must stay small.

## The task names this group calls

A group's workflows call task names, and **task names are group-local
convention** (`CONCEPT.md` §7.1). Taking a group is an agreement to define that
group's names:

| Task | What the repository puts in it |
|---|---|
| `lint` | the fast check that needs no build |
| `test` | the test suite |

Two names, and the list is closed. `full-test` reaches further by calling
`devenv test`, which every devenv repository already has, so the exhaustive
workflow costs a repository no third task.

```nix
tasks."lint".exec = "ruff check .";
tasks."test".exec = "pytest";
```

A repository that decomposes differently takes a different group, or shadows the
file (§7.3). The plane does not police what a name means.

## The workflows

| File | Queue | Steps |
|---|---|---|
| `check.yaml` | `light` | `lint` |
| `validate.yaml` | `normal` | `lint`, `test` |
| `full-test.yaml` | `heavy` | `lint`, `test`, `devenv test` |

## What is deliberately absent from every file

`name`, `working_dir`, and `log_dir`.

- A top-level `name:` makes `dagu validate` fail — "entrypoint document must not
  define name". A DAG's identity is its file name (A5).
- `working_dir` and `log_dir` are identical in every workflow, so the machine
  writes them once into Dagu's `base.yaml` and every DAG inherits them (E4).

`queue` stays, because it is the one thing that genuinely varies from workflow to
workflow (§7.2).

## Why the multi-step files say `type: chain`

`chain` runs the steps in order. `graph`, Dagu's default, runs steps with no
`depends` at the same time, and two `devenv tasks run` invocations in one
checkout then contend for one devenv state directory. Order is the workflow's
own business, so the key sits in the file rather than in the machine's
`base.yaml`.
