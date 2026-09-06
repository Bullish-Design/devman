# Project 009 — deep code review

Date: 2026-08-31

## Executive verdict

devman has a strong architecture, an unusually explicit safety charter, and a
good Python test suite. Its best mechanisms are built around the correct idea:
a successful run in the wrong repository is worse than a loud refusal.

The implementation does not yet uphold that rule at every entry point. I found
six P1 defects. Four can route work through the wrong runtime context, one can
make valid projects unprojectable or give them invalid Dagu identities, and one
can expose an unauthenticated control plane if an advertised option is changed.
The most important defects sit in the generated projection header and in
parameter resolution. Both are trusted boundaries.

The green baseline is real but incomplete. Ruff passed, all 236 Python and
pinned-Dagu tests passed, and the live 54-project plane reported healthy. Those
checks do not execute the exact generated projection or the daemon-owned
schedule path. Several confirmed defects therefore survive all three signals.

My release recommendation is: do not broaden adoption, add more scheduled
workflows, or expose the service beyond loopback until P1-1 through P1-6 are
fixed and covered at the real projection boundary.

## Priority scale

- **P1 — fix before the next release.** The defect can run the right workflow in
  the wrong place, break a core execution path, or expose the control plane.
- **P2 — fix soon.** The defect creates a late failure, hides corruption, or
  leaves a major contract unproved.
- **P3 — hardening.** The defect causes misleading output, avoidable work, or an
  invalid configuration that another check eventually finds.

No P0 was found. The default installed plane is loopback-only, and I found no
unprompted remote code path or unconditional data-loss path.

## Scope and method

I reviewed the complete library path rather than only `src/devman/`:

- the project 006 charter and stage logs;
- the project 007 proposal and stage log;
- `README.md`, `USER.md`, `AGENTS_GUIDE.md`, and `tests/README.md`;
- every Python module in `src/devman/`;
- the devenv projection module;
- the NixOS service module, packaging, flake checks, and task graph;
- every unit and Dagu conformance test;
- every shipped and local workflow;
- the live service configuration, registry, generated projection, and scheduler
  environment where a read-only check was useful.

I then built disposable reproductions for the Python findings and invoked the
actual projection store script for the producer-side findings. See
[`EVIDENCE.md`](EVIDENCE.md) and [`reproductions.py`](reproductions.py).

## Findings

### P1-1 — Projection semantics are inferred with grep, so comments and unrelated `env` entries change runtime behavior

Location: [`modules/devenv.nix`](../../../modules/devenv.nix), lines 331-351.

The projection does two textual tests:

```text
grep -q 'DEVMAN_SELF_DIR' source
grep -q '^env:' source
```

The first searches comments, strings, child parameters, and executable text. It
does not ask whether the workflow is a cross-repository parent. The second asks
only whether any top-level `env:` exists. If it does, the projection omits the
required directory variable instead of merging it into the existing block.

Both failures are confirmed with the actual generated plan:

- an ordinary workflow with `env: [REVIEW_FLAG: enabled]` receives no
  `DEVMAN_PROJECT_DIR`;
- an ordinary workflow with a comment that mentions `DEVMAN_SELF_DIR` receives
  `DEVMAN_SELF_DIR` instead of `DEVMAN_PROJECT_DIR`.

The second case already affects a shipped workflow.
[`plane-report.yaml`](../../../.devman/workflows/plane-report.yaml), lines 19-27,
explains that `DEVMAN_PROJECT_DIR` is correct and mentions `DEVMAN_SELF_DIR` only
while explaining why. That comment makes its generated projection state the
opposite variable.

Impact:

- scheduled runs have no trigger process to repair the environment;
- steps can see an unset variable even though the projection claims to state it;
- the inherited exit handler can lose the directory it needs for run metadata;
- harmless documentation edits can alter execution semantics;
- `devman doctor` reports the resulting projection as healthy if Dagu can load
  it and no literal directory has appeared yet.

Fix direction:

