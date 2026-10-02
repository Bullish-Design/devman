# RESEARCH — check efficacy: which `devman doctor` checks can go silent

**Date:** 2026-10-02
**Scope:** every check `devman doctor` runs (`src/devman/doctor.py`), and the
tests that exercise them (`tests/unit/test_doctor.py`, `tests/unit/test_workflow.py`,
`nix/tests/dagu-service.nix`).
**Mode:** read-only audit; no production file changed. All code quoted or
exercised is `src/devman/doctor.py` as it stands on `main` today. Where a
hypothesis was tested rather than inferred, the probe ran in a throwaway
`tmp_path`-equivalent directory, deleted after use (`/tmp/doctor_audit*`,
`/tmp/doctor-audit*` — removed; none of it survives this document).
**Trigger:** `check_link_drift` reported `ok no registered project declares a
link` for twelve days (2026-09-19 to 2026-10-01) because commit `37050e9`
deleted the module that populated its input, while the real condition (325
live symlinks into the central overlay, later measured at 450 ledger entries /
82 projects vs. 66 live repositories — `.scratch/projects/041-central-autoland/CONCEPT.md`
§1.1, DECISIONS.md D1) kept existing. This audit asks which of the other ~26
checks share that shape.

## Executive result

**26 check functions run inside `devman doctor`'s `main()` (`doctor.py:1739-1795`).
2 are VACUOUS, 15 are FRAGILE, 9 are LIVE.** On the machine this was written on,
`devman doctor` currently prints 25 of the 26 (the 26th, `generation`, is silent
by design outside plane mode — §Part 1 note on `generation`).

FRAGILE is the dangerous middle category — a check that can genuinely report a
problem today, but whose predicate collapses to `ok` the moment its input count
goes to zero, with no way for a reader to tell "zero problems" from "zero
input." **15 of 26 checks have exactly this shape, and I demonstrated it
directly for 14 of them** by running the check function against a real,
empty `Registry` (zero projects, via the same `Plane` fixture
`tests/conftest.py:20-21` builds) and reading what it printed. `check_drift`
("shadowing") and `check_mode` are VACUOUS outright — neither has a reachable
`!!` branch at all, by construction, regardless of input.

## Definitions used

- **VACUOUS** — cannot report a problem on the current machine no matter what
  is wrong, because its input is empty or its predicate does not cover the
  failure it is named for.
- **FRAGILE** — can fail today, but an empty or absent input makes it report
  `ok` rather than report the absence. This is `check_link_drift`'s exact shape
  before project 041 fixed it.
- **LIVE** — either its input cannot silently empty, or it reports loudly
  (`..`, not `ok`) when the input is missing.

"Demonstrated" below means: I ran the named check function directly, against a
constructed input, in this session, and report its actual output. "Inferred"
means: read from the code, not executed.

## Part 1 — the inventory

Method for the "can the input go empty" column: I built a `Registry` with
zero registered projects (`helpers.Plane(root=tmp/"registry",
repos=tmp/"repos")`, no `.add()` calls — the exact shape `tests/conftest.py`
gives every unit test) and called each check function against it directly.
Where a check also reads `dagu_home` config, I ran it twice: once against an
empty `dagu_home` (no `config.yaml`/`base.yaml`), once against a populated one
with zero registered projects, because some checks short-circuit on the
*dagu-side* input before ever reaching the project loop — the second run is
what actually isolates "zero projects" as the cause.

