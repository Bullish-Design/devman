---
title: "Concept — an agent factory that compiles a library (working name; see §11)"
status: concept (developing; twelve decisions confirmed; two spikes gate the design)
source: ladder-kickoff.md; Paseo chat 2026-08-19/20; devman 004 charter; spike E
captured: 2026-08-20
revised: 2026-08-20
owner: andrew
output_type: project
depends_on:
  - dagu (the factory floor — parallel, reactive orchestration)
  - fsdantic (the unit store, optimistic concurrency, per-agent overlays)
  - templateer (typed handoffs between agent stages; the final deterministic render)
  - pydantree-sitter (AST-keyed ingest; structural diff)
  - devenv (the only thing besides drift that may block)
  - jj (undo, revision identity)
deferred_dependencies:
  - tyo3 (semantic reading and CodeDiff — v2; see §11)
  - cairn (sandboxed execution of agent-written code — v2; needs a non-human accept path)
supersedes: the "claim ledger" reading, and the "templates as generator" reading (§12)
---

# Concept — an agent factory that compiles a library

## 0. What this settles

| Question | Decision |
|---|---|
| What does the work? | LLM agents, many, in parallel, across dagu workflows. |
| What are templateer models for? | Typed handoffs between agent stages. Not leverage. |
| What do templates own? | Skeleton and bodies. Bodies are model fields. |
| Is generated source tracked? | Yes. Pay the codegen tax with a drift check. |
| What is the reverse half? | Global analysis over the rendered tree — references, links, summaries. |
| What may block a build? | `devenv` checks and drift. **Never an agent.** |
| Which fields do you author? | `spec` and `examples`. Everything else derives. No pinned fields (§3.1). |
| What happens when you edit `src/`? | The edit **promotes to the spec**, guarded by a re-derive check (§5.1). |
| What is in the cache key? | Authored fields plus dependency *signatures* — never bodies (§3.2). |
| How strong is the gate? | Exactly as strong as your `examples`, and no stronger (§10.3). |
| How do parallel writers agree? | fsdantic KV compare-and-set. Loser re-runs; **never merge**. |
| Why does re-running not re-decide? | Every stochastic result is content-addressed and cached. |
| Why does the reactive graph terminate? | It is stratified. Authored state is a sink. |
| What ships in v1? | fsdantic, templateer, dagu. No reading half. See §11.1. |

---

## 1. One sentence

> **Agents grow the library; typed handoffs, content-addressed results, and a
> trigger graph that cannot cycle are the bid to make the result reproducible
> even though no step in it is.**

"Bid", not "make" — §10.1 is the claim that this actually converges, and it is
not yet proven.

The engineering problem is not "generate code." Agents already do that. It is
**building something reliable out of many unreliable parts running at once.**

---

## 2. The shape

```
  conversation ──▶ spec ──▶ body ──▶ style ──▶ render ──▶ src/**.py
  surface edit ──▶  │        (typed + cached, §3.2)          │
                    ▼                                        │
                 UNITS ◀────────── ingest ◀──────────────────┤  src/ edit
                    │              (generation-token gated)  │
                    │                                        ▼
                    │                                   read (v2)
                    ▼                                        │
              markdown surface ◀────────────────────────────-┘
                    │                       references, links, summaries
                    └──▶ proposals ──▶ (data only; never triggers, §4.3)
```

Three input channels — talk to an agent, edit the surface, or edit Python — and
they are not equivalent. A conversation enters at `spec`. A surface edit writes
an authored field directly. A `src/` edit enters through `ingest`, which fires
only for changes the factory did not make (§8).

dagu runs the stages, hundreds at a time.

---

## 3. The three primitives

### 3.1 The unit

**One typed declaration owning everything about one function or class**: its
spec, signature, body, docstring, errors, and test.

**Two field kinds, and the list is closed.** §3.2's cache key, §4.4's conflict
rule, and §5's ingest rule all key on this split, so it is stated once here and
obeyed everywhere.

| Field | Kind | On conflict | In the cache key? |
|---|---|---|---|
| `spec` | **authored** | both sides become proposals; you resolve | yes |
| `examples` | **authored** | both sides become proposals; you resolve | yes |
| `body` | derived | discard the loser, re-derive | no |
| `test` | derived | discard the loser, re-derive | no |
| `signature` | derived | discard the loser, re-derive | no |
| `raises` | derived | discard the loser, re-derive | no |
| `docstring` | derived | discard the loser, re-derive | no |

