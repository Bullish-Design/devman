# Wave 3 item 13 — generation 3 evidence

Date: 2026-09-15 UTC

## Gate

An isolated disposable registry proved the `.dag.index` question. The test
created generations 1 and 2, ran `dagu ls` against generation 1, copied the
stale index into generation 2, and switched the active pointer to generation
2. A new `dagu ls` reported `Rebuilding DAG definition index` and resolved the
DAG path under `generations/2`. A stale index therefore does not block a new
Dagu process after an active-generation switch.

## Build and test

- `devenv tasks run -v base:check` passed.
- `devenv tasks run -v base:unit` passed: 594 tests.
- `devenv tasks run -v base:test` passed, including the NixOS VM service test.
- The VM test covers active-pointer reload, timeout and blocked markers,
  failed restart markers, Dagu index discovery, watcher convergence, and the
  nested-checkout boundary.

## Plan and activation

Vendomat planned and then updated `devman` with 48 explicit project roots,
policy root `/home/andrew/Documents/Projects/devman`, overlay root
`$HOME/.config/devman`, and state directory
`$HOME/.local/state/vendomat/devman`. The update activated generation 3.

The active registry reported:

```
active=generations/3
projects=48
dags=152
generation=3
reload_pending=no
reload_blocked=no
```

`dagu ls` exited 0 and rebuilt the index at
`$HOME/.local/state/vendomat/devman/active/dags/.dag.index`. The index contains
generation 3 paths and no generation 1 or 2 paths.

## Doctor

`devman doctor` passed the plane, registry, validation, generation, links,
reload, and watcher checks. It exited 1 with two known findings: one workflow
has no declared output ownership and the local Vendomat source has uncommitted
changes and is consumed unpinned by one project. Both findings predate this
activation. The Vendomat worktree was not modified.
