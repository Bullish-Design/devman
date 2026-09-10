# 026 — the `*man` family, from first principles

**Measured:** 2026-09-09, on `server`, in `~/Documents/Projects`.
**Method:** direct inspection of source, manifests, git metadata, both registries,
and two timed `devenv shell` A/B runs. Every claim below carries a `file:line` or
the command that produced it.

**Verdict in one line: twelve repositories hold eleven jobs, eight of those jobs
have more than one implementation, and four of the twelve repositories have no
consumer at all.**

---

## 0. The three facts that decide everything

**F1. The family is 104 days old.** First commits: copyroom 2026-05-28, testee
2026-06-08, gitman 2026-06-15, docman **and** siteman both 2026-06-18, fleetman
and vendomat 2026-06-25, shellij 2026-07-13, foreman 2026-07-31, agentman
2026-09-08 — yesterday. Only devman predates them (2025-09-09) and repoman
(2026-01-02). Eight of the twelve were born in one hundred days.

Command: `git -C <repo> log --reverse --format='%ci' | head -1`.

Nothing here is legacy. Every boundary was drawn recently, in sequence, by
someone solving the next problem — not by someone partitioning a domain. **The
roster is an accretion, and the evidence is the calendar.**

**F2. Four members have zero consumers, and a fifth has one.**

| Member | Repos that declare it | Source of the count |
|---|---:|---|
| shellij | 55 | `grep -l '^  shellij:' */devenv.yaml` |
| devman | 53 declared, 51 registered | same; `ls ~/.local/share/devman/projects` |
| repoman | 23 declared, 21 enabled | same; `grep -lE 'repoman\.enable\s*=\s*true' */devenv.nix` |
| vendomat | 12 | same |
| docman | **1** (repoman itself) | same |
| **siteman** | **0** | same |
| **fleetman** | **0** | same |
| **foreman** | **0** | same |
| **agentman** | **0** | same |

gitman, testee and copyroom show 0 devenv.yaml inputs by design: they arrive
through repoman's shared toolchain venv and through `uv`. Their real adoption is
higher — 35 repos carry `gitman.toml`, 32 carry `.jj`, 21 declare `testee`, 21
carry `.copier-answers.yml`.

The single widest-reaching first-party artifact in the fleet is not a tool. It is
**`my-ai`, a Copier layer with zero Python, present in 62 of 74 repositories**
(`ls */.copier-answers.my-ai.yml | wc -l`). That number is the design.

**F3. The current shape costs almost nothing in time, and a real amount in
correctness.**

Warm `devenv shell -- true`, three runs each:

```
bare (nixpkgs only)                    0.23  0.21  0.23
lodestar (repoman + shellij + devman)  0.26  0.29  0.26
foreman (same stack)                   1.77  0.29  0.29   # first run cold
```

**The whole family stack costs about 0.06 s of warm shell entry.** Any
consolidation argument that leads with speed is an aesthetic argument. Drop it.

The cost that is real: **every one of the 18 repositories that carries repoman's
router skill routes the agent to at least one skill file that does not exist.**

```
18 of 18 route to `testee`   — no repository has .agents/skills/testee/
10 of 18 route to `gitman`   — argentic flora flora-core foreman forgelab
                               image-gen-pipeline inferference lodestar
                               nix-paseo poddantic
 1 of 18 route to `docman`   — repoman itself
18 of 18 route to `copyroom` — resolves; copyroom exports its own skills
```

`foreman/.agents/skills/repoman/SKILL.md:29` tells the agent "open that manager's
own skill under `.agents/skills/`". `repoman/src/repoman/skills.py:5-6` claims the
router "only ever names installed managers (no dangling routes)". **It checks the
roster, not the filesystem, so the claim is false in 18 of 18 repositories.**

Only `copyroom` resolves — and it resolves because copyroom is the one tool that
converges its skills as package assets through `copyroom agent-files export`
rather than writing them once from an `init`. That single contrast is the whole
argument of §1, J7.

---

## 1. The job map

Eleven jobs. Twelve repositories. Eight of the eleven jobs have more than one
implementation.

### J1 — Reproducible per-repo environment
**Owner: devenv (third party).** 64 repositories carry `devenv.nix`. Not in scope.

### J2 — Repo identity → path on this machine · **4 implementations**
| Where | Scheme |
|---|---|
| `devman/src/devman/registry.py:33-36` | identity is **stated** as `devman.project`; registry at `~/.local/share/devman/projects/<name>/metadata.json`, written on shell entry |
| `fleetman/src/fleetman/models.py:26` | `name: str  # directory name (authoritative identity)` |
| `shellij/src/shellij/project.py:1` | sanitized CWD-relative path, else basename plus 8 hex of a sha256 of the resolved path |
| `vendomat/docs/DESIGN.md:349` | `VENDOMAT_DEV_ROOT`, default `~/Documents/Projects` — **documented and not implemented** (`grep -rn VENDOMAT_DEV_ROOT vendomat/src` returns nothing) |

