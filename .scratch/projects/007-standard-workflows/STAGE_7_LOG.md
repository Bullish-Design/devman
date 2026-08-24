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

---

## I-5 — What does an undefined task actually do?

**Answer: it fails loudly, and it names the task.** All three of `PLAN.md` §2's
conditions hold. devenv exits **1**, prints `× Task does not exist: base:check`,
Dagu records the step as **failed**, and `metadata.jsonl` records **`failed`**.

**`PROPOSAL.md` §2's rejection of the null implementation stands**, and so does
§6's no-flag-day argument. **`PLAN.md` §8's replacement clause does not fire:
no bridging alias wave is needed, and no extra line per repository.**

### Versions

devenv **2.1.2**, Dagu **2.15.0**, devman **0.3.0**. Measured in **two**
registered repositories, because the claim is about devenv rather than about
`devman`: `devman` (Python) and `siteman` (no language files, its tasks are its
own shell functions).

### The setup — the real stale-pin window, not an invented name

`devman` defines `base:lint` and has never defined `base:check`. That is exactly
the window `PROPOSAL.md` §6 describes: the group file calls the renamed task and
the repository has not re-pinned its `devenv.nix` yet. No name was invented for
the measurement.

```yaml
# .devman/workflows/_t7-undef.yaml — throwaway, deleted afterwards
queue: light
steps:
  - name: check
    run: devenv tasks run -v base:check
```

### Command

```bash
devenv tasks run -v base:check > /tmp/t7-undef.out 2> /tmp/t7-undef.err; echo "exit=$?"
devenv shell -- true
devman run _t7-undef
tail -1 .devman/.runs/metadata.jsonl
cd /home/andrew/Documents/Projects/siteman && devenv tasks run -v base:check; echo "exit=$?"
```

### Evidence 1 — devenv, directly, in two repositories

```
devman   exit=1   stdout 0 bytes   stderr: × Task does not exist: base:check
siteman  exit=1   stdout 0 bytes   stderr: × Task does not exist: base:check
```

The message is devenv's, not the plane's, and it is one line. Note that
**stdout is empty** — the same stream split I-3 found. There is nothing to read
on stdout because the task never started.

### Evidence 2 — Dagu's step status

```
$ tail -1 ~/.local/share/dagu/data/dag-runs/devman-_t7-undef/…/status.jsonl
dag status: 2                                  # failed
  step check | status 2                        # failed
  error field length: 1018
  contains "Task does not exist": True
  contains "base:check":          True
```

The recorded `error` field — the string Dagu's UI renders — ends on the message:

```
Loaded task config
  × Task does not exist: base:check
```

### Evidence 3 — `metadata.jsonl`

```
{"dag":"devman-_t7-undef","run_id":"034CMXJBlEnFx8d2tV3NdX","attempt":"04a01f",
 "status":"failed","started_at":"2026-08-23T22:08:27Z","log":"…"}
```

The DAG-level log carries the message once as well.

### Evidence 4 — the other half of §6, by grep rather than by argument

§6 rests on "only one workflow is scheduled, and it calls no repository task".
That is true, and it is one command:

```
$ grep -l 'devenv tasks run' groups/*/workflows/*.yaml    # 8 of 9
$ for f in groups/*/workflows/*.yaml; do
    grep -q 'devenv tasks run' "$f" || echo "$f"; done
  groups/base/workflows/maintain.yaml                      # the 9th

$ grep -n '^schedule:' groups/base/workflows/maintain.yaml
68:schedule: "5 0 * * *"
```

**`maintain` is both the only scheduled workflow and the only one that calls no
repository task.** A stale pin cannot break it.

### Verdict

**Passes.** `PLAN.md` §2 sets the bar at "devenv exits non-zero, names the task,
and `metadata.jsonl` records `failed`". All three hold, in two repositories.
**Gate 0's second half is closed.**

### Charter impact

**None**, and one boundary on §6 worth writing down before wave 1 rather than
finding in it.

**§6's "no automatic run breaks" is true of the *schedule* and not of the
*watcher*.** `format` is fired automatically by the watcher and it **does** call
a repository task (`python-format:fmt`). The claim survives only because the
watcher reaches exactly one repository: `devman` is the only taker of
`python-format` in the whole inventory (`PROPOSAL.md` §4), and `devman` owns the
group files, so it renames the group and the task in the same sitting.

Two consequences for the refactor, neither of them new work:

1. **R-1's group rename and `devman`'s own `devenv.nix` edit are one commit.**
   Not a wave — the same sitting. The group rename `python-format` → `format`
   changes the group *name*, so a stale `groups = [ … "python-format" … ]`
   cannot enter its shell at all (`PLAN.md` §0.2). There is no silent window
   here, only an evaluation failure, which is I-6's subject.
2. **The rule generalises past this stage.** A repository can be re-pinned
   safely ahead of its task rename **only while every automatically triggered
   workflow calls no repository task**. Today that holds. A future group that
   ships a scheduled or watched workflow calling a task would break it, and the
   place to say so is §6 rather than a later stage's surprise.

---

## Gate 0 — closed

| | Investigation | Bar (`PLAN.md` §2) | Result |
|---|---|---|---|
| I-3 | a one-step log names the failing devenv task | the log names `t7:b`, the run reports `failed` | **passes**, and the name reaches three places |
| I-5 | an undefined task fails loudly | devenv exits non-zero, names the task, `metadata.jsonl` records `failed` | **passes**, in two repositories |

**`PLAN.md` §8's stop rule does not fire.** Neither failure clause applies, so
`PROPOSAL.md` §1.1 is not rewritten. **The hinge survives, and Gate 1 — I-6 and
S-3 — may begin.**

`PROPOSAL.md` carries three small debts, all recorded above and all additive.
They belong in R-6, not in a stop-and-rewrite:

| Section | Debt |
|---|---|
| §1.1 | say the failing name is on **stderr**, not stdout |
| §1.1 | say the one-step rule also trades `type: chain`'s fail-fast for devenv's concurrent fan-out |
| §6 | bound "no automatic run breaks" to the schedule; the watcher fires `format`, which does call a task |

### What was left on the machine

