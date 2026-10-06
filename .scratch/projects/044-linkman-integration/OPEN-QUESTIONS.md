# Open questions — 044 Linkman integration

What this session could not resolve, what evidence would resolve it, and what it
blocks. Written 2026-10-05, revised the same day after the architecture change
recorded in `DECISIONS.md` D23-D26.

Ordered by what they block, heaviest first.

**Four questions closed by the architecture change**, kept at the bottom with
their reasoning so a later session does not re-open them.

---

## O1 — Do any projects declare the same link in both layers? **RESOLVED by lane 3. Zero.**

**Measured 2026-10-05.** Exactly one repo-level `links.yaml` exists across every
checkout — `~/Documents/Projects/linkman/links.yaml` — and it declares **no
links and no vars**, so no key can collide. `linkman check` exited 0 for all 59
projects with a checkout; none exited 10. **0 of 60 would refuse on this
ground.**

Independently spot-checked: `devman`, `gitman`, `flora`, `repoman` each exit 0,
`clean: true`, every link `correct` (5, 5, 6, 5 links).

The risk was real and is now closed. The reasoning is kept below because the
asymmetry still exists in Linkman and would bite if a repo-level declaration is
ever added.

#### ~~O1 as originally raised~~

**What is known.** `load_layers` (`linkman/src/linkman/config.py:44-76`) treats
the repo-local layer and the overlay layer as a **disjoint namespace, not an
override**. The same link path declared in both raises `ConfigError`
("link path … is declared in both …"), exit 10. devman's current model has the
overlay as the declaring authority, and `devman_link` resolved any overlap
silently.

**What is unknown.** Whether any of the 60 projects carries a repo-level
`links.yaml` naming a key the overlay also names. If one does, Linkman refuses
where the old engine worked, and shell entry fails for that project.

**Evidence that would resolve it.** Exactly what lane 3 is for:
`linkman check --json` across all 60 projects, counting `ConfigError` exits. Also
cheap and direct: `ls ~/Documents/Projects/*/links.yaml` to find repo-level
declarations at all, then diff their keys against the matching overlay file.

**Why it is first.** It is the one failure mode that is *silent today and loud
after the switch*, which is the shape AGENTS.md property 4 cares about — except
inverted: the loudness is correct, but it arrives at shell entry in a live
project rather than in a test.

---

## O2 — Who runs the three shell-entry steps, and in what order?

**Blocks:** lane 5's design.

**What is known.** Three things must happen at shell entry, and the order is
load-bearing. Nix reads `devenv.local.nix` before any hook runs, and
`linkman apply` creates an *empty* file for a missing external target — so an
empty `devenv.local.nix` would break the import of the link module itself. So:
write the bootstrap content, then `linkman apply`, then project the exclude file.

**The options.**

1. **One `devman-link reconcile` that does all three**, shelling out to
   `linkman` in the middle. One hook line, one ordering guarantee, and the
   adapter's independence from the workflow plane is preserved. This is my
   working assumption.
2. **The hook runs two or three absolute-path commands in sequence.** More
   transparent, but the ordering contract moves into `modules/link.nix`, which
   ships inside the adapter derivation and therefore costs a rebuild to change.
3. **`devman link reconcile`** (the full CLI). Rejected in the plan: it makes
   shell entry depend on Dagu, watchexec and the registry, which is exactly what
   `nix/link-adapter.nix:17-22` exists to prevent.

