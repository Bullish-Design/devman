# devman — Concept (re-charter)

> **STATUS: REVISED (2026-08-19).** Supersedes the PROPOSED draft of 2026-08-13.
> This document re-charters the `devman` repo from a tmuxp/Neovim workspace
> orchestrator into the **developer-asset manager** of the `*man` family. It
> supersedes repoman's project-02 (`repoman/.scratch/projects/02-devman-module/`)
> and absorbs its functionality. See §4.
>
> **What changed in this revision.** The first draft bundled two projects: a
> catalog-and-compiler tool, and a family-wide takeover of every agent skill. The
> takeover moved to `002-agent-surface`, because it needed agreement from six
> repos before one line of devman existed. Four spikes then answered four open
> questions and corrected three claims. See `.scratch/spikes/SPIKES.md`; results
> are folded in below and marked **[spike]**.

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

Little of `src/devman/` survives — 1958 lines, none of it load-bearing for the
new charter. Treat this as a rewrite that keeps the repo name, not a refactor.

### 2.2 The vacancy

The family splits into five roles, and one is empty:

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
| the **auditor** — reads every skill in a repo and reports drift (§10) | a **session manager** → shellij |
| the **harvester** — proposes assets from real shell history | a **fleet indexer** → fleetman |
| the owner of the **devenv-literacy layer** (§4) | the owner of any tool's **facts** — those stay in the tool |

devman never re-implements a doer. A devman script that runs tests calls
`testee verify`.

**Scope boundary for v1.** devman authors its own skill and the `devenv-literacy`
skills it inherits from project-02. It **reads** every other skill and reports on
it. It does not write skills it does not own. Whether devman should become the
family's single skill author is `002-agent-surface`, and it is deliberately not
decided here.

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
  (**8** skills). `copyroom update` converges them.
- The `.devman-source` manifest is retired (`repoman/docs/AGENT-FILES.md`).

> **[spike] Count corrected.** The first draft said 11 `devenv-*` skills. There
> are 8: `devenv-authoring`, `-inputs`, `-lock`, `-module-edits`, `-processes`,
> `-python-venv`, `-run-commands`, `-troubleshoot`. Eleven is the whole skill
> directory, which also holds copyroom's 3. The two sets have different owners
> and must not move together.

So the name is held by a stub, and the assets sit in a template that only reaches
repos generated from it.

### 4.2 What this re-charter does

devman takes both.

| Item | From | To | Mechanism |
|---|---|---|---|
| the name `devman` | `repoman/src/repoman/devman/` | this repo | the module retires |
| the `devenv-*` skills (**8**) | `template-py/template/.agents/skills/` | devman pack `devenv-literacy` | `devman build` emits them |
| the `.agents/devenv/` docs export (7) | `template-py/template/.agents/devenv/` | same pack | `devman build` emits them |
| the articles (6) | `template-py/template/.agents/devenv/articles/` | same pack | `devman build` emits them |
| "are the literacy assets current?" | `repoman doctor` (warn) | `devman doctor` | devman knows the pack version; repoman only sees files |

copyroom's 3 skills stay where they are. `skill_ownership_checks` stays wired at
`repoman/src/repoman/cli.py:219` — retiring it belongs to 002, not here.

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
2. `template-py` drops `template/.agents/devenv/` and the 8
   `template/.agents/skills/devenv-*`, and seeds `.devman/devman.toml` instead.
   It **keeps** `skills/copyroom*`.
3. `repoman` retires `src/repoman/devman/`. `skill_ownership_checks` moves to
   `repoman/checks/` unchanged — it still has classes to police until 002 lands.
4. `repoman/.scratch/projects/02-devman-module/README.md` gets a
   **SUPERSEDED BY devman/001-recharter** header.

Steps 2–4 are cross-repo. Do them only after step 1 is real and tested.

---

## 5. The asset model

Every asset is **one file with typed frontmatter**. This is the whole design.