**Authored fields are few, they are the cache key, and everything else is
regenerable.** That is the invariant. Two fields carry your intent; five are
computed from them.

`examples` earns its place as authored because it is what makes the gate real —
see §4.5 and §10.3.

**There is no pinned field, and adding one would be a mistake.** Marking a
derived field "user-modified, do not regenerate" is the obvious fix for §5's
ingest problem and it fails slowly. Each pin is individually reasonable, pins
accumulate, and every pinned field is a place where "the spec describes the
code" has quietly become false. A spec that says *"return the cached value, or
None past the TTL"* beside a signature taking a `default` parameter no spec
mentions will mislead the next agent that reads it to write a caller. Pinning
reintroduces exactly the drift a unit exists to prevent (§3.1), one field at a
time, invisibly. **Promotion is the mechanism instead — §5.1.**

A body in a `.py` file is a body. A body in a unit sits beside the spec it
satisfies and the test that checks it, so all three render from one declaration
and cannot drift apart. That is the whole argument for bodies-in-models.

**Units nest, and a file is not one of them.** A module unit holds module-level
content only — its docstring and constants. Function and class units belong to
it; a class unit holds method units. `src/cache.py` is not stored anywhere: it
is the render of every unit declaring `module = "cache"`. Granularity is
therefore not a choice to make; it is the nesting.

**Membership is declared by the child, never listed by the parent.** If a module
unit carried an ordered list of its members, every agent adding a function would
compare-and-set that one record, and it would become the hot row that serializes
the factory. Instead each unit declares its own module, and order is a
deterministic rule at render time: dependency order, then alphabetical. No
shared record exists, so no contention exists.

**Imports and ordering are collated, not authored.** Each unit declares what it
needs; the render dedupes and sorts. Import hygiene stops being anyone's job.

This is what makes parallel composition free. Agent A writes `get` and agent B
writes `set`, in different workflows, at the same time, neither aware of the
other, and the render joins them. **There is no merge step, because the parts
were never in conflict.**

### 3.2 The stage

**One agent step. Reads a typed input, fills a validated model, and its output
is content-addressed.**

```
stage(input, generator_version) → artifact, keyed by (hash(input), generator_version)
```

A pipeline is a chain of stages. Conversation → spec → unit model → body →
style pass → render. The final render is just a stage whose generator is
deterministic — so "render" is not a separate primitive, it is the last stage.

### The input key

§4.2 and §4.4 make opposite demands of it. §4.2 wants hits, because a hit is
what stops re-decision. §4.4 wants a losing writer's re-run to produce something
*different*, or the retry accomplishes nothing. Neither naive answer works:

| Key | Breaks |
|---|---|
| The spec alone | a loser re-runs, hits cache, and rewrites the value it just lost with. **The retry is a no-op wearing a retry's clothes**, and §4.4 is inert. |
| Spec plus full unit state | the unit holds the body, the body changes on every render, so every stage misses every run. Nothing is ever frozen, every run re-decides, and the churn §4.2 exists to prevent arrives anyway — at one model call per stage per unit. |

**Decided:**

```
input_key = hash(
    unit.spec,
    unit.examples,
    { dep_id: dep.signature_hash for dep in unit.depends_on },
)
```

In: the authored fields (§3.1), and the *interface* of everything the unit
calls. Out: the unit's own body, and the *bodies* of its dependencies.

One rule, correct in both cases:

| Event | Result |
|---|---|
| Another agent changed an unrelated unit | dep signature hashes unchanged → **cache hit** → cheap, converges at once |
| Another agent renamed `_store.fetch` → `_store.lookup` | that dep's signature hash moves → **cache miss** → genuine recompute against the real new interface |

**Dependency bodies are excluded deliberately.** Rewriting `_store.fetch`'s body
without touching its signature leaves `cache.get`'s contract intact, so
`cache.get` needs no regeneration. Including dependency bodies would cascade a
re-derive across the whole reachable graph on any edit — expensive, and a churn
source in itself.

