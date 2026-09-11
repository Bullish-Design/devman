# 037 — Stage 3, the skill pool, and the decisions already taken

Implement the link plane's Stage 3, consolidate the agent skill pool, remove
the allium cluster, archive three dead repositories, stop a scheduled test
fixture, and settle the last open charter question.

**Most of the investigation is done and written into this file.** Confirm the
measurements cheaply; do not re-derive them. Four decisions are taken and are
not open for re-litigation: archive the three repositories, remove allium,
consolidate to one pool, and treat `agents/pi` as live infrastructure to be
re-rooted rather than deleted.

# Context

Session 036 (`.scratch/projects/036-lane-and-charter-audit/README.md`) closed
every in-flight and orphaned lane and settled five of the six open charter
questions. That work is landed on `main` at `1372581`. This session acts on
what 036 left open, plus three decisions the operator has now taken.

The governing design is `.scratch/projects/025-the-link-plane/CONCEPT.md`.
Its §11 defines five stages. Stages 1 and 2 are done. **Stage 3 is the subject
of Part B and is the largest piece of this session.**

Read this file, then work through Parts A to E in order. Each part stands
alone. Report findings between parts.

# Ground rules

1. **Route every version-control action through gitman.** Raw `git` is allowed
   read-only (`status`, `diff`, `log`, `show`, `ls-files`, `rev-parse`),
   because gitman ships no diff or history-content verb.
2. **`gitman start` adopts the whole dirty working copy.** Run
   `git status --short` before landing and confirm every file belongs to your
   change. Use `gitman split --paths <sel> --into <lane>` to carve out
   unrelated work.
3. **Isolate risky work in a `--workspace` lane**
   (`gitman start <name> --workspace`).
4. **Verify before you save:**
   ```bash
   devenv tasks run -v base:check     # ruff
   devenv tasks run -v base:unit      # the Python suite
   devenv tasks run -v base:test      # nix flake check
   devman doctor                      # exit 0 for modules/, groups/, nix/, src/devman/
   ```
   `base:test` inside a nested workspace hits a known outer-Git-root filter.
   The documented workaround is `nix flake check` from a temporary copy
   outside that root. See 036's verification record.
5. **Land and push a lane by default once verify passes** (the operator's
   standing law). Stop and ask when verify fails, a conflict appears, or the
   lane touches shared or risky files.
6. **Write in Simplified Technical English.** See
   `~/.config/devman/skills/writing/SKILL.md`.

# Measured baseline, as of 2026-09-11

**Do not re-derive these. Confirm them cheaply and move on.**

| Fact | Value |
|---|---|
| devman `main` / `origin/main` | `1372581`, released `v0.5.1` |
| Registry root | `~/.local/share/devman/` — `dags/`, `projects/`, `watch/`, 2.1 MB, 51 projects |
| `~/.local/state/devman/` | **does not exist** |
| Central config repo | `~/.config/devman/`, 55 project directories, **1.2 GB** |
| Repositories with `.agents` as a symlink | 49 |
| Repositories with `.agents` as a real directory | 20 |
| Repositories with a `.devman/workflows` view | 1 (devman itself) |
| `.claude/skills` symlinks across the fleet | 50 |
| `.claude/settings.local.json` files | **7, none of them symlinks** |
| Total `.devenv` across the fleet | **39 GB** |

## `devman doctor`, run 2026-09-11 — the 7 findings to treat as pre-existing

52 projects, 163 workflows. **Any new finding is yours.** These are not:

| Check | Finding |
|---|---|
| `link drift` | `flora:.envrc` and `flora:.loci` both report state `link` |
| `local sources` | `pytuin` pins `atuout` at `d9b69592`; its HEAD is `3acdf1e9` |
| `path inputs` | vendomat `.devenv` = 123 MB (340 `shell-*.sh`), copied into every run of 1 project — **~527 ms on every devenv invocation in flora**. Doctor itself names the fix: *"url: git+file://<path> excludes it"* |
| `daemon shell` | `SHELL` unset in 1 dagu process; `default_shell` governs |
| `watcher` | informational — devman's `**/*.py -> format` watch, running since 2026-09-10 |

