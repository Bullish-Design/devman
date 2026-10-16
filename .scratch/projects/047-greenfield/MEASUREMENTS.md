# 047 measurements: Dagu 2.20.1

Date: 2026-10-15. Dagu: official `dagu_2.20.1_linux_amd64.tar.gz` from github.com/dagu-org/dagu. `dagu version` prints `2.20.1`.
SHA-256 `0d5c1612cd842931fe6d4e598fc2e43fb912a94122e571c62a8f73691ea49837` matches `checksums.txt` (`sha256sum -c`: OK).
Watchexec: 2.5.1 from the nix store.

Each measurement used its own `mktemp -d` root, its own `DAGU_HOME`, `config.yaml` and `dags_dir`, and its own ports (18090/51090 to 18094/51094).
Every config had `auth: {mode: none}` and `dag_discovery: {recursive: true, symlinks: true}`.
`dagu config` printed only temporary paths each time. The live Dagu (8080, 50055, `~/.local/share/dagu`) stayed untouched.
I killed every process I started and checked with `ps` and `ss`. I deleted the temporary roots after I copied the evidence into this file.

Base `config.yaml` (queue block only in M1, M3, M4, M6 roots):

```yaml
auth: {mode: none}
host: 127.0.0.1
port: 1809x
coordinator: {host: 127.0.0.1, port: 5109x}
dag_discovery: {recursive: true, symlinks: true}
paths: {dags_dir: <root>/dags, data_dir: <root>/home/data, log_dir: <root>/home/logs, admin_logs_dir: <root>/home/adminlogs, base_config: <root>/base.yaml}
skip_examples: true
queues: {enabled: true, config: [{name: light, max_concurrency: 1}]}
```

Run commands:

```
DAGU_HOME=<root>/home /tmp/dagu-dl.XXXX/x/dagu --config <root>/config.yaml start-all     # background, setsid
DAGU_HOME=<root>/home /tmp/dagu-dl.XXXX/x/dagu --config <root>/config.yaml <start|enqueue|validate|ls> ...
```

## Answers in short

1. **M1.** Yes. A scheduled run of a DAG on a defined queue waits for a free slot. A DAG on an undefined queue skips the queue and runs at once.
2. **M2.** Dagu does not fail on a missing `working_dir` or `log_dir`. It creates the directory (`mkdir -p`) and the run succeeds. It fails only when it cannot create the directory. Compile must check the path itself.
3. **M3.** Yes. A `handler_on` in `base.yaml` reaches every DAG, and the handler sees `DAG_NAME` and `DAG_RUN_STATUS`. The final status waits for the handler. A failing `success` or `exit` handler turns a succeeded run into a failed run. A handler that starts a background process does not block. A DAG's own handler replaces the base handler of the same key only.
4. **M4.** Both projects load as `<project>.<name>`. A symlink outside `dags_dir` changes nothing. Two files with one base name make Dagu list neither, report an error and exclude both from the scheduler. `group:` and `labels:` work, but Dagu lowercases label values. New finding: `dagu start` and `dagu enqueue` do not find a DAG in a subdirectory by name. They need the file path.
5. **M5.** One watchexec over the 33 directories sets 90 461 inotify watches (17% of the limit 524 288). Start-up takes about 14 s at one full core. Then it uses 75 MB and about 0.5 s of CPU per idle minute.
6. **M6.** Yes. `dagu enqueue <dag> -- KEY=value` passes the parameter. A step reads `${KEY}` or `$KEY`, even when the DAG does not declare it. `--name`, `--labels`, `--queue` and `--run-id` work. `--default-working-dir` has no effect on `enqueue`. Two quick enqueues of one DAG are both kept and run one after the other.

---

## M1. Queue wait for scheduled runs

**Answer.** Yes. The second scheduled run on `queue: light` (`max_concurrency: 1`) waited in the queue until the first run ended. DAGs on a queue that `config.yaml` does not define started at once, in parallel.

**Setup.** DAGs `a` and `b`: `queue: light`, `schedule: "* * * * *"`, one step: write `start <time>`, `sleep 40`, write `end <time>`.
DAGs `ghost` and `ghost2`: same step, `queue: undefinedq`, same schedule.

**Commands.**

```
start-all (background)                       # started 20:55:52
curl http://127.0.0.1:18090/api/v1/dag-runs?limit=20
```

