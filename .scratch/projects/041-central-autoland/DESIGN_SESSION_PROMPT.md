# Project 041 — follow-up design session

Use this prompt to run a second, evidence-led investigation of the central-config safety problem. Read it with `CONCEPT.md`, `DECISIONS.md`, and the original `INVESTIGATION_PROMPT.md` in this directory.

## Task

Design the smallest complete system that detects central-config drift, blocks unsafe working-copy rewrites, and keeps routine generated content from accumulating without review.

The first investigation established a strong concept. It did not settle every implementation choice or validate the current machine state. Re-check the evidence, compare the options below, challenge the provisional recommendations, and produce a concrete design and implementation plan.

This session is **investigation and design only**. Do not implement the design. Do not land, abandon, switch, or split a lane in `~/.config/devman`. Do not change a live symlink, a live Nix file, the system profile, or operator policy. Read-only inspection and temporary probes outside managed repositories are allowed. Record every probe and remove its temporary files.

## Outcome required

Produce one reviewable design package in this directory:

1. `DESIGN.md` — the selected architecture, alternatives, ownership boundaries, decisions, risks, and acceptance conditions.
2. `IMPLEMENTATION_PLAN.md` — ordered, independently reviewable steps with owners, prerequisites, commands or interfaces to change, verification evidence, rollback points, and completion criteria.
3. Update `DECISIONS.md` only when new evidence changes a prior decision. Preserve the old decision and record what supersedes it.

End with a short operator decision list. Name the choices that need approval before implementation. Do not stop the investigation to ask those questions; complete all independent research first.

## Problem statement

The central repository `~/.config/devman` is both a tracked configuration repository and a live source for files linked into many repositories. A working-copy rewrite can therefore change running machine configuration before any project check runs.

The 2026-10-01 investigation recorded three silent incidents:

| gitman operation | Observed damage | Detection |
|---|---|---|
| `split` | Removed two live `devenv.local.nix` targets | A later Linkman cutover gate failed |
| `land` | Removed 78 `links.yaml` files from the working copy | A manual count found it |
| `switch` | Reversed an archive change; two retired projects reappeared | A count in another agent's prompt caught it |

The same investigation found that Project 035 had cleaned this repository three weeks earlier. No recurring check or gate stopped the drift from returning. `gitman status` could still report `CANONICAL` while linked targets were missing or lane-only.

The investigation measured 325 live symlink views into the overlay across 66 repositories. Twelve views pointed at content that existed only on `m14-central-residue`. Three of those views were bootstrap Nix files. Three were `.git/info/exclude` projections. A missing bootstrap target can prevent shell entry before a hook can run.

The first report proposed four checks:

| Check | Property | Measured result on 2026-10-01 |
|---|---|---:|
| C1 | Every central `devenv.local.nix` evaluates | 78 files; existing `base:check` passed in 2.58 s |
| C2 | Every live view's target exists | No finding in the measured snapshot |
| C3 | Every live view's target exists on trunk | 12 findings |
| C4 | Every tracked `links.yaml` has its paired `devenv.local.nix` | 10 findings, all dead fixture projects |

Treat every count as a dated observation. Recount it before using it. The follow-up must explain the later correction that 78 Phase A declarations had reached trunk, leaving 77 uncommitted paths across two lanes at the time of the report.

The central detector must not repeat the existing `devman doctor link drift` failure. That check read an empty derived registry after commit `37050e9` removed its input projection. It reported success while 325 live views remained. The detector must use the live view side as its population, or prove another source complete and current.

## Design goals

Choose a design that:

- detects the exact failure classes before shell entry or a working-copy rewrite causes damage;
- has one owner for each predicate and one reusable check implementation;
- uses the correct enforcement point for each gitman operation;
- emits concise findings that name the repository, view, target, and reason;
- uses a fast check that runs often, with a measured cost near the recorded 3.4 seconds;
- keeps checks read-only and safe inside gitman's hook snapshot rules;
- fails with a useful status when it cannot inspect its inputs;
- prevents false success when an input set is empty or stale;
- leaves commits and lands visible and reviewable by a person;
- respects Linkman's topology-only boundary and devman's content ownership;
- preserves the `.devman-link-state.json` hash baseline used to refuse two-sided edits;
- reduces the number of central files that declare the same fact;
- has a clear fallback if gitman cannot guard every risky rewrite.

