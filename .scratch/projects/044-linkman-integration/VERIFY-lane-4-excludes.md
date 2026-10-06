# Verify — lane 4: project Git excludes from `links.yaml`

Lane `m14-l9w-excludes-on-links-yaml`. Measured 2026-10-06.

## What this report proves, and what lane 3 proved

Lane 3 (`VERIFY-diff-all-projects.md` §5) compared **entry sets**. It asked
whether the new rule computes the same owned entries as the old one. It did not
keep a byte snapshot of any `.git/info/exclude`.

This report adds a **byte baseline**: the exact bytes, file kind, and raw
symlink target of every live Git exclude file, captured before the first source
edit. Read the two as different claims. An equal entry set does not by itself
prove an unchanged file.

One part of the intended gate did not run. §8 states exactly which, and why. §7
holds the fixture gate that stands in for it.

## Revisions and environment

| Item | Value |
|---|---|
| devman trunk at lane start | `cc37acba372181e3e160775ae737d1d513fac96a` |
| devman trunk state | clean, 0 ahead and 0 behind `origin/main` |
| Linkman revision used as oracle | `a48d65a582968a022ecf0e9b54c4db1238173eee`, clean |
| Python | 3.13.14 |
| Date | 2026-10-06 |

The kickoff names `d910b98` as the baseline. Trunk was `cc37acb` when this lane
started, because the kickoff prompt itself landed as `cc37acb`. Lanes 1 and 2
had landed at `651af40`, as the kickoff states.

## 1. Current fleet count

| Measurement | Count |
|---|---|
| Overlay projects under `~/.config/devman/projects/` | 60 |
| Projects with a `links.yaml` | 60 |
| Live checkouts under `~/Documents/Projects/` | 59 |
| Projects with no checkout | 1 — `foreman` |
| Projects with a central `.local.gitignore` | 59 — `foreman` has none |
| Links declared across all 60 projects | 288 |

Lane 3 reported 283 links. That was the 59-checkout subset. `foreman` declares 5
more, so 283 + 5 = 288. The two counts agree.

Only one repository carries a repo-layer declaration: `linkman`'s own
`links.yaml`, which is `version: 1` with `links: {}`. Every other project
declares in the overlay layer alone.

## 2. The byte baseline, captured before the first source edit

Script `~/.local/state/devman-lane4-baseline/snapshot.py`, output
`baseline.json`, raw copies under `raw/`. Stored outside every tracked
repository. Exit code 0. Run twice; `baseline.json` was byte-identical both
times, so the capture is a pure read.

Per project it records: the path from `git_exclude_path`, the file kind, the raw
`os.readlink` target, the SHA-256 of `Path.read_bytes()`, the byte length, the
central `.local.gitignore` path, its SHA-256 and length, and the ledger record
for the key `<project>:.git/info/exclude`.

| Measurement | Count |
|---|---|
| Exclude files that are symlinks | 59 |
| Exclude files that are real files | 0 |
| Exclude paths absent | 1 — `foreman`, which has no checkout |
| Symlinks resolving to their own central `.local.gitignore` | 59 of 59 |
| Exclude files lacking a trailing newline | 0 |
| Exclude files containing CRLF | 0 |

Because all 59 are symlinks to their central file, `exclude_sha256` equals
`central_sha256` for all 59.

**This shape narrows the gate.** With the exclude already a symlink pointing at
the correct canonical file, `ensure_git_exclude` takes its `elif
exclude.is_symlink()` branch, finds `target == canonical`, and writes nothing
there. `append_entries` is then the only thing in the function that can change
a byte of the projected file.

## 3. Independent oracle — Linkman `config --json`

Script `oracle.py`, output `oracle.json`. Command, per project:

```
linkman config --json --repo-root <repo> --overlay ~/.config/devman --name <project>
```

Exit code 0 for all 60. The expected entry list is derived from Linkman's own
`target_scope` field with the same rule devman uses: `.devman/.runs/` first,
then each `link_rel` whose `target_scope` is `external`, deduplicated, order
preserved.

