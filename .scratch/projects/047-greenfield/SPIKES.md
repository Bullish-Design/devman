# 047 spikes: Dagu 2.15 measurements

Date: 2026-10-15. Dagu version: `dagu version` printed `2.15.0` (binary `/nix/store/8qrbhw884vjl6dkjsaih95j8xi0cgwy5-dagu-2.15.0/bin/dagu`).
Claude CLI: `2.1.291 (Claude Code)`.

Each spike used its own `mktemp -d` root, its own `--config` and `--dagu-home`, ports 18080/51055 (spike 1, 2) and 18081/51056 (spike 3).
`dagu config` resolved only the temporary paths each time. The live plane (8080, 50055) stayed untouched.
No process I started is left (checked with `ps` and `ss`).

## Answers in short

1. **Reload.** Dagu watches `dags_dir` and picks up in-place changes without a restart: atomic rename, add, remove, schedule change, and a replaced file symlink all took effect on the next tick. It does NOT follow a repointed `dags_dir` symlink. After the repoint the scheduler kept running directory A and never ran directory B. The reload adapter is needed.
2. **Labels.** Label values accept only `a-z A-Z 0-9 - _ . /`. Every glob form (`*`, `{}`, `!`), space, comma and `=` in a value is refused. Dagu also lowercases keys and values, and the API returns labels as flat `key=value` strings. So a glob cannot live in a label, and a label does not return the exact value.
3. **harness.run.** It works with `provider: claude`. One real call succeeded in 7.0 s. The status was `succeeded`, and `HELLO.txt` (content `hi`) existed in the work tree and not in the main checkout.

---

## Spike 1: reload without restart

### Setup

Config (`config.yaml` in the temp root):

```yaml
auth: {mode: none}
host: 127.0.0.1
port: 18080
coordinator: {host: 127.0.0.1, port: 51055}
dag_discovery: {recursive: true, symlinks: true}
paths: {dags_dir: <root>/dags, data_dir: ..., log_dir: ..., admin_logs_dir: ..., base_config: ...}
skip_examples: true
```

Every DAG had `schedule: "* * * * *"` and one step: `echo "<marker> $(date +%H:%M:%S)" >> <root>/out/<name>.log`.

Commands:

```
dagu --config $R/config.yaml --dagu-home $R/home start-all     # background, setsid
mv dags/.base.tmp dags/base.yaml                                # case 1
... (see cases)
dagu --config ... --dagu-home ... start base                    # case 7
kill <pid of start-all>
```

Cases 1 to 5 ran against a real `dags_dir`. Case 6 ran in a second `start-all` whose `dags_dir` was a symlink to directory A (with a fresh `data_dir`).

### Results

| Case | Action (time) | Result |
|---|---|---|
| 1 | `mv` temp file over `base.yaml`, v1 to v2 (18:37:24) | Yes. Next tick 18:38:00 wrote `v2`. |
| 2 | Add `newdag.yaml` (18:37:24) | Yes. `newdag.log` has `v1 18:38:00`. |
| 3 | `rm gone.yaml` (18:37:24) | Yes. `gone.log` stops at 18:37:00. |
| 4 | Change `sched.yaml` schedule to `0 0 1 1 *` (18:37:24) | Yes. `sched.log` stops at 18:37:00. |
| 5 | `ln -s ext2.yaml tmp && mv -T tmp ext.yaml` (18:37:24) | Yes. `ext.log` goes from `v1` to `T2` at 18:38:00. |
| 6 | Repoint `dags_dir` symlink A to B (18:40:26) | **No.** Scheduler ran A at 18:41, 18:42, 18:43. It never ran B. |
| 7 | `dagu start base` at 18:37:26 | Yes. Wrote `v2 18:37:26`. |

Dagu logged the reload for cases 1 to 5 within 125 ms of the change (quoted from `start-all` stderr):

