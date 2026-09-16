# Project 039 — vendomat half: stage log

This document records the vendomat-half work. The repoman half reads it.

## Stage 1 — 2026-09-15: measurement, implementation, and the machine-boundary block

Status: **implementation complete and verified; release and migration blocked by a
privileged step.**

### Measurement, re-verified

The prompt's counts were checked against the live tree. Two disagreements matter.

| Claim | Measured |
|---|---|
| 16 repositories declare vendomat | 16 (15 consumer `devenv.yaml` files; `nix-meta/flake.nix` is the machine pin) |
| 14 import `vendomat/modules` | 14 |
| 2 distinct pinned revisions | 2 (`511e70f` at `v0.3.9`; `b40d59f` at `v0.3.7`) |
| 6 unpinned `git+file:///home/andrew/...` inputs | 6 (flora, loci-core, loci.nvim, nix-nvim, nix-paseo, repoman) |
| 0 repositories at HEAD | 0 |
| `vendor.toolchain.enable` set by 11 repositories | **10** (to `false`, not `true`) |

The last row is the important one. The 039 README says the eleven importers set
`vendor.toolchain.enable = true`. They set `false`: argentic, eventic, flora,
flora-core, loci.nvim, nix-nvim, paloma-text-pipeline, poddantic, pyllij, shellij.
Each also sets `repoman.cliProvider = "venv"`.

**Consequence for the migration.** Deleting `vendor.toolchain.enable = false` is
not a no-op. The option default is `true`, so the removal turns the store
toolchain on and sets `repoman.cliProvider = "store"`. A safe migration preserves
the declaration as `[toolchain] enable = false` in each of those ten
repositories' `vendomat.toml`. Do not delete a stale count's line.

The remaining importer, `loci-core`, sets `knowledge.enable = true`. `repoman`
sets `vendor.enable`, `vendor.libs`, and `vendor.toolchain.mode = "editable"`.
`flora-qc` and `tyo3` set no option. `nix-paseo` declares the input and does not
import the module.

### Phase 0 gates — passed

```
devenv shell -- testee verify --mode quick                 PASSED (19.5s)
VENDOMAT_E2E=1 devenv shell -- testee verify --mode quick  PASSED (58.5s)
nix build .#repoman-toolchain-core                          /nix/store/z6ayz3iz2c3plgidf7kfslwnwrzc7yk2-repoman-toolchain-core
nix build .#devman-plane                                    /nix/store/x8nh95z1ahpnq7dkklszz7ckg12hcbjg-devman-plane
```

Toolchain digest:
`61ee05fe4280a060d3fbf1f807dbce63f5442f2abea901b5264e6b4d0a330d72`
(`share/vendomat/toolchain.json`, roster core).

### Release `v0.4.0` — not performed

`git describe origin/main` is `v0.3.9-19-gc077cc0`. The tag `v0.3.9` points at
`511e70f`. The release needs a tag and a push to `origin`. This session did not
run it. The correct sequence is the six-step canonical release in the gitman
skill:

```
gitman start 039-vendomat-v0.4.0
gitman version bump minor
gitman save -m "chore: bump version to 0.4.0"
gitman land
gitman push
gitman release
```

Then bump `nix-meta/flake.nix` to the new tag, `nix flake lock --update-input
vendomat`, and `nixos-rebuild boot`, then `switch`.

### Phase 1 — package and install the module

Implemented:

- `packages.vendomat` installs `share/vendomat/consumer-module.nix` and
  `share/vendomat/machine.json`. It names the wheelhouse, the toolchain closure,
  and the vendor knowledge tree in `machine.json`, so the consumer module
  resolves store paths without a flake input.
- `nixosModules.default` adds `vendomat.installConsumerModule` (default `true`),
  installs the package, and sets
  `environment.pathsToLink = [ "/share/vendomat" ]`. The `pathsToLink` line is
  required; NixOS links selected `share` subtrees, not all of `/share`.
- `checks.<system>.vendomat-consumer-module` runs
  `builtins.functionArgs (import <module>)` with `nix-instantiate`, and evaluates
  the real module with `lib.evalModules` against a fixture repository that has no
  `vendomat.toml`. It asserts the defaults resolve and that a manifest enables
  the knowledge face.

Measured store paths:

```
nix build .#checks.x86_64-linux.vendomat-consumer-module
  /nix/store/mwxbxgxjvjwm606w76p63z7yzcbfvzkm-vendomat-consumer-module-check
vendomat package
  /nix/store/45s04qbjwwgy32lv56pjz96f5ssvxxbd-vendomat-0.3.9
```

### Machine boundary — blocked

```sh
test -f /run/current-system/sw/share/vendomat/consumer-module.nix   # absent
```

This session runs as uid 1000 and has no `sudo`. `/run/current-system` is
read-only. `nixos-rebuild switch` and the `/run/current-system/sw/share/vendomat`
install cannot run here. The prompt is explicit: **do not migrate a repository
before this passes.** No consumer was migrated. Phase 3 did not start.