**Evidence.** Step logs:

```
b.log   start 20:55:55.22   end 20:56:35.24
a.log   start 20:56:37.09
ghost.log   start 20:55:52.11   end 20:56:32.12
ghost2.log  start 20:55:52.34   end 20:56:32.35
```

REST API (`queuedAt`, `startedAt`, `finishedAt`):

```
b      succeeded  queued 20:55:51  started 20:55:54  finished 20:56:35
a      running    queued 20:55:51  started 20:56:36   (waited 45 s, started 1.5 s after b ended)
ghost  succeeded  queued None      started 20:55:51  finished 20:56:32
ghost2 succeeded  queued None      started 20:55:51  finished 20:56:32
b      queued     queued 20:57:00   (next tick, queued while a still ran)
```

Scheduler log:

```
Catchup run enqueued dag=b / dag=a
Processing batch of items queue=light count=1 max-concurrency=1 alive=0     (20:55:54, b starts)
Processing batch of items queue=light count=1 max-concurrency=1 alive=0     (20:56:36, a starts)
Dispatching planned run dag=ghost / dag=ghost2                              (no queue step)
Skipping job because a run of the DAG is queued dag=a scheduled-time=20:56:00
```

Notes:
- The scheduler ran an old tick (20:55:00) at start-up. This is catch-up, not a normal tick.
- The scheduler checks the queue about every 2 s (`a` started 1.5 s after `b` ended).
- A DAG on an undefined queue gets `Dispatching planned run` and no queue record. Its name is its own queue name, and Dagu does not apply a limit from `config.yaml`.
- A DAG with no `queue:` field uses its own name as queue (M6 shows `Processing batch ... queue=projA.p`).

**What it means for CONCEPT.md.**
- §10 and R1 hold on 2.20.1: a queue limit now throttles scheduled runs. Keep the sentence "only when the config defines that queue".
- Add to §5 (compile refusals): refuse a workflow whose `queue:` names a queue that `config.yaml` does not define. Dagu accepts it silently and the limit does not apply. This is the "run succeeds with the wrong result" shape.

---

## M2. Missing `working_dir` and `log_dir`

**Answer.** Dagu does not fail. It creates the missing directory and the run succeeds with exit code 0. It fails with exit code 1 only when the directory cannot be created (`mkdir: permission denied`). Compile must check that `path` exists. The M2 requirement "it must fail" is not met by Dagu.

**Commands** (DAG files with a `working_dir` or `log_dir` that did not exist):

```
dagu start badwd            # working_dir: /tmp/does-not-exist-m2
dagu enqueue badwd          # working_dir: /tmp/dne-m2-enq (queue run by start-all)
schedule "* * * * *"        # badwds, working_dir: /tmp/does-not-exist-m2
dagu start badlog           # log_dir: /tmp/does-not-exist-m2-log/sub
dagu enqueue badlog
dagu start badwdroot2       # working_dir: /nonexistent-m2/x   (cannot create under /)
dagu enqueue badwdroot2
schedule badwdroots         # working_dir: /nonexistent-m2/x
```

**Evidence.**

| Case | Dagu status | `dagu start` exit | Directory after |
|---|---|---|---|
| `working_dir` missing, `start` | succeeded | 0 | created, step ran in it (`ran in /tmp/does-not-exist-m2`) |
| `working_dir` missing, `enqueue` | succeeded | 0 | created |
| `working_dir` missing, schedule | succeeded | n/a | created |
| `log_dir` missing, `start` | succeeded | 0 | created (`/tmp/does-not-exist-m2-log/sub/badlog/dag-run_...log`) |
| `log_dir` missing, `enqueue` | succeeded | 0 | created |
| `working_dir` not creatable, `start` | **failed** | **1** | none |
| `working_dir` not creatable, `enqueue` | failed | 0 for `enqueue`; the run failed | none |
| `working_dir` not creatable, schedule | failed | n/a | none |

Error text for the not-creatable case:

```
level=ERROR msg="Failed to initialize DAG execution" dag=badwdroot2 ... err="failed to create working directory: mkdir /nonexistent-m2: permission denied"
Result: Failed
Error: failed to execute the dag-run badwdroot2 (...): failed to create working directory: mkdir /nonexistent-m2: permission denied
```

