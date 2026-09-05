# 014 — `devenv tasks run` is the plane's only verb. What it costs, and what it shares.

**The headline: the 1.5 s is not evaluation, and it is not devenv's fault in the
way anybody assumed. It is devenv nar-hashing its own uncollected cache.**

`Validating lock` is 94 % of a warm run. Nix evaluation is 1.8 ms. The lock
validator re-resolves every input on every invocation, and a local `path:` input
carries no revision, so Nix copies and hashes the whole directory — `.devenv`
included, `.gitignore` ignored. devenv's shell-script cache is content-addressed
and **never deleted by anything, including `devenv gc`**. It is 22.9 GB across
54 repositories, and 51 of them take one such directory as an input.

**So there is no warm path to build. There is garbage to remove.** Deleting
`.devenv` from the input drops the verb from 1448 ms to 287 ms, measured — with
no cache, no freshness check, and no law-4 surface at all.

Working trail, with every intermediate figure: [`NOTES.md`](NOTES.md).

---

## 0. How to read the numbers

Every figure states n, the machine state, and what else was running.

**The machine was not quiet, and load average lies here.** The project-012
`find` over sysfs is **still running** — PID 1082086, 17 h of CPU, one core,
permanently. On top of that a llama.cpp Vulkan shader build (dozens of `glslc`)
saturated the other seven cores for the first 12 minutes of this session; load1
was 31.16 at 11:07. **No timing figure below was taken until it finished.**

After it finished, `vmstat 2 4` read `r`=1–3, `b`=0, 70–79 % idle, 27 GB free,
while load1 still read 4–7 because it decays over minutes. **I record load1 with
every figure as the kickoff asks, and I read `vmstat r` for the truth.**

Dagu (`dagu start-all`, 22 h) and `devman watch` were live throughout. The
watcher watches this repository; `.scratch/**` is in its ignore list, so writing
these notes fired nothing. Editing `src/devman/doctor.py` did fire `format`, as
it should, and that is visible in `doctor`'s own watcher section.

---

## 1. Where the 1.5 s goes

### 1.1 The number, re-derived

n=25, devman, warm, quiet machine:

| probe | p50 | min | p90 | max |
|---|---|---|---|---|
| `devenv tasks run` — no tasks, "nothing at all" | **1537.8 ms** | 1434.0 | 1687.9 | 2436.0 |
| `devenv tasks run -m single base:check` | **1730.1 ms** | 1529.6 | 1895.6 | 2280.6 |
| `ruff check .` after `. .devenv/load-exports` | **27.9 ms** | 16.4 | 33.7 | 35.9 |
| `ruff format .` after `. .devenv/load-exports` | **24.6 ms** | 16.5 | 32.4 | 37.2 |
| sourcing `.devenv/load-exports` alone | **3.4 ms** | 2.2 | 4.1 | 11.2 |

**013's ~1550 ms stands: p50 1537.8 ms at n=25.** So does its "the work is 2 %":
27.9 / 1730.1 = **1.6 %**.

### 1.2 The question 013 never asked

`devenv --trace-to` writes a span tree. It emits nothing at the default level —
`create_filter` (`devenv/src/tracing/mod.rs:105`) takes its level from `-v`/`-q`
and `RUST_LOG`, so without `-v` the trace file is empty and silent. With `-v`,
three consecutive warm runs on the quiet machine, in ms:

| span | run1 | run2 | run3 |
|---|---|---|---|
| **Validating lock** | **1640** | **1590** | **1660** |
| dispatch_command | 84.0 | 80.0 | 98.4 |
| — capture_shell_environment | 44.7 | 52.0 | 58.5 |
| — — capture_env_subprocess | 40.1 | 47.5 | 42.5 |
| — — prepare_shell | 4.1 | 4.0 | 15.3 |
| — — — **Evaluating shell** | **2.3** | **1.8** | **1.8** |
| — Loading tasks | 2.0 | 1.9 | 5.1 |
| — run (the task itself) | 27.4 | 18.6 | 22.8 |
| **devenv (total)** | 1740 | 1670 | 1760 |

