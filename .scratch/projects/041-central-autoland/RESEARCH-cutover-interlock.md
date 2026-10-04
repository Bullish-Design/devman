# Research: the Linkman cutover and the central guard, mapped against each other

Date: 2026-10-02
Scope: workstream A (Linkman Milestone 14, the devman-to-Linkman link cutover)
against workstream B (devman project 041, the central guard).
Mode: research only. Nothing in any repository or in `~/.config/devman` was
mutated. All probes ran in `mktemp -d` under `/tmp` and were deleted.

## Executive result

The two workstreams do not conflict in design. They share one gating
dependency: an operator must land the archive-project sublane in `m14-central-residue`
then `gitman land m14-central-residue` in `~/.config/devman`, because the
permission classifier denies that `land` to an agent at any lane size
(measured, not assumed — see §1). Until that land happens, workstream B's
own exposure (C3 = 12) stays open, and workstream A's Lane 9 cannot safely
rewrite the same 78 central files on top of an unlanded parent. No option B
is evaluating requires a change to Linkman; the open item (B4 / Q3, which Nix
file hosts the reconcile hook) is a devman-side and cutover-side decision, not
a Linkman one.

## 1. The reconcile-trigger question (B4 / Q3) — current state

**Not settled. Lanes 8, 9 and 10 have not started.**

| Fact | Evidence |
|---|---|
| Landed lanes, by commit | linkman `7e39f52` "m14 l0" (2026-10-01 12:43); devman `1be7863` l2, `c9d8360` l3, `416b402` l4, `6b909ac` l6 (folds Lane 5), `d15535c` l7 (2026-10-01 13:06–13:53) |
| Lane 1 ("devman: hygiene") | no distinct `m14 l1` commit found; the stray `devenv.yaml` change it was meant to adopt predates the session (`3e2768e`, 09:08) and left no separate landed trace — unresolved, not load-bearing for B4 |
| `modules/link.nix` | still present, `enterShell` at `modules/link.nix:70-75` (re-verified; closing brace line not re-checked beyond 70) |
| `nix/link-adapter.nix` | still present |
| `devman.link` attribute set | still declared by 68 of 68 existing central `devenv.local.nix` files (re-measured, see §3) |
| Lane order (corrected) | `m14-lanes-8-10-refactoring-guide.md:580-583`: "Decision E-b. This runs before Lane 9d, reversing the original guide" — 9e before 9d, as B3 required |
| Q1/Q2/Q3 status | `m14-lanes-8-10-readiness-review.md:740-761` (§7): each is phrased "Decisions needed from the user," with a recommendation, not a decision. Q3's recommendation is option 2. No record anywhere marks it DECIDED |
| Lane-order gate | `m14-lanes-8-10-refactoring-guide.md:956-958`: "Lanes 9c, 9e and 9d cannot start until Q1, Q2 and Q3 are answered" |