`dagu validate` exits 0 for all of these files. It checks no path.
`dagu enqueue` exits 0 at enqueue time. The failure shows later, in the run record.

Side effect: Dagu created the missing directories (I deleted them). A typo in `path` would create an empty directory with the typo name. This is the "unset variable makes a directory of that literal name" trade-off in the project notes.

Also measured: `dagu validate` rejects a top-level `name:` in a file (`entrypoint document must not define name`, exit 1), while `dagu start` accepts it. The compiled header must not set `name:`. The DAG name comes from the file name.

**What it means for CONCEPT.md.**
- §5 already refuses when `path` does not exist. Keep it and say why: Dagu creates the directory and the run succeeds in the wrong place. Rule 4 of the project notes applies.
- §5 step 2: the header must not contain `name:`.
- §13 M2: close with this answer.

---

## M3. `handler_on` in `base.yaml`

**Answer.**
- Every DAG inherits a base `handler_on` (`exit`, `success`, `failure`). This held for `dagu start` and for a run from the queue.
- The handler sees `DAG_NAME` and `DAG_RUN_STATUS` (`succeeded` or `failed`), `DAG_RUN_ID`, `DAG_RUN_LOG_FILE` and `DAG_PARAMS_JSON`.
- The run's final status and `finishedAt` wait for the handler (10 s sleep: run took 10.3 s).
- A handler failure changes the run: a failing `success` or `exit` handler turns a succeeded run into `failed`, and `dagu start` exits 1. The handler saw `status=succeeded` first.
- A DAG's own `handler_on.success` replaces the base `success` handler. Base `exit` and `failure` stay. The merge is per handler key.
- A handler that starts a detached background process (`setsid sh -c '...' &`, output redirected) does not block the run: the run finished in 0.2 s and the background process ended 10 s later.

**Setup.** `base.yaml`:

```yaml
handler_on:
  exit:
    command: |
      echo "exit name=$DAG_NAME status=$DAG_RUN_STATUS run=$DAG_RUN_ID start=$(date +%T.%N)" >> h.log
      sleep 10
      echo "exit end name=$DAG_NAME t=$(date +%T.%N)" >> h.log
  success:
    command: echo "success name=$DAG_NAME status=$DAG_RUN_STATUS ..." >> h.log
  failure:
    command: echo "failure name=$DAG_NAME status=$DAG_RUN_STATUS ..." >> h.log
```

DAGs: `ok` (step `echo ok`), `bad` (step `exit 3`), `own` (own `handler_on.success`).

**Evidence, round 1** (`dagu start <dag>`; the DAG files have no `handler_on` except `own`):

```
ok   start 20:58:36.38  end 20:58:46.69  status=succeeded  exit 0
bad  start 20:58:46.70  end 20:58:57.13  status=failed     exit 1
own  start 20:58:57.14  end 20:59:07.42  status=succeeded  exit 0

success name=ok status=succeeded t=20:58:36.59
exit name=ok status=succeeded run=034gdgHsn6oceLQ1WLSwRv start=20:58:36.62
exit end name=ok t=20:58:46.63
failure name=bad status=failed t=20:58:47.02
exit name=bad status=failed run=034gdgY6CYxAosnfKbFq8Y start=20:58:47.05
exit end name=bad t=20:58:57.07
OWN success name=own t=20:58:57.33        <- own success ran, base success did not
exit name=own status=succeeded ... start=20:58:57.36     <- base exit still ran
exit end name=own t=20:59:07.37
```

The run record says `finished-at=20:58:46` for `ok`, after the 10 s handler.

**Evidence, round 2** (failing handlers). Base `success` and `exit` both end with `exit 1`:

```
okx  (step ok)    -> Result: Failed   exit status 1
badx (step fails) -> Result: Failed   exit status 1
```

Round 3 (only the base `exit` handler fails, DAG `okx`): `status=failed`, exit 1. The handler log shows `exit-failing name=okx status=succeeded`. The run was `succeeded` when the handler ran and `failed` afterwards.

**Evidence, round 4** (background start in the handler):

```
bg (own exit handler starts setsid sleep 10 and returns):
  bg-exit-start 20:59:16.40, run finished 20:59:16.41, bg-exit-end 20:59:26.42   (10 s later)
bg again, base exit failing handler replaced by the DAG's own handler:
  run 20:59:34.61 -> 20:59:34.86 (0.25 s), status succeeded, exit 0
okx with a base exit handler that backgrounds the sleep:
  run 20:59:34.88 -> 20:59:35.08 (0.2 s), status succeeded
```

