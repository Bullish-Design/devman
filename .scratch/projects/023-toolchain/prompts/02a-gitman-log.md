Session root: ~/Documents/Projects/gitman

# Phase 2a — add `gitman log --json`

Context: devman's changelog workflow needs a jj revset range read and each
change's description. gitman has no `log` command — its CLI is entirely lane
lifecycle verbs — so the workflow imports `pyjutsu` directly inside
`devenv shell -- python3`. That import fails, because the shared toolchain venv
lends console scripts through PATH and PATH does not set `sys.path`. Adding a
console script closes the gap and removes the cross-repository import.

Read first:
- `~/Documents/Projects/devman/.scratch/projects/023-toolchain/PROBLEMS.md` (P1)
- `~/Documents/Projects/devman/groups/changelog/workflows/changelog.yaml`, steps
  `gate` and `write` — the two call sites this must replace.

## The job

Add:
```
gitman log --revset '<a>..<b>' --json
```

emitting one object per change with at least `change_id` and `description`.
That is exactly what the workflow does today through
`pyjutsu.Workspace.load(".").log(...)` and `ws.resolve(cid).description`.

Requirements:
- JSON on stdout, nothing else. Diagnostics to stderr.
- Non-zero exit on a revset that does not parse, with the revset in the message.
- Newest-last ordering, matching the workflow's `reversed(ws.log(...))` usage.
- Tests for: empty range, single change, unparseable revset.

## Verification

```bash
devenv shell -- gitman log --revset 'main~5..main' --json | python3 -m json.tool | head
devenv shell -- gitman log --revset 'nonsense~~' --json ; echo "exit=$?"   # non-zero
```
Then this repo's own gate — read `AGENTS.md`; it is repoman-managed with the
`test` manager, so `devenv shell -- testee verify` is the likely entry point.
Do not invent a command.

## Rules

- **Do not touch `[tool.uv.sources]` in `pyproject.toml`.** The pyjutsu GitHub
  release URL there is the fix for issue G3 (`.scratch/projects/32-loci-core-adoption-issues/ISSUES.md`,
  `35-wheel-distribution/OUTCOME.md`) and is what makes gitman adoptable in a repo
  with no Nix. A later phase makes the vendomat wheelhouse emit the same bytes;
  it never replaces this.
- Route version control through gitman itself: lane, `save`, `publish`.
- Nothing consumes this command yet, so it cannot regress anything.

## Ask the owner before starting

`log` is a read verb in an otherwise lane-lifecycle CLI. The alternative is that
devman's changelog group declares `pyjutsu` as its own dependency and accepts the
coupling. Confirm which they want before writing code.