## Governing rules and constraints

Read the governing documents before deciding. In particular, apply the boundary test in `025-the-link-plane/CONCEPT.md`, the cleanup evidence in `035-config-repo-cleanup/README.md`, Part C of `036-lane-and-charter-audit/README.md`, and the ownership decision in `033-local-gitignore-gitman/README.md`.

Keep these established boundaries unless new evidence proves a conflict:

- The central overlay remains the machine-local root.
- `.git/info/exclude` remains a symlinked projection of a tracked central file.
- Linkman plans purely, inspects read-only, and applies topology only. Devman owns bootstrap content, templates, and target validity.
- Do not use Linkman's `check` as a target-existence check. Its topology result can be correct while the target is dangling.
- The shared devman contract remains closed. Do not add a shared name or path without recording the charter change.
- Keep live bootstrap targets, agent surfaces, and exclude projections tracked unless the charter explicitly changes.
- A `[publish] verify` does not gate `gitman land`. Confirm the current gitman implementation before relying on a hook.
- The central repository has no remote in the 2026-10-01 snapshot. Verify whether that remains true.
- The old `nix flake check` failure, `devman doctor` findings, lane contents, and fleet counts are historical until rechecked.
- Do not solve a permission-classifier denial by moving a shared-config land into an unattended workflow.
- Do not create an unattended commit or land. The charter excludes unattended writes to trunk.

## Read and inspect

Read these in full or inspect the sections that govern each question:

1. This project's `INVESTIGATION_PROMPT.md`, `CONCEPT.md`, and `DECISIONS.md`.
2. devman's `AGENTS.md`, its guide, the `025`, `035`, `036`, `033`, and `015` project records named above.
3. Linkman's `.loci/projects/001-devman-cutover/m14-lanes-8-10-readiness-review.md` and its refactoring guide. Pay special attention to B4, F2, and Q3.
4. The current devman and central-overlay `gitman.toml` files, gitman hook code and tests, and the gitman skill.
5. `devman doctor`'s link-drift implementation, registry projection history, central Nix evaluation task, link reconciler, and ledger pruning code.
6. The current machine's `~/.claude/AGENTS.md` and `~/.claude/CLAUDE.md`, if they still exist. Treat policy changes as a separate decision.
7. Linkman's actual report model and CLI for `check --json`.

Use the manager instructions in each repository. Route version control through gitman. Do not trust a previous shell transcript when the live filesystem can answer the question.

## Revalidate the evidence first

Record a dated baseline before comparing options. Confirm:

- current central trunk, lane tree, parent-child relations, lane diffs, and remote status;
- whether `m14-central-residue`, its stacked child, `m14-central-dead-fixtures`, and the three `parked-paloma-*` lanes still exist;
- current live reverse-index count, including `.agents`, `.claude`, `.envrc`, `devenv.local.nix`, `.git/info/exclude`, and `.loci` views;
- how many live targets are absent, present only in a lane, or present on trunk;
- how many tracked `links.yaml` files lack a live project or paired bootstrap file;
- whether the central `base:check` still evaluates all required Nix files, can fail, and runs within a few seconds;
- whether `devman doctor link drift` still has an empty input or now has a complete source;
- current `.devman-link-state.json` counts and whether every live repository still has its recorded baseline;
- whether the `~/.claude` files are still separate copies and what content each has;
- current `devman doctor`, `base:check`, and `nix flake check` results. Record failures as evidence; do not repair them in this session.

For each result, give the command or source file and line. Separate measured facts, inferences, and recommendations.

## Compare these solution families

Evaluate each option against correctness, complexity, runtime, false-positive risk, ownership, operator visibility, and recovery cost.

| Family | Description | Main question |
|---|---|---|
| A. Auto-adopt and auto-land | A workflow discovers drift, creates a commit, and advances trunk | Can it separate valid generated content from unrelated edits and fixture residue? Does the charter permit it? |
| B. Detect and refuse | A fast read-only check reports drift; a gitman pre-hook blocks unsafe lands | Does this stop recurrence while keeping the decision and diff reviewable? |
| C. Protect working-copy rewrites | gitman calls a devman predicate before operations that can remove live targets | Which verbs need a guard, and can one generic hook cover them cleanly? |
| D. Reduce drift at the source | Generated outputs become untracked or a single declaration source replaces duplicate declarations | Which outputs are truly generated, and which must remain tracked for recovery and review? |
| E. Use the existing doctor or workflows | Extend a current health check or scheduled workflow | Is its input complete, is the central overlay addressable, and will a failure reach an operator? |

