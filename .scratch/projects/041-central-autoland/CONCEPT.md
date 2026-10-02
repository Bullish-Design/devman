# 041 — the central guard: drift detection and lane safety for `~/.config/devman`

**Date:** 2026-10-01
**Scope:** the central configuration repository `~/.config/devman`, the gitman
verbs that rewrite its working copy, and the devman checks that watch it.
**Mode:** investigation and concepting. **Nothing in `~/.config/devman` was
mutated.** No lane was landed, abandoned, switched or split. No live symlink and
no Nix file was changed.
**Measured:** 2026-10-01 on `server`. Every number below carries the command or
the `file:line` that produced it.
**Builds on:** `035-config-repo-cleanup/README.md` (same repository, 2026-09-10),
`036-lane-and-charter-audit/README.md` Part C, `033-local-gitignore-gitman`,
`025-the-link-plane/CONCEPT.md`, `015-what-the-plane-should-do/RESULT.md` §9.
**Corrects:** this project's own kickoff prompt on three points — evidence items
2, 5 and the `[publish] verify` framing of question B. §1.2 states each.

---

## 1. Executive result

### 1.1 The one finding the project turns on

**`devman doctor` reports `ok  link drift   no registered project declares a
link`, and it has been wrong since 2026-09-19.**

```
$ devman doctor
ok  link drift      no registered project declares a link
```

The check reads `proj.links` from the derived registry
(`src/devman/doctor.py:1278-1308`). Measured in the active generation
`~/.local/state/vendomat/devman/active/projects`:

| Source | Entries | Entries declaring ≥1 link | Links |
|---|---|---|---|
| **active** registry — what `doctor` reads | 48 | **0** | **0** |
| **legacy** registry `~/.local/share/devman/projects` | 50 | **50** | 250 |
| `.devman-link-state.json` — the reconciler's own ledger | 82 projects | 82 | **450** |
| live symlinks into the overlay, counted from the fleet | 66 repositories | 66 | **325** |

Every active-generation entry carries `"links": {}`. So the check's input set is
empty, the loop body never runs, and the `elif checked:` branch cannot be
reached. **It is a check that cannot fail**, which `AGENTS.md` property 4 and the
charter's `devenv test` measurement name as the failure the plane exists to
prevent.

**The cause is dated and mechanical.** Commit `37050e9`, 2026-09-19 14:51,
*"refactor: delete the compatibility plane module"*, deleted `modules/devenv.nix`
— 553 lines, the registration hook that wrote the link declarations into each
project's registry entry. `modules/link.nix:1-7` states the new boundary
plainly: *"This module has one job … It does not know about workflows, the
registry, Dagu, or project generation state."* Nothing replaced the projection.

**The regression is provable against a prior report.** `036`'s verification
record, 2026-09-11, reads: *"`devman doctor` returned the same seven pre-existing
findings: **two link-drift entries**, one local-source pin, one path input, one
daemon-shell notice, and the watcher report."* On that date the check had an
input and produced findings. Eight days later the input was deleted. The plane's
only link-plane detector then reported `ok` for **twelve days**, and the three
working-copy incidents of 2026-10-01 happened inside that window.

### 1.2 Why project 035's cleanup did not hold

035 was a **reading**, not a detector. Its §10 is explicit about what it did:
`status`, `diff`, `log`, `reflog`, `ls-files` — a human and an agent looking at
`git status` for one afternoon. It fixed the state and changed nothing that would
notice the state coming back. It even said so, in §2.3, about the adjacent tool:
*"the sanctioned health check says the repository is fine."* It recommended one
gitman check and shipped none.

So the recurrence has three independent causes, and all three are still live:

1. **Nothing watched.** The only candidate watcher, `doctor`'s `link drift`, was
   live on 2026-09-11 and vacuous by 2026-09-19 (§1.1). No check anywhere
   asserts a property of the central repository.
2. **Nothing could fail.** `~/.config/devman/gitman.toml` is one line,
   `trunk = "main"`. The repository ships a real `base:check` task in its own
   `devenv.nix` — `nix-instantiate` over every `projects/*/devenv.local.nix`, 78
   files, **2.58 s, passing** — and **nothing invokes it.** It is not a
   registered devman project (`projects/` holds no entry for it; `devman doctor`
   counts 48 and none is the overlay), so no workflow projects for it, and its
   gitman.toml declares no gate.
3. **The mechanism that creates the mess runs unattended, continuously.** 035 §6
   measured this and drew the right conclusion: *"low risk of loss, real risk of
   contamination … the longer this repository stays uncommitted, the more stray
   bootstrap directories accumulate."* Every `devenv shell` entry in 65
   repositories writes canonical content here. A cleanup is a subtraction against
   a process that adds. Three weeks is how long the subtraction lasted.

**A design that answers only (1) will not hold either.** Detection without a
refusal is 035 again in a cron job.

### 1.3 The hazard is live right now, and the check names it

Twelve live views in four repositories point at central content that exists only
in the unlanded lane `m14-central-residue`. Measured by the reverse index in
§3.3, 0.72 s:

```
V2  target exists but is NOT on main   : 12
      !! linkman/.agents            -> projects/linkman/agents
      !! linkman/devenv.local.nix   -> projects/linkman/devenv.local.nix
      !! linkman/.claude/skills     -> projects/linkman/agents/skills
      !! linkman/.git/info/exclude  -> projects/linkman/.local.gitignore
      !! mnemonix/.agents           -> projects/mnemonix/agents
      !! mnemonix/devenv.local.nix  -> projects/mnemonix/devenv.local.nix
      !! mnemonix/.claude/skills    -> projects/mnemonix/agents/skills
      !! scopeman/.agents           -> projects/scopeman/agents
      !! scopeman/devenv.local.nix  -> projects/scopeman/devenv.local.nix
      !! scopeman/.claude/skills    -> projects/scopeman/agents/skills
      !! scopeman/.git/info/exclude -> projects/scopeman/.local.gitignore
      !! siteman/.git/info/exclude  -> projects/siteman/.local.gitignore
```

Two damage classes, both from incident 1's family:

- **Three `devenv.local.nix` bootstrap links.** `linkman`, `mnemonix` and
  `scopeman` fail devenv shell entry the moment that lane leaves the working
  copy, with a Nix trace nothing can intercept (025 §5, §12 limit 2). One of the
  three is **linkman itself**, the repository running the cutover.