```
18:37:24.169 level=INFO msg="Rebuilding DAG definition index" dir=.../dags
18:37:24.180 level=INFO msg="Planner: DAG deleted" dag=gone
18:37:24.181 level=INFO msg="Planner: DAG updated" dag=base
18:37:24.181 level=INFO msg="Planner: DAG updated" dag=ext
18:37:24.181 level=INFO msg="Planner: DAG added" dag=newdag
18:37:24.197 level=INFO msg="Planner: DAG updated" dag=sched
```

The change shows as a file-system event, so the scheduler does not wait for the next minute to see it. The next tick uses the new state.

Case 6 evidence. After the repoint, `dagu ls` (a new process) listed `dirB`. The web API (`/api/v1/dags`) listed `dirB` with `nextRun 18:43:00`. But the running scheduler kept dispatching A:

```
18:41:00.001 Dispatching planned run dag=dirA
18:42:00.001 Dispatching planned run dag=dirA
```

`dirA.log` has `v1` lines at 18:41, 18:42, 18:43. `dirB.log` never existed. I then edited a file inside B with an atomic rename. The scheduler logged no `Planner:` line. So the watcher stays on the old directory. The web server reads the disk on each request and shows the new directory. The scheduler holds a stale view.

### Surprises and limits

- At start-up the scheduler ran a catch-up run for the minute it started in (`Dispatching planned run ... scheduledTime=18:36:00` at 18:36:24). Expect one extra run after each restart.
- Dagu creates a `wiki` directory inside `dags_dir`.
- Dagu warns `steps[0].command is deprecated; use run`. The files still work.
- I did not test a repoint plus a later restart, nor any signal that forces a rescan. I did not test a symlink target inside `dags_dir` that changes through its parent directory.
- Case 5 used a symlink to a file outside `dags_dir`. The DAG name came from the link name (`ext`), not from the target name.

---

## Spike 2: label values and read-back

### Commands

`dagu --config $R/config.yaml --dagu-home $R/home validate <file>` for each file. Read-back used the temporary server: `curl localhost:18080/api/v1/dags`, `/api/v1/dags/<name>`, `/api/v1/dags/<name>/spec`, `/api/v1/dags/<name>/dag-runs`, `dagu ls`, `dagu status lab`. (`/api/v2/dags` returns the web UI HTML here. The REST path is `/api/v1`.)

### Allowed characters (from the error text)

```
label value ... contains invalid characters (allowed: a-z, A-Z, 0-9, -, _, ., /)
label key   ... contains invalid characters (allowed: a-z, A-Z, 0-9, -, _, .)
label key cannot be empty
```

### Values

The map, string and array forms give the same verdict for the same value.

| Value | Verdict |
|---|---|
| `**/*.py` | refused (map, string, array) |
| `src/**/*.{py,pyi}` | refused (map, array) |
| `!tests/**` | refused (map, array) |
| `a b` (space, map) | refused |
| `a,b` (comma, map) | refused |
| `a=b` (equals, map) | refused |
| empty string | accepted (map `{g: ""}`, array `"k="`, string `"k="`) |
| `null` | refused (`label value "<nil>"`) |
| `src/lib/a.py`, `value/with-dots.x_y` | accepted |
| numbers and booleans (`1.50`, `true`) | accepted, stored as strings |

Exact error for the main case, map form:

```
'labels' failed to unmarshal from YAML: label value "**/*.py" contains invalid characters (allowed: a-z, A-Z, 0-9, -, _, ., /)
```

String and array forms add structure to the text, so a value can parse as a key. These are all refused:

- String `"!tests/**"` gives `label key "!tests/**" contains invalid characters`, because the string form reads it as a key.
- String `"a b, c=d"` gives `label key "a b" ...`. The string form splits on spaces and commas.
- String `"a=b=c"` gives `label value "b=c" ...`.
- Array item `"a,b"` gives `labels[0]: label key "a,b" ...`.
- Array item `"x=a=b"` gives `labels[0]: label value "a=b" ...`.