**v1 over-approximates, on purpose.** Without tyo3 there is no semantic
dependency graph; pydantree gives imports and call names, which is a coarser
set, so some misses will be spurious. That is the right direction to be wrong
in: **a spurious miss costs one model call, a spurious hit serves stale code.**
`affected_ids` narrows it exactly when tyo3 lands (§11.1).

The hit rate is unknown on a real codebase, so §10.1 measures it rather than
assuming it. At 80% §4.2 works as designed; at 15% the caching story is
decorative and you need to know before building on it.

Two properties make a chain of stochastic steps behave:

1. **No stage consumes prose.** Every handoff is a validated Pydantic model.
   The model is the contract, and a stage that cannot fill it fails loudly
   instead of improvising.
2. **No stage recomputes.** Same input, same generator version, cache hit.
   Re-running a pipeline is a series of cache reads.

### 3.3 The reading

**Global analysis over the rendered tree.** The only primitive that produces
knowledge no unit contains.

**Deferred to v2** — §11.1 cuts it, because neither riskiest claim depends on
it. Structure comes from `pydantree-sitter` first; tyo3 lands when semantic
references are genuinely needed. The table below is what tyo3 eventually gives:

| Fact | From |
|---|---|
| Who calls this | `find_references` |
| What it depends on, transitively | the code graph, `affected_ids` |
| Type hierarchy, overrides | `type_hierarchy` |
| Summaries, descriptions, embeddings | derived layers, cached by content hash |

A unit knows what it is. Only the tree knows what it is to everything else.
Rendering is local; reading is global. **They are not inverses — they do not
operate on the same scope**, so nothing round-trips between them and nothing
can ratchet.

---

## 4. The five laws

Everything hard about this design follows from "many stochastic agents, at
once." These five are what make that survivable. None is optional.

### 4.1 Typed handoffs

Every agent fills a validated model. No stage reads another stage's prose.
Multi-stage agent pipelines degrade because error compounds through natural
language; a schema at each boundary stops the compounding.

### 4.2 Content-addressed results

A stochastic result is computed once, keyed by `(input_hash,
generator_version)`, and never recomputed while those hold.

**A cached artifact is a frozen arbitrary decision.** This retires the
forced-versus-free classification an earlier draft needed. You do not classify
which decisions to keep — you refuse to recompute any of them. Change the style
guide, bump its `generator_version`, and everything re-renders deliberately.

*The gap, stated honestly:* editing a **spec** changes the input hash and thaws
everything downstream, so arbitrary picks are re-made and the code churns.
Partial mitigation — pass the previous cached output into the stage as context:
"change only what the spec change requires." **This is unproven.** It is the
second spike in §10.

### 4.3 Stratified reactions

Workflows react to events, and events are produced by workflows. Without a rule
this oscillates.

**The trigger graph is a strict DAG over workflow kinds. Authored state is a
sink.**

```
conversation ─▶ spec ─▶ unit ─▶ render ─▶ read ─▶ surface
                                                    │
                       (never backward — enqueue a proposal instead)
```

This is not invented here. tyo3's layers spec already enforces it: *"a derived
layer can never depend on an authored layer... authored layers are sinks for
the derivation cascade, so reactions always terminate."* The same rule, one
level up, over dagu workflows.

Anything that wants to fire backward — the style agent thinks the spec is
wrong, the reader notices an undocumented behaviour — **writes a proposal into
a queue.** A proposal is data. It never triggers.

### 4.4 Conflicts are re-derived, not merged

Agents do not lock units. Each writes through fsdantic's versioned KV, which
uses atomic SQL compare-and-set. The losing writer raises `KVConflictError`
carrying `expected_version` and `actual_version`. It re-runs against new head.

Locking would serialize the factory and destroy the parallelism that is the
point. fsdantic already ships the mechanism — `save_if_version`,
`compare_and_set`, per-item conflict reporting in `save_many` — so this needs
no new machinery and no MVCC database.

**The rule that matters is what happens next, and it is not a merge.**

| Field | On conflict |
|---|---|
| Derived — body, test, signature, raises, docstring | **discard the loser and re-run.** Never merge. |
| Authored — spec, examples | both survive as proposals (§4.3). You resolve. |

The full table is §3.1; this is the same split viewed from the write path.