```yaml
---
id: db-reset
kind: script            # script | skill | prompt | alias | recipe
reach: repo             # repo | user | machine — where it may be activated
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

`exit` documents the asset's own exit contract, so a generated skill can tell an
agent what a non-zero code means. This keeps the family `0/1/2/3` discipline
inside generated assets, not only inside the CLIs.

### 5.1 `reach` and `origin` are different axes

The first draft called both of these `scope`, using the same three words for
each. That made `scope: machine` on an asset defined in the repo layer both
expressible and meaningless. Two names now:

| Axis | Field | Values | Answers |
|---|---|---|---|
| **reach** | on the asset | `repo` · `user` · `machine` | where may this be activated? |
| **origin** | the layer it came from | `machine` → `user` → `pack` → `repo` | who defined it, and who wins? |

`reach: repo` assets never leak to another repo. `reach: user` assets follow you
everywhere. `reach: machine` assets never sync.

### 5.2 Three materials, not two

A skill asset is a **template with holes**. devman authors the shape; `build`
fills the holes. devman never transcribes a fact.

The first draft split this two ways — facts and prose — and assigned all prose to
devman. That over-claimed. A tool's maintainer knows *why* its boundary sits
where it does; devman does not, and that knowledge changes on the tool's
schedule, not the user's.

| Material | Changes with | Owner | Delivery | Examples |
|---|---|---|---|---|
| **facts** | the binary | the tool | introspected at build (§9) | command names, sub-commands, flags, exit codes |
| **domain prose** | the tool's design | **the tool** | a structured block devman pulls | why a boundary exists, what a failure mode means, when not to use it |
| **convention prose** | how the user wants to work | **devman** | authored here | the law, routing tables, deferral footers, "run inside `devenv shell`" |

This preserves single authorship of the **rendering** without claiming devman
knows every domain. It is also what makes 002 survivable: the takeover moves
convention prose, not domain knowledge.

---

## 6. The hidden directory

```
.devman/
  devman.toml        # tracked  — policy: packs, reach rules, activation, namespace
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
   devman, the source asset id, and the pack version. Every emitted artifact has
   a `manifest.json` entry. devman removes only what its own manifest records.

> **[spike] Provenance carries no timestamp.** Spike A measured that devenv
> hashes file *content*, not mtime: rewriting `devman.nix` with identical bytes
> costs nothing, while a content change costs ~1.3s of re-eval. A build
> timestamp in the header would make every build a content change and forfeit
> that. **All emitter output must be byte-deterministic**: sorted keys, no
> timestamps, no hostnames, no map iteration order.

`.devman/packs/` does **not** exist. Packs resolve to a machine-wide cache, never
into the repo (§7).

---

## 7. Packs, resolved per machine

### 7.1 The model

A **pack** is a versioned, distributable set of assets. Packs resolve once per
machine, into a shared cache:

```
~/.local/share/devman/packs/<name>/<version>/
```

This mirrors repoman's toolchain venv (`~/.local/share/repoman/venv`) — the same
shape, for the same reason: assets used by every repo should exist once per
machine, not once per repo.

```bash
devman sync --machine     # resolve every declared pack into the cache
devman build              # compile: repo assets + cached packs → .devman/build/
```

`.devman/lock.toml` pins which pack versions this repo uses. `devman build` reads
the cache. If a pinned version is absent, devman exits `2` and names the fix:
`devman sync --machine`. A repo never carries pack bytes.

### 7.2 The layered catalog

devman compiles a **stack**, nearest wins:

```
machine  →  user (my-ai)  →  pack  →  repo (.devman/assets/)
```

A repo can shadow a pack asset by declaring the same `id`. `devman build` reports
every shadow, so an override is visible rather than silent. Same precedence idea
as copyroom's layers, applied to assets instead of files.

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

The bootstrap stays tiny. copyroom seeds two things and nothing more:
`.devman/devman.toml` and the `devman` devenv import line. Everything else
resolves at build time.

