---
title: "Kickoff — the ladder (working name)"
status: inbox
source: Paseo chat 2026-08-19/20 — devman 004 interrogation, spike E, then a course correction
captured: 2026-08-20
owner: andrew
output_type: project
---

# Kickoff — expand and condense, as a system

> Paste this into a clean session. Read it, then **interrogate the idea before
> designing anything.** The point of this session is to find the *essence*: the
> smallest, cleanest set of ideas that generates everything else. A big design
> is a failed one.

---

## 1. What I want

I want to **grow a codebase from the top down.**

I write a thought. Agents **expand** it into detail — spec, then code. Agents
**condense** detail back up into something I can read and reason about. I stay
at the conceptual level. Agents handle the nitty-gritty. Both directions run
continuously, so the levels stay in sync as either end moves.

```
        my intent          ← I work here
   condense ↑  ↓ expand
       design / spec
   condense ↑  ↓ expand
          code             ← agents work here
```

Call the levels **rungs** and the whole thing **the ladder**, as working terms
only. Naming is an open question, not a decision.

**This must be autonomous.** I do not want to approve each change. If a system
needs me in the loop for every step, it has failed at its main job.

---

## 2. Rules for this session

1. **Interrogate first.** Surface hidden assumptions, contradictions, undefined
   or overloaded terms, scope boundaries, and the single riskiest unknown.
   Argue with the idea. Do not restate it back to me.
2. **Ask the minimum set of decision-shaping questions**, then wait. Do not
   plan or write code until I answer.
3. **Optimize for essence, not coverage.** Prefer three concepts that compose
   over ten that enumerate. If two mechanisms rhyme, they are probably one
   mechanism.
4. **Delete before you add.** For every part you propose, say what happens if
   it is removed. If nothing bad happens, remove it.
5. **Do not add ceremony.** See §5 — this is the specific way the last attempt
   failed.
6. Write in Simplified Technical English. Short sentences, active voice, one
   idea per sentence, no filler.

---

## 3. What is settled — do not re-derive

**The safety model.** The gate is **verification, not approval**. Agents run
free locally; `devenv` checks (lint, typecheck, test) decide whether work
lands. Failed work parks with its failure attached. `jj` is the undo. The only
hard boundary is outbound: do not push, do not publish.

**The tools that exist and work.** All are mine, all are local, all are proven:

| Tool | What it actually gives you |
|---|---|
| `pydantree-sitter` | source → typed rows + byte spans, via tree-sitter. Declare a Pydantic model, get checked extraction. **No unparse** — writes are span splices. Reads any language, executes nothing. |
| `templateer` | validated Pydantic model → strict Jinja → byte-deterministic artifact. The LLM fills a model; it never writes the file. |
| `fsdantic` | async overlay filesystem: `merge`, `diff`, `preview`, `reset`, `tombstone`, `to_disk`. Durable, keyed by id. |
| `dagu` | machine-level workflow orchestration: DAGs, schedules, queues, retries, history. |
| `devenv` | reproducible environment + the canonical implementation of every primitive task. |
| `jj` | source identity, immutable revisions, cheap undo, per-change review. |
| `watchexec` | file-change detection. Nothing more. |

Boundary rule from the family: **Dagu orchestrates, devenv executes.** One
canonical implementation per task. Never hand-roll `PATH` or reach for a stray
`.venv` — run under `devenv shell`.

**Measured facts (spike E, 2026-08-20,
`Projects/devman/.scratch/spikes/SPIKES.md`).** These cost a day; do not
re-measure them:

- Keying prose to `<relpath>::<dotted.symbol>` **works**. Three of four repos
  showed zero anchor failures across their whole history. Every orphan was
  prose on genuinely deleted code.
- A rename bridge is needed and cheap: `git -M` recovered 334 of 342 real
  failures; name-only symbol matching cleared 360 more with **0 ambiguous** —
  but only on public source symbols. Over tests it collided 978 times.
- **Quarantine does not heal.** Only 4–9% of detached annotations ever
  re-attach on their own. Never rely on a revert to recover something.
- A deliberate reorganization detaches most annotations and no bridge fixes it.
  The subject was renamed on purpose. That is a bulk chore, not data loss.

---

## 4. Prior art — challenge it, do not inherit it

