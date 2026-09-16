# Kickoff prompt — remove vendomat from per-repo pins

Run this in `~/Documents/Projects/vendomat`. Paste from the horizontal rule down.

---

You are implementing **Project 039, the vendomat half**: remove vendomat from
every consumer repository's version pin, using the pattern devman's Project 038
already proved and deployed.

## 0. Read these before you change a line

All paths are under `~/Documents/Projects/devman/.scratch/projects/038-devman-plane-redesign/`:

| Document | Read for |
|---|---|
| `CONSUMER_MIGRATION_GUIDE.md` | the per-repo runbook you will copy, §1, §7–§12, and the failure table at :624-635 |
| `IMPLEMENTATION_LOG.md` :785-812 | the pin-removal probe that was **run against vendomat itself** and failed. Read this first. |
| `CONCEPT.md` §10, §13.5, §13.7 | component ownership and the rules a plane update must not break |
| `IMPLEMENTATION_GUIDE.md` §11 | the removal ordering discipline |

Also read, in this repo: `AGENTS.md`, `README.md` §"the four faces",
`.scratch/projects/03-shared-repoman-toolchain/CONCEPT.md` §6 and §8.2, and
`.scratch/projects/06-generic-vendor-manager/DESIGN.md` §2–§3.

And in devman: `nix/link-adapter.nix`, `nix/nixos-module.nix:698-710`, and
`modules/link.nix`. Those three files **are the pattern**. You are building the
vendomat equivalent of them.

## 1. The measurement, dated 2026-09-15

Sixteen live repositories declare vendomat. Fourteen import `vendomat/modules`.
Two distinct revisions are pinned (`511e70f` at `v0.3.9`, `b40d59f` at `v0.3.7`),
six consumers use an unpinned `git+file:///home/andrew/...` input, and **zero
repositories are at HEAD**. The worst is 24 commits behind.

What those fourteen importers actually use:

