# devman — Concept (re-charter)

> **STATUS: PROPOSED (2026-08-13).** This document re-charters the `devman` repo
> from a tmuxp/Neovim workspace orchestrator into the **developer-asset manager**
> of the `*man` family. It supersedes repoman's project-02
> (`repoman/.scratch/projects/02-devman-module/`) and absorbs its remaining
> functionality. See §4.

---

## 1. One line

> **devman is the developer-asset manager: one authored catalog of helper
> scripts, agent skills, prompts, and aliases — compiled into every consumer
> surface, and activated per repo.**

devman holds the assets. The other managers do the work.

---

## 2. Why re-charter

### 2.1 The current repo is superseded

`devman` today is a workspace orchestrator: it discovers `.devman/` directories,
caches an index, and launches tmuxp sessions with Claude Code and Neovim windows.
Every one of those jobs now has a better owner:

| Old devman job | Current owner |
|---|---|
| launch a durable per-project workbench | **shellij** (Zellij, server-side, devenv-triggered) |
| index sibling repos, report what exists | **fleetman** (`registry.json`, `PROJECTS.md`) |
| generate project scaffolds from templates | **copyroom** (Copier, three-way merge) |
| write `.claude/` project config | the agent-files convention (`AGENTS.md` + `.agents/skills/`) |

Little of `src/devman/` survives the re-charter. Treat this as a rewrite that
keeps the repo name, not a refactor.

### 2.2 The vacancy

The family splits into four roles, and one is empty:

| Role | Members |
|---|---|
| **doers** — perform a domain action | gitman, testee, docman |
| **conductor** — orders the doers | repoman |
| **transport** — moves files between repos | copyroom (+ my-ai as a layer) |
| **host** — where the shell lives | shellij |
| **assets** — the scripts, skills, and prompts the work is made of | *(empty)* |

No member owns the assets themselves. Helper scripts accumulate in `scripts/`,
skills in `.agents/skills/`, aliases in a `.zshrc`, prompts nowhere. Nothing
validates them, nothing finds them, nothing keeps the copies in agreement.

### 2.3 The one-source-many-targets problem

One helper — "reset the dev database" — exists today as up to five hand-written
copies: a shell script, a devenv script, an atuin alias, an atuin script, and a
paragraph in a skill telling the agent it exists. Each copy drifts on its own
schedule. Nobody notices until an agent runs the stale one.

devman holds **one definition** and emits all five. That is the core mechanic;
everything else in this document supports it.

---

## 3. What devman is, and is not

| devman is | devman is not |
|---|---|
| the **catalog** — authoring, validation, search | a **transport** between repos → copyroom |
| the **compiler** — one asset, N surfaces | a **router** of lifecycle order → repoman |
| the **activator** — reconciles a repo's assets into the live shell | a **doer** (test / VCS / docs) → testee, gitman, docman |
| the **harvester** — proposes assets from real shell history | a **session manager** → shellij |
| the owner of the **devenv-literacy layer** (§4) | a **fleet indexer** → fleetman |
| the **author** of every agent skill in the family (§12.1) | the owner of any tool's **facts** — those stay in the tool |

devman never re-implements a doer. A devman script that runs tests calls
`testee verify`.

---

## 4. Supersession — absorbing repoman's project-02

### 4.1 What project-02 became

repoman's project-02 proposed `devman` as a devenv-literacy knowledge layer
**inside the repoman repo**: skills, a distilled docs export, and articles,
explicitly "not a separate repo" and "no `devman` command". It shipped
(2026-06-20), then hollowed out. Current state, verified:

- `repoman/src/repoman/devman/` holds `__init__.py` and `check.py` only — 117
  lines, **no assets**. Its docstring records the move.
- The assets live in the **genome**: `template-py/template/.agents/devenv/`
  (7 docs + 6 articles) and `template-py/template/.agents/skills/devenv-*`
  (11 skills). `copyroom update` converges them.
- The `.devman-source` manifest is retired
  (`repoman/docs/AGENT-FILES.md`).

So the name is held by a stub, and the assets sit in a template that only
reaches repos generated from it.

### 4.2 What this re-charter does

devman takes both.

