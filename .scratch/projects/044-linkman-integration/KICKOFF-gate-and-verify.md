# Kickoff — make devman's gate green, then give linkman a verify hook

**Outcome, 2026-10-06:** completed. The two targeted checks and the full gate
pass. Both devman source commits and Linkman's verify hook reached origin.
`RESEARCH_REPORT.md` records the extra hermetic test input, the VM fixture,
and the measured results. This kickoff preserves the original baseline.

You are working in `/home/andrew/Documents/Projects/devman`, and later briefly in
`/home/andrew/Documents/Projects/linkman`.

Written 2026-10-06. Every line number below was measured against devman trunk
`f4a245f` on 2026-10-05. **Treat them as current but re-verify each one before
you rely on it** — the gate findings are reproducible, the line numbers may have
drifted.

## What this session does

Two small devman lanes that make `nix flake check` exit 0 for the first time in
the M14 milestone, then one lane in linkman that gives it the publish gate it
has never had.

**This session does not start the Linkman cutover.** Lanes 3-8 of
`PLAN-lanes.md` are out of scope. Do not touch `src/devman_link/`,
`modules/link.nix`, `nix/link-adapter.nix`, or any of the 60 central project
files.

## Required reading, in this order

1. `.scratch/projects/044-linkman-integration/PLAN-lanes.md` — §0 and lanes 1-2.
   That is this session's specification.
2. `.scratch/projects/044-linkman-integration/RESEARCH-integration-surface.md`
   §A — the measured evidence for both gate failures, with commands and output.
3. `.scratch/projects/044-linkman-integration/OPEN-QUESTIONS.md` O4 — the one
   design question lane 2 raises, and O5 for context you should not act on.
4. `AGENTS.md` — properties 4, 7 and 10 bear on lane 2's design.

Everything in those documents was verified by direct measurement. Do not
re-derive it; do confirm anything you are about to change.

## The state of the gate, measured 2026-10-05

`devenv.nix:125` sets `"base:test".exec = "nix flake check"`. `gitman.toml` sets
`[publish] verify = ["nix", "flake", "check"]` with `verify_timeout = 3600`. So
the gate is both the test task and the publish hook — **no lane in this
milestone can land until it is green.**

It is red for **two unrelated reasons**.

### Failure 1 — `checks.x86_64-linux.python-tests`

```
> tests/unit/test_cutover_gate.py:15: in <module>
>     from tools.cutover.gate import (
> E   ModuleNotFoundError: No module named 'tools'
> ERROR tests/unit/test_cutover_convert.py
> ERROR tests/unit/test_cutover_gate.py
> ERROR tests/unit/test_cutover_snapshot.py
> ========================= 1 skipped, 3 errors in 1.96s =========================
```

Cause: `flake.nix:158-167`'s fileset omits `./tools`.

```nix
158  source = nixpkgs.lib.fileset.toSource {
159    root = ./.;
160    fileset = nixpkgs.lib.fileset.unions [
161      ./src
162      ./tests
163      ./pyproject.toml
164      ./groups
165      ./nix/nixos-module.nix
166    ];
167  };
```

`flake.nix:179` calls bare `pytest` and relies on `pyproject.toml:97`
(`pythonpath = [".", "src", "tests"]`) to put the repo root on `sys.path`. That
works in the working tree, where `tools/cutover/` exists and is tracked. The
hermetic build materialises only those five paths, so `tools/` never arrives.

Red since commit `1be7863` "m14 l2: snapshot and restore tooling for the
cutover" (2026-10-01 13:06), which added `tools/cutover/`, added
`pythonpath = ["."]`, and did not touch `flake.nix`. `416b402` (l4) and
`6b909ac` (l6) repeated the pattern.

### Failure 2 — `checks.x86_64-linux.dagu-service`

**This one is a product defect, not a test artefact, and no pre-existing
document records it.**

```
> File ".../devman/doctor.py", line 1620, in check_link_drift
>     lane_only = central.check_c3_lane_only(views, central_root, trunk)
> File ".../devman/central.py", line 369, in check_c3_lane_only
>     tracked = tracked_paths(central, trunk)
> File ".../devman/central.py", line 212, in tracked_paths
>     return set(_git(central, "ls-tree", "-r", "--name-only", trunk).splitlines())
> File ".../devman/central.py", line 206, in _git
>     raise InfraError("git is not on PATH; cannot read trunk's tree")
> devman.central.InfraError: git is not on PATH; cannot read trunk's tree
> !!! Test "devman doctor reports nothing on a healthy plane" failed
```

`nix/devman-cli.nix:65-70` wraps `devman` with `dagu` and `watchexec` on PATH.
It does not add `git`. `check_link_drift`'s C3 arm needs `git ls-tree` to read
the overlay trunk, so **`devman doctor` crashes outright on any machine without
git on PATH** — it does not degrade and it does not report.

### Everything else is healthy

| `checks.x86_64-linux.*` | Result |
|---|---|
| `groups-validate` | green (cached, 0 s) |
| `identity-grammar` | green (cached, 0 s) |
| `link-adapter` | green (cached, 0 s) |
| `module-assertions` | green (cached, 0 s) |
| `python-tests` | **red** — failure 1 |
| `dagu-service` | **red** — failure 2 (~99 s to fail) |

`devenv tasks run -v base:check` (ruff) exits 0, "All checks passed!". The fast
loop is fully green: `devenv shell -- python -m pytest tests/unit -x -q` →
**676 passed in 9.29 s**, all three cutover modules included. So the code and the
tests are correct. Only the hermetic inputs are wrong.

## A trap that already cost one session

**Never pipe the gate through `tail` and read `$?`.**

