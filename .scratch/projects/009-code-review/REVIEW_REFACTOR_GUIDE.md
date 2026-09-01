# Review refactor guide — project 009

Date: 2026-08-31

This guide turns [`REPORT.md`](REPORT.md) into work you can do. Read
[`REPORT.md`](REPORT.md) first for the findings. Read this file for the order,
the exact edits, and the proof each stage needs.

The guide reorders the report. The report lists fifteen findings and ten
remediation steps. Four of its P1/P2 findings are one architectural defect, so
this guide has nine stages instead of ten steps, and stage 3 closes four
findings at once.

---

## 0. Before you start

### 0.1 The law you must obey

Read [`CLAUDE.md`](../../../CLAUDE.md) — the ten rules. Four of them govern
almost every line of this refactor:

| Rule | What it means here |
|---|---|
| 1 — read the stage log first | Every comment you are about to delete cites a measurement. Find it before you delete it. |
| 2 — the charter governs | Two stages in this guide contradict `CONCEPT.md`. Each must amend it **in the same commit**, with the measurement. |
| 5 — prefer a loud refusal | Never close a finding by widening what a check accepts. |
| 8 — keep scripts minimal | Python for logic, shell stays a thin wrapper. Stage 3 is this rule, applied. |

### 0.2 How to verify

Run all three before every commit:

```bash
devenv tasks run -v base:check     # ruff
devenv tasks run -v base:test      # nix flake check
devman doctor                      # the plane's own health
```

`devman doctor` must exit 0. `base:unit` is the fast inner loop (about one
second); `base:test` is what must pass before a stage lands.

### 0.3 How to work

- **One branch per stage. One pull request per stage.** Do not batch stages.
- `push branch:main` is refused in this repository. Open a pull request from the
  branch.
- Commit and push at regular intervals. You do not need to ask first.
- Every stage writes an entry in `STAGE_9_LOG.md` in this directory (create it
  at stage 1). The entry records: what you measured, the exact command, the
  versions, the result, and what the charter had to change. This is rule 1
  paying itself forward.

### 0.4 Two things you must not do

**Do not make the projection rewrite a workflow body.** §7.2 says devman never
parses a workflow to understand it, and the shell-entry guard
(`modules/devenv.nix:565-582`) works by comparing the *tail* of the generated
file against the source body, byte for byte. A projection that edits the body
breaks both. This is why stage 3 **refuses** an unmergeable `env:` block instead
of merging it — see §3.4, which corrects the report.

**Do not add a fork to the common shell-entry path.** `enterShell` runs twice per
`devenv shell`, on the critical path of every shell the developer opens. The
measurements are at `modules/devenv.nix:478-484` and `:540-552`. The guarded slow
path may fork. The guard may not.

---

## 1. The map

Stages 1, 2, 6 are small and independent. Do them first — they close three P1
findings in an afternoon and give you the repository's habits before you touch
the hard part.

```
stage 1  trigger refusals          P1-2, P2-6        src/devman/run.py
stage 2  watcher ownership         P1-4              src/devman/watch.py, registry.py
stage 6  Nix assertions            P1-6, P3-1        nix/nixos-module.nix
        ────────────────── independent, do in any order ──────────────────
stage 5  identity grammar          P1-5              registry.py + Nix + a shared table
stage 3  the producer refactor     P1-1, P2-1, P2-2, P2-4(part)
                                                     modules/devenv.nix, new src/devman/project.py
stage 4  registry faults           P2-3              src/devman/registry.py, doctor.py
stage 7  daemon shell              P1-3              nix/nixos-module.nix, doctor.py
stage 8  the real projection test  P2-4              tests/, nix/tests/, flake.nix
stage 9  comments, docs, P3s       P2-5, P3-2, P3-3  everywhere
```

**Stage 5 must land before stage 3.** Stage 3 validates identity before it
constructs a path, so the grammar has to exist.

**Stage 8 must land after stage 3.** The test stage 8 adds is a test of the
renderer stage 3 creates.

**Stage 9 is last, always.** Correcting a comment before the behaviour it
describes is settled writes a second false comment.

### Finding traceability

| Finding | Stage | Note |
|---|---|---|
| P1-1 projection grep semantics | 3 | |
| P1-2 reserved override retargets | 1 | merged with P2-6 |
| P1-3 daemon scheduler shell | 7 | |
| P1-4 nested double-dispatch | 2 | |
| P1-5 identity not validated | 5 | |
| P1-6 non-loopback without auth | 6 | |
| P2-1 unencoded path serialization | 3 | |
| P2-2 Dagu-invalid file accepted | 3 | closed at publication, not at enqueue |
| P2-3 registry corruption | 4 | |
| P2-4 no test of real projection | 3 + 8 | stage 3 makes it testable; stage 8 tests it |
| P2-5 false comments | 9 | |
| P2-6 undeclared overrides | 1 | merged with P1-2 |
| P3-1 undeclared defaultQueue | 6 | |
| P3-2 unquoted `--print` | 9 | |
| P3-3 format trigger vs task domain | 9 | needs a decision — see §9.3 |

---

## 2. Where the renderer lives — decided

Stage 3 moves projection logic from shell into Python. The Python code must then
be reachable from `modules/devenv.nix`, the **repo** interface. Today it is not.

`nix/devman-cli.nix:1-16` states the constraint: §3.1's second rule says what
the two interfaces share must be **text**, and `nix/dagu.nix` is the single
measured exception. A Python program is not text.

### The decision: build a renderer under the consuming repository's nixpkgs