```
$ devman doctor
devman doctor — 6 projects, 36 workflows
ok  plane / queues / validate / queue names / literal dir / shadowing /
    stale entries / run output / projection / handlers / cross-repo / watcher
Nothing to report.                                                   exit 0

$ git status --short
                                                            (clean)
```

Back to 36 workflows from the 38 the measurement projected. The three
throwaway workflow files are deleted and re-projected; `dags/` holds no `_t7`
link. `devenv.nix` is back at `d183fff` — the `t7:*` tasks existed for about
four minutes, on purpose.

**Three run records are deliberately left in place**, because they are the
evidence this entry quotes:

```
devman-_t7-check  failed
devman-_t7-chain  failed
devman-_t7-undef  failed
```

They sit in `.devman/.runs/metadata.jsonl` and under `.devman/.runs/logs/`,
which git ignores and `hist_retention_days` prunes in seven days.

**No file under `groups/`, `modules/` or `src/` was changed. Gate 0 was
measurement.**

---

## I-6 — Confirm the unknown-group throw, and see what a developer sees

**Answer: the shell refuses, and the message is the last line on the screen.**
Nix ends an evaluation failure with `error: <the message>`, so the throw
`PLAN.md` §0.2 read in the source arrives at the bottom of the trace, where the
eye already is. 292 lines of trace precede it and none of them has to be read.

**Passes.** `PLAN.md` §3's bar is "the shell refuses and the message is
legible". Both hold.

### Versions

Measured against the rev a **registered repository actually pins**, not against
`HEAD`: `siteman` pins `fb78a99`, and `modules/devenv.nix:62` is byte-identical
there and at `d183fff`. devenv 2.1.2, Nix 2.34.7.

### The setup — a throwaway clone of a registered repository

`siteman`, copied to `/tmp/s7-i6`. Three edits, and two of them exist only so
that a *successful* evaluation could not reach the real registry:

```nix
project    = "s7-i6";                        # was "siteman"
registryDir = "/tmp/s7-reg";                 # was the default $HOME/.local/share/devman
groups     = [ "base" "not-a-group" ];       # was [ "base" ]
```

### Command

```bash
cp -a ~/Documents/Projects/siteman /tmp/s7-i6
cd /tmp/s7-i6 && rm -rf .devenv .devman/.runs
devenv shell -- true > /tmp/s7-i6.out 2> /tmp/s7-i6.err; echo "exit=$?"
```

### Evidence

```
exit=1
stdout bytes: 0
stderr lines: 292
```

The first line of the trace is devenv's, and it says nothing useful:

```
✖ Evaluating shell in 4.47s (failed)
  × Failed to get drvPath from shell derivation:
  … while calling the 'derivationStrict' builtin
```

The last line of the trace is the module's, and it says everything:

```
line 291 of 292:
error: devman: group 'not-a-group' does not exist.
       There is no /nix/store/sqxmkgpgrc8hmw42x9ym83qpw0k8wi3k-source/groups/not-a-group.
```

The trace also quotes the throw in context at line 285, with the file and line
number of `modules/devenv.nix:62`.

**Nothing was written.** `/tmp/s7-reg` did not exist after the run: the throw is
an evaluation failure, so `enterShell` never ran and no registry entry, `dags/`
link or `.devman/.runs/` tree was created.

### The one weakness, and it is small

**The path in the message is a store path, not the developer's own file.**
`/nix/store/sqxmk…-source/groups/not-a-group` is literally correct — the groups
root *is* the pinned input — but it points at a directory the developer cannot
edit and does not name the line of their own `devenv.nix` that caused it. The
group name is in the message, which is the part that matters, and the trace
above it names `modules/devenv.nix:62`.

**This does not justify changing the throw.** A developer who reads
`group 'not-a-group' does not exist` knows which word they typed wrong.

### Verdict and what it decides

**Passes.** `PLAN.md` §3 says a failure here would make the tombstone
mandatory rather than preferred. It did not fail, so the tombstone is decided
on its own merits by S-3 — which is below, and which recommends shipping it
anyway.

**R-3 keeps the throw.** `PLAN.md` §6's decision is settled in the direction it
predicted: the throw is correct for a misspelled group, it is legible, and S-3
shows the tombstone handles the deletion case, so the two do not compete.

### Charter impact

**None.** §0.2 of `PLAN.md` read the source correctly and this confirms it on a
real repository.

---

## S-3 — The tombstone group, three variants

**Answer: a tombstone works, and it must contain a file.** An empty directory
evaluates, ships nothing and produces no trigger — but **git cannot carry an
empty directory**, so the only tombstone that survives a `git+https` pin is
`PLAN.md`'s second variant: a directory holding a `README.md` and nothing else.
The third variant is the trap the plan predicted, and it is real.

**Passes**, with one correction to `PLAN.md` §3's recommendation: ship the
tombstone as **a directory with a README**, never as an empty directory.

### Versions

devenv 2.1.2, Nix 2.34.7, devman 0.3.0, Dagu 2.15.0. Three throwaway devman
source trees built with `git archive HEAD`, three throwaway consumer
repositories, and a **throwaway registry at `/tmp/s7-reg`** — the module's own
`registryDir` option, so the real registry was never a participant.

### The setup

```bash
for v in v1 v2 v3; do
  mkdir -p /tmp/s7-devman-$v && git archive HEAD | tar -x -C /tmp/s7-devman-$v
done
rm -rf /tmp/s7-devman-v1/groups/python && mkdir -p /tmp/s7-devman-v1/groups/python
rm -rf /tmp/s7-devman-v2/groups/python/workflows
rm -rf /tmp/s7-devman-v3/groups/python-format/workflows \
       /tmp/s7-devman-v3/groups/python-format/README.md
```

Each consumer is four lines of `devenv.nix` and a `path:` input with
`flake: false`:

```nix
devman = {
  enable = true;
  project = "s7v1";                 # s7v2, s7v3
  registryDir = "/tmp/s7-reg";
  groups = [ "base" "python" ];     # [ "base" "python-format" ] for v3
};
```

### Variant 1 — an empty directory

