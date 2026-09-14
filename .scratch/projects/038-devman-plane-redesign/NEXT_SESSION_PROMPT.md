# Clean-session prompt — the §11 removals and the stale-doc sweep

Date written: 2026-09-14
Written after: Project 038 merged to `main` (PR 167, `dc42bfc`), then Stages 39,
40 and 41 (PRs 168, 169, 170).

---

## Your task

Finish the Project 038 §11 removal sequence, and close the documentation that
now describes a world one stage behind the code.

Work one item at a time. Each item lands as its own commit with its own recorded
evidence. **Do not batch the removals**; a removal that drops a test count must
say which tests went and why.

---

## Read these first, in this order

1. `CLAUDE.md` — the ten properties. Rule 1, rule 4 and rule 10 decide most
   arguments before they start.
2. `.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_GUIDE.md` §11 —
   the six-item removal list. Note the numbering: the log calls it "§11", and it
   is the implementation guide's §11, not `CONCEPT.md`'s.
3. `.scratch/projects/038-devman-plane-redesign/REMOVAL_SEQUENCE_PROMPT.md` —
   the gates, the canary, the fleet sweep, and the three traps that let a change
   pass locally and fail hermetically.
4. `.scratch/projects/038-devman-plane-redesign/IMPLEMENTATION_LOG.md`, the last
   four sections (Stages 38 repair, 39, 40, 41) — what just happened and why.
5. `.scratch/projects/025-the-link-plane/CONCEPT.md` §6.2a and Stage 3 — only if
   you reach Wave 3.

---

## Ground truth, measured 2026-09-14

Trust this over any document that contradicts it. Re-measure before you rely on
it; do not copy these numbers into a report.

```text
main                dc42bfc, then PRs 168/169/170 merged
plane               generations/2, 46 projects, 146 DAG files
DAG digest          5acf4cc3be671f7118643e33eb01f37d708ed780ee228027956dce0dcee6022b
dagu ls             147 lines
fleet sweep         47 clean / 2 drift (image-gen-pipeline, lodestar), 0 refusals
doctor              exit 1, four known findings
base:unit           606 passed
```

The four doctor findings are `flora-037-part-e:devenv.local.nix: create`; dirty
and unpinned Vendomat; dirty and unpinned RepoMan; and the unpinned `git+file:`
advice. **Doctor exit 1 is a finding result, not a failure.** Do not repair
unrelated drift.

### Three corrections to older records

1. **`src/devman/watch.py` is free to edit.** Every record that calls it a
   protected file with unrelated worktree changes is stale. Those changes were
   formatter reflows, and they were committed on 2026-09-14 in the Stage 38
   repair. `git status src/devman/watch.py` is clean. **This unblocks two items
   at once** — see Wave 2 item D and Wave 3 item I.
2. **`~/.local/state/devman/` exists.** Link-plane Stage 3 item 1, the `stateDir`
   split, shipped. `~/.local/share/devman/` holds `dags projects watch`;
   `~/.local/state/devman/` holds `projects watch`. Stage 3 item 2, moving
   `registryDir`, did not ship and stays gated.
3. **§11 item 3 is done for every live consumer.** `tyo3` and `repoman` landed on
   2026-09-14. `devman` itself keeps the module by criterion 16 and was never
   item 3 work. Items 2 and 4 sat behind item 3 and **are now unblocked.**

### Two housekeeping steps the operator is running

Do not do these, and do not report them as your work. Check whether they landed
before you measure the plane.

- Removing `~/.local/share/devman/projects/allium-env`, its three generation DAG
  links, and `active/projects/allium-env`. Until then the projection still reads
  46 projects and 146 DAG files.
- Removing `~/.config/devman/projects/lodestar`, after committing its
  materialized agent files.

---

## Wave 1 — cheap, unblocked, currently wrong

Land these first. They cost little and they stop the next reader inheriting a
false statement.

### A. Six documents claim the state root does not exist

Each asserts that `~/.local/state/devman/` is absent or unshipped. It exists.

| File | What it says |
|---|---|
| `CLAUDE.md` / `AGENTS.md` (a symlink) :78-80 | "that directory does not exist yet" |
| `README.md` :285-289 | "does not exist on the current machine" |
| `README.md` :312-314 | "both remain deferred as described in project 029" |
| `AGENTS_GUIDE.md` :149-151 | "is not current and does not exist on this machine" |
| `USER.md` :265-268 | "the state directory is absent on the current machine" |
| `.scratch/projects/029-central-overlay-status/README.md` :255 | "does not exist yet" |

