# Operator actions — two central-repo changes an agent cannot land

Date: 2026-10-02
Scope: `~/.config/devman` (the central repository) and `~/.claude/` (two files only)
Mode: **preparation only; nothing mutated.** Every command below was checked
read-only. No `gitman` mutation, no `jj` mutation, no write under
`~/.config/devman` or `~/.claude/` was run while preparing this package.

Trunk at verification time: `main @ 2dd4fbf5ba4ace93b3e52a532b2bdd226ca59b39`.
`gitman status` (read-only): CANONICAL, 3 lanes, all `parked-paloma-*`, none
touching the paths below.

`git status --short` in `~/.config/devman` reports a stale export (jj-colocated
git index), not real dirt — see project 035 §2.5. This package trusts
`gitman status`, read-only `git` plumbing (`ls-tree`, `grep`), and the in-tree
`devman central-verify` binary. It does not trust `git status --short`.

---

## Read first — an ordering constraint, added 2026-10-02 by the orchestrator

**Do not configure `[land.pre_hook]` in `~/.config/devman/gitman.toml` yet.** This
document correctly observes that the central repository has no land gate, and
`CONCEPT.md` §4.4 proposes one. **Configuring it before the next system rebuild
would block every land in that repository.**

Measured:

```
$ /run/current-system/sw/bin/devman central-verify --phase pre
usage: devman [-h] ... {run,show,doctor,watch,agent,project,link} ...
```

The deployed `devman` has **no `central-verify` subcommand** — it is an older
system-profile build. The implementation lives in the devman working tree and
reaches the machine on the next rebuild. A hook naming a command that fails
returns non-zero, and `gitman` blocks the fold on a non-zero hook
(`CONCEPT.md` limit 9, `DECISIONS.md` D13).

**So the order is: rebuild, verify `/run/current-system/sw/bin/devman
central-verify` runs, then configure the hook.** Until then the manual
`central-verify` invocations in Tasks 1 and 2 — using the **in-tree** binary at
`/home/andrew/Documents/Projects/devman/.devenv/state/venv/bin/devman` — are the
only gate, exactly as this document says. Do not skip them.

---

## Task 1 — remove the ten dead fixture projects

### What

Delete these ten directories from the central repository's trunk, through a
gitman lane:

```
projects/docman-consumer-sitestest/
projects/docman-debug/
projects/docman-debug2/
projects/docman-existing-repo-after/
projects/docman-migrate/
projects/docman-new-repo-after/
projects/docman-roundtrip/
projects/docman-showcase-after/
projects/docman-showcase-sitestest/
projects/roundtrip-debug/
```

### Why

`devman`'s **C4** check (project 041) flags a central project as broken when it
has a tracked `links.yaml` and no `devenv.local.nix`. Run today, it names
exactly these ten and nothing else (see verification below). Project
**035-config-repo-cleanup §5.1** found the same class of problem (tracked
garbage fixture content with no backing repository) and ruled: *"all 7 are
garbage and must be removed before any commit."* These ten are a second,
independently-measured instance of that same class.

### Verification that it is safe

Every row below was re-checked for this handoff, not assumed from the brief.

| # | Project | `~/Documents/Projects/<name>` exists? | Trunk holds (under `projects/<name>/`) | Live fleet symlink resolves into it? | `.devman-link-state.json` entries |
|---|---|---|---|---|---|
| 1 | docman-consumer-sitestest | No | `links.yaml` only (1 file) | No | 5 |
| 2 | docman-debug | No | `links.yaml` only (1 file) | No | 6 |
| 3 | docman-debug2 | No | `links.yaml` only (1 file) | No | 6 |
| 4 | docman-existing-repo-after | No | `links.yaml` only (1 file) | No | 5 |
| 5 | docman-migrate | No | `links.yaml` only (1 file) | No | 6 |
| 6 | docman-new-repo-after | No | `links.yaml` only (1 file) | No | 5 |
| 7 | docman-roundtrip | No | `links.yaml` only (1 file) | No | 6 |
| 8 | docman-showcase-after | No | `links.yaml` only (1 file) | No | 5 |
| 9 | docman-showcase-sitestest | No | `links.yaml` only (1 file) | No | 5 |
| 10 | roundtrip-debug | No | `links.yaml` only (1 file) | No | 6 |