So the cutover has landed Phase A/B/C (converter, byte-identity gate, devman
calling Linkman behind `DEVMAN_LINK_ENGINE`, default off) and the independent
Lane 11 (M15 gap). It has not reached Lane 8 (move the three D5 features), so
it has not reached the point where B4 becomes actionable. B4's recommendation
(option 2 — a minimal central Nix file whose only job is the `enterShell`
hook) is endorsed twice (the review itself, and
`linkman/.loci/projects/001-devman-cutover/b4-reconcile-trigger-endorsement.md`)
but carries no formal decision record. **What B4 forecloses, if adopted, is
option 1** (a devenv module imported by each repository's own `devenv.yaml`)
— that would cross devman's own boundary test, `AGENTS.md:112-120` property
10, by moving machine-local trigger content into the repository layer. Option
2 keeps the overlay's working copy on the critical path of every shell entry
on the machine, which is also why workstream B's C3 (trunk reachability)
matters to workstream A: once 9e lands, the hook's home is still central
content, still gated by whether it is reachable from trunk.

**A citation in the review has drifted, and the code wins.** B3 cites "77 of
78" central files importing `link-module.nix` and "78 of 78" declaring
`devman.link`. Today, on trunk, there are only **68** central
`devenv.local.nix` files (not 78); the other 10 belong to the abandoned lane
`m14-central-dead-fixtures` and were never on disk at the review's citation
in the first place — they existed transiently as unlanded bootstrap output
(devman CONCEPT.md §14.2: "those 18 files are not on disk now"). Re-measured
on trunk today: **67 of 68** import `link-module.nix`; the one exception is
`projects/mnemonix/devenv.local.nix` (`grep -L` over the 68 files), exactly
the anomaly the review's own Q6 names. The underlying finding — deleting the
adapter bricks shell entry everywhere at once — is unaffected; only the
denominator was stated against a working-copy population that never landed.

## 2. Is a generation pointer for live symlink targets compatible with Linkman?

**Yes, with one behavioral fact the feasibility study needs: Linkman
collapses any symlink in the target path to its physical destination at
plan-build time (`Path.resolve()`), so the live symlink Linkman writes will
never literally read through the pointer — it reads the day's resolved
generation.** This does not require a Linkman change; it changes what a
generation flip costs operationally (see below).

**Linkman's binding boundaries, as written down:**

- D2, `/home/andrew/Documents/Projects/linkman/.loci/projects/000-Initial-concept/decisions.md:27-36`:
  "Linkman keeps no durable state. Pruning becomes an explicit operator
  command, `linkman prune <link>`." A generation pointer introduces no new
  durable state in Linkman — the pointer, if adopted, would be devman's or
  vendomat's, never read or written by Linkman.
- D5, same file, lines 74-83: "Linkman stays symlink-only. `devman` keeps
  `excludes.py`, the copyroom call and the central bootstrap file... Rejected:
  a target-provider hook in Linkman." This is the decision devman's own
  project 041 cites independently at `DECISIONS.md:329-352` (D10) and
  re-derives by measurement in `CONCEPT.md:334-360` (§3.4): `linkman check`
  reports `clean: true` on a dangling link because target existence is
  outside Linkman's contract by design.
- Planning is pure: `src/linkman/planning.py:1` ("Pure status classification
  and plan construction"), confirmed by reading `classify_status` (lines
  20-32) and `_actions_for` (lines 74-127) — no I/O, only `match` over
  already-observed state.
- Inspection is read-only: `src/linkman/inspect.py` builds `ActualLink` by
  `lstat`/`readlink` only (cited identically by the filed linkman record
  below); `apply` is topology-only: `src/linkman/reconcile.py:189`
  (`apply_plan`) only ever creates/repoints symlinks and, for missing
  **external** targets, creates the target entry (`reconcile.py:122,131` —
  `mkdir`, `touch`) — never content.

**Does a generation pointer require Linkman to know about generations?**
No — proven with the real binary, not asserted. Fixture under `/tmp`:
`links.yaml` declared `vars: {central: "${env.HOME_PROBE}/active"}` where
`$HOME_PROBE/active` was a symlink to a directory `central_gen1`, which held
the target file.

```
$ linkman config --repo-root <probe>/repo --config <probe>/repo/links.yaml
VAR      central = /tmp/.../active
LINK     bootstrap.txt -> /tmp/.../central_gen1/projects/sample/bootstrap.txt
```

`resolve_vars`/`interpolate_resolved` (`src/linkman/resolve.py:60-161`) only
ever do string substitution — `vars.central` is an opaque name to Linkman,
resolved once from `links.yaml`'s own `vars:` block or `${env.*}`/`${repo.*}`.
Nothing in `resolve.py` inspects the filesystem. **But**
`build_desired_state` (`src/linkman/topology.py:47-49`) then calls
`target_path.resolve(strict=False)` on the rendered string, and Python's
`Path.resolve()` dereferences every symlink on the path that exists,
including the pointer itself. The `LINK` line above shows the declared
target is already `central_gen1`, not `active` — the pointer symlink is gone
by the time Linkman records the desired target string.

Consequence, also measured: after creating the live symlink and repointing
`active` from `central_gen1` to `central_gen2` (nothing else touched),
`linkman check` reported the link as `"status": "repoint"` — a generation
flip is not absorbed silently. Every live symlink declared through a pointer
of this shape needs its own `linkman apply` after each flip, fleet-wide. That
is a cost the feasibility study should price in; it is not a defect and it
needs no Linkman change — `apply` doing exactly this is its contract.

**Scope classification (`INTERNAL`/`EXTERNAL`) is unaffected.**
`src/linkman/topology.py:51-52`: `internal = target_abs != root and
target_abs.is_relative_to(root)`. Scope is decided purely by whether the
*resolved* target sits inside the repository root, never by whether the path
transits `~/.config/devman` specifically or any other named root. The probe's
`diff --json` output confirmed `"target_scope": "external"` both before and
after the generation flip. A generation path for a central target stays
`EXTERNAL`, exactly as today's `~/.config/devman` targets are — nothing about
missing-target handling changes.

**No hardcoded assumption that the target is inside `~/.config/devman` or
writable**, confirmed by grep: `grep -rn "\.config/devman\|XDG_CONFIG_HOME"
src/linkman/*.py` finds only `repository.py:23-31`, which is Linkman's
*own* default config-search path (`$XDG_CONFIG_HOME/linkman`, not devman's),
per D5 revision 12 in `decisions.md`. The one place Linkman assumes
writability is `reconcile.py:122,131` (`mkdir`, `touch` for a missing
**external** target) — reached only when devman has *not* pre-created the
bootstrap content per D5's division of labor. If a generation pointer makes
the live generation tree read-only (plausible for a published, immutable
generation, mirroring how Nix store paths work), devman's own pre-create step
must run before the generation is published, not at `apply` time — a devman
design constraint, not a Linkman one.

**A working precedent for exactly this pattern already exists in devman**,
one layer up from links: `AGENTS.md:74-86` (property 6) documents
`~/.local/state/vendomat/devman/active` as "the active generation: a
complete registry root," already in production use for `registryDir`
(generation 3 since 2026-09-15), with a Stage 41 refusal keeping
`registryDir` and `overlayDir` from being set equal. A generation pointer for
link *targets* would be the same pattern applied one level down, and the
refusal that currently separates registry-root from overlay-root is the
template for whatever would need to separate a generation-pointer root from
the live `overlayDir` devman's Nix module still hardcodes
(`modules/link.nix:34`).

**Verdict for Linkman specifically: compatible, no Linkman change needed.**
`vars.central` pointing at a generation path is ordinary external-target
substitution. The two caveats above (apply-per-flip cost; devman must
pre-create before publish if the generation is immutable) are devman/vendomat
design questions, not a Linkman boundary violation.

## 3. The duplicate declaration, and its endgame

**Counts, re-measured just now, read-only:**

```
$ ls -d ~/.config/devman/projects/*/ | wc -l            78
$ ls ~/.config/devman/projects/*/links.yaml | wc -l      78
$ ls ~/.config/devman/projects/*/devenv.local.nix | wc -l 68
```

Matches the prior measurement in `b4-reconcile-trigger-endorsement.md:16-21`
and devman's `CONCEPT.md:159-162` exactly. The 10-file gap is the dead
fixture projects (`docman-*`, `roundtrip-debug`), confirmed as abandoned
cutover-tooling residue in devman `CONCEPT.md:1043-1056` (§14.2) — their
`devenv.local.nix` files are "not on disk now."

**Which survives, per whose plan, and has it landed:** `links.yaml` survives;
`devenv.local.nix` shrinks to a trigger-only file. This is Lane 9e's own
design (`m14-lanes-8-10-refactoring-guide.md:580-666`), endorsed a second
time, independently, by devman project 041's
`b4-reconcile-trigger-endorsement.md:60-80` on the P2/P4 drift-prevention
argument ("source or projection, never a copy" / "one mechanism per job,"
from devman `.scratch/projects/025-the-link-plane/CONCEPT.md`). **It has not
landed.** Lane 9e has not started (§1).

**Consumers of `devenv.local.nix`'s `devman.link` attribute set today, other
than the shell-entry reconciler:** grepped across the devman source tree —
`src/devman/cli.py`, `src/devman_link/{config,reconcile,__init__}.py`,
`tools/cutover/{snapshot,convert}.py`, and the cutover's own unit tests
(`test_cutover_gate.py`, `test_link_adapter.py`, `test_cutover_convert.py`,
`test_identity.py`, `test_cutover_snapshot.py`, `test_linking.py`). All of
them are either the `devman_link` engine itself (reachable only through the
same shell-entry reconcile path, or through `devman link reconcile` run by
hand — B5's finding) or the cutover's own comparison/conversion tooling,
scheduled for deletion in Lane 10.1. **No consumer survives outside the
cutover's own machinery.** This confirms retiring the attribute set is safe
with respect to third-party readers — the only readers are the two sides of
the cutover itself.

**Does the endorsement's argument hold up against the code? Yes.** Its two
measurements (78/78/68, and the representative `linkman` instance) both
reproduce exactly. Its claim that option 2 "ends the duplication as a
by-product" is consistent with Lane 9e's own text (`m14-lanes-8-10-
refactoring-guide.md:622-635`, "9e-2 — rewrite the 78 central files" — the
content, not just the hook, moves). One addition worth recording: devman
project 041's own checks (C1, C4 — `CONCEPT.md:287-300`) test only that
`devenv.local.nix` *evaluates* and that a `links.yaml`-bearing project *has*
a `devenv.local.nix` — neither tests the `devman.link` attribute set's
content. **Lane 9e's rewrite will not break C1/C4** by construction; they are
indifferent to what the file's content is, only that it exists and parses.

## 4. The ordered plan

```
0. OPERATOR: land the archive-project sublane in m14-central-residue, then
   gitman land m14-central-residue, in ~/.config/devman.
   WHY: both lanes are agent-denied by the permission classifier at any
   size (devman CONCEPT.md §14.1, measured against a 4-path pure-rename
   lane). Landing closes C3 (12 exposed live views -> 0) and removes the
   59-path residue that would otherwise sit under whatever Lane 9e rewrites.
   REVERSIBLE: yes, by gitman's own fold/undo semantics, until a later lane
   builds on top of it.
   BLOCKS: workstream B's O1 (the hazard stays live until this lands);
   loosely orders before workstream A's Lane 8+, so Lane 9e rewrites a
   clean, fully-landed set of 78 files rather than one with known unlanded
   residue underneath it.

1. OPERATOR (or agent, read-only check first): gitman abandon
   m14-central-dead-fixtures.
   WHY: its 18 files are reconciler bootstrap output for ten repositories
   that do not exist; nothing on disk or in the reverse index depends on
   them (devman CONCEPT.md §14.2).
   REVERSIBLE: no (abandon discards the lane), but safe — the content is
   already absent from disk and consumed by nothing.

2. A: Lane 8.0 — make `nix flake check` green (fileset gap: `./tools`).
   WHY: every later gate in the cutover reads this signal; it has been red
   since Lane 2 and five lanes landed over it (review Q4).
   REVERSIBLE: yes.
   INTERLEAVES with workstream B freely — it touches devman's own
   `flake.nix`, not the central overlay.

3. A: Lanes 8a, 8b, 8c — move the module closure, bootstrap writer and
   copyroom call out of `devman_link` into `devman`, per D5's division
   (excludes.py / bootstrap / copyroom stay devman's).
   WHY: Lane 9's deletions depend on these features having a home outside
   the code Lane 9d removes.
   REVERSIBLE: yes (`gitman undo` or revert; no live state per the guide's
   own rollback table, `m14-lanes-8-10-refactoring-guide.md:962-975`).

4. A: Lane 9a — port the remaining `devman_link` consumers (`doctor.py`,
   `watch.py`).
   Same reversibility; no live-state change.

5. OPERATOR DECISION (Q1): publish Linkman as a fetchable, pinnable
   package. Outward-facing (new repository visibility), so it is the
   user's call, not an agent's, per the review's own framing.
   BLOCKS: Lane 9c entirely ("nothing here starts without it").

6. OPERATOR DECISION (Q2): confirm the engine-flag release discipline
   (flag reaches `enterShell` first; one tag held at least seven days).
   BLOCKS: Lane 9b's flip of the default.

7. OPERATOR DECISION (Q3 / B4): choose the reconcile-hook's new home.
   Recommended and twice-endorsed: option 2, a minimal central Nix file
   whose only job is the `enterShell` hook (§1, §3). This is the one
   decision workstream B has a stake in, because its endorsement rests on
   ending the links.yaml/devenv.local.nix duplication as a byproduct — but
   the decision itself belongs to the cutover, not to project 041, which
   is explicitly forbidden from designing around a Linkman change
   (devman CONCEPT.md §6.3).
   BLOCKS: Lanes 9d and 9e.

8. A: Lane 9b (flag flip), then Lane 9c (publish/rewire the adapter) —
   gated on steps 5-6.
   REVERSIBLE: 9b by unsetting the env var; 9c by reverting devman (the
   published Linkman tag "stays and harms nothing" per the guide's own
   rollback table).

9. A: Lane 9e — rewrite the 78 (now landed, post-step-0/1) central files:
   retire the `devman.link` attribute set, land the hook's new home
   (step 7's answer), confirm the mnemonix anomaly (Q6) is resolved first.
   MUST PRECEDE Lane 9d — this is B3's finding and the guide's own
   corrected order (`m14-lanes-8-10-refactoring-guide.md:580-583`).
   IRREVERSIBLE IN PRACTICE if done out of order: deleting the adapter
   (Lane 9d) before 9e lands bricks shell entry in all 65-67 live projects
   simultaneously, with a Nix trace nothing can intercept. In order, it is
   reversible (`restore.py` for topology; revert the lane for content; the
   guide requires taking both paths before starting).
   This is also where workstream B's recommendation (step 7) becomes
   physically true: `links.yaml` becomes the sole declaration.

10. A: Lane 9d — delete `devman_link`, `modules/link.nix`,
    `installLinkAdapter`, the `repo` canonical kind.
    REVERSIBLE: activate the prior NixOS generation, then revert the
    devman commit.

11. A: Lanes 10.1/10.2 — delete cutover tooling; take the archived-project
    item only (Q5). INTERLEAVES freely with B at any point after
    step 9, since it touches only devman's own repository and the two
    archived central directories.

12. B (any time, but cleaner after step 0): a new lane removing the ten
    dead fixture projects' `links.yaml` entries from trunk — not
    blocking, closes C4's remaining 10 findings. Independent of A.

13. B, blocked on step 0: O6, canonicalize `~/.claude/AGENTS.md` as one
    tracked central file with two symlinks (devman CONCEPT.md §14.3).
    Blocked because the canonical file belongs in the overlay, whose
    working copy is mid-lane until step 0 lands.

14. B, independent of A entirely: ship the `devman central-verify` /
    `doctor link drift` / ledger-prune work to the system profile (a Nix
    rebuild — an operator action, separate from any gitman land). File
    `O4` (gitman switch-hook) and `O9` (duplicate-registration refusal)
    stay open, operator-level decisions with no dependency on A.
```

**Genuine conflicts found: none.** The two workstreams want the same
outcome for the duplicate-declaration question (step 7/9) and arrived at it
independently — the cutover's own readiness review from the link-engine
side, project 041 from the drift-detection side. The only real collision is
operational, not architectural: both workstreams are stalled on the same
`gitman land` in the same repository, which only the operator can run. If
anything "gives," it is schedule, not design — step 0 has to happen before
either workstream's remaining work can be considered low-risk, and nothing
in this research found a way around that for an agent.

## What I could not determine

1. Whether Lane 1 ("devman: hygiene") was ever completed as a distinct,
   nameable unit of work, or whether its stray `devenv.yaml` change was
   folded wordlessly into a later commit. It does not block B4 or the
   duplicate-declaration question, so it was not chased further.
2. Whether `gitman repair --dry-run` (if that flag exists) would let an
   agent verify the `m14-central-residue` land plan without the classifier
   denial devman project 041 hit — not tested here, because testing it
   would mean invoking `gitman` against `~/.config/devman`, which this
   brief's hard rule 1 forbids regardless of the verb's safety.
3. The exact cost, in wall-clock or operator attention, of a fleet-wide
   `linkman apply` after a generation flip (§2) — measured only on a
   one-link `/tmp` fixture, not at the 325-view, 66-repository scale the
   real machine would need.
4. Whether any repository outside `~/Documents/Projects/` holds a live
   view into the overlay (devman CONCEPT.md's own §12.4, unresolved there
   and not independently chased here).

## What this did not do

No `gitman` or `jj` command was run, anywhere. No file in
`~/.config/devman`, in the linkman repository, or in the devman repository
was created, edited or deleted. All `git` invocations were read-only
(`status`, `log`, `show`, `ls-tree`, `rev-parse`, `grep`, `diff --stat`
against commit pairs). The two `linkman` invocations against real
declarations (`config`, `check`, `diff`) were run only against
`~/.config/devman/projects/linkman/links.yaml` as a read, never `apply` or
`prune`, and only to reproduce figures already published by devman project
041 and by the filed linkman record
`linkman/.loci/projects/002-check-reporting-gap/check-reporting-gap.md`. The
substitution/generation-pointer probes ran entirely inside two `mktemp -d`
directories under `/tmp`, both removed after use; neither touched
`~/.config/devman`, `~/Documents/Projects/`, the registry, or the system
profile. No existing plan or review document was edited. This document is
the one new file this research produced.
