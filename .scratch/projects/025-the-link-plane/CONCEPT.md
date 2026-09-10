# The development system — full concept

**Status:** concept. No code written.
**Measured:** 2026-09-09, on `server`. Every claim carries a command or a `file:line`.
**Evidence base:** [`FINDINGS.md`](FINDINGS.md) beside this file — the twelve-repository audit this design answers.
**Supersedes:** `devman/.scratch/projects/024-personal-overlay/CONCEPT.md` §3.2 (store location) and §2.5 (the dotbot rejection stands; the reasoning is corrected in §3.6).

---

## 1. The problem, in three numbers

The family is twelve repositories implementing **eleven jobs**, of which **eight
have more than one implementation**, and **four repositories have no consumer at
all**. Full evidence in `FINDINGS.md` §1–§2.

It is not incoherent because it is large. It is incoherent because **nothing binds
it**:

- **15 distinct `Report`/`Finding` classes**, zero shared. Ten of eleven packages
  depend on pydantic and typer and none agree on what a report is.
- **Zero entry points** anywhere. `repoman`'s roster is a hand-maintained dict
  with four entries, which is why its router names skills that do not exist in
  **18 of 18** repositories.
- **Eight config formats** — `gitman.toml`, `[tool.testee]`, `.docman/zensical.toml`,
  `copyroom.project.yml`, `repoman.lock`, `repos.toml`, `.foreman/`,
  `.pyjutsu-hooks.toml`.
- **Six independent writers** of the same agent-surface files.
- **Four identity schemes** for "repository → path on this machine", of which one
  is 40 days stale and one is documented but unimplemented.

**The fix is three things, not a rewrite:** a boundary rule that decides which
repositories exist, a declaration mechanism that makes independent repositories
compose, and one file-delivery mechanism that removes the copies.

---

## 2. The boundary, and four principles

### P0 — The boundary test

> **Would this still be true for someone else who cloned the repository?**
>
> - **Yes → it is the project.** It stays in the repository, tracked.
> - **No — it is true for *me* or *this machine* → it goes central**, and reaches
>   the repository as a symlink.

This is the operative rule. Every placement decision in this document is one
application of it, and nothing is decided per file type.

| In the repository | Central |
|---|---|
| `src/`, `tests/`, `pyproject.toml`, `flake.nix` | `.agents/` — how *my* tools work |
| `devenv.nix` — what the project needs to build | `devenv.local.nix` — what *I* add on *this* machine |
| `gitman.toml` — trunk name, repo policy | `.envrc` — *my* shell activation |
| `README.md`, `AGENTS.md` — what this project is | `.claude/settings.local.json` |
| `devman.project` — stated identity (P3) | `.devman/workflows/` — when *I* run things |
| | `.loci` — *my* thinking about the project |

**The pairs that make it sharp.** `devenv.nix` stays and `devenv.local.nix` goes:
same format, same shell, one says what the project needs and the other what I want
here. `AGENTS.md` stays and `.agents/skills/` goes: one is this project's law, the
other is identical in sixty repositories, which proves it is about none of them.
`devenv.nix`'s `tasks."base:check"` stays and the workflow that runs it nightly
goes: *how you check this project* is a project fact; *I want it checked at 3am* is
mine.

**The general shape: the repository declares what the operations are; the central
store declares my use of them.**

### The four principles


### P1 — One interface per engine

Count engines, not tools. Every keep and every retirement falls out of it.

| Engine | Interface | Status |
|---|---|---|
| Dagu | **devman** | keep — the plane |
| jj | **gitman** | keep as-is |
| pytest / ruff / ty | **testee** | keep as-is |
| Copier | **copyroom** | keep |
| zensical / hugo | **docman** | keep; siteman folds in as a backend |
| Zellij | **shellij** | keep |
| an LLM API | **agentman** | keep |
| Nix / uv / maturin | **vendomat** | keep |
| — none — | fleetman | a scanner, not an interface → its job is devman's registry |
| — duplicate — | foreman | a *second* interface to Dagu, to the managers, and to Pydantic-AI → archive |
| — assembly — | **repoman** | not an interface; the one flake a consumer imports |
| — contract — | **substrate** | new, small, the missing piece |

**Wrap an engine; never rebuild one.** This is the family's original thesis. It
was correct and applied inconsistently.

### P2 — Source or projection, never a copy

Every file in a working tree is either **source** (a human wrote it, git tracks
it, nothing regenerates it) or **projection** (something built it, git ignores it,
it is a symlink). The third category — *copies* — is where every drift defect
lives: 18-of-18 dangling routes, two disagreeing registries, a 40-day-stale index.

### P3 — Stated identity, never inferred

`devman.project` in tracked source. Directory-name inference loses run history
(`devman/src/devman/registry.py:33-36`). This is the single most important
decision the family already made.

### P4 — One mechanism per job

Where two mechanisms exist for one job, one of them is drift waiting to happen.
Where a split is genuinely forced — as it is between tracked and untracked files
(§3.1) — the rule that divides them must be a property, not a file type.

---

## 3. The system: four planes

