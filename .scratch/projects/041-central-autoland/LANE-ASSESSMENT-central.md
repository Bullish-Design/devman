# Lane assessment — three parked paloma lanes in `~/.config/devman`

Date: 2026-10-03
Scope: `parked-paloma-handoff`, `parked-paloma-judge-skill`, `parked-paloma-pairwise-judge`
in the central configuration repository `~/.config/devman`.
Mode: read-only assessment. Nothing in `~/.config/devman` was mutated. All
commands below were read-only `git` or read-only `gitman status`.

No tool denial occurred. `gitman status` ran without being blocked, so the
lane-list numbers below come from gitman directly; all content analysis
(diffs, blobs, merge-base, cherry) used raw `git`, as the brief directs.

## Executive summary

All three lanes touch exactly one file:
`projects/paloma-text-pipeline/agents/skills/pairwise-quality-judge/SKILL.md`.
That file already exists on trunk, already received trunk's own edit later
the same day the lanes were parked, and `paloma-text-pipeline` is not a live,
onboarded project today. **Recommendation for all three: ABANDON.**

| Lane | Recommendation | Deciding fact |
|---|---|---|
| `parked-paloma-handoff` | ABANDON | Its edit target (same file, same lines) was independently re-edited on trunk at `8fc41475`, timestamped *after* this lane's commit. No live symlink depends on it. |
| `parked-paloma-judge-skill` | ABANDON | Converges on the same idea trunk's `8fc41475` already landed (drop the Anthropic API/SDK dependency), with different wording — a same-day duplicate, not new value. |
| `parked-paloma-pairwise-judge` | ABANDON | Adds the file at a path trunk independently populated in the same session (`288cbd79`, pool-dedup) with materially different content (281 vs 262 lines) — an add/add conflict against trunk's own later, more complete version. |

None of the three is already an ancestor of `main` (the 036 Part B
"already-landed" test does **not** fire for any of them — see §6), so this
is not a case of stale duplicate lanes that happen to carry zero diff. They
each carry real, unique commits. The abandon recommendation rests on
supersession and project-liveness, not on the 036 test.

---

## Lane 1: `parked-paloma-handoff`

**Recommendation: ABANDON.** Deciding fact: trunk edited the exact same file
at commit `8fc41475` ("chore: link docman agent surface", Sat Sep 19
16:26:04), which is *after* this lane's single commit (`9099d17b`, Sep 19
12:53:31). The lane's content is an earlier draft of the same file; trunk's
own later edit supersedes it.

**What it changes.** One file, one commit:
`projects/paloma-text-pipeline/agents/skills/pairwise-quality-judge/SKILL.md`,
+113/-41 against `main` (`git diff --stat main..parked-paloma-handoff`).
Commit message: "wip: paloma pairwise-quality-judge edit (carved from
unbookmarked @ to unblock the central lane)" — confirms this was WIP, not a
finished change.

**Live-symlink answer: no.** The reverse-index walk
(`/home/andrew/Documents/Projects/devman/.scratch/projects/041-central-autoland/artifacts/prototype-v3-reverse-index.py`,
run read-only) found 318 live symlinks across 65 fleet repositories pointing
into the central overlay, zero dangling, zero lane-only. None of the 318
targets fall under `projects/paloma-text-pipeline/` — grepping the full
output for "paloma" returns nothing. This lane touches no path any live
symlink resolves to.

**Is `paloma-text-pipeline` live and onboarded? No.**
`/home/andrew/Documents/Projects/paloma-text-pipeline` exists as a directory
but:
- it is not a git repository (`.git` absent — `ls -la .../paloma-text-pipeline/.git` → "No such file or directory"),
- it has no `.devman/project.toml` (checked directly — absent),
- its only contents are an empty `.devman/.runs/` scratch tree (logs/, reports/, artifacts/, metadata.jsonl), dated today,
- `.devman-link-state.json` in the central repo has no entry mentioning paloma at all.

So on disk this is not a going-concern repo, just a stale directory with
leftover run-scratch. Trunk's central side, by contrast, *does* carry a full
`projects/paloma-text-pipeline/` directory (`.local.gitignore`, `agents/`,
`devenv.local.nix`, `links.yaml` — all present per `git ls-tree main --
projects/paloma-text-pipeline/`), i.e. trunk is ready to serve this project
the moment it's onboarded, but nothing has claimed those links yet.

