# Stage log — project 009, the review refactor

One entry per stage of [`REVIEW_REFACTOR_GUIDE.md`](REVIEW_REFACTOR_GUIDE.md).
Each entry records what was measured, the exact command, the versions, the
result, and what the charter had to change. This is rule 1, paying itself
forward.

---

## S-1 — trigger refusals (stage 1, P1-2 + P2-6)

Date: 2026-08-31. Branch: `fix/009-stage-1-trigger-refusals`.

### What was wrong

`run.resolve()` derived the parameter map safely and then applied the caller's
overrides on top of it, with a blanket update at `run.py:149`. No parameter was
constrained. Two consequences, filed by the report as two findings:

- **P1-2** — `devman run check DEVMAN_PROJECT_DIR=/elsewhere` retargeted the run
  itself. The `is_dir()` check below it passed, because `/elsewhere` is a
  directory.
- **P2-6** — an ordinary parameter took any value. `stack-validate.yaml` declares
  `OBSERVANTIC_DIR: observantic` and hands it to a child as
  `DEVMAN_PROJECT_DIR` (lines 85-96), so `OBSERVANTIC_DIR=/anywhere` retargeted a
  cross-repository child run. Nothing in the projection blunts that: the parent's
  `working_dir` is `${DEVMAN_SELF_DIR}`, not a literal.

They are one defect, so one rule closes both.

### The rule

> A reserved name accepts no override. A parameter whose default names a
> registered project accepts only another registered project's name. Every other
> override must name a declared parameter.

### The measurement — blast radius before landing

Every override example this repository ships, and every one in the skills:

```bash
grep -rn "devman run" --include='*.yaml' --include='*.toml' --include='*.nix' \
  --include='*.md' --include='*.sh' --include='*.py' . | grep '='
```

Result: **no shipped example overrides a reserved name, and none names an
undeclared parameter.** The examples are `KEEP_DAYS=30`, `AGENT_REF=HEAD~3`,
`AGENT_PROMPT=…`, `RUNS=20`, `TARGET=pyjutsu` — all declared, none a reserved
name, none a path given to a project-name default. The refusals break no
documented call.

The only reserved-name use found is `DEVMAN_PROJECT_DIR=/tmp devman run
stack-validate` in `STAGE_3_LOG.md:165`. That is an environment assignment on the
command, not an override argument, and `child_env()` has cleared it since S13.

### The edit

- `src/devman/run.py` — the blanket update is gone. Each override is consumed
  inside the declared loop, so a later refactor has nothing to reintroduce.
  `test_the_blanket_update_is_gone` asserts that shape directly.
- `assert_target()` — the last line before the irreversible boundary, called in
  `main()` after `resolve()` and before both `command()` and the `--print`
  branch, so neither path can skip it. Its invariant is not "the value is a
  directory" but "the value is the directory of the project whose workflow was
  resolved". Earlier validation does not survive a later mutation, which is what
  P1-2 was.
- The `is_dir()` and empty-value checks stay, unchanged. They are the second
  layer, and they now fire only on a registry entry whose repository has gone —
  the state `doctor --prune` reconciles.
- `USER.md` — §3 gains "What `NAME=VALUE` may set", and the refusal table gains
  the three new messages.

### Verification

```
devenv tasks run -v base:unit     # 244 passed
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:test     # nix flake check
devman doctor                     # exit 0
```

Nine new cases in `tests/unit/test_run.py`, one per rule branch. Two existing
tests changed: the two that drove the second layer through a reserved override
can no longer reach it, so
`test_a_directory_variable_that_is_not_a_directory_is_refused` now drives it
through `make_dir=False` instead — a state that still occurs.

### Charter

No amendment. The rule is §7.2 and §11 enforced, not changed.

---

## S-2 — watcher ownership (stage 2, P1-4)

Date: 2026-08-31. Branch: `fix/009-stage-2-watcher-ownership`.

### What was wrong

Two places answered "which project owns this path", and they disagreed.

