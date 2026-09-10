# Guide 01 — the agent surface moves to the config repository

**Supersedes** the previous version of this file, which routed skills through the
genome. That approach is **withdrawn**: the config repository owns every skill.
See `CONCEPT.md` §7 for the design and §7.4 for what it gives up.

**Goal:** one pool of skills in `~/.config/devman/`, composed per project, reaching
each repository through **one directory symlink**.

**Size:** ~1 day, after the link plane exists. Part of it is already done on disk.
**Depends on:** Guide 02 (config repo + `devman.link` + reconciler). See §7.

---

## 1. State on disk, measured 2026-09-10

**The previous guide was executed and is uncommitted in five repositories.** No
commits since 2026-09-09 17:46; the work is all in working trees.

| Repo | Uncommitted | Verdict under the new design |
|---|---|---|
| **gitman** | `src/gitman/init.py` −163 lines (`SKILL_MD` + write block gone), `pyproject.toml` comment, `tests/test_m3_integration.py` | **KEEP** — tools must not write skills either way |
| **testee** | `src/testee/init.py` −41, `tests/test_init.py` | **KEEP** |
| **docman** | `src/docman/init.py` −42, `tests/test_cli.py` | **KEEP** |
| **repoman** | `src/repoman/skills.py` (routes filtered by disk), `templates/entrypoint.SKILL.md.j2` (`{% if rows %}` guard), `tests/test_skills.py`, `AGENTS.md` (seed replaced), `CONCEPT.md` | **KEEP** — design-agnostic and correct |
| **template-py** | 3 conditional skill dirs added under `template/.agents/skills/`, `golden/py/basic/.agents/skills/{gitman,testee}` regenerated | **REVERT** — the genome must stop shipping skills |

The repoman change is exactly right and stays:

```python
present = [m for m in ordered if (skills_root / m.skill / "SKILL.md").is_file()]
rows=[... for m in present]
```

**Commit the four keepers before starting.** They are green, they are useful under
any design, and leaving them uncommitted makes the revert in §4 harder to read.

---

## 2. The skill inventory, fleet-wide

`ls -d */.agents/skills/*/ | sed 's|.*/skills/||' | sort | uniq -c | sort -rn`

| Skill | Repos | Ships from |
|---|---:|---|
| `copyroom`, `copyroom-adopt`, `copyroom-template-edit` | 65 each | **genome AND copyroom package assets — shipped twice** |
| `my-ai` | 62 | the `my-ai` copier layer |
| `gitman` | 21 | `gitman init` (now removed) |
| `repoman` | 18 | generated router |
| `devenv-*` (7 skills) | 14–15 each | genome |
| `weed` `tend` `propagate` `elicit` `distill` | 6 each | project-specific |
| `allium-cli-*` (11 skills) | 6 each | project-specific |

**Four sources, one job.** The copyroom trio is delivered by two mechanisms at
once. That is the duplication this guide ends.

Two further measurements:

- **The `.claude`↔`.agents` bridge is already a symlink, and already drifted.**
  `argentic/.claude/skills/argentic-overlay -> ../../.agents/skills/argentic-overlay`,
  but `flora` has 11 real directories under `.claude/skills` against 13 under
  `.agents/skills`, and `fleetman` has 1 against 4. **17 repositories** hold a mix.
- **Nothing auto-loads `.agents/skills/`.** No repository has `.claude/skills` on a
  load path, and `~/.claude/skills` is empty. Agents open those files by path
  because `AGENTS.md` or the router points at them — so a directory symlink is
  transparent.

---

## 3. The target

```
~/.config/devman/
  skills/                                    THE POOL — real files, tracked
    copyroom/  copyroom-adopt/  copyroom-template-edit/
    devenv-authoring/  devenv-inputs/  devenv-lock/  devenv-module-edits/
    devenv-processes/  devenv-python-venv/  devenv-run-commands/  devenv-troubleshoot/
    my-ai/     gitman/     testee/     docman/
  agents/
    devenv/                                  the `.agents/devenv` docs export

  projects/flora/
    agents/
      skills/
        copyroom -> ../../../../skills/copyroom      relative → TRACKED
        gitman   -> ../../../../skills/gitman
        testee   -> ../../../../skills/testee
        repoman/SKILL.md                             generated router, real file
        flora-domain/SKILL.md                        project-specific, real file
      devenv -> ../../../agents/devenv
```

