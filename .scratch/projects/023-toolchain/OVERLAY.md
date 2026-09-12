# The lock overlay — replacing the publish-time rewrite

Supersedes the `vendomat.toml` publish path for `repoman.lock`. Written after
Phase 3b landed and its verification exposed the design fault below.

## The fault

`repoman.lock` conflates two facts:

1. **Which packages the toolchain contains.** Portable. Belongs in git.
2. **Where this machine fetches them from.** Machine-local. Does not belong in git.

The repo commits fact 2 and synthesizes fact 1 at push time. That inverts the
normal relation: it version-controls the machine-specific shape and treats the
portable shape as derived.

Vendomat's publish path exists only to undo that inversion. It replays every
outgoing commit in a disposable worktree, rewrites sources by exact text
substitution, pushes the rewritten commits, then aborts the real push. The cost:

- Local `main` and origin `main` diverge permanently. `git pull` cannot work,
  and a second machine cannot participate.
- Reconciliation depends on `refs/vendomat/published/<remote>/<branch>`, which
  exists on one machine.
- Every successful push reports a nonzero status. The documentation must teach
  that failure means success.
- Each replayed commit runs `uv lock`.

## The fault is structural, not a bug

Measured on this repo, 2026-09-07. Published `84c1b95` carries
`vendomat.toml` at `v0.3.2` and `repoman.lock` at `v0.3.1`.

Substitution maps `local` -> `github` by literal text. The parent commit already
rewrote `path:/home/andrew/Documents/Projects/vendomat` to `@v0.3.1` and
committed it. The child commit edits only `vendomat.toml`, so after the replay
the lock still holds `v0.3.1` and no `path:` string remains to match. The bump
is a no-op.

Generalized: **once a replacement publishes at some tag, editing that tag can
never change the published lock again.** Every manager pin is frozen at whatever
it said on first publication. The lock header warns that a stale pin is possible;
it is in fact unavoidable, and bumping does not cure it.

## The design

Commit the portable shape. Override locally.

`repoman.lock` names releases in git, on every machine. An untracked
`repoman.local.lock` names this machine's working trees. `repoman-sync --machine`
layers the second over the first.

```
repoman.lock          committed, fleet shape, correct anywhere
repoman.local.lock    gitignored, this machine's path: overrides
```

The overlay mirrors the lock's schema, so the two files read alike. Only `source`
is required; the lock supplies `package`.

```toml
# repoman.local.lock
[repoman]
source = "path:/home/andrew/Documents/Projects/repoman"

[managers.git]
source = "path:/home/andrew/Documents/Projects/gitman"
```

An overlay key absent from the lock is an error, not a silent addition. That
catches a typo instead of installing something the lock never named.

### The recorded manifest holds the effective shape

`$REPOMAN_TOOLCHAIN_VENV/repoman-toolchain.toml` must record the merged result,
not the committed lock. Two reasons:

- `checks.py` reads it to reconcile installed packages against the lock. It must
  see `path:` for an editable install or it reports a false version conflict.
- `declared_version` (`checks.py:334`) and `_constraints` (`:352`) already branch
  on `path:`. Recording the effective shape means neither changes.

### Machine-lock identity needs a new test

`_is_machine_lock` (`checks.py:570`) decides whether a repo-root `repoman.lock`
is the machine manifest by asking whether the recorded `[repoman].source` is a
`path:` resolving to the repo root. Under this design that holds only while an
overlay is active; a fleet machine would warn "orphan" against its own lock.

Replace the inference with a recorded fact. Write the synced-from path into the
manifest as data, and compare it:

```toml
[toolchain]
synced_from = "/home/andrew/Documents/Projects/repoman/repoman.lock"
```

`repoman-sync.sh:58` currently greps the `# synced from` comment for the same
purpose. Both callers should read the field.

## What this removes

- `repoman/vendomat.toml`
- `repoman/.pyjutsu-hooks.toml`
- the installed `.git/hooks/pre-push`
- `refs/vendomat/published/origin/main`

Vendomat keeps Face A — the hermetic native wheel build, the manylinux tag, the
RUNPATH strip, the release upload. That is load-bearing and untouched. Only the
manifest-rewriting publish path stops being used here.

Vendomat's substitution primitive stays broken for any other consumer that bumps
a pin. Fixing it is a separate decision, tracked below.

## Migration hazard

origin/main holds published commits (`84c1b95`, `4974161`) that diverge from
local main (`a3efddb`, `590688c`). Adopting this design means the two histories
must converge. A force-push of local main over origin is the clean resolution and
the one destructive step in the plan. It needs explicit approval and a check that
no other clone tracks that branch.

## Open

- Bump discipline: releasing a manager must bump its entry in the committed lock.
  Nothing enforces this yet. `repoman doctor` could compare each pin against the
  newest tag on the remote.
- Optional convenience: derive the overlay from sibling checkouts under
  `REPOMAN_DEV_ROOTS` instead of maintaining the file by hand. Implicit, so it
  should stay opt-in per run.
- Whether to repair vendomat's replacement primitive (match on the package key,
  not on literal text) for its other consumers.