**Evidence, handler environment** (run through `enqueue` and `start-all`):

```
DAG_NAME=envd
DAG_PARAMS_JSON={"A":"1"}
DAG_RUN_ID=034gdi4rohb7jG7AJgARM1
DAG_RUN_LOG_FILE=.../envd/dag-run_..._034gdi4r.log
DAG_RUN_STATUS=succeeded
DAG_RUN_STEP_NAME=onExit
DAG_RUN_WORK_DIR=.../dag-run-work/envd/.../root
DEVMAN_PROJECT_DIR=/x/y         <- the DAG's own env reaches the handler
```

**What it means for CONCEPT.md.**
- §7: `done` and `failed` via `handler_on` in `base.yaml` is valid. Call `devman emit` from the `exit` or `success`/`failure` handler. Pass `$DAG_NAME` (the `<project>.<name>` name) and `$DAG_RUN_STATUS`; `DEVMAN_PROJECT_DIR` is also present.
- Change §7: the handler must not block and must not fail. A failing `devman emit` makes the run `failed`. A slow one delays the final status. Write the handler as a detached, always-succeeding call, for example `devman emit ... || true`, or start it with `setsid ... &`. State this rule.
- A project workflow that sets its own `handler_on.exit` or `success` silently drops the base one. Say in §5 or §7 that compile refuses a source file that defines `handler_on` for a key that `base.yaml` uses, or that the header merges them. Choose one.
- §13 M3: close with this answer.

---

## M4. Discovery, symlinks, duplicates, `group:` and `labels:`

**Answer.** Both projects load as `<project>.<name>` (`projA.check`, `projA.build`, `projB.check`). A symlink to `dags/projA/` placed outside `dags_dir` (as linkman would) changes nothing, and `dagu start` works through the link. A symlink to `projA` inside `dags_dir` also changes nothing. Two files with one base name in two subdirectories are not loaded as DAGs at all. `group:` and `labels:` validate and show in the REST API, but not in `dagu ls`. Dagu lowercases the label value.

**Setup.**

```
dags/projA/projA.check.yaml   group: projA / labels: [project=projA]
dags/projA/projA.build.yaml
dags/projB/projB.check.yaml   group: projB / labels: [project=projB]
repoA/.devman/dags -> <root>/dags/projA        (symlink outside dags_dir)
```

**Evidence.**

`dagu ls` (before and after the external symlink, and after an internal symlink `dags/linkA -> projA`): the same three names each time.

```
NAME
projA.build
projA.check
projB.check
```

`GET /api/v1/dags`:

```
projA.build  fileName=projA.build  group=None   labels=[]
projA.check  fileName=projA.check  group=projA  labels=['project=proja']
projB.check  fileName=projB.check  group=projB  labels=['project=projb']
errors: None
```

Run through the link: `dagu start <root>/repoA/.devman/dags/projA.check.yaml` gave `Result: Succeeded`.

Label forms: `labels: project=projA` (string) and `labels: [project=projA]` (list) both validate and both give `['project=proja']`. A string `labels: project=proj A` splits at the space into `['project=proj', 'a']` and still validates, so a space is a separator, not an error.
The REST filter `GET /api/v1/dags?labels=project%3Dproja` returned `['projA.check', 'projA.str']`. Use the lowercase value in the filter. The runs endpoint with `labels=project%3Dprojb` returned no run (no run existed for projB at that point).
`dagu ls` has no group or label column. Its flags are `-n -l -H -t -r` only.

Duplicate base name: `dags/projA/check.yaml` and `dags/projB/check.yaml`:

```
GET /api/v1/dags -> neither "check" listed; the other five DAGs stay
errors: ['duplicate DAG file name "check": projA/check.yaml, projB/check.yaml',
         'duplicate DAG name "check": projA/check.yaml, projB/check.yaml']
dagu ls   -> warning: duplicate DAG file name "check": projA/check.yaml, projB/check.yaml
scheduler -> level=ERROR msg="DAG excluded from scheduler" err="duplicate DAG file name \"check\" ..."
```

`dagu start <root>/dags/projB/check.yaml` (a path) still ran. Removing the files cleared the error without a restart.

