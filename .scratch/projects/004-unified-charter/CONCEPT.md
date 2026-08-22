# devman — Concept (unified charter)

> **STATUS: PROPOSED (2026-08-20). Supersedes `001-recharter`.**
> This charter folds the asset catalog of 001 and a second, independently
> derived design — a two-way readable projection of a codebase — into one
> engine. It keeps 001's decided sections, its four spikes, and its success
> criteria. It does **not** re-open `002-agent-surface`, which stays blocked
> on evidence (§4.3).
>
> **What changed from 001.** 001 specified the forward half: authored assets
> compiled into consumer surfaces. It listed the reverse half — `propose`, "the
> harvester, the assistant half" — as build-order step 6, unspecified. This
> charter specifies it, and in doing so generalizes the forward half to cover
> source code as an input. Three named engines replace hand-rolled machinery:
> **pydantree-sitter** for facts, **templateer** for emitters, **fsdantic** for
> staging.
>
> **Spike E has run.** The anchor scheme in §6.2 was this charter's riskiest
> claim, so §15 gated the whole mirror half on measuring it first. It measured
> sound. The **criterion** was wrong, not the design: old §16 criterion 10
> counted prose on deleted code as a re-attachment failure. It is replaced by
> 10a/10b/10c, and the rename bridge moved out of §17 and into build step 4.
> Results and method: `../../spikes/SPIKES.md`, Spike E.
>
> **Prose has two homes, by design.** Authored prose drafts in an out-of-repo
> store, where agent churn is free and no repo cooperation is needed. It
> publishes into the repo when it settles, where it earns branch, merge, and
> revert semantics. §7.2 specifies the boundary. Neither home is right for the
> whole lifetime, which is why the intake session's single-home answer and this
> charter's first draft both got it wrong.

---

## 1. One line

> **devman compiles one authored truth into every consumer surface, and routes
> an edit made on a surface back to the input that owns it.**

devman holds the assets and renders the surfaces. The other managers do the
work. No surface is ever authoritative.

---

## 2. Why unify

### 2.1 001 built half a machine

001 is correct and stays correct. Its model is: tracked source, ignored output,
byte-deterministic emitters, provenance on every emitted file, a manifest that
bounds what devman may remove. That is a compiler.

A compiler with no path back is a one-way door. When a generated skill reads
badly, or a generated script's help text is wrong, the fix has to be made
somewhere you are not looking — in the catalog — while the thing you are
looking at is the output. In practice that means the output gets edited, the
next `build` erases the edit, and trust in the tool ends.

001 knew this. It named the fix `propose` and deferred it to step 6 with no
design. This charter promotes it, because the reverse path is what makes the
forward path safe to use.

### 2.2 The same decomposition, derived twice

001 §5.2 splits every generated artifact into three materials. A separate design
session, working on markdown projections of source code and knowing nothing of
§5.2, split every generated file into three region kinds. They are the same
split:

| 001 §5.2 material | Region kind | Owner | Changes with |
|---|---|---|---|
| **facts** — introspected at build | `derived` | the source artifact | the binary or the code |
| **domain prose** — owned by the tool | `authored` | the prose store | the design |
| **convention prose** — authored here | `chrome` | the template | how you want to work |

Two independent derivations reaching one decomposition is the strongest
evidence available that the decomposition is real. It is also the whole reverse
path: **the region an edit lands in names the input that owns it.** Routing
needs no heuristics and no model.

### 2.3 What the second derivation adds

| Addition | Replaces |
|---|---|
| Source code as an input, read statically | the walker, for a large class of facts (§9) |
| Anchors, with orphan quarantine (§6.2) | nothing — new, and the riskiest part |
| Routed change requests (§10) | 001 step 6, `propose`, unspecified |
| Overlay staging and an approval gate (§10.2) | nothing — new |
| The convergence guard (§10.3) | nothing — new |
| A template layer per repo (§8.1) | 001's single global catalog of emitters |

---

## 3. What devman is, and is not

**Is:** the developer-asset manager. One authored catalog of scripts, skills,
prompts, aliases, and code prose. One emitter per surface. One routed path back
from any surface to its input.