A deliberately avoided trap, recorded so the next session does not create it:
`/run/current-system/sw/bin/devman-link` and
`/run/current-system/sw/share/devman/link-module.nix` are present from project
038. `configuration.nix`-level `environment.pathsToLink` accumulates subtrees, so
adding `/share/vendomat` does not disturb the devman path.

### Phase 2 — the manifest-driven module

`modules/devenv.nix` now resolves every setting in this order: `vendomat.toml`
value, then the compatibility option, then the option default. It reads the
manifest with `builtins.fromTOML` at `${config.devenv.root}/vendomat.toml`. An
absent file means all defaults.

The schema:

```toml
[vendor]                 # Face A: enable, libs, self, noBuild, sharedCargo
[vendor.publish]         # enable
[toolchain]              # Face D: enable, mode, roster
[knowledge]              # Face B: enable, skillsDir
```

The module also reads the machine closure from
`/run/current-system/sw/share/vendomat/machine.json`, and falls back to the
`vendomat` flake input when the file is absent. The option declarations remain,
so the migration is reversible.

The compatibility fallback is `fromManifest "<path>" config.<option>`. It stays
for one release. Do not remove it because one canary passes.

### Phase 3 — consumer migration — not started

Blocked by the machine boundary. Per-repository work is unchanged and is in the
prompt, section 5, phase 3. Read the corrected measurement above before deleting
any option line.

### Phase 5 — carry-forward, prune, and retention

Implemented in `src/vendomat/plane.py` and `src/vendomat/cli.py`:

- `GenerationStore.active_project_names()` seeds the project set from the active
  generation.
- `_plane_operation` treats the active generation as the default declaration. An
  explicit `--project`/`--project-root` selection **adds** to that set; it does
  not replace it. A project absent from the selection is carried forward and
  printed: `carried forward N active project(s) not named on the command line`.
- `--prune <name>` is the only way to remove a project. A prune name absent from
  the active generation is reported and ignored.
- `--keep N` (default 2) bounds generation retention after an update.
  `GenerationStore.retain` always keeps the active generation and its immediate
  predecessor, so a rollback stays possible after a mid-history activation.

Tests added: carry-forward seeding, retention bounds, the rollback pair, an
invalid `--keep`, and the two CLI flags.

### Environment artifacts worth recording

Two artifacts cost time. Both are recorded because the error text names a store
path and not the cause.

**A stale git index.** The repository is jj-colocated. Its git index was stale:
`git ls-files -s` held empty blobs for `src/vendomat/plane.py`,
`tests/test_plane.py`, and `.devman/project.toml`. Nix's git fetcher then exported
a tree that disagreed with the tree it hashed, and a consumer's local flake input
failed with `path '/nix/store/<hash>-vendomat' is not valid`. `git add -A`
repaired the index. A flake source that is read through a local input is only as
consistent as the git index.

**The store-consumer fixture copied mutable state.** The fixture declared
vendomat as `path:../../..`. A `path:` input copies the whole directory,
including vendomat's mutable `.devenv/` (169 MB). That state changes while a
shell runs, so the narHash moved between evaluation and build and the copied
path became invalid: `path ... is not valid` during `Evaluating shell`. The
fixture now declares `git+file:../../..`. That input is still a relative local
path, still carries uncommitted worktree changes, and excludes ignored state.
Measured: `nix flake metadata path:../../..` changes its narHash when a file
under `.devenv/` changes; `git+file:../../..` does not.

### Gate after the change

```
devenv shell -- testee verify --mode quick                 PASSED
VENDOMAT_E2E=1 devenv shell -- testee verify --mode quick  PASSED
nix build .#repoman-toolchain-core                          /nix/store/z6ayz3iz2c3plgidf7kfslwnwrzc7yk2-repoman-toolchain-core
nix build .#devman-plane                                    /nix/store/x8nh95z1ahpnq7dkklszz7ckg12hcbjg-devman-plane
nix build .#checks.x86_64-linux.vendomat-consumer-module    /nix/store/mwxbxgxjvjwm606w76p63z7yzcbfvzkm-vendomat-consumer-module-check
```

The toolchain digest is unchanged: `61ee05fe…`.

### Version control — resolved

**Correction to the earlier note.** The earlier reading was wrong. There was no
15-commit gap and no branch-ownership ambiguity. `gitman status` showed the true
topology once gitman was on PATH:

- trunk `main` was `c077cc0` — equal to `origin/main`, in sync.
- lane `038-devman-plane-redesign` was `5517878`, 1 behind trunk.
- `5517878` was **already an ancestor of trunk**; `git diff 5517878 main` was
  empty. The 038 lane carried **zero** unique content.

The 15 commits never needed a decision. The 038 lane was merged residue.

**What was done, in order:**

