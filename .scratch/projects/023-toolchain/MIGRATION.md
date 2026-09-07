# Migration plan, ordered by risk and reversibility

Each step is independently useful and independently revertible. Stop at any
point and the machine is in a consistent state.

## Step 0 — do nothing (already correct)

See `DO-NOTHING.md`. Roughly two thirds of the current design needs no change.

## Step 1 — delete the residue (risk: none, reversible: trivially)

```
rm ~/Documents/Projects/devman/.devenv/state/venv/lib/python3.13/site-packages/_agent_factory_spike_siblings.pth
uv tool uninstall gitman
```

Fixes P2 and P7. Expected effect: `devenv shell -- python3 -c 'import
templateer'` starts failing. **That is the point** — it makes the real
dependency gap visible instead of masked. Reverse by re-creating the file.

## Step 2 — `uv` in the login shell, toolchain venv on `sessionPath` (risk: low)

One `home.packages` addition and one `home.sessionPath` line in
`nix-meta/profiles/developer.nix`. `nixos-rebuild test` first; roll back with
`nixos-rebuild --rollback`. Fixes P9.

Verify: `zsh -lic 'command -v uv gitman'` names both.

## Step 3 — one owner per name (risk: low, reversible)

```
nix profile remove devenv        # P4
```
and remove `repoman` from `home.packages` (P3). Rebuild.

Verify: `command -v repoman` names the toolchain venv from a login shell; `rlist`
and `rstatus` run 0.7.1.

## Step 4 — `gitman log --json` (risk: low, contained to gitman)

Add the command in the gitman repository, with its own tests. Nothing depends on
it until step 5. Reversible by not using it.

## Step 5 — rewrite the two `changelog.yaml` steps (risk: medium)

Replace both `devenv shell -- python3 - <<PYEOF ... import pyjutsu` blocks with
`devenv shell -- gitman log ...`. Fixes P1.

This is the step that must be proven end to end in a disposable adopter, through
a real `gitman start` / `save` / `land` and the real post-hook chain, as the 022
kickoff already requires.

Reversible: revert the workflow file. Note it cannot regress anything, because
the current form does not work.

## Step 6 — `templateer` as a versioned dependency (risk: medium)

1. `templateer_v2` tags a release and publishes a wheel to the wheelhouse.
2. `groups/changelog/README.md` states the dependency as a cost of taking the
   group.
3. `devman/pyproject.toml` declares it, pinned by URL and hash.
4. The workflow drops `TEMPLATEER_PATH` and `PYTHONPATH`, and calls a small
   adapter in `groups/changelog/` that uses `TemplateRegistry.from_paths`.
5. `TEMPLATEER_TEMPLATE_PATH` resolves through `$DEVMAN_SELF_DIR`.
6. The generation step checks `finish_reason` and fails on anything but
   `stop`. Measured (P6): gemma returns `content: ""` with
   `finish_reason: "length"` on a short budget — an HTTP 200 carrying nothing.

Fixes P2's second half and the 022 acceptance criterion "no sibling absolute
path". Reversible per file until step 4 lands.

## Step 7 — reproducibility of the machine lock (risk: medium, do last)

- Change `repoman.lock`'s `git-pyjutsu` entry from `wheel:pyjutsu>=0.20.0` to
  the exact release URL plus sha256 that `gitman/uv.lock` already records (P8).
- Record what `repoman-sync --machine` actually installed, so the venv is
  rebuildable without `UV_FIND_LINKS` pointing at one store path on one machine.

## Step 8 — separate projects, out of scope here

- The `git+file:` inputs across nix-meta and every devenv (P5). Measured cost:
  6.05 s cold evaluation against 0.755 s warm, on every dependent devenv, after
  any edit anywhere in the source repository. nix-meta has already disabled two
  such inputs for this reason.
- Garbage: `~/.cache/uv` 43 GB, `pyjutsu/target` 6.9 GB, `/home/andrew/$h`.
