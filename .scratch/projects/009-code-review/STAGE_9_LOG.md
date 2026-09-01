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

## S-6 — the machine module's assertions (stage 6, P1-6 and P3-1)

Date: 2026-08-31. Branch: `fix/009-stage-6-nix-assertions`.

### What was wrong

`nix/nixos-module.nix` held no `assertions` attribute at all. Two options stated
an invariant their type did not enforce.

**P1-6.** `configFile` always writes `auth.mode = "none"`, and the comment above
it said "Loopback only". That described the default. `host` was
`types.str`, so `host = "0.0.0.0"` exposed the web UI, the API and the
coordinator to the network with no gate, and nothing said so.

**P3-1.** `defaultQueue` was any string while `queues` is the declared set. Dagu
accepts an undeclared queue name silently and gives it concurrency 1 — the
measurement is in the `queues` description itself, citing S-9 — so a typo here
serialises the whole machine and says nothing.

### The edit

`isLoopback` accepts `127.0.0.0/8`, `::1`, `[::1]` and `localhost`, and refuses
everything else including `0.0.0.0` and `::`. Both assertions are evaluation
time, which is the cheapest place to refuse: the developer learns before the
service exists.

The boundary is stated in the **option descriptions** as well as in the
assertion messages. A developer reads the description first.

A network bind is deliberately not built. It is a second option — a Dagu auth
mode and a token file on §9.4's secrets path — and its own charter
conversation. Rule 9 notes §9.4 has never fired.

### The test, and one thing it had to learn

`nix flake check` does not evaluate a NixOS configuration that nobody builds, so
an assertion with no test is unproved. The new `module-assertions` check
evaluates the module ten ways and reads `config.assertions`, which is lazy — it
builds no system. Six of the cases are the ones the guide names; four more cover
`127.0.0.0/8`, `[::1]`, `localhost` and the default.

It asserts the **message**, not only the failure. An assertion that fires for
the wrong reason is not a test.

**Measured while writing it:** a bare `lib.nixosSystem` fails NixOS's own
root-filesystem and boot-loader assertions, so `config.assertions` is never
empty and the first case failed for a reason that had nothing to do with the
option under test. The check therefore filters to messages holding
`services.devman-dagu`. Without that filter every case would pass, including the
ones that must fail — the exact shape of a check that checks nothing (rule 5).

### Verification

```
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:test     # nix flake check — module-assertions built
devman doctor                     # exit 0
```

### Charter

No amendment. §4 already says loopback; the module now enforces what §4 says.