```
$ cd /tmp/s7-rv1 && devenv shell -- true; echo "exit=$?"
exit=0
```

**It evaluates and the shell enters.** The module takes
`modules/devenv.nix:63`'s existing escape — the group exists, `workflows/` does
not, so `groupFiles` returns `{ }`.

```
$ ls /tmp/s7-reg/projects/s7v1/workflows/
check.yaml  full-test.yaml  maintain.yaml  review.yaml  validate.yaml

$ python3 -m json.tool /tmp/s7-reg/projects/s7v1/metadata.json
  "groups":    ["base", "python"],
  "workflows": { five entries, every one "group": "base" },
  "triggers":  null
```

**Exactly `base`'s five workflows, and nothing else.** The entry records
`python` as a group the repository takes, and records not one file from it.
Five `dags/` links, all pointing at this project's own files.

### The thing that kills variant 1 anyway

```
$ cd /tmp/s7-devman-v1 && git init -q . && git add -A groups/
$ git diff --cached --name-only | grep '^groups/python/' | wc -l
0
$ git status --porcelain groups/python | wc -l
0
```

**git carries zero paths under an empty directory.** A repository pinning
`git+https` fetches a source tree in which `groups/python/` does not exist, so
`builtins.pathExists` is false and it gets I-6's throw — the exact flag day the
tombstone exists to prevent. **An empty-directory tombstone is a tombstone that
only works in the checkout that created it.**

### Variant 2 — a directory holding only `README.md`

```
$ cd /tmp/s7-rv2 && devenv shell -- true; echo "exit=$?"
exit=0

$ ls /tmp/s7-reg/projects/s7v2/workflows/
check.yaml  full-test.yaml  maintain.yaml  review.yaml  validate.yaml

groups   : ['base', 'python']
workflows: {'check': 'base', 'full-test': 'base', 'maintain': 'base',
            'review': 'base', 'validate': 'base'}
triggers : None
local    : []
```

**Byte-for-byte the same outcome as variant 1, and it is git-shippable.**
`README.md` is inert, as §7.2 promises: the module's filter is
`kind == "regular" && hasSuffix ".yaml"`, so nothing named `README.md` can be
projected, and nothing was.

**This is the variant R-1 ships.**

### Variant 3 — a stale `triggers.toml` with no `workflows/`

**The trap is real.** Evaluation succeeds, `base`'s five workflows project, and
the registry entry carries a trigger pointing at a workflow that does not exist:

```
$ ls /tmp/s7-reg/projects/s7v3/workflows/
check.yaml  full-test.yaml  maintain.yaml  review.yaml  validate.yaml

groups   : ['base', 'python-format']
workflows: ['check', 'full-test', 'maintain', 'review', 'validate']
triggers : {"group": "python-format", "map": {"**/*.py": "format"}}
```

**`format` is in `triggers`. `format` is not in `workflows`.**

**`devman doctor` does not object**, and that is the second half of the finding:

```
$ devman --registry /tmp/s7-reg doctor
devman doctor — 3 projects, 15 workflows
ok  validate       15 projected workflows load
..  watcher        s7v3: **/*.py -> format  [python-format]
                   the watcher has never run — no state file
Nothing to report.                                                   exit 0
```

The watcher check prints the mapping and never compares `format` against the
project's own workflow set. `src/devman/doctor.py`'s `check_watcher` has no such
comparison in it.

**What a save would actually cost, measured by issuing the dispatcher's own
command.** `watch.py`'s `dispatch` runs
`devman run <workflow> --project <project>` per matched path:

```
$ devman --registry /tmp/s7-reg run format --project s7v3
devman: project 's7v3' has no workflow named 'format'
devman:  it projects: check, full-test, maintain, review, validate
exit=1
```

**So the failure is loud at the point of use and quiet everywhere else.** Every
`.py` save in a stale repository forks a `devman run` that refuses, `watch.py`
records `refused (1)` in `fired.jsonl`, and the developer — who is editing, not
reading the journal — sees nothing. Nothing is enqueued and no Dagu run reports
success, so this is **not** the silent-success shape §15.7 fears. It is waste
plus an unread complaint.

### The variants, side by side

| Variant | Evaluates | Projects | Trigger | Git-shippable | Verdict |
|---|---|---|---|---|---|
| directory removed entirely (I-6) | **no — throws** | — | — | yes | the flag day |
| empty directory | yes | `base` only | none | **no** | works, cannot ship |
| directory + `README.md` | yes | `base` only | none | yes | **ship this** |
| directory + stale `triggers.toml` | yes | `base` only | **dangling** | yes | a refused dispatch per save |

### Verdict

**Passes.** `PLAN.md` §3's bar is "an empty directory evaluates, ships nothing,
and produces no trigger". It does. One correction and one addition:

- **The tombstone is a directory with a `README.md`**, because git cannot carry
  an empty one. `PLAN.md` §6's R-1 row already says "tombstone — empty, **no
  `triggers.toml`**"; the word "empty" has to become "a README and nothing
  else".
- **`groups/python-format/`'s tombstone must drop its `triggers.toml`**, which
  the plan predicted and which variant 3 now demonstrates rather than asserts.

### What this decides

**R-1 ships tombstones**, and `PLAN.md` §3's recommendation stands: keep them
until one full rollout after wave 4, then delete them. The cost is two
directories and two READMEs.

**R-3 keeps the throw** (with I-6). The tombstone handles deletion; the throw
handles a misspelling. They do not compete.

### One new `doctor` check worth writing, and why it is not a heuristic

Variant 3 found a gap `OPEN_QUESTIONS` does not list: **nothing checks that a
trigger's workflow name is a workflow the project projects.**

This is **not** the same kind of proposal as R-4a. R-4a compares a TOML glob
list against a `find` expression, which is a heuristic, and `CONCEPT.md` §15.7
says the plane grows no heuristics. This one is exact set membership inside a
single registry entry:

```python
entry.workflow in proj.workflows      # both are already in metadata.json
```

It costs no fork, reads no repository, and has one true answer. **Proposed as
R-4d, gated on nothing**, and cheap enough to ride with whichever of R-4a/b/c
ships first.

### Charter impact