**S1 said three. It is four.** shellij's is a third distinct scheme and it is
deployed in 55 repositories — wider than either registry.

### J3 — Put the first-party CLIs on PATH · **2 implementations, both live**
- `repoman/modules/scripts/repoman-sync.sh` — 614 lines of bash, `uv pip install`
  into a mutable venv at `~/.local/share/repoman/venv`.
- `vendomat/lib/mkToolchain.nix:1` — a Nix closure that **fails evaluation on a
  duplicate executable name** (`mkToolchain.nix:3`).

`repoman/modules/devenv.nix:95` already carries the seam: `cliProvider = "venv" |
"store"`. Default is `venv`. **No repository on this machine sets `store`**
(`grep -rn cliProvider */devenv.nix` → one comment in repoman itself). The Nix
path is built, documented, and unused.

The venv path's own comment records the hazard the Nix path removes:
`repoman/modules/devenv.nix:177-188` — "ORDER IS LOAD-BEARING … a stale
pre-migration copy of a manager CLI left in `.devenv/state/venv/bin` must not
shadow the shared toolchain. Getting this backwards is silent."

### J4 — Build a native wheel once
**Owner: vendomat** (`vendomat/lib/mkMaturinWheel.nix`). One implementation.
Correct, and it must be Nix.

### J5 — Version control · **2 implementations**
- `gitman` — jj through pyjutsu, zero raw-git subprocess (`gitman/AGENTS.md:19-24`).
- `copyroom/src/copyroom/_compat/gitutil.py:26` — **348 lines of `subprocess.run(["git", …])`**:
  `clone`, `fetch`, `worktree_add`, `worktree_remove`, `checkout_new_branch`,
  `commit_all`, `snapshot`, `list_tags`, `ls_remote_tags`, `commits_ahead`,
  `delete_branch`.

`grep -rn '"git"' <repo>/src` also hits vendomat (6), repoman (4) and docman (4).
copyroom is the only one large enough to be a second implementation.

### J6 — Verification
**Owner: testee.** One implementation. Correct.

### J7 — Converge a file into a repo from a canonical source · **6 implementations**
| Where | What it writes | Version record? |
|---|---|---|
| `copyroom/src/copyroom/agent/files.py:1` (446 lines) | the canonical skills, `AGENTS.md`, the `CLAUDE.md` symlink | yes — `.copier-answers.<layer>.yml`, three-way merge |
| `repoman/src/repoman/skills.py:1` (95 lines) | the generated router skill | no |
| `gitman/src/gitman/init.py:278` | `.agents/skills/gitman/SKILL.md` | no |
| `testee/src/testee/init.py:106` | `.agents/skills/testee/SKILL.md` | no |
| `docman/src/docman/init.py:49` | `.agents/skills/docman/SKILL.md` | no |
| `fleetman/src/fleetman/cli.py:337` | a skill under **`.claude/skills`** — the retired path; the family convention is `.agents/skills` (`repoman/modules/devenv.nix:143`) | no |

A seventh file, `repoman/src/repoman/devman/check.py:1`, exists only to lint the
ownership boundaries between the six.

**This is one job.** copyroom does it with a merge and a version record. The other
five do it with `write_text` and no record — which is why 18 of 18 router skills
point at a file that is not there (F3), and why copyroom's routes are the only
ones that resolve.

### J8 — Orchestrate work on Dagu · **2 implementations**
- devman — the whole repository. `devman/src/devman/run.py:1`, per machine, queues,
  receipts, tiers.
- `foreman/src/foreman/dagu.py:1` — 213 lines, per repository, "the only place in
  Foreman that knows the Dagu command line".

### J9 — Aggregate the managers and route the lifecycle · **2 implementations**
- `repoman/src/repoman/registry.py:66` + `aggregate.py`.
- `foreman/src/foreman/managers.py:1` — 375 lines. Its docstring: "RepoMan owns
  lifecycle coordination. GitMan owns workspaces… Testee owns verification." It
  then re-implements the invocation layer that names them.

### J10 — Bounded model invocation · **2 implementations**
- agentman — the whole repository (capsules, grants, chats, receipts).
- `foreman/src/foreman/agents.py:1` — 258 lines, a Pydantic-AI planner and
  implementer with capability-rooted containment. The same idea, written
  independently, five weeks earlier.

### J11 — Build a static site from Markdown, lint it, check its links · **2 implementations**
- docman — zensical + lychee + markdownlint-cli2 + typos + mdformat
  (`docman/modules/docman.nix:136-152`).