- **Three `.git/info/exclude` projections.** `linkman`, `scopeman` and `siteman`
  lose every machine-local ignore rule at once. The repository keeps working and
  starts showing `.agents`, `.envrc`, `.loci` and `devenv.local.nix` as
  untracked. A single `git add -A` then commits the link plane into project
  history.

The second class is new to this record. 033 and 036 Part C made
`.git/info/exclude` a symlinked projection of a **tracked** central file; that
decision is binding and correct, and its consequence is that the exclusion policy
of a repository now depends on a central path being *on trunk*, not merely on
disk. Nothing stated that, and nothing checks it.

### 1.4 What the design is

**One read-only predicate, two existing gates, no new plane and no new shared
name.**

| Part | What | Where it lives | Status of the machinery |
|---|---|---|---|
| **The predicate** | `devman central-verify` — three assertions, exit `0`/`1`, writes nothing | devman, beside `doctor` | new code, ~150 lines, prototyped and measured here |
| **The refusal** | `[land.pre_hook]` in `~/.config/devman/gitman.toml` | the central repository's tracked policy | **ships in gitman today, configured by 0 of 74 repositories** |
| **The completeness report** | `[land.post_hook]` in the same file | same | same |
| **The heartbeat** | `doctor`'s `link drift`, input changed from the registry to the reverse index | devman | the check exists and is vacuous; this repairs it |

Total cost of a full run: **3.4 s** (2.58 s Nix parse + 0.72 s reverse index +
0.05 s declaration checks).

### 1.5 The four plain answers

- **Should a workflow auto-land central drift? No.** §7.
- **Does a verify step gate `land` on a repository with no remote? Not through
  `[publish] verify` — that is dead code here. Through `[land.pre_hook]`, yes,
  and it is proven on this machine.** §4.
- **devman's job or gitman's? Both, split at a named line.** gitman owns the hook
  point; devman owns the predicate. §8.
- **Why 035 did not hold?** §1.2.

### 1.6 Three corrections to this project's kickoff prompt

1. **Evidence item 2 is out of date in the operator's favour.** The 78
   `links.yaml` files are on trunk. `main` is `268c0a3`, 2026-10-01 19:32:07,
   *"m14 phase A: the converted links.yaml for all 78 central projects"*;
   `git ls-tree -r --name-only main | grep -c links.yaml` → **78**. The 155
   reconciles exactly as 78 (landed) + 59 (`m14-central-residue`) + 18
   (`m14-central-dead-fixtures`). Phase A's output is no longer at risk. The 59
   are.
2. **The tracked-but-gitignored class is devman's, not the overlay's.**
   `git ls-files -i -c --exclude-standard` in `~/.config/devman` → **0**. The
   same command in `~/Documents/Projects/devman` → **33**, every one a
   `.scratch/**/*.log`. The assertion is still worth having; it belongs in
   devman's own verify, where it fires.
3. **Question B's framing points at the wrong setting.** `[publish] verify` is
   not a weak gate on `land`; it is **no gate on `land` at all**, in any
   repository, with or without a remote. §4.1 gives the call sites. devman's own
   `gitman.toml` carries the same misunderstanding in a commit message.

---

## 2. The problem, in measured numbers

### 2.1 The repository, now

```
$ gitman --repo ~/.config/devman status
Gitman status — CANONICAL · 6 lanes
trunk: main @ 268c0a372f325185174a19eecf891c084da19e2e
  m14-central-dead-fixtures draft      1 change, +220 −0
* m14-central-residue  draft      1 change, +1287 −1   · you are here
    m14-central-residue+retire-foreman-my-ai draft      1 change, +76 −76
  parked-paloma-handoff draft      1 change, +111 −39   · 7 behind trunk
  parked-paloma-judge-skill draft      1 change, +158 −143   · 6 behind trunk
  parked-paloma-pairwise-judge draft      1 change, +262 −0   · 8 behind trunk
note: no git remote — publish/release unavailable.
```

| Quantity | Value | Command |
|---|---|---|
| dirty paths | 59 (53 `A`, 6 `M`) | `git status --short \| wc -l` |
| untracked paths | **0** | `git ls-files --others --exclude-standard \| wc -l` |
| tracked paths | 1440 | `git ls-files \| wc -l` |
| tracked **symlinks** | **614** | `git ls-files -s \| awk '$1=="120000"' \| wc -l` |
| tracked `links.yaml` | 78 | `git ls-files '*links.yaml' \| wc -l` |
| `gitman.toml` | `trunk = "main"` — 1 line, no `[publish]`, no `[land]` | `cat` |
| git remote | none | `git remote -v` |

035's headline defect is **fixed**: it measured `find projects/*/agents -type l`
→ 0 and called 62 real copies a P2 violation. There are now 614 tracked
symlinks. The agent surface is a projection, as 025 §7.2/§7.3 requires. Question
C must not undo that, and §6 does not.

### 2.2 Nothing in the repository can fail, and the task that could is unreachable

`~/.config/devman/devenv.nix` ships a real `base:check`:

```nix
tasks."base:check".exec = ''
  for file in projects/*/devenv.local.nix; do
    nix-instantiate --eval --strict --expr \
      "builtins.functionArgs (import \"$PWD/$file\")" >/dev/null
  done
'';
```

Measured: 78 files, **2.58 s**, exit 0. It can fail — a malformed central
declaration file is the thing that bricks shell entry — and **nothing runs it**:

- not the plane: the overlay is not one of `devman doctor`'s 48 projects, so no
  workflow projects for it;
- not gitman: its `gitman.toml` declares no `[publish] verify` and no `[land]`
  hook;
- not a workflow in any repository: six exist (`agent`, `check`, `maintain`,
  `test`, `format`, `release`) and
  `grep -rn 'config/devman|overlayDir|central' groups/*/workflows/` returns
  nothing.

The operator's standing policy fires *"once its verify step passes."* In the one
repository where the drift accumulated, that precondition has no referent.

### 2.3 What the fleet does with gitman's gates

| Measurement | Value |
|---|---|
| `gitman.toml` files under `~/Documents/Projects/*/` | 74 |
| of those, declaring any `verify` command | 26 |
| of those, declaring a `[land]` hook | **0** |
| repositories with no git remote | 1 (`linkman`), plus `~/.config/devman` |

**The gate the operator's policy needs already ships and has never been
configured once.** That is the cheapest finding in this report.