| Item | From | To | Mechanism |
|---|---|---|---|
| the name `devman` | `repoman/src/repoman/devman/` | this repo | the module retires; `skill_ownership_checks` retires with it (§12.1 removes the ownership classes it lints) |
| the `devenv-*` skills (11) | `template-py/template/.agents/skills/` | devman pack `devenv-literacy` | `devman build` emits them |
| the `.agents/devenv/` docs export (7) | `template-py/template/.agents/devenv/` | same pack | `devman build` emits them |
| the articles (6) | `template-py/template/.agents/devenv/articles/` | same pack | `devman build` emits them |
| "are the literacy assets current?" | `repoman doctor` (warn) | `devman doctor` | devman knows the pack version; repoman only sees files |

The takeover does not stop at the literacy layer. §12.1 extends it to **every
agent skill in the family** — copyroom's canonical set, repoman's router, and
each manager's own skill. Read §12.1 before planning any of the migration below.

### 4.3 Why the assets move out of the genome

The genome reaches only repos generated from it. The literacy layer is needed in
**every** repo, including adopted ones and repos on a different genome. A pack
resolved per machine reaches all of them, updates on its own schedule, and does
not force a `copyroom update` to fix a typo in a skill.

This also settles project-02's open question "should missing devman skills be
warn or fail?" — devman owns them, so `devman doctor` can fail (`2`) when the
pack is pinned but absent, and warn when it is merely behind.

### 4.4 Migration, in order

1. devman ships the `devenv-literacy` pack with the assets copied verbatim from
   the genome. No content change — a pure move.
2. `template-py` drops `template/.agents/devenv/` and `template/.agents/skills/devenv-*`,
   and seeds `.devman/devman.toml` instead.
3. `repoman` retires `src/repoman/devman/` — both the module and
   `skill_ownership_checks`, whose ownership classes no longer exist (§12.1).
4. `repoman/docs/AGENT-FILES.md` loses its ownership split and two-writer rule,
   and gains the two-row table from §12.1.
5. `repoman/.scratch/projects/02-devman-module/README.md` gets a
   **SUPERSEDED BY devman/001-recharter** header.
6. Each manager's skill is re-authored here, and its copy deleted in its own repo
   (§12.1). Do one manager end-to-end before the rest.

Steps 2–6 are cross-repo. Do them only after step 1 is real and tested.

---

## 5. The asset model

Every asset is **one file with typed frontmatter**. This is the whole design.

```yaml
---
id: db-reset
kind: script            # script | skill | prompt | alias | recipe
scope: repo             # repo | user | machine
summary: Drop and re-seed the dev database.
targets: [devenv-script, atuin-script, skill, agent-command]
requires: [postgres]
exit:
  1: "migration conflict"
  2: "no database reachable"
---
#!/usr/bin/env bash
set -euo pipefail
...
```

A pydantic model validates each asset. One **emitter** per entry in `targets`
renders it (§8).

`targets` is the leverage. Adding a sixth surface later — an MCP tool, a Codex
prompt, a `justfile` recipe — is one emitter, not a migration of the catalog.

`scope` decides where the asset may be activated: `repo` assets never reach
another repo; `user` assets follow you everywhere; `machine` assets never sync.

`exit` documents the asset's own exit contract, so a generated skill can tell an
agent what a non-zero code means. This keeps the family `0/1/2/3` discipline
inside generated assets, not only inside the CLIs.

### 5.1 Facts and prose

A skill asset is a **template with holes**. devman authors the prose; `build`
fills the holes by introspecting the installed tool. devman never transcribes a
fact.

| Material | Changes with | Authored by | Examples |
|---|---|---|---|
| **facts** | the binary | the tool, read at build time | command names, flags, exit codes, sub-command lists |
| **prose** | how the user wants to work | **devman** | domain boundary, the law, routing tables, deferral footers, warnings |

The prose is the bulk of every family skill, and it was never the tool's to own.
The facts are a small, mechanically extractable minority.

This makes version drift a **check instead of a risk**. `devman doctor` compares
every command name referenced in every authored skill against the installed
CLI's real command list, and exits `1` naming the stale reference. Nothing
verifies that today — a tool-shipped skill is *assumed* to match its CLI because
they share a package. devman turns the assumption into an assertion.

---

## 6. The hidden directory

```
.devman/
  devman.toml        # tracked  — policy: packs, scopes, activation, namespace
  lock.toml          # tracked  — pinned pack versions + content digests
  assets/            # tracked  — this repo's own assets (source of truth)
    scripts/
    skills/
    prompts/
    aliases.toml
  build/             # ignored  — compiled output + manifest.json
  state/             # ignored  — activation record, locks
```

Two rules keep it safe:

1. **Tracked source, ignored output.** `build/` is always reproducible from
   `assets/` plus `lock.toml`. A stale `build/` is never a merge conflict.
