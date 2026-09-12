Session root: ~/Documents/Projects/repoman

# Phase 3c — commit the fleet lock, overlay the dev paths

Context: Phase 3b put the machine toolchain's fleet shape behind a push-time
history rewrite. Verifying it showed the rewrite cannot express a pin bump, and
that it costs a permanently divergent origin. This phase inverts the design:
commit the portable shape, override it locally.

Prerequisite: Phase 3b landed. `repoman.lock` already carries a working `url:`
source form for pyjutsu; keep it.

Read first:
- `~/Documents/Projects/devman/.scratch/projects/023-toolchain/OVERLAY.md` — the
  design and the measured evidence for it
- `~/Documents/Projects/repoman/modules/scripts/repoman-sync.sh` — the resolver
  is the python heredoc at lines 98-220
- `~/Documents/Projects/repoman/src/repoman/checks.py:334`, `:352`, `:458`,
  `:570`

## The job

### 1. Invert the committed lock

Rewrite `repoman.lock` so every entry names a release. The five `path:` entries
become the pins that `vendomat.toml` currently holds:

    repoman    -> git+https://github.com/Bullish-Design/repoman@v0.7.1
    copyroom   -> git+https://github.com/Bullish-Design/copyroom@v0.7.4
    gitman     -> git+https://github.com/Bullish-Design/gitman@v0.6.0
    docman     -> git+https://github.com/Bullish-Design/docman@v0.1.0
    vendomat   -> git+https://github.com/Bullish-Design/vendomat@v0.3.2

Confirm each tag resolves before committing:
`git ls-remote --tags https://github.com/Bullish-Design/<repo>.git refs/tags/<tag>`

The `templateer` and `pyjutsu` entries are already fleet-shaped. Leave them.

Rewrite the lock's header comment. It currently describes the committed file as
the DEV shape and the fleet shape as a push-time swap. That is now backwards.

### 2. Add the overlay

`repoman.local.lock` at the repo root, gitignored. Same schema as the lock; only
`source` required, `package` comes from the lock.

    [repoman]
    source = "path:/home/andrew/Documents/Projects/repoman"

    [managers.git]
    source = "path:/home/andrew/Documents/Projects/gitman"

Layer it in the resolver heredoc, before targets are computed:

- `REPOMAN_LOCAL_LOCK` overrides the overlay path, mirroring `REPOMAN_LOCK`.
- `--no-local` skips the overlay entirely, so a CI runner can force the pure
  fleet shape.
- An overlay key absent from the lock is a hard error naming the key. Do not
  silently add an entry the lock never declared.
- A missing overlay file is normal and silent.

Write this machine's overlay covering repoman, copyroom, gitman, docman and
vendomat. Do not commit it. Add it to `.gitignore`.

### 3. Record the effective manifest

`repoman-sync.sh:414` writes `$toolchain_venv/repoman-toolchain.toml` as the raw
lock. It must write the MERGED result instead, or `checks.py` compares an
editable install against a git pin and reports a false conflict.

Add a machine-readable identity field to the manifest:

    [toolchain]
    synced_from = "<absolute path to the lock>"

Then make both current callers read it instead of inferring:

- `repoman-sync.sh:58` greps the `# synced from` comment.
- `_is_machine_lock` (`checks.py:570`) tests whether `[repoman].source` is a
  `path:` resolving to the repo root. That inference breaks the moment the lock
  is fleet-shaped — a fleet machine would warn "orphan" against its own lock.

Check that a new top-level `[toolchain]` table is not mistaken for a manager
entry anywhere that iterates the manifest (`checks.py`, `aggregate.py`).

`declared_version` (`:334`), `_constraints` (`:352`) and the editable-freshness
check (`:458`) should need no change, because the recorded manifest still shows
`path:` wherever an editable install happened. Confirm that rather than assume it.

### 4. Retire the publish path here

Delete `repoman/vendomat.toml`, `repoman/.pyjutsu-hooks.toml`,
`.git/hooks/pre-push`, and `refs/vendomat/published/origin/main`.

Leave `devenv.yaml`'s `vendomat/modules` import alone. Its `install-hook` step is
already guarded by `[ -f vendomat.toml ]`, so removing the manifest disarms it.

Do not touch vendomat's wheel build and release upload. That work is unaffected.

### 5. Tests

In `tests/test_repoman_sync.py`, alongside the existing source-form tests:
overlay replaces a source; absent overlay installs the fleet shape; `--no-local`
ignores a present overlay; an unknown overlay key exits nonzero and names the
key; the recorded manifest holds the merged shape and the `synced_from` field.

In `tests/test_checks.py`: `_is_machine_lock` is true for a fleet-shaped lock
whose manifest records a matching `synced_from`, and false for an orphan.

## Verification

    devenv shell -- testee verify
    devenv shell -- repoman-sync --machine
    devenv shell -- repoman doctor

    # the fleet shape must install with no overlay and no wheelhouse
    cd $(mktemp -d) && git clone https://github.com/Bullish-Design/repoman
    cd repoman && env -u UV_FIND_LINKS REPOMAN_TOOLCHAIN_VENV=$(mktemp -d)/venv \
      devenv shell -- repoman-sync --machine --no-local

The last command is the point of the whole phase. It must succeed on a clone
that has no working trees beside it.

## Stop and ask before

Force-pushing local main over origin. origin/main holds published rewritten
commits (`84c1b95`, `4974161`) that diverge from local main (`a3efddb`,
`590688c`). Converging them is the one destructive step here. Confirm no other
clone tracks that branch first, and get explicit approval.

## Do not

Fix vendomat's replacement primitive in this phase. It is genuinely broken for
any consumer that bumps a pin — matching on literal text cannot be idempotent
across an accumulating replay — but repairing it is a separate decision, and
nothing here depends on it.
