# Research — the 35 stale skill citations: what the sentence should say, and where it should come from

**Date:** 2026-10-03
**Scope:** the 35 tracked `AGENTS.md` files that hand-write a path into the
link plane (`.agents/skills/my-ai/SKILL.md`), and the mechanism question of
where a skill citation should live. Does **not** cover which symlinks exist
in which repository — that is a separate audit, running in parallel.
**Mode:** read-only investigation. Nothing was mutated: no file edited, no
`gitman`/`jj` write command run anywhere, no write under `~/.config/devman`.
**This file is untracked in `devman`.** `.scratch/` is tracked on purpose in
this repository, so `git status` will show it as a new, unstaged file — it
was not added or committed.

## Recommendation, in five lines

Stop citing a central-pool skill path from `AGENTS.md` at all. Three of the
four claimed topics (devenv discipline, the exit-code contract, manager
routing) already have a correct home: the generated `repoman/SKILL.md`
router, which **cannot** name a skill the pool has not linked, because it
filters its routing rows by `.is_file()` on disk
(`repoman/src/repoman/skills.py:75`). Inline those three topics' one-line
statements and the agent-files convention directly in `AGENTS.md` as
repo-owned prose — exactly what `template-py/template/AGENTS.md` already
does today, as of commit `4870b1b` (2026-09-19) — and point a cold reader at
`repoman` by name, not by a pool path. The deciding fact: a disk-rendered
router cannot dangle; 35 hand-written copies of a central path always can.
The trade conceded: a cold reader (no devenv shell) cannot click through to
live skill content — only to the static prose now inlined in `AGENTS.md`.

---

## 1. The citation text, and what it claims

Fresh survey, 2026-10-03, `grep -rl '\.agents/skills/my-ai/SKILL\.md' --include=AGENTS.md ~/Documents/Projects`,
excluding `.archive/`: **35 live repositories**, not the 38-39 an earlier
same-day pass (`CLEANUP-my-ai-fleet.md`, `REMOVAL-my-ai.md`) recorded —
`allium-env`, `repoman`, and `clinch` were edited since by that same pass
(landed for the first two; described-but-unlanded for `clinch`, which still
changes its working tree). Treat 35 as today's count, not a ceiling.

| Variant | Repositories | Count |
|---|---|---|
| **A — the four-topic boilerplate.** *"The user's cross-repo law — devenv discipline, the exit-code contract, manager routing, the agent-files convention — lives in `.agents/skills/my-ai/SKILL.md`, delivered by the `my-ai` personal layer. **Read it first.** Keep this file for what is true of *this* project only."* | `atuout`, `boomtube`, `cairn`, `embeddy`, `flora`, `flora-core`, `flora-qc`, `forgelab`, `fornix`, `grail`, `image-gen-pipeline`, `inferference`, `interplay`, `knappy`, `loci-core`, `lodestar`, `observantic`, `parsedantic`, `poddantic`, `pydantree`, `PyGentic`, `pyjutsu`, `pytuin`, `pytuin-desktop`, `silverbullet-server`, `siteman`, `structured-agents-v2`, `template-py` (its own repo-root file, distinct from the fixed `template/AGENTS.md` payload), `terminal-state`, `vendomat`, `webdantic`, `zelligate` | 32 |
| **B — writing-only, narrow.** *"Write in Simplified Technical English (ASD-STE100) style. The rules live in the personal layer: `.agents/skills/my-ai/SKILL.md`, section 'Writing style'."* | `copyroom` | 1 |
| **C — conditional, hedged.** *"...The cross-repository agent-file convention lives in `.agents/skills/my-ai/SKILL.md` when the personal layer is installed."* | `pyllij` | 1 |
| **D — two separate citations in one file**, one narrative ("Read it first. It defines the standing environment, verification, version-control, and writing rules.") and one ownership ("The personal layer owns `.agents/skills/my-ai/SKILL.md`. Change that skill in its source repository, then materialize the update here."). | `templateer_v2` | 1 |

Variant A is the common boilerplate the brief expected. **The four-topic
claim is real** — Variant A literally names four things, and three other
variants either repeat or narrow the same claim.

### Does `writing/SKILL.md` carry all four? No — confirmed by content.

