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

## S-7 — the daemon's scheduler shell (stage 7, P1-3)

Date: 2026-08-31. Branch: `fix/009-stage-7-daemon-shell`.

### The premise is confirmed, and the comment was false for a whole stage

Two workflows carry a `schedule:` — `groups/base/workflows/maintain.yaml:95`
and `.devman/workflows/plane-report.yaml:68`. So this claim, at
`nix/nixos-module.nix`, was false from the moment stage 7 shipped them:

> Setting `SHELL` on this unit was tried and does nothing for any run the plane
> makes: the daemon enqueues only under a `schedule:`, which §8 does not use.

Recorded here as a superseded state, per rule 1. It is corrected in both places
that carried it.

### Measured on the live machine, before the fix

```
$ devenv shell -- bash -c 'PYTHONPATH=src python -m devman doctor'
!!  daemon shell    pid 1302: SHELL=/run/current-system/sw/bin/zsh
```

The running daemon holds the user manager's zsh. Every scheduled run on this
machine has taken zsh rather than the `default_shell` bash since stage 7 — S9's
failure, with nobody at the prompt to see it.

### The edit

**The report's first fix direction is not expressible.** It says "remove
`SHELL` from the Dagu service environment". The variable is *inherited* from the
systemd user manager, so `environment.SHELL = null` removes nothing — there is
nothing set on the unit for a null to remove. The form that works is:

```nix
serviceConfig.UnsetEnvironment = "SHELL";
```

Two enqueue owners, two clearings: `devman run` for the CLI, the watcher and the
hook (`run.py`); the unit for the daemon's own scheduled enqueues.
`default_shell` governs both.

**Clearing per owner is a whack-a-mole invariant**, which is why the durable
form is a check. `doctor`'s new `daemon shell` reads the running Dagu's
`/proc/<pid>/environ` and reports `SHELL` if it is there. It reads what is
actually true rather than counting the places that ought to have cleared it.

### The VM proof, and two things it measured

`nix/tests/dagu-service.nix` gains two subtests:

1. the service process holds no `SHELL` — read from `/proc/<pid>/environ`
2. a fixture workflow with `schedule: "* * * * *"` and one bash-specific
   construct, `test -n "$EPOCHREALTIME"` — the exact construct that failed in S9
   — runs, and both the step and the DAG succeed

**Measurement 1 — a scheduled run needs the projection's `env:` block, not only
its `working_dir`.** The first fixture stated `working_dir` and `log_dir` and
failed: every step succeeded and the DAG reported `failed`, because base.yaml's
exit handler appends to `$DEVMAN_PROJECT_DIR/.devman/.runs/metadata.jsonl` as a
**shell** variable, and the daemon's environment holds no such name. It wrote to
`/.devman/.runs/metadata.jsonl` and exited 1. `STAGE_6_LOG.md` S2 says the
projection states "its own `working_dir`, `log_dir` and directory variable" —
this is what the third one is for, and the fixture now carries it.

**Measurement 2 — a per-minute schedule is not a neutral fixture.** Left in
place it enqueues into `light` while the rest of the script runs, and `doctor`
reads one queued item with nothing running as a wedged queue, correctly.
Removing the DAG file does not empty the queue: an item already dispatched
outlives its DAG, and `dagu dequeue light` did not clear it either. The
subtests therefore run **last**. Ordering is the only clean answer, and the
comment in the file says so.

### Verification

```
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:unit     # 236 passed
devenv tasks run -v base:test     # nix flake check — both new subtests green
devman doctor                     # exit 0 (the installed CLI; the new check
                                  # ships with the next machine rebuild)
```

The `daemon shell` check will report `!!` on this machine until the rebuild
lands the unit change and restarts the service. That is the check working.

### Charter

No amendment. §8's rule is unchanged. A comment that described the plane's
behaviour stopped being true when stage 7 added two schedules, and the fix is to
the comment and to the unit, not to the design.