### 2.4 The derived state nobody prunes

`.devman-link-state.json` is gitignored (`.gitignore:6`) and holds the
`{canonical, hash}` baseline that `excludes.py` reads to refuse a two-sided edit
of the exclude projection. Evidence item 6 is confirmed and quantified:

- `grep -n 'link-state\|link_state' src/devman/doctor.py` → **no match**.
  `doctor` never reads the file.
- `Registry.unproject` (`src/devman/registry.py:587-607`), the body behind
  `--prune`, removes `dags/` links, projected workflows, the registry entry and
  `metadata.json`. It does not touch the ledger.
- Consequence, measured: the ledger holds **82** projects and **450** entries
  against a pruned registry of **48** and a live fleet of **66**.
- The ledger also drifts unobserved. The readiness review measured **456 entries
  / 84 projects** earlier today; at 19:35 it holds **450 / 82**. Six entries and
  two projects left, and nothing recorded the write.

Any design that regenerates or discards central state must leave that baseline
alone. §3 does: every assertion reads it and none writes it.

---

## 3. The predicate: `devman central-verify`

### 3.1 What it must do, and what it must not

**Must:** fail when a path that a live repository symlinks to is missing from
disk, or present on disk but absent from trunk. Those two conditions are the
whole of incidents 1, 2 and 3 expressed as a property.

**Must not:** cost more than a few seconds; walk the fleet deeply; parse Nix
modules; consult the registry or the ledger as an authority; write anything.
An expensive check nobody runs is the same as no check, and 015 measured the
other end of that: *"54 identical reports is one report nobody opens."*

### 3.2 The three assertions

| Id | Assertion | Input | Fires today |
|---|---|---|---|
| **C1** | Every `projects/*/devenv.local.nix` evaluates | the 78 central files | 0 — 2.58 s |
| **C2** | Every live view's target exists on disk | the reverse index (§3.3) | **0** |
| **C3** | Every live view's target is on trunk | the reverse index + `git ls-tree -r main` | **12** |

Plus one pairing assertion, cheap and already failing:

| **C4** | Every central project with a tracked `links.yaml` has a `devenv.local.nix` | `projects/*/links.yaml` | **10**, all dead docman/roundtrip fixtures |

C4's ten findings are exactly the content of the parked lane
`m14-central-dead-fixtures`. A check whose first run names an already-drafted fix
is a check calibrated correctly.

### 3.3 The reverse index, and why it is the right input

**The view side is the authority. Nothing else is.** C2 and C3 take their
population by walking the fleet for symlinks whose raw target lands inside the
overlay — not from the registry, not from the ledger, not from `links.yaml`.

```
reverse index — 325 live views into the overlay, across 66 repositories
  .agents                      66     devenv.local.nix              66
  .git/info/exclude            64     .envrc                        60
  .claude/skills               54     .claude                       11
  .claude/settings.local.json   3     .devman/workflows              1
elapsed 0.72s      (os.walk, depth ≤ 2, plus .git/info/exclude)
```

Three reasons it beats every declaration source, each measured:

1. **The registry is empty** (§1.1). A check built on it reports `ok` forever.
2. **The ledger is stale by 34 projects** (§2.4) and names 16 projects whose
   repositories do not exist. Driven from the ledger, the same assertions produce
   **27 findings of which 1 matters** — 035's "report nobody opens", reproduced.
3. **Every declaration source has a liveness gate that is wrong for this job.**
   The cutover census counts 65 live projects by `.devman/project.toml`. By that
   test `mnemonix` is not live — and `mnemonix` is one of the two bootstrap
   targets `gitman split` deleted in incident 1, and one of the three exposed in
   §1.3. A repository with a symlink into the overlay is live for this purpose
   whether or not it has onboarded.

The reverse index also needs no maintenance. It cannot go stale, because it is
not a record of anything — it is a reading of the filesystem that owns the fact.

### 3.4 Why this cannot be `linkman check`

Linkman is the link engine, so P1 says the interface should be Linkman's. It
cannot be, and the reason is a contract, not a gap. Measured on a throwaway
repository in `/tmp`, with a symlink pointing at a deliberately absent target:

```
$ linkman check --json --repo-root <probe>/repo --config <probe>/links.yaml
{ "clean": true,
  "links": [ { "link_rel": "devenv.local.nix",
               "status": "correct",
               "expected_target": "…/central/projects/probe/devenv.local.nix",
               "message": "link matches its declaration" } ],
  "summary": { "total": 1, "correct": 1, "changes_required": 0, "refusals": 0 } }
exit 0
```

**`linkman check` reports `clean: true` and `correct` on incident 1's exact
damage.** `Status` (`src/linkman/models/domain.py:75-82`) describes the link
side: it compares the symlink's raw target string against the declaration.
Target existence is outside Linkman's boundary by design — apply is
topology-only, and D5 keeps the bootstrap content in devman. Linkman is right;
it is answering a different question.

Two consequences:

- **The predicate is devman's**, because devman owns the content that lives at
  the target. Stated as the boundary test in §5.
- **`linkman check` with no config found also reports `clean: true, total: 0`,
  exit 0.** Run inside `linkman` itself it reports zero links while four are
  live, because the declaration is central and the default search is repo-local.
  That is a second check that cannot fail, and it is recorded here for Linkman's
  owner rather than fixed here (open question O6).

### 3.5 What C3 means, stated carefully

C3 is not "uncommitted work exists". The central repository is a live write
target and will always be dirty; 035 §6 established that and nothing has changed.
C3 is narrower and it is the whole mechanism:

> **A path that a live repository symlinks to must be reachable from trunk.**

Why trunk and not "in a lane": in a colocated jj repository the working copy *is*
a commit. Content held only in a lane is on disk only while `@` sits on that lane.
`switch`, `split`, `land` and `abandon` all rewrite the tree. Trunk is the only
place in the repository whose content survives every lane operation. For 73 of
the 74 fleet repositories that distinction is academic. For this one the working
tree **is** the machine's configuration, and the distinction is the difference
between a working shell and a brick.

C3 therefore reads `git ls-tree -r --name-only main`, not the index. The index in
a colocated repository is jj's export artifact, not a staging area — 035 §2.5
paid for that lesson and this check does not repeat it.

### 3.6 Disclosed: read-only raw `git`