- siteman — Hugo extended + markdownlint-cli2 (`siteman/module/devenv.nix:29,33`).

Both repositories were first committed on **2026-06-18**.

### Also present, single-implementation, and real
- **Cross-repo index** — fleetman. See §3, Q5.
- **Fan out one command across repos** — `fleetman run`
  (`fleetman/src/fleetman/cli.py:188`) and, by the standing rule at
  `.scratch/projects/021-local-first-plane/ARCHITECTURE.md:238`, a devman workflow
  with many triggers. Two answers to one question.
- **Durable terminal workbench** — shellij. 55 consumers. Unique.
- **Work-item authoring** — foreman. Zero consumers.
- **Personal configuration content** — `my-ai`. Zero Python. 62 repositories.

---

## 2. The seed findings, confirmed or corrected

### S1 — CORRECTED, and the correction is sharper than the finding

The two registries do **not** cover the same 52 repositories, and one of them is
stale.

```
$ python3 … (diff of registry.json names vs ls ~/.local/share/devman/projects)
fleetman only: PyGentic atuout-reconciler-test clinch foreman forgelab fsdantic
               lodestar nix-meta nix-terminal nixos-core paloma-story-generation
               pytuin-desktop silverbullet-server        (13)
devman only:   argentic boomtube cairn changelog-e2e flora-qc grail llgym my-ai
               probe pyllij talkee templateer_v2 tyo3    (13)
both:          39
```

`.agents/index/registry.json` is dated **31 Jul 2026 17:20** — 40 days stale. It
misses 23 directories that exist on disk today, including agentman, my-ai, vendor
and tyo3, and it names one directory that does not exist
(`atuout-reconciler-test`).

**No tool reads it.** `grep -rn 'index/registry.json'` across the fleet returns
fleetman's own source and documentation, plus two prose mentions in design docs.
Its only consumer is an agent reading Markdown.

devman's registry is live — its newest entry was written today at 17:53. It is
also incomplete, and the reason is correct: four repositories carry
`devenv.local.nix` holding `devman.enable = lib.mkForce false`
(`foreman/devenv.local.nix:5`, and the same file in forgelab, image-gen-pipeline,
lodestar, all dated 8 Sep 2026). Its comment reads "Backburner: keep this
checkout out of the machine's devman plane." **That is a deliberate opt-out, not
a defect** — and it is direct evidence for Q5 below.

Add the fourth claimant: shellij (`shellij/src/shellij/project.py:1`), in 55
repositories.

### S2 — CONFIRMED, and the shortfall is worse than stated

`repoman/src/repoman/registry.py:66` holds exactly four entries: `copy`, `git`,
`test`, `doc`. `repoman/modules/managers/` holds exactly four files. The README
table is current.

The correction is to the other side. `repoman/CONCEPT.md:38` says "eight
instances of one pattern, **no conductor**". **Nowhere in repoman does anything
enumerate eight.** `repoman/CONCEPT.md:17-27`, the concept's own manager table,
names **five** — and explicitly excludes one of them: "shellij is the one
non-roster member of the family".

So the gap is not "conducts four of eight". It is that **"eight" is a number with
no list behind it.** Do not treat it as a target.

### S3 — CONFIRMED as a survey; here is the judgement it did not make

| Tool | Its refusal | Verdict |
|---|---|---|
| copyroom | managed⇒tracked⇒committed; `update` needs a clean worktree (`copyroom/src/copyroom/project/config.py:53`) | **Stands.** It is what makes a three-way merge safe. It does **not** block copyroom owning the agent surface — skills are tracked files. |
| repoman | no registry, no repo paths, fleet scope refused (`repoman/CONCEPT.md:38-40`) | **Stands, and it is decisive.** A tool that refuses fleet scope cannot conduct a fleet-shaped family. The refusal does not need reversing; it means repoman must shrink. |
| fleetman | read-only indexer by charter; hard-fails on symlinked project dirs (`fleetman/src/fleetman/run.py:143`) | **Falls with the repository.** "Read-only" is a scope statement, not an invariant. Zero consumers, 40-day-stale output. |
| vendomat | its shared tree is a read-only `/nix/store` path | **Stands.** That is what build-once means. |
| gitman | repo-scoped by invariant; nested `.gitignore` over `.git/info/exclude`, tests lock it in | **Stands.** Load-bearing, and enforced by construction (`gitman/AGENTS.md:51-55`). |
| siteman | documented decision against symlinks — **the seed cites `siteman/CONCEPT.md:95-98`, and that file does not exist.** The decision is real but lives at `siteman/.scratch/projects/01-brainstorming/CONCEPT.md:96,189`, and it is a Hugo file-watching risk, not an architectural refusal | **Moot.** The repository goes. |
| my-ai | deleted its own `my-ai-sync` file distributor on purpose (`my-ai/devenv.nix:35-38`) | **Stands, and it is the model for this whole project.** my-ai deleted its distributor, moved to a Copier layer, and reached 62 repositories. Copy that decision, do not reverse it. |