**What is unknown.** Whether shelling out from Python to a second absolute store
path is acceptable under AGENTS.md property 7 ("Python for core logic; shell
stays a thin wrapper"). I read it as acceptable — the logic stays in Python and
the subprocess call is not shell — but it is a judgment call about the property,
not a measurement.

**Evidence that would resolve it.** None needed; it is a design choice. Worth
settling before lane 5 is written rather than during.

---

## O3 — Where does template intent get declared, once it leaves `links.yaml`?

**Ownership and placement are RESOLVED by D27.** The capability stays, moves to
devman's CLI at adoption time, and leaves the reconcile path. What remains open
is the declaration site, and it is a genuine design question rather than a
missing measurement.

**Why the old site is unavailable.** Linkman's `LinkConfig` has one field,
`target: str`. `links.yaml` is the sole declaration format after the cutover, so
there is nowhere to write `template:`. That constraint is not a nuisance — per
D27 it is the design telling us something true: `links.yaml` declares *links*,
and "how this content was created" is a different lifecycle.

**What is unknown: where template intent lives instead.** Three candidates, none
measured:

1. **`.devman/project.toml`** — the repo's own manifest, already the identity
   source (`devman_contract`). A `[templates]` table would ride the mechanism
   that already resolves per-project facts. But it puts central-overlay content
   intent in the *repo*, which the boundary test (AGENTS.md property 10) may
   refuse: the overlay's shape is true for this machine, not for a cloner.
2. **A central `templates.toml` beside the overlay's other central state.**
   Satisfies the boundary test cleanly. Costs a new central file and a new
   schema.
3. **An argument to the adoption command**, e.g.
   `devman project apply --template <name>`, with no persisted declaration at
   all. Simplest, and it matches copyroom's own documented model — adoption is a
   deliberate, reviewed act, "report-only unless `--write`", with no
   `--reconcile` (`copyroom-adopt/SKILL.md:35-38`). The cost is that nothing
   records what a project was templated from, so convergence (`copyroom update`)
   has no declaration to read.

**Candidate 3 is where I would start**, with one caveat: if `copyroom update`
convergence is ever wanted — and copyroom is built around it — then a persisted
declaration becomes necessary and candidate 2 is the honest answer. That makes
the real question: **is central-overlay templating a one-shot render, or a
converged relationship?** A one-shot render needs no declaration. Convergence
does.

**Evidence that would resolve it.** Author one real central-overlay template and
try to adopt a project with it. The first concrete template will show whether
convergence matters, which settles the declaration site. 024 §3.4's own advice
points the same way: "Adopt copyroom at the second structural change to an
existing project's layout."

**Blocks:** nothing in lanes 1-8. This is a separate initiative.

---

## O3a — Does devman still need `.devman/.runs/` in the exclude set?

**Resolved: yes, unconditionally.** `excludes.py:52` prepends `.devman/.runs/`
regardless of any declaration, so it is devman's own entry and survives the
switch to a `links.yaml`-derived set. Lane 4 must keep prepending it; it will
never appear as a link key.

---

## O9 — A failing `enterShell` is silently swallowed, for every project

**Blocks nothing. A pre-existing defect the cutover must not inherit, and it
amplifies several other findings.**

**Measured 2026-10-05** against the live generated script. The hook text appears
inside `shellHook` (`.devenv/shell-0a1ec6ce83df1770.sh:208-211`) and is run by
`eval "${shellHook:-}"` (`:2321`). A grep of all 2,323 lines found no `set -e`,
no `errexit` and no `trap` wrapping that `eval` — only unrelated `set -o` calls
inside stdenv helper functions.

So bash default semantics apply: **a non-zero exit from
`devman-link reconcile` is discarded.** Whatever it printed to stderr scrolls
past among boot messages, and the shell opens as though nothing failed.

**Why it matters beyond itself.** It is the amplifier behind two other findings:
D27's reason 2 (a declared template would have silently aborted a project's
entire reconcile) and D28's rejection of the multi-command hook (no `errexit`
means nothing sequences the steps). Any correctness that shell entry is supposed
to enforce is currently advisory.

**It is also the exact shape AGENTS.md property 4 names:** "A run that reports
success while producing an incorrect result is the failure this design exists to
prevent." Shell entry reports success unconditionally.

**Evidence that would resolve the fix, not the finding.** The finding is
measured. What needs deciding is the remedy, and the options differ in blast
radius: make the hook `|| { echo …; }` so a failure at least prints a framed,
noticeable message; or have `devman-link` itself print loudly on refusal, since
it is the only component that knows what failed; or surface a stale/failed
reconcile through `devman doctor`, which already runs fleet-wide and *can* fail
loudly. The third is the only one that can fail a gate rather than print into a
scroll-back.

**Recommendation: the third, plus the second.** Do not try to make `enterShell`
abort — devenv's own design discards the code, and fighting it puts control flow
in a shell string (property 7). Make the failure loud where it happens and
detectable where something checks.

---

## O4 — Should `devman doctor` survive a missing `git`, or is crashing correct? **DECIDED for lane 2, 2026-10-06.**

**Blocks:** nothing. A design question raised by lane 2.

**What is known.** `devman doctor` raises `InfraError` and exits 1 when `git` is
absent, from `central.py:206` via `check_c3_lane_only`. That kills the whole
command — every other check included — rather than reporting C3 as unavailable.
Lane 2 adds `git` to the wrapper so the check can run.