2. **Provenance on everything.** Every emitted file carries a header naming
   devman, the source asset id, and the pack version. Every emitted artifact —
   including the ones outside `.devman/` — has a `manifest.json` entry. devman
   removes only what its own manifest records.

Note that `.devman/packs/` does **not** exist. Packs resolve to a machine-wide
cache, never into the repo (§7).

---

## 7. Packs, resolved per machine

### 7.1 The model

A **pack** is a versioned, distributable set of assets. Packs resolve once per
machine, into a shared cache:

```
~/.local/share/devman/packs/<name>/<version>/
```

This mirrors repoman's toolchain venv (`$REPOMAN_TOOLCHAIN_VENV`, default
`~/.local/share/repoman/venv`) — the same shape, for the same reason: assets used
by every repo should exist once per machine, not once per repo.

```bash
devman sync --machine     # resolve every declared pack into the cache
devman build              # compile: repo assets + cached packs → .devman/build/
```

`.devman/lock.toml` pins which pack versions this repo uses. `devman build`
reads the cache. If a pinned version is absent, devman exits `2` and names the
fix: `devman sync --machine`. A repo never carries pack bytes.

### 7.2 The layered catalog

devman compiles a **stack**, nearest wins:

```
machine  →  user (my-ai)  →  packs  →  repo (.devman/assets/)
```

A repo can shadow a pack asset by declaring the same `id`. `devman build`
reports every shadow, so an override is visible rather than silent. This is the
same precedence idea as copyroom's layers, applied to assets instead of files.

### 7.3 The personal layer as a pack — decided

The `my-ai` repo gains a `pack/` directory. It becomes the **personal pack**,
resolved per machine like any other.

| Asset | Owner | Delivery |
|---|---|---|
| `AGENTS.md` seed, `CLAUDE.md` symlink, `my-ai/SKILL.md` (the law) | my-ai | copyroom, per repo — unchanged |
| the user's executable assets: scripts, aliases, prompts, personal skills | my-ai's devman pack | devman, once per machine |

Why not ship them through copyroom per repo: a personal alias set copied into 60
repos means 60 merge lineages for one file, and a fix requires 60
`copyroom update --layer my-ai` runs. One machine cache means one copy and one
update. copyroom keeps the small, genuinely per-repo law file, where three-way
merge earns its cost.

The bootstrap stays tiny. copyroom (via the genome or the my-ai layer) seeds two
things and nothing more: `.devman/devman.toml` and the `devman` devenv import
line. Everything else resolves at build time. This is what keeps devman clear of
the two-writer rule (§12.1).

---

## 8. The emitters

| Target | Output | Runtime |
|---|---|---|
| `devenv-script` | `.devman/build/devman.nix`, imported by `devenv.nix` | the pinned shell — **the primary path** |
| `skill` | `.agents/skills/<name>/SKILL.md` — **every** skill in the repo (§12.1) | Claude Code, any agent |
| `agent-command` | `.claude/commands/<id>.md` | slash commands |
| `atuin-script` | `atuin scripts new`, named `dm.<ns>.<id>` | your shell — searchable, sync'd |
| `atuin-alias` | `atuin dotfiles alias set dm-<id>` | your shell, everywhere |
| `prompt` | prompt file, plus registration | agents, `atuin ai` |
| `docs` | `.agents/devenv/**` | the literacy export (§4) |

`devenv-script` is the primary target. It puts the helper on `PATH` **inside the
pinned shell**, so an asset inherits the same determinism as every other family
tool. No `PATH` manipulation, no wrapper scripts, no "works on my machine".

### 8.1 The atuin boundary

Reach atuin through **pytuin**, never by direct subprocess. pytuin already owns
the hardened runner, the KV store, and status probing. devman gains atuin
integration without owning an atuin boundary.

Verified on this machine (atuin 18.18.1): `scripts`, `dotfiles alias|var`, `kv`,
`hook`, `mcp`, and `ai init|inline` exist. There is **no documented prompt-template
store**. Therefore:

- Treat prompt templates as **files devman owns**, plus a thin registration step.
- Confirm the atuin surface before building the `prompt` emitter's atuin half.
- The `skill` and `agent-command` targets deliver prompts to agents today, with
  no atuin dependency.

Do not design the catalog around an atuin feature that may not exist.

---

## 9. The lifecycle

```
author    devman add script db-reset --last 3    # from your actual history
build     devman build                           # catalog → build/ + manifest
activate  devman activate                        # reconcile the live surfaces
verify    devman doctor                          # assets valid, surfaces in sync
harvest   devman propose                         # mine history → suggest assets
```