**Lock validation is 94 % of the run. Nix evaluation is 1.8–2.3 ms.**

This retires a family of 013's leads in one stroke. `--offline`, `--no-reload`
and every eval-cache flag are irrelevant **because the eval cache already hits
and costs 2 ms**. The eval cache was never the problem.

### 1.3 What lock validation does, from the source

`devenv-nix-backend/src/lock.rs:35-45` calls `validate_lock_file` then
`fingerprint` on **every** invocation. `validate_lock_file`
(`devenv-nix-backend/src/lib.rs:363-426`) builds an `InputsLocker` with
`.mode(LockMode::Virtual).use_registries(true)` and calls `.lock(...)`: it
re-resolves every flake input, every run.

A `path:` node has nothing to short-circuit on. The locked entry is literally
`{"path": "/tmp/014/sh-big", "type": "path"}` — **no revision, no narHash** — so
Nix must copy and hash the directory to learn what it is.

### 1.4 The controlled experiment

Five synthetic devenv projects under `/tmp/014`, identical but for their inputs,
one task `probe:noop` whose `exec` is `true`. n=20 each:

| project | its `path:` input | size | p50 | min | max |
|---|---|---|---|---|---|
| L0 | none | — | **146.1 ms** | 111.4 | 246.8 |
| L1 | a tiny dir, `flake: false` | 8 KB | **162.5 ms** | 107.6 | 193.5 |
| L4 | copy of shellij, **`.devenv` deleted** | 29 MB | **286.5 ms** | 249.5 | 321.5 |
| L3 | copy of shellij, **`.devenv` kept** | 298 MB | **1448.1 ms** | 1382.3 | 1999.7 |
| L2 | the live shellij (git, dirty) | 301 MB | **1565.1 ms** | 1419.9 | 1742.6 |
| — | devman itself, `base:check` | 301 MB | 1697.0 ms | 1491.2 | 2251.4 |

**devenv's own startup floor is 146 ms.** Everything above it is the path input.
**Deleting `.devenv` from that input recovers 1161 ms — 80 % of the cost.**

L2 and L3 are the same tree with and without `.git`, and cost the same:
**Nix does not honour `.gitignore` for a `path:` input.** `.devenv` is gitignored
in shellij and is copied regardless.

### 1.5 The proof, not the inference

`/nix/store` holds copies of the **live** shellij — they contain `.git` and
`.jj`, so they are not my `/tmp` copies:

```
/nix/store/0v6fwcpw…-source   294M   .devenv = 265M   2179 shell-*.sh
/nix/store/1ay0ha72…-source   275M   .devenv = 248M   1969 shell-*.sh
```

Sweeping every `-source` path over 50 MB that contains a `.devenv`:
**38 store paths, 18,053 MB.** The largest is 922 MB holding 10,181 shell
scripts.

### 1.6 Why the cache exists at all

`devenv/src/devenv/mod.rs:2163-2172`:

```rust
fn write_executable_script(dir: &Path, content: &str) -> PathBuf {
    let hash = &compute_string_hash(content)[..16];
    let path = dir.join(format!("shell-{}.sh", hash));
    if !path.exists() { std::fs::write(&path, content)...; }
    path
}
```

Content-addressed, called from three places, **and there is no delete path in
the crate**. `devenv gc` does not help: all 85 lines of
`devenv/src/devenv/gc.rs` collect Nix store paths and dangling GC-root symlinks
and never look inside the dotfile.

Measured across all 54 registered repositories:

| | |
|---|---|
| `shell-*.sh` files | **277,950** |
| `shell-*.sh` bytes | **22.89 GB** |
| `.devenv` total | **54.46 GB** |
| shell cache share of `.devenv` | 42.0 % |
| mean script size | 80.4 KiB |

`df -h /home`: 444 G total, **399 G used, 42 G free, 91 %**.
22.89 GB in the repositories plus 18.05 GB duplicated into the store is
**~41 GB against 42 GB of headroom.**

