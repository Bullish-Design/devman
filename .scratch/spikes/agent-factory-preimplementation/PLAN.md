# Agent factory pre-implementation investigation plan

Date: 2026-08-20

## Objective

Finish the evidence phase for project `005-agent-factory`. Do not implement the
production factory. End with one verdict from the kickoff prompt.

## Fixed boundaries

- Work only under `.scratch/spikes/agent-factory-preimplementation/`, except for
  the final evidence update to `.scratch/spikes/SPIKES.md`.
- Treat edited source and the last accepted store as immutable after a failed or
  ambiguous operation.
- Use disposable copies for corruption, migration, interruption, and replay.
- Do not use the network, provider credentials, or a hosted model without new
  authorization.
- Do not start concurrency stress tests. Define their entry criteria and matrix.
- Run Python, test, lint, formatting, and Git commands through
  `devenv shell -- ...`.

## Environment and command form

The repository has no executable `devenv.sh`. Use this form:

```text
devenv shell -- <command>
```

`gitman` is not present in the pinned shell. Use Git through the devenv shell as
the documented fallback. The user authorized regular commits and pushes on
2026-08-20.

Each probe run receives a new directory:

```text
.scratch/spikes/agent-factory-preimplementation/artifacts/<UTC timestamp>-<phase>/
```

Each directory records the resolved command, versions and commits, full output,
exit status, inputs, hashes, and the first failure boundary.

## Phase 0 — baseline and control documents

Hypothesis: the prior evidence and current sibling revisions are sufficient to
state the unresolved risks without changing production code.

Accept when the plan, issue register, research report, decision record, and
baseline artifact exist. Reject when a required source or revision cannot be
identified.

Status: complete. The first baseline import failed because fsdantic is not
available in this devenv. The failure and successful bounded retry are saved.

## Phase 1 — truth model and authored boundary

Hypothesis: every source element can have one explicit owner, and exact-source
records can remain a declared bootstrap mechanism instead of the semantic truth.

Probe requirements, examples, signatures, bodies, imports, comments, layout,
and tests at module, class, function, method, statement, and fragment scope.

Accept when the ownership table has no dual-authority field and gives a bounded
bootstrap exit. Reject when ordinary edits require two accepted owners.

Status: pending.

## Phase 2 — Templateer raw Python boundary

Hypothesis: Templateer can represent a typed raw Python fragment without
weakening normal quoted-string escaping.

Trace model validation, finalization, rendering, parser validation, audit, and
formatting. Reproduce current escaping. Compare a raw fragment type, an emitter,
section rendering, `language: text` plus validation, and an external renderer.

Accept when one executable contract preserves fragment bytes, rejects invalid
syntax, keeps ordinary strings escaped, composes deterministically, and provides
actionable errors. Reject Templateer at this boundary if no option meets all
conditions without a global bypass.

Initial commands:

```text
devenv shell -- python .scratch/spikes/agent-factory-preimplementation/templateer_probe.py --artifacts <fresh-directory>
devenv shell -- python -m unittest discover -s .scratch/spikes/agent-factory-preimplementation -p 'test_*.py'
devenv shell -- ruff check --exclude artifacts .scratch/spikes/agent-factory-preimplementation
devenv shell -- ruff format --check --exclude artifacts .scratch/spikes/agent-factory-preimplementation
```

Status: complete. Current Python rendering fails the fragment contract. A
source-only text template works with layered validation but creates a mixed-field
injection trap. Final Python assembly moves outside Templateer until the
first-class fragment contract exists.

## Phase 3 — semantic promotion and transaction state

Hypothesis: deterministic orchestration can bound promotion failures without
claiming unmeasured model quality.

Define the input, schema, context, allowed edits, retry policy, normalization,
maximum attempts, terminal states, and acceptance transaction. Use an
adversarial deterministic provider for every required edit and failure class.

Accept when success, rejection, malformed output, non-convergence, stale input,
and rollback preserve all promised bytes. Model-quality remains `unknown` unless
an authorized local provider and blinded corpus become available.

Status: pending.

## Phase 4 — Python support corpus

Hypothesis: the supported Python subset can preserve 100 percent of bytes, and
the parser can reject every unsupported construct before mutation.

Build the categorized corpus from Section 4 of the kickoff prompt. Include
non-ASCII text and compare UTF-8 byte offsets. Classify each case as preserve,
own, collate, or reject.

Accept when every supported case has byte identity and every unsupported case
has a pre-mutation diagnostic with the best available owner.

Status: pending.

## Phase 5 — durable identity, imports, and ordering

Hypothesis: automatic identity continuity is safe only for uniquely supported
evidence, while ambiguous structural change stops before mutation.

Exercise rename, move, copy, delete-and-recreate, reorder, split, merge,
extraction, inlining, duplicate bodies, overloads, nested names, and competing
targets. Exercise conditional, relative, wildcard, side-effect, and local
imports plus dependency cycles.

Accept when the report measures false matches, missed matches, ambiguity, and
unrelated churn. Define automatic, proposal, and human-choice boundaries.

Status: pending.

## Phase 6 — persistence, determinism, and recovery

Hypothesis: one explicit state machine can prevent accepted-store/source split
brain across every single-process interruption point.

Probe parse, validation, render, formatter, test, stale-token, partial write,
process interruption, and practical disk-full cases. Inspect fsdantic's
compare-and-set, best-effort transaction, and staging-swap limits. Repeat cold
and warm renders across processes and traversal orders.

Accept when each transition has a recovery rule and fresh evidence. Do not
claim atomicity beyond the tested filesystem and backend boundary.

Status: pending.

## Phase 7 — real history, migration, and performance

Hypothesis: representative local histories and realistic trees bound adoption
cost and editor latency.

Replay first-parent samples from multiple local Python repositories. Record the
sampling reason and exclusions. Measure ingest, diff, validation, render, write,
memory, store growth, and artifact growth at small, medium, and large sizes.

Accept when migration review burden, rejection rate, identity ambiguity, and
latency budgets follow from measurements rather than post-hoc thresholds.

Status: pending.

## Phase 8 — security, developer experience, and compatibility

Hypothesis: hostile input cannot cross parsing, path, command, logging, or
execution boundaries silently, and ordinary repository operations have a clear
recovery path.

Threat-model all inputs named in the kickoff prompt. Walk edit failures, branch
operations, formatter hooks, adoption, disable, repair, export, and removal.
Build the dependency/API and platform matrix from local metadata and source.

Accept when every trust boundary has validation, redaction, ownership, and a
safe failure mode. Mark untested platforms and supply-chain facts explicitly.

Status: pending.

## Phase 9 — synthesis and concurrency prerequisites

Reconcile every issue. Separate facts, inferences, recommendations, and
unknowns. Supply concept edits, support tables, transaction diagrams, recovery
tables, dependency contracts, implementation gates, and the later concurrency
matrix. Rerun all probes from fresh fixtures before the verdict.

Status: pending.