Commands behind each column:

```bash
# Column 2 — repository existence
for p in docman-consumer-sitestest docman-debug docman-debug2 \
         docman-existing-repo-after docman-migrate docman-new-repo-after \
         docman-roundtrip docman-showcase-after docman-showcase-sitestest \
         roundtrip-debug; do
  ls -ld ~/Documents/Projects/"$p"
done
# -> all ten: "No such file or directory"

# Column 3 — exactly what trunk holds
cd ~/.config/devman
for p in docman-consumer-sitestest docman-debug docman-debug2 \
         docman-existing-repo-after docman-migrate docman-new-repo-after \
         docman-roundtrip docman-showcase-after docman-showcase-sitestest \
         roundtrip-debug; do
  echo "== $p =="; git ls-tree -r --name-only main -- "projects/$p/"
done
# -> each prints exactly one line: projects/<name>/links.yaml

# Column 4 — the safety question: any live view into these ten?
cd ~/Documents/Projects
python3 devman/.scratch/projects/041-central-autoland/artifacts/prototype-v3-reverse-index.py
# -> "reverse index — 325 live views into the overlay, across 66 repositories"
#    V1 dangling: 0.  V2 (target exists, not on trunk): 2, both `mnemonix`
#    (`.agents`, `.claude/skills`) — unrelated to the ten; nothing resolves
#    into any of the ten project paths. Full raw output archived below.

# Column 5 — ledger entries, informational only (do not hand-edit this file)
python3 -c "
import json
names = ['docman-consumer-sitestest','docman-debug','docman-debug2',
         'docman-existing-repo-after','docman-migrate','docman-new-repo-after',
         'docman-roundtrip','docman-showcase-after','docman-showcase-sitestest',
         'roundtrip-debug']
d = json.load(open('/home/andrew/.config/devman/.devman-link-state.json'))
for n in names:
    print(n, len([k for k in d if k.startswith(n+':')]))
"
```

**Result: none of the ten is excluded.** All ten have no backing repository, no
live fleet symlink into them, and trunk holds only a single `links.yaml` per
project. This matches 041's C4 output exactly — nothing more, nothing less:

```bash
/home/andrew/Documents/Projects/devman/.devenv/state/venv/bin/devman \
  central-verify --phase pre
```
```
!! C4  docman-consumer-sitestest: has links.yaml, no devenv.local.nix
!! C4  docman-debug: has links.yaml, no devenv.local.nix
!! C4  docman-debug2: has links.yaml, no devenv.local.nix
!! C4  docman-existing-repo-after: has links.yaml, no devenv.local.nix
!! C4  docman-migrate: has links.yaml, no devenv.local.nix
!! C4  docman-new-repo-after: has links.yaml, no devenv.local.nix
!! C4  docman-roundtrip: has links.yaml, no devenv.local.nix
!! C4  docman-showcase-after: has links.yaml, no devenv.local.nix
!! C4  docman-showcase-sitestest: has links.yaml, no devenv.local.nix
!! C4  roundtrip-debug: has links.yaml, no devenv.local.nix
```
Exit code: 1 (finding). Ten findings, ten projects, no other C1/C2/C3 findings
mixed in.

**Also checked:** trunk's tree holds no other reference to any of the ten names
outside their own `projects/<name>/` path —
`git grep --fixed-strings "<name>" main -- . ':(exclude)projects/<name>/*'`
returned nothing for all ten.

**Ledger note:** `.devman-link-state.json` is gitignored and lives outside
version control. It holds 55 stale entries across these ten projects (out of
450 entries total). Do not hand-edit it — it carries the `{canonical, hash}`
baseline the exclude projection's two-sided-edit refusal depends on. The
operator's `devman doctor --prune` clears stale entries on its own schedule;
it is unrelated to this gitman lane and can run before or after it.

### Commands

Route through gitman. This is a lane, never a direct write to trunk.