**The chain, every link measured:** devenv never collects its shell cache →
`.devenv` grows without bound → 52 of 54 repositories take a local `path:`
input and 51 take shellij → every `devenv tasks run` copies and hashes that
directory, cache and all → **devenv is slow because of devenv's own garbage.**

---

## 2. What makes a run warm, and what makes it cold

### 2.1 The mechanism

Two caches, and they are not the same thing.

**The shell script cache** (`.devenv/shell-<hash>.sh`) is keyed on the *content*
of the generated environment script. It is a write-if-absent store with no
freshness question: same content, same file.

**The eval cache** (`.devenv/nix-eval-cache.db`, SQLite + WAL) is the one that
decides warm from cold. `EvalCacheKey` (`devenv-eval-cache/src/ffi_cache.rs:42`)
is `hash(serialised NixArgs + attr_name)`. The row stores an `input_hash` over
every file and environment input, plus one row per input.

`validate_inputs` (`devenv-eval-cache/src/caching_eval.rs:228-320`) recomputes
the input hash, then `check_file_state` for every file and `check_env_state` for
every variable. **It is a real freshness check** — it is not a timestamp, and it
is not optional.

### 2.2 What invalidates it, on this repository

The live `shell` entry has **43 file inputs and 6 environment inputs**. The
environment inputs are stable (`DEVENV_CONTAINER`, `HOME`, `SECRETSPEC_SECRETS`,
three `NIXPKGS_ALLOW_*`). The file inputs are not, and this is the finding:

```
devenv.nix  devenv.yaml  devenv.lock  pyproject.toml
groups/*/workflows/*.yaml   groups/*/triggers.toml   nix/*.nix
src/devman/__init__.py  cli.py  doctor.py  project.py  registry.py
src/devman/run.py  show.py  watch.py  workflow.py
src/devman/__pycache__          <- a DIRECTORY input
```

**Every Python source file in this repository is an input to the shell
evaluation.** So is `src/devman/__pycache__`.

For a directory the eval cache hashes the sorted list of its *immediate child
paths* (`eval_inputs.rs:197-202`) — names only, non-recursive. So rewriting a
`.pyc` does not invalidate, but **adding one does**, and `pytest` adds one
whenever a module appears.

Note this is a *second* directory-hash function: `devenv-cache-core`'s
`compute_directory_hash` is recursive and includes content. Two subsystems, two
answers. Only the eval-cache one matters here.

### 2.3 What cold costs

n=10 each, quiet machine (load1 2.18 at start):

| probe | p50 | min | max |
|---|---|---|---|
| `--refresh-eval-cache -m single base:check`, devman | **9186.8 ms** | 8596.3 | 9652.7 |
| warm control, same command without the flag | 1662.9 ms | 1533.0 | 2091.6 |
| `--refresh-eval-cache`, L0 (no `path:` input) | 1482.6 ms | 1299.9 | 1621.9 |

**A cold run in this repository is 9.2 s — 5.5× warm.** Without a `path:` input
it is 1.48 s, so the input costs ~7.7 s on the cold path too.

And a real invalidation is worse than the flag. Single runs, in sequence:

| | |
|---|---|
| warm | **1715 ms** |
| after `touch src/devman/__pycache__/probe014.cpython-313.pyc` | **13907 ms** |
| the run after that | **2059 ms** |

**One new `.pyc` — which running `pytest` creates as a matter of course — makes
the next `devenv tasks run` in the same repository 8× more expensive.** The
probe file was removed; `git status` is clean.

### 2.4 The nightly case the kickoff asked about

**It does not exist, and this corrects the kickoff.** Reading `schedule:` out of
all 170 projected files:

| workflow | files | schedule |
|---|---|---|
| maintain | 54 | `5 0 * * *` |
| plane-report | 1 | `20 0 * * *` |
| **check, test, format, release, everything else** | **114** | **none** |