A string like `"devman.on=save devman.glob=src/lib/a.py"` is accepted. The string form is space-and-comma separated `key=value` pairs.

### Keys

| Key | Verdict |
|---|---|
| `devman.on` (dots) | accepted |
| `DevMan` (uppercase) | accepted (but lowercased, see below) |
| `devman/on` (slash) | refused |
| `a b`, `a=b`, `a,b`, `x*` | refused |
| empty key | refused (`label key cannot be empty`) |

### Read-back

A program can read labels from Dagu, but not the exact value. Test file (in the live-like `dags_dir`):

```yaml
labels:
  devman.on: save
  devman.glob: src/lib/a.py
  Mixed.Case: Value/With-Dots.x_y
  empty: ""
  num: 1.50
  flag: true
```

`GET /api/v1/dags/lab` returned `dag.labels` (and an identical legacy `dag.tags`):

```
["mixed.case=value/with-dots.x_y", "devman.glob=src/lib/a.py", "devman.on=save", "empty", "flag=true", "num=1.5"]
```

What changed:

- Dagu **lowercases keys and values** (`Mixed.Case` became `mixed.case`; `Value/With-Dots.x_y` became `value/with-dots.x_y`).
- An **empty value loses the `=`**: `empty: ""` reads back as the bare label `empty`. A bare label and an empty-value label look the same.
- `1.50` became `1.5`.
- The list is flat strings, not a map. The order is not the file order.
- The same flat list appears on `/api/v1/dags/lab/dag-runs` for each run.
- `GET /api/v1/dags/lab/spec` returned the same parsed `labels` list under `dag`. I did not find an endpoint that returns the raw YAML text of a label. (I did not test a raw-source endpoint beyond `/spec`.)
- `dagu ls` prints names only. `dagu status` prints no labels.
- Filter: `?labels=devman.on=save` returned `['lab']`. `?labels=devman.on=nope` returned `[]`. So the server filters by exact `key=value`.

So: a program that needs the exact (case-sensitive, glob-bearing) value must read the YAML file. Dagu gives back a lowercased, simple form only.

### Surprises and limits

- The REST version is `/api/v1`, and `/api/v2` serves HTML.
- I did not test label limits on length or count.
- I did not test whether quoting or escaping can carry a refused character. The error text lists no escape.

---

## Spike 3: `harness.run` with `claude`

### Schema (from `dagu schema dag`)

- `harnessRunActionConfig`: `allOf` the executor config plus `prompt` (required, `minLength: 1`, "Task prompt passed to the harness CLI") and optional `stdin`.
- `harnessExecutorConfig`: open object. `provider` and `model` are named. `fallback` (array of provider configs) is reserved. `binary` and `prompt_args` are forbidden keys. "Unknown keys are passed through to the CLI as flags." "When no DAG-level harness defaults exist, specify provider."
- `harnessProviderConfig`: same, `provider` is required. Reserved keys: `provider`, `fallback`.
- Built-in providers: `aider, amp, claude, cline, codex, copilot, cursor, deepseek, droid, gemini, goose, kiro, opencode, pi, qwen`. A custom name comes from a top-level `harnesses:` entry.
- Flag values: a scalar gives one flag value. An array gives a repeated flag. Booleans and numbers are allowed.
- DAG-level `harness:` key = `harnessDefaultsConfig` (executor config, `provider` required). Steps inherit it. Step-level keys override.
- Custom `harnesses:` entries (`harnessNamedDefinition`): `binary` (required), `prompt_mode` (`arg|flag|stdin`), `prompt_flag`, `prompt_position`, `prefix_args`, `flag_style` (`gnu_long|single_dash`), `option_flags`.
- Outputs: the schema lists no fixed outputs for `harness.run`. The step stdout is captured with `output: VAR` (example 13 in `dagu example 13`). A `git.worktree.*` step **refuses** `output:`: `git worktree actions have fixed outputs`. I did not find the fixed output names.