```bash
cd ~/.config/devman

# 1. Delete the ten paths on disk.
rm -rf \
  projects/docman-consumer-sitestest \
  projects/docman-debug \
  projects/docman-debug2 \
  projects/docman-existing-repo-after \
  projects/docman-migrate \
  projects/docman-new-repo-after \
  projects/docman-roundtrip \
  projects/docman-showcase-after \
  projects/docman-showcase-sitestest \
  projects/roundtrip-debug

# 2. Adopt the dirty working copy into a new lane rooted on trunk.
gitman start central-remove-dead-fixtures --adopt-mine

# 3. Describe the change.
gitman describe -m "$(cat <<'EOF'
remove ten dead fixture projects from central (035 §5.1, 041 C4)

devman central-verify --phase pre's C4 check flags a central project as
broken when it carries a tracked links.yaml with no matching
devenv.local.nix. Run today it names exactly these ten and nothing else:
docman-consumer-sitestest, docman-debug, docman-debug2,
docman-existing-repo-after, docman-migrate, docman-new-repo-after,
docman-roundtrip, docman-showcase-after, docman-showcase-sitestest,
roundtrip-debug.

None of the ten has a backing repository under ~/Documents/Projects, and
the reverse index (prototype-v3-reverse-index.py) found zero live fleet
symlinks resolving into any of the ten, across 325 live views in 66
repositories. Project 035-config-repo-cleanup §5.1 found the same class of
tracked garbage fixture content and ruled it must be removed before any
commit. This is a second, independently measured instance of that class.

Each project held exactly one tracked file, projects/<name>/links.yaml.
EOF
)"

# 4. Land the lane into trunk.
gitman land
```

Note on the `--adopt-mine` flag: it refuses if a co-tenant's dirty path is
present that this operator did not write. If it refuses, check what else is
dirty (`gitman status`) before deciding whether `--adopt-all` is correct —
do not reach for `--adopt-all` by default.

**Contradicts the brief, flagged loudly: `gitman land` does not gate on this
today.** Project 041's `CONCEPT.md` §4.1 describes a `[land.pre_hook]` /
`[land.post_hook]` wired to `devman central-verify`. The live
`~/.config/devman/gitman.toml` is one line, `trunk = "main"` — no hooks are
configured. `gitman land` will fold this lane in regardless of C4 findings.
The post-check below is the only gate right now; run it, do not skip it.

### Post-check

```bash
cd ~/.config/devman
/home/andrew/Documents/Projects/devman/.devenv/state/venv/bin/devman \
  central-verify --phase pre
echo "exit: $?"
```
Expect: `devman central-verify: ok (pre)`, exit 0 — zero C4 findings. (Checked
in `devman/src/devman/cli.py:525,527` — read-only; this file was not edited.
The in-tree binary is used because the `devman` on `PATH` is an older build.)

Optionally, confirm the lane actually landed:

```bash
gitman status           # expect: CANONICAL, trunk hash changed from 2dd4fbf5...
git -C ~/.config/devman log -1 --format='%H %s' main
```

### Rollback

```bash
gitman undo
```

`gitman undo` is whole-intent and op-log backed. Run immediately after `gitman
land` (before any other gitman operation), it reverts the **land**: trunk
returns to `2dd4fbf5ba4ace93b3e52a532b2bdd226ca59b39`, and the
`central-remove-dead-fixtures` lane returns to its pre-land, un-landed state.
It does not retroactively undo the `rm -rf` as a separate recorded step — the
deletion is folded into the lane's one change, so undoing the land restores
trunk's prior tree, which still has the ten `links.yaml` files in it.