Two of seven refusals are territory rather than invariant. Both belong to
repositories with zero consumers.

### S4 — CORRECTED. The Nix line counts are inflated by worktrees and generated files

`repoman`'s 3164 Nix lines are `.devenv.flake.nix` (a devenv-generated file, 398
lines) counted three times, plus two full `.worktrees/` copies of the module tree.

| Repo | Python (src, no worktrees) | Nix as counted | **Nix, real** |
|---|---:|---:|---:|
| devman | 5331 | 3007 | **2790** |
| repoman | 1517 | 3164 | **652** |
| fleetman | 1519 | 69 | 69 |
| gitman | 6500 | 391 | **146** |
| siteman | 0 | 176 | 176 |
| docman | 400 | 389 | 389 |
| foreman | 2857 | 235 | 214 |
| agentman | 2437 | 229 | 229 |
| copyroom | 8739 | 176 | 176 |
| vendomat | 2372 | 1165 | **836** |
| testee | 2180 | 107 | 107 |
| shellij | 987 | 310 | 310 |

Exclusion: `-not -path '*/.worktrees/*' -not -path '*/.scratch/*' -not -name '.devenv.flake.nix'`.

**repoman is not Nix-heavy. It is 1517 Python to 652 Nix, and its own concept says
"the center of gravity is Nix" (`repoman/CONCEPT.md:222`).** That inversion is the
finding, and it is the opposite of what the seed table implied.

Genuinely two things: **devman** (2790 Nix is a NixOS module, a Dagu package, a
renderer and a 850-line devenv module — all real) and **vendomat** (836 Nix is the
product; the 2372 Python is publishing around it).

Genuinely a module with no library: **siteman** (0 Python, correct as-is) and
**docman** (400 Python of `cli`/`doctor`/`init`/`models` wrapped around a 268-line
devenv module that holds the actual behaviour).

### S5 — MEASURED. See F3. The headline is that time is not the cost

- Warm shell entry: **+0.06 s** for the full family stack over a bare devenv.
- `devenv.yaml` inputs: **median 5 per repo, median 2 of them family members.**
- CLIs on PATH in a repoman repo: **6** — measured inside foreman's shell:
  `gitman`, `testee`, `copyroom`, `repoman` (toolchain venv and consumer venv),
  `shellij` (Nix store), `devman` (system profile).
- `AGENTS.md` files an agent must read: **1** per repo, with `CLAUDE.md` symlinked
  to it. This convention works and is universal.
- Skills an agent must read: **13 directories, 520 lines, 3935 words** in a
  typical repoman repo. **Seven of the thirteen are `devenv-*` literacy docs**, not
  manager skills. Only `repoman`, three `copyroom-*` and `my-ai` are manager
  surface.
- **The dangling-route defect: 18 of 18.** See F3.

### One more, unlisted

**Four of the twelve `AGENTS.md` files are unedited seed templates.** repoman,
fleetman and siteman all still read, at line 10:

```
_One paragraph: what it does, who uses it, what it is not._
```

The kickoff calls `AGENTS.md` "the law each tool wrote for itself — this is the
primary source". **For repoman, fleetman and siteman, no such law was ever
written.** The conductor has no written law. That is not a minor documentation
gap; it is the absence of the evidence a boundary claim needs.

---

## 3. The decisions

### Q1 — What is the irreducible set of jobs?

**Eleven, listed in §1. Eight of them have more than one implementation.** The
foundation of everything below is one observation:

> **J7 is not six jobs. It is one job done six ways, and copyroom already does it
> correctly.** "Put a file into a repository from a canonical source and keep it
> converged" is exactly Copier's problem. copyroom solves it with a version record
> and a three-way merge and reaches 62 repositories. The other five write bytes
> and forget.

### Q2 — Which boundaries are real?

**Real — each names an invariant that would break if merged:**

