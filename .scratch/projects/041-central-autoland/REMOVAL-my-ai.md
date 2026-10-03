# 041 — `my-ai` removal: survey and operator commands

**Date:** 2026-10-03
**Scope:** every `my-ai` artefact on this machine — the Copier template repo, the
`copyroom update --layer my-ai` distribution path, the central pool skill, the
central per-project symlinks, the registered devman project, and the two
governing-document citations.
**Mode:** investigation and read-only survey. **No mutating `gitman`/`jj`
command ran anywhere. No write to `~/.config/devman` or `~/.claude/`.** One
exception, stated in full in §5: zero files were deleted by this agent;
everything reported as "removed" in this survey window was removed by
concurrent activity outside this agent's control, not by this agent.

**This report corrects 035 §9 against today's machine state. 035 itself is a
historical record and was not changed.**

---

## 0. Headline finding, before the detail

`035-config-repo-cleanup/README.md` §9 (2026-09-10) described `my-ai`
retirement as a ~62-lane undertaking "not part of this cleanup," deferred to
later. **It is not deferred any more. As of today it is almost entirely done,**
and it was done in the order 035 §9.3 prescribed: fleet crossover first,
template archival second. The one ordering mistake the brief warned about —
archiving the template before the fleet crossed over — **did not happen.**

While this survey was running, a **live background process in this same
machine mutated `~/Documents/Projects/devman` out from under the survey**:
`devman`'s `.copier-answers.my-ai.yml` existed, was read, and then was gone
eight minutes later, landed by commit `dc2c15e` ("parked: the my-ai enrollment
deletion, carved out of 041") whose own message says *"deleted in devman's
working copy by another session's my-ai retirement work (035 §9's roadmap)."*
**The operator (or another agent) is already executing this exact retirement,
concurrently with this survey.** Treat every count below as a snapshot, not a
ceiling — re-run the verification command before acting on any of them.

---

## 1. The crossover measurement

