# Task: fix two "documented but not true" defects — one in devman, one in gitman

You are starting a fresh session. Two independent defects are already measured and
waiting. **They are in different repositories and share no code**, so they can be
done in either order or in parallel. One of them needs a decision from the
operator before any code is written; ask for it early and get on with the other
meanwhile.

Both are instances of one pattern the prior project named and did not finish
removing: **a thing that reports or documents its own behaviour, incorrectly.**
Keep that frame. The fix in each case is to make the claim and the behaviour
agree, not to add a feature.

---

## How to work here

- **Run everything inside the repository's `devenv` shell.** Never invoke bare
  `uv`, `python`, `pytest`, `ruff`, `git` or `jj` for a mutating operation.
  Read-only `git` for inspection is fine and is disclosed practice in this
  project lineage (035 §10 recorded the same choice with its justification).
- **Route all version control through `gitman`.** Never raw `jj`.
- **devman's verify commands are its own:**
  `devenv tasks run -v base:check` (ruff) and `devenv tasks run -v base:unit`
  (unit tests). **The `-v` is load-bearing** — without it `devenv tasks run`
  prints `{}` and hides the result. **devman does not use Testee**, whatever
  older documents say.
- **Do not run `nix flake check` / `base:test` in devman.** It is **red** for a
  known pre-existing reason owned by the Linkman Milestone 14 cutover: the
  `python-tests` check's fileset omits `./tools`, so three test files cannot
  import. Not yours, not a signal about your change.
- **gitman's verify is `pytest -q`** from inside its devenv shell.
- Write in **Simplified Technical English**: short sentences, active voice, one
  word for one meaning, no filler. Match each file's existing comment density —
  both repositories write long comments that cite measurements, and that is
  deliberate.
- **When a planning document and your judgment conflict, follow your judgment
  and say so in writing.** Project 035 is the local precedent: it corrected two
  earlier reports and named the sections it superseded.

## Four traps the prior session hit. Do not re-learn them

1. **`devman` on `PATH` is a stale system-profile build.** `/run/current-system/sw/bin/devman`
   lacks the `central-verify` subcommand entirely. For anything you change, test
   with the in-tree binary:
   `/home/andrew/Documents/Projects/devman/.devenv/state/venv/bin/devman`.
2. **`git status --short` in `~/.config/devman` lies.** It reports ~59 paths that
   are not dirt. In a jj-colocated repository the git index is jj's export
   artifact (035 §2.5 recorded two prior audits misreading exactly this).
   **Trust `gitman status`.**
3. **Verify a skip marker by running the negative case.** Both devman phases
   assembled `pytest.mark.skipif` lists by reading code, and both were wrong —
   a `PATH`-stripped run found four more git-dependent tests the first time and
   three more the second. Run:
   `PATH=/tmp/emptydir .devenv/state/venv/bin/python -m pytest tests/unit/<file> -q -p no:cacheprovider`
   (make and remove the empty directory). Expect skips, **zero errors**.
4. **devman now has a guard that will fail your suite if you add a check without
   a firing test.** `tests/unit/test_doctor.py` holds `_checks_in_main()`, which
   parses `doctor.main()` with `ast`, plus `FIRING_TESTS` and `INFORMATIONAL`
   dicts. Adding a `check_*` call to `main()` without an entry in one of them
   fails `base:unit` with a message telling you what to add. That is working as
   intended — satisfy it, do not route around it.

## Repository state as you begin — verify, do not assume

- **devman**: trunk is **2 commits ahead of origin** (unpushed, deliberately —
  `nix flake check` is red, which is the operator's own carve-out against
  pushing). There may also be an **unlanded lane** `041-phase1-check-efficacy`.
  Run `gitman status` first. **Do not push and do not land another session's
  lane without asking.** Start your own lane.
- **gitman**: was clean and in sync. **Its `[land.pre_hook]` runs the test
  suite on every `land`**, wrapped as
  `["env", "PYTEST_ADDOPTS=-p no:cacheprovider", "PYTHONDONTWRITEBYTECODE=1", "pytest", "-q"]`.
  The wrapper is load-bearing: without it the hook writes `.pytest_cache` and
  gitman blocks the fold, because `filesystem_snapshot` ignores only
  `.git`, `.jj`, `.gitman`, `.worktrees`. **Do not remove the wrapper.**
- **`~/.config/devman` is read-only for you.** A permission classifier denies
  `gitman` mutations there to an agent at any lane size — measured on a 4-path
  pure-rename lane. Read it freely; never write. Neither workstream below needs
  to write there.

---

# Workstream A — devman: `doctor`'s header names a path the projects did not come from

## The measurement

```
$ /home/andrew/Documents/Projects/devman/.devenv/state/venv/bin/devman doctor
devman doctor — 4 projects, 19 workflows
    registry   /home/andrew/.local/share/devman        <-- NOT the source of the 4
    state      /home/andrew/.local/state/devman
```

```
$ ... devman --registry /home/andrew/.local/state/vendomat/devman/active doctor
devman doctor — 48 projects, 152 workflows
    registry   /home/andrew/.local/state/vendomat/devman/active     <-- correct here
```

