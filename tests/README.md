# tests — what this suite protects, and what it refuses to test

**The point is not coverage. The point is that a refactor cannot silently undo a
measured refusal.**

Several mechanisms in `src/devman/` look exactly like cleanup a future refactor
would delete: clearing `$SHELL` before `dagu enqueue`, clearing the inherited
directory names, the nested-checkout refusal, reading a `steps:` mapping as no
steps at all. Each exists because a run once succeeded and did its work in the
wrong place. Each now has a test that names the entry that measured it.

Set no coverage target. A test that breaks when a function is renamed, but
nothing behaves differently, is a liability here.

## The two layers

| | |
|---|---|
| `unit/` | the bounded reader, resolution, the refusal contract, the watcher's decisions. No subprocess, no network, no Dagu. |
| `conformance/` | the devman/Dagu semantic boundary, against the pinned binary. |

`fixtures/dagu/` holds one YAML file per case the conformance layer pins. Each
carries a comment saying what Dagu does with it and why devman reads it that way.

**A Dagu pin bump must run `conformance/` before it is accepted.** Every unit
test asserts a measurement of Dagu 2.15.0's behaviour, and nothing but that layer
notices when the binary underneath those measurements changes. A failure there is
a pin bump, not a devman regression — read Dagu's message before changing a case.

## How to run it

```bash
devenv tasks run -v base:unit     # about a second — the developer's loop
devenv tasks run -v base:test     # nix flake check, which includes python-tests
```

Both run the same suite. `base:unit` runs it in this shell; `checks.python-tests`
in `flake.nix` runs it hermetically, with the pinned Dagu, on a machine that has
never entered this shell. pytest comes from nixpkgs in both places and is not in
the venv — a Nix check has no network, so a venv pytest could not serve it, and
two installs of one name resolved by order is §3.3's `devman 0.2.0` hazard.

## The rules this suite keeps

1. **Nothing touches the installed plane.** No `~/.local/share/devman`, no
   running Dagu service. Every test builds its own registry under `tmp_path`
   (`helpers.py`). The Nix sandbox is what guarantees it rather than a habit.
2. **`dagu validate` only.** It reads a file and exits. `dagu dry` creates
   `log_dir`, which reproduces the literally-named directory the bounded reader
   exists to avoid (S1). If a case ever needs `dry`, confine it to a disposable
   home and say so in a comment.
3. **Assert the measurement, do not re-derive it.** Every table here comes from
   `.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`, entries S-8, S-9,
   S-10 and S-11. Cite the entry in the test's docstring so the next reader can
   find the evidence.
4. **When a test and a docstring disagree, measure against the pinned binary and
   fix whichever is wrong.** Do not make the test match the code. S-11 found one
   this way: `Workflow.queues()` read a `steps[].queue` Dagu 2.15.0 refuses
   outright, and missed the `with.queue` it accepts.

## What is not tested here, and where it is

| Not here | Where |
|---|---|
| Dagu's HTTP API — queues, health | `nix/tests/dagu-service.nix`, against a real service |
| the watchexec supervisor loop, systemd | the same NixOS test |
| the devenv module's projection | `groups-validate`, and a shell entry |
| every shipped group file loading | `checks.groups-validate` |

A stub of Dagu's HTTP API would test the stub. A mocked systemd, a mocked queue
and a second implementation of Dagu's schema are all out for the same reason.