**`check` and `test` are not nightly. Nothing scheduled runs the verb at all**
— `maintain` and `plane-report` are the only scheduled workflows and both run
plain shell. So "a nightly `check` on a repository nobody has entered for a
month" is not a case the plane has. What it has instead is `format`, fired by a
save, in the one repository that takes the `format` group.

**And `format` is the worst case, not the best.** It fires on a `.py` save; a
`.py` save invalidates the eval cache (§2.2); so the workflow triggered by an
edit is the one guaranteed to run cold.

---

## 3. What the verb shares

### 3.1 The enumeration

| path | what it is | written when | collected |
|---|---|---|---|
| `.devenv/shell-<hash>.sh` | the realised environment, ~80 KiB each | a new environment | **never, by anything** |
| `.devenv/nix-eval-cache.db` (+`-wal`,`-shm`) | SQLite WAL: `cached_eval`, `file_input`, `eval_input_path`, `eval_env_input`, `eval_resource_spec` | every eval | rows deleted on invalidation |
| `.devenv/state/tasks.db` (+`-wal`,`-shm`) | SQLite WAL: `task_run`, `watched_file` | **every successful task** | `cleanup_stale_files` only |
| `.devenv/state/venv` | the uv virtualenv | `devenv:python:virtualenv` | no |
| `.devenv/run` | symlink to `/tmp/devenv-<7 hex>` | shell entry | per boot |
| `.devenv/profile`, `.devenv/gc` | GC roots | build | `devenv gc` |
| `.devenv/load-exports`, `input-paths.txt`, `task-names.txt`, `imports.txt` | flat metadata | shell entry | overwritten |

`/tmp/devenv-<hex>` is `runtime_base.join(format!("devenv-{}", &hex[..7]))`
(`devenv-processes/src/lib.rs:34`) — a hash of the dotfile path, so it is
**stable per project** and does not vary per session. It is not a source of
cache misses.

### 3.2 Every successful task writes `tasks.db`

`devenv-tasks/src/task_state.rs:617-633` runs, on success:

```rust
if result.success {
    let expanded_paths = find_files_matching_patterns(&self.task.exec_if_modified);
    for path in &expanded_paths { cache.update_file_state(&self.task.name, path).await?; }
    cache.cleanup_stale_files(&self.task.name, &expanded_paths).await?;
    if let Some(cmd) = &self.task.command {
        cache.update_file_state(&self.task.name, cmd).await?;   // <- unconditional
    }
}
```

The last line is **outside** the `exec_if_modified` check. So every successful
task writes one `watched_file` row naming its own script's store path, whether
or not it caches anything. The live database agrees exactly — 9 rows, one per
task, every `path` a store path, every `modified_time` 1:

```
base:check    /nix/store/ppxd5hxh…-base-check     1  2336244aae8a
base:test     /nix/store/d0b1v2fl…-base-test      1  7c583f798f7a
format:fmt    /nix/store/cg5jmkpp…-format-fmt     1  7399217aa63f
```

This is what 013 saw as `Removing stale watched_file entry … Updating file state
for task`, and it appeared again in this session's own `base:unit` run. It is
harmless — store paths are immutable — but it is the write two concurrent
invocations would collide on.

### 3.3 The concurrency experiment

**No collision, at any concurrency I could produce.**

| experiment | result |
|---|---|
| 6 distinct tasks × 10 rounds, one repository, one `tasks.db` | 60/60 executed, **all rc=0**, 0 bytes of stderr, no `database is locked` |
| **16-way concurrent, same task**, × 6 rounds | 96/96 executed, **all rc=0**, no stderr, `pragma integrity_check` = `ok` |
| two tasks sharing one `exec_if_modified` file, concurrently | both ran, both rc=0, integrity `ok` |

`watched_file` is `UNIQUE(task_name, path)` and the write is a single upsert, so
two tasks watching one file keep separate rows and cannot interfere.
**Classified: no self, sibling, cross-workflow or resource collision on
`tasks.db`.** 013 found no sibling collision by reading workflow bodies; I
looked at the shared file it could not see, and there is none there either.

**The one shared thing that does hurt is not a lock — it is the 22.9 GB.**

