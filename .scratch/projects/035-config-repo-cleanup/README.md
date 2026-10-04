# 035 — `~/.config/devman` cleanup plan

**Date:** 2026-09-10
**Scope:** the central configuration repository at `~/.config/devman` only.
**Mode:** investigation and analysis. **Nothing in that repository was mutated.**
**Supersedes the live-state accounts in:**
`devman/.scratch/projects/029-central-overlay-status/README.md` §8 and
`devman/.scratch/projects/034-stage-3-readiness-audit/README.md` §9/§15 — both
are now out of date, and §1 below states how.

**Every version-control read ran through `gitman`** at
`/home/andrew/Documents/Projects/gitman/.devenv/state/venv/bin/gitman --repo
/home/andrew/.config/devman`. Raw `git` was used **read-only** for content
diffs, history, and reflog, because gitman ships no `diff`/`show`/`reflog`
verb (`gitman --help`: 26 commands, none of them a diff). That choice is
disclosed in §8 with its justification.

---

## 1. Executive result

**The repository is in a safer state than either prior report recorded, and the
diagnosis is different from the one assumed.** Three corrections:

1. **Nothing is untracked.** `git ls-files --others --exclude-standard` → **0**.
   029's "three untracked paths" and 034's "substantial new untracked content"
   have both moved on: all 124 dirty paths are in the index and in jj's working
   copy. Nothing is at risk of a stray `clean`.
2. **The detached HEAD is not an interrupted gitman operation.** It is **two raw
   `git commit` invocations**, at 15:21 and 16:42 today, on top of the normal
   jj-colocated detached HEAD. The reflog names them (§2). They bypassed gitman,
   which is why jj has never heard of them.
3. **Those two commits are 2 commits *ahead* of `main`, not behind or diverged** —
   and their content is **fully duplicated** inside jj's working copy. So the
   work exists in three places at once. There is no recovery problem.

**The real problem is not loss risk. It is that committing this content as-is
would enshrine a charter violation.** The entire agent surface — 62 files across
three projects — is **real file copies with zero symlinks**, where
`025-the-link-plane/CONCEPT.md` §7.2/§7.3 mandates relative symlinks into the
central pool. One skill (`gitman/SKILL.md`) already exists in **three different
versions**. This is precisely the "copies are where every drift defect lives"
failure P2 exists to prevent (§4).

**Plus 7 files of test-fixture garbage are staged for commit** (§5).

**All three blocking decisions were taken (§8), so the plan in §7 was
executable end to end.** At the time, the operator chose to convert the agent
surface to symlinks before committing, retire only the personal layer's
Copier/copyroom delivery mechanism, and move the Simplified Technical English
rules into a devman-owned pool skill. On 2026-10-03, the operator extended the
scope to retire every active deployment, enrollment, and reference. The source
repository remains in its dated archive. This later decision supersedes the
deployment roadmap in §9.

---

## 2. Detached-HEAD diagnosis

### 2.1 The facts