```
                      ┌───────────────────────────────────────────┐
   one devenv input → │  THE NIX PLANE      repoman + vendomat    │
                      │  environment, and every CLI on PATH       │
                      └────────────────────┬──────────────────────┘
                                           │
   ┌───────────────────┬───────────────────┼───────────────────────┐
   │                   │                   │                       │
┌──▼──────────────┐ ┌──▼───────────────┐ ┌─▼──────────────────┐ ┌──▼─────────────┐
│ THE FILE PLANE  │ │ THE LINK PLANE   │ │ THE WORK PLANE     │ │ AGENT SURFACE  │
│                 │ │                  │ │                    │ │                │
│ copyroom        │ │ devman.link      │ │ devman + Dagu      │ │ the config     │
│ TRACKED content │ │ UNTRACKED content│ │ when work runs,    │ │ repo owns ALL  │
│ templates,      │ │ machine-local    │ │ queues, receipts   │ │ skills (§7)    │
│ layers,         │ │ config, notes,   │ │                    │ │                │
│ AGENTS.md       │ │ overlays,        │ │ gitman decides     │ │ one .agents    │
│                 │ │ **the agent      │ │ where writes land  │ │ link per repo  │
│ 3-way merge +   │ │   surface**      │ │ testee decides     │ │ + one          │
│ version record  │ │ one inode,       │ │ if it is green     │ │ generated      │
│                 │ │ zero drift       │ │                    │ │ router         │
└─────────────────┘ └──────────────────┘ └────────────────────┘ └────────────────┘
```

### 3.1 The line between the file plane and the link plane

**git forces it.** A symlink is stored as mode `120000` whose blob is the path
string; the content behind it is never tracked, and an absolute path dangles on
any other machine. Measured:

```
$ git ls-files -s
120000 3d5002cd... 0    notes
$ git cat-file -p 3d5002cd
/tmp/gitsym-UjNq/external/notes          ← the blob is an absolute path
$ git ls-files | grep note.md            ← nothing
```

Therefore:

| Content | Mechanism | Why |
|---|---|---|
| **Tracked, shared** — `AGENTS.md`, templates, genome content | **copyroom** | git must see the bytes; a version record and a three-way merge make it updatable |
| **Untracked, machine-local** — `devenv.local.nix`, `.envrc`, notes, overlays, **`.agents/`** | **the link plane** | one inode means zero drift, and nothing enters anyone's history |

This is not a file-type split. It is one property — *does git track it* — and it
is not negotiable.

**The one deliberate exception is the agent surface.** `.agents/skills` is tracked
today in every repository sampled (gitman 5 files, testee 5, copyroom 5, my-ai 6,
foreman 13, shellij 14) — and §7 moves it to the link plane on purpose, because a
skill is only *actionable* inside the devenv shell, so cold visibility buys
nothing. `AGENTS.md` and `CLAUDE.md` stay tracked and become the cold entry point.

---

## 4. The Nix plane

One input, one import, and a repository has its environment and every CLI.

```yaml
# devenv.yaml
inputs:
  repoman: { url: "git+https://github.com/Bullish-Design/repoman?dir=modules&ref=refs/tags/vX.Y.Z", flag: false }
```

```nix
# devenv.nix
{
  repoman.enable   = true;
  repoman.managers = [ "copy" "git" "test" ];
  devman = { enable = true; project = "flora"; groups = [ "base" ]; };
}
```

**Two corrections to today's shape:**

1. **One way to put CLIs on PATH.** `repoman/modules/scripts/repoman-sync.sh` is
   614 lines of bash filling a mutable venv; `vendomat/lib/mkToolchain.nix:3`
   builds a Nix closure that **fails evaluation on a duplicate executable name**.
   repoman's own comment records that the venv path resolves the same collision by
   PATH order, silently (`repoman/modules/devenv.nix:177-188`). The seam already
   exists — `cliProvider = "venv" | "store"` at `repoman/modules/devenv.nix:95` —
   and **no repository sets `store`**. Flip the default; do not ask 21 consumers
   to set it.
2. **testee stays a per-repo `uv` dependency.** Its tools import the consumer's
   code (`repoman/src/repoman/registry.py:96-97`). This is mechanically forced and
   must never be "fixed".

**Consequence, measured:** the toolchain venv runs `python3-3.13.15` and a
consumer venv runs `python3-3.14.6`. `gitman` is importable in one and `testee`
only in the other. **Python entry points can never enumerate the family.**

### 4.1 The declaration mechanism: devenv module merging

devenv's module system merges a typed registry across independently imported
modules. Spiked:

```
mods/substrate.nix   options.dev.managers  (listOf submodule)
mods/gitman.nix      dev.managers = [ { key = "git";  command = "gitman"; } ];
mods/testee.nix      dev.managers = [ { key = "test"; command = "testee"; } ];

$ devenv shell -- echo $DEV_MANAGERS
  test:testee git:gitman
```

Each manager registers itself; the roster is **derived**. This is strictly better
than entry points here: language-agnostic, immune to the venv split, typed, and
it fails at eval rather than at runtime.

A symlinked `devenv.local.nix` sets custom options the same way:

```
PROJECT=flora
EXPOSE=[agents=.agents workflows=.devman/workflows]
```

---

## 5. The link plane

**One mechanism replaces every way an untracked file reaches a repository.**

A **link** has a **canonical** side and a **view** side. The canonical side holds
the content. The view side is a symlink to it. One reconciler makes the filesystem
match the declaration.

**Where the declaration lives.** In `devenv.local.nix`, not `devenv.nix` — by P0
it is *my* wiring, not the project's, and a collaborator's clone must not carry it.
Verified: a symlinked `devenv.local.nix` sets `devman.link` and the module reads it,
because Nix merges both files into one config.

```nix
# devenv.nix — TRACKED. Three lines, the only devman fact the project owns.
devman = { enable = true; project = "flora"; };
```

`devman.project` staying tracked is P3, not a compromise: identity is stated in
tracked source, never inferred.

