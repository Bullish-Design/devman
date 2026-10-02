# 041 — decisions

**Date:** 2026-10-01
**Companion:** [`CONCEPT.md`](CONCEPT.md) beside this file. Section references
below are to it unless another document is named.
**Form:** each decision states what was chosen, what was rejected, and the
measurement or charter clause that forced it. A decision with neither a
measurement nor a clause behind it is marked **unforced** and is a
recommendation, not a finding.

---

## D1 — The check reads the filesystem, not the registry and not the ledger

**Decided:** `central-verify`'s population is a reverse index — every symlink in
the fleet whose raw target lands inside `~/.config/devman`. No declaration source
is an authority.

**Rejected — the derived registry.** `devman doctor`'s existing `link drift`
check reads `proj.links` from the active generation. Measured: **0 of 48 entries
declare a link** while **325** live views exist. The check reports
`ok  no registered project declares a link`. Cause: `37050e9` (2026-09-19)
deleted `modules/devenv.nix`, the registration hook that wrote the projection;
`modules/link.nix:1-7` states that the link module deliberately knows nothing
about the registry. A check built on an empty input cannot fail.

**Rejected — `.devman-link-state.json`.** 450 entries, 82 projects, against a
live 66. Driven from the ledger the same assertions produce **27 findings of
which 1 matters** (16 belong to projects whose repositories do not exist). That
is 035's *"report nobody opens"* and 015's *"54 identical reports is one
report"*, reproduced.

**Rejected — the 78 tracked `links.yaml` files alone.** They are tracked and
correct, but they are a declaration: they record what should be, and the hazard
is about what is. They also exclude two live view kinds, `.loci` (56 views) and
`.git/info/exclude` (64 views), because those are devman's under D5 and not
Linkman's.

**Forced by:** `AGENTS.md` property 4 — *"prefer a check that can fail to one
that cannot"* — and by the measurement that the two record-based inputs are
respectively empty and 34 projects stale.

**Second reason, and it is the stronger one:** every declaration source carries a
liveness gate that is wrong for this job. The cutover census counts live projects
by `.devman/project.toml` and so excludes `mnemonix`. `mnemonix` is one of the
two bootstrap targets `gitman split` deleted in incident 1 and one of the three
repositories exposed today. **A repository holding a symlink into the overlay is
live for this purpose whether or not it has onboarded.** The view side is the
only source that knows that, because it is the fact itself rather than a record
of it.

---

## D2 — The gate is `[land.pre_hook]`, not `[publish] verify`

**Decided:** `~/.config/devman/gitman.toml` gains `[land.pre_hook]` and
`[land.post_hook]`.

**Rejected — `[publish] verify`.** Measured: `run_verify` has exactly two call
sites in gitman, `core.py:1369` (`do_publish`) and `release.py:64`
(`do_release`). `do_land` (`core.py:1467`) is not one of them. So **`[publish]
verify` has never gated a `land` in any repository**, with or without a remote.
In `~/.config/devman` it is worse than ineffective: with no remote, `publish` and
`release` refuse before the hook, so a configured gate there could never run.

**Proven, not assumed.** In a throwaway colocated repository with no remote, a
hook exiting 1:

| Phase | Outcome | gitman exit | Trunk |
|---|---|---|---|
| `pre_land` | `BLOCKED` | 1 | unchanged |
| `post_land` | `LANDED` + *"no rollback was attempted"* | 1 | advanced |

**Forced by:** the call-site measurement, and by the operator's policy requiring
*"once its verify step passes"* in a repository where no verify step could ever
execute.

**Collateral finding this forces into the open:** devman's own `gitman.toml`
carries `[publish] verify = ["nix","flake","check"]`, added by `81a1340` with the
message *"move the verify gate under `[publish]` so gitman reads it"*. gitman
does read it — on `publish` and `release`. Every `gitman land` in devman since
then has run no verify. Recorded as open question O2 rather than fixed here,
because `nix flake check` in devman is currently red and the change would make
devman unlandable.