**Is not:** an orchestrator (Dagu), an environment (devenv), a source-control
tool (jj), a scaffolder (copyroom), a workbench (shellij), a registry
(fleetman). devman renders and routes. It does not schedule, execute, or own
source identity.

**A new "is not", forced by the mirror:** devman is not a documentation
generator. A generated file that nobody can correct is a liability, because a
stale explanation reads exactly like a fresh one. Every surface devman emits
must be correctable through §10, or devman should not emit it.

---

## 4. Supersession

### 4.1 What carries forward from 001, unchanged

These are decided. Do not re-litigate them.

- **§4** — the absorption of repoman's project-02, and the literacy move.
- **§5, §5.1** — one file with typed frontmatter; `reach` and `origin` as
  separate axes.
- **§6's two rules** — tracked source, ignored output; provenance on everything.
- **§7** — packs resolve to a machine-wide cache, never into the repo.
- **§8.1** — reach atuin through pytuin, never by direct subprocess. There is no
  atuin prompt-template store; do not design around one.
- **§10** — the stale-reference check and the trigger-collision check, in that
  order, parameter-aware from day one.
- **All four spike results.** Baselines live in `.scratch/spikes/SPIKES.md` and
  the scripts still run. Byte-determinism (Spike A) is load-bearing and is now
  load-bearing twice — see §10.3.

### 4.2 What this charter changes

| 001 said | This charter says | Why |
|---|---|---|
| Assets are authored files | Assets are authored files **or projections of a source artifact** | source code is a fact source like a CLI is |
| Facts come from the walker | Facts come from the walker **or pydantree**, by asset kind | §9 |
| Emitters are hand-written per target | Emitters are **templateer templates**, layered (§8.1) | byte-determinism, strict-undefined, and a patchable unit |
| `propose` is step 6, undesigned | The reverse path is §10, and lands in the build order at step 4 | §2.1 |
| `build` writes; nothing reads back | `ingest` reads a surface and stages change requests | §10 |

### 4.3 What stays blocked

`002-agent-surface` — the proposal that devman author every agent skill in the
family — remains **blocked on evidence**, exactly as 001 left it. Its five entry
criteria in 002 §5 stand. The family measured **0 drift across 79 references**,
so its central premise is still unevidenced. Nothing in this charter is an
argument for the takeover, and the reverse path is not one either: a routed
change request works on surfaces devman already owns.

`003-cli-schema` is unaffected and still follows build-order step 2. §9 narrows
what it must cover but does not retire it — a CLI's own command tree is not
recoverable from source text alone in the general case.

---

## 5. The asset model

Unchanged from 001 §5. Every asset is one file with typed frontmatter, validated
by a pydantic model, rendered by one emitter per entry in `targets`.

```yaml
---
id: db-reset
kind: script            # script | skill | prompt | alias | recipe | mirror
reach: repo             # repo | user | machine
summary: Drop and re-seed the dev database.
targets: [devenv-script, skill, agent-command]
requires: [postgres]
exit:
  1: "migration conflict"
  2: "no database reachable"
---
#!/usr/bin/env bash
set -euo pipefail
...
```

`targets` is still the leverage. One new `kind` joins the list.

### 5.1 `reach` and `origin`

Unchanged from 001 §5.1. `reach` is on the asset and answers *where may this be
activated*. `origin` is the layer it came from and answers *who wins*. The two
axes now also decide where code prose lives — see §7.2.

### 5.2 Three materials

Unchanged from 001 §5.2, and now also the region model (§6.1). The table in §2.2
is the mapping.

### 5.3 The mirror — a new asset kind

A `kind: mirror` asset is a projection of a source artifact. It differs from
every other kind in one way: **its `derived` content is not authored anywhere.**
It is read out of the source at build time.

```yaml
---
id: mirror/src/fsdantic/overlay.py
kind: mirror
reach: repo
source: src/fsdantic/overlay.py
grammar: python
template: mirror/python            # resolved through the layers (§8.1)
targets: [markdown]
---
```

Slicing is **1:1 with the source file**. One source file, one mirror. Coarser
slicing (per package) and cross-file concept views are deferred — see §17.

---

## 6. Surfaces and regions

### 6.1 Region kinds