| Option | Repos setting it |
|---|---:|
| `vendor.toolchain.enable = false` | 10 — **`false`, not `true`. The default is `true`.** Deleting the line turns the store toolchain ON. Preserve it as `[toolchain] enable = false`. The same ten also set `repoman.cliProvider = "venv"`; that is one coherent opt-out pair and both halves must survive. |
| `vendor.enable`, `vendor.libs`, `vendor.toolchain.mode` | 1 (vendomat's own consumer, repoman) |
| `knowledge.enable` | 1 (loci-core) |
| `vendor.self`, `vendor.noBuild`, `vendor.sharedCargo`, `vendor.publish.enable`, `knowledge.skillsDir` | **0** |

`nix-paseo` declares the input and never imports the module. That is a dead
input; delete it and take no other action there.

**Verify these numbers yourself before you act.** They are three days old by the
time you read them, and a stale count that drives a delete is the failure mode
this plane exists to prevent.

## 2. Blocking precondition — cut `v0.4.0` first

`git describe origin/main` reports `v0.3.9-19-g<sha>`. The tag `v0.3.9` points at
`511e70f`, which predates every line of `src/vendomat/plane.py`. It has no `plane`
subcommand, no `devman-plane` flake output, and no
`VENDOMAT_DEVMAN_PLANE_MANIFEST` wrapper.

`nix-meta/flake.nix` locks that tag. Every consumer pin points at a pre-plane
vendomat. The running plane on this machine was therefore driven from a working
tree or an override, not from the pinned closure.

**Do this before Phase 1 and stop if it does not pass:**

```bash
cd ~/Documents/Projects/vendomat
devenv shell -- testee verify --mode quick
VENDOMAT_E2E=1 devenv shell -- testee verify --mode quick
devenv shell -- nix build .#repoman-toolchain-core --no-link --print-out-paths
devenv shell -- nix build .#devman-plane --no-link --print-out-paths
gitman release            # verify gate is testee verify --mode ci, 1800s timeout
```

Then bump `nix-meta/flake.nix` to the new tag, `nix flake lock --update-input
vendomat`, `nixos-rebuild build`, and run `nix-meta/scripts/repoman-toolchain-test`
(14 checks against the live login shell). All 14 must pass.

Record the tag, the `devman-plane` store path, and the toolchain digest. You will
compare against them at the end.

## 3. The target state

### Before — what a consumer declares today

`devenv.yaml`:
```yaml
inputs:
  vendomat:
    url: "git+https://github.com/Bullish-Design/vendomat?ref=refs/tags/v0.3.7"
    flake: true

imports:
  - vendomat/modules
```

`devenv.nix`:
```nix
  vendor.toolchain.enable = false;      # ten repos — an opt-OUT, not an opt-in
  repoman.cliProvider = "venv";         # the matching half of the same opt-out
```

`devenv.lock`: a `"vendomat"` node plus the root edge `"vendomat": "vendomat"`.

### After — what a consumer declares

Nothing. No input, no import, no option block, no lock node.

Repository-scoped configuration that genuinely varies moves into the repo's
existing `vendomat.toml`, which is already a tracked publish manifest:

```toml
[toolchain]
mode = "editable"      # repoman only — it feeds the roster it would otherwise consume
```

```toml
[knowledge]
enable = true          # loci-core only
```

Eleven repositories need no file at all, because importing the module was already
the opt-in (`README.md:33-36`: *"importing Vendomat IS the opt-in"*). Keep that
property: the machine-delivered module is active for every repository that has a
central overlay declaration, and does nothing measurable for a repository that
sets no options.

### The delivery path that replaces the pin

Copy devman's link-adapter shape exactly, because its two failure modes are
already recorded and fixed:

1. **A package that installs the module into `share/`.** Follow
   `devman/nix/link-adapter.nix`:
   ```nix
     postInstall = ''
       install -Dm644 modules/devenv.nix "$out/share/vendomat/consumer-module.nix"
     '';
   ```
2. **A NixOS module that puts it in the system profile.** Vendomat has no
   `nixosModules` output today; add one, mirroring
   `devman/nix/nixos-module.nix:698-710`. **The `pathsToLink` line is not
   optional** — NixOS links selected `share` subtrees, not all of `/share`.
   Devman's first switch shipped the binary without the module path and a
   consumer could not import it (038 Stage 18 follow-up). Do not re-learn this:
   ```nix
     environment.pathsToLink = lib.mkIf cfg.installConsumerModule [ "/share/vendomat" ];
   ```
3. **`nix-meta` imports the module.** One pin, in one place, replacing sixteen.
4. **The central overlay carries the import.** Each repository's
   `~/.config/devman/projects/<project>/devenv.local.nix` gains one line:
   ```nix
     imports = [
       /run/current-system/sw/share/devman/link-module.nix
       /run/current-system/sw/share/vendomat/consumer-module.nix
     ];
   ```
   That file already reaches every repository as a symlink through devman's link
   plane, which is deployed and working. **This is why the work is cheap:** you
   are adding one line to fourteen central files, not building a new delivery
   mechanism.

The module must resolve its own settings without a repo-side `vendor.*` option
block. Read `vendomat.toml` from `config.devenv.root` with `builtins.fromTOML`,
exactly as `devman/modules/link.nix` reads `.devman/project.toml`. Absent file
means all defaults.

## 4. Traps the 038 log already paid for

**Read `IMPLEMENTATION_LOG.md:785-812` first.** The pin-removal probe was run
against this repository and it failed at Nix evaluation with `attribute 'devman'
missing`, because the machine-local overlay still read `config.devman.project`
to build its link declarations. The consumer-side removal and the central-side
conversion are **one transition**, not two.

Before you touch anything, run the analogous check:

```bash
grep -rn 'config\.vendor\|config\.knowledge\|vendor\.toolchain' \
  ~/.config/devman/projects/ ~/Documents/Projects/nix-meta/ 2>/dev/null
```

Anything that reads `config.vendor.*` from outside a consumer repo is a
`attribute 'vendor' missing` waiting to happen.

Five more, each with a named source:

| Trap | Why it bites | Source |
|---|---|---|
| Duplicate option declaration | importing the machine module while the repo still imports `vendomat/modules` declares `options.vendor` twice; evaluation fails | 038 guide §1 |
| `test_fleet_shape.py` | refuses `/home/<user>/` in `flake.nix`, refuses `file:///home/...` anywhere in `flake.lock`, and requires every first-party input to be `refs/tags/` with a locked rev. *"Vendomat is the ROOT of the chain, so this guard has no transitive exemption."* | `tests/test_fleet_shape.py` |
| Measuring from a repo shell | devman's Stage 50 acceptance reported `mode compatibility` purely because a project venv sat ahead of `/run/current-system/sw/bin`. Measure from `/tmp` with `env -u PYTHONPATH -u NIX_PYTHONPATH` | 038 Stage 50 |
| direnv | re-enters the shell and repairs a broken link before your explicit entry runs, so a broken state reads as healthy | 038 Stage 16 |
| The bootstrap rule | the `vendomat` binary and the `devman-plane` closure are **the same artifact** (`flake.nix:232-238`). The plane must never become the delivery channel for the binary that operates the plane. Keep the binary coming from Nix and only the registry from the plane. | `flake.nix`, 038 §12.6 |

Also keep vendomat's own dev shell free of vendomat. `devenv.nix:7-9` records that
it *"imports nothing from vendomat's own consumer module"*. That is the cleanest
bootstrap property in the repo. Do not spend it.

## 5. Phases

### Phase 1 — package and install the module

1. Add the `share/vendomat/consumer-module.nix` install to the vendomat package.
2. Add `nixosModules.default` with `installConsumerModule` (default `true`) and
   the `pathsToLink` entry.
3. Add a flake check in the shape of devman's `link-adapter` check: assert
   `nix-instantiate --eval --strict --expr "builtins.functionArgs (import
   $out/share/vendomat/consumer-module.nix)"` succeeds, and that the module
   evaluates against a fixture repository with no `vendomat.toml`.
4. Tag, bump `nix-meta`, `nixos-rebuild boot`, then `switch`.
5. Prove the machine boundary:
   ```bash
   test -f /run/current-system/sw/share/vendomat/consumer-module.nix
   readlink -f /run/current-system/sw/share/vendomat/consumer-module.nix
   ```
   **Do not migrate a single repository before this passes.**

### Phase 2 — make the module manifest-driven

Replace every `config.vendor.*` read with a value resolved from `vendomat.toml`
under `config.devenv.root`, defaulting when the file is absent. Keep the option
declarations for one release as a compatibility fallback, with the devman
comment discipline: *"the fallback keeps the migration reversible without making
the compatibility option part of the new interface."*

Write `vendomat.toml` for the two repositories that need one (repoman:
`mode = "editable"`; loci-core: `knowledge.enable = true`) **before** removing
their inputs.

### Phase 3 — migrate the fourteen, one lane each

Per repository, in this order, with **both halves in one transition**:

```bash
export P=<project>
export R=~/Documents/Projects/$P
export CENTRAL=~/.config/devman/projects/$P/devenv.local.nix

cd "$R" && gitman status && gitman start 039-vendomat-depin-"$P"
```

Detached HEAD → stop and resolve branch ownership. Do not process two consumers
in one lane or one commit.

1. **Central**: add the `consumer-module.nix` import line to `$CENTRAL`.
2. **`devenv.yaml`**: delete the `vendomat:` input block and the
   `- vendomat/modules` import line. Nothing else.
3. **`devenv.nix`**: delete the `vendor.*` / `knowledge.*` block. Keep all tasks.
4. **`devenv.lock`**: delete the `"vendomat"` node and the root edge
   `"vendomat": "vendomat"` only. Inspect the diff — devenv normalises unrelated
   entries. If the lock is git-ignored, re-lock locally and stage nothing.

Then verify, stopping at the first new failure:

```bash
cd "$R"
devenv shell -- true
grep -rn 'vendomat\|vendor\.' devenv.yaml devenv.nix
devenv tasks run -v base:check
devenv tasks run -v base:test

cd /tmp
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link status \
  --project "$P" --root "$R" --overlay "$HOME/.config/devman"   # exit 0, five ok states
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
```

Plane invariants must be **identical** before and after. Record them at the start
of the session and re-check after each repository:

```bash
PLANE="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE"
find -L "$PLANE/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE/dags" -type f -name '*.yaml' -exec sha256sum {} + | sort | sha256sum
```

Generated plane count or digest changed → **stop**. A consumer migration must
never activate or rewrite plane state.

Save with `gitman save -m "refactor: remove vendomat consumer integration"` then
`gitman publish`. Commit the central declaration separately in `~/.config/devman`.
Append a dated stage entry to this project's log.

Suggested order — the two that carry configuration last, so the simple cases
prove the mechanism first:

`nix-paseo` (dead input, delete only) → `shellij` → `poddantic` → `pyllij` →
`eventic` → `flora-core` → `argentic` → `flora-qc` → `paloma-text-pipeline` →
`tyo3` → `flora` → `loci.nvim` → `nix-nvim` → `loci-core` → `repoman`.

### Phase 4 — collapse the remaining pins

After the fourteen, exactly two vendomat pins should remain, and both are correct:

- `nix-meta/flake.nix` — the machine pin. This is the one that replaced sixteen.
- vendomat's own `flake.nix` `devman` input — **keep it permanently.** 038 Stage
  39 is explicit: *"that is Vendomat packaging Devman, not Vendomat consuming the
  module."* The repository that builds the plane must pin the plane, or the
  generation becomes `PATH`-dependent instead of reproducible.

Then clean the three stale devman lock entries this work will surface:
`nix-meta`'s `devenv.lock` still holds `devman` at `v0.4.0`, `nix-terminal`
floats `devman` on `main` at a 2026-01-01 timestamp, and `pydantree` has an
orphan `devman` path node its `devenv.yaml` does not declare. Leave `forgelab`
and `lodestar` alone — both are in the archive set.

### Phase 5 — the carry-forward defect (separable; do it, but in its own lane)

This is the fleet-inventory gap, and it lives in this repository.

`vendomat plane update` takes its project set from argv and nothing else.
`store.build()` stages into a fresh `mkdtemp` and writes only the bundles passed
on **this** invocation. A project omitted from argv is **silently dropped** from
generation N+1. Evidence: `~/.local/state/devman/projects/` holds three entries
while the active generation holds forty-six, because the fleet was passed as
forty-six `--project-root` flags.

Fix it by seeding the project set from the active generation's own `projects/`
directory when no explicit selection is given, and require an explicit `--prune
<name>` to remove a project. Borrow the three-way classification from the
archived fleetman's `plan_sync` (`~/Documents/Projects/.archive/fleetman/src/fleetman/sync.py`):

| State | Meaning | Action |
|---|---|---|
| declared, in active | carry forward | re-inspect; copy bundle if unchanged |
| declared, not in active | new | render |
| **in active, not declared** | **unmanaged** | **surface it and never drop it silently** |

That third row is the property the argv interface lacks.

Separately: `generations/` has no retention or garbage collection. Add a
`--keep N` with a default that retains at least the active generation and its
immediate predecessor, so rollback stays possible.

## 6. The gate

```bash
devenv shell -- testee verify --mode quick
VENDOMAT_E2E=1 devenv shell -- testee verify --mode quick
devenv shell -- nix build .#repoman-toolchain-core --no-link --print-out-paths
```

Plus, from `~/Documents/Projects/devman`:

```bash
devman doctor      # must exit 0 or keep exactly its known findings; no new finding
```

And the fleet sweep, from `/tmp`, environment cleared:

```bash
for d in "$HOME/.config/devman/projects"/*/; do
  p=$(basename "$d"); r="$HOME/Documents/Projects/$p"
  [ -d "$r" ] || continue
  env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
    status --project "$p" --root "$r" --overlay "$HOME/.config/devman" >/dev/null 2>&1
  printf '%s %s\n' "$?" "$p"
done | sort | uniq -c -w2
```

A new refusal is a regression. Diagnose it before removing anything else.

## 7. Do not

- Do not start a pinning campaign. This project deletes inputs; the six unpinned
  `file://` consumers are fixed because the input disappears, not because you
  pinned them.
- Do not remove vendomat's `devman` flake input. It is the packager's pin.
- Do not make the plane the delivery channel for the vendomat binary.
- Do not run `vendomat plane update` during a consumer migration.
- Do not add a `product` other than `devman` to the plane. The
  `product != "devman"` guard appears in five places and a second product means a
  second state root and a second renderer contract. Delivering repoman "the
  toolchain way" is already done.
- Do not remove a compatibility fallback because one canary passed.
