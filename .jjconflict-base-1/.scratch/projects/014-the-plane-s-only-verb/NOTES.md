# 014 working notes

Raw findings as they land. RESULT.md is the deliverable; this is the trail.

## Machine state (recorded with every number)

Session start 2026-09-05 11:07. `uptime` load1 = 31.16, 8 cores.
Two heavy loads present:

1. The runaway `find` from project 012 is **still there**. PID 1082086,
   `find -L /sys/bus/pci/devices/0000:19:00.0 ... -name *busy*`, elapsed
   16:56:18, CPU time 16:46:54. It holds one core.
2. **New, and not in the kickoff:** a llama.cpp Vulkan shader build in
   `~/Documents/Projects/talkee/.stage/llama.cpp`. Dozens of concurrent `glslc`
   plus `clang++`. This saturates the other seven cores.

`/tmp/014/loadwatch.sh` samples load every 30 s to `/tmp/014/loadlog.tsv` and
stops when `glslc` and `clang` are gone. **No timing figure is taken until it
stops.**

## Source

devenv 2.1.2 confirmed (`devenv version`, and `Cargo.toml` `version = "2.1.2"`).
Binary: `/nix/store/z8s1yrg6mvld9nlx8857wk5k6wc00cfq-devenv-2.1.2/bin/.devenv-wrapped`,
49 MB, a `makeCWrapper` target. Source cloned to `/tmp/devenv-src` at tag
`v2.1.2`. 013 read no source; every claim below cites a file and a line.

## F1 — the receipt is written after the work, from a re-stat (Part B.2)

`devenv-tasks/src/task_state.rs:617-633`:

```rust
let result = crate::executor::execute(ctx, &callback, cancellation).await;

// Only update file states on success - failed tasks should not be cached
if result.success {
    let expanded_paths = find_files_matching_patterns(&self.task.exec_if_modified);
    for path in &expanded_paths {
        cache.update_file_state(&self.task.name, path).await?;
    }
    cache.cleanup_stale_files(&self.task.name, &expanded_paths).await?;
    if let Some(cmd) = &self.task.command {
        cache.update_file_state(&self.task.name, cmd).await?;
    }
}
```

`update_file_state` calls `TrackedFile::new(path)`
(`devenv-cache-core/src/file.rs:37-60`), which stats the file **now** and
computes a **blake3 content hash of what is on disk now**
(`compute_file_hash`, same file). The glob is re-expanded after the command
too, so a file the task created also gets a receipt.

**This is the same defect shape 013 found in `format`.** A file edited after
the command last read it but before the command exits gets its post-edit hash
written as the receipt. The next run compares against that hash, finds no
change, and skips — `task_state.rs:565-579` returns
`TaskCompleted::Skipped(Skipped::Cached(..))`. The edit is never checked. A
successful run that did the wrong thing, which is law 4.

**`format`'s fixpoint does not close this window.** The fixpoint makes the task
idempotent; the window is between the command's last read and
`update_file_state`, and nothing inside the task can shorten it.

**But the plane's exposure today is zero.** See F2.

## F2 — nothing in the plane sets `execIfModified` (Part B.2, exposure)

Walked every `*.nix` in all 54 registered repositories (skipping `.git`,
`.devenv`, `node_modules`, `.venv`, `target`, `.stage`). **`execIfModified`
appears zero times.** The only use anywhere is devenv's own `devenv.nix:144`,
in the upstream source tree, not here.

So F1 is a real defect, confirmed from source, with **no live exposure**. It
becomes live the moment any repository adds `execIfModified`.

## F3 — every successful task writes `tasks.db`, whether or not it caches

The `if result.success` block above runs `update_file_state(name, cmd)`
**unconditionally**, outside the `exec_if_modified` check. `cmd` is the task
script's nix store path. So each successful task writes one `watched_file` row
per run.

Live `.devenv/state/tasks.db` in devman agrees exactly — 9 rows, one per task,
every `path` a store path, every `modified_time` 1 (store mtime), each with a
blake3 hash:

```
base:check    /nix/store/ppxd5hxh...-base-check     1  2336244aae8a  0
base:test     /nix/store/d0b1v2fl...-base-test      1  7c583f798f7a  0
format:fmt    /nix/store/cg5jmkpp...-format-fmt     1  7399217aa63f  0
...
```

Schema (`tasks.db`, `journal_mode=wal`):