```nix
# devenv.local.nix — symlinked from ~/.config/devman/projects/flora/
{ ... }: {
  devman.link = {
    ".agents"           = { canonical = "central";  path = "projects/${project}/agents"; };
    ".devman/workflows" = { canonical = "central";  path = "projects/${project}/workflows"; };
    ".claude/skills"    = { canonical = "central";  path = "projects/${project}/agents/skills"; };
    ".envrc"            = { canonical = "central";  path = "common/envrc"; };
    ".loci"             = { canonical = "external"; path = "~/Notes/1_Projects/${project}"; };
  };
}
```

**`devenv.local.nix` itself needs no declaration.** The module always links it from
`<overlayDir>/projects/<project>/devenv.local.nix` when that file exists. That one
**implicit bootstrap link** is the entry point; everything else is declared inside
it.

⚠ **The reconciler must never leave a dangling `devenv.local.nix`.** Nix evaluates
it before any hook runs, so a broken link fails shell entry with a trace nothing
can intercept — measured: `error: path '…/local.nix' does not exist`. Create the
canonical file before the link, always.

**Why the whole devman block does not move.** Putting `enable`/`project` in
`devenv.local.nix` needs the module input in `devenv.local.yaml`, and devenv merges
both yaml files before locking into one `devenv.lock` with no flag to redirect it
(project 024 §2.2). Every repository would carry a permanently modified tracked
lock. Three visible lines in `devenv.nix` is the cheaper trade.

### 5.1 Five states, one reconciler

| View side is… | Action |
|---|---|
| the correct symlink | nothing |
| a symlink to the wrong target | repoint |
| **a real file or directory** | **promote content → canonical, then link** |
| absent | link it |
| absent, **and canonical absent** | create canonical (`mkdir -p`, or render `template`), then link |

The third row is the repair. It is a state, not a special case, so it needs no
separate workflow and no second mechanism.

### 5.2 Three behaviours derived from one declaration

1. **The symlink** — created and repointed by reconcile.
2. **The `.git/info/exclude` line** — for every view inside a git repository. You
   cannot link a file in and forget to exclude it, because both come from the same
   attribute. This extends a writer already proven in all 51 registered
   repositories (`devman/modules/devenv.nix:788-827`; verified at
   `copyroom/.git/info/exclude:7`).
3. **The drift assertion** — `test -L` plus `readlink -f`. This *is* the detector;
   it is only "which of the five states am I in".

### 5.3 Two triggers, one function

- **Shell entry.** Must run here. A naive relink would destroy an edit, so
  reconcile promotes first and links second.
- **The watcher.** `watchexec` ignores only `.devman/.runs/`, `.git/`, `.devenv/`,
  `.direnv/`, `.venv/`, `__pycache__/` and `node_modules/`, so every declared view
  path is already visible. A trigger-map entry calls the same function.

One operation, two callers. Not a hook *and* a workflow.

### 5.4 Three safety rules on promote

- **Record what was linked.** Store the content hash when the link is made. If
  canonical has *also* changed since, **refuse and report the conflict**. Never
  merge (`devman/AGENTS.md:63-67`).
- **Land it in a gitman lane**, `promote/<project>-<file>`. Never trunk.
  `devman/AGENTS.md:129` — *"An unattended write to trunk has no tier … A lane
  carries a name and a diff instead."*
- **Never delete.** Promote overwrites canonical, and the config repository is
  version-controlled, so a wrong promotion is one `gitman undo` away.

### 5.5 What actually breaks a link, measured

```
✅ shell >        ✅ shell >>       ✅ python open(w)      ✅ cp over it
❌ sed -i         ❌ sed -i.bak     ❌ python os.replace    ❌ jq + mv
```

**Only rename-based writers break a file link.** Directory links are immune,
because the files inside are real files. The break is silent — the repository
keeps working, only the central copy goes stale. This is why the reconciler
promotes before it links.

### 5.6 dotbot: rejected, with the reasoning corrected

dotbot 1.24.0 is in nixpkgs and the per-project-config shape **works** — absolute
targets outside the base directory are accepted for both `create:` and `link:`.
*The earlier objection about link direction was wrong and is withdrawn.*

The lifecycle is the problem:

| Test | Result |
|---|---|
| Idempotent re-run | ✅ silent no-op |
| Real directory holding user data, `relink: true` | ✅ refuses |
| Same with `force: true` | ❌ **"Removing agents"** — destroyed the data |
| Drop a link from the config, re-run | ❌ **orphan left forever** |
| Repo deleted → dead link, with `clean: ["."]` | ❌ **still there** |

`clean` removes only dead links pointing *inside* the base directory unless
`force: true` — the same flag that destroys real files. **dotbot adds; it never
converges.** Convergence is what a 52-project index needs most.

---

## 6. The work plane

**Dagu is the engine. devenv executes. devman is the contract between them.**
That statement is already devman's charter and it is correct. What changes is how
a workflow reaches Dagu.

### 6.1 Two layers: groups, then the per-repository overlay

devman already resolves workflows in layers —
`devman/src/devman/project.py:591-600`:

> *"`<workflow> -> the file that won §7.3`, group files then local overrides. The
> repository's own `.devman/workflows/` is the last layer and shadows every group,
> whole-file."*

**Central-with-per-repository-overlay is already the model.** Groups are the shared
layer; the local files are the overlay. The only defect is the path: `_sources`
hard-codes `root / ".devman" / "workflows"`, so the overlay sits in the project
repository.

**By P0 it does not belong there.** Look at what devman's five local workflows
actually are — `agent-review` (an agent reviews a commit; needs `claude-code` on
*this* machine), `gitman-commit-message`, `bench-entry`, `plane-report`,
`stack-validate`. None is project definition. They are personal automation that
happens to run in a repository, exactly the category notes and skills moved for.

So the overlay moves central and the repository gets a view:

```
~/.config/devman/projects/flora/workflows/*.yaml     canonical · tracked
flora/.devman/workflows -> that directory            gitignored · editable in place
```