```bash
devenv tasks run -v base:test 2>&1 | tail -120   # exit code is tail's: 0
```

That reports success on a failing gate. Use no pipe, or capture
`${PIPESTATUS[0]}`, or `set -o pipefail`. A gate that reports success while
failing is the exact shape AGENTS.md property 4 exists to prevent, and it
happened to the investigation session that produced these documents.

## Lane 1 — `m14-l8.0a-tools-fileset`

**Scope:** add `./tools` to the fileset at `flake.nix:160-166`. One line.

Write a comment noting the entry is removed again when `tools/cutover/` is
deleted. `PLAN-lanes.md` §F3 defers that deletion beyond this push.

**Gate:** `nix build .#checks.x86_64-linux.python-tests --no-link` exits 0, and
the three `test_cutover_*.py` modules collect and pass inside the hermetic build.

**Verify:** `base:check`, `base:unit`, `base:test`, `devman doctor`.
**Rollback:** `gitman undo`.

## Lane 2 — `m14-l8.0b-doctor-git-path`

**Scope:** add `git` to the `makeWrapper` invocation at `nix/devman-cli.nix:65-70`,
alongside `dagu` and `watchexec`.

**Gate:** `nix build .#checks.x86_64-linux.dagu-service --no-link` exits 0, then
the **whole** `base:test` exits 0.

**Verify:** the same four commands. **Rollback:** `gitman undo`.

### The design question, and do not quietly expand scope

`OPEN-QUESTIONS.md` O4 asks whether `devman doctor` should *also* survive a
missing `git` by reporting C3 as unavailable rather than crashing. There is a
real argument each way:

- AGENTS.md property 4 prefers a loud refusal to a silent default, and crashing
  is certainly loud.
- But it converts one unavailable check into zero available checks, and
  `check_link_drift` already has a dedicated `EMPTY` status used deliberately at
  `doctor.py:1633-1640`, because "an ok, 0 found line was indistinguishable from
  a broken walk for twelve days."

**Recommendation: do the wrapper fix only.** That makes the check able to run,
which is what the gate requires. If you believe the degradation belongs in the
same lane, say so and ask first — do not decide it silently. Either way, record
what you chose and why.

## Lane 3 — linkman's verify hook

**Different repository:** `/home/andrew/Documents/Projects/linkman`.

`linkman/gitman.toml` currently contains only `trunk = "main"`. There is no
`[publish] verify`, so **every lane in that repo lands without a gate.** devman's
equivalent is the pattern to copy:

```toml
trunk = "main"

[publish]
verify = ["nix", "flake", "check"]
verify_timeout = 3600
```

linkman's flake defines `checks.linkman` and `checks.overlay`
(`linkman/flake.nix:84-122`), so `nix flake check` is a meaningful gate there.

**Prerequisite, and it is not optional: confirm linkman's own `nix flake check`
is green BEFORE adding the hook.** Do not adopt a gate that fails on arrival —
that is precisely the state devman has been in since 2026-10-01, and it is what
lanes 1 and 2 exist to end. If linkman's gate is red, **stop, report what fails,
and do not add the hook.** Fixing linkman's checks is a separate decision.

Note `checks.overlay` builds a fresh nixpkgs with the overlay applied; it may be
slower than the other checks. Measure it and choose `verify_timeout` from the
measurement rather than copying devman's 3600 blindly.

## Process rules

- **Run everything inside `devenv shell`.** Never invoke bare `uv`, `python`,
  `pytest`, `ruff`, `git` or `jj`.
- **All version control through gitman**, and the workflow is:
  `gitman start <name>` → make changes → `gitman describe -m "…"` →
  `gitman land` → `gitman push`. **`gitman save` is deprecated — use
  `describe`.** `gitman start` adopts in-progress working-copy changes into a
  lane, so it is safe to edit first and start the lane after.
- Both repositories are **jj-colocated**. Do not use raw `git` write commands.
- In linkman, `gitman` is not on `$PATH` — it is a RepoMan toolchain binary
  resolved through `$REPOMAN_TOOLCHAIN_BIN`. Run it from inside
  `devenv shell`, or via `devenv shell -- gitman …`. Several
  `repoman-toolchain-core` generations exist in the store; do not pick one by
  hand.
- **Never add `Co-Authored-By` trailers** or any agent attribution to commits or
  PR bodies.
- **Do not write to `~/.config/devman`.** The permission classifier denies it,
  and `041/DECISIONS.md` D9 argues that denial is correct. Nothing in this
  session needs to.
- `nix flake check` may take a while. `dagu-service` is a QEMU VM test, ~99 s
  when it fails; expect longer when it passes.
- Report every count and timing with the date you measured it.

## Landing

Per the global rule: land and push each lane once its verify step passes — do
not stop to ask. Run the full loop: verify, describe, land, push.

Stop and ask if: verify fails or would be skipped, a merge conflict appears, or
the change grows beyond the scope above.

## Deliverables

1. **devman's gate green.** `devenv tasks run -v base:test` exits 0, measured
   without a masking pipe, with the output recorded.
2. **Lanes 1 and 2 landed and pushed.**
3. **linkman's verify hook added and landed** — or a clear report of why not,
   if its own gate is red.
4. **`PLAN-lanes.md` updated**: mark lanes 1 and 2 done with the date and the
   measured result, in the style already used for lane 3's entry. Record the O4
   decision in `OPEN-QUESTIONS.md` and, if you made a real choice, as a decision
   in `DECISIONS.md`.

## How to finish

Report: the gate's before and after state with real command output, what each
lane changed, the O4 decision and its reasoning, whether linkman's gate was
green and what you did about the hook, and anything you found that contradicts
these documents.

Do not begin lane 4 of `PLAN-lanes.md`.
