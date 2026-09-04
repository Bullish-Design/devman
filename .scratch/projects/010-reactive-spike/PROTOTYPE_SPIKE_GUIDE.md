# PROTOTYPE_SPIKE_GUIDE — the reconciler spike

A build guide for an agent. Follow it top to bottom. Every gate passes or fails
by exit code, not by judgement.

**Version 2.** Version 1 is kept at `PROTOTYPE_SPIKE_GUIDE.v1-frozen.md`. Its
central gate was tautological — see §9 for what changed and why.

---

## 0. Read this first

**You are the implementing agent.** This guide is written for you to execute
with nobody present. It gives you the questions, the prior art you must not
re-derive, the build order, the gates, and the verdict form.

**The spike is disposable.** It exists to decide what to build. Write it to be
read once and thrown away.

### Ground rules

1. **Build in `~/Documents/Projects/devman-spike`.** Create it. It is a new git
   repository and the only tree you write to.
2. **Never write to `~/Documents/Projects/devman` or
   `~/Documents/Projects/templateer_v2`.** Read them freely. After every stage
   run `git -C ~/Documents/Projects/templateer_v2 status --porcelain` and
   confirm it is empty. If it is not, you broke rule 2 — restore it and record
   what did it.
3. **Do not run `uv run --project ~/Documents/Projects/templateer_v2 ...`.** It
   re-syncs that project's venv. Measured: `Uninstalled 5 packages / Installed
   5 packages`. That is a write.
4. **Network in stage 1 only.** `uv sync` fetches packages. After stage 1, no
   network and no LLM call. Every render in this spike is from plain data.
5. **Stop at a failed gate.** Do not work around it. A failed gate is a result.
   Record it in `SPIKE_RESULT.md` and stop.
6. **Never make a gate pass by making it check less.** If a gate is wrong, write
   why in `SPIKE_RESULT.md` and stop.
7. **Commit after every passing gate**, with the gate name in the message.

### Sizing

Budget **700 lines** across `src/`, `tests/`, `scripts/` and `templates/`
combined — not `src/` alone. Today's devman is 3,923 lines of Python plus 4,435
lines of Nix. If the spike passes **1,200** combined lines, that is a result:
record what grew. It is the outcome this spike most needs to be able to catch.

---

## 1. The three questions

Version 1 asked whether reconcile-at-startup repairs a missed event. That is
true by construction — it restates the definition of a pure function — and the
gate for it passed before the daemon finished starting. Replaced.

The spike now answers three questions that can each come back "no".

### Q1 — Does the antecedent hold?

> **Can real generation work be declared as a pure function of a
> glob-enumerable input set — and when it cannot, does the tool refuse instead
> of producing a silently wrong artifact?**

Everything downstream assumes purity. A collector that reads a file no glob
covers makes a permanently stale artifact that no restart repairs. **Gates P1
and P2.** These decide whether the design is applicable at all.

### Q2 — Does the reconciler hold under adversarial conditions?

> **Is reconcile a genuine fixpoint when inputs move underneath it, when an
> artifact is edited by hand, and when the process is killed mid-write?**

**Gates A1, A2, A6, A7, A11, A16.** A11 (torn read) is the sharp one: it is a real
case where startup reconcile does *not* repair, because staleness is judged
against a hash the artifact was never built from.

### Q3 — Is a daemon worth building?

> **Does an event-driven daemon earn `watcher.py`, a pid file, signal handling
> and its gates — against a one-second poll loop, and against no daemon at
> all?**

**Gates A4, A5, A8, A10, A12, A13, A14, A15.** This is the decision-relevant
question. If
`dspike gen` in a save hook is within a couple of seconds, the daemon is
300 lines of nothing. A14 is the one that could force the answer sideways: a
design needing a periodic floor has already half-conceded to the poller.

### What is out of scope

Do not build these. They belong to the machine-wide design and do not apply to
a per-repository process:

- multi-repository ownership (devman's `deepest()` rule, 009 P1-4)
- a registry, a projection, or any Nix beyond `devenv.nix` and `devenv.yaml`
- a workflow engine, DAG, retries, run history, or Dagu
- an HTTP, SSE or WebSocket server
- an event-bus abstraction over more than one event source
- LLM generation

---

## 2. Prior art — verified facts, do not re-derive

Measured on this machine. Trust it. If something contradicts it at build time,
record the contradiction in `SPIKE_RESULT.md`.

### 2.1 templateer_v2 — the LLM-free render path

Two calls, both synchronous. Verified with `OPENAI_API_KEY` and
`ANTHROPIC_API_KEY` unset:

```python
from templateer import TemplateRegistry

registry = TemplateRegistry.from_paths([root / "templates"])   # list REQUIRED
artifact = registry.render_from_model("doc-index", data)       # data is a dict
errors, warnings = registry.validate_artifact("doc-index", artifact, model_data=data)
```

`TemplateRegistry` is one of four public names in `templateer.__init__`
(`FailureReason`, `GenerationRequest`, `GenerationResult`, `TemplateRegistry`).

Build the registry **once, from an absolute path**, in `cli.py`, and pass it
into `reconcile`. A relative path silently loads nothing (traps T6, T14).

Measured cost:

| Step | Time |
|---|---|
| `import templateer` | **1,136 ms** (973 ms of it `pydantic_ai`) |
| `from_paths` | 1.0 ms |
| first render | 1.19 ms |
| warm render | **0.127 ms** |
| `validate_artifact` | 0.021 ms |

The import is roughly 9,000 warm renders. **This argues for a long-lived
process — not necessarily an event-driven one.** A poll loop is also long-lived.
Gate A10 is what separates the two; gate A13 asks whether either is needed.

**Read that last row as a warning, not a budget.** 0.021 ms is what it costs to
validate nothing. Templateer's built-in parsers cover `toml`, `json`, `yaml` and
`python`; a `markdown` output runs no parser and `check_round_trip` returns
nothing for it. Measured on the fixture pipeline: `validate_artifact` returned
`([], [])` for a good artifact, for the text "total garbage", **and for the
empty string**. Any guard your reconciler builds on that return value is dead
code until you give the template a real check.

Templateer's validator kinds are a closed union — `parse`, `command` and
`markdown` — with no in-process kind. A `command` validator does run for any
language, and it is the correct first fix, but measure it before you keep it:

| Check for one markdown artifact | p50 |
|---|---:|
| `command` validator, `python -m your_check` | 49.5 ms |
| `python -c pass` — the part of that which is pure process start | 35.4 ms |
| the same check called as a function | 0.83 ms |

**Declare the checker in `rules.toml`, next to `collect`, and call it in
`reconcile`.** A subprocess spends 35 ms starting an interpreter to run 0.8 ms
of work, and that dominates every live edit. Keep the module's standard-input
entry point so a Templateer consumer outside your reconciler can still run the
same check as a `command` validator.

### 2.2 templateer_v2 template layout

```yaml
# templates/<name>/metadata.yml
name: <name>                    # MUST equal the directory name
description: One line.

output:
  path: SOMETHING.md            # advisory; you choose where to write
  language: markdown

schema:
  module: schema                # schema.py in this directory
  class: MyModel

renderer:
  file: template.j2             # `engine:` defaults to minijinja

prompt:
  file: prompt.md               # REQUIRED KEY even with no LLM (trap T3)
```

`schema.py` declares the Pydantic model. `template.j2` receives
`model.model_dump(mode="json")`. `undefined_behavior` is hard-coded to
`strict`, so any name drift is a hard `RenderError`. `trim_blocks` and
`lstrip_blocks` are both on.

### 2.3 watchfiles 1.2.0

Installed at 1.2.0. `nixpkgs` has 1.1.1 as `python3Packages.watchfiles`; there
is no top-level attribute. Its only dependency is `anyio`.

```python
def watch(*paths, watch_filter=DefaultFilter(), debounce=1_600, step=50,
          stop_event=None, rust_timeout=5_000, yield_on_timeout=False,
          debug=None, raise_interrupt=True, force_polling=None,
          poll_delay_ms=300, recursive=True,
          ignore_permission_denied=None) -> Generator[set[FileChange], None, None]
```

`Change` is an `IntEnum`: `added=1`, `modified=2`, `deleted=3`.
`FileChange = tuple[Change, str]`.

**The critical correction.** `debounce` is *not* a quiet period. It is the
maximum time a group may grow. The quiet period is `step`, default 50 ms.
Measured: 12 writes 50 ms apart gave **6 separate yields** at defaults, and
**1 yield** at `step=500`.

```python
for changes in watch(
    root,
    watch_filter=SpikeFilter(),
    step=300,               # the real quiet period; coalesces a save burst
    debounce=1_600,         # hard cap on group growth
    rust_timeout=1_000,     # bounded, so stop_event is noticed within ~1 s
    stop_event=stop,        # anything with .is_set(); threading.Event works
    raise_interrupt=False,  # return instead of re-raising KeyboardInterrupt
):
    ...