`_sources` takes the overlay directory as a parameter instead of hard-coding it.

**Measured: exactly one repository has `.devman/workflows/` — devman itself.** Every
other project takes group workflows by writing `groups = [ "base" ]`, with no file
at all. That is the elegant part, and it is why the overlay is rare.

### 6.2 The workflow file, and the naming trap

```yaml
# ~/.config/devman/projects/flora/workflows/check.yaml
queue: light
steps:
  - name: check
    run: devenv tasks run -v base:check
```

**No `name:`, no `working_dir`, no `log_dir`.** devman's own settled decision,
stated at `devman/groups/base/workflows/check.yaml:14`: *"the file name is the
identity, and the projection supplies both directories."*

**Confirmed, and the reason matters.** `dagu ls` *displays* a stated `name:`, but
`dagu start <name>` resolves by **filename**. When they disagree you get a DAG you
can see and cannot run:

```
dags/wrongname-a.yaml -> repoA/check.yaml   (file says name: repoA.check)
$ dagu ls                → repoA.check
$ dagu start repoA.check → Error: failed to read ".../dags/repoA.check.yaml"
```

So the filename `<project>.<workflow>.yaml` is the identity **and** the collision
guard. Two projects may ship byte-identical `check.yaml` files; their symlink names
differ, and the duplicate-registration refusal
(`devman/modules/devenv.nix:778-786`) keeps project names unique. **Never add a
`name:` field.**

### 6.2a Replacing the render with a link — deferred

devman renders each workflow into the registry and symlinks the copy. A direct
symlink is possible and verified (§6.3) and would remove roughly 500 of
`project.py`'s 879 lines.

**It is not what makes workflows easy, and it is not next.** Of `check.yaml`'s 28
comment lines, **two** concern the projection. The rest are Dagu and devenv
semantics that survive any refactor: `-v` is load-bearing, without it
`devenv tasks run` swallows output and logs `{}` even on failure; no `type: chain`
for one step; a failure is named on stderr, and that moved between devenv 2.1.2 and
2.2.0.

**Once the overlay is central, the question also changes shape.** devman can link
straight from the config repository into the DAGs directory —
`dags/flora.check.yaml -> ~/.config/devman/projects/flora/workflows/check.yaml` —
and the project repository leaves the chain entirely. Revisit then, with evidence
from having written workflows in two or three repositories.

### 6.3 Measured: the whole chain works

| Property | Result |
|---|---|
| `dagu start <path>` / `dagu enqueue <path>` | Work. **A workflow runs with no plane installed at all** |
| `working_dir: ${PROJECT_DIR}` | Step ran in the repository and saw its files |
| Symlinked external DAG, discovered | Needs `dag_discovery: {symlinks: true}` — **already set in your live config** |
| Symlinked external DAG, **scheduled** | Fired at `19:43:00`, ran in the repository directory |
| **Editing the target in place, scheduler already running** | Fired `VERSION_TWO_EDITED` at `22:02:00` — **no re-link, no restart** |
| Two-hop chain (`dags/x` → `projects/f/workflows` → repo) | Discovered **and executed**, correct cwd |
| Multi-document YAML (parent + children in one file) | Works; `action: dag.run` resolved the in-file child |
| Repo DAG calling a registered shared DAG by name, with params | Works |
| Queue serialization via the scheduler | A ran 8 s, B held until A finished |
| `devenv tasks run` inside a step | 0.15–0.20 s. `devenv shell --` 0.31 s |

### 6.4 The one hazard that must be gated

Two DAGs directory entries resolving to one name:

```
dags/flora.nightly.yaml -> repoA     dagu start  → REPO_A (3/3)
dags/flora.nightly.yml  -> repoB     scheduler   → REPO_B
```

`dagu ls` prints the name twice, exit 0, no warning. **Manual verification cannot
detect it**, because the manual path picks the other file. Not symlink-specific —
two plain files collide identically.

Bounded: only `.yaml` and `.yml` are discovered (`.YAML`, `.json`, `.dag` are
ignored), and two files cannot share a full name in one directory. Under
`recursive: true` a duplicate basename in two subdirectories yields `No DAGs
found` — a loud total refusal, which is correct and inconsistent with the flat
case.

**Defence: the plane owns the DAGs directory exclusively, and refuses to link a
name already linked elsewhere.** Never skip it.

---

## 7. The agent surface

**The config repository owns every skill and every piece of agent configuration.**
A project repository holds one directory link and nothing else.

### 7.1 Why not copyroom

Skills look like tracked, shared content, which §3.1 assigns to the file plane.
They are the one exception, for a mechanical reason: **a skill is only actionable
inside the devenv shell.** A skill that says *"route all version control through
gitman"* is useless to a reader with no gitman, no testee and no toolchain venv —
which is exactly what a cold reader is. So the cold-visibility argument that keeps
`AGENTS.md` tracked does not reach skills.

Two more facts settle it:

- **Four sources ship overlapping skills today.** The genome
  (`template-py/template/.agents/skills/`) ships `copyroom`×3 and `devenv-*`×7;
  copyroom's package assets (`copyroom/src/copyroom/agent/assets/skills/`) ship the
  same `copyroom`×3; `gitman init` writes `gitman`; `repoman install-skills`
  generates the router. The copyroom trio is shipped twice, by two mechanisms.
- **The `.claude`↔`.agents` bridge is already a symlink**, and already drifted:
  `argentic/.claude/skills/argentic-overlay -> ../../.agents/skills/argentic-overlay`,
  while `flora` carries 11 real directories against 13 in `.agents`, and `fleetman`
  1 against 4. Seventeen repositories hold a mix of links and stale copies.

