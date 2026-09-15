# Kickoff prompt — remove repoman from per-repo pins

Run this in `~/Documents/Projects/repoman`. **Do the vendomat half first**
(`VENDOMAT_PROMPT.md`): vendomat's module supplies `REPOMAN_TOOLCHAIN_BIN`, and
repoman's module fails loudly without it. Paste from the horizontal rule down.

---

You are implementing **Project 039, the repoman half**: remove repoman from every
consumer repository's version pin, using the pattern devman's Project 038 proved
and vendomat's half of 039 just repeated.

## 0. Read these before you change a line

Under `~/Documents/Projects/devman/.scratch/projects/038-devman-plane-redesign/`:

| Document | Read for |
|---|---|
| `CONSUMER_MIGRATION_GUIDE.md` | the per-repo runbook, §1, §7–§12, and the failure table at :624-635 |
| `IMPLEMENTATION_LOG.md` :785-812 | the probe that failed because a machine-side file read a consumer option |
| `IMPLEMENTATION_GUIDE.md` §11 | the removal ordering discipline |

Under `~/Documents/Projects/devman/.scratch/projects/039-tool-depinning/`:
`VENDOMAT_PROMPT.md`, and the stage log the vendomat half produced.

In devman: `nix/link-adapter.nix`, `nix/nixos-module.nix:698-710`,
`modules/link.nix`. Those three files are the pattern.

In this repo: `README.md`, `AGENTS.md`, `CONCEPT.md` §"Primary form",
`modules/devenv.nix` (all 225 lines), `modules/managers/*.nix`,
`modules/scripts/repoman-sync.sh`, and
`.scratch/projects/12-toolchain-single-instance/PROGRESS.md`. **Project 12 is
your own precedent** — it already deleted `repoman.lock` from fifteen consumers
and moved the CLI managers into one machine venv. This project finishes the same
move for the module.

## 1. The measurement, dated 2026-09-15

Twenty-five live repositories declare repoman. Twenty-three import the
meta-module. Three distinct revisions are pinned, eleven consumers use an
unpinned local `file://` or `path:` input, and **zero repositories are at HEAD**.

| Pinned rev | Ref | Date | Repos | Behind HEAD |
|---|---|---|---:|---|
| `57473ad4` | `main` | 2026-09-12 | 10 | 4 commits / 2d 22h |
| `cd34bfd4` | `v0.7.5` | 2026-09-07 | 3 direct + 13 transitive | 14 commits / 7d 16h |
| `a83b571d` | `v0.7.1` | 2026-08-25 | 1 (agentman) | 38 commits / 21d 21h |

**Ten repositories bind repoman twice at once** — `57473ad4` from their own
`devenv.yaml`, and `cd34bfd4` as the `repoman_2` node vendomat's flake drags in.
That diamond is the sharpest edge in the current graph. Removing the direct pin
collapses it to one revision, owned by the machine.

What the twenty-three importers actually use:

| Option | Repos setting it | Note |
|---|---:|---|
| `repoman.managers` | 23 | genuinely varies — four rosters in play |
| `repoman.enable` | 22 | becomes implicit |
| `repoman.cliProvider` | 10 | **all ten set `"store"`, which is already the default.** Delete the lines; change nothing. |
| `repoman.nativeBuild` | 1, commented | tyo3 |
| `repoman.template`, `toolchainBin`, `installSkills`, `skillsDir` | **0** | dead option surface |

Roster distribution: `[copy git test]` × 15, `[copy git]` × 6 (the nix repos,
which have no Python tests), `[git]` × 1 (tyo3), `[copy git test doc]` × 1
(repoman itself).

**Verify these numbers before you act.** They are days old by the time you read
them.

## 2. The target state

### Before

`devenv.yaml`:
```yaml
inputs:
  repoman:
    url: "git+https://github.com/Bullish-Design/repoman?dir=modules&ref=refs/tags/v0.7.1"
    flake: false

imports:
  - repoman
```