---

## D3 — Pre-land blocks on content; post-land reports on completeness

**Decided:** C1 (Nix evaluation), C2 (target exists) and C4 (`links.yaml` ↔
`devenv.local.nix` pairing) run in `pre_land` and **block**. C3 (target is on
trunk) runs in `post_land` and **reports**.

**Rejected — C3 in `pre_land`.** It would refuse the one operation that fixes
the condition it detects. A live view is lane-only *because* the lane has not
landed; blocking the land to protest that the lane has not landed is a deadlock.

**Rejected — everything in `post_land`.** A post hook cannot roll back, by
gitman's design and by its own message (*"land succeeded; no rollback was
attempted"*). Folding a central declaration file that does not evaluate is damage
a report cannot undo.

**Forced by:** the asymmetry between the two finding classes. C1/C2/C4 are
*the content is wrong*; C3 is *the content has not reached safety yet*, and
landing is its cure.

**Consequence accepted:** between a partial land and the next one, the exposure
is real and only reported (limit 5).

---

## D4 — No new write tier. One invariant, scoped to one repository

**Decided:** the tier table (`free` / `lane` / `insitu`) is unchanged. One
invariant is added:

> **CENTRAL-1.** In `~/.config/devman`, a path that a live repository symlinks to
> has not finished being written until it is reachable from trunk. Tier `free` is
> not terminal there.

**Rejected — a fourth tier for machine-generated central content.** The three
named cases already route under the existing table plus P2, and two of the three
were decided before this project:

| Content | Routing | Authority |
|---|---|---|
| promoted agent surface, `.local.gitignore`, `links.yaml` | tracked; `free` on creation, `lane` on edit | 025 §7.3, 035 §8.7, **036 Part C (binding)** |
| `repoman install-skills` routers, `agents/index`, `agents/pi/`, `dags/`, the ledger | gitignored, never tracked, no tier | the live `~/.config/devman/.gitignore`, with the reason written in the file |

**Rejected — gitignoring the agent surface.** 035 measured 62 real copies with
zero symlinks and called it a P2 violation; the repository now holds **614
tracked symlinks**. 025 §7.3 rests on them being tracked: *"Selection is a
directory of links — `ls`-able, diffable, and version-controlled."* Untracking
them re-creates 035's violation from the other side — an authoritative pool with
invisible selection.

**Forced by:** 036 Part C for `.local.gitignore`, 025 §7.3 for the surface, and
the `.gitignore` precedent already shipped for generated routers. **The tier was
never the defect.** The defect is that `free` lands "in the working tree", and in
a colocated jj repository the working copy *is a commit* — so in the one
repository whose working tree is also the machine's live configuration, `free`
is a staging area with 325 live consumers, not a resting place.

**Why an invariant and not a tier:** CENTRAL-1 is checkable (it is C3) and scoped
to one repository. A fourth global tier would be an uncheckable claim in 74
`writes.toml` files. 015 §9 said the amended tiers still owed an audit; this adds
a checkable property rather than another claim. Note also that `check_writes`
(`src/devman/doctor.py:682-706`) only flags `tier = "free"` **outside** tier A's
agent surface — and the overlay's content *is* agent surface, so a `free` claim
over it passes the audit cleanly. CENTRAL-1 closes that seam without touching the
audit.

---

## D5 — No workflow commits or lands central drift

**Decided:** no. The plane detects, refuses and reports. It does not adopt, commit
or land.

**Forced by a charter clause, not by judgment.** 015 §9, in the same amendment
that replaced rule 3 with the three tiers: *"**Rule 2 stands. The lane stays
local.** No `publish`, no `push`, no `land`. Creating a lane is reversible on this
machine; pushing it is not."* The amendment that weakened the write rule withheld
`land` from the plane explicitly. A landing workflow is a charter change, and
nothing measured here forces one.

**Three measurements agree independently:**