**Nothing auto-loads `.agents/skills/`.** An agent opens those files by path,
because `AGENTS.md` or the router points at them. A directory symlink resolves
transparently for that.

### 7.2 The shape

```
~/.config/devman/
  skills/                                      THE POOL — real files, tracked
    copyroom/  copyroom-adopt/  copyroom-template-edit/
    devenv-authoring/ … (the 7 literacy skills)
    my-ai/    gitman/    testee/    docman/
  agents/
    devenv/                                    the `.agents/devenv` docs export

  projects/flora/
    agents/                                    this repo's composed surface
      skills/
        gitman -> ../../../../skills/gitman    relative → TRACKED, portable
        testee -> ../../../../skills/testee
        copyroom -> ../../../../skills/copyroom
        repoman/SKILL.md                       generated router — real file, tracked
        flora-domain/SKILL.md                  project-specific — real file, tracked
      devenv -> ../../../agents/devenv
```

In the project repository, **one link** — plus the bridge:

```
flora/.agents        -> ~/.config/devman/projects/flora/agents    absolute → gitignored
flora/.claude/skills -> ../.agents/skills                          derived  → gitignored
```

### 7.3 Why it composes

**Selection is a directory of links.** Which skills a repository gets is expressed
by which links exist under `projects/<name>/agents/skills/` — `ls`-able, diffable,
and version-controlled, because relative links inside the config repository are
tracked (§2.5).

**The reconciler already knows the roster.** `devman.link` plus the manager roster
the devenv module merges (§4.1) is enough to create those links. No new mechanism.

**One link per repository, not one per skill.** `.agents` is a directory link, so
it is immune to the rename-on-save hazard of §5.5, and adding a skill to a project
is one `ln -s` in the config repository with no touch to the project at all.

**It collapses four sources to one** and cleans the 17-repository `.claude/skills`
mess in the same move.

### 7.4 What this gives up, stated

- **Cold readers see no skills.** `AGENTS.md` stays tracked and per-repository; it
  is the cold entry point, and it is the only thing a cold reader can act on.
- **The tools stop owning their own skills.** `~/.config/devman/skills/gitman/`
  becomes the source of truth, so bumping gitman means editing the config
  repository. This trades tool-coupled versioning for one place edited daily. It is
  a deliberate choice, not an oversight.
- **copyroom stops delivering the agent surface.** It keeps templates, layers and
  `AGENTS.md`. `copyroom agent-files export` no longer applies to skills, and the
  genome stops shipping them.

### 7.5 The router stays generated, and stays repoman's

`repoman install-skills` writes exactly one file: `repoman/SKILL.md`, rendered from
the roster. It must render routes from **what is on disk**, not from the roster —
otherwise it names skills the pool has not linked. That change is design-agnostic
and correct under any of these designs.

### 7.6 One report shape

Not one model — `testee`'s `Failure{kind, tool, message, file, line, test_id,
rerun_command}` is a *finding*, while gitman's `Change` / `Conflict` / `LandFold` /
`TrunkRef` are *domain state*. The substrate ships an **envelope** — `{tool,
version, status, exit, payload}` — with `list[Finding]` as the payload for checkers
and `RepoState` for gitman. An agent parses one outer shape; the inside stays
honest. Keep the `0/1/2/3` exit contract.

---

## 8. The layout

**Three roots, three owners.** Each holds one kind of thing and versions it on its
own terms.

```
~/.config/devman/                        ← a git repository, managed by gitman
  .gitignore                             projects/*/repo · projects/*/workflows
                                         projects/*/agents/index · projects/*/notes
                                         dags/ · **/.runs/ · notes/
  common/
    envrc                                one pinned direnvrc for the whole fleet
    claude.json                          the broad permission allowlists
  skills/                                THE POOL (§7) — real files, tracked
  projects/flora/
    devenv.local.nix                     tracked · real file
    claude.json                          tracked · real file
    agents/                              composed agent surface (§7.2) · tracked
    repo      -> ~/Documents/Projects/flora        ignored · absolute · derived
    workflows -> <repo>/.devman/workflows          ignored · absolute · derived
    notes     -> ~/Notes/1_Projects/flora          ignored · absolute · derived
  dags/
    flora.check.yaml -> ../projects/flora/workflows/check.yaml     ignored

~/Notes/                                 ← its OWN git repository. Not the config repo.
  .loci/vault.toml                       ONE vault manifest for every project
  1_Projects/flora/                      REAL directory — flora's notes live here
  1_Projects/argentic/  …
  Inbox/  Journal/  Library/  Scratch/   personal notes

~/Documents/Projects/flora/
  .loci -> ~/Notes/1_Projects/flora      symlink · .git/info/exclude'd

~/.local/state/devman/                   generated; never hand-edited
  projects/<name>/metadata.json, plan.json, triggers.toml
  runs/