`devenv.nix`:
```nix
  repoman.enable = true;
  repoman.managers = [ "copy" "git" "test" ];
  repoman.cliProvider = "venv";     # in ten repos, redundantly naming the default
```

`devenv.lock`: a `"repoman"` node plus the root edge.

### After

`devenv.yaml` and `devenv.nix`: nothing. `devenv.lock`: the direct node and root
edge gone; leave `"repoman_2"` alone — vendomat owns it.

The roster, which genuinely varies, moves to a new tracked manifest at the
repository root, `.repoman/project.toml`:

```toml
schema = 1
managers = ["copy", "git"]
```

Default it to `["copy", "git", "test"]` so fifteen of twenty-three repositories
need **no file at all**. Only the eight exceptions carry one. Model the schema on
`devman/src/devman_contract/manifest.py`: a fixed field set, unknown fields
rejected outright, values validated against the identity grammar, and a
path-independent digest. Copy that file's discipline; do not improvise a parser.

### The delivery path

Identical to the vendomat half:

1. **Install the module into `share/`.** Follow `devman/nix/link-adapter.nix`:
   ```nix
     postInstall = ''
       mkdir -p "$out/share/repoman"
       cp -r modules/. "$out/share/repoman/module/"
     '';
   ```
   Copy the whole `modules/` tree, not one file — `modules/devenv.nix` imports
   `managers/*.nix` and `scripts/repoman-sync.sh` by relative path.
2. **A NixOS module** with `installConsumerModule` and
   `environment.pathsToLink = [ "/share/repoman" ]`. **The `pathsToLink` line is
   not optional.** Devman's first switch shipped the binary without the module
   path and consumers could not import it (038 Stage 18 follow-up).
3. **`nix-meta` imports it.** One pin replacing twenty-five.
4. **The central overlay carries the import.** Each repository's
   `~/.config/devman/projects/<project>/devenv.local.nix` gains one line:
   ```nix
     imports = [
       /run/current-system/sw/share/devman/link-module.nix
       /run/current-system/sw/share/vendomat/consumer-module.nix
       /run/current-system/sw/share/repoman/module/devenv.nix
     ];
   ```
   That file already reaches every repository through devman's link plane.

The module resolves the roster from `.repoman/project.toml` under
`config.devenv.root`, exactly as `devman/modules/link.nix` reads
`.devman/project.toml`. Absent file means the default roster.

## 3. Four traps specific to repoman

### 3.1 The transitive module imports — verify this before Phase 1

`modules/devenv.nix:76` does:
```nix
  ++ lib.optional (inputs ? shellij) (inputs.shellij + "/modules/devenv.nix")
```
and `modules/managers/docman.nix:29` does the same for docman. Repoman's module
**imports two other repositories' modules on the consumer's behalf**, reading the
consumer's `inputs`.

When the module is imported from an absolute machine path rather than from an
input, confirm by experiment whether `inputs` still resolves to the consumer's
devenv inputs in that scope. Write a throwaway fixture consumer under `/tmp` that
declares a `shellij` input and imports the module by absolute path, and evaluate
it. **Do not assume either answer.** If `inputs` does not reach the machine
module, the shellij and docman imports must move to the consumer's own
`devenv.yaml` before any migration — which is a larger change and should be its
own phase.

This is the repoman equivalent of the `attribute 'devman' missing` failure that
stopped 038's first probe. Find it in a fixture, not in a real repository.

### 3.2 The pre-push fleet-lock gate will fire

`.pyjutsu-hooks.toml` runs `scripts/check-fleet-lock.py` on every push. It refuses
a push whose `devenv.lock` names `/home/<user>/` anywhere in the node graph.
Every lock edit in this project touches that file. Expect the gate; fix by
`relock`, never by `--no-verify`.

### 3.3 The tests encode the consumption surface you are deleting

These will fail and must be edited deliberately, not deleted to go green:

| Test file | What it asserts |
|---|---|
| `tests/test_fleet_shape.py` | `test_the_self_input_is_a_path_not_a_git_url` asserts the literal `url: "path:./modules"` |
| `tests/test_modules_nix.py` | 19 tests over `enterShell` PATH order, `cliProvider` default `store`, `toolchainBin` resolution, the store-mode `:?` failure |
| `tests/test_toolchain_coherence.py` | 13 tests over `repoman-sync --machine` |
| `tests/consumer-example/` | a full copy of the consumption surface — update it to the new shape, and it becomes your fixture for 3.1 |

`tests/test_modules_nix.py` is the one that matters: it is the only thing proving
the PATH-prepend order, and that order is load-bearing (`modules/devenv.nix:191-196`).
Keep every assertion; change only how the module is reached.

### 3.4 The router skill is tracked in 21 of 22 consumers

`.agents/skills/repoman/SKILL.md` is generated by `repoman install-skills` and
`docs/AGENT-FILES.md` says it *"must never be redistributed as a static copy"* —
yet `git ls-files` finds it committed in nearly every consumer.

Apply devman's boundary test (`devman/CLAUDE.md` property 10): would this file
still be true for someone else who cloned the repository? It is generated agent
surface whose content depends on the machine's roster, so **no**. It belongs in
the central overlay, reaching the repository as a symlink with its own
`.git/info/exclude` line — which is exactly where `.agents/` already goes. The
exclude file is already owned by `devman_link/excludes.py`; add the entry there,
do not hand-edit `.git/info/exclude`.

Do this as its own phase, after the pins are gone. Untracking a file in
twenty-one repositories is separable work and mixing it with the pin removal
makes every diff unreadable.

## 4. Phases

### Phase 0 — the fixture experiment

Resolve trap 3.1 before anything else. Build the `/tmp` fixture, evaluate it, and
record the answer in the stage log. If `inputs` does not reach the module, stop
and re-plan: the shellij and docman imports become a prerequisite phase.

### Phase 1 — package and install the module

1. Install `modules/` into `$out/share/repoman/module/`.
2. Add `nixosModules.default` with `installConsumerModule` and the `pathsToLink`
   entry.
3. Add a flake check in the shape of devman's `link-adapter` check: assert the
   module file exists, that `builtins.functionArgs (import …)` evaluates, and
   that a fixture consumer with no `.repoman/project.toml` gets the default
   roster.
4. Tag, bump `nix-meta`, `nixos-rebuild boot`, then `switch`.
5. Prove the boundary:
   ```bash
   test -f /run/current-system/sw/share/repoman/module/devenv.nix
   readlink -f /run/current-system/sw/share/repoman/module/devenv.nix
   ```
   **Migrate nothing until this passes.**

### Phase 2 — make the module manifest-driven

Add `.repoman/project.toml` parsing with the default roster
`["copy", "git", "test"]`. Write the manifest into the eight repositories whose
roster differs, **before** removing their inputs:

- `[copy git]`: `forgelab`, `loci.nvim`, `nix-desktop`, `nix-nvim`, `nix-paseo`,
  `nix-secrets`
- `[git]`: `tyo3`
- `[copy git test doc]`: `repoman` itself

Keep the `repoman.*` options for one release as a compatibility fallback, with
devman's comment discipline: *"the fallback keeps the migration reversible
without making the compatibility option part of the new interface."*

Delete the four dead options (`template`, `toolchainBin` as a public name,
`installSkills`, `skillsDir`) in a separate commit, with the measurement that no
repository sets them.

### Phase 3 — migrate the twenty-three, one lane each

Per repository, **both halves in one transition**:

```bash
export P=<project>
export R=~/Documents/Projects/$P
export CENTRAL=~/.config/devman/projects/$P/devenv.local.nix

cd "$R" && gitman status && gitman start 039-repoman-depin-"$P"
```

Detached HEAD → stop. One repository per lane, per commit. Seven repositories
were parked on detached HEAD during 038 (`gitman`, `image-gen-pipeline`, `llgym`,
`loci-core`, `nix-paseo`, `pydantree`, `pyjutsu`); expect some still are.

1. **Central**: add the module import line to `$CENTRAL`.
2. **`devenv.yaml`**: delete the `repoman:` input block and the `- repoman`
   import line.