C3 and C4 call `git -C ~/.config/devman ls-tree`, `ls-files` and `rev-parse`.
gitman ships 24 verbs and **none of them is `diff`, `show` or `reflog`** —
035's finding, re-confirmed against `gitman --help` today — and no verb answers
"is this path in trunk's tree". The choice is also strictly safer than the
alternative: every gitman or jj invocation snapshots the working copy and
publishes an operation, and in this repository a snapshot is a live-system write.
Read-only `git` plumbing does not. 035 §10 disclosed the identical choice with
the identical reasoning.

---

## 4. Where the check lives, and who runs it

### 4.1 `[publish] verify` is dead code here, and it is dead code everywhere for `land`

```
$ grep -rn "run_verify" ~/Documents/Projects/gitman/src/
core.py:176     def run_verify(...)
core.py:1369        ok, out = run_verify(session.config.publish.verify, …)   # do_publish
release.py:64   ok, out = run_verify(verify_cmds, repo_root, …)              # do_release
```

Two call sites. `do_land` (`core.py:1467`) is not one of them. So:

- **`[publish] verify` has never gated a `land`, in any repository.** This is not
  a no-remote special case.
- In `~/.config/devman` it is worse than ineffective. The repository has no
  remote, `publish` and `release` both refuse before reaching the hook, so a
  `[publish] verify` block there would be a configured gate that can never run —
  the most expensive kind of false assurance.
- **devman's own `gitman.toml` carries the same misreading.** Commit `81a1340`,
  *"fix: move the verify gate under `[publish]` so gitman reads it"*, sets
  `verify = ["nix","flake","check"]` with `verify_timeout = 3600`. gitman does
  read it — on `publish` and `release` only. Every `gitman land` in devman since
  then has run no verify. Open question O1.

**Reject `[publish] verify` for this job.**

### 4.2 `[land.pre_hook]` is the gate, and it is proven on this machine

`LandConfig` (`gitman/src/gitman/config.py:44-57`) declares `pre_hook` and
`post_hook`, each `{command, timeout_seconds, allowed_paths}`. The pre hook runs
inside the repository lock, before any fold (`core.py:1707-1734`); the post hook
runs after, outside the lock (`core.py:1482-1508`). Both receive a stable JSON
event on stdin — `schema_version`, `event`, `mode`, `repository_root`,
`workspace_path`, `current_lane`, `requested_lanes`, `planned_folds`,
`completed_folds`, `trunk_advances`, `land_all` (`models.py:84-101`).

Measured in a throwaway colocated repository **with no remote**, a hook that
exits 1:

| Phase | Result | gitman exit | Trunk |
|---|---|---|---|
| `pre_land` | `Gitman land — BLOCKED`, hook output quoted | **1** | **unchanged** — lane still live |
| `post_land` | `Gitman land — LANDED` + `post-land hook failed` + *"land succeeded; no rollback was attempted"* | **1** | advanced |

That is exactly the pair of semantics this design needs, and neither requires a
remote, a network, or a change to gitman.

One property to respect: gitman snapshots the workspace before and after the
hook (`hooks.py:filesystem_snapshot`) and **blocks on any file change outside
`allowed_paths`, even when the hook exits 0**. `central-verify` must write
nothing. That suits it; it is a read.

### 4.3 The placement, and the boundary test applied to each candidate

| Candidate | Boundary test (property 10) | Verdict |
|---|---|---|
| `gitman.toml` `[publish] verify` | n/a — measured dead (§4.1) | **reject** |
| `gitman.toml` `[land.pre_hook]` / `[post_hook]` | *"would this be true for someone else who cloned the repository?"* **Yes** — "this repository must not land a broken declaration" is the repository's own policy. 025 P0's table puts `gitman.toml` on the repository side: *"trunk name, repo policy"*. The file is tracked in the overlay | **accept — the gate** |
| `devman doctor` | **Yes** for the code; the *reading* is machine-local, which is what a diagnostic is for. `doctor` is already the fleet-wide reader and already owns a `link drift` check | **accept — the heartbeat** |
| a devman `check`-group workflow for the overlay | **No, and it recurses.** For the overlay to join the plane it needs `.devman/project.toml` and a `devenv.nix` devman block — tracked repository facts. But the overlay *is* the machine-local root; a workflow that runs there has nowhere further central to go, and 025 §6.1 moved the overlay to hold other repositories' workflows, not its own. 015 rule 7 also applies: a nightly report on one repository is a report nobody opens | **reject as the primary; §4.5 keeps a narrow version** |
| a new per-repository hook | **Reject on P4** — one mechanism per job. gitman already ships the hook point, unused by 74 of 74 repositories |

### 4.4 The configuration, concretely

```toml
# ~/.config/devman/gitman.toml           TRACKED in the overlay
trunk = "main"

[land.pre_hook]
# Content correctness: refuse to fold a broken declaration into trunk.
# C1 + C2 + C4. Writes nothing; gitman blocks the land if it does.
command = ["devman", "central-verify", "--phase", "pre"]
timeout_seconds = 120

[land.post_hook]
# Completeness: after the fold, is any live view still lane-only?
# C3. Exit 1 reports; it does not and must not roll back.
command = ["devman", "central-verify", "--phase", "post"]
timeout_seconds = 120
```

**The pre/post split is the load-bearing decision, and it is not cosmetic.**
C1, C2 and C4 are *"the content is wrong"* — landing wrong content is worse than
not landing, so they block. C3 is *"the content has not reached safety yet"*, and
**landing is the cure**, so blocking on it would refuse the one operation that
fixes it. C3 therefore runs after the fold and reports. Run today against the
state in §1.3, the post hook's message is the whole handoff:

```
central-verify: 3 of 6 lanes landed; 12 live views in 4 repositories are still
lane-only. linkman, mnemonix, scopeman cannot enter a devenv shell if
'm14-central-residue' leaves the working copy. Land it, or
`gitman switch m14-central-residue` is unsafe.
```

### 4.5 One scheduled run, and its justification against rule 7

`doctor` already runs once for the machine through `plane-report` —
`maintain.yaml` records why, with the arithmetic: 58 identical plane-wide reports
is not a signal, one is. **The repaired `link drift` check inherits that
placement and needs no new workflow.** That is the whole of the scheduled half of
this design: one existing nightly run, one existing report, one check inside it
that starts being able to fail.

No new workflow. No new queue name. No new shared contract name. The shared
contract stays closed.