### Pre-checks

- `command -v claude` gave `/run/current-system/sw/bin/claude`.
- `claude --help` has **no turn limit flag**. It has `--max-budget-usd`, `--effort`, `--permission-mode`, `--model`.

### The run

Temp repo with one commit (`e0e0f59 init`). Config with `dags_dir`, `DAGU_HOME`, ports 18081/51056 in `/tmp/spike3.*`. DAG:

```yaml
working_dir: <root>/repo
steps:
  - name: add
    action: git.worktree.add
    with: {path: <root>/wt, branch: spike/hello, create_branch: true}
  - name: ask
    depends: [add]
    working_dir: <root>/wt
    action: harness.run
    with:
      provider: claude
      model: haiku
      max-budget-usd: 0.25
      permission-mode: acceptEdits
      prompt: "Create a file named HELLO.txt containing the single word hi. Do nothing else."
    output: ASK_OUT
  - name: report
    depends: [ask]
    command: |
      echo "ASK_OUT=${ASK_OUT}"
      git -C <root>/wt status --short
      cat <root>/wt/HELLO.txt
      ls <root>/repo; git -C <root>/repo status --short
  - name: remove
    depends: [report]
    action: git.worktree.remove
    with: {path: <root>/wt, branch: spike/hello, force: true}
```

Command: `dagu --config <root>/config.yaml --dagu-home <root>/home start hello`. One call only. No retry.

Results:

- Exit status of `dagu start`: **0**. Dagu run status: **Succeeded** (`status=succeeded`). All four steps succeeded.
- Wall time: 7.0 s for the run (18:43:51 to 18:43:58). The `ask` step took 7.0 s.
- `report` step output:

```
ASK_OUT=Done.
--- status
?? HELLO.txt
--- file
hi--- main checkout
README
```

`HELLO.txt` held `hi` (no trailing newline) in the work tree. The main checkout held only `README`, and its `git status --short` was empty.

- The command line Dagu built (seen with `ps`):

```
claude -p Create a file named HELLO.txt containing the single word hi. Do nothing else. --max-budget-usd 0.25 --model haiku --permission-mode acceptEdits
```

So the prompt goes as the `-p` argument, `model` becomes `--model`, and unknown keys become `--key value`. Dagu added no permission flag by itself, so a file write needs `permission-mode` (I did not test the run without it).
- Harness stdout (`ask.*.out`): `Done.`. The `output: ASK_OUT` variable was stored as `ASK_OUT=Done.` (the status file keeps `NAME=value`; `${ASK_OUT}` in a later step expanded to `Done.`).
- Harness stderr: `Warning: claude.ai MCP servers blocked by enterprise policy: claude.ai Gmail, claude.ai Google Calendar, claude.ai Google Drive`. This is noise from the user setup. It did not fail the step.
- The Dagu run log has only step start lines and the finish line. It holds no harness detail.
- Authentication: inherited from the user environment. No `ANTHROPIC_*` variable is set. `~/.claude/.credentials.json` exists. The CLI most likely read it through `HOME`. I did not verify which source the CLI used, and I printed no credential.

### Surprises and limits

- `git.worktree.add` and `.remove` print nothing to stdout and refuse `output:`. The step cannot hand the work tree path on. Pass a fixed `path:`.
- `remove` with `force: true` deleted the untracked `HELLO.txt` with the work tree. The report step printed the file first. The branch `spike/hello` stayed, because `delete_branch` was not set.
- The `claude` CLI has no turn limit. The cap used is a budget (`--max-budget-usd 0.25`). Real cost was not measured.
- I could not see the token count or the dollar cost, because Dagu does not log them.
- I ran from inside a Claude Code session. The nested call worked. The result may differ from a plain systemd context.
- I did not test the fallback list, `stdin`, or a named custom harness.
