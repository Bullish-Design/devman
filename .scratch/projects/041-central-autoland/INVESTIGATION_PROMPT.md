# Task: investigate and concept a devman mechanism for central-config drift and lane safety

You are starting a new project. This session is **investigation and concepting
only**. Produce a concept document and a decision log. Do not implement a
workflow, do not land a lane in `~/.config/devman`, and do not change a live
symlink or a Nix file.

## The problem, in four numbers

On 2026-10-01, during Linkman's Milestone 14 cutover, the central configuration
repository `~/.config/devman` was found holding **155 uncommitted paths**. 78 of
them were the entire output of the cutover's Phase A — the `links.yaml` files
that a later milestone step checks as a precondition. They existed only in a
dirty working copy. The repository reported **CANONICAL** and clean the whole
time.

**Project 035 cleaned this same repository on 2026-09-10.** Three weeks later it
had re-accumulated. A one-off cleanup did not hold, and that recurrence — not
the mess itself — is what this project exists to answer.

Three further numbers from the same session:

- **Three separate working-copy incidents**, each silent, each a different kind
  of damage (listed in "Evidence" below).
- **Zero** verify steps in that repository. `~/.config/devman/gitman.toml` is one
  line: `trunk = "main"`.
- **Six** devman workflows exist. **None** touches the central overlay.

## Read first, in this order

1. `AGENTS.md` in this repository, in full. Property 10 is the boundary test,
   property 6 is the three-root registry picture, and the write-tier table near
   the end (`free` / `lane` / `insitu`) is the framework this project should
   extend rather than reinvent. Note what it already says: **"An unattended
   write to trunk has no tier, and it is the one shape to keep out of a
   workflow: it appears in somebody's `git status` the next morning with nothing
   to explain it."** That is a verbatim description of what happened. The
   charter predicted this failure and nothing enforces it.
2. `.scratch/projects/025-the-link-plane/CONCEPT.md` — §2 P0 (the boundary
   test), §5 (the link plane), §6.2a (render-to-link, **deferred**, and why),
   §7 (the agent surface), §10 (what must be preserved). This is the governing
   charter for anything touching the central overlay.
3. `.scratch/projects/035-config-repo-cleanup/README.md` — **the most important
   prior art.** Same repository, same class of problem, 2026-09-10. Read its §1
   executive result in full. It found that the assumed diagnosis was wrong three
   times over, that two raw `git commit` invocations had bypassed gitman, and
   that the real problem was not loss risk but that committing as-is would
   enshrine a charter violation. Do not repeat its investigation; build on it,
   and ask why its fix did not hold.
4. `.scratch/projects/036-lane-and-charter-audit/README.md` — lane hygiene
   closure, 15 orphaned lanes abandoned, and the `.local.gitignore` ownership
   decision. Part C is binding.
5. `.scratch/projects/033-local-gitignore-gitman/README.md` — how
   `.git/info/exclude` became a symlinked projection of a tracked central file,
   and the two-sided-edit refusal. That refusal depends on a recorded hash
   baseline, which matters to this project (see Evidence item 6).
6. `.scratch/projects/015-what-the-plane-should-do/` — where the write tiers
   come from.
7. `~/.claude/CLAUDE.md`, the "Version control lanes" section — the operator's
   standing policy: *"land and push a lane by default once its verify step
   passes — do not stop to ask first,"* with carve-outs for a failed verify, a
   lane touching shared or risky files, a merge conflict, or an instruction to
   review first.
8. The gitman skill, and `gitman --help`. Know the real verb list before
   designing around it. Project 035 recorded that gitman ships **no** `diff`,
   `show` or `reflog` verb; confirm whether that still holds, because it shapes
   what a check can be built from.
9. For the live case study: in the `linkman` repository,
   `.loci/projects/001-devman-cutover/m14-lanes-8-10-readiness-review.md` and
   `m14-lanes-8-10-refactoring-guide.md`. You do not need the cutover's detail,
   only its §1.4 census and the blockers that touch the central repository.

## Evidence carried forward from 2026-10-01

Verify each against the live machine before building on it. Do not rediscover
it from scratch.

1. **The three working-copy incidents.** All silent. All in `~/.config/devman`.
   In none of them did `gitman status` or `git status` report a problem.

   | # | Operation | Damage | What caught it |
   |---|---|---|---|
   | 1 | `gitman split` | **deleted** two live bootstrap targets, `projects/{linkman,mnemonix}/devenv.local.nix` | the Linkman cutover gate failed with `bootstrap central target does not exist` |
   | 2 | `gitman land` | 78 `links.yaml` left the working copy until a `gitman sync` | counting them by hand |
   | 3 | `gitman switch` | **reverted a completed change** — `projects/.archive/` vanished and two retired projects reappeared | a count in a subagent's prompt, which the subagent correctly refused to proceed past |

   The common cause: in a colocated jj repository the working copy **is** a
   commit, so moving between lanes rewrites the tree. Content held only in an
   unlanded lane leaves the disk. This repository's files are **live symlink
   targets for 65 real repositories**, so a working-tree rewrite is a
   live-system event. Incident 1's class is the dangerous one: Nix reads
   `devenv.local.nix` before any shell hook runs, so a dangling one fails shell
   entry with a trace nothing can intercept.