**New finding: the CLI does not resolve subdirectories by name.**

```
dagu start projA.check   -> Error: failed to read file ".../dags/projA.check.yaml": no such file or directory
dagu enqueue projB.check -> Error: failed to read file ".../dags/projB.check.yaml": no such file or directory
dagu start check         -> Error: ... .../dags/check.yaml: no such file or directory
```

The CLI looks only in the top of `dags_dir`. It accepts a file path (`dagu enqueue /abs/dags/projA/projA.p.yaml`, tested in M6). The REST API accepts the DAG name: `POST /api/v1/dags/projA.p/enqueue` (M6) enqueued the subdirectory DAG.

**What it means for CONCEPT.md.**
- §3.2 holds. The `<project>.` prefix and the subdirectory work. The duplicate rule is correct: a duplicate hides both files and excludes both from the scheduler. Say that compile refuses a duplicate in the same project. The `<project>.` prefix already prevents one across projects.
- §7 needs a change: the router must call `dagu enqueue <absolute path to dags/<project>/<project>.<name>.yaml>`, or call the REST API by name. It cannot call `dagu enqueue projA.check`. Pick one. The path form works without a server. The router knows the path because compile wrote it.
- §6: a linkman symlink to `dags/<project>/` outside `dags_dir` is safe. Keep it. Do not put the link inside `dags_dir`.
- §5 step 2: label values are lowercased. Use `project=<project lowercased>` in any filter. Label values and `group:` accept `.` (`loci.nvim` is a legal label value per the earlier spike).
- §13 M4: close with this answer.

---

## M5. Cost of one watchexec over 33 repositories

**Answer.**

| Quantity | Value |
|---|---|
| inotify watches (from `/proc/<pid>/fdinfo`) | 90 461 |
| system limit `fs.inotify.max_user_watches` | 524 288 (17% used) |
| first watch set | 0.2 s |
| all watches set | about 14 s after launch (run 1: 66 732 at 12.8 s, 90 461 by 15 s) |
| CPU during start-up | about 15 s (1 506 ticks at 15.6 s; one full core) |
| resident memory after 1 minute | 74 804 to 74 984 kB (about 75 MB) |
| CPU over one idle minute | 0.55 s (55 ticks at 100 per s), about 1% of one core. A second sample: 17 ticks in 35 s |
| event count while idle | 0 |
| one touch in one repository | 1 event (the `echo EVENT` command ran once) |

**Setup.** One command, run three times (run 1 measured the touch event, run 2 and run 3 measured start-up and the idle minute):

```
watchexec -w /home/andrew/Documents/Projects/agentman -w .../argentic ... -w .../vendomat \
  -i '**/.git/**' -i '**/.jj/**' -i '**/.devenv/**' -i '**/.direnv/**' \
  -i '**/.venv/**' -i '**/node_modules/**' -i '**/__pycache__/**' \
  --postpone -- echo EVENT
```

(all 33 directories, the full list in the task). The command only prints. watchexec 2.5.1 at `/nix/store/lnlrjslg1hcna5xghav2fq63cp5piqip-watchexec-2.5.1/bin/watchexec`.

I counted watches with `grep -c '^inotify wd:' /proc/<pid>/fdinfo/*` and CPU from `/proc/<pid>/stat` (fields 14+15).

**Evidence.** Timeline from run 3 (every 5th sample):

```
t=4635ms   watches=35970  cpu_ticks=529   VmRSS 37816 kB
t=10014ms  watches=69001  cpu_ticks=1085  VmRSS 64704 kB
t=15575ms  watches=90461  cpu_ticks=1506  VmRSS 74976 kB
t=21124ms  watches=90461  cpu_ticks=1510
t=55541ms  watches=90461  cpu_ticks=1527  VmRSS 74984 kB
```

Run 2: `idle_minute_ticks 55 VmRSS: 74804 kB`.

Tree size: 55 809 directories under the 33 repositories. 23 192 of them lie under an ignored name (`.git`, `.jj`, `.devenv`, `.direnv`, `.venv`, `node_modules`, `__pycache__`). I did not test whether watchexec skips watches for the ignored directories. The 90 461 count is larger than the directory count, so I infer that it watches ignored directories too. Treat the ignore patterns as an event filter, not as a watch filter.