---

## 4. Does `exec_if_modified` have the defect 013 found in `format`?

**Yes. Confirmed from the source and reproduced.** And **the plane's exposure is
zero**, because nothing sets it.

### 4.1 From the source

The receipt in §3.2 is written **after** `executor::execute` returns, by
re-stat'ing the files at that moment. `update_file_state` calls
`TrackedFile::new(path)` (`devenv-cache-core/src/file.rs:37-60`), which computes
a **blake3 hash of what is on disk now**. The glob is re-expanded afterwards
too, so a file the task created also gets a receipt.

So a file edited after the command last read it, but before the command exits,
has its **post-edit** hash written as the receipt. The next run compares against
that hash, finds no change, and returns
`TaskCompleted::Skipped(Skipped::Cached(..))` (`task_state.rs:565-579`).

**`format`'s fixpoint does not close this.** The fixpoint makes the task
idempotent; the window is between the command's last read and
`update_file_state`, and nothing inside the task can shorten it.

### 4.2 Reproduced

A task that reads early and exits late — the shape of every linter and
formatter:

```nix
tasks."probe:watch" = {
  exec = "cat data/target.txt >> data/seen.log\nsleep 3";
  execIfModified = [ "data/target.txt" ];
};
```

| step | result |
|---|---|
| set `target` = `D`, run it, set `target` = `E` at t=1.5 s | `seen.log` = `C D` |
| run again | `seen.log` = `C D` — **skipped** |
| run again | `seen.log` = `C D` — **skipped** |

`target.txt` holds `E`. The task never saw `E`, and no further run will ever
process it. Exit 0 every time, no warning.

**The discriminator, to rule out coincidence:** set `target` back to `D` — the
content the task really did process. A correct receipt would hold `hash(D)` and
skip. It ran, and appended `D`. So the stored receipt was `hash(E)`: content the
task never read. **A successful run that did the wrong thing — law 4, exactly.**

### 4.3 Exposure

I walked every `*.nix` in all 54 registered repositories, skipping `.git`,
`.devenv`, `node_modules`, `.venv`, `target` and `.stage`. **`execIfModified`
appears zero times.** The only occurrence anywhere is devenv's own
`devenv.nix:144`, upstream.

**So this is a real, confirmed, silent defect with no live exposure. It becomes
live the moment any repository adds `execIfModified`** — and the natural reason
to add it is to make `check` cheaper, which is exactly what this project's
findings might tempt somebody to do. That is worth writing down before somebody
does it.

Note the asymmetry, because it decides whether upstream can fix it: for a
**mutating** task like `format`, the receipt *must* be taken after, or the task
would re-run forever. For a **read-only** task like `check`, taking it before
would be correct. devenv takes it after in both cases.

---

## 5. The warm-path verdict

**No warm path should be built. The question was the wrong shape.**

A warm path caches the *result* of expensive work. Here the expensive work is
not work at all — it is Nix hashing 269 MB of dead files that devenv itself
wrote and will not delete. **Remove the garbage and the verb costs 287 ms with
no cache in it.**

Against Part C's three tests, for completeness:

| test | a devenv-caching warm path | **removing the garbage** |
|---|---|---|
| **keeps ordering in the repository** | yes if it still calls `devenv tasks run <task>` | **yes — nothing changes at all** |
| **has a freshness check** | devenv's eval cache already has a real one (§2.1) — but it is not what costs the time, so caching harder wins nothing | **not applicable: no cache is added, so nothing can be stale** |
| **`doctor` can see it** | would need a new invariant | **yes — shipped, §7** |

**What kills every warm path I considered** is the same fact: the eval cache
already hits, in 1.8 ms. There is no evaluation left to cache. `--offline`,
`--no-reload`, a `base.yaml` `default_shell` warm-up, and a persisted
`load-exports` all attack a cost that is 8 % of the run. The 013 lead
`. .devenv/load-exports && ruff format .` measures 3.4 + 24.6 = **28 ms**, which
is a bound on a warm path's prize — but it also **bypasses the task graph
entirely**, which is law 5, so it was never a candidate and is not one now.