**Three of these resolve inside this session.** `path inputs` is Part E.
`link drift` on flora is worth one look while you are in Part E, since flora is
also the only remaining `path:` consumer of vendomat. `local sources` on
`pytuin` is a one-line pin bump and closes a finding cheaply.

**Note what doctor does *not* report:** `stale entries` passes, and it should
not. See B.6.

---

# Part A — Settle the Claude settings question

This is the **last unsettled question** in `CONCEPT.md` §13. 036 could not
close it because no controlled permission approval was run.

**The question:** does `.claude/settings.local.json` survive linking, or does
Claude's writer replace it by rename and break the symlink?

**Why it matters:** the answer decides how many per-repository settings files
can be centralized. It does not block Parts B to E.

**The settling test, exactly:**

1. Pick one low-stakes repository from the seven that have the file:
   `nix-meta`, `nix-secrets`, `lodestar`, `flora`, `image-gen-pipeline`,
   `fleetman`, or devman itself. **Prefer `lodestar`** — it is backburnered
   (`devman.enable = lib.mkForce false`), so nothing schedules against it.
2. Promote its `.claude/settings.local.json` to the central store and link it,
   using the normal reconciler path — a `devman.link` declaration plus a shell
   entry. Do not hand-place the symlink; the point is to test the real path.
3. Confirm the link: `test -L <repo>/.claude/settings.local.json`.
4. Approve one permission through Claude in that repository.
5. Re-run `test -L`. Record whether the symlink survived.

**Both outcomes are useful. Record which one happened:**

- **Survives** — propose centralizing the remaining six files. Say whether
  they should share one canonical file or stay per-project.
- **Breaks** — keep all seven files repository-local, and hoist only the
  genuinely shared allowlists to `~/.claude/settings.json`. Amend
  `CONCEPT.md` §13 item 1 with the measurement in the same commit.

Update `CONCEPT.md` §13 either way. The question stops being open in this
session.

---

# Part B — Stage 3, in full

**This is the main work.** `CONCEPT.md` §11 Stage 3 budgets one day and states
**zero repository edits** — `grep -rn registryDir */devenv.nix` returns 0 hits,
so changing the default changes every repository at once.

## B.1 The target layout

```text
~/.config/devman/          authored config + the dags/ links Dagu reads
~/.local/state/devman/     generated metadata, plans, triggers, watcher state, runs
~/.local/share/devman/     removed, last
```

The split is by **kind**, not by convenience. `dags/` is a projection of
authored config and belongs beside it. `metadata.json`, `triggers.toml`,
`watch/` and run state are regenerated on every shell entry and belong in
state.

## B.2 Every touch point — found by grep, verify the list is complete

| File | Line | What it holds |
|---|---|---|
| `nix/nixos-module.nix` | 88 | `paths.dags_dir = "${registryToken}/dags"` |
| `nix/nixos-module.nix` | 227 | `--add-flags "--registry ${home cfg.registryDir}"` |
| `nix/nixos-module.nix` | 236 | `registry="${cfg.registryDir}"` |
| `nix/nixos-module.nix` | 332-338 | the `registryDir` option and its default |
| `modules/devenv.nix` | 259 | the comment pointing at `dags_dir` |
| `modules/devenv.nix` | 512-515 | the `registryDir` option and its default |
| `modules/devenv.nix` | 581 | `devman_reg="${cfg.registryDir}"` |
| `src/devman/registry.py` | 8, 33, 36 | `DEFAULT_REGISTRY` and its docstring |
| `src/devman/registry.py` | 333 | `dags_dir` property |
| `src/devman/link.py` | 395 | `--registry` argparse default |
| `src/devman/watch.py` | 62 | a comment naming the old path |
| **`nix/tests/dagu-service.nix`** | **53, 77** | **asserts the literal path in the VM test** |