Every emitter tags what it writes. A tagged region is the unit of routing.

| Kind | Content | Emitted from | An edit here is a change request against |
|---|---|---|---|
| `derived` | signatures, types, docstrings present in source, exit codes, flags | the source artifact | **the source** |
| `authored` | why this exists, what invariant it holds, what breaks | the prose store | **the prose store** |
| `chrome` | headings, tables, ordering, phrasing, the deferral footer | the template | **the template** |

Regions nest. A `chrome` region contains `derived` slots — a rendered signature
line is template-owned formatting around source-owned values. An edit that
changes only slot values routes to the source. An edit that changes the
surrounding text routes to the template. Templateer's strict-undefined Jinja
makes the slot boundaries exact, so this is a diff at known offsets, not a
guess.

### 6.2 Anchors

Reattaching authored prose across a regeneration is the core mechanism, and the
riskiest thing in this charter.

**The anchor is `<relpath>::<dotted.symbol.path>`.** pydantree hands it over
directly: the `name` capture on the matched node, walked up the ancestor path
the `OutputModel`'s `__match__` already pins. It is human-readable, stable under
edits to a body, and stable under edits to neighbours.

It is **not** stable under rename or move. That is not fixable, so it is
bridged and contained instead.

> **[spike E] The bridge is two lookups, in order.** First `git -M`: if the
> file was renamed and the symbol survived, re-attach. That recovered **334 of
> pydantree's 342** real failures. Then name-only: match the dotted symbol
> alone, ignoring the path — **360 recoveries, 0 ambiguous** on public source
> symbols. Scope the second lookup to public source; over tests it measured
> **978 collisions**, because test names repeat across files.
>
> A deliberate reorganization still detaches most prose, and no bridge fixes
> that — the subject was renamed on purpose. Treat it as a bulk re-attachment
> chore, and give `doctor` a command for it.

### 6.3 Orphans and staleness

Two failure states, with different severities.

**Orphaned** — the anchor is gone. The symbol was renamed, moved, or deleted.
**devman never deletes orphaned prose.** It moves to a quarantine section at the
tail of the surface, tagged with its last-known anchor and the revision where
the anchor was last seen. Re-attaching it is a one-line edit that routes through
§10 like any other. This is the WORKFLOW rule — automation must not silently
discard a user's work — applied at the merge layer.

> **[spike E] Quarantine prevents loss; it does not recover.** Across four
> repos, only **4–9%** of detached prose ever re-attached on its own. Do not
> rely on a revert or a re-landed branch to heal quarantine — that is what the
> rename bridge is for. Quarantine's job is that nothing is ever lost, and it
> does that job perfectly (**0 lost**, all four repos).

**Stale** — the anchor is intact, but the source changed after the prose was
written. This is the more dangerous state, because stale prose reads exactly
like fresh prose and an agent consuming the surface cannot tell. So:

> Every `authored` region carries the **source content hash** and the **jj change
> ID** it was written against. The renderer compares against the current source
> and emits a visible staleness marker into the surface.

A stale marker is not a failure. It is the surface telling its reader which
sentences to distrust. Without it, the mirror is worse than no mirror.

---

## 7. The hidden directory

Revised from 001 §6.

```
.devman/
  devman.toml        # tracked  — policy: packs, reach rules, activation, namespace
  lock.toml          # tracked  — pinned pack versions + content digests
  assets/            # tracked  — this repo's own assets (source of truth)
    scripts/
    skills/
    prompts/
    aliases.toml
    mirror/          # tracked  — *published* prose, one sidecar per mirrored source
    templates/       # tracked  — repo-local template overrides (§8.1)
  build/             # ignored  — compiled output + manifest.json
    mirror/          # ignored  — the rendered surfaces
  state/             # ignored  — activation record, locks, staged change requests
```

and one store outside every repo:

```
~/.local/share/devman/prose/<project>/
  .jj/                                 # its own history — churn is free here
  src/fsdantic/overlay.py.prose.md     # drafts, keyed by anchor
  manifest.json                        # anchor → last-seen revision + source hash
```

001's two rules are unchanged and now cover more:

1. **Tracked source, ignored output.** `build/` is always reproducible from
   `assets/` plus `lock.toml` plus the current source tree.
