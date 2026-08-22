# Kickoff prompt — close the agent-factory pre-implementation investigation

You are working in the `devman` repository on project `005-agent-factory`.
Act as a senior systems investigator, language-tooling engineer, and skeptical
design reviewer. Your task is to finish the evidence-gathering phase before any
production implementation begins.

The objective is not to confirm the concept. It is to find the places where the
concept could lose source, misidentify ownership, become nondeterministic, hide
an unbounded migration cost, or fail in ordinary development. Challenge every
important assumption and leave a decision-quality record of what is proven,
what is bounded, what must change, and what is still unknown.

No investigation can prove that there are literally no possible issues. Reach
high confidence by maintaining an explicit issue inventory, testing the full
support boundary, and naming every residual unknown. Do not use phrases such as
"looks safe" or "probably fine" without evidence and a stated confidence level.

## Start here

Read these completely before planning or changing files:

1. `AGENTS.md` and the standing `my-ai` skill.
2. `.scratch/projects/005-agent-factory/ORIGINAL_KICKOFF.md`
3. `.scratch/projects/005-agent-factory/CONCEPT.md`
4. `.scratch/projects/005-agent-factory/IDEAS_WORKFLOW.md`
5. `.scratch/projects/005-agent-factory/KICKOFF_PROMPT.md`
6. `.scratch/spikes/SPIKES.md`, especially Spikes E and F.
7. `.scratch/spikes/agent-factory-round-trip/PLAN.md`
8. `.scratch/spikes/agent-factory-round-trip/RESEARCH_REPORT.md`
9. The round-trip prototype, tests, fixture, templates, and preserved artifacts
   under `.scratch/spikes/agent-factory-round-trip/`.
10. `.scratch/projects/004-unified-charter/CONCEPT.md` and
    `.scratch/spikes/anchors.py` where identity and mirror behavior overlap.

Then inspect the relevant local source and tests in sibling repositories,
especially `pydantree`, `templateer_v2`, and `fsdantic`. Use their actual APIs
and repository history as primary evidence. Do not infer behavior from package
names, old notes, or generated documentation when source and tests are
available.

Follow all repository command-routing rules. In particular, run project Python,
test, lint, formatting, and Git commands through this repository's
`devenv shell -- ...` environment. Never use `PYTHONPATH` or execute a sibling
repository's interpreter. Do not install dependencies, access the network, use
a hosted model, create a pull request, commit, or push unless the user explicitly
authorizes that action in the investigation session.

## Settled evidence to carry forward

Do not spend the session merely repeating the completed fixture spike. Recheck
its claims only when a broader case contradicts them.

The existing spike established, for its deliberately small Python fixture:

- 100% byte identity on initial ingest and render.
- deterministic repeated rendering and Ruff stability;
- localized body, signature, and docstring edits;
- stable add, recoverable delete, same-file method rename, and cross-file move;
- correct rejection ownership for an unsupported collated import edit;
- source/store preservation plus a proposal artifact after failed promotion;
- green independent unit, lint, format, and ten-case scenario runs.

It did not establish production viability. Two known gaps remain:

1. Templateer does not yet expose a demonstrated, validated raw-Python-fragment
   contract. The prototype rendered with `language: text` and ran Ruff
   afterward because `language: python` escapes strings for quoted positions.
2. The deterministic source-backed promotion test double proves transaction and
   convergence mechanics, not that a semantic model can reliably update the
   authored specification and examples.

Treat exact source captured in a record as a bootstrap/losslessness mechanism,
not automatically as proof of a meaningful semantic specification. Detect and
name any design that merely moves source text into a database while claiming
the specification became the durable truth.

## Hard boundary

This is an investigation, not production implementation.

You may add minimal disposable probes, fixtures, replay scripts, and tests under
`.scratch/spikes/agent-factory-preimplementation/`. You may make the smallest
environment-only adjustment required to execute an approved local probe, but
you must explain and verify it. Do not build the watcher, editor integration,
production store, production generator, migration command, or concurrency
system. Do not quietly repair a sibling library as part of the investigation.
Record a required upstream change with an executable reproducer instead.