| Fact | Value |
|---|---|
| git HEAD | `b4e15fa07c06526169086d2c292212cfc7f612d1`, **detached** (`git symbolic-ref -q HEAD` → empty) |
| `main` | `da0533e9e44da8d92511cc7db49402ccd4786a29`, 13 commits |
| `gitman status` | `CANONICAL · 0 lanes`, trunk `main @ da0533e9`, `@` has unbookmarked work |
| `gitman doctor` | WARNINGS (no remote only); **`ok colocated-head`**, **`ok colocated-refs`** |
| HEAD vs main | HEAD is a **descendant**: `main` → `186fbf2` → `b4e15fa`. `git merge-base --is-ancestor HEAD main` → false; the reverse holds |
| jj's view of HEAD | **Does not exist.** `gitman log --revset b4e15fa…` → `Revision … doesn't exist`. Same for `186fbf2…` |
| jj `heads(all())` | `topswsplnwnzupqpnuyusmvzyumnvolt` — the single undescribed working-copy change `@`, child of `main` |

### 2.2 How it got detached — the reflog is unambiguous

```
b4e15fa HEAD@{2026-09-10 16:42:17}: commit: docs: describe central devman workflow overlay
186fbf2 HEAD@{2026-09-10 15:21:28}: commit: chore: declare central agent links
da0533e HEAD@{2026-09-10 13:15:53}: export from jj
33b8cf0 HEAD@{2026-09-10 13:05:51}: export from jj
…  (every earlier entry is "export from jj")
```

**`commit:` is git's reflog action for `git commit`. jj only ever writes
`export from jj`.** So:

1. Up to **13:15:53**, all activity was gitman/jj. The jj op log ends that
   sequence with `gitman:save` then `gitman:land` at 13:15:53, which advanced
   `main` to `da0533e` and left `@` undescribed on top of it. At this point HEAD
   was detached at `da0533e` — **which is normal, correct jj-colocation state,
   not a fault.**
2. At **15:21:28** and **16:42:17**, someone ran **raw `git commit`** twice.
   Because HEAD was already detached, each commit landed on no branch.
3. **The jj operation log has no entry at all between 13:15:53 and 17:26:43.**
   jj was not running. It learned nothing of those commits, because jj imports
   *refs*, and no ref points at them.
4. jj's later snapshots (17:26:43, 21:59:23) absorbed the **working tree** into
   `@`, which is why `@` now carries the same content the orphan commits do.

**So the detachment is a standing-rule violation, not a tool failure:** two
commits were authored outside gitman, against this machine's rule to route every
version-control action through it. Worth finding the source (§7.3) — a second
pair of orphans will appear the next time it happens.

### 2.3 A gitman diagnostic gap, worth reporting upstream

`gitman doctor` reports **`ok colocated-head  git HEAD reachable from a
bookmark`** against a HEAD that is two commits *ahead* of the only bookmark and
on no branch, and **`ok colocated-refs  jj bookmarks ↔ git refs in sync`** while
git holds two commits jj cannot resolve at all. Both checks pass on a genuinely
divergent state. `gitman status` likewise reports `CANONICAL`.

This is the one reason the condition survived two prior audits: **the sanctioned
health check says the repository is fine.** Recommend a gitman check that
compares `git rev-parse HEAD` against the jj commit set and fails when HEAD is
not resolvable as a jj revision.

### 2.4 Is any content at risk?

**No. Every byte exists in three independent places:**

| Location | Holds |
|---|---|
| the working tree | all 124 paths (tracked content byte-identical to `b4e15fa`: `git diff HEAD --name-status` → 69 `A`, **zero `M`**) |
| jj's `@` (`topswspl…`) | all 124 paths — confirmed per-path with `gitman log --revset '@ & files("<path>")'` for `allium-env/devenv.local.nix`, `devman/agents`, `talkee`, and `paloma-text-pipeline`; `@` is returned for each |
| git objects | `186fbf2` + `b4e15fa` hold the 55 modifications (not the 69 additions), reachable from detached HEAD and the reflog |

The orphan commits become unreferenced once HEAD moves, and git's reflog retains
them ~90 days by default. Because their content is a strict **subset** of `@`,
losing them costs nothing.

### 2.5 Why the prior audits read "MM" as staged-plus-unstaged

They read it as a human having staged one version and edited another. It is
neither. In a jj-colocated repository **the git index is jj's export artifact,
not a staging area.** Here it is simply stale:

- worktree vs HEAD (`b4e15fa`): **0 modified** → worktree == HEAD for tracked files
- index vs HEAD: **55 modified** → the index still holds `main`-era content
- therefore worktree vs index differs → git prints the second `M`

`MM` is one stale export, not two competing edits. **Nobody hand-staged
anything.**

---

## 3. Per-project classification of the 55 dirty files

`git diff main --name-status` → **69 `A`** (new) + **55 `M`** (modified). The 55
`M` are *exactly* the content of the two orphan commits, nothing more.

### 3.1 The 54 `devenv.local.nix` files — one uniform mechanical change

**All 54 receive byte-identical added lines. Measured, not sampled:** hashing
every file's added/removed lines across all 54 yields exactly two distinct added
lines, each appearing 54 times, and one removed line (a trailing blank) 48 times:

```
54 × +    ".agents" = { canonical = "central"; path = "projects/${config.devman.project}/agents"; };
54 × +    ".claude/skills" = { canonical = "central"; path = "projects/${config.devman.project}/agents/skills"; };
48 × -    (trailing blank line)
```

Four whole-diff hash variants exist, and all four differ **only** in hunk
headers and surrounding context — not in semantics:

| Variant | Count | Projects | Why it differs |
|---|---|---|---|
| `c69ecffc25` | 48 | the standard case | baseline |
| `ca35959586` | 4 | `foreman`, `forgelab`, `image-gen-pipeline`, `lodestar` | the backburnered four carry `devman.enable = lib.mkForce false`, shifting context |
| `aeb633ff19` | 1 | `devman` | also declares `.devman/workflows`; no trailing blank to remove |
| `4ed1e03829` | 1 | `pydantree` | no trailing blank to remove |

**Classification — all 54 identically:**

| Project name | What changed | Classification | Confidence |
|---|---|---|---|
| `allium-env`, `argentic`, `atuout`, `boomtube`, `browsee`, `cairn`, `copyroom`, `devman`, `docman`, `embeddy`, `eventic`, `fleetman`, `flora`, `flora-core`, `flora-qc`, `foreman`, `forgelab`, `fornix`, `gitman`, `grail`, `image-gen-pipeline`, `interplay`, `knappy`, `llgym`, `loci-core`, `loci.nvim`, `lodestar`, the personal-layer source, `mypi-agent`, `nix-desktop`, `nix-nvim`, `nix-paseo`, `nix-secrets`, `nixbuild`, `nixvim`, `observantic`, `parsedantic`, `poddantic`, `pydantree`, `pyjutsu`, `pyllij`, `pytuin`, `repoman`, `shellij`, `siteman`, `structured-agents-v2`, `talkee`, `templateer_v2`, `terminal-state`, `testee`, `tyo3`, `vendomat`, `webdantic`, `zelligate` **(54)** | adds the `.agents` and `.claude/skills` link declarations; 48 also drop a trailing blank line | **Mechanical, expected** — this is the GUIDE-01 agent-plane rollout (`CONCEPT.md` §7.2). It is exactly orphan commit `186fbf2` "chore: declare central agent links" | **High** — uniformity proved by hashing all 54, not by sampling |

**No project's declared links changed beyond this.** There is no real-content
change and nothing unexplained among the 54.

### 3.2 The one non-Nix modified file

| Path | What changed | Classification | Confidence |
|---|---|---|---|
| `projects/devman/workflows/README.md` | +10 −6. Retitles to "central workflow overlay"; restates the canonical path as `~/.config/devman/projects/devman/workflows/` with the project-side `.devman/workflows/` as a symlink view; clarifies that editing either side then re-entering the shell re-projects | **Real content change, and correct** — it brings the file in line with the central-overlay model recorded in 029 §3.4. It is orphan commit `b4e15fa` | **High** |

### 3.3 The 69 added files

| Group | Count | Classification | Confidence |
|---|---|---|---|
| `projects/devman/agents/skills/*/SKILL.md` | 8 | expected — devman's composed surface. **But copies, not symlinks** (§4) | High |
| `projects/talkee/agents/**` | 27 (13 `devenv/` docs + 14 skills) | expected migration. **Copies, not symlinks** (§4) | High |
| `projects/paloma-text-pipeline/**` | 27 (13 `devenv/` docs + 13 skills + a new `devenv.local.nix`) | expected migration, **one skill short** (§4.3). **Copies** | High |
| `projects/fixture-*/**` | **7** | **Test-fixture garbage. Must not be committed** (§5) | High |

---

## 4. `paloma-text-pipeline` and `talkee` completeness

Both are real, registered projects — repositories exist at
`~/Documents/Projects/{talkee,paloma-text-pipeline}` and both have registry
entries under `~/.local/share/devman/projects/`. Neither is half-written or
truncated at the file level. **Staging state: both are fully in the index and in
jj's `@`; neither is untracked.**

The reconciler's own record confirms these two plus `devman` are the only places
the agent surface was ever actuated — `.devman-link-state.json` holds **59
`devenv.local.nix`, 56 `.envrc`, 55 `.loci`, but only 3 `.agents` and 3
`.claude/skills`**, matching 034 §9 exactly.

`paloma`'s `devenv.local.nix` is **new rather than modified** (absent from
`main`), and its formatting is the compact one-line-per-link bootstrap-template
style — not the multi-line style the other 54 carry. It was **generated by the
reconciler's own bootstrap template**, not adopted from a pre-existing file.
That is correct behaviour for a project whose first shell entry came after the
central feature landed.

### 4.1 The finding that matters: these are copies, not projections

```
find projects/*/agents -type l        →  0
git ls-files -s  (whole repo, mode 120000)  →  0
```

**There is not one symlink in the entire repository**, tracked or untracked.
`CONCEPT.md` §7.2 specifies the opposite:

```
projects/flora/agents/skills/
    gitman   -> ../../../../skills/gitman     relative → TRACKED, portable
    repoman/SKILL.md                          generated router — real file
    flora-domain/SKILL.md                     project-specific — real file
  agents/devenv -> ../../../agents/devenv
```

and §7.3 rests on it: *"Selection is a directory of links… version-controlled,
because relative links inside the config repository are tracked."*

Live reality: 62 real files. Of the skills present, only `repoman` (generated
router) and `devman`/`devman-adopt`/`devman-workflow` (project-specific, absent
from the pool) are legitimately real files. **The rest should be links and are
not.** This is a direct P2 violation — *"Source or projection, never a copy"* —
and §3.1 calls copies *"where every drift defect lives."*

It has already produced drift. It is also **self-reinforcing**: the top-level
`~/.config/devman/agents/` directory §7.2 requires **does not exist**, so the 13
`devenv/` documentation files are duplicated into `talkee` and `paloma` with no
shared source at all — 26 files, two copies, zero canonical.

### 4.2 Measured drift, already present

`gitman/SKILL.md` exists in **three different versions**:

| Copy | Bytes | State |
|---|---|---|
| `skills/gitman/SKILL.md` (the pool) | 8403 | **newest** — carries the expanded release section ("uv owns the version", the six-step canonical release) |
| `projects/paloma-text-pipeline/.../gitman/SKILL.md` | 8402 | current content, differs only by a trailing blank line |
| `projects/devman/.../gitman/SKILL.md` | 7917 | **stale** — missing the whole expanded release section |
| `projects/talkee/.../gitman/SKILL.md` | 7917 | **stale** — identical to devman's |

Every other pool-sourced skill checked (`copyroom`, `copyroom-adopt`,
`copyroom-template-edit`, the personal-layer skill) was byte-identical to the pool
at that time. So the
drift is one skill deep **right now** — and `gitman/SKILL.md` is the one skill
that is *regenerated by `gitman init`*, i.e. a moving target. Committing 62
copies guarantees this recurs across all of them.

### 4.3 Composition differences

| Surface | Skills | Has `agents/devenv/` docs? |
|---|---|---|
| the pool (`skills/`) | 15 — `copyroom`×3, `devenv-*`×8, `docman`, `gitman`, personal-layer skill, `testee` | — |
| `devman` | 8 — `copyroom`×3, `devman`, `devman-adopt`, `devman-workflow`, `gitman`, personal-layer skill | **no** |
| `talkee` | 14 — `copyroom`×3, `devenv-*`×8, `gitman`, personal-layer skill, `repoman` | yes (13 files) |
| `paloma-text-pipeline` | **13** — as talkee, **minus the personal-layer skill** | yes (13 files) |

`diff -rq` of the two surfaces returns exactly two differences: the
`gitman/SKILL.md` version, and the personal-layer skill present only under
`projects/talkee/agents/skills`.
The two were produced by the same bulk operation and are otherwise byte-identical
across 26 files.

**Assessment:** `paloma` missing the personal-layer skill reads as an **omission
from an interrupted migration**, not a deliberate per-project selection. It
held the personal conventions that every other surface carried, and nothing about
`paloma` suggests it should opt out. Flagged for decision in §7.4 rather than
assumed either way. Also note `docman` and `testee` sit in the pool selected by
nobody, and `devman` alone lacks the `devenv-*` literacy skills — plausible, but
unverified as intent.

**Nothing is truncated.** No zero-length or partially-written file was found;
all 62 files parse as complete Markdown with front matter.

---

## 5. Cross-check against 029's three untracked paths

029 §8 recorded, as of its writing, detached at `b4e15fa` with three untracked
paths. **Both halves have drifted.**

| 029 §8 recorded | State now | Drift |
|---|---|---|
| detached at `b4e15fa` | **still detached at exactly `b4e15fa`** | unchanged — but `main` has since advanced to `da0533e` by a `gitman:land` at 13:15:53, so HEAD is now 2 commits *ahead* of trunk rather than merely parked |
| `projects/devman/agents/` untracked | **in the index**, 8 files | no longer untracked |
| `projects/paloma-text-pipeline/` untracked | **in the index**, 27 files | no longer untracked |
| `projects/talkee/agents/` untracked | **in the index**, 27 files | no longer untracked |

**Same three paths, four months on, same content concern — but the staging state
has moved on entirely.** `git ls-files --others --exclude-standard` → **0**:
there is nothing untracked left in the repository. 029's instruction "either
commit those paths or explicitly classify them as local-only" is still the open
question; its premise that they are untracked is not.

### 5.1 New since 029 and 034: fixture contamination is now staged

034 §6/§15 disclosed that a fixture-testing agent wrote stray directories into
this live repository and described them as *"untracked, so they carry no git
history to lose."* **That is no longer true — they are now in the index and would
be captured by the next commit.** The repository now holds **59 project
directories, not 55.**

```
 A projects/fixture-literal/agents          A projects/fixture-literal/devenv.local.nix
 A projects/fixture-literal-2/agents        A projects/fixture-literal-2/devenv.local.nix
 A projects/fixture-var/agents              A projects/fixture-var/devenv.local.nix
 A projects/fixture-nested/devenv.local.nix
```

Each `devenv.local.nix` is the stock bootstrap template; the `agents` entries are
empty directories. **All 7 are garbage and must be removed before any commit.**
The matching 8 registry stubs (`fixture-literal`, `fixture-literal-2`,
`fixture-nested`, `fixture-var`, `part2-a`, `part2-a2`, `part2-b`, `part2-c`) are
still present under `~/.local/share/devman/projects/` and clear with
`devman doctor --prune`.

---

## 6. Is anything at risk from a live writer?

**The GUIDE-03 shape of failure does not apply, but this repository *is* a live
write target.** Checked explicitly:

| Check | Result |
|---|---|
| nested git repository inside the worktree | **none** (GUIDE-03's `notes/` conflict is gone) |
| a `notes` path inside the config repo | **absent** — `~/Notes` is its own repository, as GUIDE-03 §8.1 requires |
| SilverBullet writing into `~/.config/devman` | **no** — `silverbullet.service` is running and its git-backup timer is active, but both are scoped to `~/Notes` |
| symlinks in the worktree a writer could follow in | **zero** |
| `.devman-link-state.json` | gitignored (`.gitignore:6`) — correctly excluded generated state |

**Active writers that do reach this repository:**

1. **`devman watch` (PID 3386703)** plus its `watchexec` (PID 3386740). The
   watchexec `--watch` is scoped to `~/Documents/Projects/devman` **only**, but
   its dispatch calls `link.reconcile()`, which writes canonical content into
   `~/.config/devman/projects/devman/`.
2. **Every `devenv shell` entry in any of the 59 registered projects** fires the
   same reconciler. This is not hypothetical — **it is how the 4 fixture
   directories got here**, and how `paloma`'s `devenv.local.nix` was authored.
3. **`dagu start-all` (PID 2729591)** — scheduled workflows that enter a shell
   reach the reconciler by the same path.

**Assessment: low risk of loss, real risk of contamination.** The reconciler's
discipline is to refuse rather than clobber (034 §4 verified this against
source), and it never deletes. But it *creates* — so the longer this repository
stays uncommitted, the more stray bootstrap directories accumulate in the
pending commit. **That is an argument for committing soon, not for waiting.** The
danger is the opposite of GUIDE-03's: not a service overwriting tracked content,
but generated content drifting into a commit nobody inspected.

One consequence for sequencing: **a shell entry between inspection and commit can
change the file set.** Re-check `git status --short | wc -l` (expect 124, or 117
after the fixtures go) immediately before saving.

---

## 7. The ordered plan

**All blocking decisions are taken (§8); the whole sequence is executable.** Step
4b is the one the decisions added. Nothing here publishes — this repository has
no remote.

### Step 0 — prove the safety net, before touching anything

```bash
G=/home/andrew/Documents/Projects/gitman/.devenv/state/venv/bin/gitman
$G --repo ~/.config/devman status --json > /tmp/035-pre.json
git -C ~/.config/devman rev-parse HEAD main          # expect b4e15fa…, da0533e…
git -C ~/.config/devman status --short | wc -l        # expect 124
```

Record `b4e15fa` and `186fbf2` somewhere outside the repository. They are the
only copy of the 55 modifications *as commits*; after step 7 they are reachable
only via reflog. Their content is also in `@`, so this is belt-and-braces.

**Rollback for every step below is `gitman undo`** (whole-intent, op-log backed),
or `gitman undo --op <id>` to any op listed by `gitman undo --list`.

### Step 1 — remove the fixture garbage (§5.1)

Plain file deletion, not a VC operation — these 7 paths have no committed
history, so nothing is lost:

```bash
rm -rf ~/.config/devman/projects/fixture-literal \
       ~/.config/devman/projects/fixture-literal-2 \
       ~/.config/devman/projects/fixture-var \
       ~/.config/devman/projects/fixture-nested
devman doctor --prune        # clears the 8 matching registry stubs
git -C ~/.config/devman status --short | wc -l   # expect 117
```

### Step 2 — stop the raw-`git` writer (§2.2)

Before committing, establish what ran `git commit` at 15:21 and 16:42 — a shell
alias, an agent, a tool, or a hand invocation. Check `atuin` history filtered to
the human author column for `git commit` in that window. **If the source is not
found and closed, the next pair of orphan commits is already scheduled.**

### Step 3 — adopt `@` into a named lane

`gitman status` already prescribes this: *"working copy `@` has unbookmarked
work — `gitman start <name>` to adopt it into a lane."*

```bash
$G --repo ~/.config/devman start agent-plane-rollout
$G --repo ~/.config/devman status        # expect 1 lane, @ on it
```

### Step 4 — move git HEAD off the orphan chain

After step 3, HEAD should export to the lane. Verify, and heal if not:

```bash
git -C ~/.config/devman rev-parse HEAD        # should no longer be b4e15fa
$G --repo ~/.config/devman doctor             # colocated-head / colocated-refs
# only if HEAD is still b4e15fa:
$G --repo ~/.config/devman reconcile          # the sanctioned ref-drift repair
```

**Do not `git checkout main`.** Raw git is what created the problem, and a
checkout here would also fight jj's working copy.

### Step 4b — convert the agent surface from copies to symlinks (§8.1)

**This is the decided shape (`CONCEPT.md` §7.2) and it must happen before the
commit, so the copies never enter history.** All four preconditions were verified
read-only:

| Precondition | Verified |
|---|---|
| talkee's and paloma's 13 `devenv/` docs are byte-identical | `diff -rq` → no differences. Safe to promote one copy to a shared canonical |
| pool personal-layer skill == devman's and talkee's copies | `diff -q` → SAME for both. Symlinking loses nothing |
| which skills are absent from the pool and must stay real files | `devman`, `devman-adopt`, `devman-workflow` (devman); `repoman` (talkee, paloma) |
| relative depths in `CONCEPT.md` §7.2 are correct | `skills/<s>` is 4 levels up from `projects/<p>/agents/skills/`; `agents/devenv` is 3 up from `projects/<p>/agents/` |

**4b.1 — create the shared docs export that §7.2 requires and does not exist:**

```bash
cd ~/.config/devman
mkdir -p agents
cp -a projects/talkee/agents/devenv agents/devenv     # 13 files, identical in both
```

Plain `cp`, not `git mv`: the source is uncommitted, so there is no tracked path to
move. 4b.2 removes both original copies and replaces them with links.

**4b.2 — replace every pool-sourced skill with a relative symlink:**

```bash
POOL="copyroom copyroom-adopt copyroom-template-edit gitman"
DEVENV_SK="devenv-authoring devenv-inputs devenv-lock devenv-module-edits \
devenv-processes devenv-python-venv devenv-run-commands devenv-troubleshoot"

# devman — 5 pool links; devman/devman-adopt/devman-workflow stay real files
for s in $POOL; do
  rm -rf projects/devman/agents/skills/$s
  ln -s ../../../../skills/$s projects/devman/agents/skills/$s
done

# talkee and paloma — 13 pool links each; repoman stays a real file
for p in talkee paloma-text-pipeline; do
  for s in $POOL $DEVENV_SK; do
    rm -rf projects/$p/agents/skills/$s
    ln -s ../../../../skills/$s projects/$p/agents/skills/$s
  done
  rm -rf projects/$p/agents/devenv
  ln -s ../../../agents/devenv projects/$p/agents/devenv
done
```

The personal-layer skill is omitted from the pool link list. The old plan added
it to `paloma` to match the other two surfaces; the 2026-10-03 retirement decision
supersedes that step.

**4b.3 — confirm the conversion before saving:**

```bash
find projects/*/agents -type l | wc -l            # expect 33 = devman 5 + talkee 14 + paloma 14
find projects/*/agents -xtype l                   # expect EMPTY — no dangling link
readlink -f projects/talkee/agents/skills/gitman  # must resolve into ~/.config/devman/skills/
git -C . ls-files -s -- projects/ | awk '$1=="120000"' | wc -l   # symlinks now tracked
grep -c 'uv owns the version' projects/talkee/agents/skills/gitman/SKILL.md  # 1 → drift gone
```

**Expected effect on the commit:** tracked additions drop from **69 to ~52**, and
the duplicated bytes go to zero — 26 `devenv/` doc copies collapse to 13 shared,
and the three-way `gitman/SKILL.md` drift (§4.2) resolves to the single pool copy
with no decision needed. §8.2 is settled by construction.

⚠ **One thing to verify, not assume.** The reconciler records a canonical content
hash and refuses a two-sided edit (034 §4). Its behaviour hashing a *directory of
symlinks* is untested. After step 8, re-enter a shell in `talkee` and run
`devman link status` plus `ls -L .claude/skills/` to confirm the links resolve
through two hops and no spurious drift is reported. If it does report drift, that
is a devman finding, not a reason to revert this shape.

### Step 5 — split by concern into sibling lanes

One commit per concern, using `gitman split --paths`, which partitions the draft
change and leaves the remainder in place:

| Lane | Paths | Files | Why separate |
|---|---|---|---|
| `agent-plane-rollout` (the remainder) | the 54 `projects/*/devenv.local.nix` | 54 | one uniform mechanical change; reviewable as a single diff (§3.1) |
| `workflow-overlay-docs` | `projects/devman/workflows/README.md` | 1 | unrelated documentation change (§3.2) |
| `shared-devenv-docs` | `agents/devenv/` | 13 | **new after 4b** — the shared export §7.2 requires. Must land *before* the three surfaces, because their `devenv` symlinks point at it |
| `agent-surface-devman` | `projects/devman/agents/` | 8 (3 real + 5 links) | one project's surface |
| `agent-surface-talkee` | `projects/talkee/agents/` | 15 (1 real + 14 links) | one project's surface |
| `agent-surface-paloma` | `projects/paloma-text-pipeline/` | 16 (1 real + 14 links + `devenv.local.nix`) | one project's surface, **plus a new `devenv.local.nix`** |

```bash
cd ~/.config/devman
$G split --paths projects/devman/workflows/README.md --into workflow-overlay-docs \
         -m "docs: describe central devman workflow overlay"