1. Determine the directory variable from the parsed workflow semantics already
   implemented in `Workflow.triggers_other_dags()` and `Workflow.params()`.
2. Generate one complete YAML document. Merge the required variable into the
   existing `env` value, while preserving Dagu's supported map/list spellings.
3. Refuse a source that explicitly assigns the reserved variable to another
   value. Do not silently trust it.
4. Add projection tests for comments, existing map-form `env`, existing list-form
   `env`, cross-repository parents, and ordinary scheduled workflows.

This is the clearest example of a design rule being correct while its producer
implements a weaker textual approximation.

### P1-2 — A caller can retarget a resolved workflow to any existing directory

Location: [`src/devman/run.py`](../../../src/devman/run.py), lines 130-160.

`resolve()` first sets the reserved directory parameter from the registered
project. It then applies every user override with `params.update(overrides)`.
The only later check is `Path(value).is_dir()`.

This command shape is therefore accepted:

```text
devman run check --project project-a \
  DEVMAN_PROJECT_DIR=/path/to/project-b
```

It resolves and verifies project A's DAG link, then tells Dagu to execute that
workflow in B. The focused reproduction confirms the substituted target.

This contradicts the public contract that `devman run` resolves the project,
exports that project's directory, and refuses wrong-tree execution. The defect
also defeats the careful DAG-link collision check: file identity remains A while
execution identity becomes B after the check.

Fix direction:

- reject overrides for `DEVMAN_PROJECT_DIR` and `DEVMAN_SELF_DIR` outright;
- construct reserved parameters after applying allowed user overrides, or keep
  reserved and user dictionaries separate;
- assert at the final boundary that the directory value equals the selected
  registered project's canonical path;
- add tests for both reserved names, symlink spellings, relative paths, and an
  existing but different directory.

The safe invariant is not “the value is a directory.” It is “the value is the
directory of the project whose workflow was resolved.”

### P1-3 — Scheduled workflows use the daemon's login shell, not the declared default shell

Locations: [`nix/nixos-module.nix`](../../../nix/nixos-module.nix), lines 80-101
and 421-430; [`src/devman/run.py`](../../../src/devman/run.py), lines 194-227.

The module correctly records that Dagu prefers `$SHELL` over `default_shell`.
`child_env()` correctly clears `$SHELL` for CLI, watcher, and hook-triggered
enqueues. The systemd Dagu service does not clear or set it.

The comments say this is safe because the daemon schedules no workflows. That
became false when scheduled maintenance and plane reporting were added. The live
user manager and Dagu process both hold zsh in `$SHELL`, so the daemon-owned
schedule path uses zsh and bypasses `default_shell = bash`.

Impact:

- one workflow has different shell semantics when invoked manually and when
  started by its schedule;
- a bash-compatible workflow can pass tests and manual runs, then fail at night;
- the source contains a stale proof that actively discourages the correct fix.

Fix direction:

- remove `SHELL` from the Dagu service environment, or set it to the same shell
  as `default_shell` if Dagu cannot distinguish absence after manager inheritance;
- add a VM assertion that the service process has no overriding `$SHELL`;
- schedule a fixture that uses a small bash-specific construct and prove it runs
  under the declared machine shell;
- update the comments in the same change.

The shell must be normalized at both enqueue owners: `devman run` and Dagu's
scheduler.

### P1-4 — Nested registered projects both fire for one file event

Locations: [`src/devman/registry.py`](../../../src/devman/registry.py), lines
198-216; [`src/devman/watch.py`](../../../src/devman/watch.py), lines 477-496.

`Registry.project_for()` explicitly defines the correct rule: the deepest
registered project wins. `watch.match()` does not use that rule. It loops over
every watch entry and accepts every project root that contains the path.

For `outer/inner/changed.py`, where both `outer` and `inner` are registered and
take the format trigger, the reproduction returns:

```text
['inner', 'outer']
```

Impact:

- one save enqueues two workflows;
- the outer workflow can scan or rewrite across the nested repository boundary;
- queue and run history show two legitimate-looking successes;
- ordering is incidental, so the two formatters can race.