What it does **not** recover:
- If another gitman operation (for example, Task 2's lane) ran after this
  land, "undo the last intent" no longer means this one. Use
  `gitman undo --list` to find the specific land operation's id and
  `gitman undo --op <id>`.
- If `devman doctor --prune` ran against `.devman-link-state.json` in the
  meantime, the 55 ledger entries are gone regardless — that file is
  gitignored and outside gitman's op log entirely. `gitman undo` cannot touch
  it either way.

---

## Task 2 — canonicalise `~/.claude/AGENTS.md` and `CLAUDE.md`

### What

`~/.claude/AGENTS.md` and `~/.claude/CLAUDE.md` are measured to be **two real
files, not a symlink pair**, both outside version control, and they disagree.
Replace them with:

```
~/.config/devman/common/claude-agents.md     canonical, tracked
~/.claude/AGENTS.md  -> that file
~/.claude/CLAUDE.md  -> AGENTS.md
```

`~/.claude/` itself stays untouched — no link on the directory. Only these two
files inside it become symlinks.

### Why

Three charter rules are violated by the current two-real-files state:

- **P0, the boundary test** (`devman/.scratch/projects/025-the-link-plane/CONCEPT.md`
  §2, lines 42-48): *"Would this still be true for someone else who cloned the
  repository? No — it is true for me or this machine → it goes central, and
  reaches the repository as a symlink."* This file is the operator's own
  standing policy for every repo on this machine — true for the machine, not
  for any one project — so it belongs central.
- **025 §10 item 11** (`CONCEPT.md` line 802-803): *"The 0/1/2/3 exit contract,
  and `AGENTS.md` canonical with `CLAUDE.md` a symlink to it."* Two real files
  is the opposite of this, fleet-wide.
- **P2, source or projection, never a copy** (`CONCEPT.md` §P2, lines 98-103):
  two independent real files that can drift is exactly the "copy" category P2
  rules out.

### Verification

```bash
# Confirm these are two real files, not a symlink pair.
ls -la ~/.claude/AGENTS.md ~/.claude/CLAUDE.md
file ~/.claude/AGENTS.md ~/.claude/CLAUDE.md
```
```
-rw------- 1 andrew andrew 2.4K Sep 30 18:42 /home/andrew/.claude/AGENTS.md
-rw------- 1 andrew andrew 2.9K Sep 30 18:42 /home/andrew/.claude/CLAUDE.md
/home/andrew/.claude/AGENTS.md: Unicode text, UTF-8 text
/home/andrew/.claude/CLAUDE.md: Unicode text, UTF-8 text
```
Both regular files. Confirmed.

```bash
diff ~/.claude/AGENTS.md ~/.claude/CLAUDE.md
```
```
18c18
< AGENTS.md points its Writing style note to the removed personal-layer skill.
---
> Full rules live in the personal layer: `.agents/skills/writing/SKILL.md` (in repos that carry the layer).
30a31,41
> ## Version control lanes
> ... (11 lines)
```
Two real differences, matching the brief exactly:
1. `AGENTS.md` line 18 cites the pre-035-§8.5 skill path;
   `CLAUDE.md` line 18 already has the post-move path (`writing/SKILL.md`),
   which 035 §8.5 decided.
2. `AGENTS.md` is missing the entire "Version control lanes" section (11
   lines) that `CLAUDE.md` carries.

**`AGENTS.md` is the stale side on both counts.** `CLAUDE.md`'s content is a
strict superset: every line in `AGENTS.md` other than line 18 is byte-identical
to the corresponding line in `CLAUDE.md`, and `CLAUDE.md`'s line 18 is the
correct one. The merge is therefore: **take `CLAUDE.md` verbatim, in full.**

`/home/andrew/Documents/Projects/devman/.scratch/projects/041-central-autoland/handoff/claude-agents.md`
is byte-identical to the current `~/.claude/CLAUDE.md` — checked with `diff`,
no output. No wording was changed anywhere.

### Commands

```bash
# 1. In the central repository: add the canonical file as a tracked lane.
cd ~/.config/devman
cp /home/andrew/Documents/Projects/devman/.scratch/projects/041-central-autoland/handoff/claude-agents.md \
   common/claude-agents.md

gitman start central-claude-agents-canon --adopt-mine

gitman describe -m "$(cat <<'EOF'
add common/claude-agents.md: canonical global agent law (025 §10 item 11)

~/.claude/AGENTS.md and ~/.claude/CLAUDE.md were two real, untracked files
that disagreed: AGENTS.md lacked the "Version control lanes" section and
cited the pre-035-§8.5 skill path instead of the
post-move path (writing/SKILL.md). This violates P0 (machine-true content
goes central), 025 §10 item 11 (AGENTS.md canonical, CLAUDE.md a symlink to
it), and P2 (source or projection, never a copy).

This file is CLAUDE.md's content verbatim — it was already the superset of
the two and already had the correct skill-path citation. No wording changed.
EOF
)"

gitman land

# 2. On the machine: point the two ~/.claude files at it.
#    First, preserve the current content (see Rollback) before linking.
mkdir -p ~/.claude.bak-$(date +%Y%m%d)
cp ~/.claude/AGENTS.md ~/.claude/CLAUDE.md ~/.claude.bak-$(date +%Y%m%d)/

rm ~/.claude/AGENTS.md ~/.claude/CLAUDE.md

ln -s /home/andrew/.config/devman/common/claude-agents.md ~/.claude/AGENTS.md
ln -s AGENTS.md ~/.claude/CLAUDE.md
```

**Link targets, and why:**
- `~/.claude/AGENTS.md` → **absolute** target
  (`/home/andrew/.config/devman/common/claude-agents.md`). This matches the
  fleet's existing convention for links that cross from a view directory into
  the central overlay — every sampled example (`linkman/.agents ->
  /home/andrew/.config/devman/projects/linkman/agents`,
  `linkman/.envrc -> /home/andrew/.config/devman/common/envrc`) uses an
  absolute target. The central repo's own `.gitignore` rule (*"Derived:
  absolute links and generated state. Relative links are tracked"*) governs
  links that live **inside** the central repo's tracked tree; these two links
  live in `~/.claude/`, outside that tree and outside git entirely, so that
  rule does not apply to them — the fleet-convention precedent does.
- `~/.claude/CLAUDE.md` → **relative** target (`AGENTS.md`). This matches
  every sampled repo's own `CLAUDE.md -> AGENTS.md` link (checked `linkman`,
  `devman`, `docman`, `testee`: all relative, same-directory).