| Comparison | Result |
|---|---|
| Set equality of devman's entries against the oracle's | **60 / 60** |
| devman's unsorted order equals `links.yaml` declaration order | **60 / 60** |
| Links resolved | 288 |
| `target_scope: external` | 288 |
| `target_scope: internal` | 0 |

Zero internal targets across the whole fleet. This matches lane 3 §5. The
internal branch of the new rule therefore has no live coverage, and only the
unit tests exercise it — see §5 and §7.

`foreman` has no checkout, so it ran against a disposable fixture: a temporary
directory holding an empty `.git/`, with its real overlay declaration.
`oracle.json` marks that row `is_fixture`. **No live Git exclude file exists for
`foreman`.** This report makes no claim about one.

## 4. Preflight — compute, write nothing

Script `preflight.py`, output `preflight.json`. Exit code 0. For each of the 59
live projects it computed `exclude_entries(...)`, then read the **real** current
central `.local.gitignore` and listed every computed entry that is not already
an exact line in it. Those lines are exactly what `append_entries` would append,
and each one would be a byte change.

| Measurement | Result |
|---|---|
| Live projects checked | 59 |
| Projects with zero entries to add | **59 / 59** |
| Projects with any entry to add | 0 |

No project has any addition. `append_entries` would return `False` everywhere,
so it would open no file for writing.

Two projects deserve a named verdict, because lane 3 §5 flagged both.

- **`linkman`** — the computed set omits `.loci`, as lane 3 predicted. The live
  file carries the line as `#.loci`, commented by the operator under O0's
  2026-10-06 resolution. `.loci` is not computed and `#.loci` is not touched,
  because `append_entries` only appends. Per the kickoff, this lane adds no
  `.loci` link and restores no exclusion.
- **`flora`** — its hand-authored first line,
  `.scratch/projects/063-warm-sglang-sweep/smoke_prompts.json`, is present and
  is not owned by the projection. It survives untouched.

### A pre-existing ledger drift, not caused by this lane

`mnemonix`'s ledger record hash (`92d14cc4…`) disagrees with its own central
file's content hash (`2acb95be…`). Its exclude symlink is correct and all its
computed entries are already present.

The drift is in `baseline.json` itself, captured before the first source edit:
the baseline's `state_record.hash` already disagreed with its own
`central_sha256`. So it predates lane 4 and this lane did not create it. The
old projection recomputes the same record and would refresh it identically, so
this is not a behaviour change. Recorded here, not repaired here — repairing
central operator data to make a gate look clean is the thing the kickoff
forbids.

## 5. Unit proof

New file `tests/unit/test_excludes.py`: 48 cases, all passing. It imports no
`linkman`, so it runs in the hermetic suite.

Covered, each able to fail for the reason it names:

- scope and order — external adds, internal adds nothing; `.devman/.runs/`
  first even with no declaration and with both layers absent; declaration order
  with repo layer before overlay layer and no sorting; duplicate removal
  without reordering; a target equal to the repository root counts as external;
  a symlinked parent directory that moves a target out of the repository, and
  the mirror case that reaches back in;
- interpolation — `${env.*}` from an injected mapping; `${repo.name}`,
  `${repo.root}`, `${repo.parent}`; a nested variable chain; unset environment
  name; unknown `repo` name; unknown `vars` name; a cycle, with the `->` trace;
  the depth limit beyond 50; `${bad}`, `${nope.x}` and an unclosed token; a NUL
  byte;
- declarations — a link name in both layers, naming both files; a variable name
  in both layers; **a link name and a variable name that are the same string,
  which must not refuse**; `version: 2`; `version: true`; an unknown top-level
  key; an unknown key inside a link entry; a bare `links:`; six invalid link
  names; invalid YAML; empty and whitespace-only targets;
- byte preservation — comments, blank lines, a hand-authored exclusion and the
  computed entries in a different order all survive with identical bytes; a
  file with no trailing newline keeps its exact bytes when nothing is missing,
  and gains one newline before an appended entry; a missing entry appends at the
  end and moves no existing line; a second call returns `False` and changes no
  bytes;