**Conflict and supersession risk: high, confidence high.** Merge-base is
`288cbd79` itself (the commit that first populated this file via the
milestone-14 skill-pool dedup, "297 duplicate skill directories replaced by
relative pool symlinks"). Between that merge-base and `main` there are 11
commits, and one of them (`8fc41475`) edits this exact file — removing the
requirement to check `ANTHROPIC_API_KEY`/`ant auth status` and run
`uv sync --extra dev`, replacing a "frontier Claude judge" design with an
"isolated coding-agent harness" design. Diffing trunk's *current* file
content directly against this lane's file content
(`git diff --no-index <(git show main:...) <(git show parked-paloma-handoff:...)`)
shows 287 changed lines out of roughly 300 — essentially a full rewrite, not
a localized conflict. A sync would not cleanly apply; it would need a manual
reconciliation that mostly reinvents the wording trunk already has.

**Cost if this recommendation is wrong.** If the right call was actually
LAND: the only thing lost is a slightly different phrasing of guidance text
in a skill file for a project that is not onboarded and has no live
consumer. No repository other than the central one is affected, because no
symlink resolves here. Worst case is purely editorial: a future
`paloma-text-pipeline` onboarding inherits trunk's `8fc41475` wording
instead of this lane's wording. That is a content-quality question, not a
safety one.

---

## Lane 2: `parked-paloma-judge-skill`

**Recommendation: ABANDON.** Deciding fact: this lane's own description
text — "Run Paloma's blind pairwise story-quality labeling with a Claude
coding-agent judging harness (no API key, no SDK call)" — is the same idea
trunk's `8fc41475` already landed ("…with an isolated judging subagent"),
authored later the same day. This is a parallel draft of a change trunk
already made, in different words.

**What it changes.** Same single file, +155/-140 against `main`
(`git diff --stat main..parked-paloma-judge-skill`). Commit message: "chore:
park another session's pairwise-judge skill edit" (Sep 19 14:47:56) — the
commit message itself records that this was a parked, not-landed, in-flight
edit from a different session.

**Live-symlink answer: no.** Same reverse-index result as Lane 1 — zero
live symlinks resolve anywhere under `projects/paloma-text-pipeline/`.

**`paloma-text-pipeline` live/onboarded status:** identical to Lane 1 — not
a git repo, no `.devman/project.toml`, not in the link-state file. Not live.

**Conflict and supersession risk: high, confidence high.** Merge-base is
`7e06743c` ("chore(link-plane): stop tracking generated routers", Sep 19
afternoon-ish). Ten commits separate it from `main`, and `8fc41475` again
falls inside that range and touches this same file. Direct content diff of
trunk's current file against this lane's file
(`git diff --no-index`) shows 312 changed lines — the largest of the three,
meaning this lane's version is the most divergent from what trunk ended up
with. Landing it as-is would overwrite trunk's already-landed wording with
an earlier, less-settled draft of the identical idea.

**Cost if this recommendation is wrong.** Same shape as Lane 1: no live
symlink, no other repository touched, no onboarded consumer today. Worst
case is overwriting trunk's more-polished same-day edit with an earlier
draft — recoverable by re-running `8fc41475`'s intent, not a data-loss
event.

---

## Lane 3: `parked-paloma-pairwise-judge`

**Recommendation: ABANDON.** Deciding fact: at this lane's merge-base
(`0d119ff6`), the target file did not exist yet for `paloma-text-pipeline`
(this lane's diff is a pure add, +262/-0). Trunk independently created the
same path with different content five minutes later in wall-clock terms of
the same working session, via the milestone-14 skill-pool dedup (`288cbd79`,
281 lines, "pool is authoritative"). This is an add/add collision against
trunk's own, more complete, same-day population of that path — not new
content trunk is missing.

**What it changes.** One new file (from the lane's point of view):
`projects/paloma-text-pipeline/agents/skills/pairwise-quality-judge/SKILL.md`,
+262/-0 against `main`. Commit message is explicit about its own
provisional status: "parked: pairwise-quality-judge skill for
paloma-text-pipeline. Adopted from an unbookmarked working copy so a
concurrent conversion lane could start clean. Not written by this session;
left as a draft for its author to land or amend." (Sep 19 12:05:54 — the
earliest of the three lane commits.)

**Live-symlink answer: no.** Same reverse-index result — zero matches under
`projects/paloma-text-pipeline/` among the 318 live views.

**`paloma-text-pipeline` live/onboarded status:** identical to Lanes 1 and
2 — not onboarded.

**Conflict and supersession risk: high, confidence high.** Twelve commits
separate the merge-base from `main`. Two of those touch this exact path:
`288cbd79` (which created it from the pool) and `8fc41475` (which then
edited it further). A sync/rebase of this lane onto current `main` is not a
plain "apply a new file" — the path now exists on trunk with unrelated
content, so git will refuse a clean fast-forward and present an add/add-style
conflict. Direct content diff (trunk's current file vs. this lane's file)
shows 238 changed lines out of roughly 280 — again close to a full rewrite.

**Cost if this recommendation is wrong.** Unchanged from the other two: no
live symlink, no onboarded project, no other repository in the 65-repo
fleet depends on this path today. Worst case is a lost early draft that
differs from trunk's landed version mostly in which design (API-key judge
vs. coding-agent harness) is described — recoverable from this lane's own
git history if anyone needs the earlier phrasing later.

---

## Project liveness (shared across all three lanes)

- `/home/andrew/Documents/Projects/paloma-text-pipeline` exists but is not a
  git repository and has no `.devman/project.toml`. It is not onboarded.
- The central repository still carries `projects/paloma-text-pipeline/` on
  `main`, including the milestone-14 `links.yaml` and `devenv.local.nix`
  that *would* wire it up if the project were ever onboarded. It has not
  been moved to `projects/.archive/` (unlike `foreman` and the personal-layer
  project, which have).
- The reverse-index walk found no live symlink anywhere in the 65-repository
  fleet that resolves into `projects/paloma-text-pipeline/`. Nothing live
  depends on this project's central content today.

Net: the project is dormant, not archived — present on trunk, absent on
disk as a real repo, unclaimed by any live symlink.

## Devenv.local.nix / links.yaml check (item 5 of the brief)

None of the three lanes touches `devenv.local.nix` or `links.yaml` for
`paloma-text-pipeline` — confirmed by `git diff --name-only main..<lane>`
for each, which lists only the one `SKILL.md` path. So there is no direct
collision between these lanes and the milestone-14 links-plane cutover
content itself; the supersession here is purely about the skill-file prose,
not about the links/legacy-nix dual-declaration problem the cutover is
otherwise worried about.

## Already-on-trunk test (036 Part B, item 6 of the brief)

```
git merge-base --is-ancestor <lane> main   # all three: exit 1 (NO)
git cherry main <lane>                      # all three: "+ <sha>" (unique commit)
```

None of the three lanes passes the "already an ancestor of main, no unique
patch" test. Each carries one real, unique commit. The 036 Part B test does
**not** by itself justify abandoning them — the justification here is
supersession (trunk independently re-did the same conceptual edit, later,
on the same file) plus the absence of any live consumer, not "there's
nothing here."

## What I could not determine

- I could not read the *intent* behind `8fc41475` beyond its commit message
  and diff — I don't know if the author who wrote it was aware these three
  parked lanes existed, or deliberately chose to re-derive the edit instead
  of landing one of them. That is a judgment call for the operator, not
  something the git history settles.
- I did not inspect `.loci/design/PAIRWISE-QUALITY-JUDGE.md` or the
  `PROGRAM-AUDIT-2026-09-19.md` referenced inside the skill file's own
  prose — those live outside the central repo (in the eventual
  `paloma-text-pipeline` working copy, which doesn't exist on disk), so I
  could not check whether the skill's substantive content (not just
  wording) is accurate against current project design docs.
- I did not determine *why* `paloma-text-pipeline` was never onboarded
  despite trunk carrying a full `links.yaml`/`devenv.local.nix` pair for it
  — only that it wasn't.
- I did not run `gitman sync`, `land`, `switch`, `split`, or any other
  mutating verb, per the hard rules. The conflict assessment above is
  reasoned entirely from `git diff`/`merge-base`/`cherry`/`show`, not from
  an actual merge attempt, so "would not cleanly apply" is an inference from
  overlapping line ranges and near-total-rewrite diff sizes, not a verified
  merge-conflict marker.
- I did not check whether any *other* (non-symlink) consumer — e.g. a
  script that reads central paths directly rather than through a fleet
  symlink — depends on this file. The brief's live-symlink reverse index
  does not cover that case, and I found no evidence of one, but I did not
  exhaustively search for it either.

## Where the brief was right / wrong against what I found

- The brief's framing ("does it add content a live view needs") is the
  right question, and the answer for all three lanes is unambiguous: no.
  The reverse-index prototype worked exactly as described, ran clean
  (0 dangling, 0 lane-only across 318 views), and is reusable as-is.
- One nuance the brief didn't anticipate: the three lanes don't just risk
  being *behind* trunk — trunk already independently re-did the same
  substantive edit on the same file, later the same day. The brief's model
  of "trunk moved past the lane" (milestone-14 residue, archive moves,
  links.yaml rollout) is accurate as general cutover risk, but in this
  specific case the sharper fact is same-file, same-day, same-idea
  supersession at the content level, which the "10-12 commits behind"
  framing undersells — it sounds like generic staleness, but the real
  story is a direct collision with a same-day sibling edit.
- Everything else in the brief (gitman status wording, the three lane
  names, diff-stat magnitudes, the 11/10/12-behind counts) matched what I
  observed.