3. **`devenv.nix`**: delete the `repoman.*` block. Keep all tasks. If a `base:*`
   task chains `after` a `repoman:*` task, keep the chain — the task names do not
   change.
4. **`devenv.lock`**: delete the `"repoman"` node and the root edge
   `"repoman": "repoman"`. **Leave `"repoman_2"`** — vendomat's flake owns it.

Verify, stopping at the first new failure:

```bash
cd "$R"
devenv shell -- true
grep -rn 'repoman' devenv.yaml devenv.nix
devenv tasks run -v base:check
devenv tasks run -v base:test
repoman doctor                       # exit 0; the toolchain must still resolve

cd /tmp
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link status \
  --project "$P" --root "$R" --overlay "$HOME/.config/devman"
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman doctor
```

Then the plane invariants — pointer, project count, DAG digest — **identical**
before and after. Any change means the migration touched plane state: stop.

Suggested order, simplest first so the mechanism proves itself before the hard
cases:

`agentman` (single pin, no vendomat) → `talkee` → `nix-secrets` → `nix-desktop` →
`inferference` → `llgym` → `image-gen-pipeline` → `shellij` → `poddantic` →
`pyllij` → `eventic` → `flora-core` → `argentic` → `flora-qc` →
`paloma-text-pipeline` → `loci.nvim` → `nix-nvim` → `nix-paseo` → `flora` →
`tyo3` → `nix-terminal` (flake input, its own `modules/repoman.nix` wrapper —
treat separately) → `repoman` itself.

Leave `forgelab` and `lodestar` alone. Both are in the archive set.

### Phase 4 — collapse the remaining pins

After the twenty-three, exactly three repoman references should remain:

- `nix-meta/flake.nix` — the machine pin, replacing twenty-five.
- `vendomat/flake.nix:42-43` — the packager's pin, which builds
  `repoman-uv2nix-cli` for the roster. **Keep it.** The repository that builds the
  toolchain must pin the toolchain.
- `repoman/devenv.yaml` `path:./modules` — the self-host. Keep it, for the same
  reason devman keeps `- ./modules`: *"this repository is the plane, so there is
  no rev to pin against itself."* Update `tests/test_fleet_shape.py`'s
  `test_the_self_input_is_a_path_not_a_git_url` to match whatever shape survives;
  do not delete the test.

### Phase 5 — untrack the router skill (separable)

Move `.agents/skills/repoman/SKILL.md` to the central overlay per trap 3.4. One
lane per repository, twenty-one repositories, no other change in the diff.

## 5. The gate

```bash
devenv shell
repoman-sync
devenv tasks run -v base:check      # repoman:lint — ruff check src
devenv tasks run -v base:test       # repoman:test — testee verify --mode quick
repoman doctor --json
```

Release gate: `gitman.toml [publish].verify = ["devenv","shell","testee","verify","--mode","ci"]`.

From `~/Documents/Projects/devman`:
```bash
devman doctor       # exit 0, or exactly its known findings; no new finding
```

And the fleet sweep from `/tmp` with `env -u PYTHONPATH -u NIX_PYTHONPATH`, as in
`VENDOMAT_PROMPT.md` §6. A new refusal is a regression.

Two measurement traps, both already paid for in 038: **direnv re-enters the shell
and repairs a broken link before your explicit entry runs**, and **a repository
shell puts a project venv ahead of `/run/current-system/sw/bin`**. Measure from
`/tmp`, with both Python path variables cleared, every time.

## 6. Do not

- Do not start a pinning campaign. The eleven unpinned `file://` consumers are
  fixed because the input disappears.
- Do not remove vendomat's repoman pin or repoman's `path:./modules` self-host.
- Do not touch `"repoman_2"` in any consumer lock.
- Do not delete a failing test to go green. `tests/test_modules_nix.py` is the
  only proof that the PATH-prepend order holds.
- Do not mix Phase 5 into Phase 3.
- Do not touch `forgelab` or `lodestar`.
- Do not remove a compatibility fallback because one canary passed.