**The VM test is the one that will bite.** `nix/tests/dagu-service.nix:53`
hard-codes `HOME + "/.local/share/devman"` and line 77 asserts
`dags_dir: '{REG}/dags'` appears in the generated config. Stage 3 must update
it in the same commit, or `base:test` fails.

Two flake checks also read `modules/devenv.nix` by literal path
(`CONCEPT.md` §11.0). **A new shell variable must be added to the `unset` block
ending in `devman_cur` in the same commit**, or `shell-variable-unset` fails.

## B.3 The failure to design against

**If `registryDir` moves and `paths.dags_dir` does not move with it in the same
rebuild, Dagu reads an empty directory and every scheduled workflow silently
stops firing. Nothing errors.** That is the exact shape property 4 exists to
prevent: success reported, nothing done.

So: change both paths together, rebuild, run `devman doctor`, **confirm Dagu
actually resolves the DAGs**, and only then remove the old root. Give the
verification something that can fail — count the DAGs Dagu sees and compare it
against the projection, rather than checking only that the directory exists.

## B.4 Order of work

1. Add the `stateDir` option beside `registryDir` in both Nix modules.
2. Change the `registryDir` default to the authored config root.
3. Move `metadata.json`, `plan.json`, `triggers.toml` and watcher state to
   `stateDir` in `src/devman/registry.py` and `src/devman/watch.py`.
4. Point `paths.dags_dir` at the new root.
5. Update `nix/tests/dagu-service.nix`.
6. Rebuild. Re-enter representative repositories so they re-register.
7. `devman doctor` exits 0. Dagu resolves the same DAG count as before.
8. **Only then** remove `~/.local/share/devman/`.

Record the before and after DAG counts. They must match.

## B.5 The `agents/pi` directories — investigated 2026-09-11, **do not delete**

**The earlier reading of this as a "state leak" was wrong. It is live
infrastructure.** The investigation is below so this session does not redo it.

### What `pi/` actually is

It is the runtime root of **mypi-agent**, a repo-scoped bootstrap for the Pi
coding agent. `manifest.json` names it exactly:

```json
{"pi_package": "@earendil-works/pi-coding-agent", "pi_version": "0.78.0",
 "generated_by": "mypi-agent", "resources": ["extensions","skills","prompts","themes"]}
```

**It is read at runtime, not merely stored.** `mypi-agent/modules/pi-agent.nix`
puts `$DEVENV_ROOT/${MYPI_AGENT_ROOT:-.agents/pi}/node_modules/.bin` on `PATH`
and resolves extension and state paths under it (lines 65, 97, 111, 375).
**Deleting it breaks six repositories' shells until `mypi sync` re-runs.**

**Six repositories reach it through the central `.agents` symlink:**
`mypi-agent`, `browsee`, `zelligate`, `tyo3`, `templateer_v2`, `copyroom`.
Two more — `paloma-local`, `paloma-story-generation` — have a real `.agents`
and hold their own copy outside the central store.

### The finding that matters

**All six central copies are the same install.** Measured:

| Project | `package-lock.json` md5 | pi version | size |
|---|---|---|---|
| mypi-agent | `07c16db9be6f` | 0.78.0 | 205 M |
| browsee | `07c16db9be6f` | 0.78.0 | 170 M |
| zelligate | `07c16db9be6f` | 0.78.0 | 168 M |
| tyo3 | `07c16db9be6f` | 0.78.0 | 168 M |
| templateer_v2 | `07c16db9be6f` | 0.78.0 | 168 M |
| copyroom | `07c16db9be6f` | 0.78.0 | 168 M |

Identical lock file, identical version, **141 MB of `node_modules` each**. And
**every declared resource directory — `extensions`, `skills`, `prompts`,
`themes` — is empty in all six.** So 1.1 GB is six identical npm installs
carrying zero per-project content.

The only genuine per-project state is `mypi-agent/agents/pi/.pi-state/`:
`auth.json` (mode 600), `models.json`, `settings.json`. The other five have no
`.pi-state` at all.