Merging is for authored data you cannot regenerate. A body is a cached function
of its spec, so a losing writer has nothing worth saving — it re-derives at the
cost of one cache miss. Merging two independently generated bodies is the worst
operation available: agent A adds a TTL field, agent B renames the store, the
text merges cleanly, and the code is broken. Worse, the merge would itself be a
stochastic stage, adding a failure mode instead of removing one.

Overlays use `MergeStrategy.ERROR`, never `OVERWRITE`. fsdantic refuses silent
overwrites by default, which is exactly the required behaviour.

**Why the conflict surface is small.** Agents write *units* — keyed records —
and `src/` is rendered downstream by one deterministic owner. Two agents on
different units never touch. Filesystem-level contention mostly does not exist
in this design, so the expensive question is one it never has to ask.

### 4.5 Stochastic proposes, deterministic disposes

**Only `devenv` checks and the drift check may block a build. An agent never
gates.** A style-review agent emits an artifact and, at most, a proposal.

This is `WORKFLOW.md`'s existing rule — "fast, objective checks may block a
change; agent judgment should normally create a review artifact" — and it is
also the kickoff §5 lesson: a stochastic gate fails open, so it buys nothing
and costs autonomy.

**The gate is only as strong as `examples`.** `test` is derived, so code and
tests descend from one spec through one class of model. A passing suite proves
the two agents agreed with each other, not that either agreed with you. The
`examples` field (§3.1) is what supplies an assertion neither agent chose. §10.3
states the failure and its bound.

---

## 5. The round trip — why editing Python stays legal

Bodies live in models, so the obvious cost is reviewing TOML instead of Python.
You do not, because the final render is deterministic and ingest is AST-keyed.

```
edit src/cache.py → dagu sees it → parse, walk to the qualified name
                  → write the body node to that unit
                  → re-render → byte-identical to what you saved
```

**No marker comments in generated source.** An earlier draft delimited each
unit's span with markers and mapped span back to unit. A marker is bookkeeping
for the round trip. Writing it into the artifact makes the output carry the
mechanism that produced it, and a formatter or a careless edit can delete it.
pydantree resolves `cache.get` by qualified name and hands over the body node
and its byte span, so the mapping needs nothing written into the file.

**`ruff format` is the last render stage.** Byte equality (§3.2) is only
attainable if the render survives your formatter. Without this, the first
`ruff format` over `src/` breaks drift detection everywhere.

`render(ingest(render(u))) == render(u)`. Editing Python is a first-class way to
change a unit.

**The rule: ingest everything that has a home; fail only on what does not.**

| Edit on disk | Action |
|---|---|
| none — file equals the render | nothing |
| maps to a **derived** field — body, signature, docstring, raises | **promote to the spec** (§5.1). Never stored in the field. |
| a new top-level `def` or `class` | **create a new unit** in that module |
| a deleted `def` or `class` | **tombstone** the unit; it is recoverable, never dropped |
| maps to nothing — the import block, member ordering, module boilerplate | **fail**, and name the declaration to change instead |

An earlier draft failed the build on anything outside a body slot. That would
reject adding a parameter in your editor, which is an ordinary thing to do. The
only edits that genuinely have nowhere to go are the **collated** ones (§3.1) —
they are computed from declarations, so editing them by hand is meaningless
rather than dangerous.

### 5.1 Promotion — an editor edit changes the spec, not the field

Every field an editor edit can reach is derived (§3.1). Writing the edit into
that field would leave the unit internally inconsistent, and nothing would
complain until the next re-derivation silently reverted it.

**The failure it prevents, concretely.** `cache.get`'s spec says *"Return the
cached value, or None past the TTL."* You add `default: V | None = None` in your
editor. Ingest updates `signature` and `body`; `spec` is untouched. Nothing is
wrong yet. Then anything re-derives — a lost compare-and-set, a
`generator_version` bump, a typo fix in the spec — and the body stage reads a
spec that has never heard of `default`. The parameter vanishes. If callers use
it the typechecker fails, but the error points at the *caller*, three stages
away from the field that was reverted. If no caller uses it yet, nothing fails
at all.

**So the edit updates the spec instead:**