### Check for anything that would break

```bash
cd ~/Documents/Projects
grep -rln --include="*.md" --include="*.toml" --include="*.nix" \
  --include="*.yaml" --include="*.yml" \
  -E '~/\.claude/(AGENTS|CLAUDE)\.md|\.claude/(AGENTS|CLAUDE)\.md' . \
  | grep -v '/\.jj/\|/\.git/'
```
Result: only planning/scratch documents reference the path literally —
`035-config-repo-cleanup/README.md`, `036-lane-and-charter-audit/PROMPT.md`,
and several `041-central-autoland` documents (all discussing this exact
issue), plus two unrelated kickoff prompts (`flora`'s and `mnemonix`'s) that
say "follow `~/.claude/CLAUDE.md`" generically. No functional config
(`gitman.toml`, `devenv.nix`, a `SKILL.md`) sources or includes the path. None
of these breaks: the path still resolves to a file after the change (now via
one extra symlink hop), so a generic "follow `~/.claude/CLAUDE.md`" reference
keeps working.

### Rollback

The two original files are preserved by the `cp` step above, before the `rm`:

```bash
ls ~/.claude.bak-<date>/     # AGENTS.md, CLAUDE.md — the original content

# To fully reverse the symlink step:
rm ~/.claude/AGENTS.md ~/.claude/CLAUDE.md
cp ~/.claude.bak-<date>/AGENTS.md ~/.claude.bak-<date>/CLAUDE.md ~/.claude/

# To also reverse the central lane:
gitman undo   # immediately after `gitman land`, before any later gitman op
```

### Risk — flag before applying

**This changes live operator policy while sessions may be running.** A
session already mid-task reads its system prompt once; it will not notice the
swap. The *next* session started after the swap is the first to read the
merged file. Apply this when no agent session is mid-task, and expect that
only sessions started afterward see the "Version control lanes" section and
the corrected skill path.

---

## Summary of files in this handoff

- `claude-agents.md` — the merged canonical file, ready to `cp` into
  `~/.config/devman/common/claude-agents.md`.
- `OPERATOR-ACTIONS.md` — this file.