### Git status: already clean, and two lines to tidy

**Nothing under any `agents/pi` is tracked** (`git ls-files 'projects/*/agents/pi'`
→ 0). `.gitignore:12` already carries the class rule `projects/*/agents/pi/`.
**Lines 22-27 are redundant per-project duplicates of it** and can go. That is
the whole of the gitignore work — the class rule the earlier draft asked for
already exists.

### What to actually do

**This is a configuration change, not a deletion.** `mypi-agent` exposes a
`root` option (`modules/pi-agent.nix:206`, default `.agents/pi`). Point it at
one shared machine-state location so six identical installs become one. That
location is what Stage 3's `stateDir` is for, which is why this belongs in
Part B rather than on its own.

1. Confirm `mypi sync` rebuilds the root from `manifest.json` and
   `package-lock.json`, and time it. It is an npm install, so it probably needs
   the network. **A rebuild that needs the network is not a free rollback.**
2. Propose the shared root. Check the cost first: `mypi doctor`
   (`src/mypi_agent/doctor.py:155,175`) expects `npm-global` under the root and
   a settings symlink spelled `../.agents/pi`. A shared root touches both.
3. Decide whether `.pi-state/` follows the shared root or stays per-project.
   It holds a credential, so it is the one part that must not be shared.
4. Report the reclaimed size. Expect about 1.0 GB if five copies collapse.

**Flag, do not fix here:** `auth.json` is a credential sitting in the central
config repository. It is untracked and ignored, so it is not in history, and
`AGENTS.md` property 8 says the plane holds no secret value. Report whether
that property is violated in spirit and what moving it would cost. **Do not
move a credential as a side effect of a layout change.**

**The general lesson worth recording:** the reconciler promoted this because
promote takes a directory wholesale, and `.agents/` turned out to hold runtime
state as well as agent surface. Propose whether promote should refuse or skip
a directory that carries a `manifest.json` naming another generator, and say
what that check costs.

## B.6 A scheduled test fixture is running nightly — **live defect, fix first**

Found 2026-09-11 while checking the registry. **This is independent of Stage 3
and should be fixed before it, because it is firing now.**

Two registry entries point into `/tmp`:

| Entry | Path | Workflows |
|---|---|---|
| `changelog-e2e` | `/tmp/devman-changelog-e2e` | **5 DAGs** |
| `probe` | `/tmp/ovl-repo` | 0, inert |

`changelog-e2e`'s `maintain.yaml:146` carries `schedule: "5 0 * * *"`. **It has
run every night and reported success** — Dagu status 4 on 7, 8, 9, 10 and 11
September, five runs, against a throwaway fixture in `/tmp`.

**This is property 4's exact failure shape: a run that reports success while
doing work nobody wants.** It also inflates the plane's own numbers — doctor
reports 52 projects and 167 DAGs, of which 2 and 5 are fixtures.

**Why `--prune` does not fix it.** `devman doctor` reports `ok stale entries`
and `--prune` removes neither entry, because both `/tmp` paths currently
resolve. The check tests whether the path is a directory, not whether it is a
real project. **On the next reboot `/tmp` clears and the entries become stale,
so the failure mode changes rather than ending.**

**Do this:**

1. Remove `/tmp/ovl-repo` and `/tmp/devman-changelog-e2e`, then run
   `devman doctor --prune`. Confirm the registry drops to 50 projects and 162
   DAGs. Registry backups are at `/tmp/037-backup-probe` and
   `/tmp/037-backup-changelog-e2e`, made 2026-09-11.
2. **This was attempted in the session that wrote this prompt and was blocked
   by a permission check on recursive deletion.** Nothing was removed. The
   fixture directories and both registry entries are still live.
3. Then close the hole. `stale entries` passing on a `/tmp` path is the reason
   this survived. Propose a check that refuses to register, or at least warns
   about, a project whose path is under `/tmp` or another ephemeral root. Say
   what it costs — the e2e tests that created these fixtures presumably need
   to register somewhere.