`registry.project_for()` carried the rule — the deepest registered project wins
— with the measurement behind it (`STAGE_5_LOG.md`, S3). `watch.match()`
implemented containment for itself, as `path.relative_to(entry.path)` over every
entry, and accepted **every** registered root containing the path.

Reproduced in the review: `outer/inner/changed.py`, with `outer` and
`outer/inner` both registered, returned `['inner', 'outer']`. One save, two
runs. The outer repository's formatter then rewrote source across the nested
repository boundary, and both runs reported success — the failure this design
exists to prevent.

### The edit — extract, do not copy

The report says the watcher "should share it instead of implementing containment
independently". Taken literally: copying the rule into `watch.py` would recreate
the same duplication in a new place.

`registry.deepest(roots, here)` is the rule, and it now has exactly two callers.
`project_for()` calls it and keeps its own nested-checkout refusal, which is a
separate rule and stays where it is. `match()` resolves ownership **once per
path**, then matches only that project's globs. The per-project/per-workflow
coalescing is unchanged; it now runs after ownership rather than instead of it.

One behaviour change inside the rule: depth is compared on `len(resolved.parts)`
rather than `len(str(root))`. Path length in characters is not depth. The old
form happened to agree on every path this machine holds.

### Verification

```
devenv tasks run -v base:unit     # 243 passed
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:test     # nix flake check, VM test included
devman doctor                     # exit 0
```

Six new unit cases plus one shape assertion.
`test_deepest_and_project_for_agree` asserts the two callers agree on a shared
table of paths — that is what keeps the extraction honest, since they drifted for
a whole stage before.

New VM subtest, "a save inside a nested checkout fires only the inner project":
registers a second project inside the first, saves one file in the inner one,
waits for the fire, then sleeps ten seconds and reads the whole `fired.jsonl`.
The assertion is that the set of projects that fired is exactly `{"nested"}` —
the outer one firing late would fail it.

### Charter

No amendment. §8's rule is unchanged; one of its two implementations was wrong.

---

## S-6 — the machine module's assertions (stage 6, P1-6 and P3-1)

Date: 2026-08-31. Branch: `fix/009-stage-6-nix-assertions`.

### What was wrong

`nix/nixos-module.nix` held no `assertions` attribute at all. Two options stated
an invariant their type did not enforce.

**P1-6.** `configFile` always writes `auth.mode = "none"`, and the comment above
it said "Loopback only". That described the default. `host` was
`types.str`, so `host = "0.0.0.0"` exposed the web UI, the API and the
coordinator to the network with no gate, and nothing said so.

**P3-1.** `defaultQueue` was any string while `queues` is the declared set. Dagu
accepts an undeclared queue name silently and gives it concurrency 1 — the
measurement is in the `queues` description itself, citing S-9 — so a typo here
serialises the whole machine and says nothing.

### The edit

`isLoopback` accepts `127.0.0.0/8`, `::1`, `[::1]` and `localhost`, and refuses
everything else including `0.0.0.0` and `::`. Both assertions are evaluation
time, which is the cheapest place to refuse: the developer learns before the
service exists.

The boundary is stated in the **option descriptions** as well as in the
assertion messages. A developer reads the description first.

A network bind is deliberately not built. It is a second option — a Dagu auth
mode and a token file on §9.4's secrets path — and its own charter
conversation. Rule 9 notes §9.4 has never fired.

### The test, and one thing it had to learn

`nix flake check` does not evaluate a NixOS configuration that nobody builds, so
an assertion with no test is unproved. The new `module-assertions` check
evaluates the module ten ways and reads `config.assertions`, which is lazy — it
builds no system. Six of the cases are the ones the guide names; four more cover
`127.0.0.0/8`, `[::1]`, `localhost` and the default.

It asserts the **message**, not only the failure. An assertion that fires for
the wrong reason is not a test.

