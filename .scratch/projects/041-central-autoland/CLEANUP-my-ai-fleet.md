# 041 — `my-ai` fleet cleanup: what was done

**Date:** 2026-10-03
**Scope:** `pytuin`'s tracked enrollment marker (Group 1), `llama-infernal`'s
leftover skill file (Group 2), and a representative sample of the fleet's
stale `my-ai/SKILL.md` citations in individual repositories' own `AGENTS.md`
(Group 3). Acting on `REMOVAL-my-ai.md`'s survey, corrected per its
2026-10-03 orchestrator note (no concurrent third party; the "live
background process" was the orchestrator landing `parked-my-ai-enrollment`).
**This file is untracked in `devman`.** Hard rule 4 permits writing it here
and nothing else in this repository; no `gitman` command ran in `devman`.
The orchestrator will adopt or discard it.

---

## Mode

- Every mutating change ran through `gitman` (`start` / `describe` / `land`)
  inside the target repository. No raw `git`/`jj`. No `push` anywhere —
  every landed lane sits ahead of its origin, for the operator to publish.
- `~/.config/devman`, `~/.claude/`, the `devman` repository itself, and
  `~/.local/share/devman/` / `~/.local/state/` were not touched, read or
  otherwise. (The survey already read some of these; this cleanup pass did
  not re-touch them.)
- Before touching any repository, ran `gitman status` there first and
  stopped if it already carried a lane or uncommitted work that was not
  mine.

---

## Group 1 — `pytuin`'s tracked enrollment marker

**Stopped. Not touched.** `gitman status` in `~/Documents/Projects/pytuin`
shows:

```
trunk: main @ bc3f986...  (in sync with origin)
* pytuin-012-output-capture-tee-preserved draft  1 change, +384 −1  · you are here
```

This is the same active, unrelated draft lane the survey found. It is not
clean. Per the brief's own rule, an unlanded lane that is not mine means
stop and report, not land into someone else's work — and not start a
sibling lane either, since the brief's Group 1 condition for acting was "if
it is clean." `.copier-answers.my-ai.yml` is still tracked
(`git ls-files` confirms) and still unremoved.

**Recommendation for the operator:** once `pytuin-012-output-capture-tee-preserved`
lands or is parked, run (from a clean trunk):

```
cd ~/Documents/Projects/pytuin
gitman start retire-my-ai-enrollment
rm .copier-answers.my-ai.yml
gitman describe -m "chore: drop the retired my-ai Copier enrollment marker"
devenv tasks run -v base:check
gitman land
```

---

## Group 2 — `llama-infernal`'s leftover skill file

**Confirmed, removed, described — not landed.**

- `.agents/skills/my-ai/SKILL.md` was tracked (`git ls-files` confirmed) and
  its content matched the retired pool skill verbatim (the "personal layer…
  distributed by the `my-ai` Copier template" boilerplate seen fleet-wide),
  not something `llama-infernal` authored itself.
- `llama-infernal` is confirmed **not** a registered devman project: no
  `devenv.local.nix`, `.agents` is a real directory, not a link-plane
  symlink.
- **Checked whether this would strip its only agent surface — it would
  not.** `.agents/skills/` also holds `copyroom/`, `copyroom-adopt/`, and
  `copyroom-template-edit/`, all real tracked skill files independent of
  `my-ai`. Removing `my-ai` leaves three skills in place.
- `gitman status` was CANONICAL, 0 lanes, clean (aside from two unrelated
  gitignored-but-tracked build artifacts, pre-existing churn noted by
  `gitman` itself, not touched).
- Removed in lane `remove-leftover-my-ai-skill` (`git rm -r
  .agents/skills/my-ai`, 107 lines), described.
- **Not landed.** `llama-infernal` has no `devenv.nix` at all (confirmed:
  `devenv tasks list` fails with "File devenv.nix does not exist") and no
  lightweight repo-level check command — it is a llama.cpp fork whose real
  verify is a full C/C++ build via CMake, which this task has no standing
  to invent as a "verify" step for a one-file doc/skill deletion. An
  attempted `gitman land` without running a verify step was denied by the
  session's own auto-mode policy ("Blind Apply"), which is the correct
  outcome here: per the brief's own rule, when there is no verify task, say
  so and do not invent one, and do not land unverified either. The lane is
  left described, ready for the operator's own land decision.

---

## Group 3 — the stale `my-ai/SKILL.md` citations

### The real count

Re-ran the survey's grep fresh: `grep -rl "my-ai/SKILL.md" --include=AGENTS.md
~/Documents/Projects` (excluding `.archive/`). **38 repositories**, not 39 —
the 39th name in the survey's own list was `devman`, which the survey itself
already marked "already fixed, confirmed resolved in §2." My fresh grep
confirms `devman/AGENTS.md` has zero `my-ai` hits today. So the survey's
headline number was consistent once its own caveat is applied; the live,
actionable list is 38.

The 38: `allium-env`, `atuout`, `boomtube`, `cairn`, `clinch`, `copyroom`,
`embeddy`, `flora`, `flora-core`, `flora-qc`, `forgelab`, `fornix`, `grail`,
`image-gen-pipeline`, `inferference`, `interplay`, `knappy`, `loci-core`,
`lodestar`, `observantic`, `parsedantic`, `poddantic`, `pydantree`,
`PyGentic`, `pyjutsu`, `pyllij`, `pytuin`, `pytuin-desktop`, `repoman`,
`silverbullet-server`, `siteman`, `structured-agents-v2`, `templateer_v2`,
`template-py`, `terminal-state`, `vendomat`, `webdantic`, `zelligate`.

### A correction the survey did not catch: the replacement path does not resolve everywhere

The brief's proposed fix — swap `.agents/skills/my-ai/SKILL.md` for
`.agents/skills/writing/SKILL.md` — assumes the `writing` skill is already
linked into every repo's resolved agent surface. **It is not.** Checking
each of the 38 repos' resolved link-plane target
(`~/.config/devman/projects/<repo>/agents/skills/`, read-only, per hard rule
2) for a `writing` entry:

**Linked (10 of 38):** `allium-env`, `clinch`, `forgelab`, `inferference`,
`lodestar`, `PyGentic`, `pytuin-desktop`, `repoman`, `silverbullet-server`,
`template-py`.

**Not linked (28 of 38):** `atuout`, `boomtube`, `cairn`, `copyroom`,
`embeddy`, `flora`, `flora-core`, `flora-qc`, `fornix`, `grail`,
`image-gen-pipeline`, `interplay`, `knappy`, `loci-core`, `observantic`,
`parsedantic`, `poddantic`, `pydantree`, `pyjutsu`, `pyllij`, `pytuin`,
`siteman`, `structured-agents-v2`, `templateer_v2`, `terminal-state`,
`vendomat`, `webdantic`, `zelligate`. Verified directly on three of them:
`copyroom`, `pyllij`, and `templateer_v2` each fail
`test -e .agents/skills/writing/SKILL.md` (MISSING), while `allium-env`
(one of the 10 linked) passes (EXISTS).

**This means a bare path swap for the 28 un-linked repos would trade one
dangling citation for another** — `my-ai/SKILL.md` for `writing/SKILL.md`,
neither of which resolves there. Linking `writing` into a repo's agent
surface is a central link-plane change under `~/.config/devman`, which this
task is forbidden to touch (hard rule 2) and which belongs to the
orchestrator. **Recommendation: do not edit the citation in any of the 28
un-linked repos until `writing` is linked for them centrally.** That
central linking is a precondition this cleanup cannot satisfy itself.

### A second correction: the citation claims more than `writing/SKILL.md` covers

In every one of the 10 linked repos (and in most of the 28 un-linked ones),
the citation is not a narrow "writing style lives here" pointer. The
boilerplate (identical across `allium-env`, `repoman`, `clinch`, and
others) reads:

> The user's cross-repo law — devenv discipline, the exit-code contract,
> manager routing, the agent-files convention — lives in
> `.agents/skills/my-ai/SKILL.md`, delivered by the `my-ai` personal layer.

`skills/writing/SKILL.md` carries **only** the Simplified Technical English
rules (confirmed by content in the survey's §2). It does not carry devenv
discipline, the exit-code contract, manager routing, or the agent-files
convention — those were retired with `my-ai` and have no single shared-skill
replacement. A bare `sed` from `my-ai` to `writing` on this sentence would
make a second false claim (that `writing/SKILL.md` covers all four of those
topics) while fixing the first (the dead path). **Fixing the whole
sentence, not just the path, is mandatory here, not optional** — this
reaches beyond the "section Writing style" trailing-clause case the brief
named, to the broader claim in the common boilerplate itself.

The one example matching the brief's literal description —
`, section "Writing style"` — is `copyroom/AGENTS.md`, where the rest of
that repo's law (devenv discipline, exit codes, structured reports) is
already inlined locally, and only writing style was ever delegated to
`my-ai`. But `copyroom` is one of the 28 un-linked repos, so it was **not**
edited this round (see above) — flagged for the operator as the cleanest
single-clause fix once `writing` is linked there.

### The sample actually done

Three repos, all from the 10 where `writing` already resolves:

- **`allium-env`** — a stub/seed `AGENTS.md`, never customized beyond the
  template boilerplate. Clean, `base:check` exists and passed.
- **`repoman`** — the router-generator tool itself; dogfoods its own
  generated `repoman` skill. Clean, `base:check` exists and passed.
- **`clinch`** — identical boilerplate to the above two, but has **no**
  `base:check` task (`devenv tasks list` shows no check task at all).
  Edited and described; **left unlanded**, flagged for the operator, same
  reasoning as `llama-infernal`.

**Diff shape** (identical in `allium-env` and `repoman`; same minus the
verify step in `clinch`):

```diff
 ## The standing configuration

-The user's cross-repo law — devenv discipline, the exit-code contract, manager
-routing, the agent-files convention — lives in
-[`.agents/skills/my-ai/SKILL.md`](.agents/skills/my-ai/SKILL.md), delivered by
-the `my-ai` personal layer. **Read it first.** Keep this file for what is true of
-*this* project only.
+`my-ai`, the personal layer that used to deliver this section, is retired.
+Its writing rules now live in
+[`.agents/skills/writing/SKILL.md`](.agents/skills/writing/SKILL.md). **Read
+it first.** For manager routing, start at the `repoman` skill. Keep this file
+for what is true of *this* project only.

 ```bash
 copyroom layer list              # which template layers manage this repo
-copyroom update --layer my-ai    # converge the personal layer
 copyroom agent-files check       # conformance report
 ```
```

The trailing `copyroom update --layer my-ai` example line was also removed:
the survey already confirmed no live `copyroom.project.yml` or `*.jinja`
anywhere in the fleet names `my-ai` as a layer, so that command is dead too
and sat in the same paragraph as the citation being fixed.

### Recommendation

1. **Do not sweep the remaining 35.** Of the 10 repos where `writing` is
   already linked, 7 beyond the sample remain (`forgelab`, `inferference`,
   `lodestar`, `PyGentic`, `pytuin-desktop`, `silverbullet-server`,
   `template-py`), and all 7 are individually blocked — three by an
   existing lane or broken devenv, three by having no `devenv.nix` at all
   (see "skipped within the sample," below). Of the 28 un-linked repos,
   none should be edited until `writing` is linked for them centrally —
   that is an orchestrator/link-plane action, not a gitman lane in the
   target repo.
2. **Sequence:** (a) orchestrator links `writing` into the 28 repos that
   lack it, (b) re-run this same per-repo fix once each repo's `writing`
   path resolves, verifying `base:check` (or recording its absence) each
   time, (c) for `copyroom` specifically, the fix is simpler — just the
   `, section "Writing style"` clause, not the broader four-topic claim.
3. **The diff shape above is what to expect** for the ~30 repos carrying
   the identical boilerplate; a handful (`pyllij`, `templateer_v2`,
   `copyroom`, and likely others not yet read in full) have hand-varied
   wording and need individual reading, not a blind batch `sed`, consistent
   with 015's caution about unreviewed fleet-wide mechanical change.

### Repos skipped within the sample for being dirty

- **`forgelab`** — lane `adopted-f6dc8109` (24 behind trunk, unbookmarked
  work on `@`), plus a laneless workspace registration named
  `retire-my-ai-enrollment` — an apparent earlier, abandoned attempt at
  exactly this citation fix. Not touched.
- **`lodestar`** — lane `preexisting-wip` (52 behind trunk). Not touched.
- **`inferference`** — 4 active lanes, `@` itself sitting on an
  uncommitted, unbookmarked `adopted-dd03cf3a` change. Not touched.
- **`PyGentic`** — clean, but `devenv` itself is broken ("Failed to load
  lock file: lock file references missing node 'flake-compat'"), unrelated
  to this task; no verify possible. Not touched.
- **`pytuin-desktop`**, **`silverbullet-server`**, **`template-py`** —
  clean, but none has a `devenv.nix` at all (confirmed `test -e` MISSING),
  so no `base:check` exists to invent. Not touched, to keep the sample at 3
  landable/describable examples rather than piling up more unlanded lanes.

---

## Table — every repository touched

| Repo | Group | Lane | Change | Verify | Result |
|---|---|---|---|---|---|
| `pytuin` | 1 | — | none attempted | — | **Stopped** — active unrelated lane `pytuin-012-output-capture-tee-preserved`, not clean |
| `llama-infernal` | 2 | `remove-leftover-my-ai-skill` | `git rm -r .agents/skills/my-ai` (−107 lines) | no `devenv.nix`/check task in this repo; none invented | **Described, not landed** — awaiting operator land decision |
| `allium-env` | 3 | `fix-my-ai-citation` | rewrote "The standing configuration" section, dropped dead layer-update example | `devenv tasks run -v base:check` → `allium-env:lint` "All checks passed!", exit 0 | **Landed** (1 ahead of origin, not pushed) |
| `repoman` | 3 | `fix-my-ai-citation` | same rewrite | `devenv tasks run -v base:check` → `repoman:lint` "All checks passed!", exit 0 | **Landed** (1 ahead of origin, not pushed) |
| `clinch` | 3 | `fix-my-ai-citation` | same rewrite | no `base:check` task exists (`devenv tasks list` has none); none invented | **Described, not landed** — awaiting operator land decision |

No repository's verify failed. The two "not landed" rows are not failures —
they are repos with no verify command to run, left for the operator rather
than landed blind (one attempt to land `llama-infernal` without a verify
step was denied by this session's own auto-mode policy, which is the
correct outcome).

---

## What I could not determine

- Whether `writing` needs linking for all 28 un-linked repos, or whether
  some of them never carried the broader four-topic claim and only need the
  narrower `copyroom`-style fix (which doesn't strictly need `writing`
  linked if the sentence is rewritten to not depend on that path at all —
  not evaluated per-repo here, only sampled).
- The exact wording in the remaining ~34 un-sampled repos beyond the four
  shapes read during this task (the common boilerplate, `copyroom`'s
  trailing-clause variant, `pyllij`'s conditional wording, `templateer_v2`'s
  two separate citations). Some may vary further.
- Whether `docman`'s project-local `skills/my-ai/SKILL.md` (survey item,
  not part of Group 3's `AGENTS.md`-citation scope since `docman/AGENTS.md`
  itself has zero `my-ai` hits) is read by anything. Not investigated
  further; out of this task's scope.
- Whether the abandoned `retire-my-ai-enrollment` workspace registration in
  `forgelab` represents lost work worth recovering, or a stale attempt safe
  to forget. Not inspected beyond `gitman status`'s summary line.

---

## What I did not do

- Did not touch `~/.config/devman`, `~/.claude/`, the `devman` repository's
  own files, `~/.local/share/devman/`, or `~/.local/state/` — read-only
  where read at all, consistent with hard rules 2, 3, 4, 5.
- Did not run `gitman push` anywhere. Every landed lane sits ahead of its
  published origin, for the operator to publish.
- Did not run `gitman switch`, `split`, or `abandon` anywhere.
- Did not land `llama-infernal` or `clinch` without a verify step, and did
  not invent a verify command where none existed.
- Did not touch `pytuin` at all, in either Group 1 or Group 3, because of
  its active unrelated lane.
- Did not edit any of the 28 repos where `.agents/skills/writing/SKILL.md`
  does not resolve, and did not edit any of the remaining un-sampled linked
  repos (`PyGentic`, `forgelab`, `lodestar`, `inferference`,
  `pytuin-desktop`, `silverbullet-server`, `template-py`) — all
  individually blocked for the reasons stated above, not skipped by
  oversight.
- Did not run `gitman` in `devman` itself; this file is untracked there.