```

### 2.4 devenv conventions on this machine

- `devenv` 2.1.2. Python 3.13, pinned through the `nixpkgs-python` input.
- `languages.python.uv.enable = true` **installs nothing.** Only
  `uv.sync.enable = true` runs `uv sync` on shell entry.
- **`devenv up` does not run `enterShell`.** A process exports what it needs.
- The venv `bin/` is on the interactive shell's PATH but **not** the task
  runner's PATH.
- `devenv tasks run` needs `-v`, or stdout is swallowed and the log holds `{}`.
- Inside a Nix `''` string a shell variable needs `''$`: `''${PORT:-8080}`.
- A `processes.<name>` entry also appears as task `devenv:processes:<name>`.
- **`uv` is not on PATH outside a devenv shell.** Measured: `which uv` fails.

### 2.5 devman mechanics worth carrying

**Glob matching** — `PurePath.full_match`, never `fnmatch`, on the path
relative to the repository root (`src/devman/watch.py:544`):

```python
if any(PurePath(rel).full_match(g) for g in globs):
    ...
```

**A hash, not a timer** (`groups/format/README.md:70`):

> "Edit `foo.py` a second after the formatter wrote it and the hash differs, so
> the work runs. A suppression window would swallow that edit and would still
> pass a naive 'one save, one run' test."

The spike inherits this. **Never add a suppression window.** Gate A5 tests for
one.

**The ignore list** (`src/devman/watch.py:70-78`). These are `full_match`
globs against a repo-relative path. watchfiles' `ignore_dirs` takes bare
directory *names* and `ignore_paths` takes absolute prefixes — three different
languages. Do not paste devman's tuple into a `DefaultFilter` constructor.
Translate:

```python
class SpikeFilter(DefaultFilter):
    # DefaultFilter's keyword args OVERRIDE the class lists rather than
    # extending them (trap T15), so splat the parent's in.
    ignore_dirs = (*DefaultFilter.ignore_dirs, ".devenv", ".direnv", ".devman")
```

`.devman/` holds the manifest, the log and the pid file, all written while the
daemon runs. It **must** be ignored, or the daemon watches its own bookkeeping.

---

## 3. What the spike builds

### 3.1 The shape

```
devman-spike/
├── devenv.nix
├── devenv.yaml
├── pyproject.toml
├── .gitignore
├── VERSION                     # fixture for gate P2; contains "0.1.0"
├── .devman/
│   ├── rules.toml
│   ├── manifest.json           # derived; gitignored
│   ├── watch.log               # derived; gitignored
│   ├── watch.pid               # derived; gitignored
│   └── watch.stdout            # derived; gitignored
├── templates/
│   ├── doc-index/
│   └── module-table/
├── docs/
│   ├── one.md                  # fixture
│   ├── two.md                  # fixture
│   ├── INDEX.md                # GENERATED, inside the watched tree on purpose
│   └── MODULES.md              # GENERATED
├── src/dspike/
│   ├── __init__.py
│   ├── rules.py                # load and validate .devman/rules.toml
│   ├── collect.py              # the collectors named by rules.toml
│   ├── manifest.py             # hashing, atomic manifest write
│   ├── reconcile.py            # THE CORE — everything else is a caller
│   ├── watcher.py              # watchfiles loop, calls reconcile
│   └── cli.py                  # gen | watch | status
├── tests/
├── scripts/
│   ├── lib.sh
│   ├── gate_*.sh               # one per gate
│   └── demo.sh
└── SPIKE_RESULT.md
```

`docs/INDEX.md` lives inside `docs/`, which is a rule's input glob. That is
deliberate: it is the only way gate A5 tests anything real.

### 3.2 The fixtures — exact contents

Write these verbatim. Gates A2, A7 and A11 compare byte-for-byte, so they are
only reproducible if the fixtures are fixed.

```markdown
<!-- docs/one.md -->
# One

The first document.
```

```markdown
<!-- docs/two.md -->
# Two

The second document.
```

```
0.1.0
```
(`VERSION`, one line, no other content.)

### 3.3 The rule model

`.devman/rules.toml` is the whole configuration:

```toml
[doc-index]
inputs   = ["docs/**/*.md"]
output   = "docs/INDEX.md"
template = "doc-index"
collect  = "dspike.collect:doc_index"

[module-table]
inputs   = ["src/**/*.py"]
output   = "docs/MODULES.md"
template = "module-table"
collect  = "dspike.collect:module_table"
```

A collector is `(root: Path, blobs: dict[str, bytes]) -> dict`. It returns the
model data. **It is handed the bytes; it must not open an input itself** —
see §3.7, and §3.6 enforces it. That is the only extension point, and it is Python rather than more TOML
on purpose: a spike must not grow a configuration language.

**Input expansion excludes every rule's output.** `docs/**/*.md` matches
`docs/INDEX.md`; expansion drops it. This is loop-prevention layer 1 and it is
why the `[doc-index]` rule above is legal as written.

**Rule chains are therefore not supported.** Rule B cannot consume rule A's
output, because every output is dropped from every expansion. Reconcile is
single-pass; a chain would need a bounded fixpoint loop and a cycle refusal,
and the spike has neither. Record in `SPIKE_RESULT.md` whether a real workload
would have wanted one.

`rules.py` must **refuse** to load, naming the file and the fault, when:

1. a key other than `inputs`, `output`, `template`, `collect` appears
2. `collect` does not resolve to a callable
3. `template` is not in the registry — list the templates that *are* loaded
4. **two rules declare the same `output`** — name both rules and the path
5. a collector reads a file inside the root that no input glob covers (§3.6)

Rule 4 matters more than it looks. Two rules on one output clobber each other,
each marks the other stale forever through §3.5's third clause, and under the
daemon they ping-pong without end.

```python
seen: dict[str, str] = {}
for r in rules:
    if r.output in seen:
        raise RuleError(
            f"{path}: rules '{seen[r.output]}' and '{r.name}' both write "
            f"'{r.output}'. One output belongs to exactly one rule."
        )
    seen[r.output] = r.name
```

Follow devman's refusal style: name the file, state what is wrong, state the
legal shape. Never default silently.

### 3.4 Loop prevention — three layers

**Layer 1, structural.** A rule's output never survives input expansion.

**Layer 2, the hash.** Reconcile renders only when the input hash differs. A
second reconcile writes nothing.

**Layer 3, the write.** After writing, record the output's hash. The filesystem
event that write produces reaches the watcher, maps to no rule input, and is
logged as a skip.

**Do not add a fourth layer that suppresses events by time.** Gate A5 tests for
one.

### 3.5 The manifest

`.devman/manifest.json`, gitignored:

```json
{
  "version": 1,
  "rules": {
    "doc-index": {
      "inputs_hash": "sha256:...",
      "output_hash": "sha256:...",
      "output": "docs/INDEX.md",
      "rendered_at": "2026-09-03T12:00:00.000+00:00"
    }
  }
}
```

`inputs_hash` is sha256 over the sorted sequence of
`(relative_path, sha256(content))` pairs. A rename changes it; a touch without
an edit does not.

**A rule is stale when** the input hash differs, **or** the output is missing,
**or** the output's hash on disk differs from `output_hash`. The third clause
repairs a hand-edited artifact (gate A6).

Write atomically: a temporary in the same directory, then `os.replace`. **Give
the temporary a per-process name — `manifest.json.<pid>.tmp`, not
`manifest.json.tmp`.** One shared name is atomic against a *reader* and not
against a second *writer*. Measured over 24 concurrent `gen` processes against
a shared name: 21 exited 0, 2 exited 1, and 1 exited 2 with
`FileNotFoundError: .devman/manifest.json.tmp`, because a peer had already
renamed the shared temporary away. With per-process names, 48 of 48 exited 0.
The same rule applies to the output write.

**A missing, unparsable, or unknown-version manifest is not an error.** Treat it
as empty and rebuild everything, logging one line saying which case fired. A
daemon that dies on a `JSONDecodeError` stops updating the tree with no repair
path, and `git clean -x` in another terminal is enough to cause it. Gate A16
tests all three states.

### 3.6 Purity enforcement — the P2 mechanism

A collector that reads a file no glob covers breaks the whole design silently.
Detect it with an audit hook. Verified working on Python 3.13:

```python
import sys