**Measured while writing it:** a bare `lib.nixosSystem` fails NixOS's own
root-filesystem and boot-loader assertions, so `config.assertions` is never
empty and the first case failed for a reason that had nothing to do with the
option under test. The check therefore filters to messages holding
`services.devman-dagu`. Without that filter every case would pass, including the
ones that must fail — the exact shape of a check that checks nothing (rule 5).

### Verification

```
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:test     # nix flake check — module-assertions built
devman doctor                     # exit 0
```

### Charter

No amendment. §4 already says loopback; the module now enforces what §4 says.

---

## S-5 — the identity grammar (stage 5, P1-5)

Date: 2026-08-31. Branch: `fix/009-stage-5-identity-grammar`.

**Land this before stage 3.** Stage 3 validates identity before it constructs a
path, so the grammar has to exist first.

### What was wrong

The conformance suite proves Dagu 2.15.0 accepts only alphanumerics, dash, dot
and underscore in a DAG name (S-11). The codec validated one condition:
`dag_name_fault()` refuses a dot in the workflow half. `devman.project` was a
bare `types.str`.

So `bad@project` registered, `run.resolve()` returned `bad@project.check`, and
the pinned Dagu refuses it. Worse characters reached path construction:
`projects/$proj`, `dags/$proj.$workflow.yaml`, and the sweep loops in
`modules/devenv.nix`. A slash, an empty name, or `..` selects a registry
subpath.

### The measurement — who this breaks

Run before landing, against the installed plane:

```bash
ls ~/.local/share/devman/projects/          # 54 projects
ls ~/.local/share/devman/projects/*/workflows/*.yaml | xargs -n1 basename
```

**Zero of the 54 registered project names fail the grammar, and zero of the 10
distinct workflow names fail it.** No repository loses its shell to this stage.
`doctor` names an invalid legacy project anyway, because the measurement is of
this machine and the plane runs on others.

### The grammar

```
^[A-Za-z0-9][A-Za-z0-9._-]*$
```

The character set is Dagu's, measured. The leading character is restricted
further, so `-flag` and `.hidden` cannot be names. The empty string, `.`, `..`,
a path separator and a control character are already excluded by the pattern —
each is refused **with its own message anyway**, because "does not match a
regex" does not tell an author what to do.

### Two boundaries, one shared table

§3.1 says what the two interfaces share must be **text**, so a shared table is
charter-compatible where shared code is not.
`tests/fixtures/identity.json` holds 23 cases as `{name, valid, why}`, and
**three** readers assert against it:

| Reader | What it proves |
|---|---|
| `tests/unit/test_registry.py` | `identity_fault()` agrees with every case, and the Python grammar string **is** the table's |
| `tests/conformance/test_dagu_yaml.py` | the pinned `dagu ls` lists a DAG for every name marked valid — the grammar is a promise about Dagu, so Dagu proves it |
| `flake.nix` `identity-grammar` | the Nix-side pattern agrees with every case, read with `builtins.fromJSON` |

That is what makes duplicating a small grammar at both boundaries safe.

### The edits

- `registry.identity_fault(kind, value)`, beside `dag_name_fault()`.
  `dag_name_fault()` stays: the no-dot rule for the workflow half is
  **additional**, and it carries the injectivity argument.
- `run.resolve()` calls it for both halves, before `workflow_file()` — before
  any path is constructed.
- `modules/devenv.nix` refuses an invalid `devman.project` at evaluation time,
  beside the group-name throw. It is a `throw` rather than a
  `types.strMatching` for the same reason the group throw is one: the type
  error says the value does not match a pattern, and says nothing about what to
  write instead.
- `doctor`'s `check_dag_names` now flags a legacy entry whose **project** half
  is invalid, and names the `metadata.json` so the developer can find it. That
  is what gives an affected repository a rename path instead of a broken shell.

### What this stage does not do

`Registry.projects()` still skips rather than faults. Stage 4 owns that, and
the guide says so — a legacy entry with an invalid project half becomes a
registry fault there, not here.