**Do nothing to the plane's invocation shape.** One `devenv tasks run` per step
stays. What changes is that `doctor` now says why it is slow.

---

## 6. Criterion 14 — can it be checked?

### 6.1 Is it violated today? No, and this is measured

Parsing all 170 projected files with PyYAML:

| | |
|---|---|
| files / steps | 170 / 175 |
| files containing `devenv tasks run` | **113** |
| textual verb calls | **114** |
| files with more than one step | 3 (`devman/release`, `devman/stack-validate`, `observantic/release`) |
| **files running the verb more than once** | **0** |
| **steps declaring `depends`** | **0** |
| files with `type: chain` | 6 |

**The kickoff's 114 is a count of calls, not files: 114 calls in 113 files.**
The breakdown differs too — `bench-entry` names the verb only in a comment, and
`format` carries two textual calls in **one** step (013's fixpoint, over the
*same* task, which is a repetition and not an order).

**Criterion 14 holds today.** Not by construction any longer — 013 retracted
that — but as a fact: no workflow names two devenv tasks, so none can re-state
an order. Meanwhile **44 of 54 repositories declare devenv task order**, almost
all in the idiom `tasks."base:check".after = [ "<proj>:lint" ]`, and `pyjutsu`
carries the two-level graph the charter names.

### 6.2 Can `doctor` check it? Yes — exactly, not by guessing

I expected to answer "no, because the plane must not parse a workflow to
understand it, and devenv's graph is Nix". **Both halves turn out to be
available without either.**

- **The workflow half needs no interpretation.** Counting how many distinct
  devenv tasks a workflow's steps name is set membership on text the file
  already contains — the same shape as `check_fanout`.
- **The devenv half is already published as JSON.** Each repository's
  `.devenv/nix-eval-cache.db` holds a `cached_eval` row for
  `devenv.config.task.config:build` whose `json_output` is a store path to a
  `tasks.json`. That file carries **`after`, `before`, `command` and
  `exec_if_modified` for every task**:

```json
[ { "name": "base:check", "after": [], "before": [],
    "command": "/nix/store/…-base-check", "exec_if_modified": [], … } ]
```

  So the real order graph is readable with a SQLite read and a JSON load, with
  **no `devenv` invocation and no Nix evaluation.**

The check would be: for each workflow naming two or more devenv tasks, load that
repository's `tasks.json` and report any pair whose workflow order is already an
edge in `after`/`before`. That is set membership on both sides, so §15.7 —
"`doctor` does not guess" — does not reach it.

### 6.3 I did not ship it, and why

Three reasons, and I would rather state them than quietly widen the change:

1. **It has zero instances.** Nothing in the plane can violate criterion 14
   without somebody first writing a workflow with two devenv tasks in it.
2. **Its expensive half reads 54 other repositories' live WAL databases.** This
   project's own rule was to keep out of other repositories' `.devenv`. A check
   that opens every one of them, to guard a criterion with no instances, is more
   risk than the finding carries.
3. **The cheap half is worth more than the whole.** The count in §6.1 — "no
   workflow runs the verb more than once" — is one line and would catch the
   shape before the expensive half is ever needed.

**What the gap costs, plainly:** criterion 14 will become false silently, the
first time a repository adds a second `devenv tasks run` to a workflow whose
order its `devenv.nix` already declares. Then two files state one order and the
workflow wins, and nothing reports the disagreement. `pyjutsu` is one ordinary
edit away. **§6.2 is the recipe; it is a small job when the first two-task
workflow appears.**

---

## 7. What I shipped

One `doctor` check, `check_path_inputs`, with six unit tests.

It reads `url: path:…` out of each registered repository's own `devenv.yaml`
(resolving `path:./modules` and `path:../vendomat` against the repository that
names them), `stat`s `<target>/.devenv/shell-*.sh`, and reports any target whose
shell cache exceeds **50 MB** — which by §1.4's measurement (~4.3 ms per MB) is
~215 ms added to every invocation, already more than devenv's entire 146 ms
floor. It counts **only** `shell-*.sh`: the rest of `.devenv` is not the
unbounded part and is not safe to delete.

