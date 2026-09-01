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