Fix direction:

1. Resolve each changed path to its deepest registered project once.
2. Match only entries owned by that project.
3. Keep the existing per-project/per-workflow batch coalescing after ownership is
   resolved.
4. Add unit and VM cases for nested registered roots, including different trigger
   maps on parent and child.

The registry already has the ownership rule. The watcher should share it instead
of implementing containment independently.

### P1-5 — Project and workflow identities are not validated against Dagu or path rules

Locations: [`modules/devenv.nix`](../../../modules/devenv.nix), lines 317-329 and
438-447; [`src/devman/registry.py`](../../../src/devman/registry.py), lines
42-97.

The conformance suite proves that Dagu accepts only alphanumerics, dash, dot, and
underscore in a DAG name. The codec validates only one condition: a workflow
name may not contain dot. Project identity is an unrestricted Nix string.

The reproduction registers `bad@project` and `run.resolve()` returns
`bad@project.check`, although the pinned Dagu rule rejects `@`. More dangerous
characters are also possible at the producer boundary. Slash, empty, `..`, and
path separators interact with:

- `projects/$proj` directory creation;
- `dags/$proj.$workflow.yaml` link names;
- shell patterns and cleanup loops;
- the inverse codec.

This is both a correctness defect and a path-boundary defect. Even if shell
quoting prevents command execution, identity must not be allowed to select
registry subpaths.

Fix direction:

- define one explicit identity grammar from the pinned Dagu character set;
- validate both halves before any path is constructed;
- refuse empty names, `.`/`..`, separators, control characters, and every Dagu-
  invalid character;
- keep the additional “no dot in workflow” codec rule;
- duplicate the small grammar at the Nix producer and Python reader boundaries,
  with one shared conformance table that proves agreement;
- make `doctor` flag legacy entries whose project half is invalid.

### P1-6 — The service allows a non-loopback bind while authentication is forced off

Location: [`nix/nixos-module.nix`](../../../nix/nixos-module.nix), lines 41-53
and 318-322.

The safe default is `127.0.0.1`. However, `host` is a public unrestricted string,
while generated Dagu configuration always sets `auth.mode = none`. A user who
sets the documented bind option to `0.0.0.0`, `::`, or a LAN address exposes the
web UI, API, and coordinator without authentication.

This is a configuration trap. The comment “Loopback only” describes the default,
not an enforced invariant.

Fix direction:

- assert that `host` is loopback while authentication is disabled; or
- expose a deliberate authentication configuration and require it for every
  non-loopback address;
- add Nix evaluation tests for IPv4 loopback, IPv6 loopback, wildcard, and LAN
  values;
- state the security boundary in the option description.

### P2-1 — Runtime paths are serialized into YAML and JSON without encoding

Location: [`modules/devenv.nix`](../../../modules/devenv.nix), lines 339-353,
419-430, and 612-614.

The projection writes `$root` into YAML plain scalars with `printf`. The metadata
template puts `@PATH@` inside JSON quotes and then performs Bash string
substitution. Neither operation uses a YAML or JSON encoder.

A valid directory containing colon-space generated invalid YAML and was refused
by the pinned Dagu validator. A `#` can silently truncate a YAML plain scalar.
A quote or backslash can corrupt `metadata.json`. Newlines and control characters
create further ambiguity.

Impact ranges from shell entry failure to a silently wrong path or an invisible
registry entry. This also makes the project-path domain narrower than the public
contract states without any refusal that explains the restriction.

Fix direction:

- use an encoder, not quoting folklore;
- generate metadata with `jq --arg` or a small packaged Python renderer;
- generate the projection as structured YAML or use a correctly encoded JSON
  scalar, which YAML accepts;
- if the critical-path process budget forbids an encoder on every shell entry,
  encode only on the guarded slow path;
- test spaces, colon-space, `#`, quotes, backslashes, Unicode, and newlines.