The four projects in the first run are `agentman`, `devman`, `flora`,
`pydantree` — exactly the contents of `~/.local/state/devman/projects`, the
**state** root. They did not come from the printed registry path. Confirm this
yourself before changing anything.

## Why it happens, and what is NOT the defect

`Registry.load()` reads `self.project_source or self.state_projects_dir`
(`src/devman/registry.py:380`). `project_source` is set by exactly one caller —
the plane-mode view (`registry.py:338`, `project_source=self.projects_dir`),
which `doctor` adopts only when the root proves plane mode by carrying
`generation.json`.

**The mode behaviour is deliberate, documented, and correct. Do not change it.**
`registry.py:330-334` states the reason: *"Plane projections keep the complete
project set beside their workflow files. The stable state root can lag behind a
generation, so doctor uses this view when the active root proves plane mode.
Other commands keep the state-root view and do not change their source of
truth."* `check_mode` (`src/devman/doctor.py:1010`) reads `generation.json`'s
presence for the same reason, stated in its docstring.

**The defect is the report, and only the report.** `doctor.py:1947-1954` prints
`reg.root` unconditionally. In compatibility mode that is not where
`reg.projects()` came from.

## Why it matters, with the incident

This is not cosmetic. It has already produced one wrong conclusion. An agent
verifying a 26-check change ran `devman doctor` against the four-project view,
saw no new noise, and reported the change safe on a healthy fleet — believing it
had examined 48 projects. The error was caught only because a reader thought the
number looked wrong.

The report's whole job is to say what it examined. A header that misnames its own
source is the same failure class the parent project exists to remove: plausible,
specific, and not the whole truth.

## What to build

Make the header state where the projects actually came from. Beyond that the
design is yours. Decide and record your reasoning for each:

- Print the real project source, print both paths, or print the mode alongside
  them. Weigh that `doctor`'s output is read daily and that **54 identical
  reports is one report nobody opens** — adding a line everyone skips is a real
  cost, not a free win.
- `check_mode` already reports `compatibility` or `plane`, but the prior session
  relabelled it **informational**, so a reader is now explicitly told not to
  weigh it. Decide whether the mode belongs in the header, whether that
  relabelling should be revisited, or whether the header alone suffices.
- Whether any other command misreports its source the same way. `registry.py`'s
  own docstring says other commands keep the state-root view; check whether any
  of them *print* a registry path. Report what you find; fix only what is in
  scope and say what you left.

## Verification for A

- `devenv tasks run -v base:check` and `base:unit` both pass. Note the count
  before and after; the baseline was **723 passed, 1 skipped**.
- A test that fails without your change. The honest one asserts the header names
  the source the projects were loaded from, in **both** modes — build a
  `tmp_path` fixture for each rather than asserting against the live machine,
  whose counts change hourly.
- Run the in-tree binary both ways (no flag, and `--registry <active>`) and paste
  both headers before and after.
- The `PATH`-stripped run from trap 3.

---

# Workstream B — gitman: three config keys are documented and do nothing

## The measurement

| Key | Declared | Read anywhere in `src/`? | Documented as |
|---|---|---|---|
| `[policy] protected` | `src/gitman/config.py:60` | **No** | *"Refs that must never be rewritten/force-pushed"* — `docs/USING_GITMAN.md:183`, `docs/GITMAN_CONCEPT.md:720` |
| `[lanes] always_workspace` | `src/gitman/config.py:24` | **No** | "start always isolates" |
| `[publish] branch_prefix` | `src/gitman/config.py:34` | **No** | a lane→branch prefix |

Verify each with a grep that excludes `config.py` itself. `[policy] protected`
has one near-hit at `src/gitman/core.py` in a comment about pyjutsu's own,
separate immutability mechanism — which never consults this list. Confirm that.

**Measured: 0 of 70 fleet `gitman.toml` files configure any of the three.** So
nobody is currently relying on a protection they do not have. Re-verify, because
that number is the whole reason this is not an emergency.

## Why `protected` is the one that matters

The other two fail **benignly and visibly**: a lane is not isolated, a branch
lacks a prefix. You notice immediately.

`protected` fails by **granting false confidence about an irreversible
operation**. Someone reads the documentation, sets `protected = ["main"]`,
believes trunk cannot be force-pushed, and learns otherwise at the only moment
it ever mattered. Nothing warns them. Treat the three as one cleanup but rank
`protected` first, and say in your write-up why the asymmetry justifies that.

## A decision is required before you write code — ask for it early

For each of the three, the operator must choose:

1. **Implement** it to match the documentation.
2. **Delete** the key and its documentation rows.
3. **Keep and mark it explicitly unimplemented**, so a reader cannot be misled.

Do not choose for them. **Do prepare the decision properly** — that is the real
work of this workstream. For each option and each key, establish from the code:

- What implementing it would actually mean. For `protected`: gitman's real
  protection is a pyjutsu mechanism. Find it. Would implementing `protected`
  duplicate it, configure it, or contradict it? **A second mechanism for one job
  is drift waiting to happen** — that is devman charter P4, and gitman's own
  concept document may say something equivalent; look.
