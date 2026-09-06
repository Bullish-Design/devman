Session root: ~/Documents/Projects/devman

# Phase 0 — remove the duplicate and undeclared tool sources

Context: an investigation (`.scratch/projects/023-toolchain/`) found that this
machine has several tools installed by more than one manager, and one Python
import path that no file in any repository declares. This phase deletes the
undeclared and duplicate ones. Nothing depends on any of them.

Read first: `.scratch/projects/023-toolchain/PROBLEMS.md` (P2, P4, P7).

## The job

1. Delete the stray sys.path injection:
   `rm ~/Documents/Projects/devman/.devenv/state/venv/lib/python3.13/site-packages/_agent_factory_spike_siblings.pth`
   It is residue from project 005. It makes `templateer`, `pydantic` and `yaml`
   importable in this devenv by accident.

2. `uv tool uninstall gitman` — a dormant editable install at `~/.local/bin/gitman`.
   `~/.local/bin` is not on PATH today, so it does nothing until something adds it.

3. `nix profile remove devenv` — an imperative install at `~/.nix-profile/bin`,
   which precedes `/etc/profiles/per-user` on PATH and therefore shadows the
   Home Manager one. Both are 2.1.2 today, by coincidence.

## Verification

```bash
devenv shell -- python3 -c 'import templateer'   # MUST now fail. That is the success condition.
ls -la ~/.local/bin/gitman                        # No such file
nix profile list                                  # act only
command -v devenv                                 # /etc/profiles/per-user/andrew/bin/devenv
cd ~/Documents/Projects/devman && devenv shell -- true
```

Step 1's failure is the point: it unmasks a real dependency gap that Phase 2 fixes.

## Rules

- Do not add a replacement for the deleted `.pth`. Do not add `templateer` to
  devman's `pyproject.toml`. devman must keep an empty venv and no `uv.lock` —
  its own `devenv.nix` argues why ("one name, two installs, resolved by order").
- Preserve unrelated worktree changes. This tree has many; do not clean them up.
- Nothing here needs a commit. If you commit, route it through gitman (lane,
  save, publish, PR to main), never raw git or jj.

## Stop if

Removing the `nix profile` devenv changes `devenv --version`, or any devenv
fails to enter afterwards. Roll back with `nix profile install nixpkgs#devenv`.
