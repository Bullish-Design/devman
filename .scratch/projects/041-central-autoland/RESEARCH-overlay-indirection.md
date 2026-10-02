# Research — should the overlay's live symlinks resolve through a generation
# pointer instead of the jj working copy?

**Date:** 2026-10-02
**Scope:** `~/.config/devman`, the 325 live symlinks across 66 repositories that
target it, and `~/.local/state/vendomat/devman/active` — the generation
mechanism project 041 §9 proposes as a precedent.
**Mode:** research and measurement only. **Nothing was mutated.** No `gitman`
or `jj` command ran against `~/.config/devman` or any managed repository.
Read-only raw `git` (`log`, `show`, `ls-files`) was used against
`~/.config/devman`, for the same reason 035 and 041 disclose: gitman ships no
verb that answers "how often was this path touched" or "is this path in
trunk's tree." Two throwaway probes ran in `mktemp -d` under `/tmp` and were
removed; see "What this did not do."
**Builds on:** `041-central-autoland/CONCEPT.md` §1.3, §3.3, §9, §11;
`025-the-link-plane/CONCEPT.md` §5, §6.2a, §6.3, §8, §12; `devman/AGENTS.md`
property 6; `035-config-repo-cleanup/README.md`.

---

## Executive result

**Recommendation: (d) now — keep live targets on trunk and gitignore the
generated remainder — and never (b), the generation pointer.** (c), a partial
pointer limited to the two live-critical classes, is the one escape hatch
worth banking if (d) alone is judged insufficient later; it is not needed
today.

**The one measurement that decides it:** the two content classes whose
breakage is most severe — `devenv.local.nix` (bricks shell entry, §1.3) and
`.local.gitignore` (exposes the link plane to `git add -A`, §1.3) — are also
two of the three *most frequently edited* classes in the repository's entire
22-day history, touched on 8 and 5 of its 9 active days respectively, most
recently today. The hypothesis implicitly assumes live-critical content is
rarely edited, so indirection would cost little. **That assumption is false
for this repository.** There is no clean split between "breaking this bricks a
shell" and "this is edited daily" — the two sets overlap almost completely.
A generation pointer would tax the highest-frequency, highest-severity content
hardest, which is the opposite of what makes indirection cheap.

**A second, independent reason, found while reading the generation mechanism
itself: it is the wrong shape of thing for this content.**
`vendomat.plane.GenerationStore` stores *rendered, derived* output — Dagu
projections built from a renderer, validated (`dagu validate`), hashed by
digest, and periodically pruned. The git-tracked overlay content behind the
325 symlinks is the opposite: hand-authored source, edited directly, reviewed
and recovered through git — precisely the class 025 P2 says must never be
duplicated into a copy. Routing it through a generation store does not add
indirection to a stable root; it converts tracked source into a second,
derived copy of itself, which is the exact "copies are where every drift
defect lives" failure 025 §3.1 names and 035 spent a whole project fixing
(62 real copies → symlinks, one skill three-way drifted). **This is evidence
the premise of the brief is not just costly but structurally wrong for this
content class** — see "Where this contradicts CONCEPT.md §9 and AGENTS.md
property 6" below.

---

## 1. The existing generation mechanism

### 1.1 What it is, and what it holds