- Whether deleting it breaks any config in the fleet (measured: no) or any test.
- Whether gitman already has machinery for "a key that no longer applies" —
  the prior audit noted a `RETIRED_TABLES` mechanism in `config.py` and an
  existing `doctor.py` check for `on_fail = "block"` with an empty `verify`.
  **Both are precedents; use them rather than inventing a fourth pattern.**
- Which option each key deserves. They may differ, and saying so is a better
  answer than one blanket verdict.

Present it as: key, recommendation, the one fact that decides it, and the cost of
the alternatives. Short. Then stop and ask.

## The durable half, which outlives all three keys

Fixing three keys leaves nothing stopping a fourth. **Propose the mechanism that
makes a declared-but-unread key impossible to ship**, and cost it concretely.

The prior audit's suggestion, which you should evaluate rather than adopt: a test
that enumerates `config.py`'s model fields and asserts each is read somewhere in
`src/`, with an explicit opt-out list for fields that are legitimately
declaration-only. devman just built the same shape for its checks — read
`devman/tests/unit/test_doctor.py`'s `_checks_in_main()` / `FIRING_TESTS` /
`INFORMATIONAL` guard as a worked precedent, including **how it derives its list
by parsing source rather than hand-maintaining a copy**, because a hand-copied
list is the same defect the guard exists to prevent.

State honestly what such a guard cannot catch: a field that is read but
misinterpreted, like `allowed_paths` — which *is* read, and still does not do
what its name says (`describe_changes`, `src/gitman/hooks.py`, returns a refusal
for matched paths too; only the message differs). That one is already filed; do
not re-audit it, but use it as the example of the guard's limit.

## Verification for B

- gitman's suite passes: `pytest -q` in its devenv shell.
- A test per key for whatever option is chosen — if implemented, a test that
  fails without the implementation; if deleted, a test or a grep proving nothing
  reads it; if marked unimplemented, a test asserting the warning fires.
- If you touch `filesystem_snapshot`, `describe_changes` or the land-hook path,
  **re-verify the land hook still works** in a throwaway `mktemp -d` colocated
  repository, and delete it afterwards. gitman's own `land` depends on it.

---

## Required reading, and the parts that bind you

Read these sections, not the whole documents:

- `devman/.scratch/projects/041-central-autoland/CONCEPT.md` — §1.1 (the
  original defect this pattern comes from), §14.4 and §14.5 (what shipped and
  the `allowed_paths` measurement), §14.7 (limits).
- `devman/.scratch/projects/041-central-autoland/DECISIONS.md` — **D18** (the
  gate that does not gate), **D19**, **D20** (skip versus stub, and why the
  negative case must be run), **D21** (a rejected architecture — do not
  re-propose a generation pointer for the overlay).
- `devman/.scratch/projects/041-central-autoland/RESEARCH-check-efficacy.md` —
  context for workstream A's incident. **Its tallies are stale**; a later phase
  closed most of the gap it names. Read it for reasoning, not for counts.
- `gitman/.scratch/projects/64-config-gate-audit/GATE-AUDIT.md` — **this is
  workstream B's specification.** Verify its claims; it was not written by
  gitman's maintainer.
- `devman/AGENTS.md` — property 4 (*"prefer a check that can fail to one that
  cannot"*), property 6 (the three registry roots and their owners), property 10
  (the boundary test).

**Binding, do not re-litigate:** devman's mode behaviour and the three-root split
(`AGENTS.md` property 6); the `0/1/2/3` exit contract; the deferred
render-to-link decision; D21's rejection of an overlay generation pointer; and
gitman's strict hook snapshot, which is a defensible design whose only flaw is
that it cannot distinguish a hook editing tracked source from a build tool
touching its own cache.

## Deliverables

1. The code changes, each on its **own gitman lane in its own repository** —
   never one lane spanning both.
2. A short record per workstream, in each repository's own convention:
   devman uses `.scratch/projects/<NNN-name>/`; gitman uses
   `.scratch/projects/<NN-name>/` with sequential numbering (it was at 64 —
   check and take the next). Each record states what was wrong, the measurement,
   what changed, what you decided and why, and what you deliberately left.
3. Verification evidence pasted, not summarised: the before/after headers for A,
   the suite counts for both, and the `PATH`-stripped run.

**Do not land or push anything without asking.** devman is already 2 ahead of
origin for a stated reason, and workstream B changes a version-control tool the
operator uses on every repository.

## Report at the end

1. Workstream A: the header before and after, in both modes, and your design
   choice with its reason.
2. Whether any other command misreports its source.
3. Workstream B: your recommendation per key, each with the one fact that decides
   it — and flag clearly that you are **waiting on the operator** if the decision
   has not come back.
4. Your proposed guard against the next declared-but-unread key, its cost, and
   what it cannot catch.
5. Anything in this prompt you found to be wrong. It was written from one
   session's measurements and the line numbers may have drifted — **the code
   wins, and say so.**