2. **Provenance on everything.** Every emitted file names devman, its source
   asset id, and the pack version. devman removes only what its manifest
   records. **No timestamps, no hostnames, no map iteration order** — Spike A.

### 7.2 Where code prose lives — draft outside, publish inside

Authored prose has two lifetimes, and one home cannot serve both.

While prose is **churning** it must not touch the repo. §11.2 has an agent
proposing prose on every `mirror-full` run, and you correcting it. Committed
in-repo, that noise interleaves with real code commits, fills `jj log`, and
lands in every collaborator's review diff. Out-of-repo it costs nothing and
needs no cooperation from a repo you may not own.

Once prose **settles**, the repo is the better home. Prose about a function is
only true of *that revision* of that function. Tracked, it branches when the
code branches, merges when the code merges, reverts when the code reverts, and
reaches anyone who clones.

So the boundary is explicit:

| Phase | Home | Versioned by |
|---|---|---|
| **draft** | `~/.local/share/devman/prose/<project>/` | its own jj repo |
| **published** | `.devman/assets/mirror/<relpath>.prose.md` | the source repo |

`devman prose publish` copies a curated selection from the draft store into
`.devman/assets/mirror/`. It is explicit and **never automatic**. This mirrors
001 §16's treatment of `activate`: the step that crosses a boundary is always
its own gated step.

**`reach` decides whether publishing is permitted at all** (§5.1):

| `reach` | Drafts in | May publish? |
|---|---|---|
| `repo` *(default)* | the store | yes |
| `user` | the store | **no** — your private notes on a repo you do not own |
| `machine` | the store, never synced | no |

The renderer resolves published prose first, then layers the draft store on top.
A draft edit to already-published prose is therefore visible immediately, and
the surface marks it **unpublished** until you publish it.

**Anchor-keyed, not branch-keyed.** Draft prose resolves on any branch, and
§6.3's source-hash comparison marks it stale wherever the code differs. Prose
written on one branch is visible-but-flagged on another rather than absent —
which is the better failure. Published prose gets the stronger property
instead: it is exactly as correct as the revision that carries it.

The symlink the intake asked for stays, for ergonomics and for agents:
`.mirror/ → .devman/build/mirror/`, gitignored, one line.

### 7.3 The other symlink

Two symlinks, opposite directions, different jobs. Do not conflate them.

```
registration:  ~/.config/dagu/dags/repos/<project>  →  <repo>/.dagu/
ergonomics:    <repo>/.mirror/                      →  <repo>/.devman/build/mirror/
```

---

## 8. The emitters

Carried from 001 §8, with the engine named and one target added.

| Target | Output | Runtime | ship? |
|---|---|---|---|
| `devenv-script` | `.devman/build/devman.nix`, imported by `devenv.nix` | the pinned shell — **primary** | **yes** |
| `skill` | `.agents/skills/<name>/SKILL.md` | Claude Code, any agent | **yes** |
| `docs` | `.agents/devenv/**` | the literacy export | **yes** |
| `markdown` | `.devman/build/mirror/<relpath>.md` | agents first, humans second | **yes** |
| `agent-command` | `.claude/commands/<id>.md` | slash commands | later |
| `atuin-script` | `atuin scripts new`, named `dm.<ns>.<id>` | your shell | later |
| `atuin-alias` | `atuin dotfiles alias set dm-<id>` | your shell | later |
| `prompt` | prompt file, plus registration | agents, `atuin ai` | later |

**An emitter is a templateer template.** Validated pydantic model in, strict
Jinja out, deterministic artifact. This is not a convenience — it is what makes
§10.3 possible. A hand-written emitter is a function you cannot patch from its
own output.

Spike A confirmed `devenv-script` as primary: 5.46s cold, 0.16–0.21s warm,
1.44s on the build after a catalog change.

### 8.1 Template layers

Templates resolve through layers, like the catalog:

```
machine  →  user  →  pack  →  repo        (repo wins)
```

Global defaults live in `~/.config/devman/templates/`. A repo overrides in
`.devman/assets/templates/`. **A `chrome` change request patches the repo layer
by default.** Promoting an override to the global layer is a separate, explicit
command with its own blast-radius preview (§10.4).