Do not start concurrency stress testing until the single-process ownership,
transaction, persistence, and generation-token semantics are understood. You
must still investigate concurrency requirements and define the later test
matrix.

Never overwrite an accepted source file or accepted store after a failed or
ambiguous experiment. Run destructive migration and corruption experiments only
on disposable copies. Preserve failure evidence.

## Investigation method

Begin by creating:

- `PLAN.md` — phases, hypotheses, commands, acceptance criteria, and status;
- `ISSUE_REGISTER.md` — one row per risk or unanswered question;
- `RESEARCH_REPORT.md` — dated narrative, evidence, and conclusions;
- `DECISION_RECORD.md` — final architecture decisions and implementation gates;
- `artifacts/<UTC timestamp>/` — raw logs, environment/version data, fixtures,
  diffs, hashes, timing data, and failure proposals.

Every issue in the register needs a stable identifier and these fields:

- subsystem and invariant at risk;
- concrete failure mode;
- triggering construct or workflow;
- likelihood, impact, and detectability;
- current evidence and reproducer path;
- status: `proven-safe`, `bounded-risk`, `blocker`, `deferred-with-owner`, or
  `unknown`;
- proposed mitigation and where it belongs;
- residual risk, confidence, and the evidence needed to change the status.

For each phase, use the loop:

1. State a falsifiable hypothesis and exact acceptance/rejection criteria.
2. Inspect local primary sources and existing tests.
3. Build the smallest probe that can disprove the hypothesis.
4. Record the command, environment, exit status, output, and before/after hashes.
5. Classify failures before changing the probe.
6. Make only a minimal investigation fix when needed.
7. rerun from a fresh disposable fixture and preserve both failed and successful
   evidence.
8. Update the issue register and explain what remains unproven.

When exact semantic equivalence is undecidable, define observable invariants
and an explicit human-review boundary. A formatter-clean result is not evidence
of semantic preservation.

## Questions that must be closed

### 1. Truth model and authored boundary

- Precisely define what humans author, what a model proposes, what is accepted
  truth, what is derived output, and what is disposable cache.
- Determine whether requirements, examples, signatures, bodies, imports,
  comments, and layout have one owner or multiple owners. Reject ambiguous
  dual-authority fields.
- Determine the smallest useful typed unit. Test whether module-, class-,
  method-, function-, statement-, and fragment-level ownership create
  unacceptable coupling or bookkeeping.
- Prove that examples can serve as an executable correctness gate, or state the
  narrower claim they actually support. Include missing, weak, stale, and
  overfitted examples.
- Establish when exact-source fallback is legitimate and when it defeats the
  concept. Define an exit path from bootstrap records to meaningful authored
  specifications.
- Find contradictions between the concept, workflow, spike behavior, and the
  actual capabilities of the three sibling libraries.

### 2. Templateer raw-source boundary — current blocker

- Trace the exact Templateer parse, validation, escaping, rendering, and
  formatting path from local source and tests.
- Reproduce the `language: python` escaping failure with the smallest fixture.
- Determine whether Templateer can safely support a typed, validated raw-source
  fragment without weakening escaping for ordinary string fields.
- Compare at least these options: a first-class raw fragment type; a
  language-aware emitter/serializer; section-level rendering; `language: text`
  plus parser validation and Ruff; or a renderer outside Templateer.
- For each option, analyze syntax validation, injection risk, composition,
  diagnostics, deterministic formatting, backward compatibility, and ownership
  of the change.
- Produce an executable contract test that a future upstream implementation
  must pass. End with one recommended contract or an explicit decision to remove
  Templateer from this boundary.

### 3. Semantic promotion and convergence — current blocker

- Specify the model input, output schema, context boundary, examples, allowed
  edits, validation, retry policy, and acceptance transaction.
- Separate deterministic orchestration guarantees from stochastic model-quality
  claims.