Recommend a composed design if no single family covers detection, enforcement, and recurrence. Reject options with a measured reason or a named charter conflict.

## Decisions to resolve

Carry these eight open questions forward. The listed positions are hypotheses from the prior design discussion. Verify them and either adopt or replace each one.

| ID | Decision | Provisional position to test |
|---|---|---|
| O1 | What should happen to the parked central lanes? | After fresh inspection and operator review, fold `m14-central-residue+retire-foreman-my-ai` into its parent, then land the residue. Abandon dead fixture output only after proving no live view consumes it. Remove dead fixture declarations in a separate named change. Do not execute these steps in this session. |
| O2a | What gates a land in the central overlay? | Use `[land.pre_hook]` for C1, C2, and C4. Use a post-land check for C3 because a successful land may be the action that cures lane-only targets. Keep the hook read-only. |
| O2b | What gates a land in the devman source repository? | Keep `nix flake check` under `[publish] verify`. Add a separate, fast `[land.pre_hook]` using the existing passing `base:check`. Add `doctor` only after its findings are resolved and its result is useful. Do not confuse this gate with the central-overlay gate. |
| O3 | How should `links.yaml` and `devenv.local.nix` relate? | Keep declarations in `links.yaml`. Retain a minimal central Nix file only if it provides the required shell-entry reconcile trigger. Remove declarations duplicated in that file. Reconcile this with Linkman's cutover Q3 before changing either repository. |
| O4 | Which gitman verbs need a rewrite guard? | Ask gitman for a generic, domain-neutral pre-rewrite hook. The guard must cover every operation that can remove lane-only live targets. Check `split` as well as `switch` and `abandon`; incident 1 was a `split`. Have devman answer whether any live target is lane-only. Do not make gitman understand links or compute domain paths. |
| O5 | How should stale ledger entries be pruned? | Extend the existing prune path only if repository-directory presence is a safe liveness gate. Never prune a live repository's hash baseline because it is absent from the derived registry. Prove two-sided-edit refusal still works after pruning. |
| O6 | Should this work repair `~/.claude/AGENTS.md`? | Treat it as a separate, later link-plane change. Test a tracked canonical file at `~/.config/devman/common/claude-agents.md`, `~/.claude/AGENTS.md` pointing to it, and `~/.claude/CLAUDE.md` pointing to `AGENTS.md`. Do not link the whole `~/.claude` directory, which contains private session data. |
| O7 | Does Linkman's check report enough to callers? | Hand off a bounded reporting issue. Consider exposing target kind/usability and a distinct missing-config result while keeping apply topology-only. Do not make the central safety design depend on a Linkman change. |
| O8 | Did the link-plane restructure preserve required behavior? | Audit 025 §10 items 2 and 13 against current code and tests. The former cites the removed `modules/devenv.nix`; the latter concerns worktree-aware exclude writes. Record whether enforcement moved, weakened, or disappeared. |

Also resolve the schedule and ownership question: a nightly check was proposed, but the central overlay is not a registered devman project in the old snapshot. Identify a real runner and a delivery path that does not rely on a report nobody reads. Do not add a shared workflow parameter or project fact without applying the charter boundary test.

## Provisional recommended design

Use one devman-owned, read-only predicate named `central-verify` as the source of truth for central overlay health. Build its live population from symlinks on disk that point into the overlay. Do not trust the active registry or `.devman-link-state.json` as a complete inventory.

Keep these checks distinct:

| Phase | Checks | Effect |
|---|---|---|
| Before central `land` | C1, C2, C4 | Block a land that adds invalid or incomplete central content |
| After central `land` | C3 | Report whether every live target now exists on trunk; do not imply rollback |
| Before a risky rewrite | C3 | Refuse `switch`, `split`, or `abandon` when live views depend on lane-only content |
| Scheduled health run | C1–C4 | Report recurrence with actionable paths and an owner; write nothing |