**The tension.** AGENTS.md property 4 prefers a loud refusal to a silent default.
Crashing is certainly loud. But it converts one unavailable check into zero
available checks, and `check_link_drift` already has a dedicated `EMPTY` status
used deliberately at `doctor.py:1633-1640`, because "an ok, 0 found line was
indistinguishable from a broken walk for twelve days." That precedent argues for
reporting C3 as unavailable rather than aborting.

**Decision basis.** This is a judgment call about the error behavior. The gate
requires `git` on the packaged CLI's PATH, regardless of that choice.

**Decision (D29).** Add `git` to the CLI wrapper. Keep the missing-`git` refusal
unchanged in this lane. The VM test reached the next doctor check after the
wrapper change and passed after its fixture supplied `writing/SKILL.md`.
Changing how doctor reports an unavailable C3 check would change its error
behavior. That needs a separate lane and evidence for the new report.

---

## O5 — How many devman derivations have a silently drifting interpreter?

**Blocks:** nothing. Explicitly out of this milestone. **This question outlived
the architecture change on its own merits** — it was found while investigating
Linkman's packaging, but it is not about Linkman.

**What is known, measured 2026-10-05.** devman's nixpkgs `python3` is **3.14.7**;
`python313` is 3.13.15. `nix/devman-cli.nix:43` and `nix/link-adapter.nix:36`
take unpinned `python3Packages` and build on 3.14.7, verified off
`nativeBuildInputs` and corroborated by the VM test log showing
`devman-0.6.0/lib/python3.14/site-packages/`. Meanwhile `flake.nix:137` and
`devenv.nix:24` pin `python313`. **devman ships on 3.14.7 and tests on 3.13.15**,
and nothing records it.

**What is unknown.** `nix/renderer.nix` also takes `python3Packages`
(`:51,57,67,68`) and was not examined. Whether anything else in the plane runs on
an interpreter nobody chose.

**Evidence that would resolve it.** For every derivation in `nix/`, evaluate
`nativeBuildInputs` and record the interpreter, as was done for the three here.
Mechanical, and it produces a table worth keeping.

**Why it matters even though nothing is broken.** `pyproject.toml` requires
`>=3.13`, so both interpreters satisfy it and the split is silent. The shipped
interpreter is currently a function of nixpkgs' roll date rather than a decision.

---

## O6 — Would devman ever need Linkman's `environ` override?

**Blocks:** nothing. It is the named trigger for revisiting D23.

**What is known.** The one capability reachable from `linkman.api.*` with no CLI
equivalent is the `environ: Mapping[str,str] | None` parameter
(`linkman/src/linkman/api.py:64,79,107,190,217,335`). Without it, `${VAR}`
interpolation always resolves against the live `os.environ`
(`resolve.py:66`). Also minor: `ConfigResult` has no `name` field, so the CLI
never echoes the project name it resolved.

**What is unknown.** Whether devman will want to evaluate a project's links
against a synthetic environment — for example, to verify all 60 configurations
from a context whose env differs from a real shell's.

**Why it is recorded.** D23 chose the CLI on the finding that nothing devman
needs is library-only. If this capability is ever needed, that finding changes
and D23 should be re-read, not worked around. Note the library route stays
available at any time: Linkman is `buildPythonPackage` precisely so a consumer
can import it.

**Separately, for Linkman's owner, not decided here:** `api.check/diff/apply` are
what Linkman's own CLI calls (`cli.py:132-180`) but none is in `__all__`, so by
concept §15's own rule they are private. Whether that is intended is Linkman's
question.

---

## O0 — `linkman`'s `.loci` had no second copy. **FIXED 2026-10-06.**

**Resolution: the vault is tracked in the linkman repository.** Commit `81c1668`
"track the loci vault: this project design record" — 17 files, +6810 lines,
landed on `main` and pushed to `origin`. Verified: `git ls-files .loci` → 17,
and `HEAD` equals `origin/main`. The documents now have git history and an
offsite remote.