### P2-2 — `devman run` accepts workflows that Dagu's schema rejects

Locations: [`src/devman/run.py`](../../../src/devman/run.py), lines 58-69;
[`src/devman/workflow.py`](../../../src/devman/workflow.py), lines 42-54.

The trigger's “fails to load” refusal checks only YAML syntax and top-level
mapping shape. It does not run Dagu validation. The repository already has a
pinned fixture proving that a top-level `name:` is syntactically valid YAML but
invalid Dagu. `run.resolve()` accepts that exact shape and returns a DAG for
enqueue.

This moves a deterministic refusal from the foreground command to Dagu's later
queue processing. It weakens the promise at `run.py` lines 60-68 that a file
which cannot load is refused before enqueue.

Fix direction:

- validate the resolved projected file with the pinned Dagu binary before
  enqueue, with a cache keyed by file identity and content metadata if spawn cost
  matters;
- alternatively, make the projection validate before atomically publishing a
  DAG link, so every runnable link is known valid;
- retain the bounded reader for devman-specific mechanical checks. Do not grow a
  second Dagu schema in Python.

### P2-3 — Registry corruption is either a process crash or silent disappearance

Location: [`src/devman/registry.py`](../../../src/devman/registry.py), lines
159-185.

`projects()` skips unreadable and invalid JSON, but assumes any valid JSON is an
object. A metadata file containing `[]` raises `AttributeError` at `raw.get` and
can crash `run`, `show`, `watch`, and `doctor` together.

The opposite path is also unsafe diagnostically: invalid JSON is skipped as if
the project did not exist. Its old DAG links and schedules can remain active
while every registry reader, including `doctor`, becomes blind to them. The
comment explains half-written data, but `metadata.json` is written last; a
corrupt final file is not made safer by silence.

Fix direction:

- distinguish absent, temporarily incomplete, invalid JSON, wrong top-level
  type, and invalid field types;
- make registry loading return both valid projects and named entry faults;
- let `doctor` report faults without crashing;
- make commands that need the corrupt project refuse with its metadata path;
- publish metadata atomically with write-to-temp plus rename, then remove the
  need to treat parse failure as a normal half-write state.

### P2-4 — The exact generated projection and daemon schedule path have no automated test

Locations: [`tests/README.md`](../../../tests/README.md), lines 61-68;
[`nix/tests/dagu-service.nix`](../../../nix/tests/dagu-service.nix), lines 82-123.

The test guide says the devenv projection is covered by `groups-validate` and a
shell entry. `groups-validate` validates source group YAML, not the generated
header. The VM test manually creates a projection in the expected shape and
manually supplies `DEVMAN_PROJECT_DIR` when enqueueing. It does not run the
devenv module's plan, inspect its generated YAML, or let Dagu's scheduler own the
enqueue.

This gap directly explains P1-1, P1-3, and P2-1. The consumer layers are tested
against an ideal producer output rather than the producer's actual bytes.

Fix direction:

- factor the projection renderer into a separately invokable artifact;
- run it in a derivation or VM for a fixture repository;
- validate and execute the emitted file without manually adding environment;
- include an actual scheduled run;
- assert generated metadata parses and the directory variable, working
  directory, logs, and exit metadata all resolve to the fixture project;
- update `tests/README.md` so it names the real proof.

### P2-5 — Several load-bearing comments now state false runtime facts

Locations include:

- [`nix/nixos-module.nix`](../../../nix/nixos-module.nix), lines 96-101 and
  425-429: the daemon allegedly schedules nothing;
- [`groups/base/workflows/maintain.yaml`](../../../groups/base/workflows/maintain.yaml),
  lines 79-84: scheduled dispatches allegedly enter and are bounded by the
  `light` queue, while the stage 7 measurement says schedules bypass admission;
- [`modules/devenv.nix`](../../../modules/devenv.nix), lines 23-25: local Git
  inputs allegedly cannot be pinned, contrary to the current charter guidance;