---

## 8. The emitters

v1 ships the first two. The rest are named so `targets` is designed once.

| Target | Output | Runtime | v1? |
|---|---|---|---|
| `devenv-script` | `.devman/build/devman.nix`, imported by `devenv.nix` | the pinned shell — **the primary path** | **yes** |
| `skill` | `.agents/skills/<name>/SKILL.md` — devman's own + the 8 literacy skills | Claude Code, any agent | **yes** |
| `docs` | `.agents/devenv/**` | the literacy export (§4) | **yes** |
| `agent-command` | `.claude/commands/<id>.md` | slash commands | later |
| `atuin-script` | `atuin scripts new`, named `dm.<ns>.<id>` | your shell — searchable, sync'd | later (§12.2) |
| `atuin-alias` | `atuin dotfiles alias set dm-<id>` | your shell, everywhere | later (§12.2) |
| `prompt` | prompt file, plus registration | agents, `atuin ai` | later |

> **[spike] `devenv-script` confirmed as primary.** Spike A measured shell entry
> at 5.46s cold, 0.16–0.21s warm, and 1.44s on the build after a catalog change.
> The generated-nix approach is viable. The `scripts`-directory-on-`PATH`
> fallback is not needed.

`devenv-script` puts the helper on `PATH` **inside the pinned shell**, so an
asset inherits the same determinism as every other family tool. No `PATH`
manipulation, no wrapper scripts, no "works on my machine".

### 8.1 The atuin boundary

Reach atuin through **pytuin**, never by direct subprocess. pytuin already owns
the hardened runner, the KV store, and status probing.

Verified on this machine (atuin 18.18.1): `scripts` (`new`/`run`/`list`/`get`/
`edit`/`delete`), `dotfiles alias|var`, `kv`, `hook`, `mcp`, and `ai` all exist.
There is **no prompt-template store**. Therefore:

- Treat prompt templates as **files devman owns**, plus a thin registration step.
- The `skill` and `agent-command` targets deliver prompts to agents today, with
  no atuin dependency.

Do not design the catalog around an atuin feature that does not exist.

---

## 9. Fact introspection — decided

> **[spike] This was §15's largest open question. Spike B answers it.**

devman ships **one small walker script** and runs it under whichever interpreter
can import the target tool. It returns JSON: every command, its kind (group or
leaf), its positional arity, and its options.

```
~/.local/share/repoman/venv/bin/python  walker.py copyroom.cli app   → 19 nodes
<repo>/.devenv/state/venv/bin/python    walker.py testee.cli   app   →  8 nodes
```

**Why out-of-process, not an import.** The first draft assumed "every family
member is a Typer CLI in the same machine venv". testee is not:
`repoman/src/repoman/registry.py` sets `install="uv"` because testee's tools
import the consumer's code. It is a per-repo dependency, unreachable from the
shared venv. One out-of-process walker covers both install models and needs no
`--schema` export negotiated with any tool.

**Three rules the spike forced, all non-obvious:**

1. **Never `import click`.** typer 0.27.1 vendors it as the private
   `typer._click`, and no top-level `click` exists in the toolchain venv.
2. **Never use `isinstance` against click types.** In a venv where a real `click`
   *is* installed, `isinstance(get_command(app), click.Group)` returns **False**
   for a genuine `TyperGroup`, because typer built it from its own vendored copy.
   The check fails silently and every group reads as a leaf.
3. **Duck-type instead.** A node is a group when `.commands` is a dict. A
   parameter's kind is `.param_type_name` (`"argument"` / `"option"`). Verified
   across typer 0.26.8 and 0.27.1.

devman cannot pin the interpreter it borrows, so the walker must tolerate version
skew. It already exists in the family today: toolchain 0.27.1, testee's repo venv
0.26.8.

---

## 10. The two checks — services devman offers, not territory it claims