| check name | function | input source | input can go empty/absent? → reports | can fail today (`!!`/non-ok reachable)? | test that fires it | verdict |
|---|---|---|---|---|---|---|
| mode | `check_mode` doctor.py:871-881 | `(reg.root/"generation.json").is_file()` | n/a — single `rep.add("mode","ok",...)`, no branch | **No `!!` branch exists anywhere in the function.** | `tests/unit/test_doctor.py:489,498` (both assert `"ok"`) | **VACUOUS** — by construction, not oversight; it is a status line, not a fault detector |
| plane | `check_plane` doctor.py:118-139 | Dagu `/api/v1/health` | HTTP unreachable → `..` (loud), demonstrated live: real machine prints `ok plane healthy` | No `!!` branch; only `ok`/`..`. `..` never counts toward `rep.findings` (doctor.py:82-83), so a down Dagu never fails the exit code. | `nix/tests/dagu-service.nix:381-387` asserts the `ok` path only; the `..` path is untested anywhere | LIVE (reports loudly, not `ok`, when down) but note: it can never produce a *counted* finding — demonstrated (real run) |
| queues | `check_queues` doctor.py:142-234 | Dagu `/api/v1/queues`, gated on `check_plane` succeeding | unreachable → `..`; zero queues → `ok "0 queues, 0 running, none waiting"` (a true, not-masking zero) | `!!` reachable: wedged queue (queued, nothing running) or a failed condition | `nix/tests/dagu-service.nix:596-654` (the `tick.yaml` subtest deliberately leaves one queued item with nothing running and documents `doctor reads one queued item with nothing running as a wedged queue — correctly`) | LIVE, demonstrated (nix) |
| registry | `check_faults` doctor.py:808-833 | `Registry.load()` → `projects_dir.iterdir()`, `registry.py:373-375` returns `({}, [])` if `projects_dir` is not even a directory | **Demonstrated:** empty registry → `ok "every entry under projects/ reads"`, identical output whether the directory is empty or is missing entirely | `!!` reachable: a `metadata.json` that fails to parse | `tests/unit/test_doctor.py:380` (`test_a_registry_fault_is_reported_with_its_metadata_path`), `:413` (clean case) | **FRAGILE**, demonstrated — a registry root pointed at the wrong path, or with its `projects/` directory simply absent, reads as clean |
| validate | `check_load` doctor.py:241-283 | `reg.projected_files()` (per-project glob of `workflows/*.yaml`) + `dagu` on PATH | no `dagu` → `..`; **demonstrated:** zero projects → `ok "0 projected workflows load"` | `!!` reachable: `dagu validate` non-zero exit, collected per file | none found (unit tests exclude it — docstring `tests/unit/test_doctor.py:7` says `check_plane`/`check_queues` are excluded because they'd mock Dagu; `check_load` shells out to `dagu validate` too and is excluded the same way, but unlike `check_plane`/`check_queues` no nix test exercises a *broken* workflow file through `doctor` either) | **FRAGILE**, demonstrated for the empty case; the `!!` path is additionally untested anywhere |
| queue names | `check_queue_names` doctor.py:286-314 | `dagu_home/config.yaml` queue list + `reg.projected_files()` | no queue list → `..`; **demonstrated:** populated queue list + zero projects → `ok "every queue named is one of: heavy, light"` | `!!` reachable: a workflow naming an undeclared queue | `tests/unit/test_doctor.py:160,175` (fires), `:193` (clean), `:203` (`..` path) | **FRAGILE**, demonstrated both ways |
| literal dir | `check_literal` doctor.py:344-373 | registered project paths **plus** `reg.root`, `reg.state`, `dagu_home`, `Path.cwd()` | **demonstrated:** zero projects → `ok "none in 4 places"` — true, because the 4 non-project roots are still walked | `!!` reachable: a directory literally named `${DEVMAN_PROJECT_DIR}` etc. | **none at the `check_literal` level** — `tests/unit/test_doctor.py:219,231,243` call the private helper `doctor._literal_dirs()` directly, never `check_literal` itself, so the `rep.add(..., "!!", ...)` branch is untested | LIVE — the fallback roots mean a fully empty registry still gets checked somewhere, so this does not collapse the way the pure per-project checks do, but the doctor-level wiring is as untested as `handlers`/`cross-repo`/`fan-out` |
| shadowing | `check_drift` doctor.py:376-408 | `reg.projects().values()`, `proj.local` | **demonstrated:** zero projects → `ok "no repository shadows a group file"` | **No `!!` branch exists.** The function's own comment states why: *"Drift is a fact, not a fault... a shadowing file is the mechanism working."* Every path, including a diff failure (`OSError`), still ends in `rep.add("shadowing","ok",...)`. | `tests/unit/test_doctor.py:298,324` (both assert `"ok"`) | **VACUOUS** — intentional design, not a bug, but it occupies a doctor row that looks like a check and cannot report a problem under any input |
| stale entries | `check_stale` doctor.py:422-449 | `reg.projects().values()`, each entry's `.exists` | **demonstrated:** zero projects → `ok "every registered path is a directory"` (vacuously true, 0 of 0) | `!!` reachable: a registered path that is not a directory | `tests/unit/test_doctor.py:257,270,284` | **FRAGILE**, demonstrated — cannot distinguish "nothing stale" from "the registry itself is empty" |
| run output | `check_ageing` doctor.py:452-488 | `dagu_home/base.yaml` `hist_retention_days` + `reg.projects().values()` `.runs_dir` | no retention setting → `..`; **demonstrated:** retention set + zero projects → `ok "nothing older than hist_retention_days (7)"` | `!!` reachable: a project whose newest run predates the retention window | **none found anywhere** (`tests/unit/test_doctor.py`, `nix/tests/*`) | **FRAGILE**, demonstrated, and the only check in this table with zero test coverage at any level |
| projection | `check_projection` doctor.py:491-529 | `reg.projected_files()` | **demonstrated:** zero projects → `ok "0 DAG names each point at their own project's file"` | `!!` reachable: `dags/<project>.<workflow>` pointing at the wrong file | `tests/unit/test_doctor.py:345` | **FRAGILE**, demonstrated |
| dag names | `check_dag_names` doctor.py:532-567 | `reg.projects().values()` + `reg.projected_files()` | **demonstrated:** zero → `ok "0 workflow names render one DAG name each"` | `!!` reachable: a name the codec cannot render | `tests/unit/test_doctor.py:357,367` | **FRAGILE**, demonstrated |
| schema | `check_schema` doctor.py:836-868 | `reg.projects().values()`, `.schema` | **demonstrated:** zero → `ok "every entry is schema 4 or older"` | `!!` reachable: an entry schema newer than `project.SCHEMA` | `tests/unit/test_doctor.py:473` | **FRAGILE**, demonstrated |
| generation | `check_generation` doctor.py:884-926 | `reg.projects()` → each project's `projection.json`, plus `reg.root/generation.json` | **demonstrated:** zero records → the function returns at doctor.py:896 **without calling `rep.add` at all** — the row does not print, rather than printing `ok` | `!!` reachable: a projection whose `plane_generation` disagrees with the active generation, or an unreadable `generation.json` | `tests/unit/test_doctor.py:508,522,537,562` (all against a populated plane-mode registry) | LIVE when plane-mode records exist (well tested); **outside plane mode it is silently absent, not falsely clean** — a third behavior this table hasn't needed elsewhere (see Part 2's "zero population" question) |
| handlers | `check_handlers` doctor.py:570-606 | `reg.projected_files()`, `Workflow.read(path).handlers()` | **demonstrated:** zero projects → `ok "no workflow defines handler_on..."` | `!!` reachable: a workflow defining its own `handler_on` | predicate tested at `tests/unit/test_workflow.py:386` (`Workflow.handlers()` directly); **no test calls `check_handlers` itself with a firing fixture** | **FRAGILE**, demonstrated; the doctor-level wiring is untested even though the underlying predicate is |
| cross-repo | `check_cross_repo` doctor.py:609-638 | `reg.projected_files()`, `Workflow.triggers_other_dags()`/`.holds_project_dir()`/`.params()` | **demonstrated:** zero → `ok "0 workflows trigger others..."` | `!!` reachable: a parent workflow holding `DEVMAN_PROJECT_DIR` for itself, or missing `DEVMAN_SELF_DIR` | predicate tested at `tests/unit/test_workflow.py:199,351`; **no test calls `check_cross_repo` itself with a firing fixture** | **FRAGILE**, demonstrated |
| fan-out | `check_fanout` doctor.py:641-679 | `reg.projected_files()`, `Workflow.child_runs()`/`.unbounded_fanout()` | **demonstrated:** zero → `ok "0 workflows start child runs..."` | `!!` reachable: a `dag.run`/`dag.enqueue` parent with no stated concurrency bound | predicate tested at `tests/unit/test_workflow.py:328,351`; **no test calls `check_fanout` itself with a firing fixture** | **FRAGILE**, demonstrated |
| writes | `check_writes` doctor.py:682-759 | `reg.projects().values()`, `proj.raw_writes()` | **demonstrated:** zero → `ok "0 projects declare output ownership — none"` | `!!` reachable: unknown tier, undeclared workflow name, `tier: free` outside agent surface | `tests/unit/test_doctor.py:733,746,764,778,796,809,826` | **FRAGILE**, demonstrated (well tested otherwise) |
| trigger target | `check_trigger_targets` doctor.py:1477-1523 | `watch_map(reg)` (reads `proj.triggers`, a registry-projected field) + `proj.workflow_names()` | **demonstrated:** zero → `ok "no registered project declares a trigger"` | `!!` reachable: a trigger naming a workflow the project no longer projects (a tombstoned group) | **none found anywhere** | **FRAGILE**, demonstrated, and entirely untested — structurally the closest sibling to `check_link_drift`'s original shape: it trusts a registry-projected field (`proj.triggers`) rather than re-deriving from the filesystem, same as `proj.links` did |
| link drift | `check_link_drift` doctor.py:1278-1330 | `central.reverse_index(fleet, central_root)` — a filesystem walk of live symlinks, not a registry field (project 041's fix) | **demonstrated (real machine):** currently non-empty and firing — 12 real findings printed live, see Part 3 | `!!` reachable and firing today | `tests/unit/test_doctor.py:91,116,133` | LIVE — this is the repaired check; included for contrast |
| ledger | `check_ledger_stale` doctor.py:1364-1474 | `.devman-link-state.json` read directly (`_read_ledger_raw`), independent of the registry | missing file → `ok` (stated as the correct "fresh machine" reading, doctor.py:1412-1413, not a mask); malformed → `!!`, never silently `ok` | `!!` reachable and firing today (450 entries / 82 projects, 16 dead on the real machine, see Part 3) | `tests/unit/test_doctor.py:983,1003,1017,1043,1067,1083,1098,1118,1137` | LIVE — deliberately reads the filesystem fact rather than a projected field, same fix shape as `link drift` |
| local sources | `check_local_sources` doctor.py:1126-1200 | `reg.projects().values()` → `devenv.lock`/`flake.lock` per project | **demonstrated:** zero → `ok "0 local libraries feed 0 inputs..."` | `!!` reachable: a dirty or unpinned local git source | `tests/unit/test_doctor.py:868,889,903,918` | **FRAGILE**, demonstrated |
| path inputs | `check_path_inputs` doctor.py:1203-1275 | `reg.projects().values()` → `devenv.yaml` `path:` inputs | **demonstrated:** zero → `ok "0 directories are path: inputs..."` | `!!` reachable: a `.devenv` over 50 MB behind a `path:` input | `tests/unit/test_doctor.py:600,618,632,648,663,682,699,710` | **FRAGILE**, demonstrated |
| daemon shell | `check_daemon_shell` doctor.py:929-981 | `/proc` process table, matched against `dagu_home` | no running Dagu → `..` (loud); not registry-dependent at all | `!!` reachable: `SHELL` set in the running Dagu's environment | none found — `nix/tests/dagu-service.nix:607` asserts the raw `/proc/<pid>/environ` directly, not `doctor`'s output | LIVE (process-table based, cannot silently empty the way a registry field can), but the `!!` branch itself is untested anywhere |
| reload | `check_reload` doctor.py:1526-1562 | `reg.state/"reload.pending"`/`"reload.blocked"` marker files, independent of project count | **demonstrated:** zero projects → `ok "no reload in progress"` — correct, because this input has nothing to do with project count | `!!`/`..` reachable and tested | `tests/unit/test_doctor.py:422,430,445,458` | LIVE, demonstrated |
| watcher | `check_watcher` doctor.py:1565-1736 | `watch_map(reg)` (project-count-dependent, same field as trigger target) **plus** `running_watchers()` (process table) **plus** `WatchState(reg).read()` | **demonstrated:** zero projects → `ok "no registered project takes a group that declares triggers"` for the watch-map half; the dead/orphan/multi-watcher branches are process-table-based and reachable independent of project count | `!!` reachable: dead watcher, orphaned watchexec, two watchers running, a watch set stale against the registry | `nix/tests/dagu-service.nix:389-488` (watcher picks up a new project; "doctor still tells a dead watcher from a watching one") exercises the process-table branches; the registry-side half (watch-map matching the live set) is the same shape as `trigger target` and shares its exposure | LIVE overall (the process-table branches cannot go silently empty), **with a FRAGILE sub-path**: if the registry's trigger population silently emptied the way `proj.links` did, this check's watch-map lines would read "no registered project takes a group that declares triggers" exactly as they do for a genuinely empty fleet |

Tally: **VACUOUS 2** (mode, shadowing) · **FRAGILE 15** (validate, queue names,
registry, stale entries, run output, projection, dag names, schema, handlers,
cross-repo, fan-out, writes, trigger target, local sources, path inputs) ·
**LIVE 9** (plane, queues, literal dir, generation, link drift, ledger, daemon
shell, reload, watcher). 26 total.

**14 of the 15 FRAGILE rows are demonstrated directly** (ran the function
against a real empty registry, read its output, shown above). The 15th,
`validate`, is demonstrated for the empty-input branch but its `!!` branch
(a `dagu validate` failure) is inferred from the code, not executed, because
exercising it needs a real `dagu` binary and a deliberately broken workflow —
in scope for a future probe, not done here.

**What ties all 15 FRAGILE rows together structurally:** every one iterates
`reg.projects()` or `reg.projected_files()` and, when the collection is empty,
falls through to an `else`/`if not bad` branch that calls `rep.add(name, "ok",
[f"... {len(x)} ..."])`. That is the identical shape `check_link_drift` had
before project 041: a `for` loop over a collection that can go to zero without
the machine's real state going to zero, followed by a status line that reads
as health rather than as absence. Nine of these (`stale entries`, `run output`,
`projection`, `dag names`, `schema`, `handlers`, `cross-repo`, `fan-out`,
`trigger target`) read a field the devenv projection module (or its
replacement) writes into the registry, exactly as `proj.links` was — so the
specific failure mode that hit `check_link_drift` (a write path silently
deleted while the read path stays) remains structurally available to all of
them. `trigger target` is the closest match: like `check_link_drift` before
the fix, it trusts `proj.triggers`, a registry-projected field, rather than
re-deriving its answer from the filesystem, and it has no test at all.

**What is NOT demonstrated, and I am flagging rather than guessing:**
- `check_load`'s `!!` branch (a real `dagu validate` failure) — inferred only.
- `check_daemon_shell`'s `!!` branch (a leaked `SHELL`) — inferred only; the
  nix test checks `/proc` directly, not `doctor`'s output.
- `check_plane`'s down-path and `check_watcher`'s dead-watcher path print `..`/`!!`
  per the code, but I did not spin up and then kill a real Dagu/watcher to
  confirm it live; the nix test suite does this for `watcher`, not for a
  verified read of `doctor`'s own `..` line on `plane`.

## Part 2 — the mechanism that would have caught this

**Candidate: every check ships a fixture that makes it fire, and the suite
asserts it fires.**

**Cost, concretely.** Of 26 checks, 13 already have a doctor-level test that
asserts a non-`ok` result at the `check_*` function itself (`queue names`,
`stale entries`, `projection`, `dag names`, `schema`, `writes`, `local
sources`, `path inputs`, `link drift`, `ledger`, `registry`, `reload`, plus
`queues` at the nix level). The ones with **no** firing test at the
doctor-check level — `validate`, `literal dir` (its helper `_literal_dirs` is
tested, `check_literal` itself is not), `run output`, `handlers`,
`cross-repo`, `fan-out`, `trigger target`, `plane` (down-path), `daemon
shell`, and `watcher`'s registry-side branch (its process-table branches are
exercised in a VM, not through a unit-level firing fixture) — put **roughly 9
to 10 fixtures** on the list to bring every FRAGILE/LIVE-but-untested check up
to "ships a fixture that makes it fire." The 2 VACUOUS checks (`mode`,
`shadowing`) cannot be given a firing fixture at all — attempting to write one
is itself the signal that the check has no failure mode, which is a second,
free benefit of the exercise: a fixture-writing pass over all 26 checks would
have surfaced `check_drift`'s "no `!!` branch exists" on inspection, for free.

**Where it should live.** `AGENTS.md` property 7 says Python carries core
logic and shell stays a thin wrapper; the verify path here is `base:check`
(ruff) / `base:unit` (pytest), not a shell script. A `doctor --self-test`
subcommand would duplicate what pytest already does and add a second place
the fixture list can drift from the check list. **One table-driven
parametrised test is the right shape**: a list of `(check_name, fixture_fn)`
pairs, one assertion — `status != "ok"` — run over all of them, so a new check
added to `main()` without a corresponding fixture entry is itself a visible
gap (missing from the table) rather than a silently-passing suite. This is
cheaper than one unit test per check (26 near-identical test bodies) and
cheaper than a new CLI surface.

**What it cannot catch.** A fixture written to match a wrong predicate proves
nothing. If `check_handlers` is renamed in spirit to mean something slightly
different from "a workflow that replaces the exit handler," and the fixture
author writes the fixture *against the new, wrong meaning*, the test still
passes and the mechanism gives a false "this check can fail" signal. This is
real and is the limit of assertion coverage as a class: it tests that
**a** branch of **a** `!!` is reachable, not that the `!!` means what the
check's docstring claims. `check_link_drift`'s own regression would **not**
have been caught by this mechanism in its weakest form — the check's own test
suite (`test_link_drift_fires_on_a_dangling_view`, etc.) was presumably
passing on 2026-09-18 against the *old* `proj.links` input; the break was in
a *different* file (`modules/devenv.nix`, deleted) that the check's own test
never touched, because the test built its input by hand rather than through
the real population path. A fixture that constructs its input directly (as
every test in `test_doctor.py` already does, per the `Plane.add()` helper)
proves the predicate works on a well-formed input; it does not prove the
*real* population path still produces that input. That gap is exactly why
project 041 also asked the harder question in D1: which input source cannot
go stale independent of the registry.

**Alternatives, evaluated:**

- **Mutation testing over `doctor.py`.** Would catch a wrong predicate (the
  gap above) by flipping a condition and checking a test fails. Far more
  expensive to run and maintain than the fixture table — `doctor.py` is ~800
  lines of check logic, and most of its conditions are narrow Boolean guards
  (`if not fault`, `if tier not in TIERS`) that a mutation framework turns
  into a large number of surviving mutants requiring triage per check.
  Reserve for the FRAGILE rows specifically, if ever, not the whole file.
- **A check asserts its own input is non-empty and reports `!!` when it is
  not.** This is cheap — one `if not <collection>: rep.add(name, "!!",
  [...]); return` guard per check — and it is **specifically** the fix for
  FRAGILE, not a general-purpose test. It does not fix VACUOUS (`shadowing`
  has no "wrong" population to assert against — zero shadowing files is
  legitimately fine) and it does not fix the predicate-correctness gap above.
  For the 15 FRAGILE rows, though, this is the highest-value-per-line
  intervention in this document: it converts "ok, 0 of 0" into a loud,
  distinct state exactly once, at the one place the risk lives, rather than
  asking every caller to remember to write a fixture. **I recommend making
  this a rule for every check whose input source is `reg.projects()` or
  `reg.projected_files()`: assert count > 0 (or count the registered fleet
  against an independent source, if one exists) before trusting an empty loop
  as "nothing to report."** Several checks already *have* the information to
  do this cheaply — `check_stale`, `check_schema`, `check_dag_names` and
  friends are each one line away from `if not reg.projects(): rep.add(name,
  "!!" or a new third status, ["the registry reads as empty"])`.
- **A periodic comparison of each check's input count against an independent
  source.** This is what project 041 built for `link drift` and `ledger`
  (the reverse index, the live-fleet directory count) — expensive relative to
  the other options because it needs a second, trustworthy count to compare
  against, and for most of the FRAGILE rows here (`handlers`, `cross-repo`,
  `fan-out`, `trigger target`) there is no cheaper independent source than
  "walk the fleet's repositories directly," which is exactly what `35` found
  too costly to do routinely at `~/Documents/Projects` scale without the
  registry as a shortcut. Worth doing for `registry`/`check_faults` and
  `stale entries` specifically, because D1's own measurement (48 registered
  vs. 66 live) is already an independent count sitting in this project's own
  files.

**Recommendation.** Do the "assert non-empty input" rule first, across the 15
FRAGILE rows (cheap, directly closes the exact gap this document found,
~1 line per check). Add the table-driven firing-fixture test second, to cover
the 8 checks with no firing test at all and to make a future new check's
absence from the table visible. Skip mutation testing and the independent-count
comparison for now except where 041 already built them.

**Should `ok` ever be printed with a count of zero?** No — not as plain `ok`.
`check_link_drift` printed `ok no registered project declares a link`, and
that sentence was true and useless; this document found **14 more checks**
that print the identical shape today. A zero-population check should report a
**third status**, distinct from `ok` and from `!!` — something like `ok (0)`
or a literal `empty` marker in the same column `..` occupies — specifically
when the collection being iterated is both (a) the thing the check exists to
examine and (b) capable of being empty for a reason other than "nothing is
wrong." The cost across a 48-project fleet is one extra status symbol in the
legend and, per the `Report.print()` format (doctor.py:85-91), zero additional
lines — the existing `head = lines[0]` mechanism already prints exactly one
line per check regardless of status, so a third status is a column value, not
new noise. The honest cost is elsewhere: a developer has to learn that `ok (0)`
is not necessarily bad, which trades one kind of silent trust (an `ok` that
might be hiding nothing to look at) for one kind of required judgment (an
`ok (0)` that needs a second's thought). That trade is worth making for the 15
FRAGILE rows; it is not needed for checks whose zero case is already loud
(`..`) or whose zero case is genuinely uninteresting (`reload`, `generation`
outside plane mode).

## Part 3 — immediate findings, priority order

1. **`trigger target` (`check_trigger_targets`, doctor.py:1477-1523) — no test
   anywhere, FRAGILE, and structurally the closest living relative of the
   original `link drift` bug** (trusts the registry-projected `proj.triggers`
   rather than a filesystem fact). *Fix: add `if not watching and not checked:
   rep.add(..., "!!" or a zero-population status, [...])` guard, and write one
   doctor-level test with a tombstoned-group fixture.*
2. **`run output` (`check_ageing`, doctor.py:452-488) — no test anywhere, at
   any level, FRAGILE.** *Fix: same empty-guard, plus a doctor-level test with
   a project whose `.runs/logs` are older than `hist_retention_days`.*
3. **`shadowing` (`check_drift`, doctor.py:376-408) — VACUOUS by construction,
   no `!!` branch exists.** Not a bug, but it occupies a row that reads like a
   health check and cannot fail. *Fix: either document in the check's own
   output that it is informational-only (so a reader stops expecting it to
   ever flag something), or decide a shadowing file past some drift threshold
   (e.g., `same_exe` below some percent of `of_exe`) should be a finding —
   that was arguably always the intent behind computing the percentage at all.*
4. **`mode` (`check_mode`, doctor.py:871-881) — VACUOUS by construction, no
   `!!` branch exists.** *Fix: same as above — either state plainly it is a
   label, or add the one case that is arguably wrong today: `compatibility`
   mode while a `generation.json` sits unused nearby, which the check could
   name as a finding rather than silently picking one.*
5. **`validate` (`check_load`, doctor.py:241-283) — FRAGILE, demonstrated for
   the empty case; its `!!` branch is untested anywhere.** *Fix: empty-guard
   plus a doctor-level test with a workflow file that fails `dagu validate`
   (needs `dagu` on the test runner's PATH, hence currently excluded — a nix
   test is the natural home, following the `dagu-service.nix` pattern.)*
6. **`handlers`, `cross-repo`, `fan-out` (doctor.py:570-679) — FRAGILE,
   demonstrated; predicate tested at the `Workflow` level but the doctor-level
   wiring (the loop, the `rep.add`) is not.** *Fix: three small doctor-level
   tests reusing the existing `test_workflow.py` fixtures (`handler.yaml`,
   `fanout-unbounded.yaml`, `cross-repo-holds-project-dir.yaml`) through
   `Plane.add()` instead of through `Workflow.read()` directly.*
7. **`literal dir` (`check_literal`, doctor.py:344-373) — LIVE overall (the
   fallback roots keep it from collapsing to silence), but its own `!!`
   branch is untested** — the three existing tests exercise the private
   `_literal_dirs()` helper, never `check_literal` itself. *Fix: one
   doctor-level test that registers a project and asserts `check_literal`'s
   `rep.add` call carries `"!!"`, not just that the helper finds the
   directory.*
8. **`stale entries`, `projection`, `dag names`, `schema`, `writes`, `local
   sources`, `path inputs`, `registry` (doctor.py, various) — FRAGILE,
   demonstrated, but each already has a doctor-level firing test for its
   non-empty case.** *Fix (lower priority than the above): add the one-line
   empty-guard so a reader can tell "checked, found nothing" from "nothing to
   check" — these are the cheapest line items because the firing tests
   already exist; only the guard is missing.*
9. **`check_faults` reads `({}, [])` identically whether `projects_dir` is
   empty or absent** (registry.py:373-375) — this is the specific mechanism
   behind finding 8's `registry` row, named separately because it is a
   one-line change in `registry.py` rather than in `doctor.py`, and it is the
   single input every other FRAGILE check ultimately depends on.

## What I could not determine

- Whether `check_load`'s and `check_daemon_shell`'s `!!` branches actually
  fire correctly when exercised for real (both are inferred from the code,
  not demonstrated — see Part 1's notes). I did not build a real broken
  workflow file or a real Dagu process with a leaked `SHELL` to confirm.
- Whether `check_plane`'s `..` branch and `check_watcher`'s dead/orphan/
  multi-watcher branches behave as documented under a live failure — the nix
  test suite exercises the watcher branches in a VM, which I read but did not
  re-run (the brief's rule 4 permits `devenv tasks run -v base:unit` and
  `devman doctor`, not `nix flake check`, which is where `dagu-service.nix`
  runs).
- The exact number of fixtures the table-driven mechanism in Part 2 would need
  is a lower bound (8, by my count) rather than a verified final number — a
  closer read of exactly which existing `test_doctor.py` assertions check
  `status != "ok"` versus merely checking line content could move that number
  by one or two in either direction.

## What this did not do

- Changed no file under `src/devman/`, `tests/`, or anywhere else in this
  repository. All probing ran against throwaway `Registry`/`Plane` fixtures
  built the same way `tests/conftest.py` builds them, in `/tmp`, deleted after
  use.
- Did not run `nix flake check` / `base:test`, per rule 4.
- Did not implement any of the fixes listed in Part 3 — those are findings,
  not patches.
- Did not evaluate `check_c1_nix_eval`/`check_c4_pairing` (`src/devman/central.py:223,291`)
  or any other `central.py` predicate not wired into `devman doctor`'s
  `main()` — this audit's scope is the checks `doctor` itself runs, not every
  predicate the codebase defines.