**None.** The tombstone uses `modules/devenv.nix:63`'s existing escape, which
`CONCEPT.md` §7.4 already describes as a group that may ship no workflows. No
section moves.

---

## Gate 1 — closed

| | Item | Bar (`PLAN.md` §3) | Result |
|---|---|---|---|
| I-6 | what a developer sees on an unknown group | the shell refuses, the message is legible | **passes** — refuses, and the message is the last line |
| S-3 | the tombstone group, three variants | an empty directory evaluates, ships nothing, produces no trigger | **passes**, with one correction: it needs a README |

**Gate 2 may begin.** R-3 keeps the throw; R-1 ships tombstones with READMEs
and no `triggers.toml`.

---

## Gate 2 — how it was built

The four Gate 2 spikes write real files, so they were built on a **spike
branch**, `spike/007-gate-2`, cut from `d183fff`. Nothing they produce is on
`dagu-devenv-automation-eli5` except this log. R-1 adopts from that branch
rather than re-typing it.

`devman` itself follows the local tree — it imports `./modules` and `../groups`
directly rather than pinning a rev — so building the content on that branch and
entering the shell makes the **installed plane** run it. That is what makes S-6
and S-5 real runs rather than throwaway-instance runs. The other five
registered repositories pin `fb78a99` by `git+https` and were not affected at
any point.

---

## S-2 — The five workflow files, validated

**Answer: nine workflows in four groups become five in three, and all five
load.** `nix build .#checks.x86_64-linux.groups-validate` passes, and the list
of files it validated is also the proof that both tombstones ship nothing.

### Versions

Dagu 2.15.0 (the check builds its own copy from `nix/dagu.nix`), Nix 2.34.7.
Spike branch `spike/007-gate-2` at `45ebbc7`.

### What was written

| Action | File |
|---|---|
| rewrite | `groups/base/workflows/check.yaml` — one step, `base:check`, **no `type: chain`** |
| add | `groups/base/workflows/test.yaml` — one step, `base:test`, queue `normal` |
| rewrite | `groups/base/workflows/maintain.yaml` — the `doctor` step goes, the `params:` block **stays** |
| rename | `groups/python-format/` → `groups/format/`, task `python-format:fmt` → `format:fmt` |
| rewrite | `groups/release/workflows/release.yaml` — the gate reads `<project>-test` (S-6) |
| delete | `base/validate.yaml`, `base/full-test.yaml`, `base/review.yaml` |
| delete | `python/workflows/` |
| tombstone | `groups/python/README.md` and `groups/python-format/README.md`, each alone in its directory |

**The two things `PLAN.md` §4 said to get right, both got right and both
verified by the check's output.**

1. `maintain.yaml` keeps `params: [DEVMAN_PROJECT_DIR: "", KEEP_DAYS: "7"]`.
   Dagu rejects a parameter a DAG did not declare and `devman run` always passes
   the directory variable, so removing the `doctor` step must not remove the
   block. It did not, and `maintain` validated.
2. `check.yaml` and `test.yaml` declare **no** `type: chain`. One step needs no
   order, and the key existed only to stop two devenv invocations contending
   for one devenv state directory. Both validated without it.

`maintain.yaml` also lost `type: chain`, for the same reason — it is down to one
step.

### Command

```bash
nix build --no-link --print-build-logs .#checks.x86_64-linux.groups-validate
```

(`nix flake check .#checks…` is not a valid invocation — `nix flake check`
takes no fragment. `nix build` on the same attribute is what runs it.)

### Evidence

```
devman-groups-validate> validating base/workflows/check.yaml
devman-groups-validate> validating base/workflows/maintain.yaml
devman-groups-validate> validating base/workflows/test.yaml
devman-groups-validate> validating format/workflows/format.yaml
devman-groups-validate> validating release/workflows/release.yaml
exit=0
```

**Five files, and only five.** `groups/python/` and `groups/python-format/`
contributed nothing to a glob of `groups/*/workflows/*.yaml`, which is S-3's
tombstone finding restated by a check that already existed.

### The size, which the proposal claimed and did not quantify

| | Files | Lines | Executable lines |
|---|---|---|---|
| before, nine workflows | 9 | 488 | **216** |
| after, five workflows | 5 | 399 | **123** |
| change | −4 | −18% | **−43%** |

"Executable lines" is every line that is not a comment and not blank.

**The honest reading is that the shrink is in the executable half, not in the
file.** Total lines fell 18% because the new files carry *more* commentary per
line of YAML — `check.yaml` is 4 executable lines under 28 of explanation. The
claim in `PROPOSAL.md` §1.1 that the group files get shorter is true of the part
a reader has to hold in their head, and R-6 should say which half it means.

### Charter impact

**None.** `groups-validate` is an existing check and this is content.

---

## S-6 — The `release` gate against the renamed `test`

**Answer: the rename is safe, and all four cases behave.** The gate refuses when
there is no record, refuses on `partially_succeeded`, and opens on a real
`succeeded` line — and the adversarial case the rename creates does not fire,
because the anchor that fixed the original bug also fixes this one.

**`PLAN.md` §8's replacement clause does not fire.** The gate keeps deriving the
project from `${context.dag.name}`; it does not need an explicit parameter, and
the rename is not dropped.

### Versions

Dagu 2.15.0, devenv 2.1.2, devman 0.3.0, the installed plane. `devman` adopted
the renamed content with the three edits `PROPOSAL.md` §6 tables for wave 1
(`groups = [ "base" "format" "release" ]`, `base:lint` → `base:check`,
`python-format:fmt` → `format:fmt`) and re-projected:

```
$ ls ~/.local/share/devman/projects/devman/workflows/
agent-review  bench-entry  check  format  maintain  release  stack-validate  test
```

`validate`, `full-test` and `review` are gone from the projection, which is the
first time the deletion has been real anywhere.

### The one line that changed

```diff
-      want="\"dag\":\"${me%-*}-validate\""
+      want="\"dag\":\"${me%-*}-test\""
```

### The adversarial case, and why it does not fire

`-test` is a suffix of a workflow name that existed until this stage —
`full-test` — so `<project>-full-test` ends in the same characters the gate now
wants. Tested directly on the construct rather than argued:

```
$ want='"dag":"devman-test"'
  vs devman-test        -> 1 match
  vs devman-full-test   -> 0
  vs devman-stack-test  -> 0
  vs foo-test-test      -> 0
  vs other-test         -> 0
```

**The anchor is what saves it.** `grep -F` looks for the whole string
`"dag":"devman-test"`, and in `"dag":"devman-full-test"` the character after
`devman-` is `f`. That is the same anchor that stopped `devman-stack-validate`
matching in stage 4's S5 — the fix for the original bug covers the new hazard
without an edit.

**A project whose own name ends in `-test` is also safe**, because the project
is derived from *this* run's DAG name and never from the wanted one:

```
devman-release     -> project 'devman'    -> wants 'devman-test'
nix-paseo-release  -> project 'nix-paseo' -> wants 'nix-paseo-test'
foo-test-release   -> project 'foo-test'  -> wants 'foo-test-test'
a-b-c-release      -> project 'a-b-c'     -> wants 'a-b-c-test'
```

The file's existing limit is unchanged and still stated in it: the derivation
assumes **this workflow's own** file name has no hyphen.

### The status match, against every status Dagu writes

```
succeeded            -> OPENS
partially_succeeded  -> refuses
failed               -> refuses
cancelled            -> refuses
queued               -> refuses
```

### The three cases, run for real

**Case 1 — no `<project>-test` line.** The natural state: `metadata.jsonl` held
81 `devman-format` lines, 9 `devman-maintain`, one `devman-validate` and no
`devman-test` at all.

```
$ devman run release            # run 034COXSxycNngIgJE3INfT
devman-release failed

## gate
- clean tree: yes
- last test: **NONE RECORDED** for `devman-test` — refusing. Run `devman run test` first

steps: gate=failed  build=skipped  record=skipped
```

**Case 2 — a `partially_succeeded` line.** One synthetic line appended to
`metadata.jsonl`, copied from a real `devman-check` record with the dag, run id
and status changed.

```
$ devman run release            # run 034COYghasrAUGIWPFAZDu
devman-release failed

## gate
- clean tree: yes
- last test: **NOT SUCCEEDED** — refusing.
  `{"dag":"devman-test",…,"status":"partially_succeeded",…}`
```

> **One measurement error, recorded because it is a trap for anybody repeating
> this.** The first injection used `json.dumps` defaults, which write
> `{"dag": "devman-test"` **with a space**. Real records are compact. The gate's
> `grep -F` did not match it and the run reported `NONE RECORDED` — case 1's
> answer, wearing case 2's clothes. The line was rewritten with
> `separators=(',', ':')` and the case then behaved. **A synthetic record must
> be byte-shaped like a real one or it measures the wrong thing.**

**Case 3 — a real `succeeded` line, clean tree.**

```
$ devman run test               # run 034COZ3faERcyzblfMzq18 — 45 s, mostly cached
devman-test: succeeded

$ devman run release            # run 034COaXpTmDqPvfYfAyULs
devman-release: succeeded

## gate
- clean tree: yes
- last test: succeeded — `{"dag":"devman-test","run_id":"034COZ3faERcyzblfMzq18",…,"status":"succeeded",…}`

## built
- head: `0376b9a304e22dc1ce1f7919b6353c286802b87f`
- describes as: `0376b9a`
devman -> /nix/store/5vk1chzi4rxd0vwsa2dymzj7ppakq793-devman-0.3.0

steps: gate=succeeded  build=succeeded  record=succeeded
```

**The gate opened on the renamed line, the build ran, and the artifact
appeared.** This is `PROPOSAL.md` §8's wave-1 proof for `observantic`, taken
early in `devman`.

### Verdict

**Passes**, all four cases. `PLAN.md` §4's three plus the adversarial one.

### Charter impact

**None.** The gate's own file already documents its derivation and its limit;
the rename adds one paragraph to that file explaining why `full-test` does not
collide, so a later reader does not have to re-derive it.

---

## S-5 — `plane-report`, run once by hand and once by the daemon

**Answer: it works, it costs about 3 seconds, and one of its three questions
found a bug in a shipped file.** The workflow runs `devman doctor` once for the
machine, writes a report, and is dispatched by Dagu's own scheduler.

**The bug is the finding.** `base/maintain`'s `doctor` step, as shipped since
stage 4, would have written a **truncated report** on any night `doctor` had a
finding — which is the only night it mattered. It never fired because `doctor`
has never had a finding on a scheduled night.

### Versions

Dagu 2.15.0, devenv 2.1.2, devman 0.3.0, the installed plane. 6 projects.

### Question 1 — does a workflow whose step fails still write its report?

**Not with the obvious shape, and the reason is that Dagu already sets `-e`.**

`PLAN.md` §4 offers two candidate answers: copy `base/review`'s
`continue_on: {failure: true}`, or write the report before the exit. **Both are
wrong for this file, and the second is wrong for a reason nothing in six stages
had measured.**

**Probe: what flags does a step's script run with?**

```yaml
run: |
  set -u
  { echo "shell: $0"; echo "flags: $-"; } > "$out"
  sh -c 'exit 3' >> "$out" 2>&1
  echo "AFTER-FAILING-COMMAND rc=$?" >> "$out"
```

```
shell: /tmp/dagu_script-745413007.sh
flags: ehuB
```

**`e` is in the flag list.** `AFTER-FAILING-COMMAND` never appeared. Dagu runs
the script with `set -e` already on, so a bare failing command aborts the whole
step at that line.

**What that does to the report**, measured with `plane-report`'s control flow
and a command guaranteed to fail:

```
# probe — devman-_s5-fail
```
pretend findings
```

— and that is the whole file. The closing fence and the verdict line are
missing, because the script died at the failing command.

**The fix, measured:**

```diff
-      devman doctor >> "$report" 2>&1
-      rc=$?
+      rc=0
+      devman doctor >> "$report" 2>&1 || rc=$?
```

```
# probe — devman-_s5-fail
```
pretend findings
```

- doctor exit: 3