```

**The `.gitignore` rule that makes the config repository safe:** *relative links
are tracked; absolute links are ignored.* A relative link points at content the
repository owns; an absolute link points at a machine fact. Verified by cloning.

**Why `~/.config` and not `~/.local/share`.** The tree holds real authored files —
`devenv.local.nix`, `claude.json`, the skill pool. That is configuration. Generated
state moves to `~/.local/state/devman/`, where it belonged.

### 8.1 `~/Notes` owns the notes, and owns their history

**This reverses an earlier version of this document**, which put the notes inside
the config repository with `~/Notes` as a view. That was wrong for a measured
reason: **`~/Notes` is a running service's data directory.** SilverBullet serves it
(`silverbullet-server/modules/silverbullet-server.nix:39` hard-codes
`default = "/home/andrew/Notes"`), writes `.chrome-data/` into it through the
Runtime API, and **auto-commits the space to git every 15 minutes**
(`:133`, `gitBackup.enable` defaults true). It already carries months of history.

So the goal — *project repositories stay streamlined, and all notes are versioned
separately on your own terms* — is met by leaving `~/Notes` exactly where it is and
pointing everything else at it:

| Access path | Mechanism |
|---|---|
| SilverBullet | native — `1_Projects/<repo>/` are **real** directories in its space |
| The project repository | `<repo>/.loci -> ~/Notes/1_Projects/<repo>`, excluded from that repo's git |
| The config repository | `projects/<repo>/notes -> ~/Notes/1_Projects/<repo>`, absolute → gitignored |
| Version control | `~/Notes`' own repository, on its own timer |

**No note content enters a project repository's history.** `.loci` is one excluded
symlink, and `.git/info/exclude` gets its line from the same `devman.link`
declaration that creates it (§5.2).

**`1_Projects/` already exists** and already holds repo names — `andrew`,
`argentic`, `flora`, `image-gen-pipeline`, `nix-nvim`, `nvcheck`, `shellij`. The
convention is in use; this wires it up.

### 8.2 One vault, and the release it needs

`~/Notes/.loci/vault.toml` is the single vault. Fifty-two vaults would mean
fifty-two caches and no cross-project links, which is loci's main feature.

loci is built for this alias shape. `loci-core/src/loci_core/vault/init.py:58`
carries `find_vault_root`, and decision **D-041** states it explicitly:

> *"`start` is RESOLVED first, which is what makes the friendly-alias case work…
> Discovery itself still refuses to follow symlinks (D-004); only root selection
> resolves."*

**But that code is unreleased.** Measured: the installed build is **0.3.0**, the
source is **0.4.2**, and `grep -c find_vault_root` in the installed package returns
**0**. So today the CLI defaults `--vault` to the cwd, and even a plain
subdirectory of a vault fails:

```
$ cd ~/Notes/1_Projects/flora && loci documents/list
error: VaultNotInitialized: no vault manifest at …/1_Projects/flora

$ cd flora && loci --vault ~/Notes documents/list
{'documents': [… '1_Projects/flora/idea.md' …]}   ✓
```

**Releasing loci-core 0.4.2 and rebuilding is a precondition** for the project-side
ergonomics. Until then, supply `--vault ~/Notes` — a `devenv` shell alias covers it.

### 8.3 Writing through a directory link is unrestricted

Create, edit, delete and rename all work through a directory symlink, and the
owning repository's git sees every change:

```
$ echo "# brand new" > <repo>/.loci/new.md
$ git -C ~/Notes status --porcelain
?? 1_Projects/flora/new.md
```

Editor atomic-rename saves are safe here — the link is on the **directory**, and
the files inside are real files (§5.5).

---

## 9. What a repository looks like, and the daily loop

```
flora/                              ← TRACKED. Code, and three lines of devman.
  devenv.nix                          devman = { enable = true; project = "flora"; };
  devenv.yaml                         repoman + devman inputs
  pyproject.toml  gitman.toml
  AGENTS.md                           this project's law — the cold reader's entry point
  src/  tests/

  devenv.local.nix  -> ~/.config/devman/projects/flora/devenv.local.nix   ← implicit bootstrap link
  .agents           -> ~/.config/devman/projects/flora/agents
  .devman/workflows -> ~/.config/devman/projects/flora/workflows
  .claude/skills    -> .agents/skills
  .envrc            -> ~/.config/devman/common/envrc
  .loci             -> ~/Notes/1_Projects/flora