devman compiles the whole set of assets and reads every skill in a repo. Two
capabilities fall out that no other component can offer, and **neither requires
owning a single file**.

### 10.1 The stale-reference check

`devman doctor --refs` compares every CLI reference in every skill against the
installed CLI's real surface, and exits `1` naming the stale one.

> **[spike] Measured: 0 false positives on 79 real references across 9 skill
> files and 4 tools; all 3 injected defect classes caught.**

**Build it parameter-aware from day one.** Spike C's first version checked
command *names* only and scored **6 findings, all false**. Family CLIs use
positional pseudo-subcommands — `copyroom layer add` and `gitman version bump`
are leaf commands taking a value, not groups taking a subcommand. Without arity
and command kind from §9, the check reports every one of them and is unusable.
This corrects the first draft's lean of "names first, flags later": flags may
wait, arity may not.

The extractor must also handle prefixes. testee's skill writes every command as
`devenv shell testee verify`; a naive extractor anchored on the tool name finds
**zero** references in it.

### 10.2 The trigger-collision check

`devman doctor --triggers` reports two skills claiming one `auto_trigger`
keyword. `repoman/docs/SKILLS.md` lists this as an open question, and must — no
single component sees every skill at once. Anything that compiles the whole set
does.

> **[spike] 33 colliding keywords found across 8 repos, present today,
> undetected.** `copyroom` and `copyroom-adopt` collide on `adopt a repo`,
> `personal layer`, and `templatize` in every repo that carries the set.
> `copyroom` and `my-ai` collide on `my-ai`. In shellij, `devenv-run-commands`
> and `devenv-troubleshoot` collide on `command not found`.

### 10.3 Why this ordering matters

These checks are the evidence for `002-agent-surface`. The first draft argued
that only a single author could deliver them. That is false — a *reader* can.
devman v1 therefore earns the argument for the takeover instead of assuming it,
and delivers real value to skills it does not own in the meantime.

---

## 11. The lifecycle

```
author    devman add script db-reset --last 3    # from your actual history
build     devman build                           # catalog → build/ + manifest
activate  devman activate                        # reconcile the live surfaces
verify    devman doctor                          # assets valid, surfaces in sync
harvest   devman propose                         # mine history → suggest assets
```

**`build` is pure.** It writes only inside `.devman/build/`, plus the tracked
agent-file targets it owns by name. It never touches state outside the repo. It
is safe in CI, safe in a sandbox, and safe to run on every save — spike A
confirms an unchanged catalog costs nothing.

**`activate` is the only impure step.** It reconciles user-global surfaces (atuin
scripts, atuin aliases) to this repo's catalog. It is idempotent and
manifest-guarded. shellij's `enterShell` hook (`shellij/modules/devenv.nix:55`)
already fires once per project — that is the natural trigger, and it needs no new
mechanism.

**`deactivate`** reverses activation from the manifest. It is opt-in, because
leaving a namespaced asset installed is harmless and removing one you did not
record is not (§12.2).

---

## 12. Harvest — the assistant half

atuin holds your command history. atuout holds the **captured output** of each
command, keyed by `ATUIN_HISTORY_ID`. Together they are a record of what you
actually do, not what you documented.

`devman propose` mines both:

| Signal | Proposal |
|---|---|
| a command run N times across M repos | a missing `script` asset, `reach: user` |
| a command that failed, then succeeded after an edit | a missing `recipe` — the failure and the fix |
| a long argument string retyped often | a missing `alias` |
| a command an agent ran bare that a doer owns | a missing skill line, or a routing bug |

`propose` writes nothing. It prints candidates; `devman add --from-proposal <n>`
accepts one. Keep the human in the loop — a catalog that grows on its own stops
being trustworthy.

This is the one capability no other family member can offer. Build it last (§15).

---

## 13. Integrations and boundaries

