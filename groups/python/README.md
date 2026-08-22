# python — the ecosystem group that proves shadowing

`pyproject.toml` appears in 52 of 71 surveyed repositories, second only to
`devenv.nix` (D4). This group exists for the decomposition Python has and `base`
does not: a type checker that is neither a linter nor a test.

## The task names this group calls

| Task | What the repository puts in it |
|---|---|
| `lint` | `ruff check .` |
| `typecheck` | `basedpyright` |
| `test` | `pytest` |

`lint` and `test` are the same two names `base` asks for, so a repository taking
both groups defines three tasks, not five.

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