1. `gitman reconcile` — adopted the stray 039 working tree into a lane
   (`adopted-0e3a4973`).
2. `gitman start 039-vendomat-depin` — adopted the current working copy. The
   working copy was a **strict superset** of the adopted snapshot (it added
   `classify_projects` and 102 more lines), so nothing was lost.
3. `gitman land 038-devman-plane-redesign` — retired the empty leftover lane.
   **This was a mistake.** It re-derived trunk as a plain commit `5517878`
   instead of leaving trunk at origin's merge commit `c077cc0`.
4. `gitman abandon adopted-0e3a4973` — the stale snapshot was superseded.
5. `gitman pull` / `gitman catchup` — both reported the twin correctly, and both
   declined to move trunk. Their content gate keeps local for a twin.
6. `gitman push --reset-origin` — the documented remedy for re-hash-twin residue.
   The trunk model is local-authored, so origin is a mirror. This aligned origin
   to the authored trunk. Content was proven identical first: both sides carried
   tree `7ae7a883`.
7. `gitman save -m "vendor the consumer module through the machine manifest"`.

**Two gitman 0.6.2 findings, recorded:**

- `_integrate_trunk` keeps local trunk for a content twin, so `pull` and
  `catchup` never fast-forward a behind-only trunk. Correct for a twin, but it
  also covers the plain ancestor case.
- `_trunk_content_relation` returns `forge-ahead` at `ahead == 0` **before** its
  documented twin-proof content check runs. A behind-only trunk therefore blocks
  `push` while `pull` calls the same commit a twin. The two paths disagree.
- `gitman save` rewrites the lane commit. The colocated git HEAD then points at
  the old commit and reads stranded. `gitman reconcile` repairs it — that is the
  sanctioned fix.

**Environment gap.** `gitman` is a flake input, not in the devenv shell PATH.
Build it with `nix build .#gitman --no-link --print-out-paths` and prepend
`bin/`.

**Final state** — `gitman status` CANONICAL, `gitman doctor` HEALTHY:

```
trunk: main @ 5517878  (in sync with origin)
  039-vendomat-depin   draft   1 change, +752 -135   · you are here
```

### Final gate

```
devenv shell -- testee verify --mode quick                 PASSED
VENDOMAT_E2E=1 devenv shell -- testee verify --mode quick  PASSED (twice)
nix flake check                                             all checks passed
nix build .#repoman-toolchain-core                          /nix/store/z6ayz3iz2c3plgidf7kfslwnwrzc7yk2-repoman-toolchain-core
nix build .#devman-plane                                    /nix/store/x8nh95z1ahpnq7dkklszz7ckg12hcbjg-devman-plane
nix build .#vendomat                                        /nix/store/wrg92bi3f1nx1z4sb44ag7sffni4iw4b-vendomat-0.3.9
nix build .#checks.x86_64-linux.vendomat-consumer-module    /nix/store/hy2lbrzfnrkh3chbdppnbwn0kxxjwx04-vendomat-consumer-module-check
```

The toolchain digest is unchanged: `61ee05fe…`.

### Next steps, in order

1. ~~Resolve version control and save the `039-vendomat-depin` lane.~~ DONE —
   see "Version control — resolved" above.
2. Land the `039-vendomat-depin` lane into trunk, then cut `v0.4.0`
   (six-step canonical release).
3. Bump `nix-meta/flake.nix`, re-lock, `nixos-rebuild boot`, then `switch`.
4. Prove the boundary:
   `test -f /run/current-system/sw/share/vendomat/consumer-module.nix`.
5. Migrate the fifteen consumers, one lane each. Preserve the ten
   `vendor.toolchain.enable = false` declarations as `[toolchain] enable = false`.

### Machine gate

```
cd /tmp && env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
  exit 1, 8 findings. It keeps the known finding "vendomat: uncommitted changes,
  consumed unpinned by 6 project(s)". That finding clears when this work is
  committed. No new finding class appeared.
```

Fleet sweep (`devman-link status`, environment cleared, from `/tmp`):

```
47  0 <project>
 1  1 image-gen-pipeline
```

The one refusal is pre-existing drift, not a regression: a real
`.claude/skills` directory where the central declaration declares a link, so the
adapter reports `promote`. This session touched no central declaration. Record it
for the operator; do not repair it inside this project.

### Not done, and why

- `v0.4.0` tag and push. Needs the version-control decision above, then the
  canonical release.
- `nix-meta` bump, `nixos-rebuild boot`/`switch`, and the boundary proof. Needs
  root; this session has none.
- Phase 3 consumer migrations. The prompt forbids migration before the boundary
  proof passes.
- Phase 4 stale devman lock cleanup. It follows Phase 3.
- `vendomat.toml` for repoman and loci-core, and for the ten
  `vendor.toolchain.enable = false` repositories. Write these in the same lane as
  each repository's input removal.