1. **The drift was not a lane.** gitman reported `working copy @ has unbookmarked
   work`. Automatic *landing* governs lanes and would have swept none of the 155.
   The gap is adoption, not landing.
2. **Automatic adoption bundles unrelated work.** The 155 were Phase A's 78
   central declarations, ten projects of docman/roundtrip fixture residue, and two
   shared pool skills (`skills/gitman/SKILL.md`, `skills/testee/SKILL.md`). One
   unreviewed commit over that set enshrines the fixtures — 035's finding
   repeating — and buries two edits that reach every repository through the
   surface links.
3. **An automatic lane nobody reads fails criterion 4.** A nightly
   `adopt-and-land` would report `Succeeded` while committing fixture garbage, and
   the repository would read `CANONICAL` and clean. That is precisely the state
   the whole of 2026-10-01 was spent inside.

**Rejected — automatic adoption into a named lane without landing.** Weaker than
it looks. It satisfies the tier table's letter and still produces, nightly, a lane
nobody reads over a path set nobody chose. 015's third owed item is explicit:
*"Lane hygiene — a scheduled tier-B workflow makes a lane per run per repository.
54 lanes a night is rule 7 wearing a new hat."* That item is unbuilt.

**What is automated instead:** the refusal and the report (D2, D3, D6). The
operator's actual complaint — *"I should not find 155 uncommitted paths three
weeks after cleaning this up"* — is answered by a detector that fires on the first
night of recurrence, not by a committer.

**Not in conflict with the operator's policy.** The policy governs an agent in a
session; the charter governs the plane. Both are right, and they bind different
actors. The policy's precondition is undefined in this repository today; D2
defines it.

---

## D6 — `doctor`'s `link drift` is repaired, and no new workflow is written

**Decided:** change `check_link_drift`'s input from the registry to the reverse
index, and add C3. No new workflow, no new group, no new queue name.

**Rejected — a devman `check`-group workflow for the overlay.** It requires the
overlay to join the plane, which needs `.devman/project.toml` and a `devenv.nix`
devman block — tracked repository facts. The overlay **is** the machine-local
root; a workflow belonging to it has nowhere further central to go, and 025 §6.1
moved the overlay there to hold *other* repositories' workflows. The boundary test
does not return an answer, because the question is malformed.

**Rejected — a new nightly report.** `maintain.yaml` records the arithmetic that
settles it: `doctor` moved to `plane-report`, which runs **once for the machine**,
because *"58 identical failures is not a signal. One is."* The repaired check
inherits that placement for free.

**Rejected — a new per-repository hook.** P4, one mechanism per job. gitman
already ships the hook point, configured by **0 of 74** repositories.

**Forced by:** the shared contract being closed (`AGENTS.md` property 3 — six
queue names, `DEVMAN_PROJECT_DIR`, `DEVMAN_SELF_DIR`, `.devman/.runs/`). This
design adds **no** shared name, so it needs no charter amendment on that axis, and
that is a deliberate constraint on the design rather than a happy accident.

---

## D7 — gitman owns the hook point; devman owns the predicate

**Decided:** the split is named and binding. gitman is asked for one generic
feature: extend its existing hook mechanism from `land` to the verbs that rewrite
the working copy — `switch`, `split`, `abandon`. devman supplies the predicate.

**Rejected — devman alone.** There is no interception point. `switch` and `split`
rewrite the tree inside gitman; by the time devman reads the filesystem the
damage has happened. Incidents 1 and 3 were both caught *afterwards*, by a failed
cutover gate and by a count in a prompt.

**Rejected — gitman alone.** *"A repository on this machine symlinks to this
path"* is a devman fact. The moment gitman knows it, gitman stops being an
interface to jj and becomes a second link plane — P1 and P4 both.

**Forced by:** P1, one interface per engine. The jj working-copy rewrite is
gitman's engine, so only gitman can refuse before it; the link fact is devman's,
so only devman can evaluate it. Neither can do the other's half.