run status: failed
```

**A complete report and a `failed` run, together.** That is the property the
question was asking for. `continue_on` is rejected on its own terms: it exists
so a *chain* can finish, one step has nothing to keep going for, and it would
report `partially succeeded` — which says the workflow half worked when the
plane is in fact unhealthy.

> **This is a defect in `groups/base/workflows/maintain.yaml` as shipped**, and
> R-1 fixes it by deleting the step. Any repository that shadowed `maintain` to
> keep the `doctor` step carries the same latent truncation.

### Question 2 — does it need `DEVMAN_PROJECT_DIR`?

**It holds `DEVMAN_PROJECT_DIR`, and that is correct.** §11's rule binds a
workflow that *triggers* other workflows; `plane-report` runs one command that
reads the registry and triggers nothing. `doctor`'s own check is the proof:

```
ok  cross-repo     1 workflows trigger others, all name DEVMAN_SELF_DIR
```

**Still 1** — `stack-validate`. `plane-report` does not appear, so
`Workflow.triggers_other_dags()` does not class it as a parent and the
projection gave it the ordinary variable.

### Question 3 — what does it cost?

```
$ devman doctor        # five runs, 6 projects, 34 workflows
2.72  2.91  2.59  2.67  2.62 s        mean 2.70 s, range 2.59–2.91
```

The workflow around it adds under a second:

```
scheduled run 034COl5xURxTJaFKEaQ2on   3.0 s
scheduled run 034COmcI6fQGMd6F72JUs8   2.0 s
```

**About 3 seconds at 6 projects.** That is `I-2a`'s first data point and the
number its curve extrapolates from.

### The proof — one manual run and one scheduled run

**Manual:**

```
$ devman run plane-report              # 034COfFf3PxrqGuyjyizQM
devman-plane-report: succeeded
```

The report holds `doctor`'s whole output inside a fenced block and ends
`- doctor exit: 0`.

**Scheduled**, with the expression temporarily at `* * * * *` in the shape
stage 6's S3 used:

```
$ journalctl --user -u dagu | grep "Dispatching planned run"
19:39:00 … msg="Dispatching planned run" dag=devman-plane-report scheduleType=Start
19:40:00 … msg="Dispatching planned run" dag=devman-plane-report scheduleType=Start

$ grep devman-plane-report .devman/.runs/metadata.jsonl | tail -2
  034COl5xURxTJaFKEaQ2on  succeeded  2026-08-23T23:39:00Z
  034COmcI6fQGMd6F72JUs8  succeeded  2026-08-23T23:40:00Z
```

**Dagu says who triggered each one**, and the contrast is the evidence:

```
manual run  : triggerType 2 | scheduleTime None
scheduled   : triggerType 1 | scheduleTime 2026-08-23T19:40:00-04:00
```

The expression is back at `20 0 * * *` — fifteen minutes after `maintain`, so
the nightly pruning finishes before the plane is asked how it is.

### Verdict

**Passes**, all three questions, and question 1 returned a defect rather than a
confirmation.

### Charter impact

**None**, and one line owed to a group file rather than to the charter:
`groups/base/README.md` describes `maintain` as the workflow that runs
`devman doctor`. R-1 rewrites that README anyway.

---

## S-5a — A bug found while running S-5: an edited override does not re-project

**Answer: editing a file in `.devman/workflows/` does NOT reach Dagu at the
next shell entry.** `STAGE_6_LOG.md` S4 says it does. It does not, and the
comment in the module says exactly why.

This was found the hard way: the corrected `plane-report` was edited, the shell
was re-entered, and the run that followed executed **the previous version** —
it wrote a report under the old file name.

### The mechanism, and it is one comment

```
$ sed -n '311,314p' modules/devenv.nix
  # `@LOCAL@` is the set of names in
  # `.devman/workflows/`, which is what makes the guard notice a repo adding or
  # removing an override. It does not need to notice an *edit*: the projection
  # is a symlink, so an edited file is already what Dagu reads.
```

**"The projection is a symlink" stopped being true at stage 6.** The projection
is now a generated copy, so an edited source is *not* what Dagu reads — but the
guard was never widened, and the entry it compares still records only names:

```
$ python3 -m json.tool ~/.local/share/devman/projects/devman/metadata.json
  "local": ["agent-review","bench-entry","plane-report","stack-validate"],
  "plan":  "/nix/store/2ksg5n9…-devman-project-devman"
