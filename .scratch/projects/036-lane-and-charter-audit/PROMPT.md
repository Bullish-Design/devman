devman full-state audit: in-flight lanes, orphaned lanes, and the link-plane
charter's open questions.

# Context

Session 035 (`.scratch/projects/035-config-repo-cleanup/README.md`) closed out
the `~/.config/devman` cleanup and the fleet-wide link-plane rollout: 44 of 49
repositories migrated, 12 repos' `.claude/skills` drift resolved, 5 stragglers
fixed or documented, `my-ai` retired as a devman project and moved to
`~/Documents/Projects/.archive/my-ai`. That work is done and pushed. Nothing
below depends on it beyond using the same conventions.

This prompt starts a **new investigation**, not a continuation. Read this file,
then work through Part A, B, and C in order. Each part stands alone — stop
between parts and report findings before acting further if anything is
ambiguous or destructive.

# Ground rules (same as 035, restated because they matter)

1. **Route every VC action through gitman.** Never raw `git`/`jj`, except
   read-only inspection (`status`, `diff`, `log`, `show`) when gitman has no
   equivalent verb.
2. **`gitman start` adopts the whole dirty working copy into a lane** — not
   just the paths you meant to touch. Before landing anything, run
   `git status --short` and confirm every file belongs to your change. If
   unrelated pre-existing work is mixed in, use `gitman split --paths <sel>
   --into <lane>` to carve it out, or `gitman undo --op <id>` back to before
   you touched the repo and leave it alone.
3. **A repo with a large amount of unrelated pre-existing dirty state is not
   yours to land.** If entering a lane sweeps in hundreds of files or a
   diff in the tens of thousands of lines that isn't about your task, back out
   and report it instead of forcing a resolution.
4. **Verify before you save**: `devenv tasks run -v base:check` in devman
   itself; `devman doctor` must exit clean of new findings your change
   introduces (pre-existing findings unrelated to your change are not yours to
   fix unless Part C asks you to).
5. **Isolate risky or exploratory work in a `--workspace` lane**
   (`gitman start <name> --workspace` / `gitman subtask <leaf> --workspace`)
   so the primary checkout's working copy is never at risk.
6. Per the user's standing law (`~/.claude/CLAUDE.md`): land and push a lane by
   default once verify passes — don't stop to ask first, unless the lane
   touches something unusual (conflicts, shared/risky files, or you're
   genuinely unsure the content is safe to land).

# Part A — Audit the 5 in-flight lanes

As of 2026-09-11, these lanes exist, each checked out in its own workspace,
none landed into `main`:

| Lane | Type | Diff size | Top commits |
|---|---|---|---|
| `031-audit-doc-corrections` | published, `ws 031-audit-doc-corrections` | +80 −22 | `docs: align central overlay audit findings` |
| `032-link-plane-hardening` | published, `ws 032-link-plane-hardening` | 2 changes, +790 −137 | `fix: centralize per-project git exclusions`, `Harden link-plane reconciliation` |
| `034-stage-3-readiness-audit` | draft, `ws 034-stage-3-readiness-audit` | +898 −7 | `Stage 3 readiness audit: fix link-plane bootstrap bug, document findings` |
| `review-009-code-review` | draft | +1057 −0 | `Add deep devman code review` |
| `preexisting-draft` | draft | +252 −0 | undescribed, sits on the codec-rollout merge |

For each lane:

1. `cd` into its workspace (`.worktrees/<lane>/` for the `ws` ones; `gitman
   switch <lane>` for the rest) and read the full diff and any `.scratch/`
   project doc it belongs to.
2. Determine: is this **done and just needs landing**, **abandoned and safe to
   discard**, or **genuinely mid-work**? Each of the three needs a different
   action — do not assume "old" means "safe to drop."
