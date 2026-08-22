# Semantic promotion state machine

Date: 2026-08-20

Status: deterministic orchestration passed; model quality and durable commit open

## Boundary

The model proposes typed semantic changes. It never writes accepted source or
the accepted store. The deterministic orchestrator validates and disposes.

## Input

- The user's edited source tree, already preserved on disk.
- The last accepted store bytes.
- The accepted generation token.
- The exact changed-unit set from structural ingest.
- Required authored examples for each changed unit.
- The prior semantic spec and bounded local context for those units.

The production prompt must exclude unrelated repository source and secrets. The
provider receives only changed declarations, their current semantic records,
their direct interface context, and relevant examples.

## Output schema

`PromotionProposal` contains the base generation token and one `UnitPromotion`
per changed unit. Each unit contains its durable identifier, edit kind,
semantic spec, and examples. The schema forbids extra fields, so there is no
dedicated source, file-write, command, or undeclared-unit channel.

That structural rule does not prove that `semantic_spec` is genuinely semantic:
a provider could disguise exact source as prose in that string. Deterministic
convergence cannot distinguish a good semantic record from that failure. The
blinded model-quality review must count it as a false acceptance.

## State flow

```text
edited source preserved
  -> request provider with timeout
  -> validate closed schema
  -> compare generation token
  -> compare exact changed-unit set
  -> validate edit kind and example obligations
  -> re-derive candidate source in staging
  -> Ruff-normalize candidate
  -> compare candidate with canonical edited source
  -> hand the candidate to the durable acceptance transaction
  -> keep the user's edited source bytes
```

Every failure before acceptance writes a proposal artifact and returns to the
same edited source and accepted store hashes. The probe completes this flow in
memory. AF-009 owns durable transaction and interruption evidence.

## Retry policy

The maximum is three provider attempts. Timeout, malformed output, partial
output, hallucinated units, example failure, and non-convergence can retry with
the prior failure. Stale input and cancellation terminate immediately. A later
implementation must use a total request budget in addition to the attempt cap.

## Normalization and convergence

The edited source must already be Ruff-canonical. The candidate passes through
the same pinned Ruff version. File paths and formatted bytes must match exactly.
No Abstract Syntax Tree equivalence or heuristic similarity counts as
convergence.

Given edited tree `E`, proposal `P`, deterministic derivation `D`, pinned Ruff
normalization `N`, and maximum attempts `k`:

```text
accept(P) iff
  token(P) = accepted_token
  and units(P) = changed_units(E)
  and examples(P) satisfy authored obligations
  and N(D(P)) = E
  within attempts <= k
```

## Terminal states

| State | Source | Store | Artifact |
| --- | --- | --- | --- |
| accepted | User edit stays byte-identical | New semantic revision | Accepted proposal and hashes |
| rejected-attempt-limit | User edit stays byte-identical | Last accepted bytes | All attempts and last proposal |
| rejected-stale-input | User edit stays byte-identical | Last accepted bytes | Expected and actual token |
| rejected-cancelled | User edit stays byte-identical | Last accepted bytes | Cancellation state |
| rejected-invalid-source | User edit stays byte-identical | Last accepted bytes | Formatter or parser failure |

## Model-quality boundary

The deterministic provider proved state routing, validation, convergence,
retry, and byte preservation for its matrix. It does not prove that a model can
write a useful semantic spec. A blinded corpus with an authorized local provider
must measure that claim later. Until then, model-quality false acceptance and
false rejection remain `unknown`.
