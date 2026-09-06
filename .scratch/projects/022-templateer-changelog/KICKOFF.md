# Kickoff: templateer-backed changelog generation

Date: 2026-09-06

## Objective

Update the `changelog` group so its generated `CHANGELOG.md` section is
produced through the sibling `templateer_v2` library. Preserve the group's
existing safety contract: entries are generated as free files, the tracked
`CHANGELOG.md` edit is made on the fixed `changelog` gitman lane, and the
workflow refuses both an empty batch and a second unreviewed lane.

The integration must use Templateer's supported API or CLI contract. It must
not copy Templateer's internals into a heredoc, replace typed generation with
an unvalidated prompt, or make the devman group depend on an absolute path to a
developer checkout.

## Starting measurements

- The target implementation is `groups/changelog/workflows/changelog.yaml`.
  Its current design gates on `.devman/changelog/entries/`, starts a fixed
  gitman lane, calls a local OpenAI-compatible model, and writes a dated
  section containing model prose plus verbatim commit references.
- The group currently enters the adopter's `devenv` before importing
  `pyjutsu` or invoking `gitman`; this is required because Dagu's daemon does
  not inherit the adopter shell environment.
- The sibling library is `/home/andrew/Documents/Projects/templateer_v2`.
  Its public package is `templateer`, version `0.3.0`, Python `>=3.12`.
  The documented boundary is `TemplateRegistry.from_paths(...)`, with
  `generate`/`generate_async` for LLM-backed generation and
  `render_from_model` for deterministic rendering.
- Templateer requires callers to supply template directories. It ships no
  installed template catalog. The integration therefore needs a repository
  or group-owned template asset and a measured distribution/install path for
  the repositories that take the group.
- The previous changelog work proved workflow validation, the pyjutsu history
  reads, real gitman lane operations in a disposable adopter, and the Dagu
  environment boundary. It did not prove a real LLM response or this new
  Templateer path.
- This checkout must be inspected and repaired if the conflict markers in the
  current workflow are real working-tree content. No implementation decision
  may be based on a conflicted file.

## Decisions to resolve by measurement

1. **API boundary:** determine whether the workflow should call a small
   repository-local adapter using `TemplateRegistry`, or invoke the
   `templateer` CLI. Prefer the Python API if it gives structured failure
   handling and keeps the workflow shell thin.
2. **Template ownership:** determine where the changelog template, schema,
   prompt, renderer, and fixtures belong so a taking repository receives them
   without referring to this machine's sibling checkout.
3. **Dependency delivery:** determine how `templateer` becomes importable in a
   real adopter's `devenv` and in Dagu's daemon environment. A local editable
   dependency may be used for the disposable test, but is not sufficient as a
   shipped group contract.
4. **Model contract:** preserve the existing local `$GPU_LLM_BASE_URL` and
   queue behavior, while mapping Templateer's `GenerationResult` failures to a
   non-zero workflow result. Verify model configuration and output bounds.
5. **Artifact contract:** decide whether Templateer generates the whole
   dated Markdown section or a typed intermediate model that the workflow
   combines with the deterministic marker and wikilink bullets. The latter is
   preferred unless Templateer's markdown validation makes the former clearly
   safer.

## Acceptance criteria

The work is complete only when all of these are true:

- The changelog workflow contains no copied Templateer implementation and no
  sibling absolute path.
- A taking repository can discover and load the required template assets and
  import the pinned Templateer package through its declared environment.
- The generated section still contains the date, the frontier marker, model
  prose, and one verbatim Obsidian wikilink bullet per pending change id.
- Templateer validation failures and model/configuration failures fail the
  Dagu step loudly; no successful run may write an empty or unvalidated
  section.
- The fixed-lane collision refusal, empty-batch refusal, and retry behavior
  remain intact.
- A disposable real gitman adopter runs `start`, `save`, and `land`; the
  actual post-hook enqueues `changelog-entries`; the chained workflow reaches
  the Templateer generation step; and the resulting lane diff is inspected.
- The deterministic render path is tested without a provider key. If a local
  model server is available, one real generation is run and its output is
  reviewed for hallucination, length, grouping, and formatting. If no server
  is available, that gap is recorded rather than masked by a fake success.
- `dagu validate` passes for both group workflows, `base:check`, `base:test`,
  and `devman doctor` pass, and Templateer's focused/full tests pass when its
  source is changed.
- The implementation, tests, and evidence are saved through gitman on the
  current PR branch and pushed. No unrelated worktree changes are discarded.

## Non-goals

- Do not make devman's own day-to-day development adopt gitman lanes.
- Do not add a new queue, secret, scheduler, or external hosted model.
- Do not make Templateer a required dependency of every devman adopter; scope
  it to the changelog group or an explicitly measured shared package path.
- Do not claim Obsidian resolution without opening the actual vault or a
  documented equivalent check.
- Do not silently modify the sibling Templateer project unless its own public
  API lacks a necessary contract and the change is separately justified there.

## Work sequence

1. Establish clean repository state and resolve the workflow conflict-marker
   question. Read Templateer's public API, template authoring rules, and
   environment definitions.
2. Build a minimal Templateer changelog template and adapter design. Add
   focused tests for model validation, Markdown rendering, frontier/bullet
   preservation, and failure propagation.
3. Implement the group integration with the smallest possible workflow
   surface. Keep gitman, pyjutsu, and file movement in thin wrappers.
4. Run focused library/template tests, then the repository verification gates.
5. Exercise the disposable adopter through real gitman `start`/`save`/`land`
   and the post-hook chain. Record every external-environment limitation.
6. Re-run refusal cases and inspect the lane diff. Update the 021 design only
   if a measured behavior changes its contract; otherwise keep this bounded
   project note as the evidence record.
7. Save, inspect, and publish the completed work through gitman.

## Evidence to retain

Record commands and relevant output in this project directory, including:

- Templateer API/import and template discovery checks.
- Focused tests and their exit codes.
- Dagu validation and devman verification gates.
- Disposable adopter gitman lifecycle and workflow run IDs.
- The generated `CHANGELOG.md` diff and the exact failure behavior for empty
  and collision cases.
- Whether a real local model and Obsidian vault were available.

## Stop conditions

Pause for a design note rather than silently choosing if Templateer's public
API cannot express the required changelog artifact, if shipping the template
would require an absolute sibling path, or if the only way to make generation
work is to weaken the group's lane/refusal guarantees.