2. **Nothing in the repository can fail.** `gitman.toml` is `trunk = "main"`,
   with no `[publish] verify`. Compare this repository's own `gitman.toml`,
   which has `verify = ["nix", "flake", "check"]` and `verify_timeout = 3600`.
   The operator's policy fires *"once its verify step passes"*; with no verify
   step that precondition is undefined, so "land by default" is unactionable in
   the one repository where the drift accumulated.

3. **The 155 paths were never in a lane.** gitman reported `working copy @ has
   unbookmarked work`. The policy governs lanes, so it never engaged. Automatic
   *landing* would not have swept them. Automatic *adoption* would have
   bundled Phase A's output with ten projects of docman test residue and two
   shared skills edits into one unreviewed commit.

4. **The permission classifier and the operator's policy collide here.**
   `gitman land` on the live-content lane was denied by Claude Code's auto mode
   classifier with reason *[Modify Shared Resources]*. That is defensible — the
   lane lands 59 paths of live machine configuration — and it coincides exactly
   with the policy's own "shared or risky files" carve-out. Any design that says
   "land automatically" must say what happens at this collision.

5. **`~/.claude/AGENTS.md` is missing the entire "Version control lanes"
   section** that `~/.claude/CLAUDE.md` carries. Claude Code reads CLAUDE.md and
   gets the policy; a tool reading AGENTS.md does not. The two files also
   disagree on a skill path (`my-ai/SKILL.md` versus `writing/SKILL.md`). Decide
   whether this project owns that fix or only reports it.

6. **`.devman-link-state.json` survives the Linkman cutover.** It is gitignored,
   and `excludes.py` reads a recorded `{canonical, hash}` baseline to refuse a
   two-sided edit of the exclude projection. A design that regenerates or
   discards central state must not break that refusal. `devman doctor --prune`
   does **not** cover this file; it prunes the derived registry
   (`doctor.py:422 check_stale`).

7. **No workflow touches the central overlay.** Six exist: `agent`, `check`,
   `maintain`, `format`, `release`, `test`. Confirmed by grep for
   `config/devman`, `overlayDir` and `central` across `groups/*/workflows/`.

## The state you will find

`~/.config/devman` has **two unlanded lanes left mid-operation**, deliberately,
because landing was blocked:

```
trunk: main @ 268c0a3
  m14-central-dead-fixtures   draft  18 paths  — dead docman/roundtrip fixtures, parked on purpose
* m14-central-residue         draft  59 paths  — LIVE central content, described, awaiting land
    m14-central-residue+retire-foreman-my-ai  draft  — stacked; retires two archived projects
  parked-paloma-*  × 3        — unrelated, do not touch
```

**The 59 paths on `m14-central-residue` are live symlink targets that exist only
in that lane.** Until it lands, incident 1's hazard is live. Treat this as the
project's first piece of evidence, not as a chore: whatever you design should be
able to detect and explain this exact state.

Do not land these lanes without asking the operator. They are the worked example.

## What to produce

Two documents in this directory, in the house style of
`035-config-repo-cleanup/README.md` and `036-lane-and-charter-audit/README.md`:

- `CONCEPT.md` — the design. Problem statement with measured numbers, the
  mechanism, what it refuses and why, where it sits in the four planes, the
  boundary-test justification for every placement, stated limits, and what you
  could not determine.
- `DECISIONS.md` — each decision, the alternatives rejected, and the
  measurement or charter clause that forced it.

## The questions to answer

Answer these from the machine and the charter, not from first principles.

**A. What is the failing-capable check?** Design a verify step for
`~/.config/devman`. At minimum it must fail when a declared link target is
missing from disk. Decide what else belongs: a dangling-symlink sweep across the
65 live repositories, a check that every central project with a `links.yaml`
also has its `devenv.local.nix`, a tracked-but-gitignored sweep (this repository
already reports that class on itself). Say what it must **not** do — an
expensive check nobody runs is the same as no check.

**B. Where does the check live, and who runs it?** Candidates, each with a
charter consequence: `gitman.toml`'s `[publish] verify`; a devman `check`-group
workflow for the central repository; `devman doctor`, which already has a
`link drift` check; a new per-repository hook. Apply the boundary test (property
10) to each. Note that `[publish] verify` only gates `publish`, and this
repository **has no git remote** — so establish whether it gates `land` at all,
and if not, say what does.