**What I touched.** Run 1 ran `touch /home/andrew/Documents/Projects/testee/README.md` once. It changed only the file's modification time (content and size unchanged). The event arrived (`events: 1`). I touched nothing else in any repository. The repository content is unchanged.

**What it means for CONCEPT.md.**
- §7 `save` is affordable: 75 MB, about 1% of a core when idle, 17% of the watch budget. One process is enough.
- Add to §7 or §10: the watcher takes about 14 s of full-core CPU at every start, and it sets about 90 000 watches. A restart per compile is wrong. Restart it only when the set of paths changes, and expect `save` events to be missing for about 15 s after a start. If the path list grows past about 150 repositories, the limit 524 288 is the next constraint.
- Do not rely on the ignore patterns to cut the watch count.
- §13 M5: close with this answer.

---

## M6. `dagu enqueue` and parameters

**Answer.** `dagu enqueue <dag> -- KEY=value` passes the parameter. A step reads it as `${KEY}` or `$KEY` (also when the DAG does not declare `params:`) and from `DAG_PARAMS_JSON`. Positional words become `1`, `2`: a step reads `${1}`, `${2}`. Flags `--name`, `--labels`, `--queue` and `--run-id` work. `--default-working-dir` has no effect on `enqueue`. Two quick enqueues of one DAG are both kept and run one at a time. `max_active_runs` and `overlap_policy` change nothing.

**Flags on 2.20.1** (`dagu enqueue --help`): `-p/--params`, `--params-stdin`, `-N/--name`, `--labels` (`--tags` is a deprecated alias), `-u/--queue`, `-r/--run-id`, `--default-working-dir`, `-q/--quiet`, `--profile`, `--no-reuse`, `--trigger-type`, `--schedule-time` (scheduler only), `-c/--config`, `--dagu-home`. `dagu start` has the same set plus `--only`, `--output`, `--outputs-from`, `--from-run-id`.

**Commands and evidence** (DAG `projA/projA.p.yaml` has `params: [KEY=default]`; `projA.u.yaml` declares none):

```
dagu enqueue .../projA.p.yaml -- KEY=value
  -> params="[KEY=value]"; step: KEY_sub=value KEY_env=value DAG_PARAMS_JSON={"KEY":"value"}
dagu enqueue .../projA.u.yaml -- KEY=value2 OTHER=x
  -> step: KEY_sub=value2 KEY_env=value2 DAG_PARAMS_JSON={"KEY":"value2","OTHER":"x"}
dagu enqueue .../projA.u.yaml -- pos_a pos_b
  -> params="[1=pos_a 2=pos_b]"; $1 and $2 empty in the shell; DAG_PARAMS_JSON={"1":"pos_a","2":"pos_b"}
dagu enqueue .../projA.pos.yaml -- a b      (step uses ${1} ${2})
  -> one=a two=b
dagu enqueue .../projA.p.yaml --params 'KEY=viaflag'
  -> KEY_sub=viaflag
dagu enqueue .../projA.p.yaml --name custom-name --labels event=save,src=test --queue light --run-id my-run-1 --default-working-dir <root>/wd -- KEY=full
  -> run name custom-name, run id my-run-1, labels ['event=save','src=test'], KEY=full
```

Per flag:

| Flag | Effect on the queued run |
|---|---|
| `-- KEY=value` / `--params` | works. `${KEY}`, `$KEY`, `DAG_PARAMS_JSON` |
| `--name` | the run's `name` is `custom-name`. `DAG_NAME` is `custom-name`. `sourceFileName` stays `projA.p`. A different name gives a different history and log directory (`logs/custom-name/...`) |
| `--labels a=b,c=d` | stored on the run: `['event=save','src=test']` |
| `--labels` plus DAG labels | merged: `['project=proja','event=save','src=test']` |
| `--queue light` | works. The scheduler log says `queue=light run-id=my-run-1`. The REST run record shows `queue: None`, so the record does not show the override |
| `--run-id my-run-1` | the run uses this id. A second enqueue with the same id and DAG fails: `Error: DAG "projA.slowc" with ID "dup-1" already exists` (exit 1) |
| `--default-working-dir` | **no effect on `enqueue`**: `pwd` was the Dagu work dir `.../dag-run-work/...`, with and without other flags. On `dagu start --default-working-dir <root>/wd` the step ran in `<root>/wd` |

