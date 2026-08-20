# Agent factory pre-implementation research report

Date: 2026-08-20

Status: active investigation

## Scope and evidence standard

This investigation tests whether project `005-agent-factory` is ready for any
production implementation. It challenges source preservation, ownership,
identity, determinism, migration cost, persistence, and ordinary development.

The acceptance bar is 100 percent preservation for supported constructs. An
unsupported construct may fail before mutation. A failed or ambiguous operation
must preserve the edited source and last accepted store byte-for-byte.

## Baseline facts

- Spike F passed its ten narrow scenarios and achieved initial byte identity.
- Its durable identity bridge covered one unique same-file rename and one unique
  cross-file move.
- Its promotion provider stored exact source inside the authored `spec`.
- Its Templateer template used `language: text`, then Ruff validated and
  formatted the rendered Python.
- Templateer 0.2.0 applies one language finalizer to every MiniJinja output site.
  For `language: python`, every string is escaped as quoted-string content.
- Templateer parses a final Python artifact with `ast.parse`, but
  `render_from_model()` does not call output validation by itself.
- Pydantree 0.2.0 reports UTF-8 byte spans from tree-sitter. It exposes parse
  error nodes but leaves rejection to the caller.
- Fsdantic 0.7.0 provides per-key SQL compare-and-set for versioned records.
- Fsdantic `save_many()` applies independent saves and returns per-item results.
  It is not a multi-key transaction.
- Fsdantic's public KV transaction is explicitly best-effort rollback.
- Fsdantic materialization uses a staging tree and rename swap. Its source calls
  cross-device fallback non-atomic and concurrent-process recovery best-effort.

## Baseline environment

The first artifact directory is `artifacts/20260820T190104Z-baseline/`. The
dependency import failed because fsdantic is not available in devman's devenv.
The directory preserves the successful probes, source hashes, and failure.

The bounded retry is `artifacts/20260820T190406Z-baseline-retry/`. It records
fsdantic as unavailable and verifies every dependency needed for the Templateer
probe.

The initial known runtime is Linux with Python 3.13.14, pydantree-sitter 0.2.0,
Templateer 0.2.0, tree-sitter-python 0.25.0, and Ruff 0.15.20. The baseline
capture will verify these values again.

## Current blocker analysis

### Templateer raw Python fragments

Templateer's current finalizer correctly protects ordinary strings in quoted
positions. It cannot distinguish a source fragment from an ordinary string.
Passing a declaration such as `def f():\n    return 1` through a Python output
site escapes the newline. The result is not the intended fragment.

A safe contract cannot disable escaping for all Python strings. It needs an
explicit typed value or an equally narrow rendering boundary. The contract must
validate the fragment as the declared syntactic category before rendering. It
must validate the assembled artifact again afterward.

### Semantic promotion

Spike F proves rollback and convergence control flow only. Its accepted `spec`
contains exact source, so re-derivation is source retrieval. This mechanism is
valid for lossless bootstrap. It is not evidence that a semantic specification
became durable truth.

## Facts, inferences, recommendations, and unknowns

Facts appear above and will receive artifact paths as probes run.

Inference: Templateer's global finalizer makes an explicit fragment wrapper the
smallest plausible upstream extension. This remains unproven until the probe
tests MiniJinja value preservation and audit behavior.

Recommendation: close the Templateer boundary before broad corpus work. The
chosen renderer determines which byte-preservation claims the corpus can test.

Unknowns include semantic promotion quality, the safe Python support subset,
identity ambiguity rates, multi-file recovery, real-history adoption cost,
performance budgets, untested platforms, and supply-chain status.

## Research log

### 2026-08-20 — prerequisite review

Read the complete remaining-investigations prompt, project design sources,
Spikes E and F, the round-trip prototype and tests, representative preserved
artifacts, the unified charter, and `anchors.py`.

Inspected local source, tests, and history in `pydantree`, `templateer_v2`, and
`fsdantic`. No network source was used. No sibling repository was changed.

### 2026-08-20 — baseline capture

The first baseline stopped at dependency import. Fsdantic was not exposed to
devman's Python environment. No investigation probe had started.

The fresh retry passed with Python 3.13.14, Pydantic 2.13.4,
pydantree-sitter 0.2.0, Templateer 0.2.0, tree-sitter-python 0.25.0,
Ruff 0.15.20, and devenv 2.1.2. It records fsdantic runtime behavior as
unavailable rather than inferring it from source.

### 2026-08-20 — Templateer raw Python boundary