`~/.local/state/vendomat/devman/active` is a symlink into
`~/.local/state/vendomat/devman/generations/<N>/`, each generation an
**immutable** directory of rendered Dagu projections, one per registered
project (`projects/<name>/projection.json`, `projects/<name>/metadata.json`,
plus the project's `workflows/*.yaml`), built by calling a renderer binary and
validated with `dagu validate` before activation
(`vendomat/src/vendomat/plane.py:1073-1089`, `_validate_dags`).

`devman/AGENTS.md` property 6 names the three roots and their owners:

| Root | Holds | Status |
|---|---|---|
| `~/.local/share/devman/` | the compatibility registry: `dags/` and the shell-entry projection | live |
| `~/.local/state/devman/` | the stable state root: metadata, kept config copies, watcher state, run metadata | Stage 3 item 1, deployed |
| `~/.local/state/vendomat/devman/active` | the active generation: project metadata, projected workflows, Dagu links, `generation.json` | generation 3 since 2026-09-15 |

### 1.2 Is the swap atomic? Yes, and the mechanism is explicit

`GenerationStore._activate_number` (`vendomat/src/vendomat/plane.py:503-513`):

```python
def _activate_number(self, generation: int, *, fault: FaultHook | None = None) -> None:
    if self.active.exists() and not self.active.is_symlink():
        raise PlaneError(f"active pointer exists and is not a symlink: {self.active}")
    temporary = self.root / f".active-{generation}.new"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(Path("generations") / str(generation))
    ...
    os.replace(temporary, self.active)
```

A fresh symlink is built at a temp path beside `active` (same directory, same
filesystem), then `os.replace(temporary, self.active)` — a single `rename(2)`
— swaps it onto the live name. `os.replace` on POSIX is `rename`, which is
atomic for same-filesystem renames, including when the destination exists.
This is the correct mechanism; a pointer swap built any other way (unlink then
symlink, or writing through the existing name) would have a window where the
pointer is absent or half-written, exactly what AGENTS.md property 4 calls
"a run that reports success while producing an incorrect result" the other
way round. Project 041 and 035 both independently credit the same technique
(`os.replace`) for safety elsewhere in this family.

**Serialization.** `operation_lock()` (`plane.py:221-232`) takes an
exclusive `fcntl.flock` on `<root>/.lock` around build, activate, rollback and
recovery (`vendomat/src/vendomat/cli.py:306,458,536`). Only one writer can run
the sequence at a time. A reader holding an already-opened file descriptor
across the swap keeps reading the old generation's inode until it reopens the
path — ordinary POSIX symlink-swap semantics, and it is why generations are
retained (`retain()`, `plane.py:301-323`) rather than deleted immediately: the
active generation and its immediate predecessor are always kept, so an
in-flight reader or a rollback has somewhere to land.

**Who may swap it:** `vendomat`'s CLI only, via `plan_or_update`/`rollback`,
both wrapped in `operation_lock()`. Nothing else writes `active`.

### 1.3 Immutability, and why that matters later

`GenerationStore.build` refuses to overwrite an existing generation directory:

```python
final = self.generations / str(generation_number)
if activate and final.exists():
    raise PlaneError(f"generation {generation_number} already exists and is immutable")
```

A generation is build-once, swap-in, never edited. There is no "edit this
file in the active generation" operation anywhere in `plane.py` — the only
way content changes is a brand-new generation number, rendered fresh and
activated. §3 below measures what this costs a repository whose canonical
content is routinely edited directly.

### 1.4 Why the stable state root was separated

`~/.local/state/devman/` holds run metadata, watcher state and kept config
copies — generated facts about *what ran*, never content a repository links
to. It survives a generation swap because swapping `active` only ever changes
*which Dagu projections exist*; it must not also discard the record of what
already ran against the old ones. This is the precedent cited in the brief,
and it is sound for exactly the content it protects: metadata about
execution, not source a human edits.

---

## 2. Classifying the overlay's content by mutability — the decisive measurement

Commands, read-only, against `~/.config/devman` (`git log --all`, which spans
`jj`'s exported history including unlanded lanes):

```
git log --format=%H --all -- '<pathspec>' | wc -l
git log --format=%ad --date=short --all -- '<pathspec>' | sort -u | wc -l   # distinct days
git log --format=%ad --date=short --all -- '<pathspec>' | sort -u | tail -1  # last touched
```

The repository's whole recorded history spans **2026-09-10 to 2026-10-01**,
**9 distinct active days** out of 22 elapsed.

| Content class | Live-criticality (§9, 025 §3) | Commits touching it | Distinct days touched | Last touched |
|---|---|---|---|---|
| `projects/*/devenv.local.nix` | **High** — Nix reads it before any hook; a dangling one bricks shell entry with an uninterceptable trace | 137 | **8 of 9** | 2026-10-01 |
| `projects/*/.local.gitignore` | **High** — projected to `.git/info/exclude`; losing it exposes the repository to `git add -A` committing the link plane | 51 | **5 of 9** | 2026-10-01 |
| `projects/*/agents/**` (skill-pool links + composed surface) | Medium — degrades an agent session, breaks no shell | 103 | 7 of 9 | 2026-10-01 |
| `skills/**` (the pool itself) | Medium — same | 17 | 4 of 9 | 2026-10-01 |
| `projects/*/links.yaml` | Medium — Linkman's declaration source, mid-cutover | 8 | 2 of 9 | 2026-10-01 (all 7 of these on this one day) |
| `projects/*/workflows/**` | Low — exactly one repository (devman) uses this | 19 | 2 of 9 | 2026-09-11 (dormant 20 days) |
| `common/envrc` | Unmeasured directly; feeds 60 views' shell activation | 7 | **1 of 9** | 2026-09-10 (written once, untouched since) |

**Is there a clean split?** No. The brief asks for the boundary between
"breaking this bricks a shell" and "this is edited daily," and names it as
the most valuable result if it does not hold. **It does not hold.** The two
highest-severity classes — `devenv.local.nix` and `.local.gitignore` — are
also the first and third most frequently touched classes by distinct-day
count, and both were edited again on the very last active day. The only
classes that are both low-severity and low-frequency are `workflows/**`
(one consumer, dormant for 20 of the repository's 22 days) and `common/envrc`
(written once, in one burst, then stable). Those two together back
**61 of 325** live views (`.devman/workflows` 1, `.envrc` 60, per 041 §3.3);
the two high-severity, high-frequency classes back **131 of 325**
(`.agents` 66 + `devenv.local.nix` 66 − 1 double-counted project, per the same
census) by key alone, before counting `.git/info/exclude`'s 64.

A secondary check, because raw git-commit counts in a jj-colocated repository
can overstate real edit events (every jj snapshot exports as a git commit,
some undescribed): sampling ten `devenv.local.nix`-touching commits and
counting files changed per commit shows 2–16 files each, named per-project
(`fix: import link-module.nix in the four legacy central files`,
`repoman: migrate the declaration to the manifest header`) rather than one
giant bulk rewrite repeated nine times. The high day-count is real,
targeted, per-project editing, not nine copies of one mechanical commit.

---

## 3. What the pointer would break

### 3.1 Edit-in-place immediacy — the main, quantified cost

025 §6.3 measured, and it is the property the whole link plane is built
around: *"Editing the target in place, scheduler already running — fired
`VERSION_TWO_EDITED` … no re-link, no restart."* 025 §5.5 generalizes it:
only rename-based writers break a file link; a plain editor save does not.

A generation store has **no edit-in-place operation at all.** §1.3 showed
`build()` refuses to touch an existing generation directory — the only way
content changes is building and activating a new generation number through
the renderer-and-validate pipeline (`render_project` shells out to a renderer
binary; `_validate_dags` shells out to `dagu validate` for every workflow
file). There is no code path that means "I edited one file, make it live."

Combined with §2: `devenv.local.nix` and `.local.gitignore` were each edited
on more than half this repository's active days. Under a generation pointer,
**every one of those edits** would need an explicit publish-and-activate
step before it reached a live symlink — turning "save the file" into "save
the file, then run a build/activate command" for the two content classes
edited most. For the three sampled devenv.local.nix commits with named
single-project messages, that is not an occasional cost; it is the normal
edit loop.

**A second, structural reason this is worse than it sounds.**
`devman_link.paths.resolve()` builds the canonical side with
`(root / rendered).resolve()` (`src/devman_link/paths.py:50`) — Python's
`Path.resolve()` follows every symlink component, including a hypothetical
`active` generation pointer, all the way to the concrete
`generations/<N>/...` path. The symlink the reconciler then creates
(`view.symlink_to(canonical)`, `src/devman_link/reconcile.py:110`) therefore
embeds the resolved generation number, **not** the `active` indirection,
at the moment it is made. A live view would not track future generation
swaps automatically; it would need re-running through the reconciler after
every swap, fleet-wide, to pick up a new generation at all — the same cost as
an explicit re-link, just moved one step later. Making the indirection work
as described in the hypothesis needs a second change: stop resolving the
`active` component when computing each view's target. That is a real, not
cosmetic, code change to `paths.py`.

### 3.2 The reconciler's promote path — incoherent against an immutable canonical

025 §5.1 state 3 ("a real file or directory on the view side → promote
content to canonical, then link") is implemented in
`reconcile.py:222-233`/`excludes.py:99-126`, and both write directly to
`canonical_path` with `shutil.copy2` + `os.replace`
(`reconcile.py:124-126`, `_copy_content`). If canonical resolves inside a
generation directory, promote has nowhere coherent to write: writing into
`generations/<N>/...` directly violates the store's own immutability
invariant (§1.3) without going through the renderer or updating
`generation.json`'s digests, and the *next* `plan_or_update` run would
either silently "retain" a generation whose content no longer matches its
recorded digest, or the write would need to be redefined as "stage and
activate generation N+1" — a heavyweight operation (render, validate,
activate) for what is today a single `os.replace`. Promote is not merely
slower under this model; **it has no defined target.**

### 3.3 The exclude projection's hash baseline — the refusal still works, narrowly, but for the wrong reason

`.devman-link-state.json` records `{canonical, hash}`
(`excludes.py:139`, `reconcile.py:164-168`) and refuses a two-sided edit when
the canonical side's content hash has moved since the link was recorded
(`excludes.py:111-122`; `reconcile.py:224-231`). Because `canonical_path` is
the fully-resolved physical path (§3.1), the recorded path would point at a
specific immutable generation directory forever. Since that directory truly
never changes once built, the refusal's "has canonical changed?" check would
**never fire for staleness** — not because the mechanism was strengthened,
but because the thing it watches is frozen by construction. The refusal
degrades from "catches a real two-sided edit" to "can never catch anything,"
which is 041's own definition of a check that cannot fail
(AGENTS.md property 4; 041 §1.1's `link drift` finding is exactly this
failure mode in a different check). This is a regression, not a win, for
the one safety property the brief asks about directly.

### 3.4 `gitman untrack`

Orthogonal. `untrack` operates on the overlay repository's own git tree, not
on symlink-target resolution. It is unaffected either way, and 041 §9.2
already rejects untracking the live-critical targets regardless of this
question — correctly, since untracking does not remove the hazard, it only
moves it outside recovery and the two-sided-edit refusal.

### 3.5 Nix evaluation

No measured problem. The fleet already evaluates one symlink hop reliably —
every central `devenv.local.nix` imports
`/run/current-system/sw/share/devman/link-module.nix`, itself a Nix-store
symlink, read successfully on every shell entry in 65 live projects
(041 §1.3, §B3 in the linkman readiness review). 025 §6.3 separately measured
a two-hop symlink chain (`dags/x → projects/f/workflows → repo`) discovered
and executed correctly by Dagu. An additional hop through a generation
pointer is the same shape of indirection Nix and Dagu already resolve today.
**Unaffected**, on existing precedent; not independently re-probed, because
the existing precedent is direct and strong enough not to need a new `/tmp`
experiment.

### 3.6 The watcher

`devman`'s own watcher (`nixos-module.nix:802-850`) is unaffected in kind: it
already re-reads its own trigger map every five seconds and replaces its
watchexec child when the watched path set changes, so it does not statically
cache a path across a generation-style swap. The **precedent that a swap
needs its own reload signal** is already built and running, for Dagu: a
`systemd.user.paths` unit watches the *parent* of `registryDir` for
`PathChanged` and runs a reload script on the active pointer's replacement
(`nixos-module.nix:257-345,780-800`). **That mechanism does not exist for the
overlay.** Making the 325 live symlinks pick up a swap without a fleet-wide
re-run of `devman-link reconcile` would need an equivalent new path-unit
hook, scoped to every one of 66 repositories' `enterShell`, or a scheduled
sweep. Nothing today provides it; it is new work, not reuse, despite living
beside code that does the equivalent job for a different root.

---

## 4. The migration, costed honestly

**How many views, by what mechanism.** All 325, because the mechanism that
places every one of them is the same `devman-link reconcile` call
(`modules/link.nix:70-75`'s `enterShell` hook, or the watcher's reactive
trigger). Re-running it fleet-wide is not "66 shell entries": a shell that is
already open does not re-enter; it would need either a manual
`devman-link reconcile` invoked in each of 66 open shells, a restart of each,
or — more realistically — one scheduled sweep from the overlay side, which is
new code (§3.6).

**Safe ordering.** The readiness review's blocker **B3**
(`linkman/.loci/projects/001-devman-cutover/m14-lanes-8-10-readiness-review.md`
§B3) found that deleting the link adapter before the 77-of-78 central files
that import it stop doing so bricks shell entry in all 65 live projects at
once, because Nix reads `devenv.local.nix` before any hook runs. A
generation-pointer migration has the identical shape: the moment canonical
resolution changes (from "the working copy" to "a generation path"), every
one of 325 views is affected simultaneously, and if the new resolution is
wrong for even one view the failure is uninterceptable from inside the
affected shell, exactly as B3 describes. There is no partial-rollout window
smaller than "the next shell entry per repository," because resolution lives
in `devman_link/paths.py`, shared code, not a per-repository setting.

**Rollback.** At the mechanism level, rolling back means repointing
`paths.resolve()` back to the working copy and re-running reconcile — the
same fleet-wide blast radius as the forward migration, with the same B3-shape
risk. There is no generation-level rollback available here, because the
hazard being fixed is in *how a path resolves*, not in *which generation is
active* — `GenerationStore.rollback()` (§1) answers a different question
than this migration needs answered.

**What this retires.** Only if the generation pointer's physical root is
moved entirely outside the jj-colocated working copy — i.e., the live bytes
no longer live inside `~/.config/devman`'s working tree at all — does C3
("every live view's target is reachable from trunk," 041 §3.2) become
unnecessary for the content that moved, because no `switch`/`split`/`abandon`
on the jj repository could touch a path outside it. By the same token the
proposed `[switch.pre_hook]`
(`gitman/.scratch/projects/60-switch-hook-request/ISSUE.md`) becomes
unnecessary for that content too. **But that is only true if the generation
store becomes the sole copy of the content** — and §3.1–§3.3 showed that is
incompatible with git-tracked, hand-edited source (P2) without duplicating
it. If instead the generation is *rendered from* the git-tracked overlay
(keeping the overlay as source and the generation as a derived copy), C3
would need to be reframed, not retired: the question becomes "is trunk's
rendered copy current," which is a new, harder check than "is the path in
trunk's tree," and the switch-hook request's underlying hazard (content that
exists only on an unlanded lane) is completely unaddressed, because the
rendered copy would be built from whatever lane happened to be checked out
at render time. **Net: the pointer does not cleanly retire either defensive
mechanism; it either needs them in modified form, or it requires exactly the
P2-violating duplication §3 found expensive.**

---

## 5. The alternatives, compared

### (a) Status quo plus detection — what 041 shipped

**Verdict: adequate as a backstop, not a fix.** `central-verify`'s C2/C3/C4
plus the repaired `link drift` detector catch the hazard within one night or
before a `land`. Cost: already paid, ~150 lines, 3.4 s to run. Residual risk:
`switch`/`split`/`abandon` are still ungated (041 §9.3, §11 limit 6) — the
window is bounded by keeping C3 at zero, not closed. Retires nothing; it is
pure detection layered on an unchanged hazard.

### (b) The generation pointer, in full

**Verdict: reject.** §2 shows the content most exposed to the hazard is also
the content edited most often, so indirection taxes exactly the wrong
population. §3.1–3.3 show the mechanism itself (immutable, build-once
generations) has no coherent edit-in-place or promote operation for
hand-authored source, and the exclude-projection refusal degrades rather than
survives. §4 shows the migration has the same fleet-wide, uninterceptable
blast radius as the B3 hazard it is trying to avoid. §1 confirms the atomic
swap mechanics are sound — this is not a rejection of the *pattern*, which
works well for its intended content (Dagu projections); it is a rejection of
applying that pattern to this content.

### (c) A partial pointer — live-critical classes only

**Verdict: the one fallback worth banking, not adopting now.** Limiting the
pointer to `devenv.local.nix` and `.local.gitignore` does not escape §2's
finding — those are precisely the two most frequently edited classes, so the
immediacy cost in §3.1 lands in full. It would only be worth it if (d) below
is judged insufficient and a stronger structural guarantee is wanted
specifically for the bootstrap file and the exclude projection, accepting
that every edit to either becomes a two-step publish. Not recommended today
because (d) already removes 313 of 325 views from the hazard at a fraction
of the engineering cost, and the remaining 12 are a landing-discipline
problem, not a resolution-mechanism problem (see (d)).

### (d) Keep live targets on trunk, gitignore everything generated

**Verdict: recommended, and already mostly in effect.** 041 §9.1 measured
that 313 of 325 live views already point at content reachable from trunk,
and are therefore already immune: a `switch`, `split` or `abandon` cannot
remove a path trunk holds, because every lane descends from trunk. The
hazard's size is exactly the count of lane-only views (12, measured 041
§1.3), not a property of the repository. This is cheaper than (b) or (c) by
a wide margin — it needs no new mechanism, only the discipline project 041
already names: land promptly, keep C3 at zero, let the nightly check and the
`[land.pre_hook]`/`[land.post_hook]` gate catch the nights it drifts. **What
it does not cover:** the window between a new bootstrap file's creation and
its land — new content always starts life on a lane (041 §9.1 point 2) — and
`switch`/`split`/`abandon` remain structurally ungated during that window
(041 §8.3, §11 limit 6). That residual is real and is exactly what the
gitman `[switch.pre_hook]` request targets, at low stated priority, because
313-of-325 already makes the exposure small and bounded.

### (e) A read-only published copy (rsync-style), not a live pointer

**Verdict: reject, same reasoning as (b), sharper.** 025 P2 forbids copies
inside a working tree because they drift silently and 035 found exactly that
failure already live in this repository (a skill in three different byte
states). The objection is about *machine-local* copies too, not only
cross-machine ones: 035's 62 copies were all on one machine, and they still
drifted. A read-only publish step is a slower-moving, equally real instance
of the same failure — it adds a second place the bytes live, with a human
remembering to re-run the publish being the only thing keeping them in sync,
which is precisely the discipline-not-mechanism gap 041 §9.3 already warns
against for a different mechanism. It does not even gain the atomic-swap
property (b) has; a copy mid-rsync is a visible half-state, worse than
either (b) or (d).

---

## What I could not determine

1. **Whether `common/envrc`'s single edit-day (written once on 2026-09-10,
   untouched since) means it is genuinely low-frequency, or just young.** The
   repository's whole history is 22 days; one data point cannot distinguish
   "stable by design" from "nobody has needed to touch it yet." Settled by
   watching this class for another month before relying on its apparent
   low-frequency status in any future design.
2. **The exact live-criticality of `.envrc`.** 025 §8 calls it "my shell
   activation," and the live census (041 §3.3, linkman readiness review
   §1.3) counts 60–65 live views, but no probe in this research or in the
   required reading measured what happens to shell entry specifically when
   `.envrc` is dangling, as distinct from `devenv.local.nix`. Settled by a
   `/tmp` probe analogous to 041's `devenv.local.nix` dangling-target
   measurement.
