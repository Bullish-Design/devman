# Agent factory round-trip spike plan

Date: 2026-08-20

## Question

Can nested typed units preserve a real Python module through ingest, ordinary
source edits, guarded promotion, and deterministic re-rendering?

This spike tests only the round-trip premise. It does not build the factory.

## Environment

The repository has no executable `./devenv.sh` wrapper. The canonical local
command form is:

```text
devenv shell -- <command>
```

The managed environment does not currently expose `pydantree_sitter`,
`templateer`, or their Python dependencies. Add the local sibling projects
through `devenv.nix`. Do not set `PYTHONPATH` or use another virtual
environment.

Use these exact evidence commands:

```text
devenv shell -- python .scratch/spikes/agent-factory-round-trip/run_spike.py --artifacts <fresh-UTC-directory>
devenv shell -- python -m unittest discover -s .scratch/spikes/agent-factory-round-trip -p 'test_*.py'
devenv shell -- ruff check --exclude artifacts .scratch/spikes/agent-factory-round-trip
devenv shell -- ruff format --check --exclude artifacts .scratch/spikes/agent-factory-round-trip
```

Each runtime attempt gets a new UTC artifact directory. The runner records the
resolved command, environment versions, standard output, byte hashes, unit
changes, failure artifacts, and the final fixture tree.

## Fixtures

The initial fixture is `fixtures/original/catalog.py`. It contains:

- a module docstring and future import;
- standard-library imports that units request and the renderer collates;
- annotated top-level functions;
- a class with annotated methods and docstrings;
- conditionals, a loop, a comprehension, and exceptions; and
- a module constant.

The cross-file case adds `normalization.py` and moves one helper into it. Two
small modules expose file membership, import collation, stable identity, and
unit churn without creating a generic framework.

## Unit schema and identity

Persist a Pydantic `UnitStore` with typed records:

- `ModuleUnit`: module identity, module docstring, and constants;
- `ClassUnit`: durable identity, current location, and class declaration;
- `FunctionUnit`: durable identity, current location, and declaration; and
- `Tombstone`: removed unit, prior location, source bytes, and removal reason.

Each declaration unit carries the closed authored fields `spec` and `examples`.
It also carries derived signature, docstring, body, import requirements, and
render artifact fields. The prototype never treats a derived field as authored.
Each child declares its module and optional parent identifier. Parents do not
persist membership lists. The renderer constructs the nested view.

The current location is `<module>::<qualified.name>`. A durable identifier is
created from the first location and stays with the unit. Pydantree-sitter
supplies each declaration's byte span. Nested containment establishes method
ownership. A same-file rename or move is accepted only when one removed unit
and one added unit have the same normalized declaration fingerprint. A
cross-file move uses the same rule across the complete edited tree. A unique
match retains the durable identifier at its new location. Ambiguous matches
fail.

## Supported constructs

- UTF-8 Python modules with Unix line endings;
- one module docstring;
- `from __future__` and absolute `import` or `from` imports;
- annotated synchronous top-level functions;
- classes with annotated synchronous methods;
- decorators that remain attached to one declaration;
- module constants;
- arbitrary valid synchronous statement bodies within captured declarations;
- add, delete, rename, or move of one uniquely matched declaration; and
- import changes derived from unit import requirements.

## Unsupported constructs

These constructs fail with an owner and a corrective route:

- hand edits to collated imports or deterministic member ordering;
- asynchronous functions, generators, lambdas, nested functions, and nested
  classes;
- overload sets, conditional definitions, metaclass expressions, and dynamic
  exports;
- wildcard or relative imports;
- multiple simultaneous rename or move candidates with the same fingerprint;
- changes to module boilerplate or constants after initial ingest; and
- syntax errors or declarations whose byte spans overlap unexpectedly.

The renderer also records a known boundary. Templateer escapes string values
for `language: python`, so raw declaration fragments cannot preserve bytes.
The spike uses a typed Templateer template with `language: text`, then Ruff
validates and formats the Python artifact. This proves deterministic rendering
through Templateer. It does not prove that Templateer's production Python
boundary safely accepts validated source fragments.

## Promotion and convergence guard

A deterministic promotion test double receives the old spec, old declaration,
and edited declaration. It writes a source-backed spec and re-derives the
declaration from that spec.

Accept the unit update only when the re-derived declaration equals the edited
declaration after Ruff formatting. Otherwise keep the edited source, keep the
old unit store, and write a proposal-like failure artifact.

This proves identity, routing, rollback, and convergence control flow. It does
not prove that a stochastic model can express the semantic meaning of an edit
as useful prose.

## Required cases

1. Initial ingest and render.
2. Function body change.
3. Signature parameter addition.
4. Docstring change.
5. New top-level function.
6. Deleted top-level function with recoverable tombstone.
7. Safe same-file method rename or an explicit unsupported result.
8. Cross-file helper extraction or an explicit retreat if identity requires
   guessing.
9. Unsupported collated import edit with the owning declaration named.
10. Forced promotion failure that preserves the edited source and old store.

## Success and kill criteria

Success requires every acceptance row below to pass. Initial identity must be
100 percent. Body, signature, and docstring promotion must preserve the edit.
Additions need stable units. Deletions need recoverable tombstones. Unsupported
edits must fail loudly. Structural reports must use unit keys. Ruff must produce
no post-render drift.

Kill the model-owned-body premise immediately if initial identity is below 100
percent. Retreat to skeleton-only generation if the cross-file case needs
guessing or produces excessive unit churn. Do not lower either threshold.

## Results

| Measure | Required result | Observed result | Evidence |
| --- | --- | --- | --- |
| Initial ingest to render | 100% byte identity | Pass; 100%; hashes match | `artifacts/20260820T182540Z/results.json` |
| Body ingest | Re-render preserves edit | Pass; one changed unit; promotion converged | `body-change` |
| Signature ingest | Re-render preserves edit | Pass; one changed unit; promotion converged | `signature-parameter` |
| Docstring ingest | Re-render preserves edit | Pass; one changed unit; promotion converged | `docstring-change` |
| New declaration | Stable unit renders | Pass; `catalog::summarize` added | `add-function` |
| Deleted declaration | Recoverable tombstone | Pass; `catalog::build_catalog` recoverable | `delete-function` |
| Same-file rename or move | Safe match or explicit unsupported result | Pass; identifier retained for `Catalog.resolve` | `rename-method` |
| Cross-file refactor | Safe match with bounded churn, or retreat | Pass; one moved unit and one added module unit | `cross-file-move` |
| Unsupported collated edit | Loud failure names owner | Pass; owner `catalog::build_catalog` | `collated-import-rejected/failure/proposal.json` |
| Failed promotion | Source preserved; store rejected; artifact written | Pass; source and accepted store preserved | `failed-promotion-preserves-source/failure/proposal.json` |
| Structural diff | Keyed changed, moved, added, and removed units | Pass; durable-key set comparison | Per-case `structural-diff.json` |
| Formatting | Ruff produces no render drift | Pass; repeated Ruff format stable | `initial-identity.formatting_stable` |