```

Neither field changes when a `.devman/workflows/` file is edited in place, so
the guard sees a matching entry and forks nothing.

### Evidence

```
$ grep -n 'rc=0' .devman/workflows/plane-report.yaml
89:      rc=0
$ grep -n 'rc=0' ~/.local/share/devman/projects/devman/workflows/plane-report.yaml
(nothing)
```

Two files were stale at once — `plane-report.yaml` and a throwaway probe — after
an ordinary `devenv shell -- true`.

### The workaround, measured

```bash
rm -f ~/.local/share/devman/projects/<project>/metadata.json
devenv shell -- true
```

The guard finds no entry on disk, so it re-projects everything. Verified: both
files matched their sources afterwards.

Adding or removing any file in `.devman/workflows/` also works, because that
changes `local`.

### Why it matters beyond this spike

**It is a correctness bug in the shipped plane, not a spike artefact.** A
developer who edits their own `.devman/workflows/check.yaml` and re-enters the
shell gets the old workflow, silently, with no message and a `doctor` that
reports nothing wrong — `doctor` compares the projection against the *group*
version it shadows, never against the repository's own source.

**It is not in Gate 2's scope and it is not fixed here.** Recorded as a defect
for the refactor:

| | |
|---|---|
| Where | `modules/devenv.nix`, the `entryTemplate` guard, and the stale comment above it |
| Fix | fold a content hash of `.devman/workflows/*.yaml` into `@LOCAL@`, or drop the guard's fast path for repositories that have any override |
| Cost | one `$(<file)` per override on every shell entry, against §5.2's "fork nothing on the common path" — so the hash has to be built with bash parameter expansion, not `sha256sum` |
| Also | `STAGE_6_LOG.md` S4's "an edit to it reaches Dagu at the next shell entry" is wrong and should be corrected where it stands |

**Proposed as R-8**, gated on nothing, and it should ship before wave 2 — waves
2 and 3 add repositories that will write their own overrides.

### Charter impact

**None yet.** §9.3 says the projection is reconstructable by entering the shell,
which remains true — the bug is that entering the shell does not always
*reconstruct* it. If R-8 changes the guard, §5.2's cost budget is the section to
re-check.

---

## S-4 — The format glob/hash hazard, seen once on purpose

**Answer: the failure is real, it is completely invisible, and it is
byte-identical to a correct loop-break in every field the plane records.**

**And that last fact is what decides `OPEN_QUESTIONS` §4.** The check
`PLAN.md` §4 proposes — compare a `triggers.toml` glob list against the hash's
`find` expression — **should not be written**, because it is the heuristic
§15.7 forbids. A different, exact check is proposed instead, and the reasoning
is below.

### Versions

Dagu 2.15.0, devenv 2.1.2, devman 0.3.0, watchexec via the installed
`devman-watch` unit. The real watcher, the real plane, the real repository.

### The setup — a group that widens the glob and not the hash

```toml
# groups/s7-widen/triggers.toml — throwaway, deleted afterwards
"**/*.py"  = "format"
"**/*.nix" = "format"
```

It ships **no** `workflows/`. Group trigger resolution is whole-file and
last-group-wins, so `devman` taking `[ "base" "format" "release" "s7-widen" ]`
replaces the mapping while `groups/format/workflows/format.yaml` still supplies
the workflow — whose precondition hashes only `*.py`. That is the widening rule
broken in the smallest possible way, which is also the most likely way somebody
breaks it.

```
$ devman doctor
ok  watcher        devman: **/*.nix, **/*.py -> format  [s7-widen]
```

### Command

```bash
devman run format                       # establish .devman/.runs/.format.hash
cat > s7-probe.nix <<'EOF'
{   pkgs ,  ... }:{
  probe    =   "s7-4"  ;
}
EOF
```

### Evidence — what saving a `.nix` file produced

```
format runs before: 82
format runs after:  83

run 034COrZIMgZEqCTjS8lzgZ   succeeded
  dag status  : 4    (succeeded)
  step format : 5    (skipped)
  step error  : ''
```

**The file the save named is untouched**, byte for byte as written.

**The watcher recorded a success:**

```
{"at":"2026-08-23T19:43:15.313-04:00","project":"devman","workflow":"format",
 "path":"…/s7-probe.nix","outcome":"enqueued"}
```

**`devman doctor` reports nothing wrong — and displays the firing as evidence
of health:**

```
ok  watcher        devman: **/*.nix, **/*.py -> format  [s7-widen]
                   fired 2026-08-23T19:43:15.313-04:00  devman/format
                        <- …/s7-probe.nix
Nothing to report.
```

### The comparison that makes it dangerous

A **correct** loop-break was produced for contrast: `touch src/devman/show.py`,
no content change, so the hash matches and the step rightly skips.

| Field | HAZARD — `.nix` save, hash cannot ever cover it | CORRECT — `.py` touch, nothing changed |
|---|---|---|
| dag status | 4 | 4 |
| step status | 5 (skipped) | 5 (skipped) |
| step error | `None` | `None` |
| `metadata.jsonl` | `succeeded` | `succeeded` |
| `fired.jsonl` outcome | `enqueued` | `enqueued` |

**Identical in every field.** The only thing that differs is the path in
`fired.jsonl`, and nothing reads it for this purpose.

### Answering `OPEN_QUESTIONS` §4 — is a `doctor` grep worth writing?

**The failure is genuinely invisible**, so by `PLAN.md` §4's own test something
is warranted. **But not the check it names.**

**Against the proposed check.** It would have to read `"**/*.nix"` out of a TOML
table and decide whether `-name '*.py'` inside a shell one-liner covers it. That
is parsing a shell expression to guess which extensions a hash spans. It is
defeated by any precondition that computes its hash another way — `git ls-files`,
a script, a different `find` — and the plane cannot tell "this glob is not
covered" from "this precondition is written in a way I cannot read". **A check
that is wrong in both directions is §15.7's heuristic exactly**, and §15.7 is
the section that says the plane will not grow one.

**What the file does instead.** `groups/format/workflows/format.yaml` now
carries the widening rule in capitals, next to the hash it governs, where the
person adding a glob is already looking. That is where a rule belongs when no
check can enforce it honestly.

**What can be checked exactly, and is proposed instead:**

| | Check | Why it is exact |
|---|---|---|
| **R-4d** | a trigger names a workflow the project does not project | set membership inside one registry entry (S-3) |
| **R-4e** | a glob whose runs have *only ever* skipped | counting records the plane already writes |

R-4e's data is already on disk and needs no parsing:

```
devman-format, every recorded step status:
  did work (succeeded): 67
  skipped (precondition): 17