def collect_checked(rule, root, blobs, expanded):
    opened: list[str] = []
    hook = lambda ev, a: opened.append(str(a[0])) if ev == "open" else None
    sys.addaudithook(hook)          # NOTE: audit hooks CANNOT be removed
    data = rule.collect(root, blobs)
    stray = sorted({p for p in opened if inside(root, p) and Path(p) not in expanded})
    if stray:
        raise RuleError(
            f"rule '{rule.name}': collector read {stray[0]}, which no glob in "
            f"inputs={rule.inputs} covers. A change to it would never be seen."
        )
    return data
```

`sys.addaudithook` cannot be removed once installed, so install **one** hook at
process start writing into a module-level list, and clear the list around each
collector call. Exclude `.devman/`, `__pycache__`, and anything outside `root`.

If you cannot make this work, **say so in `SPIKE_RESULT.md`** and mark Q1
UNCHECKED. Do not silently drop the gate.

### 3.7 The core function

Everything routes through one function. `gen`, `watch` and every test call it.

```python
def reconcile(root: Path, rules: list[Rule], registry: TemplateRegistry,
              only: list[str] | None = None) -> ReconcileReport:
    """Bring every stale output up to date. Idempotent."""
```

`ReconcileReport` carries `written: list[str]`, `skipped: list[str]`,
`errors: list[tuple[str, str]]`, `duration_ms: float`.

**Per-rule error isolation is required.** A collector that raises must not stop
the other rules. `gen` exits non-zero when `errors` is non-empty, after doing
every rule it could.

**Read each input's bytes exactly once.** This is the whole torn-read defence,
and it is a design rule rather than a check. Without it the manifest can record
a hash the artifact was never built from, and the output stays wrong forever —
no restart repairs it, because the rule never looks stale again.

```python
# Read once. Hash the bytes you rendered from, never a second read of the file.
blobs = {rel: path.read_bytes() for rel, path in expanded}
inputs_hash = hash_blobs(blobs)          # over the bytes in hand
data = collect_checked(rule, root, blobs, expanded)
artifact = registry.render_from_model(rule.template, data)
write_atomic(rule.output, artifact.rstrip("\n") + "\n")   # output first...
record(rule, inputs_hash, sha256(artifact))               # ...then the manifest
```

This is why §3.3's collector signature takes `blobs` rather than paths. Take
that cost: a collector that re-opens a file it was handed can read different
bytes than the ones that were hashed, which is exactly the failure A11 exists
to catch. §3.6's audit hook also catches the re-read, because a second `open`
of an input is still an `open`.

**Order matters: write the output, then the manifest.** A crash between them
leaves an output whose hash does not match the manifest, which §3.5's third
clause repairs. A crash in the other order leaves a manifest claiming work that
was never done, which nothing repairs.

`only` narrows to rules and is a latency optimization, nothing more. **The
watcher must never be the only path that produces a correct tree.**

---

## 4. Build order

Each stage ends in gates. Run them. Record the real output in
`SPIKE_RESULT.md`. Do not start the next stage until they pass.

### Stage 1 — the environment

```toml
# pyproject.toml
[project]
name = "dspike"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["templateer", "watchfiles>=1.2.0"]

[project.scripts]
dspike = "dspike.cli:main"

[project.optional-dependencies]
dev = ["pytest", "ruff"]

[tool.uv.sources]
templateer = { path = "../templateer_v2" }   # NOT editable — ground rule 2

