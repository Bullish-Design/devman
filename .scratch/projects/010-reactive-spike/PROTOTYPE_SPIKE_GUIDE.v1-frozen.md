# PROTOTYPE_SPIKE_GUIDE — the reconciler spike

A build guide for an agent. Follow it top to bottom. Every stage ends in a gate
that passes or fails by exit code, not by judgement.

---

## 0. Read this first

**You are the implementing agent.** This guide is written for you to execute
without a person present. It gives you the claim to test, the exact prior art
you must not re-derive, the build order, the gates, and the verdict form.

**The spike is disposable.** It exists to answer one question. Write it to be
read and thrown away, not to be maintained.

### Ground rules

1. **Build in `~/Documents/Projects/devman-spike`.** Create it. It is a new git
   repository and it is the only tree you write to.
2. **Never write to `~/Documents/Projects/devman` or
   `~/Documents/Projects/templateer_v2`.** Read them freely. After every stage,
   run `git -C ~/Documents/Projects/templateer_v2 status --porcelain` and
   confirm it is empty. If it is not, you broke rule 2 — restore it and record
   what did it.
3. **Do not run `uv run --project ~/Documents/Projects/templateer_v2 ...`.** It
   re-syncs that project's venv. Measured: `Uninstalled 5 packages / Installed
   5 packages`. It is a write.
4. **No network.** No LLM calls. The whole spike renders from plain data.
5. **Stop at a failed gate.** Do not work around it. A failed gate is a result.
   Record it in `SPIKE_RESULT.md` and stop.
6. **Never make a gate pass by making it check less.** If a gate is wrong,
   write down why in `SPIKE_RESULT.md` and stop.

### Sizing

Target 500–700 lines of Python, everything included. Today's devman is 3,923
lines of Python plus 4,435 lines of Nix. If the spike passes 1,200 lines of
Python, stop and record that the concept did not stay small — that is a real
result and it is the one this spike most needs to catch.

---

## 1. The claim under test

> **For generation whose output is a pure function of tracked inputs,
> reconcile-at-startup makes event delivery a latency concern, not a
> correctness concern.**

If that claim holds, a per-repository `devenv` process is sufficient, and the
machine-wide watcher, the registry, the Nix projection, the systemd units and
the workflow engine are all unnecessary for this workload.

If the claim fails, the machine-wide design was right and the spike ends.

### What decides it

Gate **A3** in stage 6. Stop the daemon, change an input while it is down,
start it again, and change nothing else. The artifact must become correct.

Everything else in this guide is scaffolding for that one test.

### Explicitly out of scope

Do not build these. They are the machine-wide design's problems and they do not
apply to a per-repository process:

- multi-repository ownership (devman's `deepest()` rule, 009 P1-4)
- a registry, a projection, or any Nix module beyond a `devenv.nix`
- a workflow engine, a DAG, retries, run history, or Dagu
- an HTTP, SSE or WebSocket server
- an event-bus abstraction over more than one event source
- LLM generation

---

## 2. Prior art — verified facts, do not re-derive

Everything in this section was measured on this machine. Trust it. If something
contradicts it at build time, record the contradiction in `SPIKE_RESULT.md`.

### 2.1 templateer_v2 — the LLM-free render path

Two calls, both synchronous. Verified with `OPENAI_API_KEY` and
`ANTHROPIC_API_KEY` unset:

```python
from templateer import TemplateRegistry

registry = TemplateRegistry.from_paths(["templates"])   # list is REQUIRED
artifact = registry.render_from_model("release-note", {"heading": "Hi", "summary": "..."})
errors, warnings = registry.validate_artifact("release-note", artifact, model_data=data)
```

`TemplateRegistry` is one of four public names in `templateer.__init__`
(`FailureReason`, `GenerationRequest`, `GenerationResult`, `TemplateRegistry`).

Measured cost:

| Step | Time |
|---|---|
| `import templateer` | **1,136 ms** (973 ms of it is `pydantic_ai`) |
| `from_paths` | 1.0 ms |
| first render | 1.19 ms |
| warm render | **0.127 ms** |
| `validate_artifact` | 0.021 ms |

**The import is roughly 9,000 warm renders.** This is the empirical case for a
daemon: it is not about latency of the render, it is about not paying 1.1
seconds of LLM-SDK import per invocation. Stage 8 measures exactly this.

### 2.2 templateer_v2 template layout

A template is a directory holding `metadata.yml`, a schema module, and a
MiniJinja file. Verified minimal working example:

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
  file: prompt.md               # REQUIRED KEY even with no LLM (see trap T3)
```

