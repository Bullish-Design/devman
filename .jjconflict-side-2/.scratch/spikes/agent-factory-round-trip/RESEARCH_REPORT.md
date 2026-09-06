# Agent factory round-trip spike results

Date: 2026-08-20

Status: all required cases passed

Recommendation: investigate one named blocker before production work. Templateer
needs a validated raw Python source-fragment boundary.

## Outcome

The narrow round-trip premise survived this fixture. Initial ingest and render
produced 100 percent byte identity. Body, signature, and docstring edits updated
the authored spec and survived re-derivation. Add, delete, rename, and cross-file
move cases also converged.

The cross-file case retained the moved function's durable identifier. It added
one module unit. It changed no unrelated declaration units. This is bounded
unit churn.

The result does not justify the full agent factory. The promotion stage used a
deterministic source-backed test double. It proves transaction and guard flow.
It does not prove that a model can write a useful semantic spec.

## Acceptance evidence

| Measure | Observed result | Evidence |
| --- | --- | --- |
| Initial ingest to render | Pass; identical SHA-256 hashes; 100% | `artifacts/20260820T182540Z/results.json` |
| Deterministic repeat | Pass; second render matched the first | `initial-identity.deterministic_repeat` |
| Body ingest | Pass; one unit changed; spec promotion converged | `body-change` |
| Signature ingest | Pass; one unit changed; spec promotion converged | `signature-parameter` |
| Docstring ingest | Pass; one unit changed; spec promotion converged | `docstring-change` |
| New declaration | Pass; `catalog::summarize` received one durable identifier | `add-function` |
| Deleted declaration | Pass; recoverable `catalog::build_catalog` tombstone | `delete-function` |
| Same-file rename | Pass; method identifier moved to `catalog::Catalog.resolve` | `rename-method` |
| Cross-file refactor | Pass; one moved function and one added module unit | `cross-file-move` |
| Unsupported import edit | Pass; rejected with owner `catalog::build_catalog` | `collated-import-rejected/failure/proposal.json` |
| Failed promotion | Pass; source and old store preserved | `failed-promotion-preserves-source/failure/proposal.json` |
| Structural diff | Pass; exact durable-key sets, no span churn | Per-case `structural-diff.json` files |
| Formatting | Pass; repeated Ruff format produced no drift | `initial-identity.formatting_stable` |

The final run artifact is
`artifacts/20260820T182540Z/`. The independent verification logs are in
`artifacts/20260820T182609Z-verification/`.

## Environment

The repository has no `./devenv.sh` wrapper. Every command used this form:

```text
devenv shell -- <command>
```

The final environment recorded:

| Component | Version |
| --- | --- |
| Python | 3.13.14 |
| pydantree-sitter | 0.2.0 |
| Templateer | 0.2.0 |
| Ruff | 0.15.20 |

The devman environment lacked the two sibling libraries. `devenv.nix` now
creates one managed `.pth` file. It exposes both sibling source trees and their
UV-managed dependencies. No command set `PYTHONPATH`. No command executed a
sibling virtual environment. The spike contacted no network service.

## Commands

Final runtime:

```text
devenv shell -- python .scratch/spikes/agent-factory-round-trip/run_spike.py --artifacts .scratch/spikes/agent-factory-round-trip/artifacts/20260820T182540Z
```

Independent checks:

```text
devenv shell -- python -m unittest discover -s .scratch/spikes/agent-factory-round-trip -p 'test_*.py'
devenv shell -- ruff check --exclude artifacts .scratch/spikes/agent-factory-round-trip
devenv shell -- ruff format --check --exclude artifacts .scratch/spikes/agent-factory-round-trip
```

The unit test ran all ten cases and passed. Ruff lint passed. Ruff reported all
six source files formatted.

## Failure history

The investigation kept the acceptance criteria fixed.

1. The initial dependency task failed before runtime. UV offline resolution did
   not index a cached MiniJinja wheel. A later full Templateer install also
   expanded into unavailable agent dependencies. The final devenv task exposes
   the already UV-managed sibling environments through a generated `.pth` file.
2. Runtime attempt 1 failed during pydantree model construction. `Span` requires
   `arbitrary_types_allowed`. Pydantree's own consumer fixture confirmed the
   setting. The local output models now declare it.
3. Runtime attempt 2 failed during environment reporting. The pydantree source
   tree has no installed distribution metadata. The runner now falls back to
   `pydantree_sitter.__version__`. The preserved classification is
   `artifacts/20260820T182005Z/bootstrap-failure.txt`.
4. Runtime attempt 3 revealed 0 percent initial identity. The AST decorator
   expression starts after the `@` byte. The parser now extends the pydantree
   span by one byte for decorated declarations. The preserved diff is under
   `artifacts/20260820T182100Z/`.
5. Runtime attempt 4 passed every byte gate. Three edit cases still reported
   five changed units. Only their byte spans moved. Structural diff now compares
   declaration content hashes and locations, not routing metadata. The next run
   reported one changed unit for each local edit.

## Local source research

The spike used local primary sources because its contract forbids network
access.

- [pydantree user guide](../../../../pydantree/docs/user-guide.md) defines
  `Span = source_meta()` and extraction from the Python grammar wheel.
- [pydantree consumer fixture](../../../../pydantree/tests/fixtures/consumers/consumer_nix.py)
  shows the required arbitrary-type model configuration.
- [Templateer renderer](../../../../templateer_v2/src/templateer/renderer.py)
  confirms deterministic rendering from a validated Pydantic model.
- [Templateer escaping](../../../../templateer_v2/src/templateer/escaping.py)
  confirms that Python strings are escaped for quoted-string positions.

## Supported result

The prototype supports the constructs listed in `PLAN.md`. It uses
pydantree-sitter spans, AST-qualified locations, durable identifiers, Pydantic
stores, Templateer rendering, and Ruff as the final render stage.

The unsupported import case failed with the correct declaration owner. The
promotion failure wrote a proposal artifact. It preserved both the edited source
and the accepted store hash.

## What the evidence does not prove

- The fixture is small. It is not a replay of a real repository history.
- The promotion test double stores exact source in the spec. It does not prove
  semantic promotion by a model.
- The parser rejects asynchronous functions, generators, nested declarations,
  relative imports, overloads, conditional definitions, and ambiguous moves.
- The cross-file case moves one unchanged top-level function. It does not test a
  many-file rename with caller edits.
- Templateer rendered a `language: text` target. Ruff then validated Python.
  This keeps raw source bytes but weakens Templateer's structured-language
  boundary.

## Recommendation

Do not retreat to skeleton-only generation from this evidence. The measured
round trip and cross-file identity both passed.

Do not start the full factory yet. First investigate one blocker: add or reject
a Templateer contract for validated raw Python source fragments. The contract
must preserve byte-deterministic rendering without treating arbitrary model
strings as safe Python syntax.

If that contract cannot exist without bypassing Templateer's safety model,
retreat to skeleton-only generation. If it can exist, run the same experiment
against real commit history before concurrency work.