```

**Every link is gitignored, via a `.git/info/exclude` line written from the same
declaration that created it.** `git status` shows code. `ls -la` shows where
everything else actually lives.

The loop:

```
devenv shell            registers, reconciles links, writes exclude lines
copyroom update         converge tracked template content
<change>
testee verify           check
gitman save / land      where the write goes
devman run <workflow>   when work runs unattended
```

Six commands, **one entry skill**, whose routes resolve because it renders from
what is on disk.

## 10. What must be preserved

Each was paid for once. A restructure that loses one has failed.

1. **Stated identity, never inferred** (`devman/src/devman/registry.py:33-36`).
2. **The duplicate-registration refusal** (`devman/modules/devenv.nix:778-786`) —
   with one file per name, it makes `<project>.<workflow>` unique by construction.
3. **The tier table** and the shape it excludes (`devman/AGENTS.md:120-131`).
4. **The plane holds no project fact** (`devman/AGENTS.md:67`). Link paths are a
   formula over `devman.project`.
5. **Prefer a loud refusal to a silent default** — behind it, `devenv test` exited
   0 having tested nothing in 30 of 58 repositories, for a month
   (`devman/AGENTS.md:106`).
6. **Secrets are declared, never held**, and masking covers the exact value only
   (`devman/AGENTS.md:75-81`).
7. **gitman's canonical-lane invariants I1–I5**, enforced by construction, and its
   refusal ever to pass `ignore_immutable=True` (`gitman/AGENTS.md:29-32,51-55`).
8. **testee is a per-repo `uv` dependency** (`repoman/src/repoman/registry.py:96-97`).
9. **Layers discovered by glob, never configured** (`copyroom/AGENTS.md:65-66`) —
   why `my-ai` reaches 62 repositories with no registry.
10. **`mkToolchain` fails evaluation on a duplicate executable name**
    (`vendomat/lib/mkToolchain.nix:3`).
11. **The 0/1/2/3 exit contract**, and `AGENTS.md` canonical with `CLAUDE.md` a
    symlink to it.
12. **Absence is the boundary** (`agentman/AGENTS.md:54-57`).
13. **The exclude writer's worktree awareness** (`devman/modules/devenv.nix:798-827`).

---

## 11. The switch-over

### 11.0 Constraints that bind the implementation

Two flake checks read `modules/devenv.nix` by literal path:

- `devman/flake.nix:80-95` (`shell-variable-unset`) requires every `devman_*=`
  assignment to appear in the `unset` block ending in `devman_cur`
  (`modules/devenv.nix:841-847`). **New shell variables go there in the same
  commit.**
- `devman/flake.nix:136-176` (`hook-path-refusal`) cuts the refusal block out by
  literal path.

`devman doctor` must exit 0 before any change to `modules/`, `groups/`, `nix/` or
`src/devman/` is committed (`devman/AGENTS.md:88-94`).

### Stage 0 — fix the front door (1 day)

Independent of everything else, and the only thing blocking daily use.

1. Render router routes from the filesystem (§7, change 1).
2. Archive **fleetman**, **foreman**, **siteman** — zero consumers each.
3. Write the three missing `AGENTS.md` files. `repoman/AGENTS.md:10`,
   `fleetman/AGENTS.md:10` and `siteman/AGENTS.md:10` are all still the unedited
   seed: *"One paragraph: what it does, who uses it, what it is not."*

### Stage 1 — create the config repository (½ day)

Reversible by deleting one directory.

1. `~/.config/devman/` — `git init`, then `gitman init --colocate`.
2. `common/envrc` — one pinned devenv `direnvrc`. Today the five repositories with
   an `.envrc` **all differ**, and two pin different devenv revisions (`nixvim` at
   `95f329d4`, `PyGentic` at `82c01476`). Converging them is a fix, not tidiness.
3. `common/claude.json` — the broad allowlists.
4. `notes/` — `loci init`. `~/Notes -> ~/.config/devman/notes`.
5. `.gitignore` — `projects/*/repo`, `projects/*/workflows`, `projects/*/agents`,
   `dags/`, `**/.runs/`.
6. A `check` task that evaluates every `projects/*/devenv.local.nix`. A store whose
   Nix does not evaluate breaks every repository at once.

### Stage 2 — the `devman.link` option and the reconciler (2 days)

1. `devman.link`, typed as `attrsOf (submodule { canonical; path; template; })`.
2. `devman link reconcile` in Python — the five states of §5.1, per property 7
   (`devman/AGENTS.md:74-75`). Project name is an argument outside the plane and
   defaults from `devman.project` inside it.
3. The hook calls it, guarded by `[ -d ]` so it forks nothing when absent — the
   shape at `devman/modules/devenv.nix:832-838`.
4. The exclude writer gains the derived lines (§5.2).
5. `devman doctor` gains `link drift`, reporting the state name per link.

**Stop here and use it for a week.** Stages 0–2 give the whole model with the
registry in its old place and workflows still rendered.

### Stage 3 — move the registry, split config from state (1 day)

1. `devman/nix/nixos-module.nix:334` and `devman/modules/devenv.nix:485`: default
   `registryDir` → `$HOME/.config/devman`; add `stateDir` →
   `$HOME/.local/state/devman`.
2. `devman/nix/nixos-module.nix:88`: `paths.dags_dir` follows the new root.
3. `metadata.json`, `plan.json`, `triggers.toml` move to `stateDir`.
4. Rebuild. Every repository re-registers on its next shell entry. Delete
   `~/.local/share/devman/` when `devman doctor` is clean.

**Zero repository edits.** `grep -rn registryDir */devenv.nix` returns **0 hits**.

### Stage 4 — stop rendering workflows; link them (2 days)

§6.2. Editing the repository's file then takes effect on the next run and on the
next *scheduled* run, with no re-projection — both verified.

### Stage 5 — one toolchain (several weeks, and separable)

Flip `cliProvider` to `store` by default with repoman importing vendomat's
toolchain module, so consumers change only their input list. Keep `venv` working
for one release. Then merge vendomat's `lib/` into repoman, keeping the
consumer-facing name `repoman.enable`. **Do not start before Stage 4 is stable**,
and verify first with `nix build .#repoman-toolchain-core` plus one repository
running `repoman doctor` under `store`.

### 11.1 A new repository

```bash
copyroom new …
$EDITOR devenv.nix          # devman.project = "<name>"; devman.link = { … };
devenv shell                # registers, reconciles, links, writes excludes
```

The reconciler creates `~/.config/devman/projects/<name>/`, renders any declared
`template` with copyroom, `mkdir -p`s the `canonical = "repo"` targets, links both
directions and writes the exclude lines. **One shell entry, nothing else.**

**Auto-template is legitimate here and only here.** copyroom's invariant is
managed ⇒ tracked ⇒ committed, and `update` needs a clean worktree
(`copyroom/src/copyroom/project/config.py:53`). Inside the config repository that
invariant **holds** — those files are tracked by design, which is what
`024-personal-overlay/CONCEPT.md` §3.4 concluded before deferring it for want of a
need. **Never render a template into a project repository**; there,
`canonical = "repo"` targets get `mkdir -p` and nothing more.

### 11.2 An existing repository

1. **Nothing, at first.** A repository with no `devman.link` reconciles an empty
   set. Stage 2 is a no-op for 52 of 52 until you opt one in.
2. **Opt in** by adding `devman.link` to `devenv.nix` (shared) or to the central
   `devenv.local.nix` (machine-only).
3. **First shell entry after opting in** hits state three of §5.1 for anything that
   already exists. The four repositories carrying a real `devenv.local.nix` today —
   `foreman`, `forgelab`, `image-gen-pipeline`, `lodestar` — are **promoted, not
   clobbered**, and land in a lane for review.