```

A healthy glob produces both. A glob whose hash cannot cover it produces
**only** skips, forever. Reporting that count is arithmetic, and the judgement
stays with the reader — which is the line §15.7 actually draws.

**Recommendation: ship R-4d, hold R-4e until the hazard bites in the wild.**
R-4e needs a join between `fired.jsonl` and Dagu's per-run step statuses, which
is a new data path in `doctor` for a hazard that has never occurred outside this
spike. R-4a as written is refused.

### Verdict

**Passes** — the spike's job was to make the failure visible once, and it did.
`PLAN.md` §4's decision for R-4a is settled: **do not ship it.**

### Charter impact

**None**, and the widening rule moves from `PROPOSAL.md` §4 into the workflow
file itself, which is where R-1 already put it.

---

## Gate 2 — closed

| | Spike | Result |
|---|---|---|
| S-2 | the five workflow files, validated | **passes** — 9 files become 5, 216 executable lines become 123, `groups-validate` exits 0 |
| S-6 | the `release` gate against the renamed `test` | **passes** — all three cases plus the adversarial one |
| S-5 | `plane-report`, one manual and one scheduled | **passes**, and found a latent truncation bug in `maintain` |
| S-4 | the format glob/hash hazard | **passes** — invisible as predicted, and R-4a is refused on the evidence |

**Gate 3 may begin** — S-1 (58 synthetic DAGs on the `light` queue) and I-2a
(the `dagu validate` cost curve, whose first point S-5 already measured at
2.70 s).

### What Gate 2 changed about the refactor

| | Change |
|---|---|
| R-1 | ships the five files from `spike/007-gate-2`; both tombstones carry a README; `format.yaml` carries the widening rule in its own text |
| R-2 | `plane-report` ships with `\|\| rc=$?`, not `continue_on` |
| R-4a | **refused** — the glob/hash comparison is a heuristic |
| R-4d | **new**, from S-3 — a trigger must name a workflow the project projects |
| R-4e | **new**, from S-4 — a glob that has only ever skipped. Held until it bites |
| R-8 | **new**, from S-5a — an edited `.devman/workflows/` file must re-project. Before wave 2 |

### What was left on the machine

```
$ devman doctor
ok  watcher        devman: **/*.py -> format  [format]
Nothing to report.                                                   exit 0

$ git status --short
                                                            (clean)
```

The throwaway group `s7-widen`, the probe `s7-probe.nix` and the three `_s5-*`
workflows are deleted and re-projected. `plane-report`'s schedule is back at
`20 0 * * *`.

**`devman` is still running the spike content**, on branch `spike/007-gate-2`:
`groups = [ "base" "format" "release" ]`, `base:check`, `format:fmt`, and a
projection of `check`, `test`, `maintain`, `format`, `release`, `plane-report`
plus its own three. That is deliberate — it is R-1 and R-2 and half of R-5,
proved early — and it is one `git checkout` from reverting. The other five
registered repositories pin `fb78a99` and were never touched.

---

## I-2a — The `dagu validate` cost curve

**Answer: `doctor` is linear, the proposal's extrapolation was right to within
half a second, and 58 projects costs 14.3 seconds — measured, not predicted.**

**`PLAN.md` §8's replacement clause does not fire.** `doctor` is not
superlinear, so §5's one-nightly-plane-report survives and **R-4b is not
required before wave 4** — the curve does not reach 30 s until about 120
projects, twice the inventory.

**And the fix, if it is ever needed, is not R-4b.** The fan-out parallelises
almost perfectly: the same 174 files validated 8 at a time take **1.86 s
instead of 13.35 s**. A `--project` scope hides the cost; four lines of
`ThreadPoolExecutor` remove it.

### Versions

Dagu 2.15.0, devman 0.3.0, 8 cores. Synthetic registries under `/tmp/s7-i2a`,
each project a byte copy of `devman`'s own projection with the path rewritten,
three workflows each — which is `PROPOSAL.md` §5's own arithmetic, 58 × 3 = 174.

### Command

```bash
# one file
dagu --dagu-home ~/.local/share/dagu validate \
     ~/.local/share/devman/projects/devman/workflows/check.yaml

# the whole of doctor, against a synthetic registry of N projects
devman --registry /tmp/s7-i2a-run doctor
```

### Evidence 1 — the two halves, at the real registry

```
one `dagu validate`   : median  74 ms   (mean 70, range 53–85, 10 samples)
`devman doctor`       : median 3.00 s   (35 workflows, 5 samples)

  validate fan-out    : 35 × 74 ms = 2.59 s
  everything else     : 0.41 s   — 14% of the run
```

**Eighty-six percent of `doctor` is one subprocess per projected file.** The
other eleven checks cost 0.41 s together.

### Evidence 2 — the curve, six points

| projects | files | `devman doctor` | per file |
|---:|---:|---:|---:|
| 6 | 18 | 1.53 s | 85 ms |
| 10 | 30 | 2.29 s | 76 ms |
| 20 | 60 | 4.50 s | 75 ms |
| 30 | 90 | 7.60 s | 84 ms |
| 40 | 120 | 10.00 s | 83 ms |
| **58** | **174** | **14.33 s** | 82 ms |

```
linear fit: doctor = -0.15 s + 83.6 ms x files
residuals : +0.17  -0.07  -0.37  +0.22  +0.11  -0.07     max |r| = 0.37 s
predicted at 174 files: 14.4 s      measured: 14.33 s
```

**The intercept is within noise of zero and the residuals are under 0.4 s across
a tenfold range.** Nothing in `doctor` grows faster than the file count, which
was the assumption `PROPOSAL.md` §5 labelled and could not check.

**`PROPOSAL.md` §5's "roughly 14 s" is now a measurement.** It said so honestly
at the time and it was right.

### Evidence 3 — the fan-out is spawn cost, not daemon cost

```
174 files, serial (as doctor does it) : 13.35 s
174 files, 8 workers                  :  1.86 s        7.2x
```

Eight cores, near-perfect scaling. **The Dagu daemon is not the limit** — each
`dagu validate` is an independent short-lived process that reads one file, and
nothing contends.

### What this decides

**R-4b — a `--project` scope for `doctor` — is not needed.**

| Threshold | Files | Projects |
|---|---:|---:|
| 30 s, `PLAN.md` R-4b's trigger | 359 | **≈ 120** |
| 14.3 s, today's whole inventory | 174 | 58 |

The plane would have to double its inventory before the scope mattered, and
`plane-report` runs at 00:20 with nobody waiting on it.

**Proposed instead, and it is cheaper than the thing it replaces:**

| | Change | Effect |
|---|---|---|
| **R-4f** | run `check_load`'s subprocesses through a `ThreadPoolExecutor` | 14.3 s → ~2.3 s at 58 projects |

`check_load` already collects failures into a list and reports them together, so
the order of results does not matter and the change is confined to one loop.
**It is not a heuristic and it changes no output** — the same files are
validated and the same findings reported.

**I-2b is now cheap.** The curve is `83.6 ms x files`, so each rollout batch
needs one number to confirm the line rather than to discover it.

### Charter impact

**None.** §5's argument for moving `doctor` out of `maintain` rested on 58 × 14 s
of duplicated work; the 14 s is now measured and the argument is stronger, not
weaker. The one number `PROPOSAL.md` §5 should gain is that the cost is linear
and the per-file constant is 84 ms.