| Member | The invariant |
|---|---|
| **gitman** | canonicity, enforced transactionally: trunk frozen at init, one lane per change, gitman the sole writer under a lock, auto-rollback on violation (`gitman/AGENTS.md:51-55`). Merging it into anything that also writes the repo breaks I4. |
| **testee** | its tools import the consumer's code, so it must be a per-repo `uv` dependency and can never be a shared CLI (`repoman/src/repoman/registry.py:96-97`). Mechanically forced. |
| **copyroom** | a per-repo version record plus a real three-way merge. Nothing else in the family can converge a file twice. |
| **devman** | one control plane per machine, and a small set of machine-global names every repository inherits (`devman/AGENTS.md:55-61`). Two planes is two Dagu homes. |
| **vendomat** | build-once means a read-only content-addressed store path. This must be Nix. |
| **shellij** | one server-side Zellij daemon per project, outliving the shell. Not a manager, and repoman already says so (`repoman/CONCEPT.md:26`). |
| **agentman** | a grant is a PATH closure — absence is the boundary, not a prohibition (`agentman/AGENTS.md:54-57`). |

**Name-only — the distinguishing property is the suffix:**

| Member | Why it is a merge candidate |
|---|---|
| **repoman** | No invariant is stated anywhere. Its `AGENTS.md:10` is an unedited template. Its concept claims a Nix center of gravity that the line counts contradict (S4). What consumers actually take is one devenv module and one sync script. |
| **fleetman** | "read-only indexer by charter" is a scope, not an invariant. Zero consumers, 40-day-stale output, and a `.claude/skills` writer on the retired path. |
| **docman** | A devenv module with a Python wrapper. One consumer. Same job as siteman. |
| **siteman** | 0 Python, 176 Nix, zero consumers. Same job as docman, born the same day. |
| **foreman** | Backburnered by its own owner (`foreman/devenv.local.nix:5`). Re-implements devman (J8), repoman (J9) and agentman (J10). |

### Q3 — Who owns repo identity?

**devman. One answer, and the losers are not symmetrical.**

devman states identity in tracked source (`devman.project`), records it on shell
entry, and refuses directory-name inference because it loses run history. Its
registry was written today. It is the only one of the four that is both current
and correct.

- **fleetman loses outright.** `fleetman/src/fleetman/models.py:26` is a latent
  bug by devman's own reasoning, and its output is 40 days stale with no reader.
  Migration: fleetman's index job moves to devman, reads
  `~/.local/share/devman/projects/*/metadata.json` for name and path, and derives
  only the edges it is genuinely good at (`pyproject.toml` deps, `flake.nix`
  inputs). Roughly 200 lines. See Q5.
- **shellij does not lose, because it is not asking the same question.**
  `shellij/src/shellij/project.py:1` computes a *session name* from a path. That
  is correct for a daemon that must work in a worktree, in a clone, and outside
  the plane. **Rename the concept, do not merge the code.** State in shellij's
  (currently unwritten) `AGENTS.md` that the identifier is a session key, never a
  repository identity, so nobody joins it to devman's registry later.
- **vendomat's `VENDOMAT_DEV_ROOT` is not implemented.** Delete the documented
  seam (`vendomat/docs/DESIGN.md:349`) rather than build it. If vendomat ever
  needs a path, it reads devman's registry.

### Q4 — Does the family need a conductor, and is it repoman?

**No, and no — but do not delete repoman.**

The family needs two things that repoman already ships, and neither is a
conductor:

1. **One devenv meta-module** so a repository declares one input
   (`repoman/modules/devenv.nix`, 211 lines). This earns its keep: 21 repositories
   use it.
2. **One generated router skill** so an agent has one entry point
   (`repoman/src/repoman/skills.py`, 95 lines).

What it does **not** need is a Python program that re-invokes four CLIs and takes
the worst exit code. `repoman doctor` / `status` / `managers` are 1517 lines of
Python for a job that is `set -e` plus arithmetic — and the aggregation is already
duplicated by `foreman/src/foreman/managers.py`.

**Keep the four-manager roster at four.** `copy`, `git`, `test`, `doc` are
lifecycle phases: scaffold → change → verify → save → docs. devman, vendomat and
shellij are not phases; they are the plane, the Nix layer and the terminal. They
must not be added, and `repoman/CONCEPT.md:38` should be corrected rather than
satisfied.

**What repoman's 4681 lines become:** roughly 650 Nix (the meta-module, the four
manager modules, plus docman's docs module moved in), 614 lines of sync bash that
should be deleted with J3 (see Q6/M1), and about 400 lines of Python — the router
generator and the ownership lint. The `doctor`/`status`/`managers` aggregation
retires.

And **fix the router first**: make `skills.py` check the filesystem, not the
roster, so its "no dangling routes" claim becomes true (F3). That is a one-day fix
with an 18-of-18 defect behind it, and it is independent of everything else here.

### Q5 — What can be deleted outright?