An override is stored as a full template, not a diff, so rendering stays simple.
`devman doctor` renders the delta against the layer below, so you can always see
what a repo actually customized. Without that view, promotion is guesswork.

---

## 9. Fact introspection

001 §9 decided this and §14.3 recorded its sharp edge: **the walker borrows an
interpreter it does not control.** It imports a Typer app to read its command
tree, so it inherits that tool's dependencies, its import side effects, and its
failures. `typer-vendors-click` is a scar from exactly this — duck-type when
walking, because `isinstance` against click fails silently.

Split the job by fact source:

| Fact source | Read by | Executes anything? |
|---|---|---|
| **source code** — signatures, types, docstrings, structure | **pydantree-sitter** | no |
| **a CLI's own command tree** — sub-commands, flags, exit codes | the walker, then `003-cli-schema` | yes |

pydantree removes the walker for every source-derived fact, which is most of
them and all of the mirror's. It parses text with tree-sitter and validates
against an `OutputModel` at bind time, before any text is read. No import, no
interpreter, no side effects, and it works on languages devman has no runtime
for.

The walker survives for what static reading genuinely cannot recover: a command
tree assembled at runtime. `003-cli-schema` still retires it there.

**pydantree also supplies the byte `Span`s** that make §10.1's source route
possible. There is no unparse in pydantree and this charter does not need one —
write-back is a span splice, never a regeneration.

---

## 10. The reverse path

The half 001 deferred.

> Every surface devman emits is fully derived. It is therefore never
> authoritative, and an edit to it is never a conflict. It is a **change
> request** against one of three inputs.

### 10.1 Routing

Deterministic, from the region the edit landed in (§6.1). No model, no
heuristic.

| Region | Route | Applied by |
|---|---|---|
| `authored` | prose store | write the **draft** store; publishing is a separate, explicit step (§7.2) |
| `chrome` | template | templateer fills a template-change model; §10.3 guards it |
| `derived` | source | span splice at the pydantree `Span`, refused if the jj change moved |

A second, softer signal: if the same edit appears in *N* surfaces, it is
probably a template change misfiled as *N* local ones. `doctor` reports the
pattern and offers promotion. It never acts on it.

### 10.2 Staging and approval

No change request applies itself. Every route lands in an **fsdantic overlay**,
keyed by run ID, durable across processes so an approval can span two Dagu steps.

```
edit a surface
   → ingest: parse, classify by region, build the change set
   → overlay.merge into a staged workspace
   → dagu approval step, showing overlay.diff / preview
   → materialize to the owning input
```

For the `authored` route the owning input is the **draft** store, never the
repo. No path through `ingest` writes a tracked file. The only command that
adds prose to the source repo is `devman prose publish` (§7.2), and it is run
by you.

fsdantic supplies the whole mechanism already: `merge`, `list_changes`, `diff`,
`preview`, `reset`, `tombstone`, `to_disk`. devman adds no filesystem staging of
its own.

**A staged proposal is not prose yet.** The draft store is durable and
version-controlled. A staged proposal is disposable operational state in
`.devman/state/`, with retention — unapproved proposals otherwise accumulate
without bound. Three stages, each one step further from disposable: staged →
drafted → published.

fsdantic is async and Dagu steps are one-shot processes. A thin `devman ingest`
/ `devman apply` CLI wraps `asyncio.run` per subcommand; the overlay persists
between them by run ID.

### 10.3 The convergence guard

For the `chrome` route only, and non-negotiable.

> After patching a template, re-render with unchanged inputs. Assert the output
> reproduces the edit. If it does not, reject the patch before it reaches the
> approval step.

This is cheap, automatic, and it is the difference between a safe template route
and an LLM rewriting your emitters on a guess. It works **only** because Spike A
already forced byte-determinism on every emitter. That constraint was adopted for
devenv's eval cache; it now also buys the reverse path its correctness test.

### 10.4 Blast radius

A template patch changes every surface that uses it. The approval step must show
more than the template diff: re-render all affected surfaces into the overlay,
report the count, and show sample before/after pairs. `overlay.preview` exists
for this.