**`build` is pure.** It writes only inside `.devman/build/`, plus the tracked
agent-file targets it owns by name. It never touches state outside the repo. It
is safe in CI, safe in a sandbox, and safe to run on every save.

**`activate` is the only impure step.** It reconciles user-global surfaces
(atuin scripts, atuin aliases) to this repo's catalog. It is idempotent and
manifest-guarded. shellij's `enterShell` hook already fires once per project —
that is the natural trigger, and it needs no new mechanism.

**`deactivate`** reverses activation from the manifest. It is opt-in, because
leaving a namespaced asset installed is harmless and removing one you did not
record is not (§12.2).

---

## 10. Harvest — the assistant half

atuin holds your command history. atuout holds the **captured output** of each
command, keyed by `ATUIN_HISTORY_ID`. Together they are a record of what you
actually do, not what you documented.

`devman propose` mines both:

| Signal | Proposal |
|---|---|
| a command run N times across M repos | a missing `script` asset, scoped `user` |
| a command that failed, then succeeded after an edit | a missing `recipe` — the failure and the fix |
| a long argument string retyped often | a missing `alias` |
| a command an agent ran bare that a doer owns | a missing skill line, or a routing bug |

`propose` writes nothing. It prints candidates; `devman add --from-proposal <n>`
accepts one. Keep the human in the loop — a catalog that grows on its own stops
being trustworthy.

This is the one capability no other family member can offer, and it is the
reason the atuin integration justifies its complexity. Build it last (§14).

---

## 11. Integrations and boundaries

| Repo | devman consumes | devman provides | The hard boundary |
|---|---|---|---|
| **copyroom** | its CLI facts, introspected at build time; the bootstrap seed `.devman/devman.toml` + the devenv import line | every copyroom skill (§12.1) | copyroom transports *files between repos*; devman resolves *packs at build time*. copyroom no longer ships skill assets. |
| **my-ai** | the personal pack, resolved per machine (§7.3) | the pack format; the law rendered as a skill | my-ai keeps `AGENTS.md` and the `CLAUDE.md` symlink. devman owns the personal executable assets and the law's rendered form. |
| **repoman** | `registry.py` — the roster, `SPINE`, `route_when`; the `devenv shell` and `0/1/2/3` contracts | roster key `dev`; the rendered router skill | repoman owns the **facts of ordering**; devman owns the **prose**. devman never decides what comes before what. |
| **shellij** | the `enterShell` activation trigger | the assets its panes run | shellij owns sessions and panes. devman owns what is on `PATH` inside them. |
| **fleetman** | `registry.json` — which repos exist | fleet-wide asset queries: "which repos carry `db-reset`?" | fleetman indexes *repos*; devman indexes *assets*. Cross-repo execution stays `fleetman run`. |
| **testee** | its CLI facts | the testee skill; assets may call `testee verify` | devman never runs a test. |
| **gitman** | its CLI facts | the gitman skill; assets may call `gitman save` | devman never touches VCS. |
| **docman** | its CLI facts | the docman skill; assets may call `docs-build` | devman's `docs` target ships the *literacy export*, not a site. |
| **pytuin** | the typed atuin client (KV, status, recordings) | nothing | pytuin owns the atuin subprocess boundary. |
| **atuout** | captured command output, for `propose` | nothing | atuout owns capture and storage. devman only reads. |

### 11.1 The rule that generates this table

> devman owns the **words**: every developer asset's definition, and every agent
> skill's prose. Every other manager owns the **facts** — its own commands, exit
> codes, and domain semantics — plus the actions an asset calls.

When a boundary question comes up, apply that sentence twice:

- "Would devman **run** it?" If yes, the answer is wrong — that is a doer's job.
- "Would devman **decide** it?" If the decision is a domain fact (what `land`
  does, what comes before what), the answer is wrong — read it from the tool.

---

## 12. The sharp edges

### 12.1 One author for the family's agent surface

**Decided:** devman authors **every** agent skill in the family, and is the only
writer under `.agents/skills/`.

This is larger than adding devman as one more owner. It replaces the ownership
protocol outright.

#### What it replaces

