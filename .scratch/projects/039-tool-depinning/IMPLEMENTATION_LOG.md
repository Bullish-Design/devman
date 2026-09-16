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

## Stage 2 — 2026-09-16: audit of both halves, and the manifest gap

Stage 1 above is **stale**. It was written before the releases. Corrections:
`v0.4.0` and `v0.4.1` both shipped, the machine boundary now passes, and the
measurement it records was itself wrong in two places.

### Corrected measurement, 2026-09-16

| Claim in Stage 1 / README | Measured |
|---|---|
| 16 repositories declare vendomat | **15** — the sixteenth was `nix-meta`, the machine pin |
| 6 unpinned `git+file://` consumers | **5** — repoman moved to a tag on 2026-09-07 |
| 2 distinct pinned revisions | **3** — `v0.3.4`, `v0.3.7` ×7, `v0.3.9` ×2 |

The `v0.3.4` pin is **repoman's own**, which makes the tool that consumes
vendomat the most stale consumer in the fleet.

### What is deployed

Both machine modules are live and match their pins exactly, verified by
evaluation rather than inference:

```
vendomat v0.4.1 → /nix/store/7azcp47xhrfawzsngx65mvpygk9a5m72-vendomat-0.4.1        MATCH
repoman  v0.8.1 → /nix/store/12gznckrvzxr8wrlix6fh89x90adm4ya-repoman-module        MATCH
```

System generation 119. `devman doctor` exits 0 with 6 findings, down from 8;
the vendomat local-source finding cleared. Fleet link sweep: 47 ok, 1
pre-existing `image-gen-pipeline` refusal. Plane invariants show **no drift** —
generation 3, 48 projects, 152 DAGs, `dagu_digest sha256:d3bbe557…`.

### Three repositories run with no manager commands

`llgym`, `nix-secrets`, `image-gen-pipeline` resolve `cliProvider = "store"`
with `REPOMAN_TOOLCHAIN_BIN` unset. Measured inside `llgym`:

```
PROVIDER=store   TOOLCHAIN=[]   MANAGERS=copy git test
gitman MISSING   copyroom MISSING   repoman MISSING   testee MISSING
```

`enterShell` warns to stderr and continues by design, so `devenv shell` exits 0
and the roster still populates. **This is charter property 4**: the run reports
success and the result is wrong.

It is **not** a 039 regression. All three consumed repoman through an unpinned
`git+file:` input resolving live against its working tree, where the
`cliProvider` default flipped `venv` → `store` on 2026-09-08 (`79db869`). None
declares vendomat, so nothing supplies the closure. They have been broken since
a week before this project started. 039 did not cause it and did not detect it —
the `v0.8.1` acceptance checked that `REPOMAN_MANAGERS` was populated, which it
was, rather than that a manager resolves.

### The manifest gap this exposed

`REPOMAN_PROMPT.md` §2.1 required the `cliProvider` opt-out move into
`.repoman/project.toml`. **That was not implemented.** The shipped parser
accepted two fields only:

```nix
manifestKnownFields = [ "schema" "managers" ];   # unknown fields throw
```

So the ten opt-out repositories still hold the value in `devenv.nix`, in the
option documented as removable "in one release". Withdrawing it would put all
ten into the state the three repositories above are already in.

**Fixed in repoman `v0.8.2`** (`ef8c69a`): `manifestKnownFields` gains
`cliProvider`, `allCliProviders` is shared by the validator and the option enum
so the two cannot disagree, and `checks.repoman-consumer-module` now evaluates
the real module against two fixture roots — one with no manifest (asserts
`store` and the default roster), one carrying the opt-out (asserts `venv`).

### Ordering constraint — measured, not assumed

A manifest carrying `cliProvider` **must not land before `v0.8.2` is
deployed**. The evaluation is lazy, so the throw does not fire on
`config.repoman.cliProvider`; it fires as soon as `managers` is forced, which
every real shell does. Proved against the deployed `v0.8.1`:

```
error: repoman: …/manifest-venv/.repoman/project.toml has unknown field(s): cliProvider
```

### The vendomat.toml trap — confirmed live

Writing `vendomat.toml` into a consumer installs a **pre-push git hook** on its
next shell entry. `publish.enable` defaults to `true` and the gate is file
presence, in the v0.3.7 module those repositories pin *and* in the v0.4.1
machine module:

```nix
(lib.mkIf cfg.publish.enable {
  enterShell = ''if [ -f vendomat.toml ]; then ${vendomatCli}/bin/vendomat install-hook; fi'';
})
```

Neither prompt mentions this. Write `[vendor.publish] enable = false` alongside
the toolchain opt-out, or migrate the gate off file presence. Do not write the
twelve manifests ahead of the migrations.

### Central overlay — the largest operational risk