```python
# templates/<name>/schema.py
from pydantic import BaseModel, ConfigDict, Field


class MyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")   # see trap T7
    heading: str = Field(description="...")
```

`template.j2` receives `model.model_dump(mode="json")`. `undefined_behavior` is
hard-coded to `strict`, so any name drift is a hard `RenderError`.

### 2.3 watchfiles 1.2.0

Installed on this machine at version 1.2.0. `nixpkgs` has 1.1.1 as
`python3Packages.watchfiles` — there is no top-level attribute. Its only
dependency is `anyio`.

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
Measured: 12 writes 50 ms apart produced **6 separate yields** at defaults, and
**1 yield** with `step=500`.

Use these settings, and say in a comment why:

```python
for changes in watch(
    root,
    watch_filter=my_filter,
    step=300,               # the real quiet period; coalesces an editor save burst
    debounce=1_600,         # hard cap on group growth
    rust_timeout=1_000,     # bounded, so stop_event is noticed within ~1 s
    stop_event=stop,        # anything with .is_set(): threading.Event works
    raise_interrupt=False,  # return instead of re-raising KeyboardInterrupt
):
    ...
```

### 2.4 devenv conventions on this machine

- `devenv` 2.1.2. Python 3.13, pinned through the `nixpkgs-python` input.
- `languages.python.uv.enable = true` **installs nothing.** Only
  `uv.sync.enable = true` runs `uv sync` on shell entry.
- **`devenv up` does not run `enterShell`.** A process must export what it
  needs itself.
- The venv `bin/` is on the interactive shell's PATH but **not** on the task
  runner's PATH. Tasks say `uv run ...`, never a bare `pytest`.
- `devenv tasks run` needs `-v`, or the task's stdout is swallowed and the log
  holds only `{}`.
- Inside a Nix `''` string, a shell variable needs `''$`:
  `''${PORT:-8080}`.
- A `processes.<name>` entry also appears as the task `devenv:processes:<name>`.
- **`uv` may not be on your PATH.** Measured: `which uv` fails outside a devenv
  shell. Run everything from inside `devenv shell` in the spike directory,
  which puts `pkgs.uv` on PATH.

### 2.5 devman mechanics worth carrying

Carry these three. They are bought knowledge. Leave the rest.

**Glob matching** — `PurePath.full_match`, never `fnmatch`, on the path
relative to the repository root (`src/devman/watch.py:544`):

```python
if any(PurePath(rel).full_match(g) for g in globs):
    ...
```

**The ignore list** (`src/devman/watch.py:70-78`), verbatim:

```python
DEFAULT_IGNORES = (
    "**/.devman/.runs/**",
    "**/.git/**",
    "**/.devenv/**",
    "**/.direnv/**",
    "**/.venv/**",
    "**/__pycache__/**",
    "**/node_modules/**",
)
```

**A hash, not a timer** (`groups/format/README.md:70`). devman breaks its
format loop with a content hash, and records why:

> "Edit `foo.py` a second after the formatter wrote it and the hash differs, so
> the work runs. A suppression window would swallow that edit and would still
> pass a naive 'one save, one run' test."

The spike inherits this rule. **Never add a suppression window.** Gate A5 tests
for one.

---

## 3. What the spike builds

### 3.1 The shape

```
devman-spike/
├── devenv.nix
├── devenv.yaml
├── pyproject.toml
├── .gitignore
├── .devman/
│   ├── rules.toml            # the trigger map
│   └── manifest.json         # derived; gitignored
├── templates/
│   ├── doc-index/            # metadata.yml, schema.py, template.j2, prompt.md
│   └── module-table/
├── docs/
│   ├── INDEX.md              # GENERATED, and inside the watched tree on purpose
│   ├── one.md
│   └── two.md
├── src/dspike/
│   ├── __init__.py
│   ├── rules.py              # load and validate .devman/rules.toml
│   ├── collect.py            # the collectors named by rules.toml
│   ├── manifest.py           # hashing and the manifest file
│   ├── reconcile.py          # THE CORE — everything else is a caller
│   ├── watcher.py            # watchfiles loop, calls reconcile
│   └── cli.py                # gen | watch | status
├── tests/
├── scripts/
│   ├── lib.sh                # wait_for, daemon start/stop
│   └── demo.sh
└── SPIKE_RESULT.md
```