3. **Whether a generation-style pointer rooted *outside* the jj-colocated
   working copy, used only as a rendered mirror of trunk (not of `@`), would
   avoid both the P2-copy objection and the immediacy cost.** This shades
   into (d) with an automated trunk-refresh step rather than (b) with full
   generation immutability, and it was not separately modeled here because
   it is a new fifth option implied by combining (d) with a sync daemon, not
   one the brief asked to compare. Settled by a follow-up project if (d)'s
   residual 12-view window is judged worth closing by a mechanism rather than
   discipline.
4. **Whether the `devman_link.paths.resolve()` change needed to make a
   pointer's *view-side* symlinks track `active` without baking in the
   generation number (§3.1) is itself safe** — it was reasoned from the
   existing `Path.resolve()` call, not built and tested in a probe, because
   building it would be writing production code for a design this research
   recommends against.

---

## Where this contradicts CONCEPT.md §9 and AGENTS.md property 6

**It does not contradict CONCEPT.md §9's measurement; it extends the same
observation to a sharper conclusion.** §9.1's "313 of 325 are already immune"
is reused here as the core evidence for recommending (d). Nothing in this
research found that number wrong.

**It confirms, rather than contradicts, AGENTS.md property 6's refusal.**
Property 6 records that `registryDir` did **not** move to
`~/.config/devman`, because `overlayDir` already defaults there and the
renderer would then overwrite hand-authored overlay content with generated
output the moment the two roots collided — guarded by a refusal added in
Stage 41, not resolved. That is the same collision this research found from
the other direction: making the overlay's canonical side resolve through a
*generation* root reintroduces the identical hazard — a render/publish step
writing derived content into the same space as git-tracked, hand-authored
source — just with the roots' roles reversed. **The brief's premise — "the
plane already solved this exact problem for a different root" — is only
true for the root's *mechanism* (an atomic symlink swap). It is not true for
the root's *content model*.** The generation store was built for, and only
for, rendered output with no human author touching it directly between
builds. The overlay's live-critical content is the opposite case by
construction, and AGENTS.md property 6 already paid for learning that these
two content models must stay apart.

