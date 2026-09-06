# Kickoff — the focused Python test layer

**This session builds a test layer. Change production code only where a test
proves a bug, and say so in the commit when you do.** The output is
`tests/`, its wiring, and a stage-log entry. If you find yourself redesigning
`modules/devenv.nix` or the DAG identity codec, you have left the scope — those
are later sessions.

Read these first, in this order:

1. `CLAUDE.md` — the ten laws. Laws 1, 5, 8 and 10 govern this session directly.
2. `.scratch/projects/006-automation-plane/CONCEPT.md` — the charter. §7 (the
   contract), §8 (triggers and parameters), §9.2 (on disk), §11 (cross-repo),
   §15.7 (what `doctor` may not decide).
3. `.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`, entries **S-8,
   S-9 and S-10**. They are at the end of the file. Every table in them is a
   test case you do not have to re-measure.
4. `src/devman/workflow.py`, `registry.py`, `run.py` — in that order. The
   docstrings carry the measurements; do not paraphrase them into tests, assert
   them.

---

## 0. Where the plane is

Built, installed, running. 53 registered projects, 167 projected workflows, one
Dagu 2.15.0 user service. `devman doctor` runs **14 checks** and reports nothing.

| | |
|---|---|
| Dagu | 2.15.0, pinned tarball in `nix/dagu.nix` |
| devman | 0.3.0, installed from `nix-meta` → `file://…/devman?ref=main` |
| Python | 3.13, `languages.python` in `devenv.nix` with `venv` + `uv` |
| Lint | ruff, `E,F,I,N,W,UP,B,C4,SIM`, `E501` ignored, `.scratch/` excluded |
| Tests today | **none.** There is no `tests/` directory |

`pyproject.toml` already has `[tool.pytest.ini_options]` with `addopts = "-v"`
and two markers, `unit` and `integration`. Somebody intended this and stopped.

### Preconditions

PR #134 (`fix/typed-params`) may still be open. Check with `gh pr list`. Start
from `main` with it merged — the params reader it fixes is one of the things
this session pins.

---

## 1. Why this session exists

Everything verified in the session that produced S-8, S-9 and S-10 was checked
by hand and then thrown away: eight parameter forms, eight fan-out shapes, five
queue cases, six typed-parameter edges. Each was a real measurement against the
pinned binary. **None of it is repeatable today.**

The next three sessions — the DAG identity codec, trigger modules, and whatever
follows — all touch the same policy functions. They need a floor.

**The point is not coverage. The point is that a refactor cannot silently undo a
measured refusal.** Several mechanisms in `run.py` and `registry.py` look exactly
like cleanup a future refactor would delete: clearing `$SHELL`, clearing the
inherited directory names, the nested-checkout refusal. Each exists because a run
succeeded and did its work in the wrong place.

---

## 2. Two decisions to make first, and state them in the log

### 2.1 Where the tests run

`base:test` is `nix flake check` today (`devenv.nix`, line 119). Unit tests must
run somewhere. Pick one and record why:

- **A.** A new flake check running pytest hermetically, so `base:test` covers it.
- **B.** A devenv task (`base:unit`?) plus a flake check, so the fast loop stays
  fast and CI still sees it.

Option A has a working precedent in this repo: `flake.nix`'s `groups-validate`
is a `runCommand` that puts the pinned Dagu on `nativeBuildInputs` and runs it
against `${./groups}`. Copy that shape. Note that whichever you choose, the
tests must run **without** the installed plane — no `~/.local/share/devman`, no
running Dagu service.

### 2.2 Whether pytest is a devenv package or a venv dependency

`devenv.nix` `packages` lists `git`, `ruff`, `dagu` and two agent CLIs. Python is
`languages.python` with `venv.enable` and `uv.enable`. Adding pytest to the venv
and adding it to a Nix check are different problems; the flake check needs it
from nixpkgs.

---

## 3. The inventory

Six modules. Roughly 60–90 assertions total, most of them parametrized tables —
**not** 90 test functions.