- [`bench-entry.yaml`](../../../.devman/workflows/bench-entry.yaml), lines 61-67:
  the step allegedly ignores `default_shell` because it inherits the daemon's
  shell, although manual `devman run` now clears it.

This repository explicitly treats measured comments as law. Stale comments are
therefore more serious here than ordinary documentation drift: future changes
are required to preserve or reason from claims that are no longer true.

Fix direction:

- audit every comment that contains “measured,” “only,” “never,” or a stage
  citation against the final stage state;
- attach a test name or current log entry to each active invariant;
- move historical states into stage logs when they no longer explain current
  behavior;
- correct the charter in the same commit if the measured runtime contradicts it.

### P2-6 — Overrides are not restricted to declared workflow parameters

Location: [`src/devman/run.py`](../../../src/devman/run.py), lines 105-169 and
230-238.

The CLI accepts any `NAME=VALUE` and adds it to the Dagu parameter list. The
focused reproduction confirms that `TYPO=value` survives resolution for a
workflow that declares no `TYPO`.

`USER.md` describes this surface as passing a declared parameter. Dagu can reject
undeclared parameters later, so a typo may be accepted and enqueued by devman,
then fail asynchronously. In a permissive Dagu path it can instead become an
unreviewed ambient value.

Fix direction:

- reject any override not present in `Workflow.params()`;
- reserve both directory names regardless of declaration;
- list declared names in the error;
- test a typo, duplicate override, empty name, and reserved-name override.

### P3-1 — `defaultQueue` can name a queue the module does not declare

Location: [`nix/nixos-module.nix`](../../../nix/nixos-module.nix), lines 339-363.

`defaultQueue` is any string. There is no assertion that it is a key in
`queues`. Dagu silently creates undeclared queues with different concurrency
semantics, and `doctor` finds the mismatch only after activation.

Add a Nix assertion that `builtins.hasAttr cfg.defaultQueue cfg.queues`. This is a
cheap configuration-time refusal for a machine-owned fact.

### P3-2 — `devman run --print` emits a command that is not safely replayable

Location: [`src/devman/run.py`](../../../src/devman/run.py), lines 247-252.

The command is printed with plain string joining. A project path or parameter
containing spaces, quotes, glob characters, semicolons, or dollar signs changes
meaning when pasted into a shell.

Use `shlex.join()` for the argv and `shlex.quote()` for the leading environment
assignment. Add a round-trip test with spaces and shell metacharacters.

### P3-3 — This repository's format trigger includes Python files that its task excludes

Locations: [`groups/format/triggers.toml`](../../../groups/format/triggers.toml),
[`groups/format/workflows/format.yaml`](../../../groups/format/workflows/format.yaml),
lines 50-56; [`pyproject.toml`](../../../pyproject.toml), lines 33-36.

The trigger and content hash include `.scratch/**/*.py`. Ruff explicitly
excludes `.scratch`. During this review, saving `reproductions.py` fired the live
format workflow. The hash changed, the task ran, and the triggering file was not
formatted.

This violates the group's stated widening rule in the repository that ships it:
the detector and hash agree, but the task has a narrower file domain.

Either exclude `.scratch` from this repository's trigger/hash through a local
workflow override, or make the format task include it. The former matches the
documented reason for Ruff's exclusion.

## Cross-cutting analysis

### The risky component is the producer, not the Python reader

The Python code is mostly small, typed by convention, and direct. The largest
semantic concentration is the shell program embedded in `modules/devenv.nix`.
It currently acts as all of these at once:

- YAML transformer;
- JSON renderer;
- identity validator and codec producer;
- registry transaction writer;
- incremental cache;
- symlink reconciler.

That concentration is not automatically wrong. The common-path latency budget
is real and well measured. But the current implementation saves subprocesses by
replacing structured serialization and semantic checks with grep and string
substitution. The cost appears later as correctness defects.

A better split is to keep the common guard in shell and move the guarded slow
path to one small, auditable renderer. Shell entry can still fork nothing when
the inputs match. When projection is necessary, correctness matters more than a
few slow-path milliseconds.