```
add `default: V | None = None`
  → ingest: signature changed, signature is derived
  → promote stage: (spec, old signature, new signature) → new spec
      "Return the cached value. Past the TTL, or on a miss, return the
       caller-supplied default, which is None unless given."
  → signature and body re-derive from the new spec
  → render
```

The spec now asks for what you wrote, so every future re-derivation reproduces
it.

**Promotion is stochastic, so it is guarded.** After promoting, re-derive and
compare against what you actually typed. If the re-derived signature has no
`default`, the promotion did not capture your intent:

> **Reject the promotion. Leave the edit in `src/`. Raise a proposal: "I could
> not express this change as a spec — write it yourself."**

This is 004's convergence guard, and without it promotion has the same
silent-loss shape as the bug it replaces. With it there are two outcomes and
both are honest.

**The cost, named rather than hidden.** An editor save now triggers a model
call. Debounce per save, never per keystroke; use a small fast model; budget it
in §8. This is the price of not having pinned fields, and it is worth paying.

### 5.2 Where a diff is structural, and where it must be bytes

Two jobs, opposite answers. Conflating them is the mistake to avoid.

| Job | Compare | Why |
|---|---|---|
| Drift detection, and any gate | **bytes** | exact and O(1). AST equality would hide formatting drift, and a heuristic gate violates §4.5 |
| Ingest, review, "what changed" | **structure** | text diffs of collated output are mostly noise |

**No tree-diff algorithm is needed.** Tree edit distance is the expensive,
heuristic way to answer "what changed" when the only structure available is
text. Units already partition the file by identity, so the diff is a set
comparison over keyed records:

| Result | Test |
|---|---|
| `changed` | same id, different body hash |
| `moved` | same id, same body hash, new location |
| `added` / `removed` | set difference over ids |

Exact, cheap, and no alignment step. tyo3's `CodeDiff` is already this shape —
identity by `DurableId`, `changed` by `content_hash`, `moved` by
`(file, qualified_name)` at equal hash. v1 gets the same shape from pydantree
without semantics: qualified name plus body hash.

**This retires the collation-stability risk.** §10.2 lists reordering and import
churn as a way the design could fail. Under a structural diff, reordering is a
large textual diff and a *zero* structural one. The ordering rule therefore has
to be deterministic, not good.

The hard case is not a body edit. It is a cross-file refactor — extract method,
move class, rename across twelve files. One editor action becomes several unit
updates plus new and deleted units. §10 measures it.

---

## 6. The surface

One markdown file per unit. **Three region kinds, one route** — only `authored`
is writable.

```markdown
# cache.get                                   <!-- unit: cache.get -->

## Spec                                       <!-- authored → unit.spec -->
Return the cached value, or None past the TTL.

## Body                                       <!-- authored → unit.body -->
```python
if (entry := self._store.get(key)) is None:
    return None
```

## Called by                                  <!-- derived, read-only -->
- [`session.resolve`](session.resolve.md) — src/session.py:112

## Proposals                                  <!-- queued, read-only -->
- style: this body duplicates `cache.peek`. Extract?
```

004 had three region kinds and three routes. `chrome` is deleted — changing how
the surface looks means editing the template, directly, which is rare. Routing
layout edits through a surface was ceremony with no risk to price.

`Called by` is v2 (§11.1). When it lands, links resolve through tyo3, so they
point at durable ids rather than line numbers and survive the next render. v1
ships `Spec`, `Body`, and `Proposals`.

---

## 7. On disk

```
.devman/
  units/            # tracked  — authored spec + final artifact, one file per unit
  stages/           # tracked  — stage definitions, prompts, schemas, generator_version
  dags/             # tracked  — dagu workflows
  proposals/        # tracked  — the backward-edge queue (§4.3)
  cache/            # ignored  — content-addressed stage outputs
  surface/          # ignored  — rendered markdown
  work/             # ignored  — fsdantic: the versioned KV, and one overlay per agent run

src/                # tracked, generated, marked -diff linguist-generated
```

**Units live twice, on purpose.** fsdantic's versioned KV is the *working*
store: it gives compare-and-set, per-agent overlays, and cheap reset, and it is
disposable. `units/` on disk is the *durable* store: it is tracked, diffable,
mergeable by jj, and it reaches anyone who clones. A unit is flushed from KV to
disk when its run settles. The KV never needs a backup, and the tracked files
never need a lock.

