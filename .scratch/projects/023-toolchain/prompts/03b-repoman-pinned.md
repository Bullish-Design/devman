Session root: ~/Documents/Projects/repoman

# Phase 3b — make the machine toolchain rebuildable somewhere else

Context: four entries in `repoman.lock` are `--editable` installs of live working
trees (`gitman`, `repoman`, `copyroom`, `docman`), and the `pyjutsu` entry is a
version floor resolved with `--upgrade` against a wheelhouse that only exists in
one directory on one machine. The shared toolchain therefore cannot be rebuilt on
another machine, and nothing records what it actually installed.

Prerequisite: Phase 3 repaired vendomat's builder and publish path.

Read first:
- `~/Documents/Projects/devman/.scratch/projects/023-toolchain/PROBLEMS.md` (P8)
- `~/Documents/Projects/vendomat/README.md`, "Local vendoring and GitHub publishing"

## The job

1. A `vendomat.toml` at the root of each of `gitman`, `repoman`, `copyroom`,
   `docman`:
   ```toml
   [[replacement]]
   files = ["repoman.lock"]
   local = "path:/home/andrew/Documents/Projects/gitman"
   github = "git+https://github.com/Bullish-Design/gitman.git@v0.6.0"
   ```
   The repo must import `vendomat/modules`; `vendor.publish.enable` defaults to
   true and the pre-push hook installs itself on shell entry when the manifest is
   present. It refuses to overwrite an existing `pre-push` hook.

2. Pin `repoman.lock`'s pyjutsu entry to the published release URL — the same one
   `gitman/pyproject.toml` names — instead of `wheel:pyjutsu>=0.20.0`. This
   removes the `UV_FIND_LINKS` precondition from `repoman-sync --machine`.

## Verification

```bash
devenv shell -- vendomat publish --dry-run      # in EACH manifest repo, before pushing
devenv shell -- repoman-sync --machine
cat ~/.local/share/repoman/venv/lib/python3.13/site-packages/pyjutsu-0.20.0.dist-info/direct_url.json
#   must still name the GitHub release URL
devenv shell -- repoman doctor
```

Read the manifest and lock diff that `--dry-run` prints. Vendomat rejects a push
if regenerating `uv.lock` adds, removes or changes a resolved version — review
that graph change separately if it fires.

Expect the first real push to print a nonzero status: the hook deliberately
aborts the outer push after pushing the rewritten commits. The
`published GitHub-source commit(s)` line above it is the success signal. This
looks like a failure the first time.

## Stop if

`repoman-sync`'s `wheel:` source parser rejects a PEP 508 direct reference. Add a
`url:` source form; do not overload `wheel:`.