There is a full charter for a related-but-different product at
`Projects/devman/.scratch/projects/004-unified-charter/CONCEPT.md`. **Read it
for what it learned, not for what it decided.** It solves a *narrower* problem:
project a codebase into readable markdown and route edits back. It treats
source as a fixed input that prose describes.

The ladder inverts that. Here, markdown is often *upstream* and code is the
artifact that grows. So 004's core framing does not transfer.

Ideas from it that may or may not survive, listed so you can attack them:

| Idea | Load-bearing, or incidental? |
|---|---|
| No emitted surface is authoritative; an edit to one is a change request against an input | Probably essential. Test it against the ladder. |
| Regions typed `derived` / `authored` / `chrome` route edits deterministically | Derived twice independently for the mirror. May not survive a directional ladder. |
| Anchors bind annotations to symbols across regeneration | Measured sound. But the ladder is many-to-many, and anchors were 1:1 with files. |
| Staleness markers — every annotation carries the source hash it was written against | Probably essential. A rung that lies is worse than a missing rung. |
| Convergence guard — re-render and assert it reproduces the edit | The one automatic correctness test in the design. Likely generalizes. |
| Approval gates on every route | **Wrong. Deleted.** See §5. |
| One markdown file per source file | Almost certainly wrong for a ladder. |

---

## 5. How the last attempt failed — do not repeat it

The previous design priced three very different operations identically, and put
a human approval gate on all of them. Two of the three touched only a
disposable, version-controlled draft store. The gate bought nothing and
destroyed the autonomy that was the whole point.

**The lesson: price each operation by what it actually risks and how reversible
it is.** Version control is the undo. Ceremony is not safety.

Watch for the same mistake in new clothes: a uniform mechanism applied across
operations whose risks differ by orders of magnitude.

---

## 6. The questions I think decide the shape

Do not answer these in order. Find which ones are actually the same question.

**Structure**

- What is a rung? Are the levels fixed and named, or emergent? Is a rung a
  document, a set of files, a scope, or just a resolution?
- Is code the bottom rung? Or are tests, or observed behaviour, below it?
- Granularity is the structural problem. One thought spans many files; one file
  serves many thoughts. The mirror was 1:1 and that made it easy. The ladder is
  many-to-many. What is the unit?

**The mathematics**

- **Expand and condense are not inverses.** Expansion adds decisions that were
  not in the rung above. Condensation discards them. So round-tripping cannot
  be identity. What equivalence *should* hold, and how do you test it?
- When an agent expands "add caching" into code, it picks a library, an
  eviction policy, a key format. That is new information. **Where does it
  live?** If nowhere, the next expansion re-decides differently and the system
  thrashes. If somewhere, is that a new rung, or an annotation on the edge
  between rungs? I suspect this is the essence of the whole problem.

**Authority and drift**

- Two rungs are edited independently and now disagree. What happens? Is there a
  winner, a merge, or a third thing?
- How do you know a rung is stale relative to the one below? Spike E answers
  this for code. What anchors an intent to a spec?
- The dangerous failure: an agent expands my thought into subtly wrong code;
  later another agent condenses that code into a summary that reads exactly
  like what I meant. The error is two rungs down and invisible from where I
  work. Approval would not catch it — the diff looks fine. What does?

**Scope**

- Does the ladder replace the repo, sit beside it, or generate it?
- Is this devman, or its own tool? Argue it either way.

---

## 7. The reduction pass

After the interrogation, before any architecture, answer these:

1. State the whole thing in **one sentence**. If it needs two, it is not one
   idea yet.
2. What is the **smallest set of primitives** from which the rest follows?
   Name them. Three is a good target.
3. **What is the durable artifact?** If the answer is "none," this is just
   prompting an LLM repeatedly and there is no system here. Say so plainly if
   that is where the reasoning leads.
4. What is the **one thing that must be true** for this to work at all? Design
   the cheapest experiment that could prove it false, the way spike E did.
5. What does this **refuse to do**? A tool with no non-goals has no shape.

---

## 8. Deliverable

Interrogation and questions first. Then, after I answer: a concept document
that a fresh reader could build from, holding the one-sentence statement, the
primitives, the non-goals, the riskiest claim, and the experiment that tests
it. No build order until the concept is settled.

Working directory `/home/andrew/Documents/ideas` unless the concept clearly
belongs in a project repo. Nothing is committed without me asking.