---

## 5. Where it sits in the four planes

```
  NIX PLANE          unchanged
  FILE PLANE         unchanged
  LINK PLANE   ◄──── C2 / C3 read here. The assertion is a link-plane property:
                     "every view's canonical is present and durable."
                     025 §5.2 behaviour 3 already calls `test -L` + `readlink -f`
                     THE detector. This adds the two questions it never asked:
                     does the canonical EXIST, and will it SURVIVE a lane move.
  WORK PLANE   ◄──── `doctor` reports (existing `plane-report` run).
                     No workflow writes. No workflow lands.
  AGENT SURFACE      unchanged. §6 keeps 614 tracked symlinks tracked.

  THE VC BOUNDARY ◄── NEW SURFACE, and it is gitman's, not a plane.
                     `[land.pre_hook]` / `[land.post_hook]`.
                     The only place a working-copy rewrite is observable
                     before it happens.
```

**The boundary-test justification for every placement:**

| Thing | Question | Answer | Placement |
|---|---|---|---|
| `central-verify` code | true for anyone who cloned devman? | **Yes** — the algorithm is the project | devman repository, tracked |
| its *finding* | true for anyone? | **No** — "linkman's bootstrap link is lane-only on *this* machine" | a report, never a committed file |
| the hook configuration | true for anyone who cloned the overlay? | **Yes** — "this repository must not land a broken declaration" is its policy | `~/.config/devman/gitman.toml`, tracked |
| the overlay joining the plane | true for anyone who cloned it? | **No, and the question is malformed** — it *is* the machine-local root | rejected (§4.3) |
| the hook *point* | true for anyone who cloned gitman? | **Yes** — "a verb that rewrites the working copy may be gated" is generic | gitman (§8) |

**Nothing moves between planes, and no plane is added.** The design's whole
content is: one predicate devman did not have, bolted to two gates gitman already
ships.

---

## 6. Question C — the write tier for machine-generated central content

### 6.1 No new tier. The tier table is not where this goes wrong

The three named cases route cleanly under the existing table plus P2, and two of
the three are already decided and already shipped:

| Content | Written by | Tracked? | Tier | Authority |
|---|---|---|---|---|
| promoted agent surface — `projects/*/agents/skills/<name>` relative symlinks | the reconciler, by composition | **tracked** (614 of them) | `free` on first creation; `lane` for an edit | 025 §7.3, 035 §8.7, 036 Part C |
| `.local.gitignore` | the reconciler, promoting existing excludes | **tracked** | `free` / `lane` | **036 Part C, binding** |
| `links.yaml` | the Phase A converter | **tracked** (78) | `lane` — it is now an edit to existing tracked source | §6.3 |
| `repoman install-skills` routers — `projects/*/agents/skills/repoman/SKILL.md` | repoman, every sync | **gitignored** | no tier — never tracked | the live `.gitignore`, with its reason recorded in the file |
| `projects/*/agents/index`, `projects/*/agents/pi/`, `projects/*/repo`, `dags/`, `.devman-link-state.json` | generated / runtime | **gitignored** | no tier | the live `.gitignore` |

**The precedent for generated content already exists in the repository and is
written down in the file that implements it:**

```
# Generated routers: `repoman install-skills` rewrites
# projects/<p>/agents/skills/repoman/SKILL.md at every repoman-sync. Generated,
# not authored — ignore them so a sync does not churn the tree.
projects/*/agents/skills/repoman/SKILL.md
```

So the rule is not new and needs no new tier: **route by P2, not by tier.** Is the
file *authored or selected* (track it) or *regenerated from a source that is
itself tracked* (ignore it)? The agent-surface symlinks are selection — *which*
skills a repository gets, and 025 §7.3 rests on them being tracked and diffable.
Gitignoring them would re-create 035's violation from the other side: the pool
would be authoritative and the selection would be invisible.

### 6.2 The real defect is not a tier. It is that `free` has no terminal state here

The tier table says `free` lands "in the working tree". That is a safe terminal
state in 73 of 74 repositories, because a working tree persists. **In a colocated
jj repository the working copy is a commit**, so "the working tree" names whatever
lane `@` currently sits on. In `~/.config/devman` the working tree is also the
machine's live configuration. Put those two facts together and `free` is not a
resting place; it is a staging area with a live consumer.

So the amendment this project proposes is **one invariant over the existing
tiers, scoped to one repository**, not a fourth tier:

> **CENTRAL-1.** In `~/.config/devman`, a path that a live repository symlinks to
> has not finished being written until it is reachable from trunk. Tier `free` is
> not terminal there. C3 is the assertion; the `[land.post_hook]` is where it is
> stated.

This is narrower than a new tier and it is checkable, which is what 015 §9 said
the amended tiers still owed. Note also that `doctor`'s `check_writes`
(`src/devman/doctor.py:682-706`) flags `tier = "free"` only *outside* tier A's
agent surface — and the overlay's content **is** agent surface, so a `free` claim
over it passes the audit cleanly. That is the exact seam the overlay slips
through, and CENTRAL-1 closes it without touching the audit.

### 6.3 One thing this project will not decide: `links.yaml` beside `devenv.local.nix`

Both files now declare the same links for all 78 projects. By P2/P4 that is two
mechanisms for one job, which is drift waiting to happen — and 035 §4.2 is the
local proof of what happens next. It is a **deliberate cutover intermediate
state**: Lane 9e retires the `devman.link` attribute set and the readiness review
B3/B4 show the ordering is not yet settled. Naming it is in scope; resolving it
is the cutover's, and this project is forbidden from designing around a Linkman
change. Recorded as open question O2.

Until it resolves, C1 and C4 cover both files and neither is privileged.

---

## 7. Question D — should a workflow commit and land central drift? **No.**

### 7.1 The charter already decided it, in the same amendment that created the tiers

015 §9, *"What did not move, and this is the part to hold on to"*:

> **Rule 2 stands. The lane stays local.** No `publish`, no `push`, no `land`.
> Creating a lane is reversible on this machine; pushing it is not.

The amendment that *weakened* rule 3 into the three tiers withheld `land` from
the plane explicitly, in writing, on the same page. This is not a judgment call
available to this project. A workflow that lands is a charter change, and no
measurement here forces one.

### 7.2 And the measurements agree, independently