`~/.config/devman` was on a **detached HEAD**, 27 commits ahead of `main` with
none on any branch, 90 uncommitted entries including every migrated repository's
repoman import line, and **no git remote**. The machine-side half of the
migration exists only in an unbacked working tree. `main` is a strict ancestor,
so the repair is `git branch -f main HEAD && git checkout main`, then commit.

**Not repaired in this session** — the ref update was refused by the harness
permission layer. It remains the first thing to fix.

## Stage 3 — 2026-09-16: the manifest gap closed, and ten of fifteen migrated

### repoman v0.8.2 — `cliProvider` gains a manifest home

`manifestKnownFields` now accepts `cliProvider`, validated against
`allCliProviders`, which the option's enum shares so the validator and the
option can never disagree. `checks.repoman-consumer-module` evaluates the real
module against two fixture roots: one with no manifest, asserting `store` and
the default roster; one carrying the opt-out, asserting `venv` and
`[copy git]`. The second assertion is what proves the manifest path.

`tests/test_modules_nix.py` was updated, not deleted. Both original guarantees
survive — the enum holds both values, the default is still `store` — and a new
test asserts the manifest can carry the opt-out.

Deployed: system generation built from `nix-meta` at `repoman v0.8.2`, verified
byte-identical to the closure built before the switch.

### The three repositories with no manager commands — fixed

`llgym`, `nix-secrets` and `image-gen-pipeline` each took
`cliProvider = "venv"` in `.repoman/project.toml`. Verified by checking that a
manager **resolves on PATH**, not merely that `REPOMAN_MANAGERS` is populated —
the check whose absence let this defect survive a release:

```
llgym               venv  gitman|copyroom|repoman -> ~/.local/share/repoman/venv/bin
nix-secrets         venv  gitman|copyroom         -> same
image-gen-pipeline  venv  gitman|copyroom|repoman -> same
```

### Vendomat phase 3 — ten of fifteen

| Repository | Shape | Proof |
|---|---|---|
| flora-qc | no options | toolchain still resolves to `repoman-toolchain-core` |
| tyo3 | store toolchain | `python` still resolves to the PROJECT venv, not the toolchain venv |
| shellij, argentic, eventic, flora, loci.nvim, poddantic, pyllij | opt-out pair | `PROVIDER=venv`, `REPOMAN_TOOLCHAIN_BIN` unset, gitman from the shared venv |
| repoman | vendor + editable | `UV_FIND_LINKS` at the wheelhouse; `repoman` resolves to this checkout, not a release |

Each opt-out repository carries **both** halves in tracked manifests —
`[toolchain] enable = false` in `vendomat.toml`, `cliProvider = "venv"` in
`.repoman/project.toml` — because both option defaults point the other way.

**Every `vendomat.toml` written also sets `[vendor.publish] enable = false`**,
and each repository was checked for `.git/hooks/pre-push` afterwards. None was
installed. Without that line the module writes one into every repository that
gains a manifest.

Plane invariants were identical before and after every migration: pointer
`generations/3`, 48 projects, DAG digest `395882db05afe769…`. `devman doctor`
exits 0 with the same 6 findings as the baseline. Fleet link sweep: 47 ok, the
same single pre-existing `image-gen-pipeline` refusal.

### Five repositories NOT migrated, and the reason is one shared fault

`flora-core`, `nix-nvim`, `paloma-text-pipeline`, `loci-core` and `nix-paseo`
each carry an **uncommitted, unlanded Project 038 devman-consumer migration** in
the working tree — the `devman` input and the `devman = { … }` option block
removed, `.devman/project.toml` added, and in flora-core's case the repoman pin
rewritten too. `paloma-text-pipeline` additionally holds 67 file deletions under
`experiments/diffusion/` and `docker/`.

Adopting any of that into a vendomat lane would bury someone's in-flight work in
an unrelated commit, so none was touched. **Land or abandon the 038 work in
those five first; the vendomat migration is a small change on top of a clean
tree.** Three of them — flora-core, nix-nvim, paloma-text-pipeline — also still
pin repoman at `57473ad`, which predates v0.8.2 and rejects `cliProvider` as an
unknown manifest field, so their `cliProvider` line must stay in `devenv.nix`
until that pin is removed.

### Central overlay — rescued

`~/.config/devman` was on a detached HEAD with 27 off-branch commits, 90
uncommitted entries and no remote. `main` was a strict ancestor, so `git branch
-f main HEAD` recovered it without rewriting anything. The 90 entries landed in
five themed commits rather than one blob. It still has **no git remote** — the
one piece of this plane with no off-machine copy.

### A hazard worth recording

A helper that inserted the vendomat import after the first matching line broke
`repoman`'s central file, whose `imports` were on a single line:

```nix
imports = [ /run/current-system/sw/share/devman/link-module.nix ];
  /run/current-system/sw/share/vendomat/consumer-module.nix   # syntax error
```

31 of 51 central files still use the single-line form. `nix-instantiate --parse`
over every central file is a cheap gate and caught it immediately.