| File | Scope | Protects |
|---|---|---|
| `tests/unit/test_workflow.py` | ~20–25 cases | the bounded Dagu reader |
| `tests/unit/test_registry.py` | ~12–15 | project resolution, worktree refusal, DAG link |
| `tests/unit/test_run.py` | ~12–15 | the enqueue refusal contract and child env |
| `tests/unit/test_watch.py` | ~10–15 | event parsing, matching, coalescing |
| `tests/unit/test_doctor.py` | ~5–8 | only bounded decisions not covered via their helpers |
| `tests/conformance/test_dagu_yaml.py` | ~12–20 fixtures | the devman/Dagu semantic boundary |

**Set no coverage target.** Test contracts, not implementation. A test that
breaks when a function is renamed but nothing behaves differently is a
liability here.

---

## 4. The measured tables — encode these verbatim

These are the session's real payload. Each row was measured against Dagu 2.15.0.
Do not re-derive them; assert them. Cite S-8, S-9 or S-10 in the test's docstring
so the next reader can find the evidence.

### 4.1 `params()` — five spellings (S-10)

| Input | Expected |
|---|---|
| `- A: x` / `- B: y` | `{A: x, B: y}` |
| `{A: x, B: y}` | `{A: x, B: y}` |
| `"A=x B=y"` | `{A: x, B: y}` |
| `[A=x, B=y]` | `{A: x, B: y}` |
| `- name: A` + `type` + `default: x` | `{A: x}` |
| `- name: A` + `type`, no default | `{A: ""}` |
| `- name: A` + `enum` + `default: y` | `{A: y}` |
| `- Z: q` then `- name: A, default: x` | `{Z: q, A: x}` |

Plus: a typed `- name: DEVMAN_PROJECT_DIR` makes `holds_project_dir()` return
`["params"]`. That is the regression the fix closed — pin it.

### 4.2 `unbounded_fanout()` — eight shapes (S-8)

| File | Expected |
|---|---|
| two `dag.run`, no `type:` | reports "2 dag.run steps, and neither type: chain nor max_active_steps" |
| two `dag.run`, `type: chain` | bounded, no finding |
| two `dag.run`, `max_active_steps: 4` | bounded — **a stated bound is never a finding, whatever its value** |
| `parallel:` with items, no `max_concurrent` | reports "step 'f' fans out with no parallel.max_concurrent" |
| `parallel:` with `max_concurrent: 2` | bounded |
| `parallel: [a, b, c]` list shorthand | reports — a list carries no limit |
| one `dag.run` | bounded |
| mapping-form `steps:` | bounded — devman reads no steps from it, by design |

The last row is deliberate and needs a docstring: Dagu's loader **runs** a
mapping-form `steps:` while `dagu validate` **refuses** it, so devman follows the
validator and leaves the file a `doctor` check 1 finding rather than becoming
more permissive than Dagu.

### 4.3 `queues()` and the queue facts (S-9)

An undeclared queue name is **not** unlimited — it becomes a real queue at
concurrency 1, shared by every DAG naming it. `queues()` itself only reports
names; the behavioural facts belong in the conformance layer or nowhere. Do not
mock a scheduler to assert them.

### 4.4 `run.resolve()` — the decision matrix

From the review's §5.5, and each maps to a refusal already in `run.py`:

- ordinary project workflow
- cross-repo parent (`dag.run` present)
- parent improperly holding `DEVMAN_PROJECT_DIR` → refusal, and **assert which
  branch fires**: S-10 showed the wrong branch can fire for the right file
- cross-repo parent declaring no `DEVMAN_SELF_DIR` → refusal
- a parameter default naming a registered project → filled with that project's
  **path**, not the name
- empty parameter value → refusal
- project directory that is not a directory → refusal
- projection identity mismatch → refusal

For `child_env()`: inherited `DEVMAN_PROJECT_DIR`, `DEVMAN_SELF_DIR` and
`$SHELL` are each removed, and the correct directory variable is restored.

**Pin `$SHELL` hardest.** It looks exactly like the cleanup a future refactor
would delete, and it is stage-4-measured.

### 4.5 `registry.py`

`tmp_path` throughout. `.git` is a **directory** in an ordinary clone and a
**file** in a linked worktree, so `_checkout_between()` tests existence, not
kind. A real `git` subprocess is unnecessary — write the marker.