Reuse the existing Nix evaluator for C1 instead of adding a second validator. Prove how the system-profile `devman` command can invoke it without depending on an interactive shell. Preserve a single implementation if the evaluator must move.

Keep the enforcement split explicit:

- **devman owns the predicate.** It knows which filesystem views point into the overlay and what target availability means.
- **gitman owns the hook point.** It knows when a lane operation will rewrite the working copy. It passes a generic event and blocks on a non-zero result.
- **The operator owns adoption and landing.** A workflow may detect and explain drift. It must not commit or land it unattended.
- **Linkman owns topology.** It may improve its report, but it does not decide whether a central target exists or is safe to remove.

Keep `links.yaml` as the declaration source. Keep only the smallest Nix shell-entry trigger needed after the cutover removes the `devman.link` attribute set. Make generated-only router files untracked only after proving that regeneration is deterministic and that no required recovery file becomes untracked.

Treat the gitman rewrite hook as a separate dependency. Until it ships, keep C3 at zero before any navigation or partition operation in the central repository. State this fallback in the operator-facing gitman guidance and measure it in the scheduled check.

Do not select auto-adopt and auto-land as the default. The 2026-10-01 counterexample combined intended declarations with dead fixture output and shared skill edits. A lane can carry a name and diff, but an unread lane can still produce a quiet-success failure. Automate detection and refusal, not trunk writes.

## Required implementation plan

Write the plan in this order. Reorder only when a dependency or safety finding requires it.

### Phase 0 — Refresh and classify the baseline

1. Re-run the evidence table above. Mark each prior number current, changed, or unverifiable.
2. Reconstruct the exact lane tree and current contents. Use gitman status and dry-run output; do not run a mutating gitman verb.
3. Reproduce C1–C4 as read-only probes. Record all paths and elapsed time.
4. Identify every live target that depends on an unlanded lane. Name the failure if it disappears.
5. Produce a short risk statement and list any operator action that cannot wait for implementation.

**Complete when:** the current exposure is exact, reproducible, and understood without editing the central repository.

### Phase 1 — Review and resolve the parked-lane plan

1. Compare the residue lane and its stacked child against current trunk.
2. Confirm whether the child contains only the intended archive renames.
3. Confirm whether the fixture lane has no live consumers and whether its files are absent from disk.
4. Generate dry runs for the proposed order: fold child, land residue, abandon dead fixture lane, then remove dead fixture declarations in a separate lane.
5. Document the exact operator review point. Do not perform the operations during the design session.

**Complete when:** every proposed operation has a reviewed diff, a clean dry run, a recovery path, and explicit operator disposition.

### Phase 2 — Specify `central-verify`

1. Define the live-view scan, including symlink depth, paths under `.git/info`, and links in repositories without a devman manifest.
2. Define C1–C4 and the phase-specific set for pre-land, post-land, pre-rewrite, and scheduled runs.
3. Define status semantics: success, finding, infrastructure/configuration error, and invalid invocation. Do not map an empty scan to success unless the scan proves that zero views is valid.
4. Define deterministic text and JSON output. Each finding must identify the repository, view, canonical target, failing condition, and next action.
5. Set and measure a runtime budget. Target the observed few-second run; explain any cost above it.
6. Prove the command is read-only, including gitman hook snapshot behavior.
7. Specify tests for absent targets, lane-only targets, fixture projects, missing declarations, empty or unreadable roots, and symlink loops.

**Complete when:** one pure predicate answers all central health questions, with no authority split between the registry, ledger, and filesystem.

### Phase 3 — Repair the existing doctor path

1. Trace how `doctor link drift` gets its input today.
2. Replace the empty registry projection as the authority, or have doctor call the shared central predicate.
3. Keep `doctor` useful when the central overlay is absent, unreadable, or not configured.
4. Add regression evidence for the 2026-09-19 input-loss failure.

**Complete when:** the doctor check can detect a deliberately broken live view and cannot report clean from an empty stale source.

### Phase 4 — Add the central land gate and scheduled detection