**C. What should the write tier be for machine-generated central content?** The
tier table has `free`, `lane` and `insitu`. Promoted agent surface, converted
`links.yaml`, and `repoman install-skills` output are all written by automation
into a tracked repository. Decide whether they are `insitu`, a new tier, or
should be gitignored and never tracked. §7.2/§7.3 of the link-plane charter
mandates relative symlinks into the central pool, and project 035 found 62 files
that were real copies instead — so answer this in a way that does not re-create
035's charter violation.

**D. Should a workflow commit and land central drift automatically?** This is
the operator's actual question. Give a recommendation with the trade-offs. Weigh
at least: that the 155 paths were unbookmarked rather than a lane; that
automatic adoption bundles unrelated work (the measured counterexample above);
that an unattended write to trunk has no tier by the charter's own rule; that a
lane carries a name and a diff and a human can read it; and that the plane's
criterion 4 is *"a run that reports success while producing an incorrect result
is the failure this design exists to prevent."* An automatic lane that nobody
reads may satisfy the letter and fail criterion 4.

**E. How does the design handle the lane-switch hazard directly?** A verify step
run at land time does not protect a `switch` or a `split`. Decide whether this is
in scope, and if so what mechanism covers it. Consider whether live link targets
should be tracked-and-stable with generated content gitignored, which would
shrink the hazard structurally rather than detecting it. If it is out of scope,
say so and say who owns it.

**F. What does the design do at the permission-classifier collision?** Evidence
item 4. A mechanism that is silently blocked in practice is not a mechanism.

**G. Is any of this gitman's job rather than devman's?** gitman is the
lane-based VC tool. A check that refuses a `switch` which would delete a live
symlink target might belong in gitman, not in a devman workflow. Say which, and
why, and what it would cost each side. Do not assume devman.

## Constraints

- **Do not re-litigate settled decisions.** Binding: the boundary test (025 §2
  P0); `.local.gitignore` ownership (036 Part C); the central overlay as the
  machine-local root; `.git/info/exclude` as a symlinked projection (033);
  render-to-link stays deferred (025 §6.2a) until its safety property is proven.
- **The shared contract is closed.** Six queue names, `DEVMAN_PROJECT_DIR`,
  `DEVMAN_SELF_DIR`, and the `.devman/.runs/` path shape. Adding a shared name
  changes the charter; weigh it that way and say so explicitly if you propose
  one.
- **Do not design around a Linkman change.** Linkman is mid-cutover and its
  boundaries are fixed: no durable state, no policy in `fs.py` or `manifest.py`,
  planning pure, inspection read-only, apply topology-only. D5 keeps the exclude
  projection, template rendering and bootstrap content in devman.
- **A check that cannot fail is not a check**, and a report nobody opens is not
  a report. The plane has measured both: `devenv test` exited 0 having tested
  nothing in 30 of 58 repositories for a month, and 54 identical reports is one
  report nobody opens.

## How to work

- Run everything inside the devenv shell of the repository you are reading.
  Never invoke bare `uv`, `python`, `pytest`, `ruff`, `git` or `jj` for a
  mutating operation. Read-only `git diff --name-only` / `git ls-files` for
  inspection is acceptable and project 035 disclosed the same choice with its
  justification — do likewise.
- Route all version control through gitman. This repository's verify commands
  are its own — `devenv tasks run -v base:check`, `base:unit`, `base:test`
  (= `nix flake check`), and `devman doctor`. **devman does not use Testee**,
  whatever the older documents say. Pass `-v`: `devenv tasks run` without it
  prints `{}` and hides the result.
- Note before you start: `nix flake check` in this repository is currently
  **red**, and has been since the cutover's Lane 2. The `python-tests` check's
  fileset omits `./tools`, so three test files cannot import. It is a known,
  recorded blocker owned by the Linkman cutover, not by you. Do not fix it, and
  do not treat it as your own failure signal.
- The shell is zsh. Unquoted `$VAR` does not word-split.
- Write in Simplified Technical English: short sentences, active voice, one term
  per meaning, no filler.
- When a planning document and your judgment conflict, follow your judgment and
  say so in the document. Project 035 is the local precedent: it corrected two
  earlier reports and said which sections it superseded.

## Report at the end

The two documents, plus:

1. A one-paragraph answer to question D — should a workflow auto-land central
   drift — with your recommendation stated plainly.
2. The verify step you designed for question A, concretely enough to implement,
   and whether it actually gates `land` on a repository with no remote.
3. Your answer to question G: devman's job, or gitman's.
4. Why project 035's cleanup did not hold three weeks later. This is the
   question the whole project turns on, and a design that does not answer it
   will not hold either.
5. The full list of open questions needing an operator decision.

Do not implement a workflow. Do not land the two waiting lanes.