**`src/` is tracked and generated** — the codegen tax, chosen deliberately. The
drift check makes duplication safe: it can never become divergence. The residual
cost is honest: a body exists in git twice, and every body edit makes two diffs.

**Name collision, flagged not resolved.** `devman` exists, owns `.devman/` with
a different meaning, and 004 §14.2 records `fsdantic` still carrying an older
`.devman/` shape. My reading: this *is* devman, grown from compiling developer
assets to compiling the library. If so, 004 is the parent charter and this
supersedes its §5.3. If not, the directory needs a new name first.

---

## 8. The factory floor

Dagu orchestrates, devenv executes.

| Workflow | Trigger | Concurrency | Agent? |
|---|---|---|---|
| `spec` | conversation ends, or a spec edit | one per unit | yes |
| `build` | a unit changes | fan out across units | yes |
| `render` | a unit's artifact changes | fan out | no |
| `ingest` | `src/` changes | per file | no |
| `read` | commit, scoped to `affected_ids` | fan out | summaries only |
| `surface` | either end changes | fan out | no |

Four of six are deterministic. Agents run in `spec`, `build`, and summary
generation only. `read` is v2 (§11.1); `affected_ids` arrives with tyo3.

**Loop-breaking is mandatory, not an optimisation.** `render` writes `src/`;
`src/` changing triggers `ingest`; `ingest` writes a unit; a unit changing
triggers `render`. That is a live cycle between two workflows in the table
above, and §4.3's stratification does not cover it — `ingest` is structurally a
backward edge that exists because a human may edit `src/`.

Break it with a generation token, not a lock. `render` records the content
hashes it just wrote to `.devman/build/generation.json`. `ingest` skips any file
whose hash matches. Stateless, no deadlock, no ordering assumption. **`ingest`
is an input channel, not a reaction:** it may only fire for a change the factory
did not make.

**Cost control is not optional at this fan-out.** One spec edit can reach
hundreds of units. dagu bounds it — queues, per-DAG concurrency, and a
`max_concurrent_agents` semaphore, which cairn already demonstrates. Add a
per-run agent budget on top, and **log what was dropped**: a silent cap reads
as full coverage. When tyo3 lands (§11.1), `precision = container | method`
narrows the affected set further and `serving = stale` lets slow producers
publish late without blocking.

---

## 9. What it refuses to do

| Refuses to | Because |
|---|---|
| Let an agent block a build | a stochastic gate fails open; it costs autonomy and buys nothing |
| Let a derived fact become a unit field | your spec would erode into a description of your own code |
| Let any workflow trigger backward | termination is by construction, not by hope |
| Recompute a cached stochastic result | re-running would re-decide, and the codebase would churn |
| Lock a unit for an agent | it would serialize the factory |
| Silently accept an edit to generated structure | that is drift, and it makes the build a lie |
| Ask you to approve each change | verification gates; approval is ceremony |
| Let an agent write `src/` directly | one deterministic owner renders it; two writers reopen every problem §3.1 closed |
| Store an editor edit in a derived field | it would be reverted by the next re-derivation, silently. Promote it (§5.1) |
| Pin a derived field against regeneration | pins accumulate, and each one makes the spec a little less true |
| Read a green build as proof of correctness | it is proof only for the behaviours `examples` pinned (§10.3) |
| Push, publish, or reach the network | the one hard boundary |

---

## 10. The riskiest claims

### 10.1 The reactive graph terminates and converges

> **With N workflows reacting to each other's events, the system reaches
> quiescence after a bounded number of steps, and reaches the same state
> regardless of scheduling order.**

Termination is arguable from §4.3 — a strict DAG cannot cycle. **Convergence is
not.** Two agents committing in different orders can leave different states, and
nothing yet proves otherwise.

**The experiment.** Build the smallest real pipeline — three stages, twenty
units. Fire fifty concurrent edits in randomized orders. Measure: does the
system quiesce, how many steps, and is the final state identical across orders?

**Isolate ordering from stage randomness with a warm cache, not a repeat run.**
Repeating one ordering only proves the cache works. Run the *first* ordering to
populate the cache, then run every other ordering against that warm cache — all
stages are now effectively deterministic, so any divergence that remains is
caused by scheduling order alone. Also record the cache hit rate (§3.2): a low
rate means the input key is wrong and §4.2 is decorative.