1. Configure the central overlay's `[land.pre_hook]` to run pre-land checks.
2. Configure its post-land check to report C3 after a fold. Test the actual hook exit semantics and output with the installed gitman version.
3. Keep the hook command available through the system profile. Verify missing-command and timeout behavior.
4. Select the smallest valid scheduler for the central overlay. Name the trigger, invocation context, owner, report destination, and failure visibility.
5. Run the scheduled check once on a known-clean and a known-failing fixture. Confirm it sends no writes and creates no duplicate noise.

**Complete when:** a malformed or incomplete central change blocks before trunk advances, and recurrence produces one actionable report.

### Phase 5 — Add the devman source-repository land gate

1. Recheck the current `devman/gitman.toml`, `base:check`, `base:unit`, `base:test`, and `devman doctor` results.
2. Keep the slow hermetic check under publish verification if it remains valid there.
3. Add only a fast, passing land gate first. Do not make `land` depend on a known-red or hour-long check.
4. Add broader doctor or unit checks only after they have a stable, understood result and acceptable runtime.

**Complete when:** every devman land runs a check that can fail on a devman source defect and is cheap enough for normal use.

### Phase 6 — Protect all risky working-copy rewrites

1. Inspect gitman's implementation for `switch`, `split`, and `abandon`, plus any other operation that can remove files from the active working copy.
2. Ask gitman for a generic pre-rewrite hook with a stable event and fail-closed behavior. Keep link semantics out of gitman.
3. Attach the devman C3 predicate to every relevant verb. Do not guard only `switch`; the recorded deletion came from `split`.
4. Test refusal before the rewrite, success when all views point to trunk, and unchanged filesystem state on refusal.
5. Keep C3 = 0 as the fallback until this support lands and is configured.

**Complete when:** no supported navigation or partition operation can remove a live central target without a refusal first.

### Phase 7 — Reduce duplicate and unobserved state

1. Decide the minimal central Nix trigger required after the link cutover. Keep declarations in `links.yaml` and remove duplicate declarations only after the trigger is proven.
2. Classify each generated file as authored, derived but recoverable, or machine state. Untrack only deterministic outputs that can be regenerated safely.
3. Extend `doctor --prune` for the link-state ledger only if directory-based liveness preserves every live hash baseline.
4. Prove the two-sided-edit refusal before and after pruning with a fixture. Record ledger counts before and after.

**Complete when:** no declaration has two authorities, generated churn is removed safely, and pruning cannot erase a live refusal baseline.

### Phase 8 — Close policy and cross-project findings

1. Plan the `~/.claude` canonical file and two file links as a separate change. Merge the missing lane policy and current skill path only after checking both source files.
2. Audit 025 §10 items 2 and 13 against current code, tests, and call sites. Record any weakened invariant.
3. Write a bounded Linkman handoff for O7. Do not change Linkman's contract as part of central verification.

**Complete when:** policy has one canonical source, preserved charter requirements have evidence, and the Linkman reporting issue has a named owner and scope.

### Phase 9 — Roll out in small lanes

1. Land the detector and its tests before enabling hooks.
2. Enable the central pre-land gate and scheduled run. Observe a full normal cycle.
3. Enable post-land reporting and verify its meaning to operators.
4. Add gitman rewrite hooks only after the generic hook is released and tested.
5. Apply structural cleanup and ledger pruning in separate, reversible lanes.
6. Recount the fleet and C1–C4 after each rollout stage.
7. Update the concept, operator guidance, and acceptance checklist from the final evidence.

**Complete when:** the system detects a recurrence, refuses unsafe rewrites, stays read-only outside named lanes, and has no silent-success path.

## Final acceptance criteria

The design package is complete only when it provides:

- a current dated baseline and a clear statement of what changed since 2026-10-01;
- a comparison of the solution families and a defended recommendation;
- a single source for each predicate and a named owner for each hook;
- an explicit policy for land, post-land, scheduled checks, and working-copy rewrites;
- a gate that can fail and a report that reaches an operator;
- a measured runtime and an explanation of failure exit codes;
- a safe plan for each O1–O8 item, including deferrals and handoffs;
- an ordered implementation plan with prerequisites, review points, rollback paths, and completion evidence;
- a precise list of actions that still require operator approval.

Do not call the problem solved because the current C3 count is zero. The design must keep it at zero and detect when it rises again.
