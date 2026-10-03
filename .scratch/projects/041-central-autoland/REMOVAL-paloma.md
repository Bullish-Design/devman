# Removal review — paloma-text-pipeline

Date: 2026-10-03
Author: agent session (read-only investigation, one disk check deferred — see Mode)
Repository: this document lives in `devman` (never in `~/.config/devman`), per the brief.

## Scope

The operator retired `paloma-text-pipeline`. The repository was moved to an
archive directory. This review checks whether the remaining traces — a stray
on-disk directory, central-repository content, plane registrations, and
fleet-wide references — are safe to remove, and prepares exact commands for
the operator where a mutation is needed. `~/.config/devman` is live machine
configuration; no agent mutation ran against it. No `gitman`/`jj` mutating
verb ran anywhere (confirmed by command history: only `status`, `log
--revset`, `workspace list`, and `--help` calls were issued).

## Mode — what happened vs. what is only planned

- **Deleted:** nothing. The stray directory
  `/home/andrew/Documents/Projects/paloma-text-pipeline` was **not** deleted —
  see Step 2. No other file anywhere was deleted, moved, or edited.
- **Planned only:** the central-repository removal (Step 3) and the three
  `gitman abandon` calls are commands for the **operator** to run. None were
  executed by this session.
- **Anomaly, not caused by this session:** the three parked lanes named in
  the brief existed at the start of this session and were gone by the end of
  it, with trunk's hash unchanged throughout. See "Lane anomaly" under Step 3.

## Step 1 — safety verification

| Check | Command | Result |
|---|---|---|
| Live symlinks resolving into paloma paths | `python3 artifacts/prototype-v3-reverse-index.py` (read-only walk of all 65 fleet repos, run from this session) | **320 live views total, 0 resolve into any path containing "paloma."** Verified two ways: the script's own missing/lane-only lists contain no paloma path, and a direct filter of its full 320-entry `views()` list for the substring "paloma" (case-insensitive) returned 0 hits. |
| Archived copy exists | `ls /home/andrew/Documents/Projects/.archive/ \| grep -i paloma` | **Found.** `/home/andrew/Documents/Projects/.archive/paloma-text-pipeline` exists with a full working tree: `.git` (real repository, not a placeholder), `src/`, `tests/`, `docs/`, `pyproject.toml`, `AGENTS.md`, etc. `~/.config/devman/projects/.archive/` does **not** exist (the brief named it as a second place to check; it is simply absent, not an error). |
| Registered in the plane | `ls ~/.local/state/devman/projects/`, `ls ~/.local/state/vendomat/devman/active/projects/`, `ls ~/.local/share/devman/projects/`, `find ~/.local/share/devman/dags/ -iname '*paloma*'` | `~/.local/state/devman/projects/` has no paloma entry. **`~/.local/state/vendomat/devman/active/projects/paloma-text-pipeline/` exists** (metadata.json + projection.json + workflows/). **`~/.local/share/devman/projects/paloma-text-pipeline/` exists** (metadata.json + workflows/). **Three DAG links exist:** `paloma-text-pipeline.{check,maintain,test}.yaml`, each a symlink into the registered project's `workflows/`. The project is still actively registered — see Step 2 for why this matters. |
| Link-state ledger | `python3 -c "... json.load(.devman-link-state.json) ..."` | **0 entries** whose key starts with `paloma`, out of 378 total entries. Not hand-edited; this was a read-only count. |

**Conclusion: safe on the live-symlink axis (0, as required), and an archived copy with real content exists.** The plane-registration finding is a genuine complication, addressed in Step 2.

## Step 2 — the stray on-disk directory

`ls -la /home/andrew/Documents/Projects/paloma-text-pipeline/` shows a single
top-level entry, `.devman/` (mode `drwxr-x---`, dated today). `test -e
.../.git` confirms **no `.git`**. Full recursive listing
(`find /home/andrew/Documents/Projects/paloma-text-pipeline`):

```
.devman/
.devman/.runs/
.devman/.runs/logs/
.devman/.runs/reports/
.devman/.runs/artifacts/
.devman/.runs/metadata.jsonl                                           (349 bytes)
.devman/.runs/logs/paloma-text-pipeline_maintain/
.devman/.runs/reports/maintain-034ZIqd7KvshXZR69oiNZ9.md                (539 bytes)
.devman/.runs/logs/paloma-text-pipeline_maintain/dag-run_20261003_040501Z_034ZIqd7KvshXZR69oiNZ9/
.devman/.runs/logs/.../dag-run_20261003.000501.605.034ZIqd7.log         (366 bytes)
.devman/.runs/logs/.../run_20261003_040501Z_e519cc/
.devman/.runs/logs/.../run_20261003_040501Z_e519cc/prune.....out        (539 bytes)
.devman/.runs/logs/.../run_20261003_040501Z_e519cc/prune.....err        (0 bytes)
.devman/.runs/logs/.../run_20261003_040501Z_e519cc/onExit....out        (0 bytes)
.devman/.runs/logs/.../run_20261003_040501Z_e519cc/onExit....err        (0 bytes)
```