**gitman has already proved the shape.** `[land.pre_hook]` is exactly a generic
hook point carrying an opaque predicate: JSON event in, exit code out, no domain
knowledge on gitman's side. The ask applies the existing idea to three more
verbs. `do_switch` (`core.py:797`) already carries two guards of this character —
refusing to strand an unnamed change with on-disk work, and refusing a double
checkout — so a third guard point is idiomatic there, not foreign.

**gitman's second, independent reason:** 035 §2.3 already recommended a gitman
check for a divergent colocated HEAD that `gitman doctor` reported `ok` on. It
was never built. The same tool, the same class of blind spot, twice — and both
times the blind spot is why a bad state survived an audit.

**Decided without the feature, too.** `land` is gated today by configuration
alone. The navigation verbs wait on gitman; D8 says what covers the gap.

---

## D8 — The lane-switch hazard is in scope, and it shrinks structurally first

**Decided:** in scope. The primary mechanism is **keeping C3 at zero**, not a
general guard. The gitman hook (D7) covers the residual window.

**Forced by a measurement that reframes the problem.** Of **325** live views,
**313** point at content on trunk and are already immune — a `switch` cannot
remove a path trunk holds, because every lane descends from trunk. Only **12**
are exposed, and they are exposed because they are new content on an unlanded
lane. **The hazard is not a property of the repository. It is a property of
unlanded new content in it, and its size is exactly the C3 count.**

So the general guard is the residual, not the fix. At C3 = 0 the hazard is
arithmetically absent rather than merely unlikely.

**Rejected — untracking the live targets** to make them survive a `switch`.
`devenv.local.nix`, `projects/*/agents/` and `.local.gitignore` must stay
tracked: 025 §7.3 and **036 Part C** bind the last two, and an untracked central
file is outside recovery, review and the two-sided-edit refusal. It moves the
hazard rather than removing it.

**Accepted for generated content:** `gitman untrack` is the right verb for
anything D4 classifies as regenerated, and the overlay's history already shows it
in use (`chore: untrack generated gitman skill`; `stop tracking notes: the vault
is a live service directory at ~/Notes`).

**If the gitman feature does not land:** devman cannot own the residual — there
is no interception point. The fallback is a discipline with a detector behind it:
C3 = 0 before any navigation verb in the overlay, stated in the **gitman skill**
where an agent reads it, with the nightly check catching the nights it was not.

---

## D9 — The whole mechanism sits on the read-only side of the permission classifier

**Decided:** `central-verify` writes nothing, `doctor` writes nothing without
`--prune`, and the `land` stays the operator's. The design never meets the
classifier.

**Forced by:** gitman's own hook contract. `hooks.py:filesystem_snapshot` captures
the workspace before and after a hook and **blocks the land on any change outside
`allowed_paths`, even when the hook exits 0**. A hook here must be a pure read.
That constraint and the classifier constraint point the same way, so satisfying
one satisfies the other.

**Rejected — splitting `m14-central-residue` to get under the classifier.** The
only way to carve it is `gitman split`, which is incident 1 — the verb that
deleted two live bootstrap targets. Running the dangerous verb to avoid a safe
denial inverts the risk.

**Rejected — moving the land into a workflow to escape the classifier.** That is
D5 with extra steps, and it converts a blocked-and-visible action into an
unattended write to trunk — the one shape `AGENTS.md` keeps out of a workflow.

**The classifier's denial is treated as correct.** The lane lands 59 paths of live
machine configuration behind 325 symlinks in 66 repositories, and *[Modify Shared
Resources]* coincides exactly with the operator's own *"shared or risky files"*
carve-out. Two independent policies agreeing is a signal. The design's job is to
make the handoff good, not to route around it: `central-verify` exit 0/1 and
`gitman land --dry-run` let an agent establish safety without landing, and the
post-hook message names the lane verbatim so the operator's action is a paste, not
a reconstruction.

---

