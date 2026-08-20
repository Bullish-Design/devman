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

## Open architecture decisions

| Decision | Options | Required evidence | Current gate |
| --- | --- | --- | --- |
| Python rendering boundary | Typed raw fragment; language emitter; section renderer; text plus validation; external renderer | Executable preservation, syntax, injection, diagnostics, determinism, and compatibility results | AF-003 |
| Durable authored truth | Semantic spec plus examples; source-backed bootstrap; skeleton-only source ownership | Promotion quality, bootstrap exit, and dual-authority analysis | AF-001, AF-002, AF-004 |
| Source structure engine | Abstract syntax tree plus spans; tokens; concrete syntax tree; explicit trivia records | Categorized corpus with 100 percent supported preservation | AF-005, AF-006 |
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