- **The drift was not a lane.** gitman reported `working copy @ has unbookmarked
  work`. The policy, and automatic *landing*, govern lanes. Neither would have
  swept the 155 paths. The gap is adoption, not landing.
- **Automatic adoption bundles unrelated work, measured.** The 155 were Phase A's
  78 central declarations, ten projects of docman/roundtrip fixture residue, and
  two shared pool skills (`skills/gitman/SKILL.md`, `skills/testee/SKILL.md`).
  One unreviewed commit over that set is the single worst outcome available: it
  enshrines the fixtures, which is 035's finding repeating, and it buries the
  two pool-skill edits that reach every repository through the surface links.
- **An automatic lane nobody reads fails criterion 4.** *"A run that reports
  success while producing an incorrect result is the failure this design exists
  to prevent."* A nightly `adopt-and-land` would report `Succeeded` while
  committing fixture garbage, and the repository would read `CANONICAL` and clean
  — which is exactly the state the whole of 2026-10-01 was spent inside. It
  satisfies the letter of the tier and defeats its purpose.
- **015's third owed item is still unbuilt.** *"Lane hygiene — a scheduled tier-B
  workflow makes a lane per run per repository. 54 lanes a night is rule 7
  wearing a new hat."* `check_writes` supplies owed items (1) and (2); nothing
  supplies (3). The amendment's own precondition — *"no tier-B workflow should
  ship before at least (1) and (2)"* — is met for a workflow that writes a lane
  in a project repository. It says nothing about one that lands in the
  machine-configuration repository, which is a larger act.

### 7.3 What to automate instead, and why it is strictly better

**Automate the refusal, not the write.** The three things worth building, in
order of value per line of code:

1. **Make `land` able to refuse** (`[land.pre_hook]`, §4.4). Zero new code in
   gitman, four lines of TOML, and the operator's policy acquires the verify step
   it has been quoting at a repository that had none.
2. **Make `doctor` able to fail** (repair `link drift`, §4.5). One function's
   input changes. The plane regains the detector it lost on 2026-09-19.
3. **Make the post-land report name the remaining exposure** (§4.4). This is the
   piece that would have turned incident 1 from a brick into a sentence.

All three are reversible, all three are machine-local, and none writes to trunk
unattended. The thing the operator actually wanted — *"I should not find 155
uncommitted paths three weeks after cleaning this up"* — is delivered by (2),
which makes the condition loud on the first night it recurs, and by (1), which
makes the repository's own standard enforceable. Landing was never the missing
piece.

### 7.4 The operator's policy is not in conflict with this

The policy governs **an agent in a session**: verify, save, land, push. The
charter governs **the plane**: no unattended land. Those are different actors and
both are right. The policy's precondition — *"once its verify step passes"* — is
undefined in this repository today. §4 defines it. After that, an agent working in
`~/.config/devman` lands under the policy, with a real gate behind it, and the
plane still never lands by itself.

---

## 8. Question G — devman's job, or gitman's? **Both, split at a named line.**

### 8.1 The split

| Side | Owns | Why it must be there |
|---|---|---|
| **gitman** | the **hook point** on every verb that rewrites the working copy | `switch`, `split`, `abandon` and `land` are gitman's. Only gitman knows a rewrite is about to happen, and only gitman can refuse before it. devman is not in the call path and cannot be |
| **devman** | the **predicate** | *"a repository on this machine symlinks to this path"* is a devman fact. gitman must not learn it. The moment gitman knows about symlinks-into-this-repo-from-elsewhere it stops being an interface to jj and becomes a second link plane (P1, P4) |

**gitman has already proved this shape.** `[land.pre_hook]` is precisely a generic
hook point carrying an opaque predicate: JSON event in, exit code out, no domain
knowledge on gitman's side. The ask is not a new idea; it is the existing idea
applied to three more verbs.

### 8.2 What each side would cost

**gitman** — one generic feature, no link knowledge:

- extend `LandHookConfig`'s shape to a `[hooks]` table keyed by verb, or add
  `[switch.pre_hook]`, `[split.pre_hook]`, `[abandon.pre_hook]` beside `[land]`;
- the event payload is mostly there already — a `WorkingCopyRewriteEvent` needs
  the verb, the from/to lane, and ideally the path set the rewrite would remove,
  which gitman can compute and nothing else can;
- the refusal plumbing is `_land_hook_blocked`, unchanged;
- `do_switch` (`core.py:797`) already carries two guards of exactly this
  character — it refuses to strand an unnamed change with on-disk work, and
  refuses a double checkout. A third guard point is idiomatic there, not foreign.

Cost: a config surface, an event model, three call sites. Benefit beyond this
project: every repository gains the ability to refuse a destructive navigation,
which is a generic good. **gitman also carries a second, independent reason:**
035 §2.3 already recommended a gitman check for a divergent colocated HEAD that
`gitman doctor` reported `ok` on, and it was never built. The same tool, the same
class of blind spot, twice.

**devman** — `central-verify`, ~150 lines, prototyped and measured here. Zero new
shared contract names. One `doctor` function's input changed.

### 8.3 What the design does today, with neither side changed

This matters, because gitman changing is not on this project's critical path.

| Verb | Covered today? | By what |
|---|---|---|
| `land` | **yes** | `[land.pre_hook]` + `[land.post_hook]`, configuration only |
| `switch`, `split`, `abandon` | **no** | nothing. Open question O3 |
| day-to-day accumulation | **yes**, within one night | the repaired `link drift` in the nightly `plane-report` |

So `land` is gated now and the navigation verbs wait on a gitman feature. §9 says
what to do in the meantime.

---

## 9. Question E — the lane-switch hazard

### 9.1 In scope, and the structural half is available immediately

A verify step at land time does not protect a `switch` or a `split`. That is
correct, and it is why §8 asks gitman for a hook. But the hazard also has a
structural shrink that needs nobody's permission, and it is the better half of
the answer:

> **Content that a live repository depends on should be on trunk and stable.
> Content that is regenerated should be gitignored. Between them there is nothing
> left for a lane to carry.**

Measured: of the **325** live views into the overlay, **313** point at content on
trunk and are already immune — a `switch` cannot remove a path trunk holds,
because every lane descends from trunk. Only the **12** in §1.3 are exposed, and
they are exposed because they are new content on an unlanded lane. **The hazard
is not a property of the repository; it is a property of unlanded new content in
it.** Its size is the count of C3 findings, and C3's whole job is to keep that
count at zero.