$G split --paths agents/devenv --into shared-devenv-docs
$G split --paths projects/devman/agents --into agent-surface-devman
$G split --paths projects/talkee/agents --into agent-surface-talkee
$G split --paths projects/paloma-text-pipeline --into agent-surface-paloma
```

**Order matters once, and only here:** land `shared-devenv-docs` before the
talkee and paloma surfaces. They are sibling lanes, so a reviewer who lands a
surface lane alone would briefly have a tracked symlink whose target is not yet
in the tree. `gitman land --all` in step 7 avoids this by folding the whole
forest in one transaction.

Reuse `b4e15fa`'s and `186fbf2`'s existing messages — they are accurate.

### Step 6 — verify before saving

This repository has its own `base:check`, which evaluates every project's Nix.
It is the one gate that matters here, because *"a store whose Nix does not
evaluate breaks every repository at once"* (`CONCEPT.md` §11 Stage 1.6):

```bash
cd ~/.config/devman && devenv tasks run -v base:check
```

### Step 7 — save each lane, then land

```bash
$G switch agent-plane-rollout && $G save -m "chore: declare central agent links"
$G switch workflow-overlay-docs && $G save -m "docs: describe central devman workflow overlay"
$G switch agent-surface-devman  && $G save -m "feat: compose devman agent surface"
$G switch agent-surface-talkee  && $G save -m "feat: compose talkee agent surface"
$G switch agent-surface-paloma  && $G save -m "feat: adopt paloma-text-pipeline into the link plane"
$G status                        # 5 lanes, all described, CANONICAL
$G land --all                    # folds the forest into main, each level its own undo point
$G status && $G doctor           # expect 0 lanes, clean @, HEAD == main
```

**No `gitman publish` / `push`.** `gitman doctor` reports **no git remote** on
this repository, so publication is unavailable and not part of this cleanup.

### Step 8 — confirm

```bash
git -C ~/.config/devman status --short      # expect empty
$G --repo ~/.config/devman status          # CANONICAL, 0 lanes, clean @
git -C ~/.config/devman rev-parse HEAD main # equal
```

---

## 8. Decisions — taken 2026-09-10

### 8.1 Copies or symlinks? — **DECIDED: convert to symlinks first**

The charter mandates relative symlinks into the pool (§4.1); the live content was
62 real copies with zero symlinks, and `gitman/SKILL.md` was already three-way
drifted (§4.2). The operator chose to convert **before** committing, so the copies
never enter history. Implemented as **step 4b**.

Rationale on the record: committing 62 copies would make the pool authoritative
in name only, and this repository has no remote — so nothing external pressured a
same-day landing.

### 8.2 Which `gitman/SKILL.md` is canonical? — **DISSOLVED by 8.1**

Pool 8403 bytes (newest, with the expanded release section) vs `paloma` 8402
(trailing newline only) vs `devman` and `talkee` 7917 (stale, missing that
section). Once the surfaces link to the pool, **the pool copy is the only copy**
and no choice is needed. Worth noting that this file is *regenerated by
`gitman init`*, which is precisely why it drifted first and why linking it rather
than copying it matters.

### 8.3 Was the missing personal-layer skill deliberate? — **HISTORICAL DECISION, SUPERSEDED**

At the time of this report, the decision was to add the skill to `paloma` for
parity. The 2026-10-03 retirement decision supersedes that deployment. The skill
is absent from the active pool and all active project links.

### 8.4 What happened to the personal layer? — **RETIRED ON 2026-10-03**

The 2026-09-10 decision retired only the Copier delivery mechanism. On
2026-10-03, the operator extended the scope: remove deployed skills, enrollment
markers, active configuration references, and all text mentions from active
working files. Keep the source repository in its dated archive. The central
writing skill is now its own pool skill, and active instructions point to it.

### 8.5 Where the Simplified Technical English rules live — **COMPLETED**

The writing rules moved to the devman-owned `skills/writing/SKILL.md` file.
Machine and repository instructions now point to that file.

### 8.6 Still open, low priority — surface composition

Should `devman`'s surface really lack the `devenv-*` skills and the `devenv/`
docs, when `talkee` and `paloma` carry both? Should `docman` and `testee` sit in
the pool selected by nobody? And should `devman`/`devman-adopt`/`devman-workflow`
— real files in devman's surface only — be promoted into the pool so other repos
can select them? All plausible as intent, none verified. **None blocks the
cleanup**, because step 4b preserves each surface's selected skills, subject to
the later retirement decision in §8.4.

### 8.7 Accept `projects/*/agents` as tracked

`~/.config/devman/.gitignore` ignores `projects/*/agents/index` but **not**
`projects/*/agents`, so the surfaces are tracked. That matches §7.3 ("relative
links … are tracked") and contradicts `CONCEPT.md` §11 Stage 1.5, which listed
`projects/*/agents` as a gitignore entry. The current file follows §7.3, which is
the later and more specific rule — **no change recommended**, but the charter's
Stage 1.5 list should be corrected so this is not re-litigated.

Per the confirmed decision, **no rule for `projects/*/.local.gitignore` was added
or recommended** — those files stay tracked. None exists anywhere in the
repository yet (`find … -name '*.local.gitignore'` → 0), so the feature has
still never run live. Not a blocker for this cleanup.

---

## 9. Retiring the former personal layer — current scope

This section supersedes the 2026-09-10 recommendation to retire only the delivery
mechanism. That report separated four concerns: the template source, its
distribution path, the shared instructions, and a registered central project.
The 2026-10-03 decision covers every active deployment, enrollment, configuration
reference, and text mention. The dated source archive stays intact.

The writing rules moved into `skills/writing/SKILL.md`. Machine instructions,
central skills, and repository guidance now point there. The central project
overlay was archived on the current trunk; its old checkout contents were not a
live link target. The final machine scan must still verify the active workspace
and every deployed surface.

The old report counted 62 repositories with the layer enrollment and explained
why the link plane can replace a repository-local `.agents` directory with one
central symlink. That historical measurement remains useful for understanding
the migration cost. It is not a current inventory or an instruction to create
62 new lanes. The current scan and repository owners decide which remaining
paths are live, generated, vendor-owned, or historical output.

### 9.1 Preserve the facts; retire the old operating instructions

The link plane's directory symlink replaces the repository-local agent surface
as a whole. The old rollout plan required each repository to promote its tracked
`.agents/` content into the central project, then land a Gitman lane. That plan
explains the earlier migration measurements, but it is no longer a runbook for
this task. Do not use its old deployment count as a current status report.

The critical content dependency was the Simplified Technical English guidance.
It moved to the separate writing skill before the personal-layer files were
removed. This preserved the rules while allowing active links and copied
instructions to be retired.

### 9.2 Current completion checks

1. Remove live skill deployments and enrollment markers after each repository
   owner confirms the paths.
2. Update live instructions, tests, code, and examples so they remain correct.
3. Keep useful measurements and research conclusions, but remove the retired
   project name from active working text.
4. Leave the dated source archive, Git history, conversation logs, caches, and
   worktrees outside the text cleanup.
5. Refresh this report from the final scan. List any unresolved owner decision or
   generated materialization as a blocker instead of claiming completion.

## 10. What this report did not do

No `git add`, `git commit`, `gitman save`, `gitman start`, `gitman land`,
`gitman reconcile`, branch checkout, or discard. No file in any of the 59 project
directories was opened for writing. No fixture directory was removed. Nothing in
`~/Documents/Projects/devman` or any other project repository was touched.

**Raw `git` was used read-only** — `status`, `diff`, `log`, `show`, `reflog`,
`ls-files`, `rev-parse`, `merge-base`, `cat-file` — because gitman exposes no
diff or history-content verb. Two notes on that choice:

1. It is strictly safer here than the alternative. Every `gitman`/`jj`
   invocation **snapshots the working copy** (the op log shows
   `snapshot working copy` entries), mutating jj state; read-only `git` does not.
2. One unavoidable side effect: `git status` refreshes `.git/index`'s stat cache,
   so the index mtime now reads `21:59:53`. Content was not changed, and the
   index is a jj export artifact that the next jj operation rewrites anyway.

**This report lives outside both repositories**, at
`~/Documents/Projects/.scratch/projects/035-config-repo-cleanup/README.md`,
deliberately: `~/.config/devman` has no `.scratch/` convention and no
`AGENTS.md`, and writing into it would have been absorbed into the very `@` this
plan proposes to commit. `~/Documents/Projects/.scratch/` is untracked working
scratch on this machine and is not inside any git repository (verified).

**Proposed permanent home once writing is authorised:** copy this file to
`~/Documents/Projects/devman/.scratch/projects/035-config-repo-cleanup/README.md`
and commit it there in a gitman lane, beside 029 and 034 — it continues their
record, and `.scratch/projects/` is devman's established convention for exactly
this. It should **not** live in `~/.config/devman`, which by its own boundary
rule holds machine-local configuration, not project records.
