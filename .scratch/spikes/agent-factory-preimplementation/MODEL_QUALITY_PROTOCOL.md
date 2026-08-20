# Semantic promotion model-quality protocol

Date: 2026-08-20

Status: not run; requires an authorized local provider

## Question

Can a fixed local model convert source edits into useful semantic specifications
and examples without exact-source fallback?

## Fixed provider inputs

Record the provider, model identifier, weight digest, quantization, runtime,
prompt digest, schema digest, decoding parameters, and generator version. Run
offline. Do not substitute a model, context size, or quantization after the run
starts.

For each case, provide only:

- the changed declaration before and after the edit;
- the prior semantic spec and authored examples;
- direct dependency signatures and direct caller signatures;
- the exact allowed durable unit identifiers and edit kind;
- the accepted generation token; and
- the closed `PromotionProposal` schema.

Do not provide the rest of the repository, credentials, unrelated comments, or
failure labels from the reference answer.

## Blinded corpus

Freeze 200 initial cases before model execution:

- 100 real accepted edits sampled from first-parent local history;
- 50 deliberate refactors from local history; and
- 50 synthetic adversarial cases that cover weak, stale, contradictory, and
  overfitted examples.

Stratify the corpus equally across body, signature, behavior, docstring, import,
rename, move, split, merge, and delete where history permits. Record exclusions.
Keep repository, commit, path, and expected result hidden from the model.

Two reviewers independently write the reference semantic delta and example
obligations before they see model output. Resolve reviewer disagreement before
scoring the model.

## Execution

Run one cold attempt and at most two repair attempts per case. Feed only the
prior machine-readable failure into a repair attempt. Preserve all raw requests,
responses, token counts, timings, validations, re-derived artifacts, and hashes.

Never accept a proposal that fails schema, token, ownership, example, or exact
convergence checks. Never let a failed proposal change source or store bytes.

## Scoring

Classify each case as:

- true acceptance: converged source and reviewer-equivalent semantic record;
- false acceptance: converged source but materially incomplete, misleading, or
  source-backed semantic record;
- true rejection: unsafe or insufficient proposal rejected;
- false rejection: a reviewer-equivalent proposal rejected; or
- unresolved: reviewer disagreement or invalid reference case.

Report counts and Wilson 95 percent confidence intervals by edit kind and in
aggregate. Report attempts, latency, token use, and context bytes separately.

## Predeclared gates

The 200-case run is a pilot gate. It requires zero false acceptances, no source
or store mutation after rejection, and at most 20 false rejections. Ten percent
false rejection is the pilot ceiling because it limits manual recovery to about
two events in a 20-edit day.

Production requires a later 600-case shadow run with zero false acceptances and
at most 30 false rejections. With zero observed false acceptances, the rule of
three places the approximate one-sided 95 percent upper bound below 0.5 percent.
The five percent rejection ceiling limits manual recovery to about one event in
a 20-edit day.

These statistical bounds do not prove safety for unseen edit classes. Any
critical semantic omission resets the gate and creates a new corpus category.

## Authorization and stop rules

Do not run this protocol until the user authorizes the named local provider.
Stop on network access, credential requests, model substitution, corpus leakage,
source/store mutation after rejection, or the first false acceptance. Preserve
the failure evidence.