`~/.config/devman/skills/writing/SKILL.md` (34 lines) opens: *"This skill
holds the user's standing writing rules. It moved out of `my-ai` so a
repository can select it without carrying the rest of that skill's law."* Its
entire body is the Simplified Technical English rule set. **It carries one
of the four claimed topics (writing style is not even one of the four named —
Variant A doesn't mention writing at all). It carries zero of Variant A's
four: devenv discipline, the exit-code contract, manager routing, the
agent-files convention.** A bare path swap from `my-ai` to `writing` would
replace a dangling citation with a citation that resolves but asserts
something false.

### Where do the four topics live today?

`~/.config/devman/skills/my-ai/` is gone from trunk entirely (`git ls-tree -r
main -- skills/my-ai` → 0 entries, confirmed in `REMOVAL-my-ai.md` §1 and
re-confirmed here) — not merely re-delivered differently, as `035
§8.4/§9`'s original plan said ("keep `skills/my-ai/SKILL.md`... as pool
content delivered by symlink"). That plan did not survive; the content was
retired outright, not relocated.

| Claimed topic | Shared home today |
|---|---|
| Devenv discipline ("run everything inside `devenv shell`") | **`repoman/SKILL.md`**, the generated router, line 12 of its template (`repoman/src/repoman/templates/entrypoint.SKILL.md.j2:12`): *"Run everything inside `devenv shell`."* Also now inlined directly, as static prose, in the current `template-py/template/AGENTS.md`. |
| Exit-code contract (`0`/`1`/`2`/`3`) | Same router line 12: *"Exit codes: `0` ok · `1` decision · `2` infra/config · `3` usage."* Also inlined in `template-py/template/AGENTS.md` ("Exit codes are an API..."). |
| Manager routing | The router's routing table (`entrypoint.SKILL.md.j2:21-29`), populated only with managers whose skill file is actually present on disk (`skills.py:75`, see §2). |
| Agent-files convention | **No shared skill carries this any more.** `template-py/template/AGENTS.md`'s own `## Agent-files convention` section states it directly, as repo-owned tracked prose — not delegated to any skill, pool or otherwise. |

So the honest fix is not "cite a different skill" — it is "stop promising a
single skill carries all four," because one of the four has no skill home at
all, and the other three live in a **per-repository generated file**, not a
single shared pool path a sentence could name once and have it stay true
everywhere.

---

## 2. The mechanism: does anything auto-load `.agents/skills/`, and does the router render from disk?

### Auto-load — 025 §7.1's claim holds, with one footnote

`CONCEPT.md:544` (`~/Documents/Projects/devman/.scratch/projects/025-the-link-plane/CONCEPT.md`):
*"Nothing auto-loads `.agents/skills/`. An agent opens those files by path,
because `AGENTS.md` or the router points at them."* No code found anywhere
in `repoman` or `copyroom` that reads a `SKILL.md` body without that body
being requested by path. **Footnote:** the Claude Code harness itself scans
`.claude/skills/` (bridged from `.agents/skills/` by a symlink, `CONCEPT.md
§7.2`) to build its own skill-trigger listing from each file's YAML
frontmatter — so frontmatter metadata is read unconditionally, even though
the body text still is not. This is a narrower claim than 7.1's literal
wording but does not change the citation argument: the question that matters
here is whether an agent ever reads a skill's *content*, and that still
requires something — `AGENTS.md`, the router, or an explicit invocation — to
point at it by path.

### The router renders from disk — confirmed, and this is the decisive finding

`repoman install-skills` (`repoman/src/repoman/cli.py:305-315`) calls
`install_entrypoint` (`repoman/src/repoman/skills.py:86-103`), which calls
`render_entrypoint` (`skills.py:64-83`). The critical line:

```python
# repoman/src/repoman/skills.py:75
present = [m for m in ordered if (skills_root / m.skill / "SKILL.md").is_file()]
```

`rows` (line 81) is built only from `present`. **The router cannot name a
manager skill that is not an actual file on disk at render time.** This
matches `CONCEPT.md §7.5`'s requirement exactly (*"It must render routes from
what is on disk, not from the roster"*) and shows the requirement is
implemented, not aspirational.

One structural limit: this makes the router **correct**, not **complete**.
It only ever lists `*man` manager skills (`copy`/`git`/`test`/`doc`/etc. from
the `REGISTRY` in `repoman/src/repoman/registry.py`) — never the
non-manager, domain-specific, or pool "literacy" skills (`writing`,
`devenv-authoring`, and so on). Those still need `AGENTS.md`, or the skill's
own `auto_trigger` frontmatter, to be discoverable at all.

### The generated router is already gitignored — the project already treats it as a projection

`~/.config/devman/.gitignore`:

```
# Generated routers: `repoman install-skills` rewrites
# projects/<p>/agents/skills/repoman/SKILL.md at every repoman-sync. Generated,
# not authored — ignore them so a sync does not churn the tree.
projects/*/agents/skills/repoman/SKILL.md
```

Confirmed present, exact path. The central repository already does not track
the router's rendered output — only the roster that produces it. This is the
same source/projection split `CONCEPT.md §P2` demands of everything else; the
router already obeys it. The 35 `AGENTS.md` files are the one place that
still does not.

---

## 3. The options, compared

| Option | Files touched now | Recurs on next pool rename? | What a cold reader sees |
|---|---|---|---|
| **(a) Swap the path in all 35** | 35, each its own lane | **Yes** — any future rename breaks the same 35 again | A citation to a skill most of these repos do not even have linked yet (prior audit: 10/38 linked, 28/38 not — see `CLEANUP-my-ai-fleet.md`). Also still false: `writing/SKILL.md` does not carry 3 of the 4 claimed topics. Not a one-line fix — it needs the precondition (link `writing` everywhere) plus a rewrite of the claim itself. |
| **(b) Stop citing a skill path; let the generated router carry the routes** | 35, once, to remove the dangling sentence and inline what survives | **No** — the router is regenerated from disk every sync; nothing tracked names a pool path any more | Loses the live, warm-reader routing table (needs `devenv shell` anyway, per `CONCEPT.md §7.1` — a cold reader gets nothing from it either way). `CONCEPT.md §7.4` already concedes *"cold readers see no skills."* They still get the devenv-discipline/exit-code/agent-files prose, now inlined instead of delegated. Close to what `template-py/template/AGENTS.md` already does. |
| **(c) Cite by name, not by path** (e.g. "the `repoman` skill") | 35, once | Survives a path/location rename; breaks if the skill is ever renamed | Keeps a pointer a cold reader can at least search for; loses clickability. |
| **(d) Template-delivered line, one edit propagates** | **Does not work as hoped.** Only 10 of the 35 even have a live `copyroom.project.yml` (`flora`, `flora-core`, `flora-qc`, `forgelab`, `image-gen-pipeline`, `inferference`, `lodestar`, `poddantic`, `pyllij`, `pytuin`) — the other 25 have no Copier relationship to any template at all, confirmed by absence of `copyroom.project.yml`. Of those 10, the offending section is not even owned by `template-py`'s own genome — it was seeded once by the now-retired `my-ai` *layer*, whose own `copier.yml` sets `_skip_if_exists: ["AGENTS.md"]` (`~/Documents/Projects/.archive/my-ai/copier.yml:33-34`), explicitly so no future layer update ever overwrites a repo's own file. `template-py/template/AGENTS.md` itself dropped this section entirely on 2026-09-19 (commit `4870b1b`) — there is no live template content to converge toward even for the 10. | N/A — there is no propagation path | N/A |
| **(e) Fix only the symlinks, leave the 35 as-is** | 0 | **Yes**, and worse — the sentence stays false even once the path resolves, because `writing/SKILL.md` never carried 3 of the 4 claimed topics | Reader follows a now-live link to a skill that does not say what the sentence claims it says |

---

## 4. Recommendation, stated in full

**(b), done the way `template-py/template/AGENTS.md` already does it**, with
a name-only pointer at `repoman` for the live manager-routing detail (a
light (c)). Concretely, replace Variant A/B/C/D's citation sentence with:

- One line restating devenv discipline and the exit-code contract directly
  (static prose — these never change often enough to need a generated
  source).
- "For manager routing, start at the `repoman` skill" (no path — the
  generated router is per-repository and gitignored; naming it by path would
  itself be a copy of a path that differs nowhere, so naming it is enough).
- The agent-files convention restated directly, as this repository's own
  prose, because no shared skill carries it any more.

**The single fact that decides this:** `repoman/src/repoman/skills.py:75`
filters the router's content to what `.is_file()` finds on disk, so that one
generated file **cannot** go stale the way a hand-written path can. Routing
35 tracked files through a mechanism that is structurally unable to dangle
is a better bet than re-synchronizing 35 copies by hand, now and at every
future rename.

**What this trades away:** the 35 edits still have to happen by hand, once —
option (d)'s hope of a free propagation does not hold, so this is exactly as
expensive *today* as (a) or (c). The win is only in the future: zero of
these files will ever need touching again for a pool rename, because none of
them will name a pool path. Also traded away: a cold reader, with no devenv
shell, already got nothing live from a skill citation (`CONCEPT.md §7.1`,
§7.4) — this option does not make that worse, it only stops pretending
otherwise.

---

## What I could not determine

- Whether any of the 25 repositories lacking `copyroom.project.yml` were
  ever template-managed and opted out, or were always hand-built and only
  received the `my-ai` layer directly — their `.copier-answers.my-ai.yml`
  files were not individually re-checked here (that is link-plumbing
  territory, out of this task's scope per the parallel audit).
- Whether `clinch`'s described-but-unlanded edit (from the same-day
  `CLEANUP-my-ai-fleet.md` pass) is still sitting in a lane or has since
  landed — not re-checked, to avoid any lane-state read that could be
  confused with a mutating check.
- The exact current linked/unlinked split of `writing` across all 35 (the
  parallel link-plumbing audit owns this measurement; this file reuses its
  2026-10-03 finding of 10 linked / 28 not-linked from the overlapping
  38-repo list, not a fresh count against today's 35).

## What this investigation did not do

- Did not edit any `AGENTS.md`, template, or skill file, in any repository.
- Did not run any mutating `gitman` or `jj` command, anywhere.
- Did not write to `~/.config/devman`.
- Did not audit which symlinks exist in which repository — that is the
  parallel agent's task.
- Did not land or stage this file; it is untracked in `devman`.