Promotion from the repo layer to a global layer repeats the check across every
repo that resolves that template.

---

## 11. Orchestration

devman does not schedule. Per the orchestration guide: **Dagu orchestrates,
devenv executes.** devman is a devenv task.

| Layer | Owns |
|---|---|
| devenv | `devman-build`, `devman-ingest`, `devman-apply` — the canonical implementations |
| Dagu | when they run, in what order, with which approval gate |
| watchexec | detecting that a file changed |
| jj | the revision a surface was derived from |

Three DAGs in `.dagu/`, matching the guide's workspace/snapshot split:

| DAG | Kind | Trigger | Contents |
|---|---|---|---|
| `mirror-sync` | workspace | file save, debounced, per-file | `devman build --only <path>`. Deterministic. No LLM. |
| `mirror-ingest` | workspace | surface changed | `ingest` → **approval** → `apply` |
| `mirror-full` | snapshot | jj commit, or scheduled | whole repo, commit-addressed, resource class `heavy`, includes the agent pass (§11.2) |

### 11.1 Loop-breaking

Two watchers that write into each other's inputs will chase each other. Break it
with a generation token, not a lock: `build` records the content hashes it just
wrote to `.devman/state/generation.json`, and `ingest` skips any file whose hash
matches. Stateless, no deadlock, no ordering assumption.

### 11.2 The agent pass

An LLM proposes `authored` prose. It runs on **`mirror-full` only** — never on
the save path — and its output lands in the overlay as a proposal that a human
approves. It never writes to the draft store directly, and it can never reach
a tracked file — publishing is yours alone (§7.2).

It must be incremental or it is unaffordable: propose only for regions that are
**empty or marked stale** (§6.3). Never re-propose prose that is fresh and
approved.

This is templateer's `generate` doing what it was built for. The model never
writes the surface; it fills a validated prose model, and the deterministic
renderer produces the surface.

---

## 12. The two checks

Unchanged from 001 §10, and still in that order.

1. **Stale-reference check.** 79 references extracted from the family's skills,
   **0 false positives**, 3 synthetic defect classes caught. Parameter-aware from
   day one — a names-only check is unusable.
2. **Trigger-collision check.** 33 known collisions reported.

001 §10's framing holds: these are services devman offers, not territory it
claims. Reading skills does not require owning them. That distinction is what
keeps `002` blocked on evidence rather than assertion.

---

## 13. Lifecycle

```
author an asset        →  .devman/assets/
build                  →  .devman/build/ + manifest.json
read a surface         →  agents, humans, the shell
edit a surface         →  ingest → classify → stage → approve → apply
                                                              ├─ authored → draft store
                                                              ├─ chrome   → template (guarded)
                                                              └─ derived  → source (guarded)
settle prose           →  devman prose publish  →  .devman/assets/mirror/
```

The loop closes. Every arrow out has an arrow back. Only the last arrow crosses
into tracked repo state, and only you draw it.

---

## 14. Sharp edges

Carried from 001 §14, plus three new.

**14.1 atuin state is user-global and sync'd.** Unchanged. Namespace everything;
reconcile on entry.

**14.2 The name.** Unchanged. `devman` is the developer-asset manager. The tmuxp
orchestrator that held the name is superseded, and `.devman/` changes meaning —
it was a workspace descriptor, it is now the asset root. **`fsdantic` already
carries a live `.devman/` of the old shape** (`.devman/store/vendor/agentfs`).
Migration must detect and report the old layout, not silently adopt it.

**14.3 The walker borrows an interpreter it does not control.** Narrowed by §9,
not removed.

**14.4 Anchors break on rename.** Bridged (§6.2) and contained (§6.3), not
solved. **[spike E]** measured this rather than assuming it: three of four
repos produced **zero** anchor failures, and pydantree — the family's worst
case — recovered 334 of 342. The residual sharp edge is a *deliberate*
reorganization, where the subject is renamed on purpose and no bridge can
help. That is a bulk chore, not data loss.

**14.5 A generated surface that cannot be corrected is a liability.** The
staleness marker (§6.3) and the reverse path (§10) are the mitigation. Do not
ship a `markdown` target without both.