## D10 — The check must not use `linkman check`, and the reason is a contract

**Decided:** the predicate is devman's own code. P1 would put it in Linkman, and
P1 is overridden here by a measurement.

**Measured** on a throwaway repository with a symlink pointing at a deliberately
absent target:

```
status: "correct"    clean: true    summary.correct: 1    exit 0
message: "link matches its declaration"
```

**`linkman check` reports `clean` on incident 1's exact damage.** `Status`
(`src/linkman/models/domain.py:75-82`) describes the link side only: it compares
the symlink's raw target string against the declaration. Target existence is
outside Linkman's boundary **by design** — apply is topology-only, and D5 of the
cutover keeps the bootstrap content in devman.

**Forced by:** the boundary test applied to the content, not the tool. devman owns
what lives at the target, so devman owns the assertion that it is there. Linkman
is not wrong; it is answering a different question, and this project is forbidden
from designing around a Linkman change.

**Recorded, not fixed:** `linkman check` with no config found also reports
`clean: true, total: 0`, exit 0. Run inside `linkman` itself it reports zero links
while four are live, because the declaration is central and the default search is
repo-local. That is a second check that cannot fail. Open question O7, for
Linkman's owner.

---

## D11 — C3 asks about trunk, not about the index

**Decided:** C3 reads `git ls-tree -r --name-only main`.

**Rejected — the git index.** In a colocated jj repository the index is jj's
export artifact, not a staging area. 035 §2.5 paid for that lesson: two prior
audits read `MM` as staged-plus-unstaged when it was one stale export, and
*"nobody hand-staged anything."* An index-based C3 would reproduce the same
misreading.

**Rejected — "the repository is clean".** The overlay is a live write target and
will always be dirty. 035 §6 established it and nothing has changed: every
`devenv shell` entry in 65 repositories writes canonical content here. A
cleanliness assertion would fire constantly and be ignored within a week, which is
015 rule 7.

**Forced by:** the colocated working-copy semantics. Trunk is the only content in
the repository that survives every lane operation, because every lane descends
from it.

---

## D12 — The repository's existing `base:check` is adopted, not replaced

**Decided:** C1 runs the `nix-instantiate` loop already written in
`~/.config/devman/devenv.nix`.

**Rejected — writing a new Nix validator.** *"Does it re-implement a task the
repository already has?"* is `AGENTS.md`'s named smell, and 015 killed candidate 3
on exactly it: *"both copies keep passing while they drift."*

**Measured:** 78 files, **2.58 s**, exit 0. Total verify cost 3.4 s with C2 and
C3 added. Well inside *"a check somebody runs"* — the constraint that an expensive
check nobody runs is the same as no check.