The REST API enqueues by name: `POST /api/v1/dags/projA.p/enqueue` with `{"params":"KEY=api","dagRunId":"api-run-1","labels":["via=api"]}` returned `{"dagRunId":"api-run-1"}` and the step saw `KEY=api`.

**Two quick enqueues of one DAG.** Three enqueues each of `slowa` (defaults) and `slowb` (`max_active_runs: 3`, `overlap_policy: all`), step sleeps 4 s:

```
slowa/slowb  KEY=1  start 21:04:30  end 21:04:34
             KEY=2  start 21:04:36  end 21:04:40
             KEY=3  start 21:04:42  end 21:04:46
```

All six runs were kept, with their own run IDs and parameters. Runs of one DAG ran one after another in both variants (gap of about 2 s between runs, the queue poll step). Reason: a DAG without `queue:` has its own queue named after the DAG, with concurrency 1. Dagu ignores `max_active_runs` for these queues (the schema says deprecated), and `overlap_policy` applies only to catch-up runs (schema text). Different DAGs ran in parallel (`slowa` and `slowb` overlapped).

To let the same DAG run in parallel, define a queue with `max_concurrency: N` in `config.yaml` and set `queue:` on the DAG. I did not need that test.

**What it means for CONCEPT.md.**
- §7 holds: the router can pass event fields as `-- KEY=value` and `--name` is not needed. Steps read `${KEY}`. Prefer declared `params:` in the compiled file, so a typo shows. Dagu accepts an undeclared key silently, and the step then reads an empty or wrong value if the router misspells it. Compile or the library template should declare every key an `on` entry may pass.
- Add to §7: do not use `--name` (it splits the run history by name and breaks "one run index per workflow"). Use `--labels event=<event>,subject=<subject>` to record why a run started. Label values allow only `a-z A-Z 0-9 - _ . /`, and Dagu lowercases them (earlier spike).
- Add to §7: use `--run-id` with an event id, so a repeated event with the same id refuses to double-enqueue. The refusal is loud (exit 1).
- §7 `events.jsonl`: record the id that `dagu enqueue` logs, or the id the router chose with `--run-id`.
- Do not use `--default-working-dir` with `enqueue`. The compiled header's `working_dir` is the way (§5).
- Burst events for one workflow queue up and run serially, so "54 identical reports" is possible. This matches the project note. The router may decide to skip a second enqueue when the same workflow is already queued.
- §13 M6: close with this answer.

---

## Summary

| # | Measurement | Answer | Concept change needed |
|---|---|---|---|
| M1 | Scheduled run waits in a defined queue | Yes. Undefined queue: no wait, no limit | Yes: §5 refuses a `queue:` that `config.yaml` does not define |
| M2 | Missing `working_dir` / `log_dir` | Dagu creates the directory and succeeds (exit 0). Fails only when it cannot create it | Yes: §5 keeps the `path` check and states the reason. Header sets no `name:` |
| M3 | `handler_on` in `base.yaml` | Inherited by every DAG. Handler sees `DAG_NAME`, `DAG_RUN_STATUS`. Run waits for it. A failing handler fails the run. Own handler replaces the same key only | Yes: §7 handler must be detached and never fail. Decide the `handler_on` merge rule |
| M4 | Subdirectory discovery, symlink, duplicates, `group`, `labels` | `<project>.<name>` loads. External symlink changes nothing. Duplicate base name hides both and excludes both from the scheduler. `group` and `labels` work (lowercased). CLI cannot start a subdirectory DAG by name | Yes: §7 router passes the file path (or uses the REST API) |
| M5 | One watchexec over 33 directories | 90 461 watches of 524 288. About 14 s and 15 s CPU at start. 75 MB. About 0.5 s CPU per idle minute. One touch gave one event | Small: §7/§10 note start cost, restart only on path change |
| M6 | `dagu enqueue` parameters | `-- KEY=value` works, read as `${KEY}`. `--name`, `--labels`, `--queue`, `--run-id` work. `--default-working-dir` is ignored by `enqueue`. Quick double enqueue keeps both, run serially | Yes: §7 records `--labels`/`--run-id` use, no `--name`, declared `params:` |

Report path: `/home/andrew/Documents/Projects/devman/.scratch/projects/047-greenfield/MEASUREMENTS.md`