Add `nix/renderer.nix` and `callPackage` it from `modules/devenv.nix`, exactly as
`installClient` does with `nix/dagu.nix` at `modules/devenv.nix:470`.

**The deciding argument is the guard, not the charter.**

The alternative was to call `devman` from `PATH`, relying on the fact recorded at
`nix/devman-cli.nix:14-16` — a devenv shell inherits the machine profile's PATH.
It fails for one reason. A `PATH` lookup is a run-time fact, so the devenv module
cannot know the renderer's identity at evaluation time, so it cannot put it into
`planFile`, so **the guard cannot observe it**. Upgrade the machine's `devman`,
and the rendering rules change while every other repository keeps a projection
produced by the old renderer: the entry still matches, nothing re-projects, and
Dagu keeps reading stale bytes. That is `STAGE_7_LOG.md` S-5a exactly — the
projection stopped being what the source implies, silently, a whole stage before
anything noticed.

It also invents a version-skew axis the plane does not have. The devenv module
comes from the repository's pinned rev; the CLI comes from the machine's. Today
they share only `metadata.json` — a text schema with a version number and soft
degradation. Moving rendering *semantics* across that boundary turns a
soft-degrading schema into a hard shell-entry dependency between two
independently-pinned components.

Under this decision the renderer is a store path known at evaluation time. It
goes into `planFile`, `plan` equality covers it (§3.3), and a renderer change
re-projects every repository at its next shell entry.

### The charter amendment, and why it does not weaken §3.1

**This amends §3.1.** Write the amendment this way, in `CONCEPT.md` §3.1 and in
`nix/devman-cli.nix`'s header comment, in the same commit (rule 2):

> §3.1's second rule exists to stop silent drift between the two interfaces.
> Sharing the renderer as a machine-side binary *creates* that drift, in the one
> form the shell-entry guard cannot see: an unversioned run-time dependency whose
> identity is not an evaluation-time fact. Building it under each consumer's
> nixpkgs makes the renderer's identity observable to the guard. The exception
> applies §3.1's own reasoning to a case its text did not anticipate.

### Cost control

All of it is precedented by `nix/dagu.nix` — "two store paths holding one
identical binary".

- `nix/renderer.nix` builds the **same source tree** as `nix/devman-cli.nix`,
  with a narrower entry point and no watchexec wrapper. One source, two
  derivations, no second implementation.
- It needs `dagu validate` for §3.5. Wrap it with `nix/dagu.nix` — the exception
  that already exists. No new dependency.
- The closure is python3 plus pyyaml, cached across every repository on the same
  nixpkgs. Measure the first-entry cost on a cold cache and record it in the
  stage log. `installClient` already pulls a Go binary of comparable size.

`devman project apply` still exists in the CLI, backed by the same module. That
is what `doctor` and the unit tests call.

---

## 3. Stage 3 — the producer refactor

Do stages 1, 2, 5 and 6 first. This is the largest stage. It closes P1-1, P2-1,
P2-2, and makes P2-4 closable.

### 3.1 Why this is one change and not four

`modules/devenv.nix` decides the directory variable, merges `env`, encodes paths,
and validates identity. `src/devman/` already does all four correctly:

| The producer needs | Python already has |
|---|---|
| is this a cross-repository parent? | `Workflow.triggers_other_dags()` (`workflow.py:144`) |
| does the file hold a reserved name for itself? | `Workflow.holds_project_dir()` (`workflow.py:197`) |
| does an `env:` block define a name? | `_env_holds()` (`workflow.py:275`) |
| is this workflow name legal? | `dag_name_fault()` (`registry.py:75`) |

The shell reimplements these as `grep -q 'DEVMAN_SELF_DIR'`
(`modules/devenv.nix:335`) and `grep -q '^env:'` (`:346`). P1-1, P1-5, P2-1 and
P2-2 are four symptoms of that one duplication. Delete the duplication and the
symptoms go with it.

### 3.2 Target shape

```
modules/devenv.nix
  enterShell           the guard. Forks nothing. Compares three sliced fields.
  planFile             ONE writeText JSON holding everything Nix derived.
  projectScript        a thin wrapper: exec devman project apply --plan ${planFile}

src/devman/project.py  NEW. The whole projection, in Python.
src/devman/cli.py      registers `project` as machinery, beside `watch`.
```

### 3.3 The guard trap — read this before you write any code

The guard at `modules/devenv.nix:680-683` fires when the entry it renders in bash
differs from `metadata.json` on disk. If Python starts writing `metadata.json`
with a proper JSON encoder, its bytes will not match bash's naive `@PATH@`
substitution, **and the guard will fire on every shell entry, forever.**

Do not try to make the two renderers agree byte for byte. Change what the guard
compares.

**New guard.** Slice three fields out of the entry on disk and compare them as
strings. The hook already slices one of them — see `modules/devenv.nix:618-624`
for the pattern, which forks nothing.

```
disk."path"   == "$DEVENV_ROOT"        the repository has not moved
disk."plan"   == "${planFile}"         nothing Nix derived has changed
disk."local"  == "$devman_local"       the override set has not changed
```

Then keep the two existing run-time checks unchanged: `devman_relink`
(`:607-610`) and `devman_stale` (`:562-582`).

**Put `project` and `schema` into `planFile` too.** Then `plan` equality covers
every derived field, and the two compared run-time facts are `path` and `local`.
The whole-entry compare loses nothing, and you can say so in a comment.