| Member | Consumers | Decision |
|---|---:|---|
| **siteman** | 0 | **Delete.** 0 Python, 176 Nix, same job as docman, born the same day. If Hugo is ever wanted, it is a backend option in the docs module, not a repository. |
| **fleetman** | 0 | **Delete the repository, keep ~200 lines of the job.** `index` and `graph` become `devman fleet index` over the live registry. `fleetman run` is a devman workflow with many triggers — the standing rule at `021-local-first-plane/ARCHITECTURE.md:238` already says so, and D-07 (which made fleetman the sole cross-repo owner) is superseded by the measurement that nothing reads its output. |
| **foreman** | 0 | **Archive.** Its owner already parked it (`foreman/devenv.local.nix:5`, 8 Sep 2026), it has not moved since 2026-08-19, and its three subsystems duplicate devman, repoman and agentman. Salvage before archiving: `foreman/src/foreman/identity.py:1` is a clean deterministic run-identity digest and `effect_digest` binds an approval to the values approved. devman's receipt work (project 019) is the right home if it lacks an equivalent. |
| **docman** | 1 | **Keep the module, delete the library.** `docman/modules/docman.nix` (268 lines) holds the behaviour. The 400 Python is `cli` + `doctor` + `init` + `models` — `init` is copyroom's job (J7), `doctor` is the module's, and the wrapper adds nothing the module cannot. Move the module into repoman's `modules/` beside the four manager modules. |
| **agentman** | 0 | **Keep.** This is the one member whose zero is "new", not "unused": 29 commits, first commit 2026-09-08, and devman project 022 already built the `devman-agentman/v1` contract for it (`agentman/AGENTS.md:87-88`). Judge it again when that contract has shipped. |

That is **three repositories deleted, one reduced to a module, and no capability
lost.**

### Q6 — What should merge, concretely?

Ordered by value over cost.

**M1 — One way to put the family CLIs on PATH: `repoman-sync.sh` retires, vendomat's closure wins.**
`vendomat/lib/mkToolchain.nix:3` fails evaluation on a duplicate command name.
`repoman/modules/devenv.nix:177-188` documents that its venv path resolves the same
collision by PATH order, silently. **One of these is correct and the other records
its own hazard in a comment.**
The seam exists (`cliProvider`) and is unused. Do not ask consumers to set it —
have repoman's module import vendomat's toolchain module and flip the default.
*Cost:* 21 repositories gain one `devenv.yaml` input; 614 lines of bash and the
mutable `~/.local/share/repoman/venv` retire. The machine `repoman.lock`
(`repoman/repoman.lock`) becomes a Nix input set. This is the largest single
reduction in the family, and it is also the riskiest — both repositories are hot
(74 and 105 commits in 90 days). Do it last.

**M2 — docman ← siteman.** One docs job. *Cost: zero.* Neither has an external
consumer worth the name.

**M3 — copyroom ← every `init` that writes a skill.** One agent-surface writer,
with a version record. gitman, testee, docman and fleetman each lose ~150 lines;
repoman's router generator stays, because it is generated from the roster and is
not template content.
*Cost:* gitman and testee would gain a copyroom dependency for adoption only —
which breaks gitman's stated goal that adopting it needs "one `[tool.uv.sources]`
entry and no nix" (`gitman/AGENTS.md:94`). **Lower-cost alternative, and the
recommended one:** the skills stay package assets in each tool, and
`copyroom agent-files export` discovers them through a Python entry point. One
writer, one merge, one record — and no tool depends on copyroom to install.

**M4 — devman ← fleetman's index.** ~200 lines against the live registry. *Cost:*
the `.agents/index/*` path stays, so any agent habit survives; one repository
retires.

**M5 — copyroom ← its own git.** `copyroom/_compat/gitutil.py` is 348 lines of
`subprocess.run(["git", …])` in a family whose VCS tool reduced its raw-git
surface to zero. *Cost:* real and possibly prohibitive — copyroom must work in
repositories that have never heard of gitman (it is the adoption tool). **Do not
merge. Record it as a known second implementation, and forbid it from growing.**
This is the one duplicate that should stay.

### Q7 — The target shape

**Four planes, seven repositories, three content repositories.**

```
                       ┌──────────────────────────────────┐
  one devenv input  →  │  THE NIX PLANE                   │
                       │  repoman   the meta-module,      │
                       │            the docs module,      │
                       │            the router generator  │
                       │  vendomat  build once; ONE       │
                       │            command closure       │
                       └───────────────┬──────────────────┘
                                       │ puts on PATH
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
┌───────▼────────┐   ┌─────────────────▼──────────────┐   ┌───────────▼────────┐
│ THE FILE PLANE │   │ THE REPO PLANE                 │   │ THE FLEET PLANE    │
│                │   │                                │   │                    │
│ copyroom       │   │ gitman   change  (jj + git)    │   │ devman   identity, │
│  templates,    │   │ testee   check   (pytest/ruff) │   │          registry, │
│  layers,       │   │ shellij  see     (zellij)      │   │          when work │
│  agent surface │   │                                │   │          runs,     │
│                │   │                                │   │          fan-out   │
│ content repos: │   │                                │   │ agentman what one  │
│  template-py   │   │                                │   │          model run │
│  template-nix  │   │                                │   │          may be    │
│  my-ai         │   │                                │   │                    │
└────────────────┘   └────────────────────────────────┘   └────────────────────┘

  retired: fleetman → devman fleet index · siteman → the docs module
           foreman  → archived (devman + repoman + agentman already hold its jobs)
           docman   → its module moves into repoman; its library retires
```