Nothing exists outside `.devman/`. No `.git`, no `.devman/project.toml`.

**But the tree is not empty**, and that is the finding that matters. The
report and metadata record a `paloma-text-pipeline.maintain` DAG run that
**succeeded at 2026-10-03T04:05:01Z** — hours before this session, same
calendar day. That run is only possible because the project is still
registered (Step 1: `~/.local/share/devman/projects/paloma-text-pipeline/`,
`~/.local/state/vendomat/.../active/projects/paloma-text-pipeline/`, and the
three DAG links are all still live) and its `log_dir` /
`DEVMAN_PROJECT_DIR` point at this exact path (confirmed by reading
`~/.local/share/devman/dags/paloma-text-pipeline.maintain.yaml`, which
resolves to `workflows/maintain.yaml` under the registered project and sets
`working_dir`/`log_dir` to
`/home/andrew/Documents/Projects/paloma-text-pipeline`). The directory is not
leftover debris; it is **actively being recreated by a still-registered,
still-scheduled maintenance job.**

The brief's deletion test is: "if and only if it contains nothing but an
**empty** `.devman/.runs` scratch tree ... delete it. If it holds anything
else ... do not delete it; report what you found and stop." This tree is not
empty — it holds a real run report, real log files, and a non-empty
`metadata.jsonl`. **I did not delete the directory.** Independently of the
letter of that test, deleting it right now would not even be durable: the
`maintain` DAG is still scheduled and would simply recreate
`.devman/.runs/...` on its next run. Deleting the directory without first
removing the plane registration (the project entry under
`~/.local/share/devman/projects/` and `~/.local/state/vendomat/.../active/projects/`,
and the three DAG links) would not stick.

**Note on an earlier assessment:** `LANE-ASSESSMENT-central.md` (same
project folder, dated 2026-10-03, written earlier) describes this same
directory's `.devman/.runs/` tree as empty ("logs/, reports/, artifacts/,
metadata.jsonl"). At the time I checked it was not empty — the maintain run
that populated it finished at 04:05 UTC. Either that assessment was written
before the run, or it undercounted. I am recording what I found just now,
not revising that document.