---

## What this did not do

No `gitman` or `jj` command ran against `~/.config/devman` or any managed
repository. No file under `~/.config/devman`, `~/.local/state/vendomat`,
`~/.local/state/devman`, or `~/.local/share/devman` was created, edited or
removed. No symlink anywhere in `/home/andrew/.config/devman` or any of the
66 repositories was created, repointed or removed. No `.py`, `.nix`,
`.toml` or `.yaml` file in any repository was changed — this document is the
only file written, at the one path requested.

Raw `git` was used **read-only** in `~/.config/devman` — `log`, `show`,
`ls-files` — for the §2 edit-frequency measurements, because gitman exposes
no verb for commit-history frequency and 035/041 already disclosed the
identical read-only-raw-git choice with the identical justification. No
`git add`, `commit`, `checkout`, `reset` or `clean` ran anywhere.

No probe mutated a real repository. Two read-only inspections were made of
code already on disk (`vendomat/src/vendomat/plane.py`,
`devman/src/devman_link/{paths,reconcile,excludes}.py`,
`devman/src/devman/doctor.py`, `devman/nix/nixos-module.nix`) — reading, not
running. No `/tmp` probe for §3.5's Nix-hop question was built, because the
existing measured precedent (025 §6.3's two-hop chain, and the fleet's
already-live store-path symlink hop) was judged strong enough not to warrant
a new one; this is recorded as item 4 under "What I could not determine"
rather than claimed as independently re-verified.