**14.6 The `derived` route is the dangerous one.** Splicing edited text back into
source is the least valuable of the three routes — you already own an editor for
source code — and the only one that can corrupt a file. It ships last, behind
the other two, and it refuses whenever the source moved since the surface was
rendered.

**14.7 The two prose homes will diverge.** Publishing copies, so the draft store
and `.devman/assets/mirror/` disagree the moment either is edited alone — and a
`jj revert` of published prose does not touch the draft that produced it.
`doctor` reports the delta in both directions and names which side is newer.
Resolution is manual and routes through §10 like any other change request. **Do
not add automatic reconciliation.** A copy that silently heals is a copy you
cannot trust, and it would reintroduce exactly the silent-rewrite failure §10.2
exists to prevent.

---

## 15. Build order

**Step 1 is a measurement, not a feature.** It can invalidate half this charter,
so it runs first and costs a day.

| # | Step | Unblocks |
|---|---|---|
| 1 | ~~**The anchor experiment.**~~ **Done — spike E, 2026-08-20.** The anchor is sound; criterion 10 was not. `anchors.py` is the regression baseline for 10a/10b/10c. | ✅ the entire mirror half |
| 2 | **Asset model + `build`.** Pydantic models, catalog loader, layered stack, templateer emitters: `devenv-script` and `skill`. **Delete `src/devman/`; do not port it.** | everything |
| 3 | **The walker + the two checks** (§9, §12). Parameter-aware from day one. | `doctor`, and the evidence for 002 |
| 4 | **The `markdown` target.** pydantree extraction, region tagging, anchors, **the two-lookup rename bridge (§6.2)**, orphan quarantine, staleness markers. Forward only. | the mirror |
| 5 | **`ingest` + `apply` for `authored`, plus `prose publish`.** The draft store, the overlay, the approval gate, the generation token, and the one command that crosses into tracked state. Lowest-risk route first. | the reverse path |
| 6 | **`init` + `doctor` + the devenv module.** Family contract compliance; register roster key `dev` with repoman. | adoption by any repo |
| 7 | **`chrome` route + the convergence guard + blast-radius preview.** | template correction |
| 8 | **Packs + `lock.toml` + `sync --machine`.** First pack: `devenv-literacy`. Second: the my-ai personal pack. | distribution |
| 9 | **The agent prose pass** on `mirror-full`. | the assistant half |
| 10 | **`activate` + the atuin emitters.** First step touching state outside the repo. | shell-surface assets |
| 11 | **`derived` route.** Span splice, revision-guarded. Last, deliberately. | code correction |

Step 3 is still not optional and not deferrable — 001's reasoning stands. It is
what makes §12 real, it is far harder to retrofit than to build in, and it is the
only thing that lets 002 be argued from data.

`003-cli-schema` opens after step 3. `002-agent-surface` opens after step 8, on
its own five criteria, or not at all.

---

## 16. Success criteria

001 §17's nine criteria carry forward unchanged as 1–9. Six more cover the new
half.

