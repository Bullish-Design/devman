# Kickoff prompt — agent-factory round-trip spike

Copy everything below into a clean agent session launched from the devman
repository.

---

Study this task in detail, then begin.

## Context to read first

You are in `/home/andrew/Documents/Projects/devman`. Read these files completely
before taking any implementation action:

1. `.scratch/projects/005-agent-factory/CONCEPT.md` — authoritative settled
   design for this work.
2. `.scratch/projects/005-agent-factory/ORIGINAL_KICKOFF.md` — provenance and
   constraints behind the design.
3. `.scratch/projects/005-agent-factory/IDEAS_WORKFLOW.md` — idea lifecycle and
   evidence standards.
4. `AGENTS.md` and `AGENTS_GUIDE.md` — devman-local working instructions.
5. `.scratch/spikes/SPIKES.md` — style and evidence standard for previous
   devman spikes.
6. `.scratch/projects/004-unified-charter/CONCEPT.md` — related prior art;
   learn from it but do not inherit its approval gate or its old terminology.

The copies in `005-agent-factory` are the portable record from the originating
ideas workspace. Preserve them unchanged. Add new work beside them.

## Environment rule

Run all Nix-dependent commands through devman's devenv environment. This
repository uses devenv.sh/devenv as the controlled development environment;
do not use a stray virtualenv, hand-set `PYTHONPATH`, or system interpreter.

First determine the repository's canonical local command form. If a
repo-local `devenv.sh` wrapper exists in the active environment, use it. If it
does not, use the equivalent `devenv shell -- <command>` form. Record the exact
command form in the spike plan and results. If the environment lacks a required
local sibling library, add it deliberately through devman's devenv configuration
instead of bypassing the environment.

Use `devenv` for Nix-based workflows and `uv` only where devman's instructions
say it is appropriate. `devenv` owns execution; Dagu is not in scope for this
spike.

## Goal

Run the first gating experiment from `CONCEPT.md` §10.2:

> Can a model-owned Python codebase survive ordinary editing while preserving a
> truthful, round-trippable representation?

This is disposable spike work. Do **not** build the full agent factory. Do not
create a production `.devman/` directory. Do not add the reading half, tyo3,
cairn, an interactive markdown surface, Dagu workflows, agent concurrency, or
network access.

The goal is evidence that validates or kills the round-trip premise before more
implementation begins.

## Settled design — do not reopen without contradictory evidence

- A module renders from nested typed units; a file is not itself a unit.
- Module units own module-level material only. Classes/functions belong to a
  module; methods belong to a class.
- The only authored unit fields are `spec` and `examples`.
- `body`, `signature`, `docstring`, `raises`, and `test` are derived.
- Source renders deterministically. `ruff format` is the final render step.
- Source edits ingest by AST-qualified identity and byte spans. Do not use
  marker comments.
- A source edit to a derived declaration promotes its meaning to `spec`; never
  persist it as a pinned derived field.
- Drift gates compare bytes. Human-facing changes use a structural, unit-keyed
  diff.
- Unsupported edits must fail loudly with an actionable route to the owning
  declaration. Never guess.
- Do not use tyo3 in this spike. `pydantree-sitter` is the structural reader;
  `templateer` is the typed deterministic renderer.

## First deliverable: a spike plan

Before implementation, create a concise plan at:

`.scratch/spikes/agent-factory-round-trip/PLAN.md`

It must state:

1. The selected fixture module(s), and why they represent real Python shape.
2. The unit schema and stable identity strategy.
3. Supported Python constructs.
4. Explicitly unsupported constructs, which must fail rather than be guessed.
5. Exact environment commands that will generate evidence.
6. The success and kill criteria below.
7. A blank results table that will be filled with actual observations.

Keep the fixture small but include module docstring/imports, a top-level
function, a class with methods, annotations, docstrings, control flow, and
imports that must be collated rather than hand-authored.

## Build the smallest prototype that can falsify the premise

Isolate all implementation under:

`.scratch/spikes/agent-factory-round-trip/`

Build only enough machinery to:

1. Parse a fixture into typed nested units.
2. Persist units in a disposable spike-local store.
3. Render the module deterministically through templateer.
4. Apply `ruff format` as the final render step.
5. Assert initial source and rendered source are byte-identical.
6. Ingest edits by AST-qualified name and byte span.
7. Re-render after each ingest.
8. Emit byte-drift evidence for gates and structural unit-level change reports
   for review.

Do not build a generic framework. Prefer a narrow, auditable prototype with
tests over abstractions intended for the final factory.

## Required edit cases

Implement and record evidence for all of these:

1. Change a function body.
2. Add a signature parameter.
3. Change a docstring.
4. Add a new top-level function.
5. Delete a top-level function; create a recoverable tombstone.
6. Rename or move a method in the same file, only if AST identity can establish
   it safely; otherwise report it as unsupported rather than guessing.
7. Perform one cross-file refactor, such as extracting a helper to another
   module or moving a class.

For edits to derived fields, test the promotion path explicitly:

```text
source edit
→ AST ingest identifies the changed declaration
→ promotion updates spec
→ re-derive/render
→ rendered declaration preserves the intended edit
```

Promotion will be stochastic in the full design. A deterministic test double
is acceptable in this spike to exercise the control flow and convergence guard.
State plainly what that does not prove.

The guard is mandatory:

```text
promote edited declaration into spec
→ re-derive from new spec
→ compare with the edited declaration
→ accept only if the intended edit survives
```

If promotion cannot capture an edit, preserve the on-disk source edit, reject
the unit update, and create a proposal-like failure artifact. Never silently
revert the edit.

## Acceptance and kill criteria

The spike succeeds only when every row passes:

| Measure | Required result |
| --- | --- |
| Initial ingest → render | 100% byte identity |
| Body/signature/docstring ingest | Re-render preserves each edit |
| New declaration | Creates a stable unit and renders correctly |
| Deleted declaration | Creates a recoverable tombstone |
| Unsupported/collated edit | Fails loudly and names the correct owning declaration |
| Structural diff | Reports changed/moved/added/removed units without tree-edit-distance heuristics |
| Formatting | Rendered output survives `ruff format` with no drift |

Kill or retreat immediately if:

- initial byte identity is below 100%; or
- ordinary cross-file refactors require fragile guessing or excessive unit churn.

The documented retreat is skeleton-only generation with bodies remaining in
`src/`. Do not weaken the criteria after seeing a result.

## Required final artifacts

Produce:

1. The plan at the path above.
2. Runnable prototype code and fixtures, entirely under the spike directory.
3. Automated checks covering every required edit case.
4. A dated results report in the spike directory and a concise entry in
   `.scratch/spikes/SPIKES.md` containing commands, observed pass/fail evidence,
   byte-identity outcome, supported/unsupported edits, cross-file result, and a
   recommendation: proceed, retreat, or investigate one named blocker.
5. A final report ordered by evidence, not optimism.

## Working rules

- Work only on this round-trip spike. Do not start the concurrency spike.
- Use `rg` for searching.
- Preserve existing changes in the devman repository.
- Do not contact the network, push, publish, or change unrelated project code.
- Do not commit unless I explicitly ask.
- State failures plainly. This spike exists to disprove the premise cheaply if
  it is wrong.