This reframes the fix. The lane-switch hazard does not need a general mechanism
first. It needs:

1. **C3 at zero**, kept there by the post-land report and the nightly check.
   At C3 = 0 the hazard is arithmetically absent, not merely unlikely.
2. **A gitman guard** for the window where C3 > 0, because new content always
   starts life on a lane. This is the residual, and it is genuinely gitman's.

### 9.2 What `untrack` already gives, and its limit

`gitman untrack` — *"Stop tracking machine-local path(s): gitignore + remove from
the tree (on the current lane)"* — is the sanctioned way to move generated
content out of the tracked set, and the overlay's history shows it in use
(`chore: untrack generated gitman skill`, and `stop tracking notes: the vault is
a live service directory at ~/Notes`). It is the right tool for anything §6.1
classifies as regenerated.

It does not help the live targets. `devenv.local.nix`, `agents/`,
`.local.gitignore` must stay tracked — 025 §7.3 and 036 Part C are binding on the
last two. Untracking them would move the hazard, not remove it: an untracked
central file survives a `switch` but is then outside recovery, review and the
two-sided-edit refusal. **Reject untracking live targets.**

### 9.3 Who owns the residual if the gitman feature does not land

**devman cannot own it.** There is no interception point; by the time devman sees
the filesystem the rewrite has happened. The fallback is not a mechanism, it is a
discipline with a detector behind it: C3 = 0 before any navigation verb in the
overlay, and the nightly check to catch the nights it was not. State that in the
gitman skill so it is where an agent reads it, not only in a concept document.

---

## 10. Question F — the permission-classifier collision

### 10.1 The collision is correct, and the design must not route around it

`gitman land` on `m14-central-residue` was denied in auto mode as *[Modify Shared
Resources]*. The lane lands 59 paths of live machine configuration behind 325
symlinks in 66 repositories. The classifier is right, and it coincides exactly
with the operator's own carve-out — *"a lane touching shared or risky files"*.
Two independent policies agreeing is a signal, not an obstacle.

### 10.2 The design's answer: put the whole mechanism on the read-only side

**Every part of this design is a read.** `central-verify` writes nothing — it
cannot, because gitman's hook snapshot blocks a hook that changes a file.
`doctor` writes nothing without `--prune`. The reverse index is an `os.walk`.
So the mechanism itself never meets the classifier.

Only the `land` crosses the line, and **the land stays the operator's.** That is
not a concession; §7 establishes it independently from the charter. The collision
therefore reduces to a handoff-quality problem, and the design answers it
directly:

| Need | How |
|---|---|
| the agent can establish the lane is safe to land, without landing | `devman central-verify` exit 0/1, plus `gitman land --dry-run`, which renders the folds and mutates nothing (`core.py:1660-1705`) |
| the operator gets the exact command, not a description | the post-hook message names the lane verbatim (§4.4) |
| the denial is explicable rather than mysterious | the check's output *is* the explanation: 12 views, 4 repositories, 3 of them unable to enter a shell |

### 10.3 What this design must not do, stated so it is not attempted later

- **Do not shrink the lane to get under the classifier.** The smallest useful
  carve of `m14-central-residue` is a `gitman split`, and `split` is incident 1 —
  the verb that deleted two live bootstrap targets. Splitting to make a land
  permissible runs the dangerous verb to avoid a safe denial.
- **Do not move the land into a workflow to escape the classifier.** That is §7
  with extra steps, and it converts a blocked-and-visible action into an
  unattended write to trunk — the one shape the charter keeps out.
- **A mechanism silently blocked in practice is not a mechanism** — so the gate
  is not "the agent lands it". The gate is `[land.pre_hook]`, which runs for the
  operator's hand-typed `gitman land` identically. The gate does not care who
  typed the verb. That is why it is the right gate.

---

## 11. Stated limits

1. **C3 is a reachability test, not a durability test.** It asserts a path is in
   trunk's tree. It does not assert the content at that path is the content the
   view needs — a stale trunk copy with a newer lane edit reads as safe. Closing
   that needs a content comparison, which is `git cat-file` per path and a real
   cost. Out of scope; the failure it misses is staleness, not a brick.
2. **The reverse index is bounded at depth 2** plus `.git/info/exclude`. It finds
   all 325 live views of the eight known kinds. A view declared deeper than two
   levels would be missed. No such declaration exists today (`.claude/skills` and
   `.claude/settings.local.json` are the deepest at depth 2), and the bound is
   what keeps the walk at 0.72 s. It must be re-measured if a deeper key is
   declared.
3. **It only sees repositories under `~/Documents/Projects/`.** 66 found against
   the cutover census's 65 live projects; the extra is `mnemonix`, which the
   census excludes for lacking a manifest. A managed repository outside that
   directory would be invisible. Unverified whether one exists.
4. **C1 evaluates `builtins.functionArgs (import …)`, not the full devenv
   module.** It catches a syntax error and a broken argument contract. It does not
   catch a declaration that evaluates and is wrong. The central `devenv.nix`
   already states this limit in its own comment and it is the right trade at
   2.58 s.
5. **`[land.post_hook]` cannot roll back, by gitman's design**, and this design
   does not want it to. A C3 finding after a land means *more landing is needed*,
   not that the land was wrong. The consequence is that between a partial land and
   the next one, the exposure is real and only reported.
6. **Nothing here protects `switch`, `split` or `abandon`** until gitman grows a
   hook (§8.3). The window is bounded by C3's count, not closed.
7. **The predicate assumes `~/.config/devman` and `~/Documents/Projects/` as
   absolute roots.** Both are machine facts. `overlayDir` is hard-coded in
   `modules/link.nix:34` as `$HOME/.config/devman`, so the design inherits an
   existing assumption rather than adding one.
8. **`.devman-link-state.json` is read by nothing in this design and written by
   nothing in it.** The two-sided-edit refusal (033, F2) is untouched. That is
   deliberate, and it means this design does not fix the ledger's 34-project
   staleness either. Open question O4.
9. **A `[land]` hook makes `land` depend on `devman` being on PATH.** If
   `devman` is missing, `run_hook` returns *"hook command not found"*, exit 2, and
   the land is **BLOCKED**. In the machine-configuration repository that is a
   failure mode worth naming: a broken toolchain would make the overlay
   unlandable. The hook command should be the absolute system-profile path
   (`/run/current-system/sw/bin/devman`), which is the same path
   `modules/link.nix:70-75` already relies on for shell entry.