```sql
CREATE TABLE task_run (
  id INTEGER PRIMARY KEY, task_name TEXT NOT NULL UNIQUE,
  last_run INTEGER NOT NULL DEFAULT (strftime('%s','now')), output JSON);
CREATE TABLE watched_file (
  id INTEGER PRIMARY KEY, task_name TEXT NOT NULL, path TEXT NOT NULL,
  modified_time INTEGER NOT NULL, content_hash TEXT,
  is_directory BOOLEAN NOT NULL DEFAULT 0, UNIQUE(task_name, path));
```

`task_run` holds one row — `devenv:python:virtualenv`. Output is only stored
for tasks with `status` or `exec_if_modified` (`tasks.rs:1125-1127`), and
devman has neither on its own tasks.

**This is the write that two concurrent `devenv tasks run` invocations collide
on.** Not yet tested — Part B.3.

## F4 — the shell script cache is content-addressed and never collected

`devenv/src/devenv/mod.rs:2163-2172`:

```rust
fn write_executable_script(dir: &Path, content: &str) -> PathBuf {
    let hash = &compute_string_hash(content)[..16];
    let path = dir.join(format!("shell-{}.sh", hash));
    if !path.exists() { std::fs::write(&path, content)...; }
    path
}
```

Called from `mod.rs:779, 810, 816`. There is **no delete path anywhere**. Every
distinct shell environment ever realised leaves an ~80 KiB file in `.devenv/`
forever.

Measured across all 54 registered repositories (`os.walk` over each `.devenv`,
`lstat` sizes, 2026-09-05 11:12):

| | |
|---|---|
| `shell-*.sh` files | **277,950** |
| `shell-*.sh` bytes | **22.89 GB** |
| `.devenv` total | **54.46 GB** |
| shell cache share | 42.0 % |
| mean script size | 80.4 KiB |

Worst offenders: `flora` 15,786 files, `image-gen-pipeline` 14,374,
`loci.nvim` 13,766, `nix-secrets` 13,653, `interplay` 13,383. devman itself:
10,648 files, 860 MB.

`df -h /home`: 444G total, **399G used, 42G free, 91%**. The shell cache is
**more than half the free space remaining.**

All 54 repositories have a `.devenv/state/tasks.db`.

---

## Machine state for every figure below

`vmstat 2 4` at 11:19, immediately before the first measurement:

```
 r  b   swpd   free   buff  cache  ...  us sy id wa
 2  0      0 27436800 124700 79096508  15 15 70  0
 1  0      0 27490120 ...                7 17 75  1
 1  0      0 27556036 ...                6 14 79  0
 3  0      0 27567184 ...               10 16 74  0
```

**Runnable 1-3, blocked 0, 70-79 % idle, 27 GB free.** The shader build had
finished. The load average still read 4-7 because it decays over minutes from
the 31 at session start — **on this machine load1 lags reality by minutes, so I
record it as instructed but read `vmstat r` for the truth.**

The floor is not zero: the project-012 `find` holds one core permanently, and
`watch -n 1 rocm-smi`, `llama-server`, `atuout` and a Paseo daemon are always
on. **Dagu (`dagu start-all`, PID 1204) and `devman watch` are live** — the
watcher's `watchexec` watches this repository, so a `.py` edit here fires
`format`. `.scratch/**` is in the ignore list, so these notes trigger nothing.

## F5 — the 1.5 s is not evaluation, it is lock validation

n=25, devman, warm:

| probe | p50 | min | p90 | max |
|---|---|---|---|---|
| `devenv tasks run` (no tasks — "nothing at all") | **1537.8 ms** | 1434.0 | 1687.9 | 2436.0 |
| `devenv tasks run -m single base:check` | **1730.1 ms** | 1529.6 | 1895.6 | 2280.6 |
| `ruff check .` after `. .devenv/load-exports` | **27.9 ms** | 16.4 | 33.7 | 35.9 |
| `ruff format .` after `. .devenv/load-exports` | **24.6 ms** | 16.5 | 32.4 | 37.2 |
| sourcing `.devenv/load-exports` alone | **3.4 ms** | 2.2 | 4.1 | 11.2 |

**013's 1550 ms is confirmed at n=25: p50 1537.8 ms.** The work is
27.9 / 1730.1 = **1.6 %** of the price. 013 said 2 %; it stands.

Now the part 013 never asked. `devenv -v ... --trace-to json:file:` writes a
span tree (tracing only emits at DEBUG, so `-v` or `RUST_LOG` is required —
without it the trace file is empty). Three consecutive warm runs, quiet machine,
times in ms:

| span | run1 | run2 | run3 |
|---|---|---|---|
| **Validating lock** | **1640** | **1590** | **1660** |
| dispatch_command | 84.0 | 80.0 | 98.4 |
| — capture_shell_environment | 44.7 | 52.0 | 58.5 |
| — — capture_env_subprocess | 40.1 | 47.5 | 42.5 |
| — — prepare_shell | 4.1 | 4.0 | 15.3 |
| — — — **Evaluating shell** | **2.3** | **1.8** | **1.8** |
| — run (the task itself) | 27.4 | 18.6 | 22.8 |
| **devenv (total)** | 1740 | 1670 | 1760 |

**Validating lock is 94 % of the run. Nix evaluation is 1.8-2.3 ms.**

This retires a whole family of 013's leads at once. `--offline`, `--no-reload`
and the eval cache cannot help, **because the eval cache already hits and costs
2 ms.** The eval cache is not the problem and was never the problem.

## F6 — the cost is one local `path:` flake input, and it is proportional to its size

`devenv-nix-backend/src/lock.rs:35-45` runs `validate_lock_file` then
`fingerprint` on every invocation. `validate_lock_file`
(`devenv-nix-backend/src/lib.rs:363-426`) builds an `InputsLocker` with
`.mode(LockMode::Virtual).use_registries(true)` and calls `.lock(...)` — it
**re-resolves every flake input, every run**. For a `path:` input there is no
revision to short-circuit on: the locked node is literally
`{"path": "/tmp/014/sh-big", "type": "path"}` with **no narHash**, so Nix must
copy and hash the directory to learn what it is.

Controlled experiment. Five synthetic devenv projects under `/tmp/014`,
identical except for their inputs. One task, `probe:noop`, `exec = "true"`.
n=20 each, `devenv tasks run -m single probe:noop`:

| project | its `path:` input | size | p50 | min | max |
|---|---|---|---|---|---|
| L0 | none | — | **146.1 ms** | 111.4 | 246.8 |
| L1 | a tiny dir, `flake: false` | 8 KB | **162.5 ms** | 107.6 | 193.5 |
| L4 | copy of shellij, **`.devenv` deleted** | 29 MB | **286.5 ms** | 249.5 | 321.5 |
| L3 | copy of shellij, **`.devenv` kept** | 298 MB | **1448.1 ms** | 1382.3 | 1999.7 |
| L2 | the live shellij (git, dirty) | 301 MB | **1565.1 ms** | 1419.9 | 1742.6 |
| — | devman itself, `base:check` | 301 MB | 1697.0 ms | 1491.2 | 2251.4 |

**devenv's own startup floor is 146 ms.** Everything above it is the path
input. **Deleting `.devenv` from the input drops the verb from 1448 ms to
287 ms — 1161 ms, 80 % of the cost.**

L2 (a git repo) and L3 (the same tree with `.git` removed) cost the same, so
**Nix does not honour `.gitignore` for a `path:` input.** `.devenv` is
gitignored in shellij and is copied anyway.

## F7 — the plane is slow because devenv's own uncollected cache is inside its inputs

Direct proof, not inference. `/nix/store` holds copies of the **live** shellij
(they contain `.git` and `.jj`, so they are not my `/tmp` copies):

```
/nix/store/0v6fwcpw...-source   294M   .devenv = 265M   2179 shell-*.sh
/nix/store/1ay0ha72...-source   275M   .devenv = 248M   1969 shell-*.sh
```

Sweeping every `-source` path over 50 MB that contains a `.devenv`:

**38 store paths, 18,053 MB.** Largest are 922 MB (10,181 shell scripts),
841 MB ×4 (9,864 each), 840 MB ×2.

So the chain, every link measured:

1. `write_executable_script` never deletes (F4).
2. `.devenv/` grows without bound — 269 MB in shellij, **22.89 GB plane-wide**.
3. **52 of 54 repositories take a local `path:` input; 51 of them take
   shellij.** Only `gitman` and `tyo3` take none.
4. Every `devenv tasks run` validates the lock, which copies and hashes the
   whole path input, `.devenv` included (F6).
5. **devenv is slow because of devenv's own garbage**, on 51 of 54
   repositories, and the garbage is duplicated a further **18.05 GB into the
   Nix store**.

22.89 GB + 18.05 GB = **~41 GB attributable**, against **42 GB free on /home**.