It reports and never deletes. Law 6 says only the projection and `--prune`
write, and deleting a `shell-*.sh` that a running `devenv shell` is still
sourcing would break that session — this machine has one such shell 16 hours
old.

On the live plane it says:

```
!!  path inputs  /home/andrew/Documents/Projects/docman: 9740 shell-*.sh = 730 MB, taken by 1 projects
                     ~3139 ms added to every devenv invocation in: repoman
                 /home/andrew/Documents/Projects/shellij: 2227 shell-*.sh = 185 MB, taken by 51 projects
                     ~797 ms added to every devenv invocation in: allium-env, argentic, atuout, boomtube, browsee, cairn …
                 /home/andrew/Documents/Projects/vendomat: 9864 shell-*.sh = 767 MB, taken by 7 projects
                     ~3297 ms added to every devenv invocation in: flora, loci.nvim, nix-desktop, nix-nvim, nix-paseo, nix-secrets …
                 devenv gc does not collect these; delete shell-*.sh when no devenv shell is sourcing one (014)
```

**This makes `doctor` exit 1, and that is the check working.** Tuning the
threshold above the real values would be making a check pass by making it check
nothing, which law 4 forbids in as many words. The remedy is the developer's:
delete the shell caches with no `devenv shell` running.

### The pre-existing finding I did not introduce

`doctor` from source at HEAD **already exited 1 before my change**, on
`daemon shell` (`pid 1204: SHELL=…/zsh`), a 009 finding about the Dagu unit.

`devman doctor` on `PATH` exits 0 only because **the installed store build is
older than HEAD** — it predates 009 and does not contain that check. I verified
this by diffing the store copy against HEAD (274 lines; the store copy lacks
four 009 checks) and by building HEAD (`nix build .#devman`), whose `doctor`
reports both `daemon shell` and `path inputs`.

**So the kickoff's "all three exit 0 today" was true of the installed binary and
not of HEAD.** I have not touched the `daemon shell` condition: it wants a
change to the NixOS unit (`serviceConfig.UnsetEnvironment = "SHELL"`) and a
rebuild, which is shared machine configuration and the user's call.

---

## 8. What this costs the plane per day

**Method, stated.** Dagu records every run under
`~/.local/share/dagu/data/dag-runs/**/status.jsonl`. I read the last line of all
1174 of them, took each node's `step.commands[].cmdWithArgs` **and
`step.script`** — the multi-line `format` step lives in `script`, and a
commands-only scan misses it — counted `devenv tasks run` occurrences, and paired
node `startedAt`/`finishedAt`. Dagu's timestamps are second-resolution, so
durations are coarse; the **counts are exact**.

| | |
|---|---|
| dag runs recorded | 1174 |
| span | 2026-08-22 → 2026-09-05 (15 days, 9 with activity) |
| verb-bearing step executions | 668 |
| of those, **skipped by precondition** | **242** |
| succeeded and ran | 383 |
| verb calls inside them | 384 |
| recorded wall time in those steps | 3587 s (59.8 min) |

Applying the measured p50s (`devenv tasks run` = 1537.8 ms; floor without a
`path:` input = 146.1 ms):

| | per calendar day | per active day |
|---|---|---|
| verb calls | 25.6 | 42.7 |
| **devenv startup** | **39.4 s** | **65.6 s** |
| **recoverable (90.5 % of it)** | **35.6 s** | **59.4 s** |

**So the plane's total daily spend on the verb is about 39 seconds, of which
about 36 seconds is recoverable.** That is 16 % of the recorded wall time in
those steps.

**I want to be plain that this is small, and that it is not the point.** A
minute a day is not what makes this worth fixing. Three things are:

1. **The disk.** ~41 GB of pure garbage against 42 GB free, on a disk at 91 %.
   That is a failure with a date on it.