### 3.2 The rule model

`.devman/rules.toml` is the whole configuration:

```toml
# One table per rule. The name is the table key.
[doc-index]
inputs  = ["docs/**/*.md"]
output  = "docs/INDEX.md"
template = "doc-index"
collect = "dspike.collect:doc_index"

[module-table]
inputs  = ["src/**/*.py"]
output  = "docs/MODULES.md"
template = "module-table"
collect = "dspike.collect:module_table"
```

A collector is `(root: Path, files: list[Path]) -> dict`. It returns the model
data. That is the only extension point, and it is deliberately Python rather
than more TOML: a spike should not grow a configuration language.

`rules.py` must **refuse** to load, with a message naming the file and the
fault, when:

- a key other than `inputs`, `output`, `template`, `collect` appears
- `collect` does not resolve to a callable
- `template` is not in the registry
- **any rule's `output` matches any rule's `inputs` glob** — see 3.3

Follow devman's refusal style: name the file, state what is wrong, state the
legal shape. Never default silently.

### 3.3 Loop prevention — three layers, and why three

**Layer 1, structural.** A rule's output is never any rule's input. Checked at
load, refused loudly. `docs/INDEX.md` matches `docs/**/*.md`, so
`rules.py` must reject the naive spelling and force the author to write
`inputs = ["docs/**/*.md"]` *with the output excluded*. Implement the exclusion
inside input expansion: drop any path equal to any rule's output. Then the
check above becomes "no rule output survives input expansion", which is
testable.

**Layer 2, the hash.** Reconcile is a fixpoint. It renders only when the input
hash differs from the manifest. A second reconcile writes nothing.

**Layer 3, the write.** After writing an output, record its hash. The
filesystem event that write produces reaches reconcile, which finds nothing
stale and does nothing.

Layer 1 alone would be enough here. Layers 2 and 3 exist because layer 1 is the
one an author can break by editing a glob, and because layer 2 is what makes the
core claim true. **Do not add a fourth layer that suppresses events by time.**

### 3.4 The manifest

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
`(relative_path, sha256(content))` pairs. A rename therefore changes it, and a
touch without an edit does not.

**A rule is stale when** the input hash differs, **or** the output is missing,
**or** the output's hash on disk differs from `output_hash`. The third clause is
what repairs a hand-edited artifact. Gate A6 tests it.

Write the manifest atomically: write `manifest.json.tmp` in the same directory,
then `os.replace`. Gate A7 kills the daemon and requires the manifest to still
parse.

### 3.5 The core function

Everything routes through one function. `gen`, `watch`, and every test call it.

```python
def reconcile(root: Path, rules: list[Rule], registry: TemplateRegistry,
              only: list[str] | None = None) -> ReconcileReport:
    """Bring every stale output up to date. Idempotent."""
```

`ReconcileReport` carries `written: list[str]`, `skipped: list[str]`,
`errors: list[tuple[str, str]]`, and `duration_ms: float`. `gen` prints it and
exits non-zero when `errors` is non-empty.

`only` is a latency optimization for the watcher, and nothing else. **The
watcher must never be the only path that can produce a correct tree.**

---

## 4. Build order

Each stage ends in a gate. Run it. Record the real output in
`SPIKE_RESULT.md`. Do not start the next stage until the gate passes.

### Stage 1 — the environment

Create the repository, `pyproject.toml`, `devenv.yaml`, `devenv.nix`,
`.gitignore`. Take templateer_v2 as a **non-editable** path dependency, so
nothing is written into its source tree:

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
templateer = { path = "../templateer_v2" }   # NOT editable — see ground rule 2