- Exercise body, signature, behavior, docstring, import, rename, move, split,
  merge, and delete proposals with an adversarial deterministic provider. Cover
  malformed output, partial output, hallucinated units, stale context,
  contradictory examples, timeout, cancellation, and repeated non-convergence.
- If a real local model/provider is already available and authorized, measure
  semantic promotion quality on a blinded corpus. Otherwise produce the exact
  experiment protocol and mark model-quality conclusions `unknown`; do not use
  network or credentials without permission.
- Define the convergence guard mathematically: compared artifacts, normalization
  rules, maximum attempts, accepted terminal state, and failure artifact.
- Prove that failure preserves the user's edited source and last accepted store
  byte-for-byte. No failed proposal may silently become truth.
- Quantify false acceptance and false rejection, not just successful examples.

### 4. Python syntax, trivia, and ownership coverage

Build a categorized corpus and a support matrix. Include, where applicable:

- shebangs, encoding cookies, module docstrings, future imports, `__all__`, blank
  lines, mixed newline endings, trailing whitespace, and missing final newline;
- comments before, between, inside, and after definitions; type comments;
  `noqa`, formatter, coverage, and type-checker directives;
- decorators, stacked decorators, multiline signatures, positional-only and
  keyword-only parameters, annotations, defaults, overloads, and generics;
- synchronous, asynchronous, generator, async-generator, nested, and closure
  functions; lambdas and comprehensions where ownership can be ambiguous;
- classes, nested classes, dataclasses, enums, protocols, properties, setters,
  static/class methods, metaclasses, descriptors, and decorated definitions;
- conditional definitions, platform/version guards, `TYPE_CHECKING`, `try`
  imports, and repeated symbol names in mutually exclusive branches;
- imports with aliases, relative levels, star imports, parenthesized imports,
  semicolon-separated statements, dynamic imports, and import side effects;
- pattern matching, exception groups, f-strings, walrus expressions, and the
  newest syntax supported by the repository's Python/parser versions;
- syntactically invalid but actively edited buffers and unsupported constructs.

For each category, decide whether the system preserves it, owns it, collates it,
or rejects it. Unsupported input must be detected before mutation, assigned to
the correct owner when possible, and preserved intact.

Determine whether AST plus byte spans is sufficient for every promised
invariant. Identify where a concrete syntax tree, tokens, or explicit trivia
records are required. Test UTF-8 byte offsets against non-ASCII source.

### 5. Durable identity and structural change

- Define identity independently from current path, symbol name, byte span, and
  body hash.
- Test same-file and cross-file rename, move, copy, delete-and-recreate,
  reorder, split, merge, extraction, inlining, and simultaneous edits.
- Include duplicate bodies, overloaded functions, repeated method names,
  identical helpers in different modules, nested definitions, and two plausible
  move targets.
- Measure false matches, missed matches, unrelated-unit churn, and ambiguity.
- Define when automatic continuity is safe, when a proposal is required, and
  when a human must choose.
- Reconcile this identity model with the anchor findings in Spike E without
  assuming that documentation anchors and model-owned source units need the same
  algorithm.
- Specify tombstone retention, reattachment, garbage collection, and audit
  semantics. Recovery must not resurrect intentionally deleted behavior.

### 6. Imports, dependencies, ordering, and collation

- Define ownership for module preamble, imports, constants, declarations,
  executable module statements, and epilogue.
- Test alias collisions, relative imports, `TYPE_CHECKING`, optional imports,
  wildcard imports, side-effect imports, local imports, circular dependencies,
  and conditional import blocks.
- Determine whether imports can be normalized or deduplicated without changing
  semantics. Treat order-sensitive imports as adversarial cases.
- Define a dependency graph for units and modules, including cycles, forward
  references, and cross-file moves.
- Prove deterministic assembly order and useful diagnostics when ordering is
  ambiguous or cyclic.

### 7. Persistence, transactions, and crash safety

- Design the accepted-store/proposal/source transaction as a state machine.
  Enumerate every interruption point.