*Fails if:* it does not quiesce, or orderings diverge. Either means the trigger
graph needs a barrier, and the factory gets slower than the design promises.

### 10.2 A model-owned codebase survives ordinary editing

> **Round-tripping holds, including refactors that cross unit boundaries.**

**The experiment.** Ingest one module into units, render, and **assert
byte-identity with the original**. Then replay the repo's real history commit by
commit, ingesting and re-rendering each.

| Rate | Fails if |
|---|---|
| Byte-identity on first ingest | anything under 100% — the render is not a function |
| Clean ingest (diff maps into body slots) | low; real edits routinely hit generated structure |
| Refactor survival across files | low; **this is the one that kills the design** |
| Unit churn vs file churn | far above 1:1; the unit boundary is wrong |
| Collation stability | *demoted by §5.2* — a structural diff makes reordering a zero-change. Measure it, but it no longer kills the design |

*Kill criteria.* Byte-identity under 100% stops the project. Low refactor
survival means bodies come out of the models — retreat to skeleton-only
templates with bodies spliced in `src/`, which stays available on purpose.

**A fourth claim, unproven and cheaper to test later:** that passing the previous
cached output into a stage stops churn when a spec changes (§4.2).

### 10.3 The gate reaches exactly as far as `examples` do

`test` is derived, so code and tests descend from one spec through one class of
model. Left alone, a passing suite proves the two agents agreed with each other.

**The failure, concretely.** The spec says *"Cache entries expire after 5
minutes."* You meant five minutes from **write**. Both agents read it as five
minutes from **last access** — a sliding TTL, a common default and an entirely
reasonable reading of that sentence. The test asserts sliding behaviour; the
body implements it. Typecheck, lint, and tests all pass. Every deterministic
gate says yes, and your session cache never expires for an active user.

**Why hiding the body from the test agent does not fix it.** It stops the test
copying the implementation, which matters. It creates no independence: both
channels still share one spec, one set of weights, and one tendency to resolve
an ambiguity the same way. That is **correlated failure, not verification** —
protection against transcription error, none against interpretation error, and
interpretation error is the one that bites.

**The fix — `examples`, authored (§3.1):**

```toml
spec = "Cache entries expire 5 minutes after they are written."
examples = [
  "set('k','v') at t=0; get('k') at t=299 → 'v'",
  "set('k','v') at t=0; get('k') at t=301 → None",
  "set('k','v') at t=0; get('k') at t=200; get('k') at t=301 → None",
]
```

The third line does all the work. It is the one assertion that separates
wall-clock from sliding, it costs about eight seconds to write, and neither
agent chose it. The test agent must now emit an assertion that fails if the body
slides the TTL, and a failure carries real information.

Writing every test yourself would give a true oracle and take back most of the
delegation. Examples are the cheap majority of the benefit, written in the same
breath as the spec. This is the first interrogation's idea — *a test is a claim
precise enough to run* — at a price worth paying.

**The bound, stated rather than implied.** Concurrency, performance, and "does
this API feel right" resist example expression. Those behaviours stay unjudged.
**The gate is exactly as strong as the examples you wrote, and no stronger.**
Do not read a green build as more than that.

---

## 11. Open

### 11.1 What v1 cuts — decided

Both riskiest claims (§10) are testable with **no reading half at all**. So v1
is three tools, not six:

| In v1 | Out, and when it returns |
|---|---|
| **fsdantic** — unit store, CAS, overlays | — |
| **templateer** — typed handoffs, final render | — |
| **dagu** — the factory floor | — |
| | **tyo3** — when the reading half needs semantic references. `pydantree-sitter` covers structure first: symbols, signatures, imports, docstrings, no execution. |
| | **cairn** — when agent-written code must run sandboxed. Needs a verification-gated accept path first (§11.2). |

Cutting the reading half also cuts the surface's `Called by` block, which makes
§6 smaller: `Spec`, `Body`, `Proposals`. That is enough to prove or kill the
design.

### 11.2 Cairn conflicts with the autonomy requirement

