# STAGE 7 — what was measured while settling the standard workflow set

`STAGE_1_LOG.md` through `STAGE_6_LOG.md` hold stages 1 to 6, in
`.scratch/projects/006-automation-plane/`. This holds stage 7, in the same
shape: the answer, the versions, the exact command, the evidence, and the
charter impact.

`PLAN.md` §1 sets the order. Gate 0 is `I-3` and `I-5`, and nothing in Gate 1
starts until both answer.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705.d407951 (Zokor), hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, `systemd --user` unit `dagu`, API on 127.0.0.1:8080 |
| devenv | **2.1.2** — the version matters, see I-3 |
| devman | 0.3.0, `/nix/store/8m2g8im0…-devman-0.3.0/bin/devman` |
| Registry | `~/.local/share/devman/` — 6 projects, 36 workflows |
| Working tree | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| devman rev | branch `dagu-devenv-automation-eli5`, at `d183fff` |
| Date | 2026-08-23 |

---

## I-3 — Does a one-step workflow's log name the devenv task that failed?

**Answer: yes, and in three separate places.** The name of the failing devenv
task reaches the step's `stderr` file, the DAG-level log, and **Dagu's own
recorded `error` field for the step** — which is the string the UI shows. The
loss `PROPOSAL.md` §1.1 predicts is smaller than predicted: the failing name
does not move from a step label into a log file that nobody opens; it also
lands in the field Dagu already puts on the screen.

**One caveat, and it decides where the rollout tells a developer to look:**
the name appears **0 times** on the step's `stdout` file. On devenv 2.1.2 the
task's own output goes to stdout and devenv's task ledger goes to stderr, and
Dagu files the two separately. A reader who opens `check.*.out` alone sees
what the task printed and never sees which task printed it.

**And one thing nobody asked, which changes the trade:** under a devenv `after`
list the siblings run **concurrently**, so a failing task does not stop the
others. Today's `type: chain` stops at the first failed step. §1.1 trades a
step label for a task name; it also trades fail-fast for fan-out.

### Versions

devenv **2.1.2**, Dagu **2.15.0**, devman **0.3.0**, in `devman` itself.
`groups/base/workflows/check.yaml`'s own header records that devenv 2.2.0 puts
both streams on stderr; **this measurement is 2.1.2 only** and the stream split
below does not carry to 2.2.0.

### The setup — three throwaway tasks, the middle one failing

```nix
# devenv.nix, added for the measurement and removed afterwards
"t7:a".exec = "echo t7-a-ran; true";
"t7:b".exec = "echo t7-b-about-to-fail; exit 3";
"t7:c".exec = "echo t7-c-ran; true";
"t7:all".after = [ "t7:a" "t7:b" "t7:c" ];
```

Two throwaway workflows, because the answer is only meaningful against the
shape it replaces. Both are `.devman/workflows/` files, so that **no file under
`groups/` was touched** — Gate 0 is measurement.

```yaml
# .devman/workflows/_t7-check.yaml — the proposed shape
queue: light
steps:
  - name: check
    run: devenv tasks run -v t7:all
```

```yaml
# .devman/workflows/_t7-chain.yaml — the shape all nine current workflows use
queue: light
type: chain
steps:
  - name: a
    run: devenv tasks run -v t7:a
  - name: b
    run: devenv tasks run -v t7:b
  - name: c
    run: devenv tasks run -v t7:c
```

### Command

```bash
devenv tasks run -v t7:all > /tmp/t7-direct.out 2> /tmp/t7-direct.err; echo "exit=$?"
devenv shell -- true                    # re-project; the guard notices a new override
devman run _t7-check
devman run _t7-chain
```

### Evidence 1 — the direct path

```
exit=1
```

**devenv exits 1, not 3.** The task's own status survives as text, never as a
process exit code:

```
✖ Running t7:b in 15.6ms (failed)
  dep t7:b status=Completed(Failed(15.324036ms, TaskFailure {
      stdout: [(…, "t7-b-about-to-fail")], stderr: [],
      error: "Task exited with status: exit status: 3" })) kind=Succeeded
• Running t7:all
✖ Running t7:all in 16.8µs (dependency failed)
✖ Running tasks in 20.3ms (failed)
  × Some tasks failed
```

That block is on **stderr**. Stdout held three lines and no task name:

```
t7-b-about-to-fail
t7-c-ran
t7-a-ran
```

**`t7:c` ran.** `after = [ "t7:a" "t7:b" "t7:c" ]` declares no order *between*
the three, so devenv started all three at once and `t7:b`'s failure stopped
nothing. Only `t7:all` itself was withheld, as `dependency failed`.

### Evidence 2 — through the plane, one step

```
$ grep 034CMRb6kvoVQnogCpcVH9 .devman/.runs/metadata.jsonl
{"dag":"devman-_t7-check","run_id":"034CMRb6kvoVQnogCpcVH9","attempt":"dae6f1",
 "status":"failed","started_at":"2026-08-23T22:04:43Z","log":"…/devman-_t7-check/…"}
```

**The run reports `failed`.** Then the two streams, counted rather than read:

```
$ cd .devman/.runs/logs/devman-_t7-check/dag-run_20260823_220441Z_034CMRb6kvoVQnogCpcVH9/run_*/
$ grep -c 't7:b' check.*.out ; grep -c 't7:b' check.*.err
0
4
```

**The DAG-level log carries it too**, because Dagu appends a stderr tail to the
failure it records:

```
$ cat dag-run_20260823.180441.365.034CMRb6.log
… level=INFO msg="Step started" step=check
… level=INFO msg="DAG run finished" status=failed
… level=ERROR msg="Failed to execute dag-run" err="exit status 1\nrecent stderr (tail):
    …dep t7:b status=Completed(Failed(…, TaskFailure { …
       error: \"Task exited with status: exit status: 3\" }))…
    • Running t7:all\n✖ Running t7:all in 8.17µs (dependency failed)…"
```

**And Dagu's own status record — the field the UI renders — holds it:**

```
$ tail -1 ~/.local/share/dagu/data/dag-runs/devman-_t7-check/…/status.jsonl
dag status: 2                       # failed
  step: check  error: "exit status 1\nrecent stderr (tail): … dep t7:b …"
contains t7:b -> True | count 1
```

### Evidence 3 — the control, three steps

```
$ tail -1 …/devman-_t7-chain/…/status.jsonl
dag status: 2
  step a | status 4 | error: (none)                     # succeeded
  step b | status 2 | error: exit status 1 …            # failed
  step c | status 3 | error: upstream failed            # not run
```

### The comparison, which is the actual finding

| | three steps, today | one step, proposed |
|---|---|---|
| Dagu step that says `failed` | `b` | `check` |
| Where the failing devenv task is named | the step's own name | `check.*.err`, the DAG log, and Dagu's `error` field |
| Named on the step's `stdout` | n/a | **no** — 0 hits on devenv 2.1.2 |
| Siblings after the failure | `c` is `upstream failed`, never runs | `t7:c` **runs**, concurrently |
| devenv invocations | 3 | 1 |
| Run status in `metadata.jsonl` | `failed` | `failed` |

### Verdict

**Passes.** `PLAN.md` §2 sets the bar at "the log names `t7:b` and the run
reports `failed`". Both hold, and the name reaches one more place than the bar
asks for. **Gate 0's first half is closed and the one-step rule survives.**

`PLAN.md` §8's replacement clause does not fire: `PROPOSAL.md` §1.1's "the
information does not disappear — its location changes" is now a measurement
rather than a prediction, and it understated the result.

### Charter impact

**None yet, and one correction owed to `PROPOSAL.md` rather than to the
charter.** §1.1's cost paragraph is accurate but incomplete, and R-6 should
carry the two lines it is missing:

1. **Which stream.** On devenv 2.1.2 the failing task's name is on **stderr**
   only. §1.1 says "the information … location changes from a step name to a
   log line" without saying which of the two files Dagu writes. The rollout
   line the plan reserves for this is: *read `<step>.*.err`, not `<step>.*.out`.*
2. **Fail-fast is traded too.** A `type: chain` workflow stops at the first
   failed step; a devenv `after` list runs its members concurrently and reports
   every failure. For `check` and `test` this is an improvement — one run
   reports every problem instead of the first — but it is a behaviour change
   §1.1 does not mention, and a repository that needs an order still writes it
   as `tasks."base:test".after = [ "base:check" ]`, which devenv does honour.

Neither weakens the recommendation. Both belong in §1.1 before R-1 ships.