**Recommendation (not executed):** the operator should first deregister the
project (clear its entry from `~/.local/share/devman/projects/`,
`~/.local/state/vendomat/devman/active/projects/`, and
`~/.local/share/devman/dags/paloma-text-pipeline.*.yaml`, most plausibly via
`devman doctor --prune`, which the tool's own help describes as removing
"stale registry entries" — unverified against this specific case, since
running it mutates live state outside this session's authorization) and only
then delete `/home/andrew/Documents/Projects/paloma-text-pipeline`. I did not
run `devman doctor --prune`; it is outside what this session was authorized
to mutate.

## Step 3 — the central repository

`cd ~/.config/devman && git ls-tree -r --name-only main | grep paloma`:

```
projects/paloma-text-pipeline/.local.gitignore
projects/paloma-text-pipeline/agents/devenv
projects/paloma-text-pipeline/agents/skills/copyroom
projects/paloma-text-pipeline/agents/skills/copyroom-adopt
projects/paloma-text-pipeline/agents/skills/copyroom-template-edit
projects/paloma-text-pipeline/agents/skills/devenv-authoring
projects/paloma-text-pipeline/agents/skills/devenv-inputs
projects/paloma-text-pipeline/agents/skills/devenv-lock
projects/paloma-text-pipeline/agents/skills/devenv-module-edits
projects/paloma-text-pipeline/agents/skills/devenv-processes
projects/paloma-text-pipeline/agents/skills/devenv-python-venv
projects/paloma-text-pipeline/agents/skills/devenv-run-commands
projects/paloma-text-pipeline/agents/skills/devenv-troubleshoot
projects/paloma-text-pipeline/agents/skills/gitman
projects/paloma-text-pipeline/agents/skills/pairwise-quality-judge/SKILL.md
projects/paloma-text-pipeline/agents/skills/writing
projects/paloma-text-pipeline/devenv.local.nix
projects/paloma-text-pipeline/links.yaml
```

**18 paths**, all under `projects/paloma-text-pipeline/`. Most are
`120000` (symlink) blobs into the shared skill pool; `.local.gitignore`,
`devenv.local.nix`, `links.yaml`, and `pairwise-quality-judge/SKILL.md` are
`100644` regular files (checked with `git ls-tree -r main --
projects/paloma-text-pipeline/`, mode column).

**Discrepancy to flag, not resolved:** a plain recursive `find` of the
**working copy** at the same path shows **19** files/symlinks — one more
than `git ls-tree main` reports:
`projects/paloma-text-pipeline/agents/skills/repoman/SKILL.md`. Raw
`git status --short` (known unreliable here per the operating rules) shows
this same area as dirty in a different, inconsistent way (`M
.local.gitignore`, `D agents/skills/my-ai`). This matches the documented
caveat that the colocated git export can lag jj's actual tree. I did not run
`jj` directly to resolve it. **Before running the `rm` below, the operator
should re-run `git ls-tree -r --name-only main -- projects/paloma-text-pipeline/`
themselves** to get a fresh count; the command sequence below removes the
whole directory, not an enumerated file list, so this discrepancy does not
change *what* gets removed, only the exact count the operator should expect
to see disappear.

### Lane anomaly — read this before running anything

At the start of this session, `gitman status` reported:

```
Gitman status — CANONICAL · 3 lanes
trunk: main @ 076c57957e74b19c84a26dd897c5a46a849af23a
  parked-paloma-handoff draft      1 change, +111 −39   · 11 behind trunk
  parked-paloma-judge-skill draft      1 change, +158 −143   · 10 behind trunk
  parked-paloma-pairwise-judge draft      1 change, +262 −0   · 12 behind trunk
```

and `gitman log --revset <name>` resolved each of the three names to a real
change id and description. Later in the **same session**, with trunk's hash
unchanged (`076c57957e74b19c84a26dd897c5a46a849af23a` throughout) and with
no mutating `gitman`/`jj` command run by this session, `gitman status`
repeatedly (3 consecutive calls) reported **0 lanes**, `gitman log --revset
<name>` refused with "Revision ... doesn't exist" for all three names, and
raw `git show-ref | grep -i paloma` returned nothing. **The three lanes are
gone, and I did not remove them.** Since trunk's hash never changed, they
were not landed; something abandoned or otherwise discarded them outside
this session's command history.

This is exactly the kind of "something unusual" the operating rules say to
stop and flag rather than paper over. **I am not including `gitman abandon`
commands for these three lanes in the sequence below**, because as of this
writing they do not exist and the command would simply refuse. Before doing
anything else in this repository, the operator should run `gitman status`
and `gitman log --revset <name>` (read-only) themselves to confirm current
state, and separately check whether another session, terminal, or
automation touched this repository during this window — this falls outside
what a read-only investigation can determine.

### Operator command sequence — central removal only

Because the three lanes are already gone (per the anomaly above), this
sequence now contains **one** lane, not four. If the operator's own re-check
finds the three lanes still present after all, abandon them first, in a
separate lane-less step (no `start`/`describe` needed for `abandon`), so
that a plain `gitman undo` after the removal `land` below still targets the
removal and not a trailing abandon — abandon is reversible on its own via
`gitman undo --op <id>` regardless of order, but ordering abandons *before*
the removal lane keeps the common case (no `--list` needed) simple.

```bash
cd ~/.config/devman

# 0. Optional, only if your own re-check still shows the three lanes present:
#    gitman abandon parked-paloma-handoff
#    gitman abandon parked-paloma-judge-skill
#    gitman abandon parked-paloma-pairwise-judge

# 1. Re-confirm the tree before deleting (discrepancy noted above).
git ls-tree -r --name-only main -- projects/paloma-text-pipeline/

# 2. Delete the project directory on disk.
rm -rf projects/paloma-text-pipeline

# 3. Adopt the dirty working copy into a new lane rooted on trunk.
gitman start central-remove-paloma-text-pipeline --adopt-mine

# 4. Describe the change.
gitman describe -m "$(cat <<'EOF'
remove projects/paloma-text-pipeline from central

paloma-text-pipeline is retired. The repository was moved to
/home/andrew/Documents/Projects/.archive/paloma-text-pipeline (confirmed
present, a real .git working tree, not a placeholder). A read-only
fleet-wide reverse-index walk of all 65 Documents/Projects repositories
(devman/.scratch/projects/041-central-autoland/artifacts/
prototype-v3-reverse-index.py) found 320 live symlinks into this central
repository and zero of them resolve into any path under
projects/paloma-text-pipeline/. The project's own link-state ledger entry
count is 0. Removing this tree's skill-pool symlinks, devenv.local.nix,
links.yaml, and .local.gitignore leaves no live consumer behind.

Note: the stray directory this project pointed at
(~/Documents/Projects/paloma-text-pipeline) still carries a live devman
project registration and three scheduled DAGs (check/maintain/test) as of
this writing; this lane removes only the central-repository side. The
on-disk directory and its registration are a separate cleanup (see
REMOVAL-paloma.md Step 2).
EOF
)"

# 5. Land the lane into trunk.
gitman land
```

### Post-check

```bash
cd ~/.config/devman
/home/andrew/Documents/Projects/devman/.devenv/state/venv/bin/devman \
  central-verify --phase pre
echo "exit: $?"

gitman status                                   # expect: CANONICAL, 0 lanes
git -C ~/.config/devman log -1 --format='%H %s' main   # expect: new hash, "remove projects/paloma-text-pipeline from central"
git ls-tree -r --name-only main | grep -i paloma        # expect: no output
```

### Rollback

```bash
gitman undo
```

Run immediately after `gitman land`, before any other `gitman` operation.
It reverts the land: trunk returns to `076c57957e74b19c84a26dd897c5a46a849af23a`
and the `central-remove-paloma-text-pipeline` lane returns to its pre-land
state. It does **not** separately restore the `rm -rf` as its own step — the
deletion is folded into the lane's one change, so undoing the land restores
trunk's tree, which still has the 18 (or 19 — see discrepancy above) paths.
It does **not** touch `.devman-link-state.json` (gitignored, outside the op
log) or any devman plane registration under `~/.local/share`/`~/.local/state`
— those are untouched by this sequence either way, since this sequence never
mutates them.

## Step 4 — other references

| Path | Hit | Classification |
|---|---|---|
| `/home/andrew/Documents/Projects/flora/devenv.nix` (lines ~9-13) | `curatorDbName = "paloma_prod_restore"`, comments about "the restored Paloma prod dump" | **Leave alone.** This is flora's own disposable Postgres restore of a "Paloma" product database dump, unrelated to the `paloma-text-pipeline` repository — a different, live, active tool. |
| `~/.config/devman` trunk, `projects/paloma-text-pipeline/*` (18 paths) | tracked files/symlinks | **Must remove** — see Step 3 sequence above. |
| `~/.config/devman/projects/*/links.yaml` (all other projects) | grep for "paloma" | **No hits.** Nothing else in the central repo's `links.yaml` files references paloma. |
| `~/.local/share/devman/projects/paloma-text-pipeline/`, `~/.local/state/vendomat/devman/active/projects/paloma-text-pipeline/`, `~/.local/share/devman/dags/paloma-text-pipeline.{check,maintain,test}.yaml` | registry/DAG entries | **Operator decision** — these are what keeps regenerating the stray directory's `.devman/.runs/` content (Step 2). Not removed by this session; likely candidate is `devman doctor --prune`, unverified for this case. |
| `~/.config/devman/.devman-link-state.json` | 0 keys starting with `paloma` | **N/A** — nothing to remove here. |
| `devman/.scratch/projects/*/*.md` (CONCEPT.md, PROPOSAL.md, LANE-ASSESSMENT-central.md, OPERATOR-ACTIONS.md, MIGRATION notes, etc. — ~24 files) | paloma mentioned as example/case-study content | **Historical record, leave alone.** These are project reports describing past design work and a prior read-only assessment of the same three lanes; rewriting them was never in scope and they are not configuration. |
| `~/.claude.json` (live, not a backup) | 3 hits: per-project settings entries for `/home/andrew/Documents/Projects/paloma-text-pipeline`, `paloma-story-generation`, `paloma-image-pipeline` (keyed by absolute path, each holding `allowedTools`/`mcpContext` etc.) | **Operator decision.** `~/.claude/` is read-only for this session by the hard rules. This is Claude Code's own per-project settings registry, not devman/gitman config; once the directory is gone the entry is simply dangling, harmless but removable at the operator's discretion. Not edited. |
| `~/.claude/backups/.claude.json.backup.*` (5 files), `~/.claude/projects/**/*.jsonl` (2,778 hits), `~/.claude/file-history/**` (502 hits), `~/.claude/tasks/**/*.json` (3 hits) | session transcripts, file-edit snapshots, and config backups mentioning paloma in passing | **Historical record, leave alone.** Session/transcript data, not configuration; reading or rewriting it was out of scope and these files were not opened beyond filename-level grep matching. |
| devman `.scratch/` registry-like config (`repos.toml` or similar) | `find ... -iname 'repos.toml'` | **No hits anywhere under `~/Documents/Projects`.** No such file exists. |
| `vendomat` toml/yaml/json config | grep for paloma | **No hits.** |

## What I could not determine

- **Why the three parked lanes disappeared mid-session.** I confirmed they
  existed (twice, by two independent read-only methods) and confirmed they
  were gone (three ways: `gitman status`, `gitman log --revset`, raw `git
  show-ref`) later in the same session, with trunk's hash unchanged and with
  no mutating command in this session's own history. I cannot tell from a
  read-only vantage point whether this was a concurrent operator action, a
  concurrent automation (the plane's `watch` service is confirmed live and
  does run scheduled jobs — see Step 2), or something else.
- **Whether `devman doctor --prune` would actually clear the
  `paloma-text-pipeline` entries under `~/.local/share` and
  `~/.local/state/vendomat`.** The tool's `--help` text says it removes
  "stale registry entries" generically; I did not run it, so I cannot
  confirm it targets this specific project or what else it might touch.
- **The 18-vs-19-file discrepancy** between `git ls-tree -r main` and the
  working-copy `find` under `projects/paloma-text-pipeline/` in the central
  repository (the extra file is `agents/skills/repoman/SKILL.md`). Raw `git
  status --short` shows unrelated-looking dirt in the same area, consistent
  with the documented jj/git export lag, but I did not run `jj` directly to
  resolve which side is authoritative.
- **Exactly when `LANE-ASSESSMENT-central.md`'s "empty .devman/.runs" check
  ran relative to the 04:05:01Z maintain run** that populated the directory
  with real content by the time I checked it.

## What I did not do

I did not delete `/home/andrew/Documents/Projects/paloma-text-pipeline` (its
`.devman/.runs/` tree is not empty — a real maintain-run report and logs are
in it). I did not run any mutating `gitman` or `jj` command anywhere,
including no `abandon` against the three parked lanes (which had already
vanished by the time I would have run it). I did not run `devman doctor
--prune` or edit `.devman-link-state.json`. I did not write, edit, or delete
anything under `~/.config/devman` or `~/.claude/`. I did not open or alter
any session transcript, file-history snapshot, or backup file beyond
filename-level grep matching. The only write this session performed is this
document, in the `devman` repository.

---

## Correction — 2026-10-03, by the orchestrator

**The "unexplained" disappearance of the three parked lanes was this session.**
This document flags that `parked-paloma-handoff`, `parked-paloma-judge-skill` and
`parked-paloma-pairwise-judge` vanished mid-session with no landing and no
command, and advises the operator to investigate before touching the repository.
**There is nothing to investigate.** The operator approved abandoning all three
on the strength of `LANE-ASSESSMENT-central.md`, and the orchestrator ran:

```
gitman --repo ~/.config/devman abandon parked-paloma-handoff
gitman --repo ~/.config/devman abandon parked-paloma-judge-skill
gitman --repo ~/.config/devman abandon parked-paloma-pairwise-judge
```

while this survey was running. All three returned `ABANDONED`. Trunk did not
move, which is why the hash looked unchanged. The survey was correct that it ran
no mutating command — a different actor in the same session did.

**The report's substantive findings stand and were independently re-verified:**
0 live symlinks resolve into any paloma path (320 views, 65 repositories); the
archive exists at `~/Documents/Projects/.archive/paloma-text-pipeline`; 0 ledger
entries; and the stray directory is genuinely not empty.

### Two findings the orchestrator confirmed and rates higher than the document does

1. **The project is still live in the plane, with six DAG links, not three.**
   `~/.local/share/devman/dags/` and the active generation each carry
   `paloma-text-pipeline.{check,maintain,test}.yaml`. A `maintain` run completed
   at `2026-10-03T04:05:01Z` and wrote the 7 files found in the stray directory.
   **So deleting that directory achieves nothing until the project is
   deregistered** — the next scheduled run recreates it. Deregistration comes
   first; the deletion is the second step, not the first.
2. **The archived copy depends on central content.**
   `~/Documents/Projects/.archive/paloma-text-pipeline/devenv.local.nix` is a
   symlink into `~/.config/devman/projects/paloma-text-pipeline/`. Removing the
   18 central paths therefore leaves the archive holding a dangling symlink.
   That is probably acceptable for an archive, but it is a consequence the
   operator should choose rather than discover.