**The paragraph.** A repository declares one input and imports one module. That
gives it a pinned environment and one command closure, built once in the Nix
store, that fails to evaluate rather than shadow a duplicate command. Inside that
shell an agent has one entry skill and four verbs: **converge** (copyroom),
**change** (gitman), **check** (testee), **see** (shellij). Everything the
repository knows about itself it states in its own `devenv.nix`; everything the
machine knows about the repository lives in one registry keyed by that stated
name. When work must run without a person, devman decides whether it may start
and where the write lands; when that work is a model, agentman decides what the
run is allowed to be. **No tool owns a second copy of another tool's job, and no
file arrives in a repository without a version record saying where it came from.**

**The honest distance.** Closer than the twelve-repository count suggests, and
further than the deletions suggest.

- **Free today:** deleting siteman, archiving foreman, retiring docman's library.
  Zero consumers, zero migration. Perhaps two days including the documentation.
- **Cheap:** M4 (fleetman → devman, ~200 lines) and fixing repoman's router to
  check the filesystem. A week.
- **Expensive and worth it:** M1. It touches 21 repositories, retires 614 lines of
  bash and a mutable machine venv, and merges the two hottest repositories in the
  family. Several weeks, and it should not start until M2–M4 have landed.
- **Not worth it:** M5, and any attempt to make repoman a real conductor.

**Is it worth it?** For M2, M4 and the router fix: unambiguously, because they
remove code with no consumer and fix a measured defect. For M1: yes, but the
argument is correctness (silent PATH shadowing), not tidiness — and it must be
made that way or it will not survive contact. For M3: only in the entry-point
form, and only after M1.

### Q8 — What must be preserved

Each of these was paid for once. A consolidation that loses one has failed.

1. **Stated identity, never inferred.** `devman.project` in tracked source;
   `devman/src/devman/registry.py:36`. Directory-name inference loses run history
   (`024-personal-overlay/CONCEPT.md` §8). This is the single most important
   decision in the family.
2. **The tier table**, and the shape it excludes: `free` / `lane` / `insitu`, and
   "an unattended write to trunk has no tier" (`devman/AGENTS.md:120-131`).
3. **Prefer a loud refusal to a silent default**, and prefer a check that can
   fail. Behind it: `devenv test` exited 0 having tested nothing in 30 of 58
   repositories, for a month (`devman/AGENTS.md:106`).
4. **The plane holds no project fact** (`devman/AGENTS.md:67`). No absolute path
   in a workflow, no project name in the machine module.
5. **Secrets are declared, never held — and masking covers the exact value only.**
   Measured: a step echoing five characters of a token logged them in clear
   (`devman/AGENTS.md:75-81`).
6. **gitman's canonical-lane invariants I1–I5, enforced by construction** with
   op-id capture and auto-rollback, and its refusal ever to pass
   `ignore_immutable=True`, with a test enforcing it (`gitman/AGENTS.md:29-32`).
7. **testee is a per-repo `uv` dependency because its tools import the consumer's
   code** (`repoman/src/repoman/registry.py:96-97`). Never promote it to the shared
   toolchain.
8. **Layers are discovered by glob, never configured**, and converge independently
   (`copyroom/AGENTS.md:65-66`). This is why `my-ai` reaches 62 repositories
   without a registry.
9. **`mkToolchain` fails evaluation on a duplicate executable name**
   (`vendomat/lib/mkToolchain.nix:3`). Carry this into the merged Nix plane
   verbatim; it is the property that makes M1 a correctness argument.
10. **The 0/1/2/3 exit-code contract.** Universal, cheap, and the only reason any
    aggregation is possible.
11. **`AGENTS.md` canonical, `CLAUDE.md` a symlink to it.** One file per repo, and
    it already holds in all 12.
12. **Absence is the boundary** — a capsule gets a grant; never write a
    prohibition where an absent capability will do (`agentman/AGENTS.md:54-57`).
13. **my-ai's own deletion.** It removed its file distributor and became a Copier
    layer (`my-ai/devenv.nix:35-38`). That single decision is the pattern this
    whole consolidation is applying to the rest of the family.