3. **`032-link-plane-hardening` matters most for Part C.** Its subject line
   ("Harden link-plane reconciliation", "centralize per-project git
   exclusions") suggests it already addresses some of what session 035 found
   the hard way (the `.git/info/exclude` pattern, the `docman` self-reference
   break, the `agents/pi/` runtime-state leak). Read it **before** touching
   anything in Part C that overlaps — you may be about to redo work that's
   already sitting here unlanded, or this lane may need updating for what 035
   found that it didn't know about.
4. **`034-stage-3-readiness-audit`** is exactly what it says: readiness for
   Stage 3 of `025-the-link-plane/CONCEPT.md` §11 (moving `registryDir` from
   `~/.local/share/devman` to `~/.config/devman`, splitting config from
   state). Confirmed today: Stage 3 has **not** shipped — the registry is
   still at `~/.local/share/devman/projects/`, `stateDir` doesn't exist. Read
   this lane's findings before touching Stage 3 in Part C.
5. Land what's ready (`base:check` first), report and hold what's ambiguous,
   propose disposal for anything confirmed stale — don't unilaterally abandon
   a lane with real content without saying so first.

# Part B — The 15 orphaned lanes

`gitman status` lists these as `ORPHANED (name-parent '<X>' gone — gitman
reconcile)`:

```
docs/001-recharter-concept
docs/002-recharter-spikes-and-split
docs/003-cli-schema
fix/009-stage-1-trigger-refusals
fix/009-stage-2-watcher-ownership
fix/009-stage-3-producer-refactor
fix/009-stage-4-registry-faults
fix/009-stage-5-identity-grammar
fix/009-stage-6-nix-assertions
fix/009-stage-7-daemon-shell
fix/009-stage-8-real-projection
fix/009-stage-9-comments-and-triggers
perf/012-dagu-call-performance
spike/007-gate-2
spike/agent-factory-round-trip
```

All show `+0 −0` in `gitman status` except `spike/agent-factory-round-trip`
(292 behind trunk) — check that one's actual diff specifically, its size in
the status line doesn't mean its content is empty, only that its last-known
diff-vs-base was zero at last measurement.

Their `/`-path name-parent (`docs`, `fix/009`, `perf/012`, `spike`) was
deleted outside gitman at some point, orphaning the children. For each:

1. Check whether its content already landed on `main` via another path (same
   method used in this session to verify lane `030-documentation-audit`:
   `git diff main <lane-branch> --stat` — empty means already absorbed).
2. If already absorbed: safe to `gitman reconcile` (re-roots or drops the
   orphan) or abandon explicitly.
3. If not absorbed: it's real, stale work. Report what it is before deciding
   whether to land, rebase onto current trunk, or abandon.

`fix/009-stage-*` (9 lanes) look like they map to the nine stages of project
`009` (find `.scratch/projects/009-*/` for the plan) — check whether project
009 is already fully landed elsewhere; if so these 9 are very likely pure
debris safe to drop after the empty-diff check confirms it.

# Part C — The link-plane charter's open questions

`.scratch/projects/025-the-link-plane/CONCEPT.md` §13, "What I could not
determine," lists six items verbatim below. Investigate in the order given —
items 2 and 5 are the ones the user specifically asked about this session.

**1. Whether `.claude/settings.local.json` survives linking without renaming
on save.**
> Settled by: linking one repository's file, approving one permission,
> running `test -L`. Do this before Stage 2 — if it fails, hoist the shared
> allowlists to `~/.claude/settings.json` and leave the per-repo files alone.

Stage 2 (the `devman.link` option + reconciler) is long since shipped, so this
should have been settled already — check whether it actually was, and if not,
run the test now. It governs how *many* per-repo settings files are safe to
centralize going forward.

**2. Whether `cliProvider = "store"` works — Stage 5, the vendomat question.**
> Settled by: `nix build .#repoman-toolchain-core` in vendomat, then one
> repository entering a shell under `store` and running `repoman doctor`.
> The whole Stage 5 argument rests on it.

This is the "vendomat becomes the source of all dependencies" question from
this session. Full Stage 5 text is `CONCEPT.md` §11: flip `cliProvider` to
`store` by default, repoman imports vendomat's toolchain, run one release,
then merge vendomat's `lib/` into repoman. Run exactly the settling test
above on **one** low-stakes repository first — do not flip the fleet default
without that proof. Also account for what `devman doctor` already flagged
today: vendomat's own `.devenv` cache is 122 MB and gets copied into every
consuming project's build under `path:` inputs — measure whether `store`
mode changes that cost before recommending the flip.

**3. Whether agentman's zero-consumer state means "new" or "wrong."**
> First commit 2026-09-08. The `devman-agentman/v1` contract is shipped on
> agentman's side and unadopted on devman's (`agentman/AGENTS.md:87-93`).
> Settled by: devman adopting `groups/agent/` and one repository running a
> real capsule.

Read `agentman/AGENTS.md:87-93` for the contract shape, then check whether
`groups/agent/` exists in devman yet.

**4. Whether `copyroom/_compat/gitutil.py` can shrink.**
> 348 lines of subprocess git in a family whose VCS tool reduced its raw-git
> surface to zero. Settled by: a call-graph over `workshop/` versus
> `project/`. If the workshop is the only caller, the duplicate is smaller
> than it looks.

Lowest priority of the six — a code-size question, not a behavioral one.

**5. Whether devman's lock readers produce noise against the new tree.**
> `check_local_sources` (`devman/src/devman/doctor.py:1061`) and
> `check_path_inputs` (`:1138`) both read `devenv.lock` across the registry.
> Flagged in `024-personal-overlay/CONCEPT.md` §5.5 and still unverified.

There is now real data on this from session 035: `devman doctor`'s
`local sources` and `path inputs` checks fired constantly during the fleet
migration — `repoman`/`shellij`/`vendomat`/`pyjutsu`/etc. flagged as
"uncommitted changes, consumed unpinned," `pytuin` flagged pinning `atuout` at
a stale rev, `vendomat`'s 122 MB `.devenv` flagged under path inputs. Read
`doctor.py:1061` and `:1138` against that lived experience: is the noise
signal or false-positive? This item may already be settled by evidence
sitting in this session's own transcript and `/tmp/migrate-fleet.log` history
— check before re-deriving it from scratch.

**6. How often a promote conflict happens.**
> §5.4 refuses when both sides moved. Whether that is rare or constant
> depends on how often the central copy is edited directly, and there is no
> data yet.

**This one is now measured.** Session 035 hit real promote refusals:
`.claude/skills` refused to promote in 12 of ~46 migrated repositories
(`argentic`, `fleetman`, `flora`, `flora-core`, `loci-core`, `loci.nvim`,
`nix-desktop`, `nix-nvim`, `nix-paseo`, `nix-secrets`, `poddantic`,
`vendomat`) — not because of genuine two-sided edits, but because of a
`state.get(link.key)` gap in `devman/src/devman/link.py:308-317`: promoting a
*second* view (`.claude/skills`) onto a canonical path already created by a
*first* view's promotion (`.agents`) always refuses, since there's no prior
recorded hash for the second view specifically, regardless of whether content
actually differs. Read `link.py:295-330` and confirm this reading, then decide
whether it's worth fixing at the source (record the hash under the canonical
path, not the view, so either link recognizes prior promotion) rather than
requiring the manual per-repo remediation 035 had to do by hand.

# What to produce

For each of Parts A, B, C: a short report — what's done, what's live, what's
dead, what you landed, what you're holding for a decision — before moving to
the next part. Don't silently land ambiguous lanes. Don't silently abandon
lanes with real, unabsorbed content.