Cases: exact project root; a child directory; deepest registered project wins;
nested ordinary clone; linked worktree; submodule; explicit lookup; missing
entry; correct DAG link; missing link; foreign link.

**The foreign-link case is the measured one**: `devman-b` + `check` and `devman`
+ `b-check` render the same flat name. Build both and assert `dag_link_fault()`
names the intruder. That test becomes the identity codec's regression test in
the session after this one, so write it to survive the encoding change — assert
through `dag_name()`, never against a hardcoded `"devman-b-check"`.

---

## 5. The conformance layer

Separate from unit tests, and the reason it exists is drift: **a Dagu pin bump
must run these before it is accepted.**

Build `tests/fixtures/dagu/` and, for each fixture, state both halves:

```
Dagu accepts / refuses it        <- dagu validate, against the pinned binary
devman extracts X                <- Workflow.read() and the bounded helpers
```

Fixtures at minimum: `params-legacy-list`, `params-legacy-map`, `params-string`,
`params-typed`, `params-typed-nodefault`, `params-typed-enum`, `steps-list`,
`steps-map`, `env-map`, `env-list`, `queues`, `handler`, `fanout-chain`,
`fanout-unbounded`, `parallel-bounded`, `parallel-unbounded`.

Known expected results, measured:

| Fixture | `dagu validate` |
|---|---|
| mapping-form `steps:` | **refused** — "entrypoint document steps must be a non-empty sequence" |
| top-level `name:` | **refused** — "entrypoint document must not define name" |
| `- name: FOO` alone | **refused** — "must define at least one field in addition to name" |
| typed param with object/array `default` | **refused** |
| `param_schema` / `param_defs` / `params_json` / `default_params` as top-level keys | **refused** — "'spec.dag' has invalid keys" |
| `steps[].command` | accepted, **deprecation warning** — "use run" |
| `action: dag.enqueue` | accepted |
| a DAG name containing `@` | **refused** — names allow alphanumerics, dashes, dots, underscores |
| a DAG filename containing `.` or `_` | accepted, and resolvable by `dagu ls`, `dry`, `enqueue` |

The last two matter to the identity-codec session. Write them now.

### Running Dagu in a check, safely

`dagu` writes to its home and **seeds five example DAGs** on first use unless
`skip_examples: true`. Always:

```bash
export HOME=$TMPDIR
export DAGU_HOME=$TMPDIR/dagu
```

`groups-validate` in `flake.nix` already does this — follow it. `dagu validate`
is side-effect-free enough for a check. **`dagu dry` is not** — it creates
`log_dir`, which is why the bounded reader exists at all (S1). If a fixture needs
`dry`, confine it to a disposable temporary home and say so in a comment.

---

## 6. Do not build

- a coverage target of any kind
- tests of trivial dataclass properties
- CLI help or output snapshots
- a mocked Dagu HTTP API, a mocked systemd, a mocked queue
- a second implementation of Dagu's schema
- heavyweight git repositories where a `.git` marker proves the same contract
- anything that touches `~/.local/share/devman` or the running service

---

## 7. Verify and land

```bash
devenv tasks run -v base:check     # ruff — tests/ IS linted, .scratch/ is not
devenv tasks run -v base:test      # nix flake check
devman doctor                      # must exit 0
```

Then: a stage-log entry, a branch, a PR. This repository lands on `main`
**through a PR** — pushing `main` directly is refused.

**The stage-log entry.** S-8, S-9 and S-10 live at the end of
`.scratch/projects/007-standard-workflows/STAGE_7_LOG.md`. Continue there as
S-11 unless you judge a test layer deserves its own log, and if you start one,
say why in its header. Follow the existing shape: the answer, the versions, the
setup, the evidence, the verdict, charter impact, and the rule-7 table of what
the entry did to the machine.

**Law 2.** If anything here contradicts `CONCEPT.md` or `PROPOSAL.md`, change
that document in the same commit, with the measurement that forced it.

---

## 8. The one thing worth getting right

S-9's lesson was that a wrong sentence in the charter gets copied faithfully into
every layer that documents it — eight places, in that case. A test suite is the
only thing in this repository that would have caught it at the source.

So when a test and a docstring disagree, **measure against the pinned binary and
fix whichever is wrong.** Do not make the test match the code.