- Probe parse failure, validation failure, render failure, formatter failure,
  test failure, disk-full simulation where practical, process interruption,
  stale generation token, and partial multi-file write.
- Specify atomic-write, fsync/rename, rollback, journal, and recovery behavior
  appropriate to the actual store backend. Do not claim atomicity beyond what
  was tested.
- Inspect whether fsdantic is suitable for versioned records, migrations,
  indexes, compare-and-swap, provenance, and proposal storage. Record gaps as
  upstream contracts rather than papering them over.
- Define schema versioning, generator versioning, migrations, downgrade policy,
  backup/restore, corruption detection, and forward compatibility.
- Ensure diagnostics and artifacts do not leak source that the repository would
  otherwise treat as sensitive.

### 8. Determinism, formatting, caching, and reproducibility

- Identify every input to generated bytes: records, template, renderer,
  ordering, environment, Python version, parser version, Ruff version, newline
  convention, locale, and generator version.
- Define cache keys and invalidation. Prove that unchanged semantic inputs do
  not trigger generation loops.
- Run repeated cold and warm renders and compare hashes. Include different
  process starts and traversal orders.
- Measure the effect of Ruff upgrades and configuration changes. Distinguish
  accepted canonical formatting from accidental formatter ownership.
- Test non-idempotent or oscillating promotion/render cycles and ensure they
  terminate safely with evidence.
- Specify provenance that is useful but does not inject timestamps or other
  nondeterminism into generated files.

### 9. Real-history replay and migration

- Replay representative first-parent histories from multiple local Python
  repositories, including calm periods and deliberate refactors. Document the
  sampling rationale and exclusions.
- On each accepted revision, measure clean ingest rate, byte identity, supported
  syntax, unit churn, file churn, identity continuity, ambiguous matches,
  rejected constructs, render stability, and recovery behavior.
- Test initial adoption of a nontrivial existing repository. Estimate the human
  review burden and identify cases that cannot be bootstrapped safely.
- Define migration preview, acceptance, rollback, and repeated-run idempotence.
  The original tree must remain recoverable and untouched until acceptance.
- Investigate repository scale, generated files, vendored code, notebooks,
  namespace packages, monorepos, and mixed Python-version constraints.

### 10. Performance and operability

- Measure ingest, diff, promotion orchestration, validation, render, and write
  separately over increasing file/unit counts.
- Capture CPU, memory, store growth, artifact growth, cold/warm latency, and the
  amount of source/model context needed per ordinary edit.
- Identify full-tree operations hiding behind unit-level language.
- Define budgets for editor-save latency, batch migration, CI validation, and
  recovery. If the concept cannot meet an interactive budget, define a coherent
  asynchronous user experience rather than hiding the delay.
- Specify observability: structured events, correlation/generation IDs,
  redaction, actionable diagnostics, and how a user finds the rejected unit and
  preserved proposal.

### 11. Security, trust, and supply chain

- Threat-model hostile repository source, hostile template content, hostile
  model output, prompt injection in comments/docstrings, path traversal,
  symlinks, oversized input, parser denial of service, and command injection.
- Establish where generated Python is parsed, validated, formatted, tested, and
  executed. Generation must not imply execution.
- Analyze trust boundaries among devman, pydantree, Templateer, fsdantic, Ruff,
  model providers, editor processes, and Git hooks/CI.
- Check dependency licenses, maintenance status, supported-version ranges, and
  the reproducibility/pinning story from local metadata. Network research, if
  later authorized, must use primary upstream sources and record access dates.
- Define secret handling and redaction for prompts, proposals, logs, stores,
  caches, and artifacts.

### 12. Developer experience and repository integration

- Walk through ordinary edit, parse error, rejected ownership, failed promotion,
  successful promotion, rename, move, merge conflict, branch switch, rebase,
  formatter-on-save, and rollback from the user's point of view.
- Determine how the system avoids fighting editors, language servers, formatters,
  pre-commit hooks, Git operations, and external code generators.