**Replace each with the true split**, which `src/devman/registry.py:8-25` already
states correctly: Stage 3 item 1 (the `stateDir` split) landed and is deployed;
Stage 3 item 2 (`registryDir` moving to `~/.config/devman`) did not, and is
gated on §6.2a. `registry.py:61-73` and `modules/devenv.nix:510-521` hold the
reason. **Cite the measurement, do not restate the plan.**

Rule 2 applies: a change that contradicts a charter changes that document in the
same commit.

### B. Project 038's README still says "Status: proposed concept"

`.scratch/projects/038-devman-plane-redesign/README.md:4`. It is merged and
deployed. Correct it, and state what remains under §11.

### C. Decide the S-12 DAG-name codec sweep

`src/devman/project.py:642-669` sweeps two DAG-name shapes and carries its own
exit condition: **"Drop `-` when `doctor` reports no unmigrated workflow."**

Run `devman doctor` and read the `dag names` check. If it reports no unmigrated
workflow, remove the legacy sweep, `LEGACY_DAG_SEPARATOR` in
`src/devman/registry.py`, `Registry.unmigrated()`, and the fallback test at
`tests/unit/test_run.py:511-520`. If it reports any, **stop and record the
count** — do not remove a migration that is still carrying repositories.

---

## Wave 2 — the unblocked §11 removals

### D. Delete `src/devman/link.py` (item 6, and the smallest real win)

42 lines. Its own docstring at `:9` says: *"Fold this into `devman.watch` and
delete the module when that file is free to edit."* **That file is now free.**

Callers: `src/devman/watch.py:58` and `tests/unit/test_doctor.py:22`. Both
import names that `devman_link` exports directly.

Fold the import into `devman.watch`, repoint the test, delete the module.
`REMOVAL_SEQUENCE_PROMPT.md` is explicit: **do not leave a dead module behind
instead.**

### E. Delete `src/devman/identity.py` (item 6)

35 lines. **Nothing in `src/` imports it.** The only caller is
`tests/unit/test_identity.py:11`. Repoint that test at `devman_link.identity`
and delete the shim.

Check the public surface first: `devman link` is a shipped command, and the
module docstring claims the command depends on these names. Verify that claim
against `src/devman/cli.py` before you delete.

### F. Delete `src/devman/contract.py` (item 6)

35 lines. Callers are `src/devman/reconcile.py:22`,
`src/devman/project.py:738,780,823`, `tests/unit/test_contract.py:7` and
`tests/unit/test_reconcile.py:9`. Repoint each at `devman_contract` and delete.

Its docstring says it "keeps the old one working for every caller inside and
outside this repository." **Audit the outside callers before you delete it** —
grep the fleet for `devman.contract`. If any consumer imports it, say so and
stop.

### G. Collapse the duplicate resolver (item 2) — the largest simplification

**This is the headline item. Read the gate evidence before you start.**

devman carries two projection paths:

| Path | Code | Entry |
|---|---|---|
| compatibility | the Nix-produced `Plan` in `src/devman/project.py` (1042 lines) | `devman project apply` |
| machine plane | `src/devman/reconcile.py` (589 lines) | `devman project render` / `inspect` |

`src/devman/reconcile.py:8-11` states the split. Item 2's gate is "every consumer
off the compatibility resolver."

**Measured 2026-09-14:** the only live caller of `project apply` is
`modules/devenv.nix:450`, the Devman devenv module. The only `devenv.yaml` files
still importing that module are `devman/devenv.yaml:26` (self-adoption,
criterion 16) and `lodestar` and `forgelab`, both in the archive set.

**Re-measure this before you act**, with the fleet sweep shape below. If the
archive set has left, devman itself is the sole user of a 1042-line duplicate.

Two copies both keep passing while they drift. That is the smell `CLAUDE.md`
names, and it is why this item exists.

**Do not simply delete the compatibility path.** devman adopts itself, so
something must still project devman's own workflows at shell entry. State the
design first: either `modules/devenv.nix` moves to the machine-plane renderer,
or the self-adoption path changes shape. Write the design into the log with the
failure it avoids, then change one thing.