In each project repository, two links, both derived and both gitignored:

```
flora/.agents        -> ~/.config/devman/projects/flora/agents
flora/.claude/skills -> ../.agents/skills
```

---

## 4. Steps

### 4.1 Commit the keepers (30 min)

Four lanes, one per repo — gitman, testee, docman, repoman. Verify each with its
own command (§8), land, push.

`repoman/AGENTS.md` has already been rewritten and reads correctly; keep it. Note
that `repoman/CONCEPT.md:38` **has already been corrected** — it now reads *"The
four lifecycle managers share the family pattern; shellij is a family member
outside the roster."* Do not go hunting for the old "eight instances" line.

### 4.2 Revert template-py (15 min)

```bash
git -C template-py checkout -- golden/ template/
git -C template-py clean -fd 'template/.agents/skills/{% if*'
```

Then **remove the skills the genome already shipped** — this is the new work:

- delete `template-py/template/.agents/skills/` entirely (the `copyroom`×3 and
  `devenv-*`×7 directories)
- regenerate: `copyroom render py basic && copyroom golden py basic`
- the golden loses 10 skill directories; that is the expected diff

`template-nix` ships `my-ai` under its own `template/.agents/skills/` — remove that
too.

### 4.3 Build the pool (1–2 h)

Move, do not copy. Sources:

| Pool entry | Take from |
|---|---|
| `copyroom`, `copyroom-adopt`, `copyroom-template-edit` | `copyroom/src/copyroom/agent/assets/skills/` |
| `devenv-*` × 7 | the genome, before deleting it in §4.2 |
| `my-ai` | `my-ai/template/.agents/skills/my-ai/` |
| `gitman`, `testee`, `docman` | the deleted constants — recover from git: `git -C gitman show HEAD:src/gitman/init.py` |

**Two edits while moving:**

- `gitman`'s body has one placeholder at old `init.py:161` —
  `This repo's version lives at: {version_location}`. Resolve it to the uv branch:
  ``pyproject.toml (`version = "X.Y.Z"`), read and written through uv``.
- Every skill body that says "installed under `.agents/skills/`" should now say the
  pool owns it. Keep the routing sentences; they are still true.

Commit the pool. It is the first real content in the config repository.

### 4.4 Declare the links (1 h)

In each repository's `devenv.nix`:

```nix
devman.link = {
  ".agents"        = { canonical = "central"; path = "projects/${project}/agents"; };
  ".claude/skills" = { canonical = "central"; path = "projects/${project}/agents/skills"; };
};
```

The reconciler (Guide 02) creates both, writes both `.git/info/exclude` lines, and
composes `projects/<name>/agents/skills/` from the roster the devenv module already
merges — one relative link per enabled manager, plus the fleet set.

### 4.5 Migrate the project-specific skills (1–2 h)

Skills that are **not** in the pool are the repository's own: `allium-cli-*` (11,
in 6 repos), `weed`/`tend`/`propagate`/`elicit`/`distill` (5, in 6 repos),
`argentic-overlay`, `loci-*`, `cairn-*`, `pydantree-*`, `fornix-*`, `nvim-demo-*`.

For each, `git mv` the directory into
`~/.config/devman/projects/<name>/agents/skills/` and commit it there. It becomes a
real tracked file in the config repository, beside the links to the pool.

### 4.6 Clean the `.claude/skills` mess (30 min)

17 repositories hold a mix of symlinks into `.agents/skills` and stale real copies.
Delete all of them from the project repositories; the reconciler replaces each with
one link.

**Measured 2026-09-10: 73 skill directories exist only under `.claude/skills` and
would be lost by a blind delete.**

```
16  gitman            7  devenv-troubleshoot   7  devenv-run-commands
 7  devenv-python-venv  7  devenv-processes    7  devenv-module-edits
 7  devenv-inputs       7  devenv-authoring    5  repoman
 1  testee              1  flora/repair-defect-images   1  flora/ai-toolkit
```

Most are stale duplicates of pool skills and can go. **Two are not**:
`flora/repair-defect-images` and `flora/ai-toolkit` exist nowhere else and must
move to `~/.config/devman/projects/flora/agents/skills/` first.