[tool.pytest.ini_options]
pythonpath = ["src"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

templateer_v2 builds with hatchling, so the non-editable path dependency
resolves to a wheel and writes nothing into its source tree.

```yaml
# devenv.yaml
inputs:
  nixpkgs:
    url: github:cachix/devenv-nixpkgs/rolling
  nixpkgs-python:
    url: github:cachix/nixpkgs-python
```

The `nixpkgs-python` input is what makes `version = "3.13"` resolve. Without it
the shell fails to evaluate.

```nix
# devenv.nix
{ pkgs, lib, config, inputs, ... }:

{
  packages = [ pkgs.git pkgs.uv ];

  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;     # uv.enable alone installs NOTHING
    };
  };

  # `devenv up` does not run enterShell, so the process exports its own path.
  # `exec` replaces the shell, so devenv's signals reach the daemon directly.
  processes.dspike-watch.exec = ''
    export PYTHONPATH="$DEVENV_ROOT/src''${PYTHONPATH:+:$PYTHONPATH}"
    exec python -m dspike.cli watch --root "$DEVENV_ROOT"
  '';

  tasks = {
    "dspike:gen".exec   = "python -m dspike.cli gen";
    "dspike:check".exec = "ruff check .";
    "dspike:test".exec  = "pytest";
  };
}
```

`.gitignore`:

```
.devenv/
.venv/
__pycache__/
templates/*/__pycache__/
.devman/manifest.json
.devman/watch.log
.devman/watch.pid
.devman/watch.stdout
```

The `templates/*/__pycache__/` line is load-bearing: loading a schema runs
`exec_module`, which writes a `.pyc` beside the template (trap T13). Without
it, ground rule 7's "commit after every gate" fails on a dirty tree.

**Gate S1**

```bash
cd ~/Documents/Projects/devman-spike
devenv shell -- python -c "import templateer, watchfiles; print('ok', watchfiles.version.VERSION)"
devenv shell -- python -c "import dspike; print('dspike importable')"
git -C ~/Documents/Projects/templateer_v2 status --porcelain   # MUST be empty
```

If `devenv shell -- <cmd>` is not the right form on this devenv, run
`devenv shell --help`, use whatever it documents, and record the correction in
`SPIKE_RESULT.md` §"What the guide got wrong".

### Stage 2 — the templates

Write both templates in full. Then prove they render with no LLM, no daemon and
no `dspike` code:

**Gate S2**

```bash
devenv shell -- env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY python -c "
from pathlib import Path
from templateer import TemplateRegistry
r = TemplateRegistry.from_paths([Path('templates').resolve()])
assert len(r) == 2, (len(r), r._catalog.load_errors)
print(r.render_from_model('doc-index',
      {'title':'T','entries':[{'path':'a.md','heading':'A'}]}))
"
```

The `assert` is mandatory. A template that fails to load **vanishes silently** —
no exception, `len(registry) == 0`, and the only trace is
`registry._catalog.load_errors`, which has no public accessor (trap T4).

**Commit the golden files now, in this stage, before `reconcile.py` exists.**

```bash
mkdir -p tests/golden
devenv shell -- python - <<'PY'
from pathlib import Path
from templateer import TemplateRegistry
r = TemplateRegistry.from_paths([Path('templates').resolve()])
data = {"title": "Documentation index", "entries": [
    {"path": "one.md", "heading": "One"},
    {"path": "two.md", "heading": "Two"}]}
art = r.render_from_model('doc-index', data)
Path('tests/golden/INDEX.md').write_text(art.rstrip("\n") + "\n")
PY
git add tests/golden && git commit -m "S2: golden artifacts, rendered before reconcile existed"
```

This ordering is the point. A golden produced later by `dspike gen` would be a
copy of the tool's own output diffed against itself — it would restate A1's
determinism and could not catch a wrong-but-stable rendering. Rendered here,
through `TemplateRegistry` alone, it is an independent baseline: any later
change to a collector or a template that alters the artifact fails A2 loudly
instead of silently re-baselining.

### Stage 3 — `reconcile` and `gen`, with no watcher

Write `rules.py`, `collect.py`, `manifest.py`, `reconcile.py`, and a `cli.py`
with `gen` and `status`. **Do not write the watcher yet.**

`gen` must accept `--json` and print `{"written":[...], "skipped":[...],
"errors":[...], "duration_ms":N}` to stdout. Gates A1 and A13 parse it.

**Gate A1 — the fixpoint**

```bash
rm -f docs/INDEX.md docs/MODULES.md .devman/manifest.json
python -m dspike.cli gen --json > /tmp/g1.json ; echo "exit=$?"
python -m dspike.cli gen --json > /tmp/g2.json ; echo "exit=$?"
python - <<'PY'
import json
a=json.load(open('/tmp/g1.json')); b=json.load(open('/tmp/g2.json'))
assert a['written'], 'first run wrote nothing'
assert b['written'] == [], f'NOT A FIXPOINT: second run wrote {b["written"]}'
assert not a['errors'] and not b['errors']
print('A1 PASS', a['written'])
PY
```

**Gate A2 — cold correctness.** Delete the outputs and the manifest, run `gen`,
diff against the **stage 2 golden** — the one rendered before `reconcile.py`
existed. Byte-identical.

```bash
rm -f docs/INDEX.md docs/MODULES.md .devman/manifest.json
python -m dspike.cli gen
diff -u tests/golden/INDEX.md docs/INDEX.md \
  || { echo "A2 FAIL — the pipeline does not reproduce the independent render"; exit 1; }
echo "A2 PASS"
```

If this fails, the collector and the template disagree about the model. Do not
re-baseline the golden to make it pass — that is ground rule 6.

Trap T8: `render_from_model` returns a string with **no trailing newline**.
Write `artifact.rstrip("\n") + "\n"`.

**Gate P1 — purity under relocation.** The antecedent, tested directly:

```bash
python -m dspike.cli gen
rm -rf /tmp/spike-copy && cp -r . /tmp/spike-copy
rm -f /tmp/spike-copy/.devman/manifest.json \
      /tmp/spike-copy/docs/INDEX.md /tmp/spike-copy/docs/MODULES.md
( cd /tmp/spike-copy \
  && env -i PATH="$PATH" HOME=/tmp/fakehome USER=nobody TZ=Pacific/Kiritimati \
       python -m dspike.cli gen )
diff -u docs/INDEX.md /tmp/spike-copy/docs/INDEX.md \
  && diff -u docs/MODULES.md /tmp/spike-copy/docs/MODULES.md \
  || { echo "P1 FAIL — output depends on path, user, env or clock"; exit 1; }
echo "P1 PASS"
```

If this fails, an absolute path, a username, a timestamp or a locale leaked
into an artifact. Find it. It is the antecedent breaking.

**Gate P2 — untracked input detection.** Add a third rule whose collector reads
`VERSION`, which no glob covers:

```toml
[stray]
inputs   = ["docs/**/*.md"]
output   = "docs/STRAY.md"
template = "doc-index"
collect  = "dspike.collect:stray_reads_version"
```

```bash
python -m dspike.cli gen 2>&1 | tee /tmp/p2.txt ; test "${PIPESTATUS[0]}" -ne 0 \
  || { echo "P2 FAIL — a stray read was accepted"; exit 1; }
grep -q 'VERSION' /tmp/p2.txt \
  || { echo "P2 FAIL — refused, but did not name the file"; exit 1; }
echo "P2 PASS"
# Remove the [stray] rule and docs/STRAY.md before continuing.
```

If §3.6's audit hook does not work, record Q1 as **UNCHECKED** in
`SPIKE_RESULT.md` and note that a permanently wrong artifact is silently
reachable. That is a real finding.

**Gate A11 — the torn read.** The sharpest test of the whole design:

```bash
python -m dspike.cli gen
( for i in $(seq 1 400); do echo "# churn $i" > docs/one.md; done ) &
CHURN=$!
for i in $(seq 1 5); do python -m dspike.cli gen >/dev/null 2>&1 || true; done
wait $CHURN
python -m dspike.cli gen                       # tree is still now; must be correct
sha_after=$(sha256sum docs/INDEX.md | cut -d' ' -f1)
rm -f docs/INDEX.md .devman/manifest.json
python -m dspike.cli gen
sha_clean=$(sha256sum docs/INDEX.md | cut -d' ' -f1)
test "$sha_after" = "$sha_clean" \
  || { echo "A11 FAIL — a mid-reconcile change was recorded as reconciled"; exit 1; }
echo "A11 PASS"
git checkout -- docs/one.md
```

**Gate A13 — the null hypothesis.** No daemon at all. Measure `gen` as a save
hook:

```bash
for i in $(seq 1 10); do
  t0=$(date +%s%3N); echo "# H$i" > docs/hook$i.md
  python -m dspike.cli gen >/dev/null
  t1=$(date +%s%3N); echo $(( t1 - t0 ))
done | sort -n | awk '{a[NR]=$1} END {print "A13 hook p50=" a[int(NR/2)] " max=" a[NR]}'
rm -f docs/hook*.md && python -m dspike.cli gen
```

Record both numbers. §6 compares them against A4's daemon numbers and against
what `watcher.py` costs in lines.

### Stage 4 — the watcher

Write `watcher.py` and the `watch` subcommand. Requirements — all of them are
tested, so implement all of them:

1. Reconcile once at startup, before watching. Log the report.
2. Write `.devman/watch.pid`, then print exactly `dspike watch: ready` on
   stdout, **flushed**.

   **Print it from inside the watch loop's first iteration, not before the
   loop.** `watchfiles.watch` registers its watches when iteration begins, so
   an edit that lands between an earlier print and the first iteration reaches
   no watch and is lost for the rest of the uptime. Measured: two of two runs
   that edited immediately after `ready` saw no wake-up at all; three of three
   that waited one second saw the edit. Pass `yield_on_timeout=True` so the
   first iteration is guaranteed within `rust_timeout` even when nothing
   changed. **Do not fix this with a confirming reconcile after `ready`** —
   that adds a periodic wake-up and gate A10 refuses it.
3. Watch `root` with `step=300`, `rust_timeout=1000`, `stop_event`,
   `raise_interrupt=False`, `yield_on_timeout=True`,
   `watch_filter=SpikeFilter()` (§2.5).
4. On a batch: map changed paths to rules by `PurePath(rel).full_match` against
   each rule's **literal `inputs` globs** — not against the expanded file list.

   This distinction decides two gates, so get it right. Layer 1's exclusion
   belongs to input *expansion*, which is what the collector receives. It must
   not narrow this match, because `PurePath("docs/INDEX.md").full_match(
   "docs/**/*.md")` is `True` and **that is what makes gate A6 possible**: a
   hand-edited artifact maps back to the rule that owns it, and §3.5's
   `output_hash` clause repairs it. Match against the expanded list instead and
   a corrupted artifact maps to nothing, so no implementation can pass A6.

   **A rule is also reached by a change to the output it owns.** Match that
   explicitly — `rule.output in changed_relative_paths` — as a second clause.
   Do not rely on the glob to cover it. `docs/INDEX.md` matches `docs/**/*.md`
   only by the accident of that layout, and a rule whose output sits outside its
   input globs is never selected and never repaired. Measured on a rule set
   whose outputs live under `generated/`: a hand-edited artifact produced no
   wake-up for 30 s. Gate A6 passes with one clause on the four-file tree and
   fails on any tree where outputs and inputs live apart.

   Then call `reconcile(only=[...])`. If no rule matches, do nothing and log
   nothing. Never pass `only=[]`.
5. **Log one line per reconcile call to `.devman/watch.log`, flushed
   immediately**, as JSON:
   `{"at":...,"trigger":[...],"written":[...],"duration_ms":N}`

   `written` is empty when nothing was stale. That case is normal and expected:
   the daemon's own write to `docs/INDEX.md` wakes it, maps back to `doc-index`,
   finds the recorded `output_hash` unchanged, and does nothing. **Gate A5
   counts lines with a non-empty `written`, not wake-ups** — the echo is
   loop prevention working, not a loop. `flush=True` on every write, or the
   counts lag and the gates go non-deterministic.
6. `--once-then-exit`: do the startup reconcile, print `ready`, then exit 0
   without entering the watch loop. Stage 4's gate uses it.
7. On `SIGTERM` and `SIGINT`: set `stop_event`, remove the pid file, exit 0.

**Gate S4**

```bash
python -m dspike.cli watch --root "$PWD" --once-then-exit
test $? -eq 0 && grep -q 'dspike watch: ready' <(python -m dspike.cli watch --root "$PWD" --once-then-exit)
```

### Stage 5 — the harness

Write `scripts/lib.sh` exactly as below. **It was tested against four fake
daemons before this guide shipped** — do not improvise a replacement:

| Case | Required behaviour | Measured |
|---|---|---|
| well-behaved daemon | start, ready, settle, stop | pass, clean exit |
| daemon that dies before `ready` | fail fast, not after the 60 s timeout | failed in **0 s** |
| daemon that ignores `SIGTERM` | escalate to `SIGKILL` | killed after **5 s** grace |
| daemon reconciling forever | `settle` times out and returns failure | timed out at 27 reconciles |

The last row is the point. V1's check exited in 5 ms and would have called that
infinite loop a pass.

**Run every gate script from inside a devenv shell**, so `python` resolves to
the project venv:

```bash
devenv shell -- bash scripts/gate_a5.sh
```

The daemon is started as `python -m dspike.cli`, never `uv run ...`. A wrapper
process would leave `$!` pointing at the wrapper, and `cleanup` would kill the
wrapper while the daemon kept running and raced the next gate.

```bash
# scripts/lib.sh — source from every gate script.

# Double-sourcing would reset WATCH_PID and orphan a running daemon.
# `if`, not `[ ... ] && return 0`: the short form works, but only because bash
# exempts a non-final member of an AND-OR list from `set -e`. Do not rely on it.
if [ -n "${DSPIKE_LIB_SOURCED:-}" ]; then return 0; fi
DSPIKE_LIB_SOURCED=1

set -euo pipefail

ROOT="${ROOT:-$PWD}"
LOG="$ROOT/.devman/watch.log"
OUT="$ROOT/.devman/watch.stdout"
WATCH_PID=""

cleanup() {
  [ -n "$WATCH_PID" ] || return 0
  if kill -0 "$WATCH_PID" 2>/dev/null; then
    kill -TERM "$WATCH_PID" 2>/dev/null || true
    for _ in $(seq 1 50); do
      kill -0 "$WATCH_PID" 2>/dev/null || break
      sleep 0.1
    done
    kill -KILL "$WATCH_PID" 2>/dev/null || true
  fi
  rm -f "$ROOT/.devman/watch.pid"
  WATCH_PID=""
}

# A bare `trap cleanup INT` would clean up and then CONTINUE the script, which
# can end in exit 0 after an interrupt. Re-raise so the status is honest.
trap 'cleanup' EXIT
trap 'cleanup; trap - INT;  kill -INT  $$' INT
trap 'cleanup; trap - TERM; kill -TERM $$' TERM

# wait_for <timeout_s> <description> <command...>
wait_for() {
  local timeout="$1"; shift
  local what="$1"; shift
  local deadline=$(( $(date +%s) + timeout ))
  until "$@" >/dev/null 2>&1; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "TIMEOUT after ${timeout}s waiting for: $what" >&2
      return 1
    fi
    sleep 0.1
  done
}

start_watch() {
  mkdir -p "$ROOT/.devman"
  : > "$OUT"; : > "$LOG"
  python -m dspike.cli watch --root "$ROOT" > "$OUT" 2>&1 &
  WATCH_PID=$!
  local deadline=$(( $(date +%s) + 60 ))
  until grep -q 'dspike watch: ready' "$OUT" 2>/dev/null; do
    # Do not wait 60 s for a process that already died.
    if ! kill -0 "$WATCH_PID" 2>/dev/null; then
      echo "daemon exited before printing ready:" >&2; cat "$OUT" >&2
      WATCH_PID=""; return 1
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "TIMEOUT: daemon never printed ready" >&2; cat "$OUT" >&2
      return 1
    fi
    sleep 0.1
  done
}

stop_watch() { cleanup; }

# Every reconcile call the daemon logged, including ones that wrote nothing.
reconciles() {
  if [ -f "$LOG" ]; then grep -c '"duration_ms"' "$LOG" || true; else echo 0; fi
}
# Only the reconciles that actually rendered. A5 counts THESE: the daemon waking
# on its own output write and finding nothing stale is loop prevention working,
# not a loop, and it must not be scored as one.
renders() {
  if [ -f "$LOG" ]; then grep -c '"written":\["' "$LOG" || true; else echo 0; fi
}

# settle <quiet_s> <max_s> — echo the RENDER count once it stops moving.
# A plain `wait_for ... test "$(reconciles)" -eq N` does NOT work: the command
# substitution expands once, before the loop, so the loop retests a constant.
settle() {
  local quiet="$1" max="$2" last=-1 now
  local deadline=$(( $(date +%s) + max ))
  while :; do
    sleep "$quiet"
    now=$(renders)
    if [ "$now" = "$last" ]; then echo "$now"; return 0; fi
    last="$now"
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "SETTLE TIMEOUT: render count still moving at $now" >&2
      echo "$now"; return 1
    fi
  done
}
```

**Gate S5 — the daemon's own shutdown, not `cleanup`'s.** The obvious S5
("stop it, confirm the process is gone and the pid file is removed") tests
nothing: `cleanup` escalates to `SIGKILL` and runs `rm -f` on the pid file, so
both assertions are satisfied by the harness. Measured — a daemon whose only
deviation is `signal.signal(SIGTERM, SIG_IGN)` passes that S5, after `cleanup`
spends 5,404 ms killing it.

Signal the daemon directly and assert all three clauses of stage 4 requirement 7,
before `cleanup` can do any of the work:

```bash
# scripts/gate_s5.sh
source scripts/lib.sh
PIDFILE="$ROOT/.devman/watch.pid"
dead() { ! kill -0 "$1" 2>/dev/null; }
gone() { [ ! -f "$PIDFILE" ]; }
fail() { echo "S5 FAIL — $1"; exit 1; }

cycle() {                       # one full start/stop cycle, per signal
  local sig="$1" p rc=0
  rm -f "$PIDFILE"
  start_watch || fail "the daemon never became ready"
  p="$WATCH_PID"
  # Requirement 2 prints `ready` and writes the pid file; the order is not fixed.
  wait_for 5 "the daemon to write its pid file" test -f "$PIDFILE" \
    || fail "no pid file 5 s after ready"
  test "$(cat "$PIDFILE")" = "$p" \
    || fail "pid file holds $(cat "$PIDFILE"), daemon is $p"
  kill -"$sig" "$p"
  wait_for 10 "the daemon to exit on SIG$sig" dead "$p" \
    || fail "daemon still alive 10 s after SIG$sig"
  wait "$p" || rc=$?
  test "$rc" -eq 0 || fail "daemon exited $rc on SIG$sig, want 0"
  wait_for 5 "the daemon to remove its pid file" gone \
    || fail "the daemon did not remove its own pid file on SIG$sig"
  WATCH_PID=""                  # already reaped; keep cleanup out of the result
}

cycle TERM
cycle INT
echo "S5 PASS"
```

Clearing `WATCH_PID` on the success path stops `cleanup` from doing the gate's
work. The `EXIT` trap stays as the backstop on every failure path.

Verified in a sandbox against this `lib.sh`: a conformant daemon passes whether
it writes the pid file before or 300 ms after `ready`; a `SIGTERM`-deaf daemon
fails with "daemon still alive 10 s after SIGTERM"; a daemon with no handler
fails with "exited 143 on SIGTERM, want 0"; a daemon that exits 0 but keeps its
pid file fails with "did not remove its own pid file".

### Stage 6 — the daemon's gates

**Gate A5 — loop prevention. One edit, one *render*.** Two parts, and the
second is what makes it real.

The daemon wakes twice for one edit, and that is correct: once for your write to
`docs/four.md`, and once for its own write to `docs/INDEX.md`, which maps back
to `doc-index` (stage 4 requirement 4) and finds nothing stale. Counting
wake-ups would score that second, healthy wake as a loop. Count renders.

```bash
source scripts/lib.sh
python -m dspike.cli gen
start_watch
before_w=$(renders); before_r=$(reconciles)

echo "# Four" > docs/four.md
wait_for 20 "artifact update" grep -q 'four' docs/INDEX.md

after_w=$(settle 2 30) \
  || { echo "A5 FAIL — render count never settled; this is the loop"; exit 1; }
test "$after_w" -eq "$((before_w + 1))" \
  || { echo "A5 FAIL — $((after_w - before_w)) renders for one edit"; exit 1; }

# The daemon MUST have woken on its own write to docs/INDEX.md and rendered
# nothing. Without this, A5 also passes when the watcher never observed the
# write at all — layer 3 would be entirely untested.
test "$(reconciles)" -gt "$after_w" \
  || { echo "A5 FAIL — the output write was never observed; layer 3 untested"; exit 1; }
echo "A5 PASS — $((after_w - before_w)) render, $(( $(reconciles) - before_r )) wake-ups"
stop_watch
rm -f docs/four.md
```

**Gate A4 — latency. Fails when p50 exceeds 400 ms or max exceeds 2,000 ms.**
Daemon up, ten edits, milliseconds from write to the artifact carrying the new
content. A one-second poll loop has p50 near 500 ms and fails this bound.
Record both numbers either way.

**Gate A10 — idle cost. The only gate a poll loop fails.**

```bash
source scripts/lib.sh
start_watch
before=$(reconciles)
cpu0=$(awk '{print $14+$15}' /proc/$WATCH_PID/stat)   # utime+stime, in ticks
bash -c 'sleep 60'                                     # no edits at all
cpu1=$(awk '{print $14+$15}' /proc/$WATCH_PID/stat)
ticks=$(( cpu1 - cpu0 ))                               # 100 ticks = 1 s CPU
test "$ticks" -le 20 \
  || { echo "A10 FAIL — ${ticks} CPU ticks over 60 idle seconds"; exit 1; }
test "$(reconciles)" -eq "$before" \
  || { echo "A10 FAIL — reconciled with no input change"; exit 1; }
echo "A10 PASS — ${ticks} CPU ticks idle over 60 s"
stop_watch
```

**Gate A6 — repair.** Daemon up. Overwrite `docs/INDEX.md` with `garbage`. The
daemon restores it within 20 s. This proves §3.5's `output_hash` clause.

**Gate A7 — crash safety.** Daemon up. `kill -9` it during a burst of 50
writes. Then the manifest still parses as JSON, and one `gen` reaches the same
state as a clean rebuild:

```bash
python -m dspike.cli gen
sha_after=$(sha256sum docs/INDEX.md docs/MODULES.md | sha256sum)
rm -f docs/INDEX.md docs/MODULES.md .devman/manifest.json
python -m dspike.cli gen
sha_clean=$(sha256sum docs/INDEX.md docs/MODULES.md | sha256sum)
test "$sha_after" = "$sha_clean" || { echo "A7 FAIL"; exit 1; }
```

**Gate A12 — scale. Fails above 3,000 ms.** Four markdown files measure
nothing. Measured on this machine: 10,000 files of 400 bytes cost ~230 ms to
enumerate and hash with a warm cache — a hard floor under every edit.

```bash
python - <<'PY'
import pathlib
for i in range(10000):
    d = pathlib.Path(f"docs/bulk/d{i//100:03d}"); d.mkdir(parents=True, exist_ok=True)
    (d / f"f{i:05d}.md").write_text(f"# h{i}\n\n" + "x"*400 + "\n")
PY
time python -m dspike.cli gen                 # cold build at 10k inputs
source scripts/lib.sh
start_watch
t0=$(date +%s%3N); echo "# Bulk" > docs/bulk/d000/f00000.md
wait_for 30 "artifact update" grep -q 'Bulk' docs/INDEX.md
t1=$(date +%s%3N)
echo "A12 one-edit latency at 10,000 inputs: $(( t1 - t0 )) ms"
test $(( t1 - t0 )) -le 3000 || { echo "A12 FAIL"; exit 1; }
stop_watch
rm -rf docs/bulk && python -m dspike.cli gen
```

If A12's number is far above A4's, the finding is that `inputs_hash` needs an
mtime-and-size prefilter before the content hash. Record it — that reopens
§2.5's "a hash, not a timer" rule and is worth knowing before anything is built
for real.

**Gate A14 — event loss inside one uptime.** The reconcile-at-startup argument
only covers restarts. Inside a single uptime a lost event — an inotify queue
overflow, a rename the filter drops, the loop blocked inside a long reconcile
while the Rust buffer fills — leaves an output stale indefinitely with nothing
to notice it. A daemon running for a week stays wrong for a week.

```bash
source scripts/lib.sh
start_watch
python - <<'PY'
import pathlib
d = pathlib.Path("docs/flood"); d.mkdir(parents=True, exist_ok=True)
for i in range(20000):
    (d / f"f{i:05d}.md").write_text(f"# flood {i}\n")
PY
wait_for 120 "tree to converge after a 20,000-file flood" \
  grep -q 'flood 19999' docs/INDEX.md \
  || { echo "A14 FAIL — an event was lost and nothing repaired it"; exit 1; }
echo "A14 PASS"
stop_watch
rm -rf docs/flood && python -m dspike.cli gen
```

**If A14 fails, add a periodic floor** — a full reconcile every N seconds — and
re-run it. That is allowed and it is not the banned fourth layer. §3.4 bans a
time window that *suppresses* a reconcile after a write; a periodic reconcile is
a safety net that only ever does more work. Record in `SPIKE_RESULT.md` whether
the floor was needed, because **it is the spike's most useful single result**:
a design that needs a periodic floor has already conceded most of the gap
between a watcher and a poller, and gate A10 should then be read again in that
light.

**Gate A15 — every rule fires live.** Every other live gate edits `docs/*.md`
and greps `docs/INDEX.md`. A watcher whose trigger map is wrong for
`src/**/*.py` never fires `module-table`, and A4, A5, A6, A7 and A12 all still
pass — A7 re-runs a full `gen` before comparing, so it hides the fault. Drive
this off `rules.toml` so it cannot drift from the config:

```bash
source scripts/lib.sh
start_watch
python - <<'PY' > /tmp/rulepairs.txt
import tomllib, pathlib
for name, r in tomllib.loads(pathlib.Path(".devman/rules.toml").read_text()).items():
    print(name, r["inputs"][0], r["output"])
PY
while read -r name glob out; do
  # touch one existing file matching this rule's first input glob
  victim=$(python - "$glob" <<'PY'
import sys, pathlib
print(next(iter(sorted(pathlib.Path('.').glob(sys.argv[1]))), ''))
PY
)
  [ -n "$victim" ] || { echo "A15 FAIL — no file matches $glob for rule $name"; exit 1; }
  before=$(sha256sum "$out" | cut -d' ' -f1)
  printf '\n<!-- a15 %s -->\n' "$name" >> "$victim"
  wait_for 20 "rule $name to fire" \
    bash -c "test \"\$(sha256sum '$out' | cut -d' ' -f1)\" != '$before'" \
    || { echo "A15 FAIL — rule '$name' never fired on a change to $victim"; exit 1; }
  git checkout -- "$victim"
done < /tmp/rulepairs.txt
echo "A15 PASS — every rule fired"
stop_watch
python -m dspike.cli gen
```

**Gate A16 — manifest damage.** Three states, all reachable from another
terminal running `git clean -x`:

```bash
source scripts/lib.sh
start_watch
for damage in delete corrupt future; do
  case $damage in
    delete)  rm -f .devman/manifest.json ;;
    corrupt) printf 'x' > .devman/manifest.json ;;
    future)  printf '{"version": 99, "rules": {}}' > .devman/manifest.json ;;
  esac
  echo "# A16 $damage" > docs/a16.md
  wait_for 20 "recovery from a $damage manifest" grep -q "A16 $damage" docs/INDEX.md \
    || { echo "A16 FAIL — did not recover from a $damage manifest"; exit 1; }
  kill -0 "$WATCH_PID" 2>/dev/null \
    || { echo "A16 FAIL — the daemon died on a $damage manifest"; exit 1; }
done
echo "A16 PASS"
stop_watch
rm -f docs/a16.md && python -m dspike.cli gen
```

### Stage 7 — refusals

Seven rows. Assert on the **exit code and the message**, not the code alone:

| Input | Required behaviour |
|---|---|
| unknown key in `rules.toml` | exit ≠ 0, names the file, the key, the legal keys |
| `collect` that does not resolve | exit ≠ 0, names the rule and the string |
| `template` not in the registry | exit ≠ 0, lists the templates that *are* loaded |
| two rules, same `output` | exit ≠ 0, names both rules and the path |
| a template that fails to load | exit ≠ 0, quotes `load_errors` |
| collector data failing validation | exit ≠ 0, names the rule and the pydantic error |
| **a collector that raises** | exit ≠ 0, names that rule, **and the other rule's output is still up to date** |

The last row is per-rule error isolation. A reconciler that aborts the pass on
one bad rule breaks the design for every other rule in the file.

**Gate S7** — every row has a test and every test passes.

### Stage 8 — the measurements

**Gate A8 — import amortization. Fails when `cold_ms / daemon_ms < 20`.** Time
ten cold `gen` runs with nothing stale, against ten in-daemon reconciles from
`watch.log`. Expect ~1,200–1,600 ms against a few milliseconds, a ratio in the
hundreds. Below 20, the daemon does not amortize enough to justify being a
process, and §6 routes to the hook.

**Gate A9 — size. Two comparisons, because one of them is rigged.**

```bash
# The spike's own total. Cannot be gamed by moving code out of src/.
find src tests scripts templates \( -name '*.py' -o -name '*.sh' \) | xargs wc -l | tail -1
find src tests scripts templates \( -name '*.py' -o -name '*.sh' \) | xargs wc -l

# The FAIR baseline: devman's watch-and-trigger subset only.
wc -l ~/Documents/Projects/devman/src/devman/watch.py     # 574
```

Report `spike total vs 574`. Report devman's full 3,923 Python / 4,435 Nix as
**prose context only, never as the gate** — §1 removes the registry,
`workflow.py`, `run.py`, `doctor.py`, `show.py`, every Nix module and the whole
Dagu path from scope, and those modules are where most of that count lives. A
ratio against work the spike never attempted is a number that cannot argue.

### Stage 8b — three questions already answered, so do not re-derive them

A later spike extended this design to eight artifact kinds over typed fixture
inputs and measured what this guide left open. Take the answers; re-measure only
if your shape differs.

**Rule fan-out is linear, so one rule per output is enough.** One rule writes
one output, so N sources by M kinds needs N×M rules. Measured to 1,024 rules:
cold build ~7.4 ms per rule, a no-op reconcile ~0.20 ms per rule, and **a live
edit flat at 4.95 ms for 8 rules and 8.30 ms for 1,024**, because
`reconcile(only=[…])` never touches an unselected rule. Do not design a fan-out
reconciler. If you need many sources, generate the rules. The counterfactual is
the argument for `only`: with no rule selection, one keystroke costs 217 ms at
1,024 rules.

**End-to-end latency is the watcher's, not the reconciler's.** Over 20 samples
the edit-to-artifact time was p50 271 ms, max 279 ms, against a 5 ms reconcile.
Making the reconcile 12× faster moved it by nothing. `step` and `debounce` set
this floor. Optimise the reconciler for the cold path and for correctness, and
stop expecting latency to follow.

**The obsolete-output policy: report always, remove only when asked.** When a
rule is deleted its artifact stays on disk. The signal is the manifest, not a
directory scan — a scan cannot tell an obsolete artifact from a file a person
put there. Report it on every run. Remove it only under an explicit `--prune`,
matching devman's own `doctor --prune`, and only when the file's bytes still
hash to what the manifest recorded; an edited file is somebody's work, so name
it and stop. **The daemon never prunes.**

---

## 5. The demo

`scripts/demo.sh` runs unattended and writes `.devman/demo-transcript.txt`.

**It must be re-runnable.** Act 1 needs an empty tree, which does not exist by
the time the demo runs. Start with a reset:

```bash
git stash push -u -- docs .devman/rules.toml >/dev/null 2>&1 || true
git checkout -- docs 2>/dev/null || true
rm -f docs/INDEX.md docs/MODULES.md .devman/manifest.json docs/three.md docs/five.md docs/six.md
```

Five acts, each echoing a heading:

1. **Cold build.** Empty tree → `gen` → show the artifacts. Show the second
   `gen` writing nothing.
2. **Live.** Start the daemon. Add `docs/five.md`. Show `INDEX.md` gaining the
   entry, with the measured latency.
3. **The two failures that matter.** Show P2 refusing a stray read, naming
   `VERSION`. Then show A11's torn-read guard skipping rather than recording a
   hash it cannot stand behind. **These are the acts that carry the result** —
   they are where the design could have been wrong and was not.
4. **Repair.** Overwrite `INDEX.md` with garbage. Show it restored.
5. **The comparison.** Print A4's daemon p50, A13's hook p50, A10's idle ticks,
   and A9's line count side by side. End on the recommendation those numbers
   support.

`demo.sh` exits 0 only when every act succeeded, and cleans up through
`lib.sh`'s trap on every exit path.

---

## 6. The verdict

Fill in `SPIKE_RESULT.md`. Do not soften a failure.

```markdown
# SPIKE_RESULT — the reconciler spike

Date: <absolute date>
Commit: <sha>

## Q1 — does the antecedent hold?
**UPHELD | BROKEN | UNCHECKED** — evidence: <P1, P2 transcripts>

## Q2 — does the reconciler hold under adversarial conditions?
**UPHELD | BROKEN** — evidence: <A1, A2, A6, A7, A11 transcripts>

## Q3 — is a daemon worth building?
**YES | NO — USE A HOOK | NO — IT IS A TIMER** — evidence: <A4, A10, A13>

## Gates

| Gate | What it checks | Threshold | Result | Evidence |
|---|---|---|---|---|
| P1 | output does not depend on path, user, env, clock | identical | | |
| P2 | a stray read is refused and named | exit ≠ 0 | | |
| A1 | reconcile is a fixpoint | 0 writes on run 2 | | |
| A2 | cold rebuild is byte-identical | diff empty | | |
| A4 | edit-to-artifact latency | p50 ≤ 400 ms, max ≤ 2 s | | |
| A5 | one edit → one **render**, and the echo was seen | 1 render, wake-ups > renders | | |
| A6 | a hand-edited artifact is repaired | ≤ 20 s | | |
| A7 | kill -9 leaves a recoverable tree | shas equal | | |
| A8 | daemon vs cold process | ratio ≥ 20 | | |
| A9 | size | ≤ 1,200 lines; vs `watch.py`'s 574 | | |
| A10 | idle cost — watcher, not timer | ≤ 20 ticks / 60 s | | |
| A11 | a mid-reconcile change is not recorded as done | shas equal | | |
| A12 | latency at 10,000 inputs | ≤ 3,000 ms | | |
| A13 | the no-daemon hook | report p50 and max | | |
| A14 | event loss inside one uptime | converges ≤ 120 s | | |
| A15 | every rule fires live, not just `doc-index` | all rules | | |
| A16 | deleted / corrupt / future manifest | recovers, daemon alive | | |
| S7 | seven refusals are loud | all | | |

**Was a periodic floor needed to pass A14?** YES / NO — if yes, say the
interval, and re-read A10 knowing it.

**Do rule chains matter for real work?** YES / NO — §3.3 refuses them.

## What the guide got wrong
<Every place this document was inaccurate. The most valuable section — it is
what a second attempt starts from.>

## What was harder than expected
## What I did not build, and why

## The decision
1. Does this replace devman for generation work? Yes / No / Partly, because...
2. What would it need before daily use?
3. What did devman have that this lost? Name it; do not hand-wave.
4. Keep it or delete it?
```

### The decision rule

Every gate carries weight. Read them in this order and stop at the first hit.

- **P1 or P2 fails** → the antecedent does not hold for real work. The design is
  not applicable as stated. Record which input escaped the globs. Stop.
- **A1, A2, A11 or A16 fails** → the reconciler is wrong. Nothing downstream is
  interpretable. Fix it or stop; do not read the other gates.
- **A5 or A15 fails** → loop prevention or the trigger map is unsolved. Name the
  layer or the rule that failed.
- **A8 fails (ratio < 20)** → the daemon does not amortize enough to justify
  being a process. **Recommend the hook**, whatever A4 says.
- **A14 needed a periodic floor** → amend the claim's wording, record the
  interval, and read A10 again. A design with a floor has already conceded most
  of the watcher-versus-poller gap.
- **A10 fails** → the daemon is a timer wearing a watcher's name. The concept
  may hold, but the design under test was not built. Recommend a periodic
  `dspike gen` and drop watchfiles.
- **A4 exceeds its bound, or A12 exceeds 3 s** → it works and it is too slow for
  a save loop. Record the tree size at which it broke.
- **A13's hook p50 is within 2 s of A4's daemon p50, and `watcher.py` plus
  `lib.sh` plus gates A5, A7 and A10 exceed 150 lines** → the daemon is not
  earning its complexity. **Recommend the hook.** The concept still holds; the
  daemon is what fails.
- **All gates pass, over 1,200 combined lines** → it works and it did not stay
  small, which was the point. Record what grew.
- **All gates pass, under 1,200 lines** → upheld. Name the first thing it
  should generate for real.

---

## 7. Appendix — verified traps

Every one was hit and fixed on this machine.

| # | Trap | Fix |
|---|---|---|
| T1 | `uv` is not on PATH outside a devenv shell | run gate scripts through `devenv shell` |
| T2 | `uv run --project <other repo>` re-syncs that repo's venv | use a path dependency in your own `pyproject.toml` |
| T3 | `prompt:` is required in `metadata.yml`, with no LLM | add `prompt: {file: prompt.md}` anyway |
| T4 | a broken template vanishes silently — no exception, `len()==0` | assert `len(registry)`; read `registry._catalog.load_errors` |
| T5 | the file named by `prompt.file` need not exist to render | a successful render is not template validity |
| T6 | a non-existent search path is skipped silently, then `TemplateNotFoundError` misattributes the fault | pass an absolute path; check it exists first |
| T7 | extra keys in the model dict are silently ignored | `model_config = ConfigDict(extra="forbid")` |
| T8 | the rendered artifact has **no trailing newline** | write `artifact.rstrip("\n") + "\n"` |
| T9 | `render_from_model` runs **no** artifact validation | call `validate_artifact`; read **both** tuple elements |
| T10 | a `None` at a `{{ }}` site raises `RenderError` wrapping `EscapeError` | guard with `{% if %}`; read `exc.__cause__` to classify |
| T11 | `undefined_behavior='strict'` is hard-coded, and the error text echoes model values | never log a render error with real data at INFO |
| T12 | `import templateer` costs 1,136 ms — 973 ms of it `pydantic_ai` | import once per process; never one process per render |
| T13 | loading a schema writes `__pycache__/` into the template directory | gitignore it, or `PYTHONDONTWRITEBYTECODE=1` |
| T14 | `from_paths` is not recursive | point it at the directory that *directly* holds the templates |
| T15 | `DefaultFilter(ignore_dirs=...)` **overrides** the class list | splat: `(*DefaultFilter.ignore_dirs, ...)` |
| T16 | `debounce` is not a quiet period; `step` is | set `step=300`; `debounce` alone changes nothing |
| T17 | `watch()` re-raises `KeyboardInterrupt` by default | `raise_interrupt=False` for a service loop |
| T18 | if every change is filtered out, the generator yields **nothing** — not an empty set | do not use an empty yield as a heartbeat |
| T19 | `ignore_paths` is a raw `str.startswith` prefix test | add a trailing separator, or `/repo/build` also ignores `/repo/buildkite` |
| T20 | an atomic save appears as `added`, not `modified` | never branch on `Change`; reconcile by hash |
| T21 | the watched path must exist before the watch starts | create directories first, or `FileNotFoundError` |
| T22 | `devenv up` does not run `enterShell` | the process block exports its own `PYTHONPATH` |
| T23 | the venv `bin/` is not on the task runner's PATH | run gates inside `devenv shell` |
| T24 | `devenv tasks run` without `-v` swallows stdout | always `-v` |
| T25 | `templateer check` exits 2 for any markdown template | never wire it as a CI gate for markdown |
| T26 | a rebuilt `TemplateRegistry` picks up an edited `schema.py`; the stale cache is per-`Template`, not `sys.modules` | rebuild the registry; do not restart the process |
| T27 | `sys.addaudithook` cannot be removed once installed | install one hook at process start; clear a shared list per call |
| T28 | `wait_for ... test "$(f)" -eq N` expands `$(f)` once, so the loop retests a constant | use `settle()` |
| T29 | killing `uv run` leaves the daemon running | start the daemon as `python -m dspike.cli`, no wrapper |

---

## 8. Order of work

1. Stage 1, gate S1 — environment; templateer_v2 still clean
2. Stage 2, gate S2 — two templates render with no LLM
3. Stage 3, gates A1, A2, **P1, P2, A11**, A13 — the reconciler and the
   antecedent. **Q1 and Q2 are decided here, before any watcher exists.**
4. Stage 4, gate S4 — the watcher
5. Stage 5, gate S5 — the harness
6. Stage 6, gates A5, A4, A10, A6, A7, A12, A14, A15, A16 — **A10, A13 and A8
   decide Q3**
7. Stage 7, gate S7 — seven loud refusals
8. Stage 8, gates A8, A9 — amortization and size
9. `scripts/demo.sh` — five acts, unattended, re-runnable
10. `SPIKE_RESULT.md` — the verdict, including what this guide got wrong

If you run out of time, stages 1–3 alone answer Q1 and Q2 and are worth
reporting on their own. The watcher is the optional half.

---

## 9. What changed from v1, and why

An adversarial review of v1 found its central gate was not a test.

| v1 | Problem | v2 |
|---|---|---|
| Claim: "reconcile-at-startup makes event delivery a latency concern" | Analytically true — it restates the definition of a pure function. No experiment could return FALSIFIED. | Three questions that can each come back "no" |
| Gate A3 decided the spike | `start_watch` waits for `ready`, which is printed *after* the startup reconcile. A3's first poll always succeeded. It tested statement ordering. | A3 removed. P1, P2, A11, A10, A13 decide |
| No gate distinguished the design from `while True: reconcile(); sleep(1)` | That loop passes every v1 gate, and is *smaller*, so it passes the size gate more easily | **A10** (idle CPU) and A4's threshold |
| The alternative considered was the machine-wide design | The real alternative is **no daemon** — `gen` in a save hook | **A13** measures it and can recommend it |
| Torn read unhandled | An input changing mid-reconcile pins a hash the artifact was never built from. The output is wrong forever; no restart repairs it. | §3.7 guard, **A11** |
| Purity assumed | The collectors were rigged pure by construction, so the antecedent was never tested | **P1**, **P2**, §3.6 |
| Four refusals | Two rules on one output ping-pong without end | Seven refusals, plus error isolation |
| Four-file test tree | Measured: 10,000 files cost ~230 ms per hash pass — a floor under every edit | **A12** |
| A5 used `wait_for ... test "$(reconciles)" -eq N` | Command substitution expands once; the loop retested a constant. Measured: exited in 5 ms and would pass an infinite loop | `settle()`, plus a skip-count assertion |
| `cleanup` killed `uv run` | The daemon is a child of the wrapper and survives | daemon started with no wrapper |
| Six of ten gates had no weight in the verdict | A4 could be 8 s and the spike still reported "upheld" | every gate appears in the decision rule |
| A2's golden was made by the tool it certifies | The agent would run `gen`, copy the output, diff it against itself — restating A1 and unable to catch a wrong-but-stable render | golden rendered in **stage 2**, before `reconcile.py` exists |
| Nothing covered event loss *inside* one uptime | Startup reconcile only covers restarts. An inotify overflow leaves a week-long daemon wrong for a week | **A14**, and the periodic floor named as an allowed remedy |
| Only `doc-index` was ever driven live | A broken trigger map for `src/**/*.py` passes every other gate, because A7 re-runs a full `gen` first | **A15**, driven off `rules.toml` |
| Manifest damage unhandled | A `JSONDecodeError` kills the daemon; `git clean -x` in another terminal is enough | §3.5 treats missing/corrupt/future as empty; **A16** |
| Torn read handled by hash-collect-rehash | Detects the window rather than removing it, and the collector could still re-read | **read each input's bytes once**; §3.7 |
| A8 had no threshold | The guide called it "the daemon's actual justification" and then let any number pass | ratio ≥ 20, and a decision branch |
| **v2 matched batches against *expanded* inputs** | A hand-corrupted `docs/INDEX.md` then mapped to no rule, so **gate A6 was unpassable**. Confirmed: `PurePath("docs/INDEX.md").full_match("docs/**/*.md")` is `True`, so matching literal globs is what makes A6 work | stage 4 req 4 matches literal `inputs` globs; expansion still excludes outputs |
| **v2's A5 counted wake-ups** | The daemon correctly wakes on its own output write and renders nothing. Counting wake-ups scored that healthy wake as a loop, so a correct implementation failed A5 | `renders()` counts non-empty `written`; A5 also asserts wake-ups > renders, which tests layer 3 |
| **v2's S5 measured `cleanup`, not the daemon** | `cleanup` escalates to `SIGKILL` and `rm -f`s the pid file, satisfying both assertions itself. Measured: a `SIGTERM`-deaf daemon passed, after `cleanup` spent 5,404 ms killing it | `gate_s5.sh` signals directly and asserts all three clauses of requirement 7 before `cleanup` can act |
| A9 compared against devman's full 8,358 lines | §1 excludes the registry, `run.py`, `doctor.py` and all Nix — the bulk of that count | fair baseline is `watch.py`'s 574 lines |
| **v2 said `validate_artifact` costs 0.021 ms** | It costs that because it validates nothing. `markdown` has no parser in Templateer, so the call returned `([], [])` for garbage and for the empty string, and every reconciler guard built on it was dead code | §2.1 states the hole, and the checker is declared in `rules.toml` and called in process — 0.83 ms, against 49.5 ms for the same check as a `command` validator |
| **v2 wrote `manifest.json.tmp`, one shared name** | Atomic against a reader, not against a second writer. Measured over 24 concurrent `gen` processes: 21 exited 0, 2 exited 1, and 1 exited 2 with `FileNotFoundError` on the shared temporary | §3.5 names the temporary per process; 48 of 48 then exited 0 |
| **v2 printed `ready` before entering the watch loop** | `watchfiles.watch` registers its watches when iteration begins. Measured: two of two runs that edited immediately after `ready` lost the edit for the whole uptime | stage 4 req 2 prints from inside the first iteration, with `yield_on_timeout=True`. **Not** with a confirming reconcile — A10 refuses that |
| **v2's batch match had one clause, for inputs only** | A rule is never woken by a change to the output it owns unless the output happens to sit inside its own input glob. `docs/INDEX.md` does, so A6 passed by that accident. Measured on outputs under `generated/`: a hand edit went unrepaired for 30 s | stage 4 req 4 adds `rule.output in changed` as a second clause |