The Nix-side `throw` is proved by the shared table's pattern, not by an
evaluation test of the module itself. The devenv module cannot be evaluated
inside `nix flake check` — it needs a second nixpkgs — which is the same
constraint `STAGE_1_LOG.md` S10 records. Stage 8 is where the real projection
gets a test.

### Verification

```
devenv tasks run -v base:unit     # 266 passed
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:test     # nix flake check — identity-grammar built,
                                  # conformance measured against dagu 2.15.0
devman doctor                     # exit 0, `dag names` still ok on 170 names
```

**One thing the suite taught:** the first run failed with
`FileNotFoundError: tests/fixtures/identity.json` inside the sandbox. The
`python-tests` check builds from a `fileset.toSource` over the flake source, so
an untracked file is not in the closure. `git add` is part of making a fixture
real here.

### Charter

No amendment. §9.1 already says identity is stated. This is the first time
anything checked what may be stated.

---

## S-7 — the daemon's scheduler shell (stage 7, P1-3)

Date: 2026-08-31. Branch: `fix/009-stage-7-daemon-shell`.

### The premise is confirmed, and the comment was false for a whole stage

Two workflows carry a `schedule:` — `groups/base/workflows/maintain.yaml:95`
and `.devman/workflows/plane-report.yaml:68`. So this claim, at
`nix/nixos-module.nix`, was false from the moment stage 7 shipped them:

> Setting `SHELL` on this unit was tried and does nothing for any run the plane
> makes: the daemon enqueues only under a `schedule:`, which §8 does not use.

Recorded here as a superseded state, per rule 1. It is corrected in both places
that carried it.

### Measured on the live machine, before the fix

```
$ devenv shell -- bash -c 'PYTHONPATH=src python -m devman doctor'
!!  daemon shell    pid 1302: SHELL=/run/current-system/sw/bin/zsh
```

The running daemon holds the user manager's zsh. Every scheduled run on this
machine has taken zsh rather than the `default_shell` bash since stage 7 — S9's
failure, with nobody at the prompt to see it.

### The edit

**The report's first fix direction is not expressible.** It says "remove
`SHELL` from the Dagu service environment". The variable is *inherited* from the
systemd user manager, so `environment.SHELL = null` removes nothing — there is
nothing set on the unit for a null to remove. The form that works is:

```nix
serviceConfig.UnsetEnvironment = "SHELL";
```

Two enqueue owners, two clearings: `devman run` for the CLI, the watcher and the
hook (`run.py`); the unit for the daemon's own scheduled enqueues.
`default_shell` governs both.

**Clearing per owner is a whack-a-mole invariant**, which is why the durable
form is a check. `doctor`'s new `daemon shell` reads the running Dagu's
`/proc/<pid>/environ` and reports `SHELL` if it is there. It reads what is
actually true rather than counting the places that ought to have cleared it.

### The VM proof, and two things it measured

`nix/tests/dagu-service.nix` gains two subtests:

1. the service process holds no `SHELL` — read from `/proc/<pid>/environ`
2. a fixture workflow with `schedule: "* * * * *"` and one bash-specific
   construct, `test -n "$EPOCHREALTIME"` — the exact construct that failed in S9
   — runs, and both the step and the DAG succeed

**Measurement 1 — a scheduled run needs the projection's `env:` block, not only
its `working_dir`.** The first fixture stated `working_dir` and `log_dir` and
failed: every step succeeded and the DAG reported `failed`, because base.yaml's
exit handler appends to `$DEVMAN_PROJECT_DIR/.devman/.runs/metadata.jsonl` as a
**shell** variable, and the daemon's environment holds no such name. It wrote to
`/.devman/.runs/metadata.jsonl` and exited 1. `STAGE_6_LOG.md` S2 says the
projection states "its own `working_dir`, `log_dir` and directory variable" —
this is what the third one is for, and the fixture now carries it.

**Measurement 2 — a per-minute schedule is not a neutral fixture.** Left in
place it enqueues into `light` while the rest of the script runs, and `doctor`
reads one queued item with nothing running as a wedged queue, correctly.
Removing the DAG file does not empty the queue: an item already dispatched
outlives its DAG, and `dagu dequeue light` did not clear it either. The
subtests therefore run **last**. Ordering is the only clean answer, and the
comment in the file says so.