**The finding this surfaces is the more important half.** The task **can** fail —
a malformed central declaration file is what bricks shell entry — and **nothing
invokes it.** Not the plane (the overlay is not one of `doctor`'s 48 projects),
not gitman (its `gitman.toml` is one line), not any of the six workflows (`grep`
for `config/devman|overlayDir|central` across `groups/*/workflows/` → nothing).
A check nobody calls is in the same class as a check that cannot fail, and the
overlay had one of each.

---

## D13 — The hook command is an absolute system-profile path

**Decided:** `command = ["/run/current-system/sw/bin/devman", "central-verify", …]`
rather than `["devman", …]`.

**Forced by:** `hooks.py:run_hook`. A missing command returns *"hook command not
found"*, exit 2, and the land is **BLOCKED**. A `[land.pre_hook]` naming a bare
`devman` makes the machine-configuration repository unlandable whenever the
toolchain is not on PATH — which is a plausible state in a repository whose job is
to configure the toolchain.

`modules/link.nix:70-75` already depends on the same absolute path for shell
entry, and the readiness review B3 measured that both `devman-link` and
`link-module.nix` resolve through one derivation in the system profile. The design
inherits an existing machine assumption rather than adding one.

**Unforced residue:** if the system profile itself is the thing being changed, the
hook fails and the land blocks. That is the correct direction to fail, and it is
stated as limit 9 rather than engineered around.

---

## D14 — This project reports the `~/.claude/AGENTS.md` defect and does not fix it

**Decided:** report only. **Unforced** — a judgment, stated as one.

**Measured:** `~/.claude/AGENTS.md` and `~/.claude/CLAUDE.md` are **two real
files, not a symlink pair**, not in the overlay, and under no version control.
`diff` returns two differences: `AGENTS.md` lacks the entire **"Version control
lanes"** section, and it still cites `.agents/skills/my-ai/SKILL.md` where
`CLAUDE.md` cites `.agents/skills/writing/SKILL.md` — and 035 §8.5 decided that
move, so `AGENTS.md` is the stale copy of a decision already taken.

**Three charter clauses are violated at once:** P0 (both are user-local, so both
belong central), 025 §10 item 11 (*"`AGENTS.md` canonical with `CLAUDE.md` a
symlink to it"*), and P2 (two copies, already drifted).

**Why not fix it here:** the fix is a link-plane rollout of `~/.claude` — a
canonical central file plus two links — which is a change to live operator policy
in the middle of a session that depends on that policy. The file is also the
source of the standing instruction this project was asked to design against.
Editing it mid-investigation would make the investigation's own premise mutable.

**Consequence worth naming plainly:** a tool reading `AGENTS.md` gets no lane
policy at all. Claude Code reads `CLAUDE.md` and does. Open question O6.

---

## D15 — The ledger is read by nothing in this design and written by nothing in it

**Decided:** `central-verify` does not read, regenerate, prune or rewrite
`.devman-link-state.json`.

**Forced by:** 033 and readiness-review F2. `excludes.py:110-124` reads the
recorded `{canonical, hash}` baseline to refuse a two-sided edit of the exclude
projection, and that baseline *"is the only thing standing between a two-sided
edit and a silent overwrite."* A design that regenerates or discards it breaks
the refusal.

**Consequence accepted:** this design does not fix the ledger's staleness either
— 82 projects against a live 66, and `doctor --prune` does not cover it
(`Registry.unproject`, `registry.py:587-607`, removes projection and
`metadata.json` only). D1 makes that staleness harmless for *this* check by not
depending on it. It stays a real defect, recorded as open question O5.

**A second observation that O5 should carry:** the ledger shrank from **456
entries / 84 projects** (readiness review, ~17:16 today) to **450 / 82** (19:35
today). Six entries and two projects left, and nothing recorded the write. A
silent shrink in the file holding the two-sided-edit baseline is the one direction
that should not happen quietly.

---

## D16 — Nothing in `~/.config/devman` was mutated, and the two waiting lanes stay

**Decided:** no `gitman` mutating verb, no `git` write, no symlink change, no Nix
change, `devman doctor` without `--prune`. The two lanes stay as found.

**Forced by:** this project's charter, which reserves the landing decision to the
operator and names the lanes *"the worked example"*. Section 1.3 of `CONCEPT.md`
is what the worked example produced: the design detects and explains that exact
state in 0.72 s, naming four repositories and two distinct damage classes.

**Two mutations are disclosed, both outside every managed repository**, in
throwaway `mktemp -d` directories under `/tmp`, both removed: a Linkman probe
proving D10, and a colocated gitman repository proving D2. Neither touched
`~/.config/devman`, `~/Documents/Projects/`, the registry or the system profile.

**Raw read-only `git`** is disclosed with the same justification 035 §10 gave:
gitman ships 24 verbs and none is `diff`, `show` or `reflog`, and none answers
*"is this path in trunk's tree"*. Read-only `git` plumbing also does not snapshot
the working copy, and in this repository a snapshot is a live-system write.

**`nix flake check` in devman is red and was not run.** It is the cutover's Lane 2
blocker — the `python-tests` fileset omits `./tools` — owned elsewhere, and not
treated as this project's signal.