**The escaping trap inside the guard.** `plan` is a store path and `local` holds
workflow names that stage 5's grammar constrains to `[A-Za-z0-9._-]`. Neither can
ever need JSON escaping, so both compare cleanly. `path` is different: Python
encodes it, bash compares it against the raw `$DEVENV_ROOT`, and for a path
holding `"`, `\` or a newline the two differ **forever** — the projection then
runs on every shell entry, idempotent and silently expensive. The existing
`devman_recorded` slice at `:618-624` has the same exposure today.

Encode everything properly, then refuse the small set the forkless guard cannot
compare. This `case` test forks nothing:

```bash
case "$devman_root" in
  *'"'*|*'\'*|*$'\n'*)
    # refuse, naming the character and the reason
    ;;
esac
```

Spaces, `: `, `#`, and Unicode all keep working — those are P2-1's real cases and
the Python writer handles them. Only `"`, `\` and control characters in the
**repository path** are out.

This is the answer to P2-1's actual complaint, which is not the restriction but
the silence: *"the project-path domain [is] narrower than the public contract
states without any refusal that explains the restriction."* State it, in the
refusal and in `USER.md`. Rule 5.

**Why `plan` equality is sufficient, and why it is not sufficient today.**
Today `plan` records `projectScript`'s store path. That path changes when a group
file changes, but **not** when `triggers.toml` changes — `triggers` reaches the
entry through a different route. So today's whole-entry compare is doing work
that a `plan` compare alone would miss.

Fix that by construction: `planFile` is one `pkgs.writeText` holding `groups`,
`workflows`, `triggers`, and the group name-to-store-path map. Its store path is
a hash of all of it. Any change to any derived fact changes the path, so `plan`
equality really does imply every derived field is unchanged. State this argument
in a comment above `planFile`, because the next reader will want to delete the
compare as redundant.

**This is a registry schema bump — schema 4.** `plan` changes meaning. Do all of:

1. Bump `schema` to 4 in `planFile`.
2. Grep every reader of `Project.plan` (`src/devman/`) and update it.
3. Record the schema in the comment block at `modules/devenv.nix:398-418`, in the
   same style as the schema 2 and schema 3 entries.
4. Make `doctor` report a schema it does not know, rather than misreading it.

`entryTemplate` (`modules/devenv.nix:419-432`) and its `@PATH@`/`@LOCAL@`
substitution disappear entirely. That is the point: the placeholder hack is what
P2-1 is about.

### 3.4 The rendering rules — and where the report is wrong

`REPORT.md` P1-1 fix direction step 2 says: *"Merge the required variable into the
existing `env` value."*

**Do not do this.** Merging means the projection edits the workflow body. That
breaks §7.2, and it breaks the guard's tail-equality test at
`modules/devenv.nix:536-538`, which depends on the generated file ending with the
source body byte for byte.

**Refuse instead.** Rule 5 says prefer a loud refusal to a silent default, and
refusing is strictly better than today's silent omission. The author's fix is one
line in their own file.

Implement exactly these rules in `render()`:

| Source state | Emit | Why |
|---|---|---|
| `triggers_other_dags()` is true | `DEVMAN_SELF_DIR` | §11. A parent must not hold the name it passes to children. |
| otherwise | `DEVMAN_PROJECT_DIR` | §7.2. The ordinary case. |
| no top-level `env:` | the header `env:` block | today's behaviour, now decided from the parsed document |
| `env:` states the required name with this project's path | nothing | already correct; do not duplicate the key |
| `env:` states the required name with a **different** value | **refuse** | never silently trust a reserved name |
| `env:` states the **other** reserved name | **refuse** | §11's two names are not interchangeable |
| `env:` exists and states neither | **refuse**, and say which line to add | this is P1-1's severe case |
| top-level `working_dir:` present | leave it | "the header adds; it never overwrites" (`modules/devenv.nix:236-240`) |
| top-level `log_dir:` present | leave it | same |

Decide `working_dir` and `log_dir` presence from the parsed document, not from
`grep '^working_dir:'`.

**Encode every emitted scalar.** Use `yaml.safe_dump` for the header block, never
`printf`. This is P2-1's YAML half. A path holding `: `, `#`, a quote, a
backslash, a newline or a control character must round-trip.

Keep the renderer **total** even for the three characters the hook refuses in
§3.3. Defence in depth: the hook's refusal protects the guard's forkless
comparison, and the renderer's encoding protects the output. Neither substitutes
for the other, and the renderer is reachable from the tests without the hook.

**Emit the body last and unchanged.** Header, then `source_text` verbatim. The
guard depends on it.

### 3.5 Validate before you publish — P2-2's better fix

`REPORT.md` P2-2 offers two directions. Take the second: *"make the projection
validate before atomically publishing a DAG link, so every runnable link is known
valid."*

Order of operations per workflow, in `project.py`:

1. Validate the project and workflow identity (stage 5's grammar). **Before any
   path is constructed.**
2. Render the file to a temporary path inside the project's own registry entry.
3. Run `dagu validate <temp>` on it.
4. On failure: refuse, name the source file and quote Dagu's message. Publish
   nothing.
5. On success: `os.replace` the temp file into place, then write the `dags/`
   symlink.

This is strictly better than validating at enqueue: it moves the refusal to the
one person who can fix it (the author, at shell entry) instead of to whoever
triggers the workflow next.

**Measure the cost and record it.** One `dagu validate` fork per *changed*
workflow on the *guarded* path. Report the wall-clock delta for a repository
with five workflows, in the stage log. If it exceeds the shell-entry budget the
answer is to validate only files whose rendered bytes changed — not to skip
validation.

### 3.6 Metadata, written atomically

`json.dumps` to a temp file, then `os.replace`. Last, exactly as today
(`modules/devenv.nix:371-373`), so an interrupted projection leaves an entry that
does not match and is retried.

This closes P2-1's JSON half and removes P2-3's premise: `metadata.json` can no
longer be half-written, so `projects()` no longer has to treat a parse failure as
a normal state. Note this in stage 4.

### 3.7 The CLI surface

`src/devman/cli.py:1-15` says §10's command list is closed, and explains that
`watch` is machinery rather than a fourth command. `project` is machinery in the
same sense: the projection script runs it, never a person.

Add it in that frame, and **update the docstring at `cli.py:1-15` in the same
commit** to say so — otherwise the file states a closed list of four while
offering five.

```
devman project apply --plan <planFile> --root <path> --registry <path>
```

`--root` and `--registry` stay arguments rather than moving into `planFile`,
because both are run-time facts. Everything Nix knows is in `planFile`.

### 3.8 Tests for stage 3

Add `tests/unit/test_project.py`. Every case asserts on the rendered string.

Required cases:

1. an ordinary workflow gets `DEVMAN_PROJECT_DIR`
2. a comment mentioning `DEVMAN_SELF_DIR` does **not** change the emitted
   variable — this is P1-1's live case, and `plane-report.yaml:23` is the real
   file it broke
3. a `dag.run` parent gets `DEVMAN_SELF_DIR`
4. a source with map-form `env:` stating the correct name and value emits no
   duplicate key
5. a source with list-form `env:` stating the correct name and value emits no
   duplicate key
6. a source with `env:` and neither reserved name is **refused**, and the message
   names the file and the line to add
7. a source assigning a reserved name a different value is **refused**
8. a source with its own `working_dir` keeps it
9. the rendered file **ends with** the source body, byte for byte
10. paths holding a space, `: `, `#`, `"`, `\`, a newline, and a non-ASCII
    character each round-trip through `yaml.safe_load` to the original string
11. the same path set round-trips through the metadata JSON
12. the hook refuses a repository path holding `"`, `\` or a newline, and the
    message names the character (§3.3)

Case 9 is the one that protects the guard. Name it so.

Case 12 needs a shell-level test, not a Python one. Add it to the projection
subtest in `nix/tests/dagu-service.nix` at stage 8, or as a small `runCommand`
check that sources the hook fragment.

### 3.9 Before you land — measure the blast radius

Rule 5's other half: know what your refusal breaks. Run this against the
installed plane and put the number in the stage log:

```bash
grep -l '^env:' ~/.local/share/devman/projects/*/workflows/*.yaml | wc -l
```

I measured zero shipped workflows with a top-level `env:` (`groups/` and
`.devman/workflows/`). Local overrides in the other 53 repositories are not
measured. If the count is non-zero, list the files in the stage log and fix them
in the same pull request — a refusal that breaks shell entry for a repository
nobody warned is a flag day, which `modules/devenv.nix:74-77` explains this
project avoids on purpose.

### Done when

- `modules/devenv.nix` contains no `grep` that decides semantics
- `entryTemplate` is gone
- `base:test` passes, `devman doctor` exits 0
- `~/.local/share/devman/projects/devman/workflows/plane-report.yaml` states
  `DEVMAN_PROJECT_DIR` after one shell entry
- the eleven cases in §3.8 pass

---

## 4. Stage 1 — trigger refusals (P1-2 + P2-6)

**Do this first.** It is small, local, and closes the report's highest-priority
finding.

### 4.1 The report splits one defect in two, and the smaller half is worse

`REPORT.md` files the reserved-name override as P1-2 and undeclared overrides as
P2-6. They are one defect: `run.py:149` applies caller input to the parameter map
**after** the safety derivation, and no parameter is constrained.

Fixing only the reserved names leaves the worse path open. Look at
`.devman/workflows/stack-validate.yaml`:

```yaml
params:
  - DEVMAN_SELF_DIR: ""
  - OBSERVANTIC_DIR: observantic     # a registered project NAME (run.py:147)
  - SITEMAN_DIR: siteman

working_dir: ${DEVMAN_SELF_DIR}      # not pinned by the projection header
```

and at lines 85-96 it hands those values straight to children:

```yaml
    action: dag.run
    with:
      params:
        DEVMAN_PROJECT_DIR: ${OBSERVANTIC_DIR}
```

`OBSERVANTIC_DIR` is not a reserved name. `devman run stack-validate
OBSERVANTIC_DIR=/anywhere` retargets a child run, and unlike an ordinary
workflow there is no literal `working_dir` in the projection to blunt it.

One rule closes both halves.

### 4.2 The rule

> A reserved name accepts no override. A parameter whose default names a
> registered project accepts only another registered project's name. Every other
> override must name a declared parameter.

### 4.3 The edit

Rewrite `run.py:130-171`. **`params.update(overrides)` must not exist when you
are done** — consume each override inside the declared loop, so there is no
blanket update for a future refactor to reintroduce.

```python
RESERVED = (PROJECT_DIR, SELF_DIR)

    declared = wf.params()
    dir_var = SELF_DIR if SELF_DIR in declared else PROJECT_DIR
    known = reg.projects()

    # (a) reserved names are not the caller's to set.
    held = sorted(k for k in overrides if k in RESERVED)
    if held:
        raise RegistryError(...)      # name the project, and say why

    # (b) an override that names nothing is a typo, and Dagu finds it later,
    #     elsewhere, and unexplained (E5).
    unknown = sorted(k for k in overrides if k not in declared)
    if unknown:
        raise RegistryError(...)      # list `sorted(declared)` in the message

    params = {dir_var: str(project.path)}
    for name, default in declared.items():
        if name == dir_var:
            continue
        if default in known:
            # (c) a project-name default stays an identity (§9.1). An absolute
            #     path here is the wrong-tree run this design refuses.
            given = overrides.get(name, default)
            if given not in known:
                raise RegistryError(...)   # list registered names
            params[name] = str(known[given].path)
        else:
            params[name] = overrides.get(name, default)
```

Keep the existing `is_dir()` check (`:151-160`) and the empty-value check
(`:162-169`) exactly as they are. They are not replaced — they are the second
layer.

### 4.4 The final assertion

The report's cross-cutting section asks for an assertion immediately before the
irreversible boundary. Add it in `main()`, after `resolve()` and before both
`command()` and the `--print` branch, so neither path can skip it:

```python
def assert_target(project: Project, params: dict[str, str], dir_var: str) -> None:
    """The last line before enqueue. Earlier validation does not survive a
    later mutation, which is what P1-2 was."""
    if params.get(dir_var) != str(project.path):
        raise RegistryError(...)
```

The safe invariant is not "the value is a directory". It is "the value is the
directory of the project whose workflow was resolved".

### 4.5 Tests

Extend `tests/unit/test_run.py`:

1. `DEVMAN_PROJECT_DIR=<other registered project>` is refused
2. `DEVMAN_SELF_DIR=<anything>` is refused
3. a reserved override naming a symlink to the correct path is refused — the
   check is identity, not equivalence
4. a reserved override spelled as a relative path is refused
5. `TYPO=value` is refused, and the message lists the declared names
6. a project-name-defaulted parameter overridden with a registered project name
   resolves to that project's path
7. a project-name-defaulted parameter overridden with an absolute path is refused
8. a plain parameter with a non-project default is still overridable
9. `assert_target` fires when `params` is mutated after `resolve()` returns

Case 7 is the `stack-validate.yaml` path. Name it in the docstring.

### 4.6 One check before you land

`USER.md` documents the override surface. Read it. If it shows an example this
stage now refuses, correct it in the same pull request.

### Done when

`params.update(overrides)` no longer appears in `run.py`, the nine cases pass,
and `USER.md` matches the new refusals.

---

## 5. Stage 2 — watcher ownership (P1-4)

### 5.1 The defect

`registry.py:198-254` defines the rule: the deepest registered project wins, and
it carries the measurement (`STAGE_5_LOG.md`, S3). `watch.py:489-495` implements
containment independently and accepts **every** project root containing the path.

Reproduced: `outer/inner/changed.py` with both registered returns
`['inner', 'outer']`. One save, two runs, and the outer formatter can rewrite
across the nested repository boundary.

### 5.2 Do not copy the rule — extract it

The report says the watcher "should share it instead of implementing containment
independently." Take that literally. Copying the rule into `watch.py` creates the
same duplication in a new place.

Add one function to `registry.py`:

```python
def deepest(roots: dict[str, Path], here: Path) -> str | None:
    """The key whose root contains `here` most deeply, or None.

    ONE RULE, TWO CALLERS. `project_for()` answers it for a developer's cwd and
    `watch.match()` answers it for a changed file. They disagreed until 009
    (P1-4): the watcher accepted every containing root, so one save enqueued a
    run in a nested repository and in its parent, and both reported success.
    """
```

Then rewrite `project_for()` to call it, and `match()` to call it. `project_for()`
keeps its own nested-checkout refusal (`registry.py:223-253`) — that is a
separate rule and it stays where it is.

### 5.3 The new `match()`

```python
def match(reg, paths):
    entries = watch_map(reg)
    roots = {e.project: e.path for e in entries}
    by_project = {}                       # project -> its entries
    for e in entries:
        by_project.setdefault(e.project, []).append(e)

    hits = {}
    for raw in paths:
        path = Path(raw)
        owner = deepest(roots, path)      # resolve ownership ONCE, per path
        if owner is None:
            continue
        for entry in by_project[owner]:   # then match only that project's globs
            ...                           # existing glob + coalescing logic
    return list(hits.values())
```

Keep the per-project/per-workflow coalescing at `watch.py:495` exactly as it is —
it is correct, and it now runs after ownership is resolved rather than instead of
it.

### 5.4 Tests

Extend `tests/unit/test_watch.py`:

1. nested registered roots, both taking `format` → one hit, and it is the inner
   project
2. nested roots with **different** trigger maps → the inner project's map decides,
   and the outer's does not fire
3. a path in the outer project but not the inner still fires the outer
4. three levels of nesting resolve to the deepest
5. sibling projects are unaffected
6. `deepest()` and `project_for()` agree on a shared table of paths — assert the
   agreement directly, so the two callers cannot drift again

Case 6 is the one that keeps §5.2's extraction honest.

Add a VM case in `nix/tests/dagu-service.nix` for nested roots as well. The
existing watcher subtests are further down that file; follow their shape.

### Done when

`watch.py` contains no `relative_to`-based ownership test of its own, the six
cases pass, and the VM watcher subtest covers a nested root.

---

## 6. Stage 6 — Nix assertions (P1-6, P3-1)

`nix/nixos-module.nix` contains **no** `assertions` attribute at all. Add one.
This is the cheapest stage in the guide and it is independent of everything else.

### 6.1 P1-6 — loopback or authentication

`nix/nixos-module.nix:41-53` always writes `auth.mode = "none"`, while `host`
(`:318-322`) is an unrestricted string. `0.0.0.0` exposes the web UI, API and
coordinator to the network with no gate. The comment "Loopback only" describes the
default, not an invariant.

Assert the invariant:

```nix
assertions = [
  {
    assertion = isLoopback cfg.host;
    message = ''
      services.devman-dagu.host is "${cfg.host}", and the generated Dagu config
      sets auth.mode = none (CONCEPT.md §4, project 009 P1-6). A non-loopback
      bind would expose the web UI, the API and the coordinator with no
      authentication. Keep it on loopback.
    '';
  }
```

`isLoopback` must accept `127.0.0.0/8`, `::1`, `localhost`, and refuse `0.0.0.0`,
`::`, and any LAN address. Write it with `builtins.match`, and test it.

**State the security boundary in the option description**, not only in the
assertion. A developer reads the description first.

If a non-loopback bind is genuinely wanted later, that is a second option
(`auth.mode`, a token file, §9.4's secrets path) and its own charter
conversation. Do not build it now. Rule 9 notes §9.4 has never fired.

### 6.2 P3-1 — `defaultQueue` must name a declared queue

`defaultQueue` (`:359-363`) is any string. `queues` (`:339-357`) is the declared
set. Dagu accepts an undeclared name silently and gives it concurrency 1 — the
measurement is in the `queues` description itself, citing S-9.

```nix
  {
    assertion = builtins.hasAttr cfg.defaultQueue cfg.queues;
    message = ''
      services.devman-dagu.defaultQueue is "${cfg.defaultQueue}", which is not a
      key in services.devman-dagu.queues (${...}). Dagu would accept the name
      silently and give it concurrency 1 (§15.4, S-9).
    '';
  }
];
```

### 6.3 Tests

`nix flake check` does not evaluate a NixOS configuration that nobody builds, so
an assertion with no test is unproved. Add an evaluation check to `flake.nix`
`checks`, in the shape of `groups-validate`:

- IPv4 loopback → evaluates
- IPv6 loopback → evaluates
- `0.0.0.0` → fails, and the message mentions authentication
- a LAN address → fails
- `defaultQueue = "light"` with `light` declared → evaluates
- `defaultQueue = "typo"` → fails

Assert on the failure by catching it with `builtins.tryEval`, and assert the
message text — an assertion that fires for the wrong reason is not a test.

### Done when

Six evaluation cases pass and both option descriptions state the boundary.

---

## 7. Stage 5 — identity grammar (P1-5)

**Land this before stage 3.** Stage 3 validates identity before constructing a
path, so the grammar must exist first.

### 7.1 The defect

The conformance suite proves Dagu 2.15.0 accepts only alphanumerics, dash, dot and
underscore in a DAG name (`registry.py:51-61`, citing S-11). The codec validates
one condition: `dag_name_fault()` (`registry.py:75-97`) refuses a dot in the
workflow half. `devman.project` is a bare `types.str` (`modules/devenv.nix:438`).

So `bad@project` registers, and `run.resolve()` returns `bad@project.check`,
which the pinned Dagu refuses. Worse characters reach path construction:
`projects/$proj`, `dags/$proj.$workflow.yaml`, and the sweep loops at
`modules/devenv.nix:297-307`. A slash, an empty name, or `..` selects a registry
subpath.

### 7.2 The grammar

One definition, from the measured Dagu character set:

```
^[A-Za-z0-9][A-Za-z0-9._-]*$
```

Leading character restricted so `-flag` and `.hidden` cannot be names. Then
refuse, explicitly and by name: the empty string, `.`, `..`, any string holding a
path separator, and any control character. Those are already excluded by the
pattern — refuse them **with their own message anyway**, because "does not match
a regex" does not tell an author what to do.

### 7.3 Two boundaries, one shared table

The report asks for "one shared conformance table that proves agreement". §3.1
says what the two interfaces share must be **text**, so a shared table is
charter-compatible where shared code is not.

1. `tests/fixtures/identity.json` — a list of `{name, valid, why}` cases.
2. Python reads it in `tests/conformance/`, asserts `identity_fault()` agrees,
   and asserts the pinned `dagu validate` agrees for every case marked valid.
3. A new `flake.nix` check reads the same file with `builtins.fromJSON` and
   asserts the Nix-side pattern agrees.

That is what makes "duplicate the small grammar at both boundaries" safe.

### 7.4 The edits

**Python.** Add `identity_fault(kind: str, value: str) -> str | None` to
`registry.py`, beside `dag_name_fault()`. Keep `dag_name_fault()` — the no-dot
rule for the workflow half is additional and it carries the injectivity argument.
Call `identity_fault` from:

- `Registry.projects()`, so a legacy entry with an invalid project half becomes a
  fault rather than a working project (see stage 4)
- `run.resolve()`, before `reg.workflow_file()`
- `project.py`'s renderer, before any path is constructed (stage 3)

**Nix.** Assert `cfg.project` at evaluation time in `modules/devenv.nix`, beside
the existing group-name throw at `:92-95`. An evaluation-time refusal reaches the
author before a path exists, which is the cheapest possible place.

**doctor.** Extend `check_dag_names` (`doctor.py:511`) to flag a legacy entry
whose *project* half is invalid, not only the workflow half. Name the metadata
path in the finding so the developer can find it.

### 7.5 Before you land

Measure. Some of the 54 registered projects may already hold a name the new
grammar refuses:

```bash
ls ~/.local/share/devman/projects/
```

Any project that fails the grammar cannot enter its shell after this stage. List
them in the stage log. If the list is non-empty, `doctor` must name them
**before** the Nix assertion lands, so the affected repositories get a rename
path instead of a broken shell.

### Done when

The shared table passes on all three sides, `doctor` names an invalid legacy
project, and the measured list of affected projects is in the stage log.

---

## 8. Stage 4 — registry faults (P2-3)

Do this after stage 3, which removes the half-write premise.

### 8.1 The defect

`registry.py:159-185` skips unreadable and invalid JSON, then assumes any valid
JSON is an object. `raw.get` on a list raises `AttributeError` and can crash
`run`, `show`, `watch` and `doctor` together.

The silent path is worse diagnostically. Invalid JSON is skipped as if the project
did not exist, while its `dags/` links and schedules stay live — so a scheduled
workflow keeps firing and every registry reader, `doctor` included, is blind to
it.

The comment at `:170-172` justifies the silence with half-written data. Stage 3
makes `metadata.json` publication atomic, so that justification is gone. Say so
in the comment when you change it.

### 8.2 The shape

```python
@dataclass
class RegistryFault:
    """One entry the registry cannot read, named rather than skipped."""
    name: str
    path: Path
    why: str

class Registry:
    def load(self) -> tuple[dict[str, Project], list[RegistryFault]]:
        """Valid projects, and every entry that is not one."""

    def projects(self) -> dict[str, Project]:
        """The valid projects. Callers that must report a fault use load()."""
        return self.load()[0]
```

Distinguish, with a distinct `why` for each: absent metadata, unreadable file,
invalid JSON, valid JSON that is not an object, and an object whose fields have
the wrong type. Apply stage 5's `identity_fault` to the project name here too.

### 8.3 Who reports what

| Caller | Behaviour |
|---|---|
| `doctor` | a new check that names every fault, with its metadata path. Never crashes. |
| `run` / `show` | refuse **only** when the requested project is the corrupt one, and name its metadata path |
| `watch` | skip a faulted project, and record the skip in the watcher state so `doctor` can report it |

`projects()` keeps its signature so the other callers need no change. That is
deliberate: a wide refactor here would touch every reader for no benefit.

### 8.4 Tests

Extend `tests/unit/test_registry.py`: `[]`, `"a string"`, `42`, `null`, truncated
JSON, valid JSON with `path` as a list, an unreadable file (chmod 000, skip when
running as root), and an entry whose project name fails stage 5's grammar.

Each must produce a named fault and must not raise. Add one `test_doctor.py` case
proving a fault is reported and the other checks still run.

### Done when

No registry shape crashes any command, and `doctor` names every fault.

---

## 9. Stage 7, 8, 9

### 9.1 Stage 7 — the daemon scheduler shell (P1-3)

**The premise is confirmed.** Two workflows carry a `schedule:` —
`groups/base/workflows/maintain.yaml:95` and
`.devman/workflows/plane-report.yaml:68`. So the claim at
`nix/nixos-module.nix:100` ("the daemon enqueues only under a `schedule:`, which
§8 does not use") and at `:425-429` is false, and has been since stage 7 added
them.

**The report's first fix direction is not expressible.** It says "remove `SHELL`
from the Dagu service environment". The variable is *inherited* from the systemd
user manager, so setting `environment.SHELL = null` removes nothing. Use:

```nix
serviceConfig.UnsetEnvironment = "SHELL";
```

Then rewrite the comments at `:96-101` and `:425-429`. Say what is now true: the
trigger clears `SHELL` for the CLI, watcher and hook paths (`run.py:225`), the
unit unsets it for the daemon's own scheduled enqueues, and `default_shell`
governs both. Keep the S13 measurement citation — it is still the reason
`default_shell` exists. Move the "the daemon schedules nothing" claim into the
stage log as a superseded state, per rule 1.

**Clearing per enqueue owner is a whack-a-mole invariant.** Two owners today. Add
a `doctor` check that reads the running Dagu process's environment and reports
`SHELL` if present. That is the durable form, and the report's cross-cutting
section names it as a good candidate.

**Prove it end to end.** Add to `nix/tests/dagu-service.nix`:

1. assert the service process has no `SHELL` (read `/proc/<pid>/environ`)
2. install a fixture workflow with a `schedule:` and one bash-specific
   construct — `$EPOCHREALTIME` is the exact construct that failed in S9
3. wait for the scheduler to fire it, and assert it succeeded

The VM has no devenv, so the fixture must not call `devenv tasks run`. Follow the
`probe.yaml` pattern at `nix/tests/dagu-service.nix:93-101`.

### 9.2 Stage 8 — test the real projection (P2-4)

`tests/README.md:67` claims the devenv module's projection is covered by
`groups-validate` and a shell entry. `groups-validate` validates **source** group
YAML, not the generated header. The VM test builds the projection by hand
(`nix/tests/dagu-service.nix:82-101`) and supplies `DEVMAN_PROJECT_DIR` manually
at enqueue (`:112`). Nothing tests the producer's actual bytes. That gap is why
P1-1, P1-3 and P2-1 survived a green suite.

Stage 3 makes this closable, because the renderer becomes directly invokable.

1. **Unit** — `tests/unit/test_project.py`, the eleven cases in §3.8. This is the
   bulk of the coverage and it costs milliseconds.
2. **VM** — replace the hand-built projection with a real
   `devman project apply` over a fixture repository. Then:
   - `dagu validate` the emitted file
   - enqueue **without** manually supplying any `DEVMAN_*` variable
   - let a `schedule:` own one enqueue (this is also stage 7's case 3)
   - assert the directory variable, `working_dir`, `log_dir` and the
     `metadata.jsonl` line all resolve to the fixture project
3. Add a fixture repository under `.scratch/projects/009-code-review/fixture-project/`
   — two files already exist there from the review (`comment-only.yaml`,
   `env-only.yaml`). Use them. They are P1-1's two cases.
4. **Rewrite `tests/README.md:61-68`** so the table names the real proof. Leaving
   a false claim in the test guide is how this gap survived.

### 9.3 Stage 9 — comments, docs and the P3s

Do this last. Correcting a comment before its behaviour settles writes a second
false comment.

**P2-5 — the comment audit.** This repository treats a measured comment as law
(rule 1), so a stale one is worse than ordinary drift: future work is required to
reason from a claim that is no longer true.

Audit every comment containing `measured`, `only`, `never`, `always`, or a stage
citation. The report names four; there will be more.

| Location | The false claim |
|---|---|
| `nix/nixos-module.nix:96-101`, `:425-429` | the daemon schedules nothing — fixed in stage 7 |
| `groups/base/workflows/maintain.yaml:79-84` | scheduled dispatches are bounded by the `light` queue, while S-7 measured that a schedule bypasses admission |
| `modules/devenv.nix:23-25` | local Git inputs cannot be pinned, contrary to current charter guidance |
| `.devman/workflows/bench-entry.yaml:61-67` | the step inherits the daemon's shell, although `devman run` now clears it |

For each: correct it, cite a test name or a current log entry, and move the
superseded state into the stage log. Where the measured runtime contradicts
`CONCEPT.md` or `PROPOSAL.md`, amend that document in the same commit (rule 2).

**P3-2 — `--print` is not replayable.** `run.py:250-252` joins argv with a plain
space. Use `shlex.join()` for argv and `shlex.quote()` for the leading
environment assignment. Add a round-trip test with a space, a quote, a `;`, a
`$`, and a glob character. The test must prove the printed line re-parses to the
same argv, not merely that it looks quoted.

**P3-3 — the format trigger's domain.** `groups/format/triggers.toml` maps
`**/*.py`; `pyproject.toml:36` excludes `.scratch` from Ruff. Saving
`reproductions.py` fired the workflow three times during the review, and formatted
nothing.

**This needs a decision, not a patch.** The report's fix — a local workflow
override in this repository — is a workaround for a general defect: the group owns
the trigger glob while the repository owns the task's file domain, and nothing
reconciles them. Telling every taker to hand-patch an over-broad group glob
contradicts §7.4's "taking a group costs nothing".

Bring three options and a recommendation:

- **A** local override here, plus a rule in `groups/format/README.md` that a
  repository excluding paths from its formatter must exclude them from the
  trigger. Cheapest. Keeps the mismatch, documents it.
- **B** a `doctor` check that compares each trigger glob against the task's
  actual effect, and reports a workflow that ran without changing a file it was
  fired for. Catches the general case. §15.7 may forbid it — read that section
  before proposing it.
- **C** narrow the group glob and let repositories widen. Inverts the current
  default; a charter question.

Do not decide alone. Ship **A** to stop the noise, and file the question.

---

## 10. Definition of done

The refactor is complete when each of these is an automated test that fails if
the behaviour regresses. These are `REPORT.md`'s exit criteria with the owning
stage attached.

| Criterion | Stage | Test lives in |
|---|---|---|
| a comment cannot change a generated environment | 3 | `tests/unit/test_project.py` |
| an existing `env:` block is refused rather than silently stripped | 3 | `tests/unit/test_project.py` |
| every supported project path round-trips through YAML and JSON | 3 | `tests/unit/test_project.py` |
| an unsupported project path is refused by name, not silently mangled | 3 | `nix/tests/dagu-service.nix` |
| a renderer change re-projects every repository at next shell entry | 2 + 3 | `tests/unit/test_project.py` (planFile covers the renderer path) |
| no CLI input makes a project's workflow run in another directory | 1 | `tests/unit/test_run.py` |
| no CLI input retargets a cross-repository child | 1 | `tests/unit/test_run.py` |
| manual and scheduled runs use the same declared shell | 7 | `nix/tests/dagu-service.nix` |
| a path belongs only to its deepest registered project | 2 | `tests/unit/test_watch.py` |
| every published DAG identity is Dagu-valid and path-safe | 3 + 5 | `tests/conformance/`, `flake.nix` |
| a non-loopback service cannot evaluate with auth disabled | 6 | `flake.nix` |
| `defaultQueue` must name a declared queue | 6 | `flake.nix` |
| corrupt registry entries are named and crash nothing | 4 | `tests/unit/test_registry.py` |
| the VM executes the actual generated projection | 8 | `nix/tests/dagu-service.nix` |

Until those statements are executable, this repository's strongest safety claims
stay better specified than enforced.

---

## 11. Two habits that will save you

**Read the stage log before you delete a line that looks redundant.** Rule 1.
Every non-obvious line in this repository has a measurement behind it, in
`.scratch/projects/006-automation-plane/STAGE_*_LOG.md` and
`.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`. Several of them
describe a failure that looked exactly like the cleanup you are about to make.

**Never make a check pass by making it check nothing.** Rule 5. If a test starts
failing during this refactor, the test is usually right — `tests/README.md:56-59`
records one case where a docstring and a test disagreed and the *code* was wrong.
Measure against the pinned Dagu binary and fix whichever is wrong.