### Verification

```
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:unit     # 236 passed
devenv tasks run -v base:test     # nix flake check — both new subtests green
devman doctor                     # exit 0 (the installed CLI; the new check
                                  # ships with the next machine rebuild)
```

The `daemon shell` check will report `!!` on this machine until the rebuild
lands the unit change and restarts the service. That is the check working.

### Charter

No amendment. §8's rule is unchanged. A comment that described the plane's
behaviour stopped being true when stage 7 added two schedules, and the fix is to
the comment and to the unit, not to the design.

---

## S-3 — the producer refactor (stage 3, P1-1, P2-1, P2-2, and P2-4 made closable)

Date: 2026-08-31. Branch: `fix/009-stage-3-producer-refactor`.

### What was wrong — one duplication, four findings

`modules/devenv.nix` decided the directory variable with
`grep -q 'DEVMAN_SELF_DIR'`, decided the `env:` header with `grep -q '^env:'`,
built the entry with `@PATH@` substitution, and validated no identity at all.
`src/devman/` already answered every one of those correctly, from a parsed
document. P1-1, P1-5, P2-1 and P2-2 are four symptoms of that one duplication.

The projection is now `src/devman/project.py`. `modules/devenv.nix` states the
plan and runs it.

### The measurements

**§3.9, the blast radius of the `env:` refusal.** Zero shipped workflows hold a
top-level `env:` — `groups/` and `.devman/workflows/` both. The 170 that match
`^env:` under `~/.local/share/devman/projects/` are the generated header itself,
which is what the count in the guide would have caught. Nothing on this machine
breaks.

**§3.5, the cost of validating before publishing.** Measured against this
repository's ten workflows, on the real plan:

```
full projection, every file validated       901 ms
the same, validation stubbed out (--dagu true)   246 ms
```

So `dagu validate` costs about **71 ms per workflow**. The guide's remedy is
taken: a file whose rendered bytes are identical to the ones already published
is republished without a second validation, because it passed when it was
written.

```
first projection (everything validated)     901 ms
re-projection, nothing changed              175-212 ms
```

**The one thing that invalidates that argument is a new validator**, so the
recorded `plan` decides. It holds the renderer's store path, and the renderer
wraps the Dagu that validates — a new Dagu, a new renderer, or any other derived
change gives a new plan path and every file is validated again. Three unit cases
pin the skip, including `test_a_new_plan_revalidates_everything`; without them
the skip is one edit away from "never validate", which rule 5 forbids.

**Shell entry, end to end.** The guarded path is unchanged at about 1.7 s, which
is devenv's own cost; the hook adds no fork. The projection path is 2.5 s.

### Three things measured while building it, each of which looked like something else

**1. A source path holding a newline made the renderer emit a file it would
refuse.** The banner comment carries the source path, so its second line landed
at column 0 and the generated document stopped loading. Found by
`test_every_supported_path_round_trips_through_the_yaml[newline]`. Every line of
the path is commented now.

**2. "Publish nothing" has to mean the whole projection.** The first version
swept the registry and then rendered. Adding an `env:` block to ONE override
refused correctly — and left this repository with **none** of its ten workflows
published, because the sweep had already removed them. A typo would have stopped
the nightly `maintain` until somebody noticed. Nothing is touched now until
every file has rendered and every changed file has validated; a refusal leaves
the previous projection exactly as it was. Proved live, and pinned by
`test_a_refusal_leaves_the_previous_projection_intact`.

**3. THE RENDERER'S SOURCE IS INVISIBLE TO DEVENV'S EVALUATION CACHE, and this
is `groupFiles`'s measurement one layer down.** `nix/renderer.nix` builds a
`fileset.toSource` over `../src`. Interpolating a path copies it to the store,
and devenv does not notice when the CONTENT of a copied path changes — so an
edited `project.py` kept producing the previous renderer's store path.