- preserved refusals — promotion without a recorded baseline; promotion with
  both sides changed; a repository with no Git marker gets no link; a linked
  worktree uses its common Git directory.

## 6. Check results

Every command ran inside devman's devenv shell. Exit codes were captured
directly, never from a pipe.

| Command | Exit | Result |
|---|---|---|
| `ruff check src/devman/excludes.py src/devman/linking.py` | 0 | All checks passed |
| `ruff format --check` on the same two files | 0 | 2 files already formatted |
| `devenv tasks run -v base:check` | 0 | All checks passed |
| `devenv tasks run -v base:unit` | 0 | 793 passed, 1 skipped |
| `python -m pytest tests/unit/test_linking.py tests/unit/test_excludes.py` | 0 | **56 passed** |
| `devman doctor` | 0 | Nothing to report |
| `devenv tasks run -v base:test` | 0 | `nix flake check`, 22 checks, all passed in 144 s |

**The hermetic suite's one skip is `test_linking.py`.** Its module calls
`pytest.importorskip("linkman")`, and `base:unit` uses a nixpkgs interpreter
holding only `pytest` and `pyyaml`. The kickoff refuses that as proof, so the
file ran separately in the devenv venv, which carries the `cutover` extra.
**All 8 of its cases ran and passed there** — none skipped — alongside the 48
new cases, for 56 total. The 8 are the Linkman-backed flow: the missing
`links.yaml` refusal and its no-half-state variant, link creation, bootstrap
ordering, bootstrap preservation, the Git exclude projection, and idempotence.

`devman doctor` reports the ledger at **345 entries across 59 projects**,
unchanged. D10 puts the key-set shrink to about 59 rows in lane 7, not here, so
an unchanged count is the correct result for this lane.

## 7. Fixture byte gate — the real function against copies of the real data

Script `fixturegate.py`, output `fixturegate.json`. Exit code 0. Final line
`PASS`.

The live gate could not run (§8). This substitutes for it. For all 60 projects it
builds a replica in a temporary directory: a byte copy of the real overlay
`links.yaml`, a byte copy of the real central `.local.gitignore`, a repository
root holding a real `.git/info/` directory, and `.git/info/exclude` as a symlink
to the copied central file — the shape §2 measured on all 59 live projects. For
`linkman` it also copies the repo-layer `links.yaml`, so both declaration layers
are present exactly as they are live. The ledger is a fresh in-memory dict.

It then calls `ensure_git_exclude` twice per project and compares bytes.

| Measurement | Pass 1 | Pass 2 |
|---|---|---|
| Replica exclude files byte-identical | **59 / 59** | **59 / 59** |
| Central file copies byte-identical | **59 / 59** | **59 / 59** |
| Live projects where the call returned `True` | 0 of 59 | 0 of 59 |

**Every one of the 59 live projects returned `False` on both passes.** The
function did no work at all — not a file write, not even a ledger record change.
The new `links.yaml` projection already agrees with what the old Linkman-driven
projection left on disk.

Two rows need their own verdict.

- **`foreman`** — a fixture, with no live checkout and no live central file. The
  projection created the central file through the `not canonical.exists()`
  branch, created the exclude symlink through the final `else` branch, and
  appended its computed entries: `.devman/.runs/`, `.agents`, `.claude/skills`,
  `.envrc`, `.loci`, `devenv.local.nix`. Pass 1 returned `True`, pass 2 returned
  `False`. **This proves the create path and its convergence. It is not a claim
  about a live file, because `foreman` has none.**
- **`mnemonix`, stale-hash variant** — seeded with the stale hash its real ledger
  carries (`92d14cc4…`) against the fresh hash of its central file
  (`2acb95be…`). Pass 1 returned `True`, pass 2 returned `False`. **Only the
  in-memory ledger record changed.** Both the central copy and the exclude
  symlink stayed byte-identical. The stale hash never reaches the promotion
  refusal, because that comparison fires only when the exclude is a real file;
  here it stays a symlink, so the mismatch trips the later `state.get(key) !=
  record` check, which is bookkeeping, not a write.