4. Find what left them registered. Both are test fixtures — `changelog-e2e`
   from a changelog-group end-to-end test on 6 September, `probe` from an
   overlay test on 9 September. **A test that registers into the live plane
   and does not deregister will do this again.**

---

# Part C — Archive three repositories

**Decision taken. Execute it.**

`CONCEPT.md` §11 Stage 0 lists `fleetman`, `foreman` and `siteman` as having
zero consumers each. Move all three to `~/Documents/Projects/.archive/`, which
already exists and holds `my-ai`.

**Before moving, confirm zero consumers.** Grep the fleet for each name in
`devenv.yaml`, `devenv.nix`, flake inputs and skill content. A hit is not
automatically a blocker, but it must be reported before the move.

**`fleetman` and `siteman` are registered devman projects**
(`~/.local/share/devman/projects/{fleetman,siteman}` exist). `foreman` is not.
So the move is not just `mv`:

1. Confirm zero consumers.
2. Move the directory into `.archive/`.
3. Remove the registry entries — prefer `devman doctor --prune`, which drops
   entries whose path no longer resolves.
4. Decide what happens to their central config directories under
   `~/.config/devman/projects/`. **Recommend keeping them**, since they are
   small and record what the repository was configured to do. State the
   decision either way.
5. Confirm `devman doctor` is clean of new findings afterwards.

**Also in Stage 0, and worth doing while you are here:** `repoman/AGENTS.md`,
`fleetman/AGENTS.md` and `siteman/AGENTS.md` are all still the unedited seed
text. Two of the three are being archived, so only `repoman/AGENTS.md` needs
writing. Treat it as optional if time runs short, and say so.

---

# Part D — Consolidate to one skill pool

**Decision taken:** one shared pool holds the canonical base set. Repository
specific skills live in that project's directory in the central config
repository.

## D.1 The measured problem

`~/.config/devman/projects/*/agents/skills/` currently holds **442 real
directories and 88 symlinks**. The charter requires the opposite: `CONCEPT.md`
§7.2 and §7.3 specify relative symlinks into `~/.config/devman/skills/`.

Session 035 converted three surfaces — `devman`, `talkee`,
`paloma-text-pipeline`. The fleet migration that followed promoted 46 more
repositories, each carrying its own copies. **The conversion never reached
them.**

**Drift is already measured, and the shape is favourable:**

| Skill | Copies | Versions | State |
|---|---|---|---|
| `copyroom`, `copyroom-adopt`, `copyroom-template-edit` | 46 each | 1 | **all identical to the pool.** Trivial |
| `my-ai` | 44 | 1 | all 44 identical to each other, all differ from the pool. **The pool is correct** — the difference is exactly the "Writing style" section that 035 split into `skills/writing/`. The 44 are one generation behind |
| `gitman` | 14 | 4 (incl. pool) | real drift. `gitman init` regenerates this file, so **take the pool copy** |
| `testee`, `docman` | 1 each | 2 | inspect, then take the newest |

**No copy contains work that the pool lacks, except possibly `gitman`. Verify
that claim before deleting anything.**

## D.2 The base set

Present in `~/.config/devman/skills/` (16):

```
copyroom  copyroom-adopt  copyroom-template-edit
devenv-authoring  devenv-inputs  devenv-lock  devenv-module-edits
devenv-processes  devenv-python-venv  devenv-run-commands  devenv-troubleshoot
docman  gitman  my-ai  testee  writing
```

**`repoman` (17 copies) is a generated router and stays a real file**, per
`CONCEPT.md` §7.5. Do not pool it.

**The `allium` cluster — DECIDED 2026-09-11: remove it. Do not pool it.**

The operator is not using allium going forward. The cluster is `allium`,
`allium-entrypoint`, 12 `allium-cli-*` skills, plus `weed`, `tend`,
`propagate`, `elicit` and `distill`. Measured spread:

| Surface | allium skills | total skills |
|---|---|---|
| `allium-env` | 18 | 23 |
| `browsee` | 19 | 24 |
| `mypi-agent` | 19 | 24 |
| `zelligate` | 19 | 24 |
| `tyo3` | 19 | 22 |
| `templateer_v2` | 19 | 25 |

**113 directories, 3.2 MB.** Deleting them cuts each of those six surfaces to
between four and six skills, which is what makes the pool conversion in D.3
small for them.

**Two things to check before deleting, and report both:**

1. Grep the six repositories and the pool for references to these skill names —
   a router entry, an `AGENTS.md` table row, a workflow step. A dangling
   reference is the one way this bites later.
2. **`allium-env` is still a live repository and a registered devman project.**
   Removing the skills from the agent surfaces is **not** the same as retiring
   that repository. Do not archive it as part of this. If it should also go,
   that is a separate decision to raise, not to take.

Note that `mypi-agent/AGENTS.md` already says *"Do not re-introduce
`allium-env` or other development-only wiring into the public root import
path"*, so the wind-down is already underway on that side. The skill removal
is consistent with it.

Everything appearing **once** — `loci-*`, `fornix-*`, `cairn-*`,
`pydantree-*`, `docman-*`, `argentic-*`, `devman-*`, `dev-*`, `shellij`,
`nvim-demo-*` — is project-specific and stays a real file in that project's
directory. That is the operator's decision, already taken.

## D.3 How to do it

Follow the shape 035 proved in its step 4b:

```bash
POOL_DIR=~/.config/devman/skills
# from projects/<p>/agents/skills/<s>, the pool is four levels up
ln -s ../../../../skills/<s> projects/<p>/agents/skills/<s>
```

**Verify after conversion, not before:**

```bash
find projects/*/agents/skills -xtype l        # must be EMPTY — no dangling link
find projects/*/agents/skills -type l | wc -l # expect ~400+
```

**Then check the thing 035 flagged and never tested.** The reconciler records a
canonical content hash and refuses a two-sided edit. **Its behaviour hashing a
directory of symlinks is still untested.** After the conversion, enter a shell
in two converted repositories and run `devman link status`. If it reports
spurious drift, that is a devman defect to fix, not a reason to revert the
shape.

Land this as a gitman lane in `~/.config/devman`, which has no remote, so
nothing publishes. Run that repository's own `base:check` first — it evaluates
every project's Nix, and a store whose Nix does not evaluate breaks every
repository at once (`CONCEPT.md` §11 Stage 1.6).

---

# Part E — The devenv copy: explain it, then fix what is left

**This is largely already answered. Confirm the analysis, apply the remaining
fix, and write it down.** Do not re-run the 014 measurements.

## E.1 What the copy is

Project 014 (`.scratch/projects/014-the-plane-s-only-verb/RESULT.md` §1, §12)
measured it:

- `Validating lock` is **94 %** of a warm `devenv` invocation. Nix evaluation
  is 1.8 ms.
- devenv re-resolves every input on every invocation. **A local `path:` input
  carries no revision, so Nix copies and hashes the whole directory —
  `.gitignore` ignored.**
- devenv's own `.devenv/` cache is content-addressed and **never deleted, not
  even by `devenv gc`**. 014 measured 22.9 GB across 54 repositories. **It is
  39 GB today.**
- So a `path:` input to a repository with a large `.devenv` pays that copy on
  every single invocation.

## E.2 The better way, already measured

**`git+file:` honours `.gitignore`; `path:` does not.** vendomat's
`.gitignore:1` already excludes `/.devenv`, so `git+file:` removes the 122 MB
copy rather than shrinking it. 014 §12 measured the same input at
**1448 ms → 149 ms, about 12×**.

**014 §15 reported that six repositories broke under `git+file:`. §16 retracted
it** — five of the six were transient filesystem failures, not
incompatibilities. Read §16 before treating `git+file:` as risky. Keep its real
lesson: **`devenv tasks run` succeeding proves nothing about `devenv shell`.
Gate any input change on shell entry.**