| # | Criterion | How it is measured |
|---|---|---|
| 1 | One asset definition emits every surface it declares | `db-reset` with `targets: [devenv-script, skill]` produces both; the skill's exit codes match the script's `exit:` block |
| 2 | An unchanged catalog costs nothing | `devman build` twice, then `devenv shell -- true` ≤ 0.25s (Spike A) |
| 3 | `build` is reproducible | two builds from the same catalog + lock produce **byte-identical** output |
| 4 | The reference check keeps its precision | ≥ 79 references, **0 false positives**; 3 synthetic defect classes caught |
| 5 | The collision check holds its finding | the 33 known collisions reported; the count falls only when a skill is fixed |
| 6 | Introspection covers both install models | facts read for copyroom, gitman, docman, repoman (toolchain venv) **and** testee (repo venv) |
| 7 | The literacy move is a pure move | 8 skills, 7 docs, 6 articles byte-identical to the genome's |
| 8 | devman adopts itself | this repo carries `.devman/`, `devman doctor` exits `0` |
| 9 | No repo carries pack bytes | `.devman/` holds no pack content after `sync --machine` |
| 10a | **Anchors survive ordinary work** | of orphans whose code still exists at the child commit, ≥ 95% re-attach after the rename bridge. **[spike E] measured 97.7%** on pydantree; 0 failures on fsdantic, templateer, devman |
| 10b | **No prose is ever lost** | every non-attaching block is quarantined and recoverable. **[spike E] 0 lost**, all four repos |
| 10c | **The name-only bridge does not guess** | 0 ambiguous matches on public source symbols. **[spike E] 0 of 360** |
| 11 | **Stale prose is always visible** | mutate a mirrored function, rebuild; the surface carries a staleness marker on every affected `authored` region |
| 12 | **Routing is exact** | edits seeded in each of the three region kinds route to the correct input, 100% |
| 13 | **A template patch converges** | every accepted `chrome` change request re-renders to reproduce the edit; non-converging patches are rejected, not applied |
| 14 | **Nothing applies unapproved** | with the approval step declined, no input file on disk changes |
| 15 | **The watchers do not chase each other** | `mirror-sync` and `mirror-ingest` both armed, one save, exactly one build and zero ingests |
| 16 | **Publishing is explicit and bounded** | `mirror-full` runs the agent pass to completion and `apply` accepts every proposal; the source repo's **tracked files are unchanged** until `devman prose publish` runs |
| 17 | **Divergence is reported, never healed** | edit a published sidecar and its draft differently; `doctor` names both sides and which is newer; neither file changes |

Criteria 2, 4, 5, and 6 are regression tests on spike baselines in
`.scratch/spikes/SPIKES.md`. Criterion 10 is the step-1 measurement, promoted.
Criteria 14 and 16 are the same guarantee at two boundaries — nothing devman
does reaches your tracked files without you.

---

## 17. Open questions

Carried from 001 §18, minus what §7–§10 answered, plus what unification opened.

**From 001, still open:**

- **Pack format.** Git ref, Python package, or tarball? Lean: git ref — no
  publish step, and `sync --machine` can pin a rev.
- **Does `build` write outside `.devman/`?** It must, to emit skills. Lean: keep
  it in `build`, and let the manifest carry the purity guarantee.
- **Repo-scoped atuin scripts.** Should a `reach: repo` asset reach a global
  store? Lean: yes, namespaced and reconciled on entry.
- **Shadowing policy.** Warning or error when a repo shadows `reach: machine`?
  Lean: warning, reported by `doctor`.
- **How does a tool publish its domain prose?** Lean: a `DOMAIN.md` per tool,
  read as a file.
- **Codex and other agents.** Which formats earn an emitter, and when?

**New:**

- ~~**Does the anchor need a rename bridge?**~~ **Answered by spike E: yes.**
  Moved into build-order step 4. `git -M` for the file case; name-only matching
  on the residue, which measured **0 ambiguous of 360** on public source
  symbols. Do not run the name-only bridge over tests — the same scope measured
  978 collisions there.
- **Coarser slicing.** 1:1 per file is the substrate. Per-package surfaces are
  better token economics for agents; cross-file concept views are better still
  and much harder to keep fresh. Lean: a second render pass that references
  file-level anchors, never a second extraction.
- **Which languages ship first?** pydantree needs a grammar per language and an
  `OutputModel` per fact shape. Lean: Python and Nix, because that is what the
  family is written in.
- **Is `chrome` one region kind or two?** Layout and phrasing may deserve
  different routes — reordering sections is a different intent from rewording a
  heading. Lean: one, until an edit proves otherwise.
- **Retention.** Staged proposals in `.devman/state/` are disposable — the guide
  suggests 7 days. The draft prose store is not disposable and needs no
  retention. Where does an *approved but unpublished* draft sit? Lean: durable,
  and `doctor` reports its age.
- **When should `doctor` nag about publishing?** Unpublished prose is invisible
  to collaborators and to CI, so a repo can look documented to you and bare to
  everyone else. Lean: report a count and the oldest age, never block, never
  publish automatically.
- **Does the draft store need a per-branch view?** Anchor-keyed drafts are
  branch-agnostic by construction (§7.2), which is right for intent and wrong
  for prose describing one branch's implementation. The staleness marker covers
  it today. Lean: leave it, and revisit only if flagged-but-wrong prose becomes
  a real annoyance.