---

## 4. The migration plan

Each step is independently useful and independently reversible. None depends on
the step after it.

| # | Step | Size | Reversible by |
|---|---|---|---|
| 1 | **Fix repoman's router to check the filesystem, not the roster.** `repoman/src/repoman/skills.py` renders a route only when `<skills_dir>/<skill>/SKILL.md` exists; otherwise it names the command and says the skill is absent. | ~30 lines + a test | reverting one file |
| 2 | **Write the three missing `AGENTS.md` files** — repoman, fleetman, siteman. State the invariant or state that there is none. Do this before deciding anything else about those three. | half a day | n/a |
| 3 | **Delete siteman.** Zero consumers. Record the Hugo option in the docs module's README as a road not taken. | one repo archived | `git clone` |
| 4 | **Archive foreman**, after lifting `identity.py` into devman if devman lacks an equivalent receipt digest. | one repo archived | `git clone` |
| 5 | **Retire docman's library; move `modules/docman.nix` into repoman's `modules/`.** `docman init` retires under step 7. | ~400 Python deleted, 268 Nix moved | reverting one commit; 1 consumer |
| 6 | **`devman fleet index`** over the live registry, writing `.agents/index/{registry.json,PROJECTS.md}` at the same paths. Run it once, confirm the output matches what an agent expects, then **delete fleetman**. | ~200 lines Python | the paths are unchanged; fleetman still clones |
| 7 | **One agent-surface writer.** `copyroom agent-files export` discovers per-tool skills through a Python entry point. gitman/testee `init` stop writing skills. | ~150 lines removed per tool, ~80 added to copyroom | each tool's `init` is one file |
| 8 | **Flip `cliProvider` to `store` by default**, with repoman's module importing vendomat's toolchain module so consumers change nothing but the input list. Keep `venv` working for one release. | 21 repos, 614 lines of bash retired | the enum still has `venv` |
| 9 | **Merge vendomat's `lib/` and flake outputs into repoman**, keeping the consumer-facing name `repoman.enable`. Only after step 8 has been stable for a release. | two hot repos become one | hardest to reverse — do it last |

**Order matters in exactly two places.** Step 2 before steps 3–6, so a deletion is
never argued from an absent document. Step 8 before step 9, so the interface moves
before the code does.

**Stop after step 7 and re-measure.** That is 12 repositories down to 9, the
measured defect fixed, and no repository has changed a line. Steps 8 and 9 are a
separate decision with a separate cost, and they should be taken on the strength
of the PATH-shadowing argument alone.

---

## 5. What I could not determine

1. **Whether agentman's zero consumers means "new" or "wrong".** It is one day
   past its first commit. The `devman-agentman/v1` contract is shipped on
   agentman's side and unadopted on devman's
   (`agentman/AGENTS.md:87-93`). *Settled by:* devman adopting `groups/agent/`
   and one repository running a real capsule. Re-ask then.

2. **Whether `copyroom/_compat/gitutil.py` can shrink at all.** I read its
   function list, not its callers. Some of it (`worktree_add`, `commits_ahead`,
   `snapshot`) may exist only for the workshop, which runs against template
   repositories, not managed ones. *Settled by:* a call-graph over
   `copyroom/src/copyroom/workshop/` versus `project/`. If the workshop is the only
   caller, the duplicate is smaller than 348 lines and the finding softens.

3. **What `foreman/src/foreman/identity.py` would cost to lift into devman.** I
   confirmed devman has a receipt (`devman/.scratch/projects/019-the-receipt/`) but
   did not compare its identity derivation to foreman's. *Settled by:* reading
   both and diffing the inputs each digest binds.

4. **Whether flipping `cliProvider` to `store` actually works today.** The code
   path exists and no repository uses it. I did not build
   `.#repoman-toolchain-core`. *Settled by:*
   `nix build .#repoman-toolchain-core --no-link --print-out-paths` in vendomat,
   then one repository entering a shell with `cliProvider = "store"` and running
   `repoman doctor`. **Do this before committing to step 8** — the whole M1
   argument rests on it.

5. **Whether any of the 23 unindexed directories are repositories that should be
   in devman's registry.** fleetman's index misses 23 directories that exist; I
   did not check which of them carry `devenv.nix`. *Settled by:* one loop
   comparing `ls -d */devenv.nix` against the registry, and reading each miss.

6. **Cold shell entry.** I measured warm entry three times per repo and saw one
   cold run at 1.77 s. A real cold-cache number needs `devenv gc` or a fresh
   `.devenv/`, which I did not do because it destroys state I was measuring
   against. *Settled by:* a throwaway clone of one consumer, timed once.
