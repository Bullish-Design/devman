# Agent factory pre-implementation decision record

Date: 2026-08-20

Status: provisional until final evidence reconciliation

## Accepted working decisions

1. Production implementation remains out of scope for this investigation.
2. Supported constructs require byte-for-byte preservation.
3. Unsupported constructs must fail before mutation with an owner when known.
4. Exact source may bootstrap a record. It does not count as a semantic spec.
5. A failed proposal may change neither accepted source nor accepted store.
6. Deterministic orchestration claims stay separate from model-quality claims.
7. Concurrency stress waits for single-process ownership and persistence rules.
8. The user authorized logical commits and pushes during this investigation.
9. Templateer remains the typed agent-handoff boundary.
10. Templateer does not assemble final Python source under its current API.
11. The agent-factory owns a narrow deterministic source assembler, full-file
    Python parse validation, and Ruff formatting.
12. A future Templateer `PythonFragment` contract can replace that assembler
    only after its ordinary-string isolation and diagnostics tests pass.
13. The unit model is the durable truth. `src/` is a rendered artifact.
14. Ingest verifies itself. `render(ingest(f)) == f` must hold, or ingest
    rejects the file and names the byte range that has no home.
15. The factory owns a whole file or does not touch it. No per-file trivia
    field exists.
16. Addressing is a per-language `Locator`. Python resolves a qualified name.
    Markdown reads its region marker.
17. The guard recurses into injected regions. A fenced Python block inside a
    Markdown surface file must satisfy the same equality.
18. A tracked artifact needs a pinned canonicalizer. An ignored surface does
    not.

## Architecture decision: spec as truth with a verified ingest guard

Date: 2026-08-21

The user accepted option A with the guard. Two architectures were compared.

**A — the unit model is truth.** `src/cache.py` is the render of every unit
declaring `module = "cache"` (`CONCEPT.md:126`). Render ends in `ruff format`
(`:359`). The round trip is a fixpoint on rendered output, not fidelity to
author bytes.

**B — source is truth.** The file is durable. Units become a derived index.

A wins on the opportunity that B cannot offer: one declaration renders source,
tests, docs, and a second language. A also keeps the no-shared-record
concurrency property (`:132-138`), which B loses because a file has an order
and the file is contended.

A's failure mode was the objection. When the model cannot represent content,
that content disappears. Decision 14 converts that silent loss into a loud,
located rejection. The guard is a prerequisite for A, not a feature of it.

**Rejected: the hybrid.** A verbatim trivia field per module would stop the
loss without the guard. Trivia is file-scoped, and `CONCEPT.md:126` states a
file is not a unit. Holding trivia requires a file-level record, which
contradicts the rule that makes the concurrency design work. Decision 15 draws
a clean ownership boundary instead.

**Rejected: LibCST.** It guarantees a lossless Python round trip, which suits
B. It is Python only, and `CONCEPT.md:733` scopes reading to Python with
Markdown next. A multi-language charter rules it out.

### Conditions on this decision

1. The guard ships before any production assembly work. It is
   architecture-neutral and it is the instrument that measures the rest.
2. `MODEL_QUALITY_PROTOCOL.md` runs before release, not after. Under A the
   model decides what has a home, so AF-004 gates the build.
3. Revisit if guard rejections cluster on content that users need and cannot
   relocate into a unit field.

## Conflicts to reconcile

The Phase 4 corpus asserted ownership decisions that the charter contradicts.
The corpus proved parser spans are correct and reassembly is possible. It did
not test `render(ingest(f)) == f`, so these conflicts stayed invisible.

| Corpus case | Corpus decision | Charter rule |
| --- | --- | --- |
| `structured-imports` | `collate`, no automatic deduplication | render dedupes and sorts (`:140`) |
| `comments-and-directives` | `preserve` | no field exists (`:126`) |
| `module-preamble-and-missing-final-newline` | `preserve` | shebang and cookie have no home |
| `mixed-newlines-and-trailing-space` | `preserve` | `ruff format` normalizes (`:359`) |

Each conflict resolves under decision 14: the guard rejects the file and names
the bytes. Decision 15 then decides whether the file is managed at all.

## Open architecture decisions

| Decision | Options | Required evidence | Current gate |
| --- | --- | --- | --- |
| Python rendering boundary | **Decided: external narrow renderer now; first-class Templateer fragment later** | Current failure, text workaround, injection counterexample, external reference, and future contract test | AF-003 is bounded-risk |
| Durable authored truth | **Decided 2026-08-21: the unit model is truth; `src/` is a render; a verified ingest guard makes unrepresentable content a loud rejection** | Charter round-trip contract, corpus/charter conflict table, guard equality | AF-001 closed; AF-004 remains the gate |
| Source structure engine | **Decided 2026-08-21: parser spans plus the render-fixpoint guard; no concrete syntax tree** | Categorized corpus with 100 percent supported preservation; guard rejection distribution | AF-005, AF-006; revisit if rejections cluster |
| Durable identity | Stored identifier plus evidence-ranked continuity; proposal; human choice | False-match, missed-match, ambiguity, and churn metrics | AF-007 |
| Import ownership | Collated subset; module-owned source; reject; skeleton-only | Adversarial semantic import corpus | AF-008 |
| Accepted-state persistence | Fsdantic records plus journal; filesystem snapshot; another store boundary | Interruption matrix and recovery evidence | AF-009, AF-010 |

## Implementation gates

Production work may not start until all blocker rows in `ISSUE_REGISTER.md` are
closed or explicitly converted to bounded pilot exclusions. The final decision
must also include the complete support table, transaction diagram, failure and
recovery table, dependency contracts, migration measurements, performance
budgets, threat model, and concurrency entry criteria.

## Verdict

Not issued. The investigation is active.