| Measure | Count | Detail |
|---|---|---|
| `.copier-answers.my-ai.yml`, live & non-fixture | **2 at survey start → 1 now** | `devman` (removed by the concurrent process mid-survey, commit `dc2c15e` on its `main`) and `pytuin` (still tracked, sitting inside pytuin's own active lane `pytuin-012-output-capture-tee-preserved`) |
| `.copier-answers.my-ai.yml`, archived-repo copies | 5 | `.archive/my-ai`, `.archive/fleetman`, `.archive/foreman`, `.archive/siteman`, `.archive/flora-037-part-e` — historical, not live |
| `.copier-answers.my-ai.yml`, template-nix fixtures | 4 | `template-nix/template/`, `/generated/nix/{basic,home}/`, `/golden/nix/{basic,home}/` — template-nix's own Nix-flake templating payload/golden fixtures, unrelated to the `my-ai` genome; flagged, not acted on |
| Repos with `.agents` as a real (non-crossed) directory | **1** | `llama-infernal` — not a registered devman project at all (no `devenv.local.nix`, absent from every registry checked); its `.agents/skills/my-ai/SKILL.md` is tracked leftover content from a `my-ai` Copier enrollment it explicitly removed in its own commit `80d1ed1dc chore: remove my-ai Copier enrollment` |
| Repos with `.agents` as a link-plane symlink into `~/.config/devman/projects/<name>/agents` | **39 sampled, 39/39** | Every repo whose own `AGENTS.md` still names `my-ai/SKILL.md` was checked individually; all 39 already resolve through the symlink. A full top-level sweep of `~/Documents/Projects/*` found no other repo with a real (uncrossed) `.agents` besides `llama-infernal` |
| Repos with no `.agents` at all | 4 | `agentfs`, `devman-spike`, `talkee-futo`, `template-nix` — never enrolled, not a crossover concern |
| Central pool `agents/skills/my-ai` symlinks, trunk of `~/.config/devman` | **0** | `git ls-tree -r main` — zero matches for `agents/skills/my-ai$` across all 77 registered projects in trunk |

**Conclusion: crossover is functionally complete.** The only repository still
depending on real (non-link-plane) `my-ai` content is `llama-infernal`, and it
already severed its own Copier enrollment — it depends on nothing going
forward, it just has unswept leftover text.

---

## 2. `skills/writing/` — does it exist, and does it carry the STE rules?

**Yes, confirmed by content, not by name alone.** `~/.config/devman/skills/writing/SKILL.md`
is tracked on trunk (`git ls-tree main` → `skills/writing`, blob `bef6ccaf…`) and
its text opens: *"This skill holds the user's standing writing rules. It moved
out of `my-ai` so a repository can select it without carrying the rest of that
skill's law."* It then restates the full Simplified Technical English rule set
(one idea per sentence, active voice, one word per meaning, imperative
instructions, no filler, spell out abbreviations, no slang). **§8.5's move
happened.** Removing `skills/my-ai/` — which is already gone from trunk — does
**not** dangle the operator's own writing law; it already has a home.

Both governing-document citations named in 035 §9.2 were checked fresh:

| Citation | State |
|---|---|
| `devman/AGENTS.md` | **Fixed.** Line 111 now reads `...no filler. See \`.agents/skills/writing/SKILL.md\`.` No `my-ai` string remains anywhere in the file |
| `~/.claude/CLAUDE.md` | **Fixed.** Its "Writing style" section (shown to this agent in-conversation) already cites `.agents/skills/writing/SKILL.md` |
| `~/.claude/AGENTS.md` | **Still dangling.** Line 18: *"Full rules live in the personal layer: `.agents/skills/my-ai/SKILL.md`, section 'Writing style' (in repos that carry the layer)."* The target no longer exists anywhere in the fleet. This is a real, live broken citation, in a file this agent may not write to (hard rule 4) |

---

## 3. Full inventory, classified

| # | Artefact | Classification | Evidence |
|---|---|---|---|
| 1 | Template repo `~/Documents/Projects/my-ai` | **LEAVE: already retired correctly** | Does not exist at that path. Lives at `~/Documents/Projects/.archive/my-ai`, still a real git repo (`.git` present), last two commits `c5a4824 chore: stop shipping my-ai skill from template` then `74f35c5 chore: retire this repository from the devman automation plane` — the precondition-then-archive order 035 §9.3 step 4 asked for |
| 2 | `copyroom update --layer my-ai` distribution path | **SAFE: already severed** | No live `copyroom.project.yml` or `*.jinja` anywhere in the fleet names `my-ai` as a layer (`grep -rl my-ai --include=copyroom.project.yml --include=*.jinja`, excluding `.archive` → empty) |
| 3 | `~/.config/devman/skills/my-ai/` (pool content) | **SAFE: already gone from trunk** | `git ls-tree -r main -- skills/my-ai` → 0 entries. Not on disk in the default workspace either |
| 4 | `~/.config/devman/skills/writing/` | **LEAVE: the §8.5 replacement, already live** | See §2 |
| 5 | Central per-project `agents/skills/my-ai` symlinks | **SAFE: already 0** | `git ls-tree -r main` across all 77 projects → 0 matches |
| 6 | `~/.config/devman/projects/my-ai/` (registered devman project) | **LEAVE: already archived on trunk** | `git ls-tree main -- projects/my-ai` → empty; `git ls-tree main -- projects/.archive/my-ai` → `devenv.local.nix`, `links.yaml`. §9.3 step 5 is decided: archived |
| 7 | **Default workspace of `~/.config/devman` itself** | **OPERATOR DECISION — do not let an agent touch this** | `gitman status` there: `@` is parked on an ancestor (`174c902d`) well behind trunk, carrying 60 leftover uncommitted deletions (the 59 symlinks + `skills/my-ai/SKILL.md`) plus unrelated `forgelab`/`fornix-*` additions. Three parked lanes (`parked-paloma-*`) and three no-lane workspace registrations (`65-gitman-skill-sync`, `fix-mnemonix-empty-surface`, `retire-my-ai-links`) sit alongside it. This is exactly the live-write hazard 035 §6 described. **I did not run `gitman switch --trunk`, `repair`, or any lane command here** — hard rule 1/2 |
| 8 | DAG symlinks `~/.local/share/devman/dags/my-ai.{check,maintain,test}.yaml` | **SAFE TO REMOVE AFTER devman doctor --prune confirms them stale** | All three are dangling symlinks to `../projects/my-ai/workflows/*.yaml`, a path that no longer exists in `~/.local/share/devman/projects/` (my-ai is absent from that registry entirely). Registry-owned; not hand-edited by this agent per the brief's own rule on `.devman-link-state.json`, extended here to the sibling `dags/` registry on the same reasoning |
| 9 | `~/.config/devman/.devman-link-state.json` | **LEAVE: already clean** | `grep -c my-ai` → 0. Nothing to prune there |
| 10 | `.copier-answers.my-ai.yml`, `devman` | **Removed by the concurrent process, not by this agent** | Present at survey start, gone eight minutes later; devman's `main` now at `ed898d0`, ancestor `dc2c15e` carries the deletion. See §0 |
| 11 | `.copier-answers.my-ai.yml`, `pytuin` | **REMOVE AFTER pytuin's own lane lands, or in a fresh lane** | Tracked (`git ls-files` confirms), sitting inside pytuin's already-active, unrelated draft lane `pytuin-012-output-capture-tee-preserved`. Not safe to fold into someone else's unrelated draft |
| 12 | `.agents/skills/my-ai/SKILL.md`, `llama-infernal` | **OPERATOR DECISION, own lane** | Tracked, real file, leftover after that repo's own `80d1ed1dc chore: remove my-ai Copier enrollment`. Repo is jj-colocated but outside the devman project registry — housekeeping only, nothing depends on it |
| 13 | `~/.claude/AGENTS.md:18` citation | **OPERATOR ACTION — this agent may not write here** | Dangling; see §2 |
| 14 | ~39 individual repos' own `AGENTS.md` citing `.agents/skills/my-ai/SKILL.md` | **OPERATOR DECISION — large, separate, fleet-wide doc fix** | Full list in §4. Each is its own git repo; a fix is ~39 one-line edits across 39 lanes, inherited boilerplate from the old `my-ai` template's `AGENTS.md.jinja`, not part of this task's explicit scope |
| 15 | `template-nix`'s 4 `.copier-answers.my-ai.yml` fixture/payload copies | **OPERATOR DECISION — needs template-nix domain knowledge** | Could be load-bearing golden-master fixtures for an unrelated Nix-flake template system; not verified either way |
| 16 | `~/.config/devman` workspace registrations with no lane (`65-gitman-skill-sync`, `fix-mnemonix-empty-surface`, `retire-my-ai-links`) | **OPERATOR DECISION** | `gitman workspace list` shows all three as `[no lane]`. `retire-my-ai-links` in particular looks like an abandoned earlier attempt at exactly this retirement, superseded by whatever path actually landed it on trunk |
| 17 | `.scratch/`/`.loci/` historical records (035, this file's own future readers, `linkman/.loci/projects/001-devman-cutover/*`) | **LEAVE: HISTORICAL RECORD, do not rewrite** | These describe what was true when written. 035 is correct for 2026-09-10; this file supersedes it only by addition, dated separately |

---

## 4. The 39 repos whose own `AGENTS.md` still names `my-ai/SKILL.md`

All verified to already have `.agents` as a link-plane symlink (so the
citation target does not resolve, but the repo itself has crossed over):

`allium-env`, `atuout`, `boomtube`, `cairn`, `clinch`, `copyroom`, `embeddy`,
`flora`, `flora-core`, `flora-qc`, `forgelab`, `fornix`, `grail`,
`image-gen-pipeline`, `inferference`, `interplay`, `knappy`, `loci-core`,
`lodestar`, `observantic`, `parsedantic`, `poddantic`, `pydantree`, `PyGentic`,
`pyjutsu`, `pyllij`, `pytuin`, `pytuin-desktop`, `repoman`,
`silverbullet-server`, `siteman`, `structured-agents-v2`, `templateer_v2`,
`template-py`, `terminal-state`, `vendomat`, `webdantic`, `zelligate`, `devman`
(already fixed, listed in the original grep hit list but confirmed resolved in
§2).

`docman` also has a stray copy at `skills/copyroom-adopt/SKILL.md`,
`skills/copyroom/SKILL.md`, and `skills/my-ai/SKILL.md` under its own
project-local `skills/` tree (not `.agents/`) — a separate, project-owned copy
rather than a link-plane citation; worth a look in that repo's own lane but
not counted above.

---

## 5. What this agent actually removed

**Nothing.** Zero `rm`, zero `git rm`, zero edit, in any repository, at any
point in this task. Every change recorded in this report — devman's
`.copier-answers.my-ai.yml` disappearing — was made by a process outside this
agent's control while the survey was in progress (confirmed by the commit
`dc2c15e`'s own message, authored by "another session").

This departs from the brief's Step 2, which expected this agent to delete
unambiguously-safe, untracked `.copier-answers.my-ai.yml` markers directly.
By the time each candidate was fully verified:

- `devman`'s copy had already been deleted by someone else.
- `pytuin`'s copy is tracked and inside another active, unrelated lane — not
  a safe solo deletion per the brief's own rule ("each such repository is its
  own git repository... needs its own lane").

So there was no candidate left that was simultaneously *safe*, *untracked*,
and *not already claimed by other in-flight work*. A survey plus a correct
plan, with nothing touched, is the conservative outcome the brief asked for
when in doubt.

---

## 6. Operator sequences, in dependency order

### Group A — fix the one dangling citation this agent cannot touch

No dependency. Do this first; it is one line.

```bash
sed -n '18p' ~/.claude/AGENTS.md   # confirm it still reads the old path first
sed -i 's#\.agents/skills/my-ai/SKILL\.md#.agents/skills/writing/SKILL.md#' ~/.claude/AGENTS.md
grep -n "writing/SKILL.md" ~/.claude/AGENTS.md   # post-check
```

Rollback: restore the single line manually; no git is involved in `~/.claude/`.

### Group B — `pytuin`'s enrollment marker

Depends on nothing else here, but **land it separately from the repo's
current draft lane** (`pytuin-012-output-capture-tee-preserved`) so an
unrelated change doesn't ride along in that commit.

```bash
cd ~/Documents/Projects/pytuin
G=/home/andrew/Documents/Projects/gitman/.devenv/state/venv/bin/gitman
$G status                                   # confirm current lane first
$G start retire-my-ai-enrollment
rm .copier-answers.my-ai.yml
$G describe -m "chore: drop the retired my-ai Copier enrollment marker

my-ai's distribution path and pool skill are retired fleet-wide (035 §9).
.agents is already a link-plane symlink here, so this file is a dead
enrollment record with nothing left reading it."
$G status                                   # expect the new lane, 1 change
# verify, then:
$G land
$G status && $G doctor                      # expect clean
```

Rollback: `gitman undo` immediately after, or `gitman undo --op <id>` from
`gitman undo --list`.

### Group C — the 39-repo citation sweep (and `docman`'s project-local copies)

Depends on nothing upstream; independent of A and B. **This is 39+ separate
lanes in 39+ separate repositories** — do not batch them into one commit
spanning repos; each repo lands its own.

Per-repo template (repeat with the repo name substituted):

```bash
cd ~/Documents/Projects/<repo>
G=/home/andrew/Documents/Projects/gitman/.devenv/state/venv/bin/gitman
grep -n "my-ai/SKILL.md" AGENTS.md
$G start fix-my-ai-citation
sed -i 's#\.agents/skills/my-ai/SKILL\.md#.agents/skills/writing/SKILL.md#' AGENTS.md
$G describe -m "docs: point the writing-style citation at skills/writing, not my-ai

my-ai's pool skill is retired; the Simplified Technical English rules moved
to skills/writing (035 §8.5/§9.2). This repo's .agents is already a
link-plane symlink, so the old citation pointed at nothing."
$G status
$G land
```

Full repo list: see §4.

### Group D — `llama-infernal`'s leftover tracked file

Independent of A–C. This repo is jj-colocated but outside the devman
registry, so treat it like any other project repo:

```bash
cd ~/Documents/Projects/llama-infernal
G=/home/andrew/Documents/Projects/gitman/.devenv/state/venv/bin/gitman
git log --oneline -- .copier-answers.my-ai.yml   # re-confirm enrollment is gone
$G start remove-leftover-my-ai-skill
git rm -r .agents/skills/my-ai
$G describe -m "chore: remove leftover my-ai skill content

This repo's Copier enrollment in my-ai was removed in 80d1ed1dc, but the
skill directory itself was never swept. my-ai is now retired fleet-wide."
$G status
$G land
```

### Group E — the DAG registry cruft

Depends on nothing. **Do not delete these symlinks by hand** — they live in
`~/.local/share/devman/dags/`, a devman-owned registry parallel to
`.devman-link-state.json`. Use the sanctioned tool:

```bash
devman doctor --prune
find ~/.local/share/devman/dags -iname "my-ai.*"   # expect empty afterward
```

If `--prune` does not clear them, that is a devman finding to report upstream,
not a reason to `rm` them directly.

### Group F — `~/.config/devman`'s own stale workspace, lanes, and default-workspace drift

**Do this last, and only the operator should run it — not an agent.** This
is the live central repository the hard rules forbid mutating.

```bash
G=/home/andrew/Documents/Projects/gitman/.devenv/state/venv/bin/gitman
# 1. Inspect first, mutate nothing yet:
$G --repo ~/.config/devman status
$G --repo ~/.config/devman workspace list

# 2. The three parked-paloma-* lanes and the no-lane registrations
#    (65-gitman-skill-sync, fix-mnemonix-empty-surface, retire-my-ai-links)
#    are stale. Decide per lane whether its content is still wanted before
#    doing anything destructive:
$G --repo ~/.config/devman workspace prune        # clears empty [no lane] registrations only

# 3. The default workspace is parked behind trunk (@ on 174c902d, trunk at
#    076c57957e74 or later by now). Re-park it onto trunk, which keeps any
#    uncommitted work rather than discarding it:
$G --repo ~/.config/devman switch --trunk

# 4. Re-check what the 60 leftover "D" lines become once @ is current.
#    If they vanish (because trunk already carries the same retirement),
#    nothing further is needed. If real, unintended new deletions remain
#    (the forgelab/fornix-* additions in particular), handle those as their
#    own lane before touching anything else.
$G --repo ~/.config/devman status
```

Rollback at every step: `gitman undo` (whole-intent) or `gitman undo --op <id>`.

### Group G — archiving the template repo

**Already done. Nothing to run.** `~/Documents/Projects/.archive/my-ai` is
the archived copy, moved there after `my-ai`'s own template-stripping commit
and its automation-plane retirement, both of which post-date the fleet
crossover measured in §1. No action needed; recorded here only to answer the
brief's explicit question.

---

## 7. What I could not determine

- **Who or what is running the concurrent retirement activity** in
  `~/Documents/Projects/devman` right now. The commit message names "another
  session," not a person or a specific tool; I did not inspect running
  processes to identify it.
- **Whether every one of the original ~62 distribution-reached repositories
  has been individually accounted for.** The original 62-repo list from 035
  is not preserved anywhere this agent found. The 100%-crossover conclusion
  in §1 rests on an exhaustive top-level sweep of `~/Documents/Projects/*`
  finding no counter-example besides `llama-infernal`, not on checking 62
  names one by one against a preserved list.
- **Whether the `my-ai.*` DAG symlinks in §3 item 8 are registered as active,
  scheduled jobs in `dagu`**, or are simply dead files nobody references. I
  did not query `dagu`'s own job list; I only confirmed the symlinks are
  dangling on disk.
- **Whether `docman`'s project-local `skills/my-ai/SKILL.md` copy (§4) is
  read by anything**, or is dead weight left over from before that project's
  own link-plane crossover.
- **Whether `template-nix`'s 4 fixture copies of `.copier-answers.my-ai.yml`
  are load-bearing golden-master test fixtures** or simply stale. This needs
  template-nix domain knowledge this survey did not acquire.

---

## 8. What I did not do

No `gitman start`, `describe`, `land`, `switch`, `split`, `sync`, `push`,
`undo`, `repair`, `workspace prune`, or `workspace forget` ran, in any
repository, at any point. No raw `git add`, `commit`, `rm`, or file edit ran
in `~/.config/devman`. No file in `~/.claude/` was written, and
`.credentials.json` was never opened. No fixture, lane, or parked workspace in
the central repository was touched, inspected beyond read-only `status` /
`log` / `workspace list` / `doctor`, or acted on. The `.devman-link-state.json`
ledger and the `~/.local/share/devman/dags/` registry were read and reported
on, never hand-edited. Nothing in any of the 39 project repos listed in §4,
`llama-infernal`, or `pytuin` was edited — every change proposed for them is a
command for the operator to run, not an action this agent took.

---

## Correction — 2026-10-03, by the orchestrator

**The "live background process mutating devman" was this session.**
This document reports that `devman`'s `.copier-answers.my-ai.yml` existed and
then vanished via commit `dc2c15e`, concludes that "someone or something else is
actively executing this exact task concurrently", and advises treating every
count as a snapshot. **The actor was the orchestrator.**

The operator asked for my-ai to be removed. A lane named
`parked-my-ai-enrollment` already held exactly that deletion, carved out of an
earlier lane. The orchestrator landed it, which produced `dc2c15e`. The commit
message's reference to "another session's my-ai retirement work" describes where
the deletion *originally* came from, not a third party acting during the survey.

Nothing was racing this survey. The snapshot caution is still sound advice in
general, and the count it affects — enrolled repositories — is one lower than
reported for that reason.

**The report's substantive conclusions stand and were independently
re-verified:** `~/.config/devman/skills/my-ai/` is gone; `skills/writing/SKILL.md`
is present, so removing my-ai does not dangle the operator's writing law; and the
template was archived *after* fleet crossover, so 035 §9.3 step 4's ordering
mistake did not occur.

### Confirmed, and the two that still need action

1. **`~/.claude/AGENTS.md:18` still cites the dead path.** Verified:
   `.agents/skills/my-ai/SKILL.md`, where `~/.claude/CLAUDE.md:18` correctly
   cites `.agents/skills/writing/SKILL.md`. This is the same defect project 041
   recorded as open question **O6**, and the `handoff/` package already carries
   the full fix — one canonical central file plus two symlinks. Prefer that over
   a one-line `sed`, because the two files being separate copies is the actual
   defect; correcting one of them leaves the copy.
2. **Three dangling my-ai DAG links.** Verified dangling:
   `~/.local/share/devman/dags/my-ai.{check,maintain,test}.yaml` all point at
   `../projects/my-ai/workflows/`, which no longer exists. They sit in the
   **legacy** registry root, which `devman doctor --prune` does not own, so they
   will not clear themselves.