It presented as a bug in the new code: the projection refused correctly and then
published one workflow anyway, because the renderer actually running was a build
from before that behaviour was fixed. `planFile` recorded that stale path, so
the guard was satisfied. Everything agreed with everything, and all of it was
old.

The fix is the one `groupFiles` already uses: `builtins.readFile` is a read the
cache tracks, so the module hashes every `src/devman/*.py` into an attribute of
the derivation. A repository pinning a `git+https` rev never meets this — a
changed source is a changed rev. devman adopting itself (criterion 16) meets it
on every edit.

**4. `dagu validate` names the DAG after the file's base name.** Validating in a
temp file called `.validate` refused every workflow with "DAG name is required".
The staging file keeps the workflow's own base name, inside a dot-directory the
sweep's glob does not see.

### The guard — schema 4

`plan` used to record the projection script's store path. That path changed when
a group file changed but **not** when `triggers.toml` changed, so `plan`
equality did not imply the projection was current, and the guard had to compare
the whole rendered entry — which forced the entry to be rendered twice, once in
bash with `@PATH@` substitution and once in Python. That is P2-1's actual cause.

`planFile` is now one `writeText` holding the groups, the resolved workflows,
the triggers and the renderer's store path, so its path is a hash of all of it.
The guard compares three sliced fields instead of the whole entry:

```
disk "path"   == $DEVENV_ROOT     this repository has not moved
disk "plan"   == ${planFile}      nothing Nix derived has changed
disk "local"  == $devman_local    the override set has not changed
```

`devman_relink` and `devman_stale` are unchanged. `entryTemplate` and its
`@PATH@`/`@LOCAL@` substitution are gone.

**The entry's layout is a requirement, not a style.** `src/devman/project.py`
writes it in a fixed shape so the three anchors stay sliceable, and every value
goes through `json.dumps`. `test_the_entry_holds_the_three_anchors_the_guard_slices`
is what stops a later tidy-up from making the guard fire on every shell entry
forever.

**The forkless comparison's one limit is stated rather than silently broken.**
A repository path holding `"`, `\`, a tab or a newline is refused at
registration, by name, with the reason. Spaces, `: `, `#` and every non-ASCII
character keep working — those are P2-1's real cases. That is P2-1's actual
complaint answered: not the restriction, but the silence. It is in `USER.md`
§2.6 and in the refusal.

**Older CLIs still read a schema 4 entry.** Nothing but `registry.py` reads
`plan`, and it reads it as a string. The installed `devman` — built before this
stage — reports `Nothing to report.` against a machine that is now entirely
schema 4. That is the soft degradation the schema version exists to provide, and
`doctor` gains a `schema` check that names an entry from a devman it does not
know rather than misreading it.

### The charter amendment (rule 2)

**This amends §3.1**, and the amendment is in `CONCEPT.md` §3.1, in
`nix/renderer.nix`'s header, and in `nix/devman-cli.nix`'s header, in this
commit. The short form: sharing the renderer as a machine-side binary *creates*
the drift §3.1's second rule exists to prevent, in the one form the shell-entry
guard cannot see — an unversioned run-time dependency whose identity is not an
evaluation-time fact. Building it under each consumer's nixpkgs makes it
observable to the guard.

### Verification

```
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:unit     # 329 passed
devenv tasks run -v base:test     # nix flake check, VM test included
devman doctor                     # exit 0, 54 projects, 170 workflows
```

Live, on this machine, after one shell entry:

- `plane-report.yaml` states `DEVMAN_PROJECT_DIR` — **P1-1's live case, closed.**
  It shipped `DEVMAN_SELF_DIR` for a whole stage because a comment in it
  mentions the name.
- `stack-validate.yaml` states `DEVMAN_SELF_DIR`, decided from its `dag.run`
  steps rather than from any comment.