Cairn's principle 1 — *"copy-on-write over merge complexity"* — is this
design's instinct, already shipped. Its principle 4 is not: *"Human authority
over automation. Only humans finalize what enters the working tree,"* with every
accept revalidating under a project lock.

That is an approval gate on every integration, and kickoff §5 deleted exactly
that. Adopting cairn unchanged would reintroduce the failure the whole project
exists to avoid.

Open: does cairn grow a verification-gated accept — `devenv` checks decide, no
human — or does this design use only its sandbox and not its integration model?
The second is cheaper and does not require changing someone else's tool.

### 11.3 Still open

**The name.** Not a ladder — there are no levels. It is a factory with a
compiler at the end and an analyser after it. Waits on §7's `.devman/` question.

**Are stage pipelines fixed or open?** §4.3 assumes a fixed stratification. A
genuinely open set of reactive workflows is more powerful and is where
termination dies. Lean: fixed kinds, arbitrary fan-out within a kind.

**Unit granularity — resolved by nesting (§3.1),** not by choosing a level.
What remains open is narrower: whether a module unit may carry an explicit
ordering override when the deterministic rule reads badly. Lean: no, until a
real file proves it necessary.

**Non-Python.** tyo3 reads Python only. Other languages can still be rendered —
templateer does not care — but get no references, links, or dependency facts.
Lean: render everything, read only Python, and say so plainly.

**Does the surface need a writable `Body` at all?** You can already edit `src/`.
If that is always nicer, `Spec` is the only writable region. §6 and §11.1
currently ship it writable; that is the status quo, not a decision. Lean: make
it read-only, and see if you miss it.

**Tombstone retention.** §5 tombstones a unit whose `def` was deleted, and
promises it is recoverable. Nothing says for how long, where it lives, or how
you get it back. fsdantic supplies the primitive. Lean: durable in `units/`,
never auto-purged, listed by a `doctor` command with its age — the same
treatment spike E's quarantine earned, and for the same reason. Spike E.2
measured that detached content almost never returns on its own, so the value is
that nothing is lost, not that anything heals.

**Conversation as an input channel.** A chat with an agent is an event source
like a file save. Where does the transcript live, and is it a durable input or
disposable once its spec is written? Lean: durable, and linked from the unit.

---

## 12. What earlier readings got wrong

Recorded so they are not re-derived.

**Reading one — a claim ledger.** Built verdicts and complaints over an authored
codebase. Internally sound, wrong system: it observed code it did not own, so it
could only ever report.

**Reading two — templates as leverage.** Treated templateer as the generator and
asked whether a template could compress N artifacts into one shape. Wrong
question. templateer is a **type system for agent output**; its determinism buys
the drift check and the round trip, not leverage.

**Reading three — tyo3 as the concurrency substrate.** Proposed MVCC snapshots
and revision-pinned commits for parallel agents. Correct in mechanism and wrong
in tool: fsdantic's versioned KV already does compare-and-set with typed
conflicts, and the write target is a keyed record rather than a tree, so the
problem MVCC solves is mostly absent. tyo3 stays useful for reading (§11.1),
which is a different job.

What survived all three corrections: byte-determinism (§3.2, §5), tyo3 as the reading
engine (§3.3), the anti-ratchet rule (§3.3), and the refusal to price every
operation identically (§9).

### 12.1 Retired vocabulary

These terms are dead. Do not reuse them, and do not borrow them as metaphors —
a retired word carries its old meaning back in with it.

| Retired | Came from | Say instead |
|---|---|---|
| `chrome` | 004 region kinds | nothing — the route is deleted (§6). For round-trip bookkeeping, say **span marker** |
| `rung`, `ladder`, `level` | the original kickoff | **unit**, **stage** — there are no levels |
| `mirror` | 004 §5.3 | **reading** (§3.3) — it analyses, it does not project |
| `claim`, `verdict` | the first reading (§12) | **unit**, **spec** |
| forced / free decision | the second reading | nothing — content-addressing subsumed it (§4.2) |
| `derived` / `authored` as *region* kinds | 004 §6.1 | keep them as **field** kinds on a unit (§4.4); they no longer describe regions of a surface |

The last row is the trap: two of the three 004 words survive with a narrower
meaning, and only the third is gone. Check which sense is in play before
reaching for one.