[tool.pytest.ini_options]
pythonpath = ["src"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

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

  # `devenv up` does not run enterShell, so the process exports its own PATH.
  # `exec` replaces the shell, so devenv's signals reach the daemon directly.
  processes.dspike-watch.exec = ''
    export PYTHONPATH="$DEVENV_ROOT/src''${PYTHONPATH:+:$PYTHONPATH}"
    exec uv run dspike watch --root "$DEVENV_ROOT"
  '';

  tasks = {
    "dspike:gen".exec   = "uv run dspike gen";
    "dspike:check".exec = "uv run --extra dev ruff check .";
    "dspike:test".exec  = "uv run --extra dev pytest";
  };
}
```

`.gitignore` must hold `.devman/manifest.json`, `.devenv/`, `.venv/`,
`__pycache__/`, and `templates/*/__pycache__/` — loading a schema runs
`exec_module`, which writes a `.pyc` beside the template (trap T13).

**Gate S1**

```bash
cd ~/Documents/Projects/devman-spike
devenv shell --  python -c "import templateer, watchfiles; print('ok', watchfiles.version.VERSION)"
git -C ~/Documents/Projects/templateer_v2 status --porcelain   # MUST be empty
```

### Stage 2 — the templates

Write both templates. Then prove they render with no LLM, no daemon, and no
`dspike` code at all:

**Gate S2**

```bash
devenv shell -- env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY python -c "
from templateer import TemplateRegistry
r = TemplateRegistry.from_paths(['templates'])
assert len(r) == 2, (len(r), r._catalog.load_errors)   # trap T4: silent skip
print(r.render_from_model('doc-index', {'title':'T','entries':[{'path':'a.md','heading':'A'}]}))
"
```

The `assert` is mandatory. A template that fails to load **vanishes silently** —
no exception, `len(registry) == 0`, and the only trace is
`registry._catalog.load_errors`, which has no public accessor.

### Stage 3 — `reconcile` and `gen`, with no watcher

Write `rules.py`, `collect.py`, `manifest.py`, `reconcile.py`, and a `cli.py`
with `gen` and `status` only. **Do not write the watcher yet.** The reconciler
is the product; the watcher is an optimization over it.

**Gate A1 — the fixpoint**

```bash
rm -f docs/INDEX.md docs/MODULES.md .devman/manifest.json
devenv shell -- uv run dspike gen --json > /tmp/g1.json ; echo "exit=$?"
devenv shell -- uv run dspike gen --json > /tmp/g2.json ; echo "exit=$?"
python -c "
import json
a=json.load(open('/tmp/g1.json')); b=json.load(open('/tmp/g2.json'))
assert a['written'], 'first run wrote nothing'
assert b['written'] == [], f'NOT A FIXPOINT: second run wrote {b[\"written\"]}'
assert not a['errors'] and not b['errors']
print('A1 PASS', a['written'])
"
```

**Gate A2 — cold correctness.** Delete the outputs, run `gen`, and diff against
a golden copy you made by hand. The artifact must be byte-identical.

Note trap T8: `render_from_model` returns a string with **no trailing
newline**. Write `artifact.rstrip("\n") + "\n"` or every artifact will carry
`\ No newline at end of file`.

### Stage 4 — the watcher

Write `watcher.py` and `cli.py`'s `watch` subcommand. Requirements:

1. **Reconcile once at startup, before watching.** This is the claim under
   test. Log the report.
2. Then print exactly `dspike watch: ready` on stdout, flushed, and write
   `.devman/watch.pid`. The harness in stage 5 waits on that line.
3. Watch `root` with `step=300`, `rust_timeout=1000`, `stop_event`,
   `raise_interrupt=False`.
4. Filter with a `DefaultFilter` subclass carrying `DEFAULT_IGNORES` from 2.5.
   **Splat the parent list** — `ignore_dirs=(*DefaultFilter.ignore_dirs, ...)` —
   because the keyword *overrides* the class list rather than extending it
   (trap T15).
5. On a batch: map changed paths to rules by `PurePath(rel).full_match`, then
   call `reconcile(only=[...])`.
6. Log one JSON line per reconcile to `.devman/watch.log`:
   `{"at":..., "trigger":[...], "written":[...], "duration_ms":...}`.
   Gate A5 counts these lines.
7. On `SIGTERM` and `SIGINT`: set `stop_event`, remove the pid file, exit 0.

**Gate S4**

```bash
devenv shell -- uv run dspike watch --root . --once-then-exit
```

Add `--once-then-exit` so the daemon can be started, do its startup reconcile,
and exit. It makes stages 5 and 6 testable without process management.

### Stage 5 — the autonomous harness

This is the part that makes the spike runnable with nobody present. Write
`scripts/lib.sh` exactly as below. It is correct; do not improvise a
replacement.

```bash
# scripts/lib.sh
set -euo pipefail

ROOT="${ROOT:-$PWD}"
LOG="$ROOT/.devman/watch.log"
OUT="$ROOT/.devman/watch.stdout"
WATCH_PID=""

cleanup() {
  if [ -n "$WATCH_PID" ] && kill -0 "$WATCH_PID" 2>/dev/null; then
    kill -TERM "$WATCH_PID" 2>/dev/null || true
    for _ in $(seq 1 50); do
      kill -0 "$WATCH_PID" 2>/dev/null || break
      sleep 0.1
    done
    kill -KILL "$WATCH_PID" 2>/dev/null || true
  fi
  WATCH_PID=""
}
trap cleanup EXIT INT TERM

# wait_for <timeout_seconds> <description> <command...>
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
  : > "$OUT"
  : > "$LOG"
  uv run dspike watch --root "$ROOT" > "$OUT" 2>&1 &
  WATCH_PID=$!
  wait_for 60 "daemon ready" grep -q 'dspike watch: ready' "$OUT" \
    || { echo "--- daemon stdout ---"; cat "$OUT"; return 1; }
}

stop_watch() { cleanup; }

# Number of reconcile lines the daemon has logged.
reconciles() { [ -f "$LOG" ] && wc -l < "$LOG" || echo 0; }
```

Two notes for you as the executing agent:

- **Run these as scripts, not as bare shell calls.** Do not issue a foreground
  `sleep` as a command of its own; the polling belongs inside `wait_for`.
- **Every wait has a deadline.** A hung daemon must fail the gate in bounded
  time, not stall the run.

**Gate S5** — start the daemon, confirm ready, stop it, and confirm the process
is gone and the pid file is removed.

### Stage 6 — the claim

**Gate A3 — missed-event immunity. This is the spike.**

```bash
# scripts/a3_missed_event.sh
source scripts/lib.sh

uv run dspike gen                       # start correct
git add -A && git stash list >/dev/null # (no-op; keeps the tree explicit)

# 1. Daemon is DOWN. Nothing is watching.
echo "# Three" > docs/three.md          # an input changes with no observer
grep -q 'three' docs/INDEX.md && { echo "A3 SETUP BROKEN"; exit 1; }

# 2. Start the daemon. Change NOTHING else.
start_watch

# 3. The artifact must become correct on its own.
wait_for 20 "INDEX.md to pick up the missed change" grep -q 'three' docs/INDEX.md \
  || { echo "A3 FAIL — reconcile-at-startup did not repair a missed event"; exit 1; }

echo "A3 PASS"
stop_watch
```

**If A3 fails, stop the spike.** Record it. The claim is false and the
machine-wide design was right.

**Gate A4 — latency.** Daemon up. Ten edits, each measuring milliseconds from
`write` to the artifact containing the new content. Report p50 and max. Use a
per-edit `wait_for` with a 20 s deadline, and `date +%s%3N` for the stamps.

**Gate A5 — no self-trigger.** Daemon up, log truncated. Make **one** edit.
Wait for the artifact to update. Then wait for the log line count to stop
changing, and assert it is exactly 1.

```bash
before=$(reconciles)
echo "# Four" > docs/four.md
wait_for 20 "artifact update" grep -q 'four' docs/INDEX.md
# Give any second reconcile a chance to appear, then require none did.
wait_for 5 "log to settle" test "$(reconciles)" -eq "$((before + 1))" \
  || { echo "A5 FAIL — $(( $(reconciles) - before )) reconciles for one edit"; exit 1; }
```

Writing `docs/INDEX.md` is itself a change inside `docs/`. If layer 1 or layer 2
is wrong, this gate produces 2, or it never stops.

**Gate A6 — repair of a hand-edited artifact.** Daemon up. Overwrite
`docs/INDEX.md` with `garbage`. The daemon must restore it. This proves the
`output_hash` clause in 3.4.

**Gate A7 — crash safety.** Daemon up. `kill -9` it during a burst of 50 writes.
Then: the manifest still parses as JSON, and one `dspike gen` brings the tree to
the same state as a clean rebuild from scratch.

```bash
# after kill -9 and `dspike gen`
sha_after=$(sha256sum docs/INDEX.md docs/MODULES.md | sha256sum)
rm -f docs/INDEX.md docs/MODULES.md .devman/manifest.json
uv run dspike gen
sha_clean=$(sha256sum docs/INDEX.md docs/MODULES.md | sha256sum)
test "$sha_after" = "$sha_clean" || { echo "A7 FAIL"; exit 1; }
```

### Stage 7 — refusals

The spike must fail loudly on bad configuration. Write a test for each, and
assert on the **exit code and the message**, not just the exit code:

| Input | Required behaviour |
|---|---|
| unknown key in `rules.toml` | exit ≠ 0, message names the file, the key, and the legal keys |
| `collect` that does not resolve | exit ≠ 0, message names the rule and the string |
| `template` not in the registry | exit ≠ 0, message lists the templates that *are* loaded |
| a rule output that survives input expansion | exit ≠ 0, message names both rules |
| a template that fails to load | exit ≠ 0, message quotes `load_errors` |
| a collector returning data that fails validation | exit ≠ 0, message names the rule and the pydantic error |

**Gate S7** — every row has a test and every test passes.

### Stage 8 — the measurements

**Gate A8 — import amortization.** Time these two, ten times each:

1. `uv run dspike gen` with nothing stale — a whole cold process
2. one reconcile inside the running daemon, from `.devman/watch.log`

Report both. Expect roughly 1.2–1.6 s against a few milliseconds. This is the
daemon's actual justification and it should be stated as a number, not a claim.

**Gate A9 — size.**

```bash
find src -name '*.py' | xargs wc -l | tail -1
find . -maxdepth 1 -name '*.nix' | xargs wc -l | tail -1
```

Record both against devman's 3,923 Python and 4,435 Nix.

---

## 5. The demo

`scripts/demo.sh` runs unattended, needs no input, and produces a transcript at
`.devman/demo-transcript.txt`. It must **prove the claim**, not show that
something happened. Structure it in five acts, echoing a heading for each:

1. **Cold build.** Empty tree → `dspike gen` → show the artifacts. Show the
   second `gen` writing nothing.
2. **Live.** Start the daemon. Add `docs/five.md`. Show `INDEX.md` gaining the
   entry, and print the measured latency.
3. **The claim.** Stop the daemon. Add `docs/six.md`. Show `INDEX.md` is now
   *wrong* — print the diff. Start the daemon. Change nothing. Show `INDEX.md`
   is right again. **This is the act that matters.**
4. **Repair.** Overwrite `INDEX.md` with garbage. Show it restored.
5. **Refusal.** Add a bad rule to `rules.toml`. Show `dspike gen` refusing with
   its message and a non-zero exit. Restore the file.

End with a one-screen summary: gates passed, latency p50, LOC, and the verdict.

`demo.sh` must exit 0 only when every act succeeded, and it must call
`cleanup` through the `trap` in `lib.sh` on every exit path.

---

## 6. The verdict

Fill in `SPIKE_RESULT.md`. Do not soften a failure.

```markdown
# SPIKE_RESULT — the reconciler spike

Date: <absolute date>
Commit: <sha>

## The claim

> For generation whose output is a pure function of tracked inputs,
> reconcile-at-startup makes event delivery a latency concern, not a
> correctness concern.

**Verdict: UPHELD | FALSIFIED | INCONCLUSIVE**

Evidence: <the A3 transcript, verbatim>

## Gates

| Gate | What it checks | Result | Evidence |
|---|---|---|---|
| A1 | reconcile is a fixpoint | | |
| A2 | cold rebuild is byte-identical | | |
| A3 | a missed event self-repairs | | |
| A4 | edit-to-artifact latency | p50 __ ms, max __ ms | |
| A5 | one edit, one reconcile | | |
| A6 | a hand-edited artifact is repaired | | |
| A7 | kill -9 leaves a recoverable tree | | |
| A8 | daemon vs cold process | __ ms vs __ ms | |
| A9 | size | __ py / __ nix | vs devman 3923 / 4435 |
| S7 | six refusals are loud | | |

## What the guide got wrong

<Every place this document was inaccurate. This section is the most valuable
one — it is what a second attempt would start from.>

## What was harder than expected

<...>

## What I did not build, and why

<...>

## The decision

Answer all four:

1. Does this replace devman for generation work? Yes / No / Partly, because...
2. What would it need before daily use?
3. What did devman have that this lost? Name it, do not hand-wave.
4. Would you keep it or delete it?
```

### The decision rule

- **A3 fails** → the concept is wrong. Stop. Keep devman as it is.
- **A3 passes, A5 fails** → loop prevention is not solved. The concept may still
  be right; the implementation is not. Record which layer failed.
- **A3 and A5 pass, `src/` is over 1,200 lines** → it works but it did not stay
  small, which was the whole point. Record what grew.
- **A3 and A5 pass, under 1,200 lines** → the concept is upheld. Recommend
  building it for real, and name the first thing it should generate.

---

## 7. Appendix — verified traps

Every one of these was hit and fixed on this machine. They are the difference
between a two-hour spike and a two-day one.

| # | Trap | Fix |
|---|---|---|
| T1 | `uv` is not on PATH outside a devenv shell | run everything through `devenv shell --` |
| T2 | `uv run --project <other repo>` re-syncs that repo's venv | use a path dependency in your own `pyproject.toml` |
| T3 | `prompt:` is a required key in `metadata.yml`, with no LLM | add `prompt: {file: prompt.md}` anyway |
| T4 | a broken template vanishes silently — no exception, `len()==0` | assert `len(registry)`; read `registry._catalog.load_errors` |
| T5 | the file named by `prompt.file` need not exist to render | do not treat a successful render as template validity |
| T6 | a non-existent search path is skipped silently, then `TemplateNotFoundError` misattributes the fault | check the directory exists before `from_paths` |
| T7 | extra keys in the model dict are silently ignored | `model_config = ConfigDict(extra="forbid")` |
| T8 | the rendered artifact has **no trailing newline** | write `artifact.rstrip("\n") + "\n"` |
| T9 | `render_from_model` runs **no** artifact validation | call `validate_artifact` and read **both** tuple elements |
| T10 | a `None` in a `{{ }}` site raises `RenderError`, wrapping `EscapeError` | guard with `{% if %}`, and read `exc.__cause__` to classify |
| T11 | `undefined_behavior='strict'` is hard-coded; the error text echoes model values | never log a render error at INFO with real data in it |
| T12 | `import templateer` costs 1,136 ms — 973 ms of it `pydantic_ai` | import once per process; never one process per render |
| T13 | loading a schema writes `__pycache__/` into the template directory | gitignore it, or set `PYTHONDONTWRITEBYTECODE=1` |
| T14 | `from_paths` is not recursive | point it at the directory that *directly* holds the templates |
| T15 | `DefaultFilter(ignore_dirs=...)` **overrides** the class list | splat: `(*DefaultFilter.ignore_dirs, ...)` |
| T16 | `debounce` is not a quiet period; `step` is | set `step=300`; `debounce` alone changes nothing |
| T17 | `watch()` re-raises `KeyboardInterrupt` by default | `raise_interrupt=False` for a service loop |
| T18 | if every change is filtered out, the generator yields **nothing** — not an empty set | do not use an empty yield as a heartbeat; use `yield_on_timeout=True` |
| T19 | `ignore_paths` is a raw `str.startswith` prefix test | add a trailing separator, or `/repo/build` also ignores `/repo/buildkite` |
| T20 | an atomic save appears as `added`, not `modified` | never branch on `Change`; reconcile by hash |
| T21 | the watched path must exist before the watch starts | create directories first, or `FileNotFoundError` |
| T22 | `devenv up` does not run `enterShell` | the process block exports its own `PYTHONPATH` |
| T23 | the venv `bin/` is not on the task runner's PATH | `uv run ...` in every task |
| T24 | `devenv tasks run` without `-v` swallows stdout | always `-v` |
| T25 | `templateer check` exits 2 for any markdown template | never wire it as a CI gate for markdown |
| T26 | a rebuilt `TemplateRegistry` picks up an edited `schema.py`; the stale cache is per-`Template`, not `sys.modules` | rebuild the registry, do not restart the process |

---

## 8. Order of work, in one list

1. Stage 1, gate S1 — environment, templateer importable, templateer_v2 clean
2. Stage 2, gate S2 — two templates render with no LLM
3. Stage 3, gates A1 and A2 — `reconcile` and `gen`, fixpoint and cold build
4. Stage 4, gate S4 — the watcher, startup reconcile first
5. Stage 5, gate S5 — `lib.sh`, daemon start and stop
6. Stage 6, gates A3, A4, A5, A6, A7 — **A3 is the spike**
7. Stage 7, gate S7 — six loud refusals
8. Stage 8, gates A8 and A9 — amortization and size
9. Stage 5's demo — `demo.sh`, five acts, unattended
10. `SPIKE_RESULT.md` — the verdict, including what this guide got wrong

Commit after every passing gate, with the gate name in the message.