- the guarded path re-projects nothing; an edited override reaches the
  projection at the next entry (S-5a's regression, still closed).
- `modules/devenv.nix` holds no `grep` that decides semantics.

### What this stage does not do

The hook's path refusal has no shell-level test yet — §3.8's case 12, which the
guide assigns to stage 8. `check_schema` has no unit case yet; stage 4 rewrites
`projects()` and is the natural place for it.

---

## S-4 — registry faults (stage 4, P2-3)

Date: 2026-09-01. Branch: `fix/009-stage-4-registry-faults`.

### What was wrong, in two directions at once

`Registry.projects()` skipped an unreadable or invalid entry, then assumed any
valid JSON was an object.

**The crash.** `raw.get` on a list raises `AttributeError`. One entry
hand-edited into the wrong shape could take down `run`, `show`, `watch` and
`doctor` together.

**The silence, which is worse diagnostically.** Invalid JSON was passed over as
if the project did not exist — while its `dags/` links and its schedules stayed
**live**. So a scheduled workflow kept firing and every registry reader,
`doctor` included, was blind to the project it belonged to.

### The premise of the silence is gone, and stage 3 removed it

The comment justified skipping with a half-written entry: the projection writes
`metadata.json` last, so an interrupted run leaves an entry that does not match
(§9.3). That is still true, and since S-3 the write is an `os.replace` of a
fully-written temporary file, so **no reader ever sees a partial one**. There is
no longer a normal state that produces unreadable JSON. An unreadable entry is
therefore a fault, and faults are named. The comment says so where it used to
say the opposite.

### The shape

`Registry.load()` returns `(projects, faults)`. `projects()` keeps its exact
signature and returns `load()[0]`, deliberately: every reader wants the valid
projects, and only three want the faults. A wide refactor would have touched
every reader for no benefit.

Six distinct `why` values: absent metadata (**not** a fault — that is §9.3's
window), unreadable file, invalid JSON, valid JSON that is not an object, a
field of the wrong type, and a project name that fails stage 5's grammar.

`_field_fault` checks `project`, `path`, `plan`, `groups`, `local`, `workflows`
and `schema` once, rather than defending each use. It special-cases `bool`,
because `bool` is an `int` in Python and a schema of `true` is not a schema.

### Who reports what

| Caller | Behaviour |
|---|---|
| `doctor` | a new `registry` check names every fault with its metadata path, and never crashes |
| `run` / `show` | `project(name)` refuses **only** when the requested project is the corrupt one, and names its entry |
| `watch` | skips a faulted project and records the skip in `watch/state.json`, so `doctor` reports it under `watcher` too |

The `run`/`show` half fixes a message as much as a behaviour: a corrupt entry
and an absent one used to give the same "no project named 'x'", which sent the
developer to register a repository that was already registered while the entry
that was actually wrong went unmentioned.

The watcher half is reported twice on purpose. "My saves stopped firing" is the
symptom a developer notices; `registry` is where the cause is.

### Verification

```
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:unit     # 349 passed
devenv tasks run -v base:test     # nix flake check, VM test included
devman doctor                     # exit 0
```

Sixteen new cases. Ten of them are the shapes the guide names — `[]`,
`"a string"`, `42`, `null`, truncated JSON, an empty file, `path` as a list,
`groups` as a string, `schema` as a boolean, and a name that fails the grammar —
each asserting a **named fault and no exception**. `test_no_registry_shape_
crashes_a_reader` is the stage in one case: five broken entries beside one good
one, and `projects()` still answers.

The unreadable-file case chmods to 000 and skips as root, which reads it anyway.

Live: this machine's 54 entries all read, and all are schema 4.

### Charter

No amendment. §9.3 already says the registry is derived and reconstructable;
this makes the unreadable case say so out loud instead of pretending the
project does not exist.

---

## S-8 — the VM executes the real projection (stage 8, P2-4)

Date: 2026-09-01. Branch: `fix/009-stage-8-real-projection`.

### The gap, and why a green suite kept it

`tests/README.md` claimed the devenv module's projection was covered by
"`groups-validate`, and a shell entry". Every part of that was wrong in a
different way:

- `groups-validate` validates **source** group YAML and never sees the generated
  header.
- a shell entry proves the projection ran, not that it was right.
- the NixOS test built the projection **by hand**, in the module's shape, and
  supplied `DEVMAN_PROJECT_DIR` itself at enqueue.

So nothing tested the producer's bytes, and three findings survived a green
suite: P1-1, P1-3 and P2-1. Stage 3 made the renderer a program so it could be
tested; this stage tests it.

### What is now real

Six new subtests run `devman project apply` — the actual renderer, the actual
`dagu validate`, the actual publication — over the fixture the review left at
`.scratch/projects/009-code-review/fixture-project/`:

1. the fixture projects
2. **`comment-only.yaml` gets `DEVMAN_PROJECT_DIR`** although its comment names
   `DEVMAN_SELF_DIR` — P1-1, in a VM, against the real producer. The subtest
   also asserts the projection **ends with its source**, byte for byte, which is
   what the shell-entry guard's tail test depends on (S-5a).
3. the emitted file passes the pinned `dagu validate` and `dagu ls` finds it
4. **it runs with no `DEVMAN_` variable supplied at enqueue.** Every earlier
   subtest passed one by hand, which is exactly what stopped this being a test
   of the producer. `working_dir`, `log_dir` and the `metadata.jsonl` line all
   resolve to the fixture, and the step's own stdout is read back to prove the
   value reached the step's environment and not merely the file.
5. **`env-only.yaml` is refused**, naming the file and the variable — P1-1's
   severe case, which the shell projection used to accept silently.
6. the refusal **published nothing**, and the previous projection still stands.

**The scheduled proof moved onto the real projection too.** Stage 7's `tick`
fixture was hand-built here; it is now a third file in the fixture repository,
projected by the renderer, and the assertion that a scheduled run gets
`default_shell` is made against those bytes. Building it by hand at stage 7 is
what taught the measurement that is now free: a scheduled run needs the
projection's `env:` block, not only its `working_dir`, because base.yaml's exit
handler appends to `$DEVMAN_PROJECT_DIR/...` as a shell variable and the daemon
has no such name. The renderer emits all three, so one subtest now asserts the
producer and the shell together.

### §3.8's case 12 — the hook's own refusal, run rather than read

The path refusal is bash, inside a Nix string, inside a devenv hook. No Python
test reaches it. `checks.hook-path-refusal` cuts the block out of
`modules/devenv.nix` between two sentinels and **runs it** against a table of
paths, so what is tested is the bytes the hook uses rather than a copy of them.

**That forced a small change to the block, and the change is an improvement.**
The first draft matched `*$'\n'*`, which the Nix string layer rewrites — so the
extracted text was not what ran, and the test would have measured something else
while passing. `[[:cntrl:]]` needs no escape at either layer and covers every
control character rather than two. The block's source text is now also its
runnable text, and a comment says why that must stay true.

Eight of the thirteen cases are the **accepted** half, which matters more than
the refused half: P2-1's complaint was that the project-path domain was narrower
than the contract stated, so a space, `: `, `#`, a single quote, a brace, a
semicolon and a non-ASCII path all have to keep working.

**Proved to measure rather than to pass.** Deleting the `[[:cntrl:]]` arm from
the module fails the check:

```
FAIL: $'has\tnewline' gave '', wanted 'a control character'
```

### The false claim is corrected, and says it was false

`tests/README.md`'s table now names the real proof for each row, and carries a
note saying the projection row was false for three stages and which three
findings that cost. A row in that table is a claim about coverage.

### Verification

```
devenv tasks run -v base:check    # ruff
devenv tasks run -v base:unit     # 349 passed
devenv tasks run -v base:test     # nix flake check — hook-path-refusal built,
                                  # six new VM subtests green
devman doctor                     # exit 0
```

### Charter

No amendment. §9.2 is unchanged; this is the first time the VM ran what §9.2
describes rather than a copy of it.