**For a stable dependency, a pinned remote tag is better still**, and the fleet
mostly uses it already: 48 repositories take devman at
`git+https://…?ref=refs/tags/v0.5.1`, and 9 take vendomat at a pinned tag. A
remote pinned input copies nothing local and cannot drift with the working
tree.

## E.3 What is actually left to fix

Only **8 `path:` inputs** remain fleet-wide:

```
clinch/devenv.yaml:10        path:…/shellij
fsdantic/devenv.yaml:15      path:…/shellij
inferference/devenv.yaml:12  path:…/repoman/modules
inferference/devenv.yaml:21  path:…/shellij
flora/devenv.yaml:19         path:…/repoman/modules
flora/devenv.yaml:26         path:…/vendomat      <- the 122 MB one doctor flags
flora/devenv.yaml:40         path:…/shellij
PyGentic/devenv.yaml:10      path:…/shellij
```

Target `.devenv` sizes: `repoman` 278 MB, `vendomat` 122 MB, `shellij` 12 MB.

**Convert each to `git+file:`, one at a time, and gate every one on
`devenv shell -- true` returning 0** — not on `devenv tasks run`. Where the
consumer does not need the local working tree, prefer a pinned remote tag
instead. Report per-repository before and after timings.

## E.4 What this does not fix

Stage 5's `cliProvider = "store"` is a **different axis**. 036 measured it:
store mode removes the manager toolchain from the consumer venv, but a consumer
importing a local vendomat tree still pays the path-input copy. **Fixing the
input scheme is the fix for the copy. Store mode is not.** Say so explicitly in
the write-up, because the two have been conflated before.

**Also report, without acting:** 39 GB of `.devenv` is a standing cost that no
input change removes, because nothing deletes it. 014 §13 measured a `maintain`
sweep worth 42 %. Say whether that sweep still exists and still runs.

---

# What to produce

A `README.md` in this directory, structured by part, recording for each:

- what was measured, with the command and the number;
- what changed, and in which lane;
- what was decided, and on what evidence;
- what is still open, and what would settle it.

Plus:

1. **Amend `CONCEPT.md` in the same commit as any change that contradicts it.**
   Property 2 of `AGENTS.md` requires it, with the measurement that forced it.
   Expect at least §13 item 1 (Part A) and §11 Stage 3 (Part B) to need it.
2. **A verification record** in the 036 style: `base:check`, `base:unit`,
   `base:test`, and `devman doctor` before and after, with the pre-existing
   finding count stated so new findings are distinguishable.
3. **Hold anything ambiguous.** Do not silently delete 1.1 GB, archive a
   repository with a consumer, or drop a skill copy that holds unique content.

**Stop and ask** on:

- any consumer found for the three archive candidates (Part C);
- any reference to an `allium` skill name outside the six surfaces (D.2);
- `mypi sync` turning out not to rebuild `pi/` offline, which would make the
  shared-root change a one-way door (B.5);
- moving `auth.json` — raise it, do not do it as a side effect (B.5).

**Do not stop to ask** about the allium removal itself, the three archives, or
the pool conversion. Those decisions are taken and recorded above.

# Sequence

The parts are written in reading order, not execution order. Execute in this
order:

1. **B.6** — the nightly fixture run. It is firing now and the fix is minutes.
2. **Part C** — the archives. Independent, small, reduces the surface everything
   else touches.
3. **Part D** — allium removal, then pool consolidation. Independent of Stage 3
   and it shrinks the tree Stage 3 moves.
4. **Part B** — Stage 3 itself, including B.5's shared `pi/` root.
5. **Part E** — the eight `path:` inputs. Independent; do it whenever.
6. **Part A** — the Claude settings test. Independent, and the only part whose
   result is a measurement rather than a change.

**B.6 before B** matters: pruning two fixture projects before the registry
migration means Stage 3 moves 50 entries rather than 52, and the before/after
DAG count in B.4 is a clean comparison.