| Repo | devman consumes | devman provides | The hard boundary |
|---|---|---|---|
| **copyroom** | its CLI facts (§9); the bootstrap seed `.devman/devman.toml` + the devenv import line | drift and collision reports on its skills (§10) | copyroom transports *files between repos*; devman resolves *packs at build time*. copyroom keeps its 3 skills in v1. |
| **my-ai** | the personal pack, resolved per machine (§7.3) | the pack format | my-ai keeps `AGENTS.md`, the `CLAUDE.md` symlink, and the law. |
| **repoman** | `registry.py` — the roster, `SPINE`, `route_when`; the `devenv shell` and `0/1/2/3` contracts | roster key `dev` | repoman owns the **facts of ordering**. devman never decides what comes before what. |
| **shellij** | the `enterShell` activation trigger | the assets its panes run | shellij owns sessions and panes. devman owns what is on `PATH` inside them. |
| **fleetman** | `registry.json` — which repos exist | fleet-wide asset queries: "which repos carry `db-reset`?" | fleetman indexes *repos*; devman indexes *assets*. Cross-repo execution stays `fleetman run`. |
| **testee** | its CLI facts, via the repo venv (§9) | drift reports; assets may call `testee verify` | devman never runs a test. |
| **gitman** | its CLI facts | drift reports; assets may call `gitman save` | devman never touches VCS. |
| **docman** | its CLI facts | drift reports; assets may call `docs-build` | devman's `docs` target ships the *literacy export*, not a site. |
| **pytuin** | the typed atuin client (KV, status, recordings) | nothing | pytuin owns the atuin subprocess boundary. |
| **atuout** | captured command output, for `propose` | nothing | atuout owns capture and storage. devman only reads. |

### 13.1 The rule that generates this table

> devman owns the **assets** — every developer asset's definition — and the
> **convention prose** that frames them. Every other manager owns its own
> **facts** and its own **domain prose**, plus the actions an asset calls.

When a boundary question comes up, apply that sentence twice:

- "Would devman **run** it?" If yes, the answer is wrong — that is a doer's job.
- "Would devman **decide** it?" If the decision is a domain fact (what `land`
  does, what comes before what), the answer is wrong — read it from the tool.

---

## 14. The sharp edges

### 14.1 atuin state is user-global and sync'd

An alias scoped to one repo, installed into a global replicated store, leaks to
every machine you own. Three mitigations, all mandatory:

1. **Namespace everything.** `dm.<ns>.<id>` for scripts, `dm-<id>` for aliases.
   The namespace comes from `.devman/devman.toml`, defaulting to the repo name.
2. **Manifest every install.** `.devman/state/` records exactly what activation
   wrote.
3. **Never delete an unrecorded entry.** Default policy is *reconcile on entry*.
   Aggressive cleanup is opt-in.

The `atuin-*` emitters are already out of v1 (§8). The `devenv-script` and
`skill` targets deliver most of the value with none of this risk.

### 14.2 The name

Resolved: devman takes the name (§4). repoman's module retires, and project-02 is
marked superseded. The literacy assets keep their `devenv-*` skill names — those
are user-facing trigger keywords, and renaming them would break every agent that
has learned them.

### 14.3 The walker borrows an interpreter it does not control

§9's design runs devman's code under another repo's python. Version skew is
already present and will widen. The walker must stay small, dependency-free, and
defensive: it returns `{"ok": false, "error": ...}` rather than raising, and
`doctor` degrades to a warning when a tool cannot be introspected. A tool devman
cannot read is a gap in the report, never a failed build.

---

## 15. Family contract compliance

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
  shared machine venv alongside copyroom, gitman, and docman — not as a per-repo
  uv dependency.

### 15.1 The CLI surface

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

## 16. Build order

**v1 is steps 1–4.** They need agreement from nobody and give a working tool.