Run the check before deleting anything:

```bash
for d in */.claude/skills/*/; do r=${d%%/*}; n=$(basename "$d")
  [ -e "$r/.agents/skills/$n" ] || echo "ONLY in .claude: $r/$n"
done
```

---

## 5. Verify

**The route audit must still print `0`:**

```python
python3 - <<'PY'
import os, re, glob
M = {'copy':'copyroom', 'git':'gitman', 'test':'testee', 'doc':'docman'}
bad = 0
for d in sorted(glob.glob('*/.agents/skills/repoman')):
    r = d.split('/')[0]
    m = re.search(r'Managers wired in: \*\*([^*]+)\*\*', open(f'{d}/SKILL.md').read())
    keys = m.group(1).split() if m else []
    missing = [M[k] for k in keys if k in M and not os.path.isdir(f'{r}/.agents/skills/{M[k]}')]
    if missing:
        bad += 1
        print(f'{r:22s} missing: {" ".join(missing)}')
print(f'repos with a dangling route: {bad}')
PY
```

Then:

- **Every `.agents` in a project repo is a symlink.** `for d in */.agents; do [ -L "$d" ] || echo "NOT A LINK: $d"; done` prints nothing.
- **No skill content is tracked in a project repo.** `git -C <repo> ls-files .agents` returns nothing, in every repo.
- **Every link resolves.** `readlink -f` on each `.agents` and `.claude/skills` lands inside `~/.config/devman/`.
- **The config repo tracks the pool and the relative links.** `git -C ~/.config/devman ls-files -s projects/*/agents/skills` shows mode `120000` entries with relative targets, and `100644` for the router and project-specific skills.
- **No absolute link is tracked.** `git -C ~/.config/devman ls-files -s | awk '$1==120000{print $4}' | while read l; do case "$(readlink ~/.config/devman/$l)" in /*) echo "ABSOLUTE TRACKED: $l";; esac; done` prints nothing.
- **Each touched repo's own verify is green** (§8).

---

## 6. Do not do these

1. **Do not put skills in the genome.** That is the withdrawn design. The genome
   keeps `AGENTS.md`, `devenv.nix`, `pyproject.toml` — the tracked scaffold — and
   ships no `.agents/skills/`.
2. **Do not re-add skill writing to any `init.py`.** §4.1's keepers exist to remove
   it permanently.
3. **Do not link individual skills into a project repo.** One `.agents` directory
   link per repository. Individual file links break on rename-on-save
   (`CONCEPT.md` §5.5); a directory link does not.
4. **Do not commit an absolute symlink to the config repo.** Relative links are
   tracked; absolute links are derived and gitignored (`CONCEPT.md` §2.5).
5. **Do not delete a `.claude/skills` entry before checking §4.6's loop.** Some may
   exist only there.
6. **Do not touch `AGENTS.md` or `CLAUDE.md`.** They stay tracked and per-repo; they
   are the cold reader's only entry point (`CONCEPT.md` §7.4).

---

## 7. Sequencing

This guide **depends on Guide 02** — the config repository, `devman.link`, and the
reconciler. §4.1 and §4.2 can land today; §4.3 onward cannot.

If you want value before Guide 02 lands, **§4.1 alone is worth committing now**: it
stops three tools writing skills and makes the router honest. The audit will then
report dangling routes for gitman/testee/docman until the pool exists, which is
correct — they genuinely are not installed.

| Guide | What | Size |
|---|---|---|
| **02** | config repo + `devman.link` + reconciler | ~2.5 days |
| **01** | this — the agent surface rides it | ~1 day |
| 03 | registry move to `~/.config/devman` | 1 day |
| 04 | workflows → symlinks | 2 days |

---

## 8. Verify commands, per repo

| Repo | Command |
|---|---|
| gitman, testee, repoman | `devenv shell -- bash -c 'devenv tasks run base:check && devenv tasks run base:test'` |
| docman | `devenv shell -- uv run pytest -q` (no `base:*` tasks) |
| template-py | `copyroom render py basic && copyroom golden py basic && copyroom update-test && copyroom release-check py` |
| `~/.config/devman` | its own `check` task — evaluates every `projects/*/devenv.local.nix` |