4. **The 31 repositories that gitignore `.envrc` but have none** get `common/envrc`
   linked in. The five that have one are promoted first, so the divergent pins
   surface as a reviewable diff.
5. **Workflows last.** Only devman's own repository has `.devman/workflows/`
   (`ls -d */.devman/workflows` → one hit), so Stage 4 moves one repository's ten
   files. Everything else keeps taking group workflows unchanged.

### 11.3 The four backburnered repositories

`foreman`, `forgelab`, `image-gen-pipeline` and `lodestar` carry
`devman.enable = lib.mkForce false` (`foreman/devenv.local.nix:5`, 2026-09-08,
*"Backburner: keep this checkout out of the machine's devman plane"*).

**That file is itself the first promotion.** Its content moves to
`~/.config/devman/projects/foreman/devenv.local.nix`, the repository gets a link,
and the opt-out keeps working — now version-controlled and visible beside the other
51.

---

## 12. The stated limits

1. **A committed absolute symlink is a silent portability bug.** The `.gitignore`
   rule prevents it; a doctor check must confirm it, because `git add -f` defeats
   the rule.
2. **A moved or absent config repository breaks every linked repository at once**,
   with a Nix trace and no interception possible — measured:
   `error: path '…/local.nix' does not exist`. Same exposure
   `024-personal-overlay/CONCEPT.md` §3.7 accepted; `doctor` catches it fleet-wide
   first.
3. **Rename-based writers break file links** (§5.5). The reconciler promotes rather
   than losing the edit, but between the break and the next reconcile the central
   copy is stale. The watcher shortens that window; it does not close it.
4. **`dag_discovery.symlinks` is young.** Dagu v2.15.0 (2026-08-21) shipped
   *"fix: preserve DAG names for external symlink entries"* — released broken, then
   fixed. The plane already depends on it, so this is pin discipline, not a new
   risk. Do not upgrade Dagu without re-running §6.3.
5. **A duplicate DAG name is silent and the two run paths disagree** (§6.4). The
   pre-link refusal is the only defence.
6. **`devenv.local.yaml` silently ignores unknown keys.** A `devman:` block in it
   exited 0 and did nothing. Declarations belong in `devenv.local.nix`, where they
   are typed and fail at eval.
7. **Warm shell entry is not the cost.** Bare devenv 0.21–0.23 s; the full family
   stack 0.26–0.29 s. Any argument that leads with speed is aesthetic.
8. **Stage 5 is a separate decision.** Its case is correctness — silent PATH
   shadowing — not tidiness, and it must be made that way.

---

## 13. What I could not determine

1. **How Claude Code writes `.claude/settings.local.json`.** If it renames on save,
   the link breaks on every permission approval and promote becomes hot rather than
   occasional. *Settled by:* linking one repository's file, approving one
   permission, running `test -L`. **Do this before Stage 2** — if it fails, hoist
   the shared allowlists to `~/.claude/settings.json` and leave the per-repo files
   alone.
2. **Whether `cliProvider = "store"` works today.** The path exists and no
   repository uses it. *Settled by:* `nix build .#repoman-toolchain-core` in
   vendomat, then one repository entering a shell under `store` and running
   `repoman doctor`. **The whole Stage 5 argument rests on it.**
3. **Whether agentman's zero consumers means "new" or "wrong".** First commit
   2026-09-08. The `devman-agentman/v1` contract is shipped on agentman's side and
   unadopted on devman's (`agentman/AGENTS.md:87-93`). *Settled by:* devman
   adopting `groups/agent/` and one repository running a real capsule.
4. **Whether `copyroom/_compat/gitutil.py` can shrink.** 348 lines of subprocess
   git in a family whose VCS tool reduced its raw-git surface to zero. *Settled by:*
   a call-graph over `workshop/` versus `project/`. If the workshop is the only
   caller, the duplicate is smaller than it looks.
5. **Whether devman's lock readers produce noise** against the new tree.
   `check_local_sources` (`devman/src/devman/doctor.py:1061`) and `check_path_inputs`
   (`:1138`) both read `devenv.lock` across the registry. Flagged in
   `024-personal-overlay/CONCEPT.md` §5.5 and still unverified.
6. **How often a promote conflict happens.** §5.4 refuses when both sides moved.
   Whether that is rare or constant depends on how often the central copy is edited
   directly, and there is no data yet.

---

## Appendix — resolved during this project

| Question | Answer |
|---|---|
| Does the Dagu **scheduler** fire a symlinked external DAG? | **Yes** — fired 19:43:00, ran in the repository directory |
| Does the scheduler re-read a target **edited in place**? | **Yes** — fired `VERSION_TWO_EDITED` at 22:02:00, no re-link, no restart |
| Do **multi-hop** symlink chains work? | **Yes** — discovered *and* executed, correct cwd |
| Does **loci** tolerate a symlinked vault root? | **Yes** — `Path(root).resolve()`; identical revision `e061916e…` from both paths, one cache |
| Can **git** version-control content behind a symlink? | **No** — mode `120000`, blob is an absolute path string |
| Can **entry points** enumerate the family? | **No** — toolchain venv `python3-3.13.15`, consumer venv `python3-3.14.6`, disjoint |
| Do **devenv modules** merge a typed registry across imports? | **Yes** — this replaces entry points |
| Does **dotbot** converge? | **No** — orphans survive; `clean` needs the same `force` that destroys data |
| Which writes break a **file** symlink? | Only rename-based ones (`sed -i`, `os.replace`, `jq + mv`) |
| Are `.agents/skills` tracked? | **Yes**, everywhere sampled — so they belong to copyroom, not the link plane |