### Safety invariants need one final assertion at the execution boundary

The code often establishes an invariant and then mutates the relevant value:

- verify project/DAG identity, then apply directory overrides;
- declare `default_shell`, then leave a higher-precedence `$SHELL` in one enqueue
  owner;
- define deepest-project ownership, then rematch all containing projects in the
  watcher.

Each path needs a final assertion immediately before the irreversible boundary:
publishing a DAG link or enqueueing a run. Earlier validation is valuable, but it
does not protect against later mutation.

### `doctor` checks symptoms well but misses producer invariants

`doctor` is a strong diagnostic surface. It validates every projected file,
checks DAG-link identity, queue names, stale paths, watcher state, handlers,
fan-out, and run ageing. It still reported this plane healthy while:

- `plane-report` held the wrong generated directory variable;
- scheduled workflows inherited zsh;
- a nested event could double-dispatch;
- reserved parameter overrides could retarget a run.

These are not all reasonable runtime checks. The watcher and override cases
belong in code refusals. The projection-variable and service-shell cases are
machine-visible invariants and are good candidates for new doctor checks after
the producer is fixed.

## What is strong and should be preserved

1. **The charter names real failure modes.** It distinguishes a successful
   wrong-tree run from an ordinary process failure and records the measurement
   behind unusual decisions.
2. **The DAG-link identity check is excellent defense in depth.** It compares the
   file Dagu will read with the file devman resolved before enqueue.
3. **The Dagu conformance suite is valuable.** It pins semantic disagreements
   between YAML parsing, Dagu validation, and Dagu execution instead of inventing
   a Python schema.
4. **The workflow reader stays bounded.** Its helpers read only the fields needed
   for explicit safety and diagnostic rules.
5. **The watcher supervisor is thoughtfully designed.** It handles missing
   paths, state pickup, command origin, and child replacement with clear evidence.
6. **`child_env()` is correct on its covered path.** It clears both ambient
   directory variables and `$SHELL`, then states exactly one directory variable.
7. **Registry cleanup is conservative.** Normal diagnosis is read-only, and
   pruning is explicit and recoverable through re-entry.
8. **The suite is fast enough to run constantly.** A 236-test baseline in under
   four seconds is an asset. The answer is to add the missing boundary tests, not
   to replace the existing suite.

## Recommended remediation order

1. Close P1-2 immediately. Reserved directory overrides are a direct violation
   of the central safety invariant and need only a small, local refusal.
2. Replace projection grep/string semantics and add exact-output tests for P1-1
   and P2-1 together.
3. Normalize the daemon scheduler shell and add a scheduled VM fixture for P1-3.
4. Make watcher ownership use the deepest registered project for P1-4.
5. Define and enforce the identity grammar on both producer and consumer sides
   for P1-5.
6. Enforce loopback-or-authentication at Nix evaluation for P1-6.
7. Make registry publication atomic and registry parsing diagnostic for P2-3.
8. Move Dagu validation to publication or cached pre-enqueue validation for P2-2.
9. Correct the load-bearing comments and test guide only after the new behavior
   is proved.
10. Take the P3 items as small hardening changes beside the relevant files.

## Exit criteria for the repair project

The repair is complete when all of these are demonstrated by automated tests:

- a comment cannot change a generated environment;
- an existing `env` block retains its values and gains exactly one correct
  reserved directory value;
- every supported project path round-trips through projection YAML and metadata
  JSON;
- no CLI input can make a selected project's workflow run in another directory;
- manual and scheduled runs use the same declared shell;
- a path belongs to only its deepest registered project for watcher dispatch;
- every published DAG identity is accepted by pinned Dagu and is path-safe;
- a non-loopback service cannot evaluate with authentication disabled;
- corrupt registry entries are named by `doctor` and do not crash other checks;
- the VM test executes the actual generated projection, not a hand-built
  approximation.

Until those statements are executable, the repository's strongest safety
claims remain better specified than enforced.