- Resolve naming and layout conflicts around `.devman/` and obey the rule that
  workspace-specific editor configuration in templates belongs there.
- Define clean enable/disable, adoption, status, explain, repair, export, and
  removal paths. Removing the tool must not make source unrecoverable.
- Identify which failures can be automatic, which require a visible proposal,
  and which require a hard stop.

### 13. Platform, compatibility, and evolution

- Test or bound Linux/macOS behavior, path case sensitivity, symlinks, newline
  conventions, atomic rename assumptions, and filesystem watchers.
- Define supported Python, parser, formatter, Templateer, pydantree, and
  fsdantic versions. Identify syntax-version skew and upgrade behavior.
- Consider Git worktrees, submodules, sparse checkouts, branch switches, rebases,
  and merge conflict markers.
- State the minimum APIs required from each sibling project, their ownership,
  and whether the agent-factory can degrade safely when one is unavailable.

### 14. Concurrency prerequisites

Do not run the concurrency spike yet. Instead:

- define generation-token and compare-and-swap semantics;
- enumerate editor/watcher, two-editor, two-process, branch-switch, and stale
  proposal races;
- define lock scope, lock ordering, cancellation, crash recovery, and the
  invariants a later concurrency spike must prove;
- list the exact unresolved single-process questions that block meaningful
  concurrency testing.

## Minimum evidence bar

The final recommendation may not rely only on the handcrafted fixture. At a
minimum, produce:

- a source-supported Templateer boundary decision and executable contract test;
- a promotion state-machine test suite covering success, rejection, malformed
  proposals, non-convergence, stale input, and rollback;
- a categorized Python support corpus with explicit pass/reject behavior;
- adversarial identity cases with measured false/ambiguous matches;
- crash/partial-failure simulations on disposable multi-file fixtures;
- deterministic hash evidence across fresh processes and varied traversal order;
- representative local history replay with transparent sampling and metrics;
- a performance baseline on small, medium, and realistically large local trees;
- a security/threat model and dependency/API compatibility matrix;
- an explicit list of all cases not tested and why.

Use 100% preservation as the bar for supported constructs. A construct may be
declared unsupported and safely rejected, but it may not be silently changed or
dropped. For failed or ambiguous operations, require byte-identical preservation
of the user's source and last accepted store. Derive and justify numeric budgets
for performance and identity ambiguity rather than choosing convenient numbers
after seeing results.

## Final synthesis

Before declaring the investigation complete:

1. Reconcile every issue-register entry; no blank status or owner is allowed.
2. Separate facts, inferences, recommendations, and unknowns.
3. List every concept section that must change and provide replacement wording
   or a precise edit instruction.
4. Produce a dependency/API contract table for pydantree, Templateer, fsdantic,
   Ruff, and any model boundary.
5. Produce a supported/unsupported Python construct table.
6. Produce a transaction state diagram and failure/recovery table.
7. Produce an implementation prerequisite checklist in dependency order.
8. State the later concurrency-spike entry criteria and test matrix.
9. Rerun all investigation tests from fresh fixtures and record final commands
   and hashes.
10. Update `.scratch/spikes/SPIKES.md` only after the evidence is final, and
    preserve the nuanced findings rather than reducing them to a pass/fail line.

End with exactly one verdict:

- **PROCEED TO IMPLEMENTATION** — every implementation blocker is closed;
- **PROCEED TO A BOUNDED PILOT** — the core is viable, with explicitly scoped
  unsupported cases and measurable exit criteria;
- **REVISE THE CONCEPT** — the premise survives but architecture or scope must
  change before implementation;
- **RETREAT TO SKELETON-ONLY GENERATION** — reliable round-trip ownership is not
  supportable at acceptable cost;
- **BLOCKED ON EVIDENCE** — a named authorization, dependency contract, or
  experiment is required before a decision.

The verdict must cite the decisive artifacts, summarize blocker status, state
residual risks, and identify the first safe next action. Do not begin production
implementation in the same session. Do not commit or push unless the user asks.