2. **The interactive cost, which Dagu's history cannot see.** Every
   `devenv tasks run` a developer types, and every shell entry and direnv reload
   in 51 repositories, pays the same 1.4 s. The plane's own history records none
   of it.
3. **The cold path.** §2.3 measured 9.2 s cold and 13.9 s after one new `.pyc`.
   The workflow the plane actually fires — `format`, on a `.py` save — is the
   one guaranteed to hit it.

The dominant consumer is `format` on devman: 230 of the 383 executions. That is
because **devman is the only repository that takes the `format` group** (base 54,
release 2, format 1), the only trigger mapping in the whole plane is
`**/*.py` → `format`, and `check`/`test` are neither scheduled nor triggered —
they run only when somebody asks.

---

## 9. What I did not measure

- **Whether deleting the caches actually recovers the time on the live plane.**
  I proved it on controlled copies (L3 vs L4, n=20). I did **not** delete
  `shell-*.sh` from shellij, vendomat or docman, because they are other people's
  repositories and one `devenv shell` on this machine is 16 hours old and still
  sourcing one of those files. That is the confirming experiment, and it is the
  user's to authorise.
- **Where the remaining 287 ms in L4 goes**, versus L0's 146 ms. A 29 MB path
  input still costs 140 ms. I did not profile inside `Validating lock` — the
  work happens in libnix through FFI and emits no devenv spans, and the two
  activity text events at `RUST_LOG=trace` were not enough to attribute it.
- **Whether a `git+file:` or a pinned rev input avoids the copy.** It is the
  obvious next question and I did not test it. It would also be a change to 51
  other repositories' `devenv.yaml`, which is out of devman's scope.
- **Any repository but devman, for timing.** All warm/cold figures are devman
  plus synthetic `/tmp` projects. I did not run `devenv` in the other 53 live
  repositories, on purpose. So "is the cost fixed or does it scale with the size
  of `devenv.nix`, the number of tasks, or the repository?" is answered **only**
  for the `path:` input variable, which turned out to dominate everything.
- **`capture_env_subprocess` at 40–48 ms**, the second-largest span. Not
  investigated.
- **The 9 000 ms cold figure's composition.** I know cold costs 9.2 s and warm
  1.66 s; I did not trace a cold run to say how much of the extra is evaluation
  and how much is realisation.
- **Whether `exec_if_modified`'s defect is upstream-known or already fixed after
  2.1.2.** I read 2.1.2's source and reproduced it there. I did not check
  devenv's issue tracker or later releases.
- **Contention between the eval cache and `tasks.db` under concurrency.** My
  concurrency tests used a project with **no** `path:` input, so each invocation
  was ~100 ms. Sixteen concurrent 1.5-second lock validations against one
  `nix-eval-cache.db` is a different experiment and I did not run it.
- **013's conflict set is unchanged.** Nothing here alters it: I found no
  sibling collision, and the shared state that does hurt is disk, not a lock. So
  013's RESULT and its recommendation stand, and this project was not the
  real-projection spike it asked for.

---

## 10. What changed, and what did not

**Changed:** `src/devman/doctor.py` gains `check_path_inputs`;
`tests/unit/test_doctor.py` gains six tests.

**Not changed:** no workflow, no group, no Nix module, no invocation shape. The
one-`devenv tasks run`-per-step shape is correct and stays. `format`'s fixpoint
stays — §4.1 shows the defect it guards against is real one level down, and
removing the fixpoint would only widen the window.

**Charter:** nothing here contradicts `CONCEPT.md` or `PROPOSAL.md`. §2.4 and
§6.1 correct two figures in this project's own kickoff, not in the charter.

**Verification.** `base:check` clean. **`base:test` (`nix flake check`) passed in
89.7 s.** `base:unit` **396 passed** — the 390 that passed before, unmodified,
plus 6 new; `tests/unit/test_run.py` untouched. `devman doctor` exits 1, for the
pre-existing `daemon shell` finding and for the new `path inputs` finding, both
of which are true.