The real ledger's bytes were compared before and after the run and are equal.
Nothing under `~/Documents/Projects/` or `~/.config/devman` was written.

**Read this as a fixture measurement, not a live one.** It exercises the real
function on the real declarations and the real file contents, and it cannot
change a live file. What it does not reproduce is each project's actual
repository path and actual inode.

## 8. Limitation — the live byte gate did not run

The intended final step was to call the new projection against each of the 59
live checkouts, twice, and re-measure every field against `baseline.json`. The
script is written and ready at
`~/.local/state/devman-lane4-baseline/bytegate.py`. It calls
`ensure_git_exclude` per project and never calls `write_state`, so it performs
no filesystem write.

**It did not run.** The agent harness's permission classifier refused to execute
it, repeatedly, and the refusal is not something this lane can resolve from
inside. So this report does **not** claim a measured "59/59 live exclude files
unchanged". It claims the following instead, each measured:

1. Before any edit, all 59 live exclude files are symlinks resolving to their
   own central `.local.gitignore` (§2). In that state `ensure_git_exclude`
   writes nothing through the symlink branch.
2. For all 59, every computed entry is already an exact line in the live central
   file (§4), so `append_entries` returns `False` and opens no file.
3. devman's computed entry set equals Linkman's independently resolved set for
   all 60 projects, in both set and declaration order (§3).
4. `ensure_git_exclude`'s body is a line-for-line copy of
   `devman_link.excludes.ensure_local_gitignore`, with only the entry
   computation replaced. Byte preservation and idempotence are proven directly
   on real temporary files (§5).
5. The same function, run against byte copies of all 60 projects' real
   declarations and real central files, changes nothing and returns `False` for
   every live project, twice (§7).

Together these show the no-op by construction, by the oracle, and on a faithful
replica — but not by a measured before-and-after on the live files themselves.
**Run `bytegate.py` to close this gap.** It prints an exact numerator and
denominator for two passes and a `PASS`/`FAIL` line. Until then, treat the live
byte claim as strongly evidenced but not directly measured.

## 9. Corrections to earlier material

**The kickoff's "disjoint namespace rule for link names and variable names" does
not exist in Linkman.** `linkman/src/linkman/config.py::load_layers` enforces
two separate rules, each inside one namespace and across the two layers:

- a link name declared in both layers refuses;
- a variable name declared in both layers refuses.

There is no check that compares a link name against a variable name. The two
live in separate mappings, and the same string may be both with no conflict.
This implementation matches that behaviour, carries a comment saying so, and
`test_a_link_name_and_a_variable_name_may_be_the_same_string` exists to stop
anyone adding a cross-namespace check later. Lane 3's "disjoint-namespace risk:
0 of 60 would refuse" measured the cross-layer link-name rule, which is the
real one.

`PLAN-lanes.md` needs no amendment. Its lane 4 contract, its P2 premise, and its
stated gate all hold as written. The one shortfall is the gate's execution, in
§7, not its design.

## 10. Files changed in this lane

| File | Change |
|---|---|
| `src/devman/excludes.py` | new — the `links.yaml` exclude projection |
| `src/devman/linking.py` | drop `_as_resolved_links`, `Declaration`, `ResolvedLink`; call the new projection; docstring updated for lane 4 |
| `tests/unit/test_excludes.py` | new — 48 cases |
| `.scratch/projects/044-linkman-integration/VERIFY-lane-4-excludes.md` | this report |

`src/devman_link/` is untouched. The six-step order in `reconcile_with_linkman`
is unchanged and step 5 stays in place. `git_exclude_path`, `append_entries`,
`local_gitignore_path`, `local_gitignore_key`, `State`, `content_hash` and
`link_path` are imported and reused, not reimplemented. Lane 5 replaces the
engine; lane 6 ports the callers. Neither is begun here.