---

## 12. What I could not determine

1. **Whether the 2026-09-19 projection loss was noticed and accepted, or missed.**
   `37050e9`'s message says consumers are link-only and the module is a
   compatibility shim. It does not mention `doctor`'s `link drift`. Nothing in
   `.scratch/projects/038-*` or `039-*` records the check going vacuous.
   *Settled by:* asking the author, or finding it in a stage log.
2. **What wrote `.devman-link-state.json` at 19:35 today**, and which two
   projects left it. The readiness review measured 456/84 at ~17:16; it holds
   450/82 now. A shrink in the file holding the two-sided-edit baseline is the
   one direction that should not happen silently.
3. **Whether `repair` would adopt the 59 paths cleanly.** `gitman repair` —
   *"Adopt stray changes into lanes and heal jj↔git ref drift"* — is the
   sanctioned answer to unbookmarked work, and it is the verb that would have
   addressed the 155. Not exercised here: running it mutates the live repository.
   *Settled by:* `gitman repair --dry-run`, if that flag exists.
4. **Whether any managed repository lives outside `~/Documents/Projects/`**
   (limit 3).
5. **Whether the classifier denies `gitman land` in the overlay every time, or
   denied it once on lane size.** One observation, reported by the operator, not
   reproducible from here. It changes §10's emphasis but not its conclusion.
6. **Whether `linkman check`'s `clean: true, total: 0` on a missing config is
   intended.** It reads as a deliberate "nothing declared, nothing wrong", and it
   is also a check that cannot fail. Linkman's owner's call (O6).
7. **Whether 025 §10's preserved items 2 and 13 survived `37050e9`.** Both cite
   `modules/devenv.nix` by line — the duplicate-registration refusal at `:778-786`
   and the exclude writer's worktree awareness at `:798-827` — in a file that no
   longer exists. `doctor`'s `projection` and `dag names` checks cover item 2's
   property at audit time rather than by construction, and 033 moved item 13 into
   the Python reconciler. Both look covered; neither was verified here, and 025
   §10 says *"a restructure that loses one has failed."* Out of this project's
   scope and worth an explicit check (O7).

---

## 13. Open questions needing an operator decision

| Id | Question | Why it needs the operator | Blocks |
|---|---|---|---|
| **O1** | Land the two waiting lanes? `m14-central-residue` (59 paths, 12 live views) and `m14-central-dead-fixtures` (18 paths, C4's ten findings). The exposure in §1.3 is live until the first one lands. | Explicitly reserved to the operator by this project's charter, and it collides with the classifier (§10) | the hazard staying live |
| **O2** | Does devman's own `gitman.toml` `[publish] verify` move to `[land.pre_hook]`? Today `nix flake check` gates `publish` only, and every `land` in devman since `81a1340` ran no verify. Note `nix flake check` is currently **red** in devman, so this makes `land` fail until the cutover's Lane 2 blocker clears. | It changes whether devman can land at all today | devman's own lane loop |
| **O3** | `links.yaml` beside `devenv.local.nix` — two declarations of one thing, for all 78 projects (§6.3). Cutover-owned, but the P2/P4 violation is accumulating now. | Sequencing against Lanes 9d/9e and readiness-review B3/B4 | C1/C4's long-term shape |
| **O4** | Ask gitman for a working-copy-rewrite hook on `switch` / `split` / `abandon` (§8.2)? | A feature request against another repository, with a real cost | closing the §9 residual |
| **O5** | Does `doctor --prune` gain the ledger, or does the ledger get its own pruner? 82 projects against a live 66 (§2.4). The two-sided-edit baseline must survive whatever is chosen (033, F2). | It touches the one file standing between a two-sided edit and a silent overwrite | ledger staleness |
| **O6** | Does this project own the `~/.claude/AGENTS.md` fix? Measured: **two real files, not a symlink, not in the overlay, not under version control.** `AGENTS.md` lacks the entire "Version control lanes" section and still cites `my-ai/SKILL.md` where `CLAUDE.md` cites `writing/SKILL.md` — and 035 §8.5 decided that move, so `AGENTS.md` is the stale copy. By P0 both belong central, and 025 §10 item 11 requires `AGENTS.md` canonical with `CLAUDE.md` a symlink to it. **Recommendation: report only.** The fix is a link-plane rollout of `~/.claude`, and editing live operator policy mid-session is not this project's to do. | It is the operator's own standing policy document | agents reading AGENTS.md getting no lane policy |
| **O7** | `linkman check` reports `clean: true` on a dangling target and on a missing config (§3.4). Linkman is right by its contract; is the *report* right? | Linkman's boundary, mid-cutover | nothing here; recorded for Linkman |
| **O8** | Verify that 025 §10 preserved items 2 and 13 survived `37050e9` (§12.7). | *"A restructure that loses one has failed."* | nothing here; owed by the charter |

---

## 14. What this report did not do

No `gitman save`, `start`, `switch`, `split`, `land`, `abandon`, `repair`,
`sync`, `undo` or `describe` against `~/.config/devman`. No `git add`, `commit`,
`checkout` or `clean`. No file in any of the 78 central project directories was
opened for writing. No symlink was created, repointed or removed. No Nix file was
changed. `devman doctor` was run **without** `--prune`. No workflow was written
or registered.

**Raw `git` was used read-only** — `status`, `ls-files`, `ls-tree`, `rev-parse`,
`log`, `show`, `check-ignore`, `remote` — because gitman ships no `diff`, `show`
or `reflog` verb and no verb answering "is this path in trunk's tree". 035 §10
disclosed the identical choice with the identical justification, and the same
side effect applies: `git status` refreshed `.git/index`'s stat cache. Content
was not changed, and the index is jj's export artifact.

**Two mutations happened, both outside every managed repository**, in throwaway
`mktemp -d` directories under `/tmp`, both removed afterwards: a Linkman probe
with a deliberately dangling symlink (§3.4), and a colocated gitman repository
used to prove the `[land]` hook semantics (§4.2). Neither touched
`~/.config/devman`, `~/Documents/Projects/`, the registry, or the system profile.

`nix flake check` in devman is **red** and was not run. It is the cutover's Lane 2
blocker — the `python-tests` fileset omits `./tools` — recorded, owned elsewhere,
and deliberately not treated as this project's signal.
