# Audit — is the shared-skill mechanism wired correctly across the fleet?

**Date:** 2026-10-03
**Scope:** `~/.config/devman` (the central link-plane repository) and the 65
repositories it serves, limited to the agent-skill surface
(`projects/*/agents/skills/`) and the per-repository `.agents` link.
**Mode:** read-only audit. Nothing was mutated: no file edited, no write
under `~/.config/devman`, no mutating `gitman`/`jj` command run anywhere.
**This file is untracked in `devman`** — `.scratch/` is tracked in this
repository on purpose, so `git status` will show this as a new, unstaged
file. It was not added or committed. The orchestrator adopts it.
**A parallel, independent audit is running the adjacent question** — what the
`AGENTS.md` citation text itself should say
(`041-central-autoland/RESEARCH-skill-citations.md`). That agent does not
cover symlink plumbing; this report does not propose citation text. The two
cross-check cleanly where they overlap (see §7).

**Trunk used throughout:** `main @ ef1b3847f028dce07c70bc64b0dad7319982da01`,
taken from `gitman --repo ~/.config/devman status` run against the primary
checkout (not a worktree — see §7 on why that distinction matters here).
`git status --short` in that repository is not trustworthy (it is jj's
export artifact), so every claim below is a `git` read against that commit
hash, never against `HEAD` or the working tree.

## Executive result — the five numbers

1. **The hypothesis holds, with one refinement.** Of the 35 repositories whose
   own `AGENTS.md` cites the dead `.agents/skills/my-ai/SKILL.md` path, all 35
   are correctly linked into the devman link plane. **None** has a private,
   never-crossed-over `.agents` directory.
2. **Class A — surface missing the `writing` link: 28 repositories.** Needs a
   central-repository lane only (add one symlink per surface). No per-repo
   action, no crossover work.
3. **Class B — surface already carries `writing`: 7 repositories.** Needs
   nothing in `~/.config/devman`. The only stale thing is the repository's own
   `AGENTS.md` text, which is the other agent's question.
4. **Zero tracked absolute symlinks** anywhere under `projects/*/agents/`
   (559 tracked symlinks checked). §12 limit 1 is not presently violated.
5. **The pool still has no `my-ai`,  and `writing/SKILL.md` is real, tracked,
   34 lines of content** — confirmed by both this audit and the parallel
   citation audit independently (same blob hash `bef6ccaf…`).

---

## 1. The pool — `~/.config/devman/skills/` on trunk

Command: `git -C ~/.config/devman ls-tree ef1b3847f028dce07c70bc64b0dad7319982da01 skills/`

15 skills, all real tracked content (no symlinks at the pool level, as the
design requires — the pool is the one place these files live):

```
copyroom  copyroom-adopt  copyroom-template-edit
devenv-authoring  devenv-inputs  devenv-lock  devenv-module-edits
devenv-processes  devenv-python-venv  devenv-run-commands  devenv-troubleshoot
docman  gitman  testee  writing
```

- **`my-ai/` is gone.** Not present at trunk. `git log --all --diff-filter=D
  -- 'skills/my-ai*'` shows it deleted in commit `d3ef2647` (2026-09-24,
  "central: commit live per-project content and two shared skills"), 82 lines
  removed. It was never relocated to `projects/.archive/` the way the
  *projects/my-ai* devman-project checkout later was (`ff7be524`,
  2026-10-01) — those are two different "my-ai" things; only the project
  checkout was archived, the pool skill was deleted outright.
