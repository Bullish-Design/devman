# RESEARCH — universal vs. selected skills in the shared pool

Date: 2026-10-03
Scope: `~/.config/devman/skills/` (the pool) and `~/.config/devman/projects/*/agents/skills/`
(the 64 live link-plane surfaces), plus the 35 repository `AGENTS.md` files that still
cite the retired `my-ai` path.
Mode: read-only investigation. Nothing was edited, no `gitman`/`jj` mutating command ran,
no file under `~/.config/devman` changed. All central reads used the trunk commit
`ef1b3847f028dce07c70bc64b0dad7319982da01` (`gitman status`'s reported trunk), not `HEAD`.

## Recommendation, up front

`writing` is universal law and was never rolled out, not selected against — the fleet-wide
distribution step that `gitman` got (2026-09-16) never happened for `writing`. Enforce it with
a `devman doctor` check that asserts every live surface's `agents/skills/` carries the
universal set (today: `writing`; `gitman`/`copyroom` are already near-universal by practice).
The check must fire today against 28 real surfaces — if it does not, it is not a real check.
A documented convention is not enough: that is the mechanism that just failed for 35 repositories.

## 1. Pool inventory and classification

Pool skills on trunk, from `git ls-tree ef1b3847... skills/`:

| Skill | Classification | Criterion / evidence |
|---|---|---|
| `writing` | **Universal law** | Description: "The user's Simplified Technical English writing rules... Read this before writing docs, skills, code comments, docstrings, commit messages, CLI help, error text, or replies to the user." No stack or tool gates this — every repository produces text. Absence means an agent writes to no stated standard, silently. |
| `gitman` | Tool interface, *de facto* universal | "Route ALL version control through gitman." Every repo in this fleet uses gitman for VC (confirmed: 59/64 surfaces carry it; the 5 without are edge cases, see §2). Selection criterion still applies in principle (a repo with no VC would not need it) but in this fleet the tool is universally present. |
| `copyroom`, `copyroom-adopt`, `copyroom-template-edit` | Tool interface, *de facto* universal | Scaffolding/template-management entry points. 63/64 surfaces carry `copyroom` (only `tyo3` lacks it). Same shape as `gitman`: selection in theory, universal in this fleet's practice. |
| `testee` | Tool interface, genuinely selected | "Use when verifying code changes... This repo verifies through Testee." Only meaningful where Testee is the verification manager. 18/64 surfaces carry it (see §3 — not zero, contra 035 §8.6). |
| `docman` | Tool interface, genuinely selected | "Route all documentation tasks... through docman." Only meaningful where a repo manages docs that way. 17/64 surfaces carry it (see §3). |
| `devenv-authoring`, `devenv-inputs`, `devenv-lock`, `devenv-module-edits`, `devenv-processes`, `devenv-python-venv`, `devenv-run-commands`, `devenv-troubleshoot` | Tool interface (not literacy/reference) | Each description is keyed to a concrete devenv.sh failure mode or authoring task ("Use when a module edit... doesn't take effect", "Use on ModuleNotFoundError"). These are decision trees for symptoms, not background reading — absence does not mislead an agent, it just leaves a known-tool problem undiagnosed longer. 31/64 surfaces carry the bundle (7 skills move together; `devenv-lock` alone sits at 24/64, a subset — see note below). The brief's "literacy, breaks nothing by absence" framing undersells how targeted these are, but the practical effect (absence ≠ wrong standard, just slower debugging) still lands them short of universal law. |

Note on `devenv-*` selection: the 33 surfaces without the bundle include `linkman`,
`copyroom`, `gitman`, `docman`, `repoman`, `testee`, `devman` — several of which *do* have a
`devenv.nix` on disk (verified for `linkman`, `copyroom`, `gitman`). So presence of the tool does
not cleanly predict presence of the skill; the split looks composition-time (added via
"chore: configure F2 link-plane projects" / "chore: add forgelab and lodestar..." commits) rather
than a stack check. I could not fully resolve whether the manager-tool repos' exclusion is
deliberate (they're simpler consumers of devenv, not authors of modules) or a second, smaller
instance of the same unrolled-skill problem as `writing`. Flagged in §6, not solved here.

`devman`, `devman-adopt`, `devman-workflow` are **not pool skills** — they live only at
`projects/devman/agents/skills/<name>/SKILL.md` directly in the devman project tree, never
symlinked. The brief's framing of these as "project-specific" pool candidates is slightly off:
they are not in the pool at all, so there is no selection question to ask about them.

## 2. Measured selection — the table

Counted with `git ls-tree ef1b3847... "projects/$p/agents/skills/"` for every one of the 67
registered projects, keeping only `120000` (symlink) entries whose basename matches a pool
skill name, and spot-verified link targets resolve to `../../../../skills/<name>` (confirmed
for `docman` and `testee`, see commands below). 64 of 67 projects have any `agents/skills/`
surface at all.

| Skill | Surfaces carrying it | / 64 |
|---|---|---|
| `copyroom` | 63 | 98% |
| `copyroom-adopt` | 63 | 98% |
| `copyroom-template-edit` | 63 | 98% |
| `gitman` | 59 | 92% |
| `devenv-authoring` | 31 | 48% |
| `devenv-run-commands` | 31 | 48% |
| `devenv-python-venv` | 31 | 48% |
| `devenv-processes` | 31 | 48% |
| `devenv-module-edits` | 31 | 48% |
| `devenv-inputs` | 31 | 48% |
| `devenv-troubleshoot` | 31 | 48% |
| `devenv-lock` | 24 | 38% |
| `writing` | 18 | 28% |
| `testee` | 18 | 28% |
| `docman` | 17 | 27% |

Commands behind this table:
```
TRUNK=ef1b3847f028dce07c70bc64b0dad7319982da01
for p in $(ls projects/); do git ls-tree $TRUNK "projects/$p/agents/skills/"; done \
  | awk -F'\t' '$1 ~ /^120000/ {print}'   # then matched basenames against the 15 pool names
# -> 542 (surface, skill) pairs, tallied with sort | uniq -c
```
Link-target spot check (`docman`, 17 surfaces; `testee`, 18 surfaces): every target resolves
to `../../../../skills/docman` or `../../../../skills/testee` — genuine pool links, not local
lookalikes.

Interpretation: `copyroom*` and `gitman` read as universal-in-practice (90%+). `writing`,
`testee`, and `docman` cluster at ~27-28%, which looks like three genuinely-selected tool
skills by count alone — but that reading is wrong for `writing` specifically (§3).

## 3. `writing` — never added, not selected against

Of the 35 repositories whose `AGENTS.md` still cites the literal retired path
`.agents/skills/my-ai/SKILL.md` (confirmed count, command below), exactly **7** have a working
`.agents/skills/writing/SKILL.md` on disk today: `lodestar`, `pytuin-desktop`, `PyGentic`,
`silverbullet-server`, `inferference`, `forgelab`, `template-py`. The other 28 have no
`writing` link at all (not a broken symlink — the entry is simply absent).

```
grep -rl '\.agents/skills/my-ai/SKILL\.md' --include=AGENTS.md /home/andrew/Documents/Projects \
  | grep -v archive | wc -l          # -> 35
# then, per repo, test -e "$p/.agents/skills/writing/SKILL.md"   # -> 7 RESOLVES, 28 MISSING
```

For all 28 missing ones, `git log --all --oneline -- "projects/<repo>/agents/skills/writing"`
in the devman repo returns **zero commits** — the path was never created, let alone removed.
That rules out "selected against" (there is nothing to have reverted). Meanwhile
`git log --all --oneline -- "projects/<repo>/agents/skills/my-ai"` for the same repos shows a
real history ending in removal, and at trunk the `my-ai` link is confirmed absent for all of
them — so the retirement half of the migration ran, and the replacement half did not.

Timeline from commit messages (dates from `git log --date=short`):
- 2026-09-11 `bf06e351`/`5d43caa2` — "split the STE writing rules out of my-ai into a pool skill" (`writing` created)
- 2026-09-16 `e93ea4e9` — "distribute the gitman skill across the fleet" (this is the kind of commit `writing` never got)
- 2026-09-19 `71344a42` — "link testee, docman and writing into repoman's agent surface" (one repo, not the fleet)
- 2026-10-01 `ff7be524` et al. — "m14: retire foreman and my-ai into projects/.archive/" (citation target removed fleet-wide, with no `writing` fleet-wide rollout to replace it)

This is exactly the "universal-but-unrolled" case the brief warned about, now confirmed by
`git log`, not inferred from counts.

## 4. 035 §8.6 — "`docman` and `testee` selected by nobody" — no longer true

Measured today: `docman` has 17 consumers, `testee` has 18 (§2). Both nonzero, both well above
"selected by nobody." `git log --diff-filter=A` on these paths shows the first consumer links
landing 2026-09-11, i.e. around or just after when 035 was likely drafted (035 itself cites a
2026-09-10 cleanup project, and §8.6 reads as a snapshot from that moment). The fleet has moved
since: this question is stale and should be closed, not reopened as a design question. The
machine (today's link state) overrides the document's (035's) claim here.

## 5. Enforcement — options and pick

Options considered, per the brief:

1. **Documented convention** — cheapest, but it is the exact mechanism that produced 28 silent
   gaps. Rejected: a convention with no check is a convention nobody has to obey.
2. **Reconciler creates the universal links** — strongest guarantee (a surface cannot exist
   without them), but conflates "what composition adds" with "what verification catches." If the
   reconciler has a bug, there is no independent signal that anything is wrong.
3. **`devman doctor` check asserting every live surface carries the universal set** — matches
   the shape of checks the project just added elsewhere, and is independently falsifiable: it
   reads the same `agents/skills/` surfaces measured in §2 and fails whenever a live surface is
   missing a universal-set link. **This is the pick.**
4. **Nothing, treat 28 as correct** — rejected by the evidence in §3: 28 is not a choice anyone
   made, it is an unfinished migration.

**What would make the check fire, concretely, right now:** run it today and it must report
28 failing surfaces (the 28 repos from §3 minus any whose surface isn't tracked in
`projects/*/agents/skills/` at all — i.e., it must enumerate every surface under
`~/.config/devman/projects/*/agents/skills/` that has at least one pool link already, assert
`writing` is among them, and fail loudly for each one that doesn't). A check that reports 0
failures against the current fleet is broken, because the fleet provably has 28 gaps today.

**Trade-off:** picking the doctor check over the reconciler means gaps can still be created
(nothing stops a composer from forgetting `writing`), but they get caught at the next doctor
run instead of being invisible indefinitely. If the reconciler is later hardened to also inject
the universal set automatically, the doctor check still earns its keep as the independent
assertion that the injection actually happened — checks and construction-time guarantees are not
substitutes for each other.

## 6. What I could not determine

- Whether the `devenv-*` family's partial (31/64, 24/64) adoption is deliberate tool-presence
  selection or a second, smaller unrolled-skill situation. Evidence is mixed: several manager
  repos (`linkman`, `copyroom`, `gitman`) have a real `devenv.nix` but never received the bundle
  (zero commits ever touching those paths), which argues against a clean tool-presence rule, but
  I did not have scope to map all 33 "without" surfaces individually to confirm or refute a
  pattern. This is a candidate for Agent A or B to pick up, or a follow-up question — I did not
  resolve it here because it falls outside "which skills are universal law."
- Why 5 surfaces lack `gitman` (`atuout`, `image-gen-pipeline`, `knappy`, `siteman`, `testee`)
  and 1 lacks `copyroom` (`tyo3`). Likely the same rollout-gap shape as `writing`, just smaller;
  not traced to specific commits.
- Whether any of the 3 repos that mention `my-ai` in prose but not the literal SKILL.md path
  (`allium-env`, `clinch`, `repoman`) have already been manually fixed versus simply phrased
  differently — not required for the headline count, so not chased further.

## What this investigation did not do

- Did not touch Agent A's territory: which symlinks exist in each central surface, or each
  repository's `.agents` plumbing mechanics (I used existence/target checks only as evidence for
  the universal/selected question, not as a plumbing audit).
- Did not touch Agent B's territory: what an `AGENTS.md` citation should say or look like after
  a fix. This document stops at "which skills are law"; it does not draft the citation text.
- Did not edit, link, or commit anything. Did not run any mutating `gitman`/`jj` command. Did
  not write or modify anything under `~/.config/devman`.
- This file (`RESEARCH-universal-skills.md`) is **untracked** in the `devman` project's git —
  it was created with a plain file write, no `gitman add`/commit ran, per instruction.