`nix/tests/dagu-service.nix` calls `project apply` at `:399`, `:457` and `:511`.
A change here changes that VM test. `nix/renderer.nix:84` is the packaged entry.

### H. Remove the compatibility registry read (item 4)

`src/devman/cli.py:262-275`. `devman link status --all` reads the compatibility
registry, because *"the compatibility registry is still the only thing that knows
which projects were registered."*

Item 4's gate is "a supported replacement for the remaining consumers." The
manifest is the registration now, so the replacement is likely a manifest sweep
rather than a registry read. **State the replacement before removing the read.**
A sweep that silently covers fewer repositories than the registry did is the
Stage 16 failure repeated — it swept without `--project`, three repositories
refused, and it predicted nothing.

---

## Wave 3 — needs a design or an operator decision. Do not start without one.

### I. The watcher half of the strict maintenance gate

`IMPLEMENTATION_LOG.md:437-441` — the watcher waiting on `reload.pending` needs
`src/devman/watch.py`, which was then forbidden. **It is no longer forbidden.**
Read the original gate design before you build the other half.

### J. The reload race for scheduled and watcher-fired runs

`nix/nixos-module.nix:266-271` states it plainly: the race is closed only for the
`devman run` path, because Dagu's scheduled enqueues and the watcher's do not go
through that Python entry point. *"Nobody has built the daemon-side hook a full
close would need."* This is an accepted, documented limitation (§5.3). Closing it
is a design task, not a patch.

### K. §11 item 5 — compatibility mode

**Blocked on three operator decisions.** Ask; do not guess a placement.

1. Three manifest placements: `copyroom`, `docman`, `mypi-agent`, whose identity
   lives in `dev/devenv.nix`.
2. Seven detached-HEAD branch decisions.
3. The disposition of the compatibility-only projects.

`src/devman_link/identity.py:170-223` is the surface — `_legacy_identities()` and
`_compatibility_identity()` parse literal `devman.project` values out of raw Nix
text for repositories with no manifest. Tests pin it at
`tests/unit/test_identity.py:97-125` and `:165`.

### L. The `registryDir` move, and §6.2a

**Do not attempt. Both have measured blockers and neither has a design.**

- **`registryDir` → `~/.config/devman`.** `_sources()` reads an authored override
  from `overlay/projects/<p>/workflows/<name>.yaml`; `apply()` writes the
  rendered projection to the same relative path under `registry/projects/<p>/`.
  Equal roots mean one file, and shell entry would overwrite hand-authored
  workflows with generated output. `025/CONCEPT.md:852-875` records that devman's
  own repository has five such files.
- **§6.2a, render-to-link.** It would remove roughly 500 of `project.py`'s lines.
  The blocker is a design gap, not a patch: `render()`'s
  `env: DEVMAN_PROJECT_DIR: <path>` block is the **only** way a *scheduled* run
  learns its project directory. A CLI-triggered run gets it from the enqueuing
  process; a scheduled run has none. `025/CONCEPT.md:889-901`: *"the mechanism
  for scheduled runs was never designed, only deferred."* Gate it against the
  scheduled subtest in `nix/tests/dagu-service.nix`.

---

## Also open, outside §11

- **`TODO(038-archive)` markers.** `IMPLEMENTATION_LOG.md:1807` and
  `.scratch/spikes/triggers.py:23`. The archive set is `allium-env`, `forgelab`,
  `lodestar`, `fleetman`, `my-ai`. Overlay directories with no checkout:
  `fleetman`, `foreman`, `my-ai`, `siteman`. Close these once the operator's two
  housekeeping steps land.
- **A contradiction worth settling.** `025/CONCEPT.md` §13 #1 records the Claude
  settings write behaviour as settled by 037 Part A; `036/README.md` Part C item
  1 says it is not settled. 037's own "Still open" leaves `nix-meta` and `devman`
  unpromoted. Reconcile into one answer.
- **A missing CLI verb.** `IMPLEMENTATION_LOG.md:2171-2177` records that there is
  no supported command to unregister a live checkout — `doctor --prune` only
  takes entries whose path is gone. Consider whether the plane should have one.