`repoman/docs/AGENT-FILES.md` fixes one owner per file and names five classes:
tool-shipped (copyroom's canonical set), genome, personal (my-ai), repoman's
generated router, and repo overlay. It needs a "two-writer rule" to keep those
classes from fighting, and `repoman doctor` needs an ownership lint to police
them.

All of it collapses to two rows:

| Owner | What |
|---|---|
| **devman** | every skill — authored here, built from packs, facts introspected |
| **the repo** | declared overlays (`.devman/devman.toml`), for permanent divergence |

The two-writer rule, the ownership classes, and `skill_ownership_checks` all
retire. A design that deletes a coordination protocol is usually the right one.

#### What each tool keeps

| Tool | Keeps | Loses |
|---|---|---|
| **copyroom** | its CLI facts (introspected at build time); seeding `.devman/devman.toml`; `AGENTS.md` + the `CLAUDE.md` symlink | `src/copyroom/agent/assets/skills/` (deleted); `agent-files export` shrinks to the two convention files, or retires |
| **repoman** | `registry.py` — the roster, `SPINE`, `route_when`. **repoman still decides lifecycle order.** | the Jinja template and `install_entrypoint`; `install-skills` becomes `skills render` or retires |
| **my-ai** | the standing law as prose, now authored as a devman skill asset in its pack | nothing structural — it was already a layer |
| **testee, gitman, docman** | their CLI facts | their hand-written skills |

The boundary that must hold: repoman owns the **facts of ordering** (`SPINE`,
`route_when`). devman owns the **prose that renders them**. devman never decides
what comes before what — it reads that from the registry. Two conductors would
be worse than none.

#### Why centralized authorship beats per-tool authorship

1. **The law is written once.** `repoman/docs/SKILLS.md` names boilerplate drift
   as a known failure: "run inside `devenv shell`", the `0/1/2/3` contract, "read
   the structured report" — repeated in every skill, "they eventually disagree."
   One author injects it once.
2. **Uniform shape becomes generation, not a lint.** The same document asks every
   manager skill to carry three disciplines (domain boundary, deferral footer,
   trigger discipline) and hopes `repoman doctor` can enforce them. A generator
   emits them by construction. This is the difference between a style guide and a
   formatter.
3. **Convention changes cost one edit.** Change the deferral-footer format today
   and it is six repos and six releases. Under one author it is one edit and a
   rebuild.
4. **Trigger-collision linting becomes possible.** `repoman/docs/SKILLS.md` lists
   it as an open question, and must, because no component sees every skill at
   once. devman compiles the whole set, so it can detect two skills
   auto-triggering on one keyword and fail with `1`.
5. **Skills generate from the assets they document.** A script asset already
   carries `summary`, `requires`, and `exit` (§5). The skill section that
   documents it writes itself. The catalog and its documentation stop being two
   things that drift.

#### The cost, stated plainly

**Release-order coupling.** copyroom ships a renamed command; until the devman
pack is rebuilt, every repo carries a skill naming the old one. That window does
not exist today, because the skill and the binary ship together.

This is a real regression, and it is acceptable for one reason: the window is
**detected**. §5.1's reference check fails loudly with exit `1` and names the
stale command; the fix is one `devman sync --machine && devman build`. Today the
window is impossible, but only as a side effect of tight packaging — and nothing
checks the coupling actually held.

Do not paper over this. Build the reference check in step 2, not later.

#### Bootstrap

A repo with no devman must still get skills. Each tool keeps a minimal export
path, and `copyroom new` still seeds a starting set. devman is the steady state,
not the only path.

### 12.2 atuin state is user-global and sync'd

An alias scoped to one repo, installed into a global replicated store, leaks to
every machine you own. Three mitigations, all mandatory:

1. **Namespace everything.** `dm.<ns>.<id>` for scripts, `dm-<id>` for aliases.
   The namespace comes from `.devman/devman.toml`, defaulting to the repo name.
2. **Manifest every install.** `.devman/state/` records exactly what activation
   wrote.
3. **Never delete an unrecorded entry.** Default policy is *reconcile on entry*.
   Aggressive cleanup is opt-in.

If any of the three is hard to implement, ship the `atuin-*` emitters later. The
`devenv-script` and `skill` targets deliver most of the value with none of this
risk.

### 12.3 The name

Resolved: devman takes the name (§4). repoman's module renames, and project-02
is marked superseded. The literacy assets keep their `devenv-*` skill names —
those are user-facing trigger keywords, and renaming them would break every
agent that has learned them.

---

## 13. Family contract compliance

devman is a normal family member. No exceptions requested:

- **Typer CLI**, single interface, no ad-hoc tool invocation.
- **Pydantic-normalized report**, rendered compact and actionable.
- **`init` + `doctor`**, like every manager.
- **Distributed as a devenv module**, imported via `devenv.yaml`.
- **Runs inside `devenv shell`** as its execution boundary.
- **Exit codes:** `0` ok · `1` finding (asset invalid, surface drifted) ·
  `2` infra/config (pack missing, atuin unreachable) · `3` usage.
- **One skill** with a domain boundary and the deferral footer to the `repoman`
  router.
- **Install model:** toolchain manager. devman is a pure CLI, so it lives in the
  shared machine venv, alongside copyroom, gitman, and docman — not as a per-repo
  uv dependency.

### 13.1 The CLI surface

```
devman init                     # scaffold .devman/, add the nix import, install the skill
devman add <kind> <id>          # author an asset; --last N reads your history
devman build                    # compile the catalog; pure
devman activate | deactivate    # reconcile the live surfaces; manifest-guarded
devman sync [--machine]         # resolve packs into the machine cache
devman list | show | search     # query the catalog
devman propose                  # mine history for missing assets
devman status | doctor          # the family pair
```

---

## 14. Build order

| # | Step | Unblocks |
|---|---|---|
| 1 | **Settle the single-author decision** (§12.1). Cross-repo; no code. Replaces the ownership split, not amends it. | every emitter that writes `.agents/` |
| 2 | **Asset model + `build`.** Pydantic models, the catalog loader, the layered stack, fact introspection + the stale-reference check (§5.1), and two emitters: `devenv-script` and `skill`. | the whole value, none of the risk |
| 3 | **`init` + `doctor` + the devenv module.** Family contract compliance; register roster key `dev` with repoman. | adoption by any repo |
| 4 | **Packs + `lock.toml` + `sync --machine`.** First pack: `devenv-literacy`, moved from the genome (§4.4). Second: the my-ai personal pack. | distribution |
| 5 | **Re-author the family skills.** One manager end-to-end first — testee is the smallest. Then copyroom, then the router. | §12.1's takeover |
| 6 | **`activate` + the atuin emitters.** The first step that touches state outside the repo. Behind the manifest. | shell-surface assets |
| 7 | **`propose`.** The harvester. | the assistant half |

Steps 1–3 give a working tool. Everything after compounds on it.

Step 2 must include the stale-reference check. It is what makes §12.1's release
coupling survivable, and it is far harder to retrofit than to build in.

Delete the old `src/devman/` at step 2. Do not port it.

---

## 15. Open questions

- **Pack format.** A git ref (like copyroom templates), a Python package (like
  copyroom's agent assets), or a plain tarball? Lean: git ref, because it needs
  no publish step and `devman sync --machine` can pin a rev.
- **Does `build` write outside `.devman/`?** It must, to emit skills. Decide
  whether that makes `build` impure, or whether a separate `devman materialize`
  step owns every write outside `.devman/`. Lean: keep it in `build`, and let the
  manifest carry the purity guarantee.
- **Repo-scoped atuin scripts.** Should a `scope: repo` asset reach atuin at
  all, given the store is global? Lean: yes, but namespaced and reconciled on
  entry — searchable history is the point.
- **Shadowing policy.** Should a repo shadowing a `machine`-scoped asset be a
  warning or an error? Lean: warning, reported by `doctor`.
- **`.devman/build/devman.nix` and the eval cache.** A generated nix file that
  changes on every `build` will fight devenv's eval cache. Measure this early —
  it may force a different `devenv-script` mechanism (a `scripts` directory on
  `PATH` rather than generated nix).
- **Codex and other agents.** The `skill` emitter is Claude-first. Which other
  agent formats earn an emitter, and when?
- **How are facts introspected?** Options: import the tool's Typer app and walk
  it, parse `--help`, or ask each manager for a `--schema` JSON export. Lean:
  walk the Typer app, because every family member is a Typer CLI in the same
  machine venv — no new surface to negotiate. Fall back to `--schema` for tools
  that are not importable.
- **How deep does the reference check go?** Command names are easy. Flags,
  sub-commands, and exit codes are progressively harder. Lean: names and
  sub-commands in step 2; flags later, behind a `--strict` mode.
- **Where does a manager's domain prose live?** In devman's pack, or in the
  manager's repo as prose devman pulls? Lean: devman's pack — otherwise the
  single-author rule leaks straight back out.
- **Does the my-ai law stay a hand-written file?** It is prose, so devman
  authors it. But it is also the one skill a user edits directly. Decide whether
  it is an asset like any other, or a permanent overlay.