Also done: `.loci/vendor/` added to `linkman/.gitignore` (vendored vault content
is somebody else's record, reproducible from its source), and the legacy `.loci`
line commented out of `~/.config/devman/projects/linkman/.local.gitignore` by the
operator — an agent cannot write there, and `041/DECISIONS.md` D9 says that
denial is correct.

**Two corrections to how this was first reported.** The original write-up below
claimed linkman's `links.yaml` "omits `.loci` which every comparable project
declares." That was wrong twice over:

1. **Nothing was dropped in conversion.** linkman's overlay `devenv.local.nix`
   declares exactly three links — `.envrc`, `.agents`, `.claude/skills`. It never
   declared `.loci`, in either format. The `.loci` exclude line was a legacy
   hand-added entry, not derived from any declaration.
2. **`~/Notes` would have been the wrong destination.** It is a git repo with
   `1_Projects` tracked and auto-snapshotted, but it has **no remote**, the vault
   declares `sync_backed = false`, and every peer loci directory is empty —
   `gitman`, `devman`, `copyroom`, `argentic` all hold 0 files. Migrating there
   would have gained local history and no offsite copy.

**The real diagnosis**, and why the fix is the one taken: the 14 files are
project design records, and devman's own boundary test (AGENTS.md property 10)
puts them in the repository. devman tracks 262 equivalent files under
`.scratch/projects/`; linkman had no `docs/`, no `.scratch/`, and its whole
design record inside an excluded directory. Tracking it also costs nothing in
the package — `linkman/nix/linkman.nix:43-55` uses an explicit
`fileset.unions` allowlist whose comment already named `.loci/` as staying out
of the closure, so doc edits never trigger a rebuild.

A safety copy taken before any change is at
`~/.local/state/loci-rescue/linkman-loci-2026-10-05.tar.gz` (101K). It is now
redundant and can be deleted whenever you like.

#### ~~O0 as originally raised~~

**Blocks nothing in the cutover. Raised to the top because it is a standing
data-loss exposure, and lane 3 is what revealed it.**

**Measured 2026-10-05:**

```
$ ls -ld ~/Documents/Projects/linkman/.loci
drwxr-xr-x  andrew 30 Sep 17:09   # a real directory, NOT a symlink
$ du -sh ~/Documents/Projects/linkman/.loci   → 336K
$ find ~/Documents/Projects/linkman/.loci -type f | wc -l   → 17
$ cd ~/Documents/Projects/linkman && git ls-files .loci | wc -l   → 0
$ git check-ignore -v .loci   → .git/info/exclude:11:.loci
$ ls -ld ~/Notes/1_Projects/linkman   → No such file or directory
```

Contrast every comparable project:

```
$ ls -ld ~/Documents/Projects/gitman/.loci
lrwxrwxrwx → /home/andrew/Notes/1_Projects/gitman     # a symlink
$ grep -A1 '\.loci:' ~/.config/devman/projects/gitman/links.yaml
  .loci:
    target: ${env.HOME}/Notes/1_Projects/${repo.name}/
```

**So:** `~/.config/devman/projects/linkman/links.yaml` declares four links and
**omits `.loci` entirely**. The directory is therefore real content living only
in that working tree — untracked, excluded from git, absent from `~/Notes`, with
no copy anywhere.

**What is in it: the governing documents of this cutover.**
`linkman-concept.md`, `decisions.md`, `m14-lanes-8-10-readiness-review.md`,
`m14-lanes-8-10-refactoring-guide.md`, `b4-reconcile-trigger-endorsement.md` and
`check-reporting-gap.md` — roughly 7,000 lines, and the authoritative contract
this session was told to read. Two of those files carry an "Exposure note"
stating this exact problem about themselves, and it is still true.

**Effect on the cutover: none, and this is worth being precise about.**
`append_entries` (`src/devman_link/excludes.py:61-77`) only appends missing
lines; it never rewrites or removes. So the legacy `.loci` line already in
`~/.config/devman/projects/linkman/.local.gitignore` **survives** lane 4, and
`.loci` stays out of `git status`. The exposure is latent, not active: it bites
only if that file is ever regenerated from scratch — a new machine, or the file
deleted — at which point 336K of unbacked design record becomes visible to
`git add`.

**Evidence that would resolve it.** None needed; it is a decision. Either
declare `.loci` in linkman's overlay `links.yaml` the way all comparable
projects do and let `linkman apply` migrate the real directory into
`~/Notes/1_Projects/linkman/` (Linkman's `migrate` exists for exactly this —
real content at a declared link path), or decide the directory stays unmanaged
and record why.

**Recommendation: fix it before lane 4**, and not because lane 4 needs it. Fix
it because the cutover's own source documents currently have one copy, on one
disk, excluded from the one mechanism that would back them up.

---

## O7 — Is the `foreman` overlay directory meant to exist?

**Blocks:** nothing. A loose end found while recounting.

**What is known.** `foreman` is one of the 60 overlay project directories and the
only one absent from the link ledger. `~/Documents/Projects/foreman` does not
exist. Its overlay files are dated 2026-10-01 19:49, about 17 minutes after the
bulk M14 conversion commit — added after it and never reconciled. It appears in
the recorded archive set, and the refactoring guide's Lane 10.2 names a
`foreman` item.

**What is unknown.** Whether it should be archived like the other 18 pruned
entries, or is pending adoption.

**Why it matters now.** Lane 3 runs `linkman diff` across all 60. `foreman` has
no checkout, so it cannot be diffed and will show as an anomaly. Archiving it
first makes lane 3's report clean; leaving it means the report must explain one
expected failure.

---

## O8 — Why does the registry know 44 projects where the overlay has 60?

**Blocks:** nothing. Recorded so a later reader does not mistake it for a fault.

**What is known**, all 2026-10-05: 60 overlay project directories; 59 projects in
the link ledger; 58 live checkouts under `~/Documents/Projects`; 44 in the active
vendomat generation. `devman doctor` exits 0, "Nothing to report." These measure
four different layers and are not in conflict.

But the overlay-to-registry gap is 16 projects — `agentman`, `clinch`, `foreman`,
`forgelab`, `fsdantic`, `inferference`, `linkman`, `mnemonix`, `nix-meta`,
`nixos-core`, `nix-terminal`, `PyGentic`, `scopeman`, `silverbullet-server`,
`siteman`, `template-py` — large enough that somebody will eventually read it as
a defect.

**What is unknown.** Whether a project is expected to enter the DAG-projection
registry only after adopting a workflow group, in which case 44 of 60 is correct
and uninteresting.

**Evidence that would resolve it.** Check whether each of the 16 carries a
`.devman/project.toml` declaring groups. Mechanical.

---

## Closed by the architecture change

Kept with their reasoning, so they are not re-opened.

**~~Can `nixos-rebuild` fetch a private `git+ssh` flake input as root?~~**
**Answered, by precedent rather than by test.** It already does, on every
rebuild: nix-meta carries `silverbullet-server` (`flake.nix:211`) and
`inferference` (`:259`) over `git+ssh`, and `machines/server.nix:435-448`
configures root's SSH declaratively with a comment naming this exact failure
("`sudo nixos-rebuild` evaluates the flake *as root* … which otherwise has no
known_hosts and no key of its own"). Nothing new is needed. See D26.

**~~Does Linkman build and pass its own checks against devman's nixpkgs?~~**
**Moot.** devman takes no flake input and builds no Linkman derivation, so the
two-nixpkgs question never arises. nix-meta's input will build Linkman against
its own pinned nixpkgs, which is Linkman's tested configuration.

**~~What should the shrunken ledger schema be?~~** **Answered in session.** It
does not change. `ensure_local_gitignore` reads *and* writes the identical
`{canonical, hash}` record (`src/devman_link/excludes.py:107-110`, `:139-142`),
using the hash for the same two-sided-edit refusal the promotion guard used. Only
the key set shrinks — from one entry per `project:view` to one exclude-projection
entry per project, roughly 345 rows down to 59. `check_ledger_stale` needs no
logic change; it partitions on `"<project>:<view>"` (`doctor.py:1769`) and a
one-entry-per-project ledger is still well-formed. **Watch in lane 4:** the count
drops by design and `doctor.py:1775` prints it, so the gate must assert the
expected post-shrink count, not "unchanged" — otherwise a correct lane fails, or
real data loss passes.

**~~Should the Linkman repository be made public?~~** **Withdrawn.** It may stay
private at no cost. See D26.

---

## Deliberately left to the operator

- **Q2** — the engine-release discipline. Largely dissolved by D24, which
  replaced the flag-and-hold with verify-then-pin. What survives is the choice to
  record lane 3's results rather than treat the verification as transient.
- **Q3** — the reconcile hook's permanent home. Deferred with the 60-file
  rewrite; lanes 1-8 do not depend on it.
- **Q6** — the one project of 60 importing a different combined module. Deferred
  with the same rewrite, but it should be identified during lane 3.
- **H5** — the `gitman land` into `~/.config/devman` that the permission
  classifier correctly denies to an agent (`041/DECISIONS.md:297-326`, D9). No
  longer on this push's critical path, which is the main benefit of D25.