- **`writing/` is present and real.** `git show
  ef1b3847:skills/writing/SKILL.md` → 34 lines, blob `bef6ccaf…`. Opens: *"This
  skill holds the user's standing writing rules. It moved out of `my-ai` so a
  repository can select it without carrying the rest of that skill's law."*
  Added in commit `bf06e351` (2026-09-11, "split the STE writing rules out of
  my-ai into a pool skill").
- **Content scope note (not this audit's call, flagged for completeness):**
  `writing/SKILL.md` carries only the Simplified Technical English rules. The
  35 stale `AGENTS.md` citations mostly claim four topics (devenv discipline,
  exit-code contract, manager routing, agent-files convention — see the
  parallel citation audit's Variant A). `writing` does not carry three of
  those four. That is a citation-content question, owned by the other agent,
  not a plumbing defect — flagged here only because it bears on whether
  "point the citation at `writing`" alone would fully fix anything.

## 2. Surface composition — all 65 project surfaces

Command (per surface):
`git -C ~/.config/devman ls-tree ef1b3847f028dce07c70bc64b0dad7319982da01 projects/<name>/agents/skills/`,
then `git cat-file -p <blob>` on every `120000`-mode entry to read the
symlink target and classify relative vs. absolute.

65 project directories exist under `projects/` (excluding `.archive/`). One,
**`mnemonix`**, has an `agents/` directory with no populated `skills/` tree at
all (0 entries) — it is mid-retirement under two registered-but-empty gitman
workspaces (`fix-mnemonix-empty-surface`, `finish-mnemonix-link-retirement`;
see §7). Mnemonix is not one of the 35 and is excluded from every count below.

Across the other 64 surfaces: 714 entries total — 542 relative symlinks into
the pool, 161 real directories (project-specific skills, e.g. `cairn-*`,
`allium-cli-*`, `loci-*`, `fornix-*`, `devman-*` — exactly the "repoman router
+ project-domain skill, both real files" shape §7.2 describes), 10 real files
(READMEs, one-off `SKILL-AGENTFS.md`), **0 absolute symlinks**.

**`writing`-carrying surfaces: 18 of 65.**
Command: `grep -l writing <(per-surface ls-tree)` — or re-derive with the loop
in §8.
`allium-env, clinch, devman, forgelab, fsdantic, inferference, linkman,
lodestar, nix-meta, nixos-core, nix-terminal, PyGentic, pytuin-desktop,
repoman, scopeman, silverbullet-server, talkee, template-py`

**`my-ai`-carrying surfaces today: 0 of 65.** Fully consistent with §1 — the
pool target is gone, so every surface that pointed at it either had the
dangling link pruned (see §2a) or never had one.

**Is the 7-vs-28 split (the 35 under audit) explained by surface
composition? Yes, exactly.** Of the 18 surfaces carrying `writing`, exactly 7
are among the 35 repositories that cite the dead path:
`forgelab, inferference, lodestar, PyGentic, pytuin-desktop,
silverbullet-server, template-py`. The other 28 of the 35 are among the 47
surfaces that carry neither `writing` nor `my-ai`. The remaining 11
`writing`-carrying surfaces (`allium-env, clinch, devman, fsdantic, linkman,
nix-meta, nixos-core, nix-terminal, repoman, scopeman, talkee`) are **not** in
the 35 — those repositories either never cited `my-ai`, or already had their
own citation fixed (confirmed for `devman/AGENTS.md`, see §7).

**§12 limit 1 check — tracked absolute symlinks under `projects/*/agents/`:**
Command: `git -C ~/.config/devman ls-tree -r ef1b3847... projects/ | awk
'$1=="120000"{print $3}' | git cat-file --batch` (559 symlinks fleet-wide,
not just the skills layer), then test whether any resolved target starts with
`/`. **Result: zero.** No defect found. This refutes the part of the brief
that treated limit 1 as presumptively live — it was worth checking, and it
checked out clean.

### 2a. How the my-ai removal actually happened — mechanism, not intent

Commit `d3ef2647` (2026-09-24) deletes `skills/my-ai/SKILL.md` from the pool
**and**, in the same commit, removes ~60 per-project `agents/skills/my-ai`
symlinks — but its own commit message says it is **"committing live
per-project content"**: machine-local state that a reconciler had already
produced on disk (dangling-link pruning after the pool file vanished) and
that had never been captured into a commit before. It is not a hand-written,
per-surface edit, and it added nothing. Contrast commit `bf06e351`
(2026-09-11, the actual hand-authored skill split): it added `writing` to
exactly the three surfaces that existed and were touched that day (`devman`,
`paloma-text-pipeline`, `talkee`). The seven surfaces in Class B
(`forgelab`, `lodestar`, `pytuin-desktop`, `PyGentic`, `silverbullet-server`,
`inferference`, `template-py`) got `writing` for a third reason: they
crossed over to the link plane on 2026-09-19 (`19d21d83`, `f3008cc2`), after
`writing` already existed in the pool, so the roster at crossover time
included it by default — and the same crossover gave them a (short-lived)
`my-ai` link that `d3ef2647` then pruned five days later, a clean swap purely
by timing coincidence.

**No commit, ever, added `writing` to a pre-existing surface that had lost
`my-ai`.** That lane never ran. The hypothesis holds precisely: removal was
incidental (a side effect of deleting the pool target), addition requires an
explicit lane (per §7.3, "selection is a directory of links" — opt-in, not
automatic), and that lane was never scheduled for the 28.

## 3. Per-repository plumbing — the 35 that cite the dead path

Commands, run against each of the 35 repositories under
`~/Documents/Projects/<name>`:
- `test -L .agents && readlink .agents` (symlink vs. real directory)
- `test -d ~/.config/devman/projects/<name>/agents` (central surface exists)
- `test -f .devman/project.toml` (registered as a devman project)
- `grep -A1 '^\s*\.agents:' ~/.config/devman/projects/<name>/links.yaml`
  (central `links.yaml` declares `.agents`)
- `test -e .agents/skills/writing/SKILL.md` and `.../my-ai/SKILL.md`
  (live resolution)

**All 35 answer identically on the first four checks: symlink, surface
exists, registered, `links.yaml` declares `.agents`.** There is no "never
crossed over" repository among the 35 — the operator's literal question
("are these repos not linked into devman correctly?") has a direct **no**:
every one of them is linked into devman correctly. The only variable across
the 35 is live resolution of `writing` vs. `my-ai`.

| Class | Repositories | Count |
|---|---|---|
| **A — crossed over correctly; central surface missing `writing`; `my-ai` link existed and was pruned on 2026-09-24** | `atuout, boomtube, cairn, copyroom, embeddy, flora, flora-core, flora-qc, fornix, grail, image-gen-pipeline, interplay, knappy, loci-core, observantic, parsedantic, poddantic, pydantree, pyjutsu, pytuin, siteman, structured-agents-v2, templateer_v2, terminal-state, vendomat, webdantic, zelligate` | 27 |
| **A′ — same remediation as A, but `my-ai` was never linked here at all** (`links.yaml`/surface never carried it; the citation was never backed by a real link — confirmed by `git log --all -- projects/pyllij/agents/skills/my-ai` returning 0 commits, and by the parallel citation audit's "Variant C, hedged": *"...when the personal layer is installed"*) | `pyllij` | 1 |
| **B — surface already carries `writing`; only the repository's own citation is stale** | `forgelab, inferference, lodestar, PyGentic, pytuin-desktop, silverbullet-server, template-py` | 7 |

A and A′ total **28** — the "surface composition explains it" number from
§2. They are one remediation class with one sub-case worth naming, not two
different fixes.

**No repository in the 35 fell into a "real `.agents` directory, private
copy" failure mode.** That class has zero members here. (It is a real
category elsewhere in the fleet in principle — §7.1 of `CONCEPT.md` names 17
repositories that historically mixed links and stale copies under
`.claude/skills` — but none of the 35 under this specific audit exhibits it
for `.agents` itself.)

## 4. What the fix would cost, per class

- **Class A / A′ (28 repositories):** one lane in `~/.config/devman`. For
  each of the 28 project names, add
  `projects/<name>/agents/skills/writing -> ../../../../skills/writing`
  (relative symlink, matching the pattern every other pool-sourced skill in
  that surface already uses). No repository-side change, no crossover, no
  reconcile — the `.agents` directory link already resolves correctly for
  all 28; only its contents are incomplete. `repoman install-skills` would
  then regenerate `repoman/SKILL.md` to route to it, per §7.5, on each
  project's next shell entry — no separate action needed for that part.
- **Class B (7 repositories):** nothing changes in `~/.config/devman`. The
  central surface is already correct. Whatever happens to the repository's
  `AGENTS.md` text is the other agent's question, not a central-repo lane.

## 5. What I could not determine

- **Whether `pyllij`'s missing `my-ai` link was a deliberate omission or an
  oversight at crossover time.** `git log` shows no commit ever added it;
  nothing in the history states why. Not load-bearing for the remediation
  (A′ gets the same fix as A), but the "why" is unknown.
- **The exact live state of three pending gitman workspaces**
  (`65-gitman-skill-sync`, `fix-mnemonix-empty-surface`,
  `finish-mnemonix-link-retirement`, `retire-my-ai-links`) registered against
  `~/.config/devman` with no lane. One worktree
  (`.worktrees/retire-my-ai-links`) reports its own `gitman status` trunk as
  `0e1898ab…`, a commit **not an ancestor** of the primary checkout's trunk
  (`ef1b3847…`) — a diverged, unlanded history, not the live state that
  governs the fleet's actual symlinks today. I did not reconcile why it
  diverged; I only confirmed it does not change anything reported above,
  because the live `~/.config/devman` checkout (not a worktree) is what every
  one of the 320 live symlinks resolves against. `retire-my-ai-links`'s name
  suggests this exact problem already has an in-progress, unlanded attempt
  somewhere — worth the orchestrator's attention before scheduling new work
  on it, to avoid duplicating or conflicting with it.
- **Whether `writing/SKILL.md`'s content gap (one of four claimed topics)
  should block or proceed independently of the symlink fix.** Explicitly the
  other agent's call (`RESEARCH-skill-citations.md`), flagged in §1 only
  because it affects what "fixed" means.

## 6. What this audit did not do

- Did not edit, create, or delete any file, anywhere.
- Did not run any mutating `gitman` or `jj` command (`land`, `switch`,
  `split`, `sync`, `describe`, `repair`, etc.) in `~/.config/devman` or any
  worktree, even where a status message suggested one (e.g. "working copy is
  stale — run `gitman repair`" in `retire-my-ai-links`).
- Did not audit the `.claude/skills` bridge or the 17-repository
  link/stale-copy mix §7.1 of `CONCEPT.md` names — out of scope for the
  35-repository question asked here.
- Did not propose `AGENTS.md` edit text — that is
  `RESEARCH-skill-citations.md`'s question, not this report's.
- Did not investigate `mnemonix`'s empty surface beyond confirming it has no
  `.agents` entry in its own `links.yaml` and is not one of the 35.

## 7. Where this audit's findings cross-check an independent parallel audit

`041-central-autoland/RESEARCH-skill-citations.md`, run the same day and
scoped to the citation-text question, independently confirms: the same 35
repositories (its own fresh `grep`, not shared code with this audit); the
same pool state (`skills/my-ai/` gone, `skills/writing/SKILL.md` present, same
blob hash `bef6ccaf…`); and that `devman/AGENTS.md` and `~/.claude/CLAUDE.md`
have already been corrected to cite `writing`, not `my-ai` — consistent with
this audit finding `devman` among the 18 surfaces carrying `writing` but
**not** among the 35 (its citation was already fixed, independent of the
symlink layer). No contradiction found between the two audits.

## 8. Reproduction commands

```bash
# trunk hash
gitman --repo ~/.config/devman status

# pool listing
git -C ~/.config/devman ls-tree ef1b3847f028dce07c70bc64b0dad7319982da01 skills/

# the 35 repositories citing the dead path
grep -rl 'skills/my-ai' ~/Documents/Projects --include=AGENTS.md 2>/dev/null \
  | grep -v '/\.archive/\|devman/\.scratch'

# per-repo plumbing (symlink? central surface? registered? links.yaml?)
for name in <35 names>; do
  repo=~/Documents/Projects/$name
  test -L "$repo/.agents" && readlink "$repo/.agents"
  test -d ~/.config/devman/projects/$name/agents
  test -f "$repo/.devman/project.toml"
  grep -A1 '^\s*\.agents:' ~/.config/devman/projects/$name/links.yaml
  test -e "$repo/.agents/skills/writing/SKILL.md"
done

# absolute-symlink sweep, all of projects/
git -C ~/.config/devman ls-tree -r ef1b3847f028dce07c70bc64b0dad7319982da01 projects/ \
  | awk '$1=="120000"{print $3}' | git -C ~/.config/devman cat-file --batch \
  | grep '^/'   # expect: no output
```