| # | Step | Unblocks |
|---|---|---|
| 1 | **Asset model + `build`.** Pydantic models, the catalog loader, the layered stack, and two emitters: `devenv-script` and `skill`. Delete `src/devman/`; do not port it. | everything |
| 2 | **The walker + the two checks** (§9, §10). Parameter-aware from day one — a names-only check is unusable. | `doctor`, and the evidence for 002 |
| 3 | **`init` + `doctor` + the devenv module.** Family contract compliance; register roster key `dev` with repoman. | adoption by any repo |
| 4 | **Packs + `lock.toml` + `sync --machine`.** First pack: `devenv-literacy`, moved from the genome (§4.4). Second: the my-ai personal pack. | distribution |
| 5 | **`activate` + the atuin emitters.** The first step that touches state outside the repo. Behind the manifest. | shell-surface assets |
| 6 | **`propose`.** The harvester. | the assistant half |

`002-agent-surface` opens after step 4, on the evidence step 2 collects.

Step 2 is not optional and not deferrable. It is what makes §10 real, it is far
harder to retrofit than to build in, and it is the only thing that lets 002 be
argued from data instead of assertion.

---

## 17. Success criteria

The first draft had none. For a re-charter that rewrites a repo, these are the
conditions under which v1 is done and correct.

| # | Criterion | How it is measured |
|---|---|---|
| 1 | One asset definition emits every surface it declares | a `db-reset` asset with `targets: [devenv-script, skill]` produces both, and the skill's documented exit codes match the script's `exit:` block |
| 2 | An unchanged catalog costs nothing | `devman build` twice, then `devenv shell -- true` ≤ 0.25s (spike A baseline) |
| 3 | `build` is reproducible | two builds from the same catalog + lock produce **byte-identical** output |
| 4 | The reference check keeps its measured precision | ≥ 79 references extracted from the family's skills with **0 false positives**; the 3 synthetic defect classes still caught |
| 5 | The collision check holds its finding | the 33 known collisions (§10.2) are reported, and the count only falls when a skill is actually fixed |
| 6 | Introspection covers both install models | facts read for copyroom, gitman, docman, repoman (toolchain venv) **and** testee (repo venv) |
| 7 | The literacy move is a pure move | the 8 skills, 7 docs, and 6 articles emitted from the pack are byte-identical to the genome's |
| 8 | devman adopts itself | this repo carries `.devman/`, and `devman doctor` exits `0` |
| 9 | No repo carries pack bytes | `.devman/` contains no pack content after `sync --machine` |

Criteria 2, 4, 5, and 6 are regression tests on spike results. Their baselines
are in `.scratch/spikes/SPIKES.md` and the spike scripts still run.

---

## 18. Open questions

Answered questions moved to §6, §8, §9, and §10. What remains:

- **Pack format.** A git ref (like copyroom templates), a Python package, or a
  plain tarball? Lean: git ref — no publish step, and `sync --machine` can pin a
  rev.
- **Does `build` write outside `.devman/`?** It must, to emit skills. Decide
  whether that makes `build` impure, or whether a separate `devman materialize`
  owns every write outside `.devman/`. Lean: keep it in `build`, and let the
  manifest carry the purity guarantee.
- **Repo-scoped atuin scripts.** Should a `reach: repo` asset reach atuin at all,
  given the store is global? Lean: yes, but namespaced and reconciled on entry.
- **Shadowing policy.** Should a repo shadowing a `reach: machine` asset be a
  warning or an error? Lean: warning, reported by `doctor`.
- **How does a tool publish its domain prose (§5.2)?** A convention'd block in
  the tool's repo that devman pulls, or a field the walker returns? Lean: a
  `DOMAIN.md` per tool, read as a file — the walker should stay dependency-free.
- **Codex and other agents.** The `skill` emitter is Claude-first. Which other
  agent formats earn an emitter, and when?
- **How deep does the reference check go?** Names, sub-commands, and arity are in
  step 2 by necessity. Flag *values* and exit codes are harder. Lean: options in
  step 2 (spike C already does them), values behind `--strict` later.