- **Project 029** is an open gap register; its §5.1 and §5.2 are Themes L above.
- **Project 035** leaves one open question at `:308`, classifying 124 uncommitted
  paths in the central repository.

---

## Verify, in layers, after every item

```sh
devenv tasks run -v base:check
devenv tasks run -v base:unit
devenv tasks run -v base:test
devenv shell -- nix build .#checks.x86_64-linux.dagu-service --no-link
devenv shell -- nix build .#packages.x86_64-linux.devman-link --no-link
devman doctor
```

`devman doctor` must exit 0, or exit 1 with only the four known findings, before
a change to `modules/`, `groups/`, `nix/` or `src/devman/` is committed.

### Three traps, already measured — do not re-learn them

1. `base:test` runs `nix flake check`, whose `python-tests` fileset is
   `./src ./tests ./pyproject.toml ./groups ./nix/nixos-module.nix`. **The
   fileset reads the git tree, so an unstaged new file fails the hermetic check
   while `base:unit` passes.** Stage 17 hit exactly this.
2. `flake.nix`'s `shell-variable-unset` requires every new `devman_*=` assignment
   in `modules/devenv.nix` to appear in the `unset` block, in the same commit.
   `hook-path-refusal` cuts a refusal block out by literal path.
3. `tests/unit/test_cli.py` asserts the parser and `handler()` name the same
   commands. Removing a command from one side must remove it from both.

### The canary, after every removal

```sh
cd /tmp
VM_ROOT=/home/andrew/Documents/Projects/vendomat
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
  status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman \
  link status --project vendomat --root "$VM_ROOT" --overlay "$HOME/.config/devman"
```

Both must return 0 with five `ok` states and the central configuration path.

### The fleet sweep, in the shape the hook actually calls

Use an explicit `--project`. Stage 16 swept without it, three repositories
refused, and that predicted nothing about shell entry.

```sh
cd /tmp
for d in "$HOME/.config/devman/projects"/*/; do
  p=$(basename "$d"); r="/home/andrew/Documents/Projects/$p"
  [ -d "$r" ] || continue
  env -u PYTHONPATH -u NIX_PYTHONPATH /run/current-system/sw/bin/devman-link \
    status --project "$p" --root "$r" --overlay "$HOME/.config/devman" >/dev/null 2>&1
  printf '%s %s\n' "$?" "$p"
done | sort | uniq -c -w2
```

**A new refusal is a regression. Diagnose it before removing anything.**

### The plane, unchanged

```sh
PLANE="$HOME/.local/state/vendomat/devman/active"
readlink "$PLANE"
find -L "$PLANE/projects" -mindepth 1 -maxdepth 1 -type d | wc -l
find -L "$PLANE/dags" -mindepth 1 -maxdepth 1 -type f -name '*.yaml' | wc -l
find -L "$PLANE/dags" -type f -name '*.yaml' -exec sha256sum {} + | sort | sha256sum
env -u PYTHONPATH -u NIX_PYTHONPATH dagu --dagu-home "$HOME/.local/share/dagu" ls | wc -l
```

---

## How to work

- **Write in Simplified Technical English.** Short sentences, active voice, one
  word for one meaning, no filler. `.agents/skills/writing/SKILL.md`.
- **Land each item on its own branch, then open a PR against `main`.** A direct
  push to `main` is refused. Merge with a merge commit; the project record cites
  commit SHAs, so do not squash.
- **No `Co-Authored-By` trailers**, and no agent attribution in PR bodies.
- **Record every item in `IMPLEMENTATION_LOG.md`** as its own stage section, with
  the measurement, the evidence directory under
  `.scratch/projects/038-devman-plane-redesign/artifacts/<TS>-<slug>/`, and what
  you did not do.
- **Prefer a loud refusal to a silent default.** A run that reports success while
  producing an incorrect result is the failure this design exists to prevent.
- **Watch for index corruption.** Three repositories this month carried a stale
  staged deletion from a stray `git add -A` — devman, repoman and lodestar. Check
  `git status --short` for `D `/`DA`/`AD` entries before you commit anywhere.

## Report at the end

Files changed per repository; tests and exact results; the live active
generation, DAG count and digest; every doctor finding; commits and pushed
branches; which §11 items closed and which remain; and any blocker needing
operator input.

**Do not mark Project 038 complete until every §11 item has its own recorded
evidence.**
