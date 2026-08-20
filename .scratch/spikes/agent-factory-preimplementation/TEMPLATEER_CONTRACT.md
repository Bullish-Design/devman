# Templateer raw Python boundary contract

Date: 2026-08-20

Status: current boundary rejected; future upstream contract specified

## Required upstream behavior

Templateer must distinguish ordinary strings from validated raw Python source.
The distinction must exist in the schema. A template-wide escape bypass does
not satisfy the contract.

The proposed surface is a first-class `PythonFragment` value. A Python output
template may interpolate that value at an explicit raw site. All ordinary
strings keep Templateer's existing quoted-string escaping.

The future implementation must satisfy
`FutureTemplateerRawPythonContract` in `test_templateer_contract.py` without an
expected-failure marker.

## Validation sequence

1. Pydantic validates ordinary fields and identifies fragment fields.
2. A fragment validator parses each value as its declared Python category.
3. The renderer emits only validated fragment values without string escaping.
4. The renderer applies normal language escaping to every ordinary string.
5. Templateer parses the complete artifact as Python after assembly.
6. Ruff may establish project canonical formatting after syntax validation.

Generation does not execute the artifact. Tests or other execution happen only
behind the repository verification boundary.

## Diagnostics

A fragment error must name the model field, fragment category, source offset,
and parser error. An assembled-artifact error must also name the template and
the rendered output line. Templateer must not replace either failure with a
generic render error.

## Compatibility and removal

Keep existing `language: python` string behavior unchanged. A new fragment
value is additive. Remove any agent-factory compatibility adapter after the
minimum supported Templateer version supplies this contract.

## Comparison options

| Option | Syntax | Injection boundary | Composition | Diagnostics | Determinism | Compatibility | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| First-class fragment | Per fragment plus final artifact | Explicit fragment fields only | Direct | Can name field and site | Yes | Additive | Templateer |
| Language-aware emitter | Depends on field metadata | Safe if metadata cannot be forged | Direct | More renderer coupling | Yes | Larger renderer change | Templateer |
| Section renderer | Per section plus final artifact | Explicit section API | Good for modules | Section-aware | Yes | New output kind | Templateer |
| `text` plus Python validators | Per field when schema adds it; final validator is separate | Unsafe when ordinary strings share the template | Works for source-only models | Split across Pydantic and output validation | Yes | Works today with caller discipline | Agent factory |
| Renderer outside Templateer | Caller-defined | Caller-defined | Direct | Caller-defined | Yes | Removes Templateer from this boundary | Agent factory |

## Decision

Use the fifth option now. The agent-factory will assemble validated fragments
with a narrow deterministic renderer. It will parse the complete artifact and
then apply Ruff.

Keep Templateer for typed agent handoffs. Do not use `language: text` as a
general Python renderer. The counterexample in
`20260820T191030Z-templateer-probe/results.json` proves that a mixed template
can accept structural injection from an ordinary string while syntax validation
still passes.

The first-class fragment option remains the preferred future Templateer
contract. The emitter and section options add more machinery without a measured
advantage.
