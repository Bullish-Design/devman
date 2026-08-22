# python — the ecosystem group that proves shadowing

`pyproject.toml` appears in 52 of 71 surveyed repositories, second only to
`devenv.nix` (D4). This group exists for the decomposition Python has and `base`
does not: a type checker that is neither a linter nor a test.

## The task names this group calls

| Task | What the repository puts in it |
|---|---|
| `python:lint` | `ruff check .` |
| `python:typecheck` | `basedpyright` |
| `python:test` | `pytest` |

devenv requires the namespace — an un-namespaced `lint` is an evaluation error —
and the namespace is the group's own name, so a group's names cannot collide
with another group's (see `../base/README.md`).

**A Python repository usually takes `[ "python" ]` alone.** Taking
`[ "base" "python" ]` means defining `base:lint` and `base:test` as well,
because python shadows `check` and `validate` while base's `full-test` survives
and still calls its own names. Take both only when you want that `full-test`.

The second set costs two lines rather than two bodies — a devenv task with only
`after` and no `exec` runs its dependency and fails when that dependency fails
(`STAGE_2_LOG.md`, S5):

```nix
tasks."base:lint".after = [ "python:lint" ];
tasks."base:test".after = [ "python:test" ];
```

## Shadowing

```nix
devman.groups = [ "base" "python" ];
```

resolves to:

| Workflow | Wins from |
|---|---|
| `check` | **python** — shadows `base/check` |
| `validate` | **python** — shadows `base/validate` |
| `full-test` | base — python defines none |

Shadowing is whole-file, never a field merge (§7.3). The repository's own
`.devman/workflows/` is the last layer and shadows both.
