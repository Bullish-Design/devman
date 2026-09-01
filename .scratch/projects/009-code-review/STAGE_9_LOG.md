# Stage log — project 009, the review refactor

One entry per stage of [`REVIEW_REFACTOR_GUIDE.md`](REVIEW_REFACTOR_GUIDE.md).
Each entry records what was measured, the exact command, the versions, the
result, and what the charter had to change. This is rule 1, paying itself
forward.

---

## S-1 — trigger refusals (stage 1, P1-2 + P2-6)

Date: 2026-08-31. Branch: `fix/009-stage-1-trigger-refusals`.

### What was wrong

`run.resolve()` derived the parameter map safely and then applied the caller's
overrides on top of it, with a blanket update at `run.py:149`. No parameter was
constrained. Two consequences, filed by the report as two findings:

- **P1-2** — `devman run check DEVMAN_PROJECT_DIR=/elsewhere` retargeted the run
  itself. The `is_dir()` check below it passed, because `/elsewhere` is a
  directory.
- **P2-6** — an ordinary parameter took any value. `stack-validate.yaml` declares
  `OBSERVANTIC_DIR: observantic` and hands it to a child as
  `DEVMAN_PROJECT_DIR` (lines 85-96), so `OBSERVANTIC_DIR=/anywhere` retargeted a
  cross-repository child run. Nothing in the projection blunts that: the parent's
  `working_dir` is `${DEVMAN_SELF_DIR}`, not a literal.

They are one defect, so one rule closes both.

### The rule

> A reserved name accepts no override. A parameter whose default names a
> registered project accepts only another registered project's name. Every other
> override must name a declared parameter.

### The measurement — blast radius before landing

Every override example this repository ships, and every one in the skills:

```bash
grep -rn "devman run" --include='*.yaml' --include='*.toml' --include='*.nix' \
  --include='*.md' --include='*.sh' --include='*.py' . | grep '='
```

Result: **no shipped example overrides a reserved name, and none names an
undeclared parameter.** The examples are `KEEP_DAYS=30`, `AGENT_REF=HEAD~3`,
`AGENT_PROMPT=…`, `RUNS=20`, `TARGET=pyjutsu` — all declared, none a reserved
name, none a path given to a project-name default. The refusals break no
documented call.

The only reserved-name use found is `DEVMAN_PROJECT_DIR=/tmp devman run
stack-validate` in `STAGE_3_LOG.md:165`. That is an environment assignment on the
command, not an override argument, and `child_env()` has cleared it since S13.

### The edit

- `src/devman/run.py` — the blanket update is gone. Each override is consumed
  inside the declared loop, so a later refactor has nothing to reintroduce.
  `test_the_blanket_update_is_gone` asserts that shape directly.
- `assert_target()` — the last line before the irreversible boundary, called in
  `main()` after `resolve()` and before both `command()` and the `--print`
  branch, so neither path can skip it. Its invariant is not "the value is a
  directory" but "the value is the directory of the project whose workflow was
  resolved". Earlier validation does not survive a later mutation, which is what
  P1-2 was.
- The `is_dir()` and empty-value checks stay, unchanged. They are the second
  layer, and they now fire only on a registry entry whose repository has gone —
  the state `doctor --prune` reconciles.
- `USER.md` — §3 gains "What `NAME=VALUE` may set", and the refusal table gains
  the three new messages.

### Verification

```
devenv tasks run -v base:unit     # 244 passed
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:test     # nix flake check
devman doctor                     # exit 0
```

Nine new cases in `tests/unit/test_run.py`, one per rule branch. Two existing
tests changed: the two that drove the second layer through a reserved override
can no longer reach it, so
`test_a_directory_variable_that_is_not_a_directory_is_refused` now drives it
through `make_dir=False` instead — a state that still occurs.

### Charter

No amendment. The rule is §7.2 and §11 enforced, not changed.

---

## S-2 — watcher ownership (stage 2, P1-4)

Date: 2026-08-31. Branch: `fix/009-stage-2-watcher-ownership`.

### What was wrong

Two places answered "which project owns this path", and they disagreed.

`registry.project_for()` carried the rule — the deepest registered project wins
— with the measurement behind it (`STAGE_5_LOG.md`, S3). `watch.match()`
implemented containment for itself, as `path.relative_to(entry.path)` over every
entry, and accepted **every** registered root containing the path.

Reproduced in the review: `outer/inner/changed.py`, with `outer` and
`outer/inner` both registered, returned `['inner', 'outer']`. One save, two
runs. The outer repository's formatter then rewrote source across the nested
repository boundary, and both runs reported success — the failure this design
exists to prevent.

### The edit — extract, do not copy

The report says the watcher "should share it instead of implementing containment
independently". Taken literally: copying the rule into `watch.py` would recreate
the same duplication in a new place.

`registry.deepest(roots, here)` is the rule, and it now has exactly two callers.
`project_for()` calls it and keeps its own nested-checkout refusal, which is a
separate rule and stays where it is. `match()` resolves ownership **once per
path**, then matches only that project's globs. The per-project/per-workflow
coalescing is unchanged; it now runs after ownership rather than instead of it.

One behaviour change inside the rule: depth is compared on `len(resolved.parts)`
rather than `len(str(root))`. Path length in characters is not depth. The old
form happened to agree on every path this machine holds.

### Verification

```
devenv tasks run -v base:unit     # 243 passed
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:test     # nix flake check, VM test included
devman doctor                     # exit 0
```

Six new unit cases plus one shape assertion.
`test_deepest_and_project_for_agree` asserts the two callers agree on a shared
table of paths — that is what keeps the extraction honest, since they drifted for
a whole stage before.

New VM subtest, "a save inside a nested checkout fires only the inner project":
registers a second project inside the first, saves one file in the inner one,
waits for the fire, then sleeps ten seconds and reads the whole `fired.jsonl`.
The assertion is that the set of projects that fired is exactly `{"nested"}` —
the outer one firing late would fail it.

### Charter

No amendment. §8's rule is unchanged; one of its two implementations was wrong.