The exact probe is `templateer_probe.py`. The passing runtime evidence is
`artifacts/20260820T191030Z-templateer-probe/`. The contract tests passed with
one expected failure for the missing future upstream API. Their evidence is
`artifacts/20260820T191014Z-templateer-tests-retry/`.

Current `language: python` changed the fragment's newline bytes to `\\n` escape
sequences. The assembled artifact failed `ast.parse` at line 1, column 22.

A source-only `language: text` template preserved the fragment, rejected an
invalid fragment before rendering, passed a declared Python parse validator,
rendered deterministically, and remained Ruff-idempotent.

That workaround is unsafe as a general Python renderer. A mixed text template
accepted an ordinary string that closed a quoted value and added an `INJECTED`
assignment. The final artifact remained valid Python, so syntax validation did
not detect the structural injection.

An external source assembler preserved the same fragment and passed Python
syntax validation. It does not weaken Templateer's escaping because Templateer
is not the final source renderer.

Fact: Templateer has no current value type that distinguishes raw Python from
ordinary strings after `model_dump(mode="json")`.

Inference: a template-wide identity finalizer cannot safely mix source fragments
with ordinary string fields.

Decision: keep Templateer for typed agent handoffs. Remove it from final Python
assembly until it supplies the explicit `PythonFragment` contract in
`TEMPLATEER_CONTRACT.md`. The agent-factory owns a narrow deterministic source
assembler, full-file parse validation, and Ruff formatting.

This decision closes the dependency blocker. It does not prove the external
assembler against the full Python support corpus.

### 2026-08-20 — semantic promotion orchestration

The exact probe is `promotion_probe.py`. The passing evidence is
`artifacts/20260820T192215Z-promotion-probe-retry/`. The full investigation
tests also passed in `artifacts/20260820T192113Z-promotion-tests-final/`.
The first final-probe wrapper pre-created its target directory, so the probe's
freshness guard correctly rejected it. That harness failure is preserved in
`artifacts/20260820T192113Z-promotion-probe-final/`.

The scripted provider covered body, signature, behavior, docstring, import,
rename, move, split, merge, and delete proposals. All ten expected promotions
reached the in-memory accepted state in one attempt.

The adversarial matrix covered malformed output, partial output, hallucinated
units, stale context, contradictory examples, timeout, cancellation, repeated
non-convergence, and an exact-source field. All nine cases rejected. Stale input
and cancellation terminated immediately. Retryable failures stopped at the
three-attempt limit.

The measured orchestration false-acceptance rate was 0 of 9. The measured
orchestration false-rejection rate was 0 of 10. Every rejection preserved the
edited-source and accepted-store hashes.

The schema forbids extra fields, so a `source_contract` cannot enter an authored
semantic record. The deterministic derivation fixture still knows the expected
source. This is an oracle for orchestration tests, not a model-quality claim.
The closed schema also cannot stop a provider from disguising exact source in
the `semantic_spec` string; the blinded review protocol must detect that case.

The probe creates accepted store bytes in memory. It does not test a durable
multi-record commit or a process interruption. Those claims remain under
AF-009 and AF-010.

No local or hosted model ran. Semantic false-acceptance and false-rejection rates
remain unknown. `MODEL_QUALITY_PROTOCOL.md` defines the authorized experiment.

### 2026-08-20 — Python syntax, trivia, and ownership corpus

The executable corpus is `python_corpus_probe.py`; the support policy is
`PYTHON_SUPPORT_MATRIX.md`. Passing evidence is preserved under
`artifacts/20260820T192930Z-python-corpus-final/`, and the expanded four-test
suite passed under `artifacts/20260820T192930Z-python-corpus-tests-final/`.

Sixteen composite cases cover 69 required syntax and trivia categories. Every
supported case was reconstructed byte-for-byte from top-level tree-sitter node
spans plus explicit opaque gap slices. There were zero byte-identity failures,
zero UTF-8 span failures, and zero parse-classification failures. The non-ASCII
case confirms that offsets must index encoded UTF-8 bytes, not Python character
positions.

The invalid active buffer produced parser error nodes and was rejected before
assembly or mutation. Optional/side-effect import blocks and unsafe star,
dynamic, and semicolon import forms were also assigned to the source owner and
rejected from automatic ownership/collation before mutation.

Fact: concrete-node spans plus opaque gaps can preserve an unchanged file.
Inference: declaration AST plus spans alone cannot safely own comments,
directives, blank lines, mixed-newline policy, or import collation. Those need
the concrete tree plus tokens or explicit trivia/gap records.

This is not a semantic edit or full regeneration result. It establishes the
unchanged preservation and rejection boundary; edits across the corpus remain a
later implementation gate.
