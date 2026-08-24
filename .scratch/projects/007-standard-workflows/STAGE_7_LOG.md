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

---

## S-1 — 58 DAGs on the `light` queue, and the queue is not what makes them fine

**Answer: `PROPOSAL.md` §5's conclusion is right and its mechanism is wrong.**
58 simultaneous `maintain` dispatches are fine — they took **2 seconds** — but
**not because the queue absorbed them.** The queue did nothing at all.

> **A run started by Dagu's own scheduler does not go through the queue.**
> Measured on a throwaway instance and confirmed on the installed plane: 58
> DAGs naming `light` (limit 4) and sharing one `schedule:` all started in the
> same second, all 58 concurrent, queue depth 0.
>
> The same 58 DAGs put through `dagu enqueue` — the path `devman run` and the
> watcher take — **never exceeded 4 concurrent** and drained in 311 s with a
> queue depth of 54.

**`PLAN.md` §8's row for S-1 does not fire as written** — nothing failed, so
`light`'s limit does not need to rise. **And raising it would change nothing**,
because the scheduled path never consults it. The replacement is below.

### Versions

Dagu 2.15.0, 8 cores. A throwaway `DAGU_HOME=/tmp/s7-s1/dagu`, web port 8094,
coordinator port 50069, carrying a **byte copy** of the installed `base.yaml`
(`diff` clean) and the installed `config.yaml` with only the two ports and
`dags_dir` changed. Started with `dagu start-all` — **the identical command the
installed user unit runs**, which is what makes the comparison fair.

### Evidence 1 — the shipped shape, 58 at once

58 DAGs, each `queue: light`, each doing what `maintain` does after stage 7: a
`find` over a report directory, a report write, nothing else. All sharing one
`schedule:`.

```
runs              : 58
statuses          : {'succeeded': 58}
first start       : 20:22:00
last finish       : 20:22:02
wall clock        : 2s
max concurrent    : 4          <- see below; this number is an artefact
per-run duration  : median 0s, range 0-1s
total CPU-time    : 0.1 CPU-minutes
peak dagu CPU     : 571%
```

**All 58 succeeded in 2 seconds.** `PLAN.md` §5's bar — "all 58 complete within
a few minutes and none fails" — is met with three orders of magnitude to spare.

**The `max concurrent 4` is not evidence of the queue.** Dagu records
second-resolution timestamps and every run finished inside 1 s, so the overlap
count cannot distinguish 4 from 58. The next two measurements exist because of
that.

### Evidence 2 — the control, and it is much worse than the proposal estimated

The same 58, each running `devman doctor` against a 58-project registry — which
is what `maintain` does **today**.

```
runs              : 58
statuses          : {'succeeded': 58}
wall clock        : 143s
max concurrent    : 58              <- unambiguous: runs last minutes
per-run duration  : median 139s, range 135-142s
total CPU-time    : 134.5 CPU-minutes
peak dagu CPU     : 638%
```

**Every run is inflated tenfold by contention.** `devman doctor` at 58 projects
costs 14.3 s alone (I-2a); run 58 at a time on 8 cores it costs **139 s each**.

**`PROPOSAL.md` §5 estimated 13 CPU-minutes for this. It is 134.** The estimate
assumed the queue serialised the work four at a time. It does not, so the real
figure is ten times the one the proposal used to justify removing `doctor` from
`maintain`. **The argument for `plane-report` is far stronger than it was
written.**

### Evidence 3 — the decisive test, and then the real plane

The two runs above differ in duration, so a clean test was built: 58 DAGs,
`queue: light`, one step, `sleep 20`.

| | scheduled | enqueued (`dagu enqueue`) |
|---|---|---|
| max concurrent running | **58** | **4** |
| max queue depth | **0** | **54** |
| wall clock | ~22 s | **311 s** ≈ 58 ÷ 4 × 20 s |

```
scheduled:  t=45  queued 0  running 20
            t=47  queued 0  running 58        <- all of them
            t=67  queued 0  finished 58

enqueued:   t=0   queued 54  running 4
            t=19  queued 50  running 4
            …every 20 s, four more…
            t=311 queued  0  running 0
```

**The enqueued column is criterion 12 working exactly as the charter says.** The
scheduled column is the same DAGs, the same queue, the same daemon.

**Confirmed on the installed plane**, so this is not an artefact of the
throwaway. Two DAGs on `exclusive` — `max_concurrency: 1`, the strictest queue
the machine has — sharing one schedule:

```
devman-_s1-excl-a  start 20:36:00  finish 20:36:20  status 4  triggerType 1
devman-_s1-excl-b  start 20:36:00  finish 20:36:20  status 4  triggerType 1

second start - first start = 0s
VERDICT: queue BYPASSED (concurrent)
```

**A queue with a limit of one ran two runs at once, because the scheduler
started them.**

### What this falsifies, precisely

**`PROPOSAL.md` §5, the paragraph headed "The schedule shape at 58
repositories".** Its sentence —

> "58 simultaneous dispatches at `5 0 * * *` are fine, and the queue is what
> makes them fine. `maintain` names `light`, limit 4, so 58 enqueued runs
> proceed four at a time."

— is wrong twice. They are not enqueued, and they do not proceed four at a time.
**The conclusion survives on a different footing:** they are fine because the
work is milliseconds, and for no other reason.

**§5's argument against a stagger loses its counterweight.** It says a stagger
has exactly one legal carrier — "The queue, if anything… it is the only legal
carrier." That carrier does not exist for scheduled runs. The argument against
writing an offset into a shared group file still stands on its own (it would
give all 58 the same offset), but **nothing now throttles the scheduled set**,
and §5 must say so instead of pointing at a mechanism that is not engaged.

**`CONCEPT.md` criterion 12 — "queues are real" — must be narrowed.** It is true
of `devman run` and of the watcher, both of which reach Dagu through
`dagu enqueue`. It is false of `schedule:`. That distinction has existed since
stage 6 put schedules in workflow files, and nothing had measured it.

### What replaces it

**The scheduled set must be cheap by construction, because nothing throttles
it.** That is now a rule rather than a preference, and it is `PROPOSAL.md` §12's
eighth entry:

> **8. Anything expensive, on a schedule.** A scheduled run does not pass
> through its queue, so the limit that protects the machine from a burst of
> `devman run` does not protect it from a burst of `schedule:`. 58 repositories
> firing one cheap DAG at 00:05 costs 2 seconds. The same 58 firing anything
> that takes seconds costs the machine minutes of full load, at ten times the
> per-run cost, with nobody present.

**Two things follow for the refactor, and neither is new work:**

1. **R-1's `maintain` is already correct** — one `find` and one report write is
   exactly the shape this rule demands, and S-2 already built it.
2. **R-2's `plane-report` is the only other scheduled workflow**, it runs once
   for the machine rather than 58 times, and it costs 3 s (S-5). Also correct.

**What is genuinely open**, and named rather than guessed: whether Dagu can be
made to enqueue scheduled runs instead of dispatching them. `maxActiveRuns` is
per-DAG and cannot bound 58 different DAGs. **Nothing was measured about a
machine-side fix**, and this log does not propose one. The measurement a stage 8
would take is whether any Dagu configuration routes `schedule:` through a queue;
if none does, the rule above is the whole answer.

### Verdict

**Passes on the letter of `PLAN.md` §5** — all 58 complete, none fails. **Fails
the assumption underneath it**, which is the more useful result. Gate 3's job was
to learn this before wave 4, and it did.

### Charter impact

**One section, and it is a narrowing rather than a reversal.** Criterion 12's
commentary gains:

> "**Queues bind the enqueue path.** `devman run`, a VCS hook and the watcher all
> reach Dagu through `dagu enqueue`, and a queue's `max_concurrency` holds
> exactly: 58 enqueued runs on `light` never exceeded 4 concurrent and drained
> in 311 s (stage 7, S-1). **A run started by Dagu's own scheduler does not pass
> through the queue** — 58 DAGs sharing one `schedule:` all ran at once, and two
> DAGs on `exclusive` with a limit of 1 both ran at once. So a `schedule:` is not
> throttled by anything, and §12's rule follows: what the plane schedules must be
> cheap by construction."

R-6 carries it, after this measurement rather than before.

### Rule 7 — what this entry did to the machine, including a mistake

**I killed the installed Dagu service for about ninety seconds, by accident.**
Cleaning up the throwaway daemon, `pkill -f 'dagu start-all'` matched the
throwaway **and the user unit**, because S-1 deliberately gave them the same
command line.

- Detected immediately: the real plane's API returned nothing on 8080.
- Repaired with `systemctl --user start dagu`; `active` and HTTP 200 within
  six seconds.
- **Nothing was lost.** No run was in flight — the last two records are the
  `_s1-excl` probes, both `succeeded` at 20:36:20, sixty seconds before the
  kill. `maintain` fires at 00:05 and `plane-report` at 00:20, both outside the
  window. The watcher is a separate unit and never stopped. The daemon journal
  reports no error since the restart.
- **`plane` now reads `up 0h` instead of `up 20h`**, which is the only visible
  trace.

The correct command was `pkill -f 'DAGU_HOME=/tmp/s7-s1'`, or killing the
recorded PID. Recorded here rather than tidied away.

**Everything else is as it was found:**

```
$ devman doctor
devman doctor — 6 projects, 35 workflows
ok  plane          healthy — dagu 2.15.0, up 0h
Nothing to report.                                                   exit 0

$ git status --short
                                                            (clean)
```

The throwaway `DAGU_HOME`, the two `_s1-excl` workflows, and I-2a's synthetic
registries under `/tmp` are all deleted. No `_s1` link remains in `dags/`.

---

## Gate 3 — closed

| | Item | Bar (`PLAN.md` §5) | Result |
|---|---|---|---|
| S-1 | 58 DAGs on the `light` queue | all 58 complete in a few minutes, none fails | **passes** — 2 s, 58/58 — but the queue is not why |
| I-2a | the `dagu validate` cost curve | is `doctor` linear? | **passes** — linear, 83.6 ms/file, 14.33 s at 174 files |

**All four gates are closed. R-1 may begin.**

### The refactor, as Gate 3 leaves it

| | Status after gates 0–3 |
|---|---|
| R-1 group content | **ready** — built and validated on `spike/007-gate-2` |
| R-2 `plane-report` | **ready** — built, run manually and on a schedule, `\|\| rc=$?` fixed |
| R-3 the module | **ready** — I-6 settled the throw; two lines |
| R-4a glob/hash check | **refused** — S-4 showed it can only be a heuristic |
| R-4b `doctor --project` | **not needed** — I-2a: 30 s arrives at ~120 projects |
| R-4c check 6 asleep-vs-stopped | unchanged, still gated on I-10 |
| R-4d trigger names a real workflow | **new**, from S-3 — exact, ships |
| R-4e a glob that has only ever skipped | **new**, from S-4 — held until it bites |
| R-4f parallelise `check_load` | **new**, from I-2a — 14.3 s → ~2.3 s, four lines |
| R-5 wave 1 | **half done** — `devman` already carries its three edits |
| R-6 the charter | **grew** — criterion 12 narrows (S-1), plus §1.1 and §6 from Gate 0 |
| R-8 edited override must re-project | **new**, from S-5a — before wave 2 |

### The three things a reader should carry out of stage 7 so far

1. **The hinge held.** One workflow, one step, one devenv task survives every
   measurement, and the failing task's name reaches more places than predicted.
2. **Three latent defects were found by building rather than by reading**: a
   truncated report on the one night it matters (S-5), an edited override that
   never re-projects (S-5a), and a queue that does not bind the scheduler (S-1).
   None was in `OPEN_QUESTIONS.md`.
3. **Two proposed changes were refused on their own evidence** — R-4a and R-4b —
   and three cheaper ones took their place.

---

## R-3 — The module · gated on I-6 and S-3

**Two lines and one decision, and Gate 1 had already settled the decision.**

```diff
-      example = [ "base" "python" ];
+      example = [ "base" "format" ];
```

**The throw stays.** `PLAN.md` §6 left this open: if S-3 failed, the throw would
have to become a warning and the module would skip an unknown group — a real
loosening. S-3 passed and I-6 showed the refusal is legible, so the two
mechanisms do not compete. **The throw is correct for a misspelled group; the
tombstone handles the deletion case.** A module that silently ignored a
misspelled group would be §15.4's misspelled-queue hazard in a second place.

**The no-workflows branch gained the second shape it now serves.** It was
documented only as a triggers-only group. Since stage 7 it is also how a deleted
group keeps every stale pin evaluating, and both constraints S-3 measured are
now stated beside the code: a tombstone must hold a file, because git cannot
carry an empty directory, and must not hold a `triggers.toml`.

Two stale group names in the module's own documentation went with it — the
adoption example at the top and the schema-2 example in the entry comment both
said `python`.

**Verified:** no group name and no workflow name survives anywhere in `modules/`
or `src/`, which is what `PLAN.md` §0.1 measured before the stage began. The
module still evaluates and `devman doctor` is clean.

### A note on where this landed

`origin/main` had already taken the stage-7 content (see the branch note at the
end of this log). R-3's only non-comment change is the `example` attribute,
which is Nix option metadata and changes no evaluated result, so **wave 1 pins
`02d00f6`** — a commit already on `main` carrying the complete group set. R-3
itself sits on `dagu-devenv-automation-eli5`.

---

## R-5 — Wave 1 · the six registered repositories

**Answer: all six adopted. Thirteen lines, as `PROPOSAL.md` §6 tabled them.
`devman doctor` is clean at 6 projects, and the plane went from 36 projected
workflows to 25.**

**Two repositories fail their own contract, and neither failure is caused by the
migration.** That is I-4's signal arriving three waves early, and it is recorded
rather than repaired.

### The six, and what each cost

| Repository | Edits | Commit | `check` | `test` |
|---|---|---|---|---|
| `devman` | 3 | `0376b9a` (during S-6) | ok | ok |
| `siteman` | 2 + delete | `541cf25` | **ok** | **ok** |
| `nix-paseo` | 1 | `65f564c` | **ok** | **ok** |
| `pyjutsu` | 1 | `8323e09` | **ok** | **fails** |
| `pydantree` | 3 | `be150be` | **fails** | **ok** |
| `observantic` | 3 | `0f835d4` | **ok** | **ok** |

Each also bumped `rev=` to `02d00f6` and ran `devenv update devman && devenv
shell -- true`, which is the ordinary adoption command.

### The two failures, and why neither is a regression

**`pyjutsu-test`.** `base:test` was **not edited** — the only change to that
repository is `base:lint` → `base:check`. The log names the failing task, on
stderr, exactly as I-3 measured:

```
✖ Running pyjutsu:build in 49.1ms (failed)
  💥 maturin failed
  Caused by: Couldn't find a virtualenv or conda environment…
✖ Running pyjutsu:test in 120µs (dependency failed)
✖ Running base:test in 13.6µs (dependency failed)
```

`pyjutsu:test` declares `.after = [ "pyjutsu:build" ]` — the very dependency
`PROPOSAL.md` §1.1 cites as proof that criterion 14 was one edit from being
false. Confirmed independently: `devenv tasks run -v base:test` fails the same
way outside the plane, and **this repository had never once run the old
`validate` workflow**, so nothing had ever exercised the path.

**`pydantree-check`.** Pre-existing and already observed: the DAG had **failed
both times it ran before this change**. `python:lint` and `python:typecheck`
each exit 1 standalone — 256 ruff findings, almost all under `.scratch/` and
`examples/`.

**Coverage did not shrink when the `python` group went.** `python/check.yaml`
ran `python:lint` then `python:typecheck` as two Dagu steps; `base:check` now
pulls both through the devenv graph. Same two tasks, one invocation, and the
repository can run them by hand. `observantic` proves it from the other side —
its `check` passes with the extended alias.

### Wave 1's own proof

**`observantic`'s `release` gate opened on the renamed line** — S-6's third case,
in a second repository, for real:

```
observantic-release: succeeded

## gate
- clean tree: yes
- last test: succeeded — `{"dag":"observantic-test","run_id":"034CQrpQUmu1pe6FnK8hxf",…,"status":"succeeded",…}`
```

**The cross-repo workflow survives untouched**, which `PLAN.md` §6 said to
confirm rather than assume. `stack-validate` names `observantic-check` and
`siteman-check`; neither DAG name changed:

```
devman-stack-validate  status 4   nodes ['observantic-check', 'siteman-check']
  sub  siteman-check     status 4   nodes ['check']
  sub  observantic-check status 4   nodes ['check']
```

Each child's own record shows a single step named `check` — the one-step shape,
two projects deep.

**The plane, after the wave:**

```
$ devman doctor
devman doctor — 6 projects, 25 workflows
ok  shadowing      devman/agent-review: invented — no group version to diff
                   devman/bench-entry: invented — no group version to diff
                   devman/plane-report: invented — no group version to diff
                   devman/stack-validate: invented — no group version to diff
Nothing to report.                                                   exit 0
```

**36 workflows became 25**, and `siteman/full-test` has left the shadowing check
because the file it shadowed no longer exists.

### The investigations this wave carried

**I-2b — `devman doctor` at 6 projects, post-change.** The curve's first real
point after the content shrank:

```
2.23  2.36  2.25  2.07  1.90 s      mean 2.16 s over 25 workflows = 87 ms/file
```

**87 ms/file against I-2a's 83.6 ms/file** — the line holds, and the absolute
cost fell from 3.00 s to 2.16 s purely because the plane projects ten fewer
files. Deleting four workflows bought back 28% of `doctor`.

**I-9 — `devman` is checked out twice.** Resolved, and it is not a problem:

| | |
|---|---|
| registered path | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| the other checkout | `/home/andrew/Documents/Projects/devman`, on `spike/agent-factory-round-trip` |
| does it carry `.devman/.runs/`? | **no** |
| runs recorded there | 0 |
| runs recorded in the registered checkout | 136 |

**Only one checkout is registered, and only that one has a run tree.** The
second has never entered a shell with `devman.enable` under this registry, so
`.devman/.runs/` was never created. `doctor`'s check 6 has nothing to say
because there is nothing ambiguous: one path, one entry, one history.

**I-11 — the first scheduled `maintain` after each re-pin — is still open.** It
cannot be measured before 00:05, and the evidence to read is six
`maintain-*.md` reports and **one** plane report. That is the last outstanding
item of wave 1's proof.

### Charter impact

**None from R-3 or R-5 themselves.** The charter changes are R-6's, and Gate 0
to Gate 3 set what they are.

---

## I-4b — The shell-entry survey across all 58 · **wave 4's real size**

**Answer: 54 of 58 repositories can enter their own devenv shell. Four cannot.**
Wave 4 is **43 repositories**, and the work per repository is one `devenv.nix`
task line — not a repair pass.

**This is the check I-4 could not make.** I-4 read `devenv.nix` and never
entered a shell. §5.2 makes shell entry the only registration path, so a
repository whose shell fails is not "hard to adopt", it is **impossible to
adopt** and invisible to `doctor` while it stays that way.

### Versions

devenv **2.1.2**, devman **0.3.0**. 58 repositories under
`~/Documents/Projects` holding a `devenv.nix`. `devman` is read at its
registered path, the worktree.

### Command

```bash
for d in $(find . -maxdepth 2 -name devenv.nix -printf '%h\n' | sort); do
  (cd "$d" && timeout 240 devenv shell -- true)
done
```

Sequential, not parallel, so that one repository's build does not distort
another's. **The whole sweep is a real cost and it is stated:** ~35 minutes of
wall clock, and it warmed a great many Nix caches.

### Evidence — the four that fail, and four distinct causes

| Repository | Cause | Class |
|---|---|---|
| `PyGentic` | `git-hooks or pre-commit-hooks input required` | devenv integration — **one input line** |
| `clinch` | `attribute 'configPath' missing` | the repository's own module |
| `inferference` | `Refusing to evaluate package 'cuda12.9-cuda_nvcc-12.9.86'` | unfree licence, not declared |
| `fsdantic` | `agentfs-src/cli/Cargo.toml` does not exist | vendored source absent (wave 3) |

**Only `PyGentic` repeats a cause already solved.** It is the same
`pre-commit-hooks` gap wave 2b traced in `webdantic` and `parsedantic`, so it is
one line away from adoptable. The other three are each their own repair.

**An honest correction to the headline.** This survey ran **after** wave 2b, so
`webdantic` and `parsedantic` report `OK` because they were fixed an hour
earlier, not natively. **The pre-session figure is 6 of 58 unadoptable**, and
that is the number to compare against wave 2's alarming 2-in-5.

### One result that was wrong until it was re-measured

`terminal-state` recorded **TIMEOUT at 568 s** against a 240 s limit — the
process outlived its own timeout, which is worth noting on its own. Re-run
immediately afterwards:

```
$ cd terminal-state && devenv shell -- true
rc=0  elapsed=3s
```

**It was a cold build, and the first run warmed it.** Recorded as `OK`, and
recorded here as a reminder that a timeout in this survey measures the cache,
not the repository. Its first-entry cost is the one real data point: **568 s
cold.**

### Cold-entry cost, which nobody had measured

```
terminal-state  568s      structured-agents-v2   48s
repoman         216s      llgym                  40s
nixvim          114s      boomtube               37s
browsee          53s      tyo3                   36s
```

Everything else is under 30 s, and most is under 10 s. **Criterion 7's ≤10 ms
budget is about a warm entry**, and nothing here touches it — but a wave that
adopts ten repositories at once should expect minutes, not seconds, the first
time.

### What wave 4 actually is

```
total repositories        58
shell enters              54
shell does NOT enter       4
already adopted           11        (waves 0-2b)
WAVE 4 = adoptable now    43
```

**By what `base:test` would be, across those 43:**

| | Count | Work per repository |
|---|---|---|
| a suite, no task | **27** | one task line naming the suite |
| `enterTest` only | **15** | one task line, **and** a check that it tests anything |
| a `<x>:test` task | **1** | one alias line |

**The 15 are the ones that can adopt a lie.** `PROPOSAL.md` §12 rule 4 rests on
`devenv test` exiting 0 having tested nothing in 30 of 58 repositories, and wave
2 hit it twice: `webdantic` and `parsedantic` both had the devenv template's
default `enterTest`, which greps `git --version`. Neither got `devenv test` as
its `base:test`. **These 15 go first in wave 4**, so the failure mode is met
while the batch is small.

### The two checks wave 4 runs per repository, before editing anything

Both were bought with a wasted wave:

1. **`devenv shell -- true`.** This survey is that check, run once for all 58.
2. **`command -v <the tool `base:test` would call>`, inside that shell.** Wave
   2b found `pytest` absent from two venvs where `pyproject.toml` declares it —
   it lives in `[project.optional-dependencies]`, which devenv's venv does not
   install. The answer there was `uv run --extra dev pytest`.

### A third thing, found while waiting, that `doctor` cannot see

The `devman` repository root holds an **empty, untracked directory literally
named** `${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}`, dated 22 August. It is the
fingerprint of §7.2's unset-variable bug, from before stage 6 generated
per-project files.

**`doctor`'s `literal dir` check does not find it, and cannot.** That check
greps the *projected YAML* for literal `${…}` strings and reports "none in 12
places" — it catches the **cause** and never the **consequence**. `git status`
misses it too, because git does not track empty directories.

**Not deleted**, and reported rather than tidied away. It is inert. If a check
for it is ever wanted it belongs in `doctor` as a filesystem test next to check
3, and it is a `find` on each registered path — a fork per project on a path
that is already allowed to spend one.

### Verdict

**`PLAN.md` §8's sizing question is answered, and the answer changed twice.**
I-4 said wave 4 was 46 repositories × one line. Wave 2 said 2 in 5 might be
unadoptable, which would have made it a repair pass. **The survey says 43 × one
line, plus 4 repairs that are somebody else's work.** The middle estimate was
the wrong one, and it came from five samples.

### Charter impact

**None.** §5.2 and §15.1 already say what this measures. What is new is the
number.

### Rule 7 — what this entry did to the machine

**No repository was edited and nothing was committed to any of them.** The sweep
entered 58 shells and `terminal-state`'s a second time. That is not free: it
realised a large number of Nix store paths that were not there before,
`terminal-state`'s alone taking 568 s. Nothing was deleted. The registry is
unchanged at **11 projects, 40 workflows**.

---

## R-7 wave 3 — `fsdantic`, blocked before the thing it was scheduled to test

**Answer: `fsdantic` cannot be adopted, and not for any reason wave 3 was
about.** Its shell does not enter:

```
$ devenv shell -- true
error: path '/nix/store/ngar1l1sc6h4qf45w2ixj6k6i3c72aqz-agentfs-src/cli/Cargo.toml'
       does not exist
```

**R-9 already answered wave 3's original question**, so nothing is lost from the
plane's side: `.devman/store/` no longer blocks registration, and the paired
measurement in R-9 proves it on a real tree. What wave 3 would have added is one
more repository, and that is what is blocked.

### Versions

devenv **2.1.2**, devman **0.3.0**. `fsdantic` on branch
`fix/materialization-remove-exdev-fallback`, clean, 0 ahead of its upstream.
**No file in `fsdantic` was edited** — the check that stopped this is wave 2b's
new first step, run before anything was written.

### The cause, traced

`fsdantic`'s own `devenv.nix` reads a Rust manifest at **evaluation** time, so a
missing file is a total shell failure rather than a build failure:

```nix
# fsdantic/devenv.nix
agentfsPath = ./.devman/store/vendor/agentfs;
agentfsSrc  = builtins.path { path = agentfsPath; name = "agentfs-src"; };
cargoToml   = builtins.fromTOML (builtins.readFile (agentfsSrc + "/cli/Cargo.toml"));
```

The symlink chain resolves, and the source is not at the end of it:

```
.devman/store/vendor/agentfs
  -> /home/andrew/Documents/Projects/vendor/agentfs        (itself a symlink)
  -> /home/andrew/Documents/Projects/fsdantic/.context/agentfs-main   (exists)

$ find .context/agentfs-main -maxdepth 1
  agentfs-main/   MANUAL.md   README.md   SPEC.md   examples/   sdk/

$ find .context/agentfs-main -maxdepth 3 -name Cargo.toml
  (nothing)
```

**The vendored checkout holds documentation and an SDK, and no Rust crate at
all.** The nested `agentfs-main/` is empty. There is no `cli/Cargo.toml` to
read, at any depth.

**Pre-existing and unrelated to the plane.** `fsdantic`'s tree is untouched and
was clean before and after. Not repaired here: restoring a vendored Rust source
tree is `fsdantic`'s own work, and it is a long way from adoption.

### What this does to `PROPOSAL.md` §8's wave 3

**Wave 3's purpose was already spent by R-9.** §8 scheduled `fsdantic` as the
repository that "must fail first", so §15.2's whitelist could be seen firing in
the wild. That whitelist no longer exists, and the decision that removed it was
measured on `devman`'s own tree with a probe of exactly `fsdantic`'s shape.

**So wave 3 is closed as "not needed, and separately blocked".** When
`fsdantic`'s vendored source is restored it adopts like any other repository —
with `.devman/store/` in place and nothing to move.

### The check that caught this, and it is the whole point

Wave 2b's closing rule was: **run `devenv shell -- true` before editing
anything.** It was written after two wrong guesses cost a wave. Its first
application, on the very next repository, found a third unadoptable repository
with a third distinct cause:

| Repository | Cause | Class |
|---|---|---|
| `webdantic` | missing `pre-commit-hooks` input | devenv integration |
| `parsedantic` | missing `pre-commit-hooks` input | devenv integration |
| `fsdantic` | vendored Rust source absent | repository's own state |

**Three of twelve repositories touched so far could not enter their own shell**,
for two unrelated reasons. That ratio is why the survey below exists, and why
it runs before wave 4 rather than during it.

### Charter impact

**None.** §15.2 was already rewritten by R-9. §5.2's "a repository is invisible
until you enter its shell once" is doing all the work here, and it is correct as
written.

### Rule 7 — what this entry did to the machine

**Nothing.** One `devenv shell -- true` in `fsdantic`, which failed, plus reads
of its `devenv.nix` and the symlink chain. No file was edited, nothing was
committed, and `fsdantic` is on the same branch and the same commit as before.

---

## R-7 wave 2b — the two blocked repositories, and two wrong guesses

**Answer: both adopted. Wave 2 is five of five registered.** The blocker was
**not** what wave 2's entry guessed, and the correction is the point of this
entry.

### Versions

devenv **2.1.2**, Dagu **2.15.0**, devman **0.3.0** from the machine closure.
Both pin `main` at `70c8e2f`.

### Wrong guess 1 — `flake: false` was correlation, not cause

Wave 2 recorded a **perfect** correlation: the two repositories that could not
enter a shell were exactly the two declaring the `shellij` input as a flake
rather than `flake: false`, and the three that worked all set it. Five for five.

**It was wrong.** Adding `flake: false` to both changed nothing:

```
webdantic    shell: STILL FAILS — git-hooks or pre-commit-hooks input required
parsedantic  shell: STILL FAILS — git-hooks or pre-commit-hooks input required
```

The change was reverted rather than kept, because the comment justifying it
stated a reason that is false.

**A five-for-five correlation over five samples is not a mechanism**, and wave 2
had the evidence to know better: it never traced the error, it matched a column.

### The actual cause, traced rather than correlated

devenv's own integration module throws, and it is reached while evaluating
`config.shell` — so the failure is total, not partial:

```
… while calling the 'throw' builtin
  at /nix/store/71bpdsq…-source/src/modules/integrations/git-hooks.nix:9:11:
     8|       or inputs.pre-commit-hooks
     9|       or (throw "git-hooks or pre-commit-hooks input required");
```

**`pydantree` carries the same template and the same direct `shellij/modules`
import, and works** — because it declares the input:

```
$ grep -A1 'pre-commit-hooks' pydantree/devenv.yaml
  pre-commit-hooks:
    url: github:cachix/pre-commit-hooks.nix
```

One input each, and both shells enter:

```
webdantic    SHELL ENTERS
parsedantic  SHELL ENTERS
```

### Wrong guess 2 — a bare `pytest` is not `base:test`

Both were adopted with `base:test` = `pytest`, copying wave 1. Both failed with
`command not found`:

```
$ devenv shell -- command -v pytest
webdantic    MISSING     ruff:ok
parsedantic  MISSING     ruff:ok
```

**`pytest` is in `[project.optional-dependencies].dev`, and devenv's venv
installs only the base dependencies.** Wave 1's Python repositories have pytest
in the venv because `testee` puts it there; these two do not. `base:test` is
therefore:

```nix
"webdantic:test".exec = "uv run --extra dev pytest";
```

```
63 passed, 3 skipped in 2.59s
```

**This is `PROPOSAL.md` §12 rule 6 in miniature** — one logical task, one
implementation, every caller reaching it the same way. A `base:test` naming a
command that is not on the shell's PATH is a second implementation that never
worked.

### Evidence — wave 2, complete

| Repository | Commit | `check` | `test` |
|---|---|---|---|
| `poddantic` | `a295423` | **failed** — 20 `ruff` | ok — 233 passed, 2 skipped |
| `nix-desktop` | `c775f2f` | ok | ok |
| `loci.nvim` | `7e6d984` | ok | ok |
| `webdantic` | `2486f27` | **failed** — 275 `ruff` | ok — 63 passed, 3 skipped |
| `parsedantic` | `e473af5` | **failed** — 78 `ruff` | **failed** — 13 collection errors |

```
$ devman doctor
devman doctor — 11 projects, 40 workflows
Nothing to report.                                                   exit 0
```

**`parsedantic`'s test failure is the repository's own, and it is controlled.**
13 errors during collection, every one
`TypeError: function() argument 'code' must be code, not str` — the library
builds functions at import time and the Python in this shell rejects it. With
devman's block removed and only the `pre-commit-hooks` input kept:

```
$ devenv shell -- uv run --extra dev pytest -q
13 errors in 0.39s        <- identical
```

**Not repaired.** Three of five now fail `check` on lint debt (20, 275 and 78
findings) and one fails `test` on a real bug. Adoption and repair stay separate,
as wave 1 decided for `pydantree`.

### What this changes for waves 3 and 4

**Two checks per repository, before any file is edited:**

1. **`devenv shell -- true`.** A repository whose shell does not enter cannot
   register at all, and I-4's static sweep cannot see it.
2. **`command -v <the tool base:test would call>`, inside that shell.** A task
   naming a command the shell does not have fails identically to a failing
   suite, and only the log distinguishes them.

**And a rule for this log: trace the error before reporting the cause.** Both
wrong guesses here were plausible, and one had five-for-five agreement.

### Charter impact

**None.** §5.2 already says shell entry is the only registration path; wave 2b
is that sentence being expensive.

### Rule 7 — what this entry did to the machine

| Repository | Commit | State |
|---|---|---|
| `webdantic` | `2486f27` | committed, **pushed** to `origin/main` |
| `parsedantic` | `e473af5` | committed, **pushed** to `origin/main` |

The registry went from 9 projects to **11**, and 34 workflows to **40**.
`doctor` is clean. The `flake: false` edits were reverted and are in neither
commit.

---

## R-9 — `.devman/` belongs to the repository · a decision, and what it costs

**Answer: the §15.2 whitelist is removed.** Registration no longer looks at what
else is under `.devman/`. devman reserves two names — `workflows/` and `.runs/`
— and never reads, writes or inspects anything else there.

**This is an owner decision, not a measurement**, and it is recorded as one. The
ask was to keep `.devman/` open for add-on functionality. The measurement below
is the proof the change does what it says, not the reason it was made.

### Why the rule was wrong, in the charter's own terms

**It contradicted §7.4.** The plane's claim is that it names the smallest
vocabulary it has to and leaves everything else to the repository. `.devman/` is
a directory the repository already owned, and "refuse to register until you move
your files" is an opinion about a repository's layout — the exact kind §7.1 says
the plane does not hold.

**Wave 3 was built around the refusal, and that was the tell.** `PROPOSAL.md` §8
scheduled `fsdantic` as the repository that "must fail first", because it holds
`.devman/store/vendor/agentfs` — a tracked symlink to a vendored checkout that
predates the plane entirely. A wave whose stated purpose is to make a
repository move its own files, so the plane will consent to notice it, is a wave
arguing for the wrong side.

### Versions

devenv **2.1.2**, devman **0.3.0**, in `devman` itself, which imports
`./modules` and therefore picks up the change without a re-pin.

### The measurement — paired, on one tree

A throwaway `.devman/store/vendor/marker` was created in `devman`'s own
checkout, and the module was swapped underneath it. **Same tree, same file, two
modules.**

```
$ mkdir -p .devman/store/vendor && echo probe > .devman/store/vendor/marker

# the old module
$ git stash push -- modules/devenv.nix
$ rm -f .devenv/nix-eval-cache.db* && devenv shell -- true
devman: refusing to register 'devman'
devman:   .devman/ holds entries devman does not recognise: store
devman:   only workflows/ and .runs/ may be there
devman:   move them, or unset devman.enable in this repository

# the new module, nothing else changed
$ git stash pop
$ rm -f .devenv/nix-eval-cache.db* && devenv shell -- true
(no output)

$ python3 -m json.tool ~/.local/share/devman/projects/devman/metadata.json
  "project": "devman"
  "path":    "/home/andrew/.paseo/worktrees/1n48r26y/special-dragon"
  "local":   ["agent-review","bench-entry","plane-report","stack-validate"]

$ find .devman/store
  .devman/store  .devman/store/vendor  .devman/store/vendor/marker
```

**It registers, and the foreign directory is untouched.** The probe was removed
afterwards and `.devman/` holds `workflows/` and `.runs/` again.

### What was removed, precisely

`modules/devenv.nix`: the `devman_bad` loop, the refusal branch that led the
`if`/`elif` chain, and the variable from the `unset` list. **The duplicate-path
refusal (§9.1) is untouched** and is now the first branch.

**Nothing replaces it, deliberately.** A `doctor` check that listed unrecognised
entries would be the same opinion in a softer voice, and §15.7 says `doctor`
does not guess.

**The hook got cheaper.** The whitelist was one directory listing on the common
path, on every shell entry, twice. It is gone, which pays back a little of R-8's
2.82 ms.

### What this gives up, stated rather than glossed

**A repository holding a `devman 0.2.0` workspace now registers silently**, and
the two tools share `.devman/` without either knowing. That is the case the
whitelist was written for, and it is the one that is genuinely lost.

**The older tool is the destructive one.** Its `init` refuses a non-empty
`.devman/`, and `--force` calls `shutil.rmtree` on it — which would delete the
tracked `workflows/` this charter calls canonical. **§3.3's removal of that
binary stops being a tidiness task and becomes the mitigation.** Nothing in the
plane can defend against a tool that deletes the directory out from under it,
and nothing in the plane now tries.

### What this changes about wave 3

**Wave 3's purpose inverts.** It was "the whitelist refuses, then `fsdantic`
moves its directory". It becomes "`fsdantic` adopts the plane **and keeps its
store**, and the two do not interact". The proof is the same shape — one
repository, one shell entry, `check` and `test` — and the thing being proved is
better.

**`fsdantic` cannot adopt until a `main` rev carries this**, because it pins
`ref=main&rev=`. The rev on `main` at the time of this entry is `70c8e2f`, which
still holds the whitelist.

### Charter impact

**§15.2, rewritten, in its own commit** (`ff62a7f`, after `0b6e013`), per stage
6's D9. It keeps the 77-checkout survey that justified the old rule, says
plainly that the rule is reversed by decision, and names what the reversal costs.

### Rule 7 — what this entry did to the machine

| | |
|---|---|
| `devman` | `modules/devenv.nix` (`0b6e013`), `CONCEPT.md` §15.2 (`ff62a7f`) |
| a probe | `.devman/store/vendor/marker`, created and **deleted**; `.devman/` holds `workflows/` and `.runs/` |
| the registry | re-projected three times; 9 projects, 34 workflows, `doctor` clean |

---

## R-7 wave 2 — three of five adopted, and two cannot be adopted at all

**Answer: the universal contract is not a Python fiction, and wave 2 proves it.**
`nix-desktop` (a Home Manager flake) and `loci.nvim` (a Neovim plugin written in
Lua, whose tests are Nix derivations) both take `base` with no group of their
own, and both pass `check` and `test`.

**But two of the five could not be adopted, and the reason is not devman.**
`webdantic` and `parsedantic` **cannot enter their own devenv shell**, before
any devman change. §5.2 makes shell entry the only registration path, so a
repository that cannot enter its shell is invisible to the plane.

### Versions

devenv **2.1.2**, Dagu **2.15.0**, devman **0.3.0** from the machine closure.
All three adopted repositories pin `main` at
`70c8e2f59883541f48a39534440f6b17d3dbef9f`, the merge of PR #129.

### Evidence 1 — the blocker, and it was found by measuring rather than by adopting

`webdantic` was edited first. Its shell entry failed:

```
error: git-hooks or pre-commit-hooks input required
```

**The control says the failure is not mine.** With `devenv.yaml` and
`devenv.nix` stashed — no devman input, no devman module — the same entry fails
the same way:

```
$ git stash push -- devenv.yaml devenv.nix
$ devenv shell -- true
error: git-hooks or pre-commit-hooks input required
```

So the baseline was taken for the other four before writing another line:

```
poddantic     shell ok
parsedantic   SHELL FAILS — git-hooks or pre-commit-hooks input required
nix-desktop   shell ok
loci.nvim     shell ok
```

**The cause correlates perfectly, and it is one line.** The two that fail are
exactly the two that declare the `shellij` input as a *flake*; the three that
work declare `flake: false`:

| Repository | `shellij` input | shell |
|---|---|---|
| `poddantic` | `flake: false` | ok |
| `nix-desktop` | `flake: false` | ok |
| `loci.nvim` | `flake: false` | ok |
| `webdantic` | *(flake, the default)* | **fails** |
| `parsedantic` | *(flake, the default)* | **fails** |

`webdantic`'s edits were **reverted** rather than committed, because a
repository pinned to the plane and never registered is worse than one that is
not pinned: the pin is config that does nothing, and it goes stale.

**This is a class of blocker `I-4` could not see.** I-4 read `devenv.nix`. It
never entered a shell. **A repository can have a suite, a task and a clean
`devenv.nix`, and still be unadoptable**, and nothing before wave 2 would have
said so. Waves 3 and 4 must run `devenv shell -- true` as their first step, per
repository, before any file is edited.

### Evidence 2 — the plane after the wave

```
$ devman doctor
devman doctor — 9 projects, 34 workflows
ok  plane / queues / validate / queue names / literal dir / shadowing
ok  stale entries / run output / projection / handlers / cross-repo / watcher
Nothing to report.                                                   exit 0
```

6 projects and 25 workflows became **9 and 34** — three repositories × `check`,
`test` and `maintain`.

**I-2b, a third point on `doctor`'s curve:**

```
2740  2756  2544  2669  2701 ms      mean 2682 ms over 34 workflows = 78.9 ms/file
```

**78.9 ms/file against I-2a's 83.6 and I-2b's 87 at six projects.** The line
holds. This is still the closure's **serial** `check_load` — R-4f is merged but
not installed, which is what the `nixos-rebuild` note is about.

### Evidence 3 — `check` and `test`, per repository

| Repository | commit | `check` | `test` |
|---|---|---|---|
| `poddantic` | `a295423` | **failed — pre-existing** | ok — 233 passed, 2 skipped |
| `nix-desktop` | `c775f2f` | ok | ok |
| `loci.nvim` | `7e6d984` | ok | ok — after an intermittent failure, below |

**`poddantic`'s `check` failure is lint debt, and the control proves it.** 20
`ruff` findings, mostly `E501` in `tests/`. With the devman changes stashed:

```
$ devenv shell -- ruff check .
Found 20 errors.
```

Identical. **Not a migration regression.** Not repaired here — adoption and
repair are separate passes, which is the same call wave 1 made for `pydantree`.

### Evidence 4 — `loci.nvim` failed once, and chasing it was worth the time

The first `test` run failed: `34 passed, 1 failed`, on `t21_move_document`. The
tempting entry was "a pre-existing test failure". **It is not that, and it is not
a regression either.** Six subsequent executions passed:

| Execution | Result |
|---|---|
| control — `nix flake check`, devman changes stashed | all checks passed |
| `nix flake check` ×2, changes restored | all checks passed *(cache hits — see below)* |
| `nix build --rebuild` ×4, forced re-execution | rc=0, four times |
| **the plane again, after `nix store delete` of the output** | **succeeded** |

**The middle two prove nothing on their own and are recorded as such.** Nix
caches a successful check, so a re-run after a pass is a cache hit. The forced
rebuilds and the store deletion are what make the last row a real second
execution *in the plane's own environment* — which is the environment that
failed.

**Verdict: `t21_move_document` is intermittent.** One failure in seven
executions. It is the repository's own test and it is recorded here rather than
filed as an adoption problem.

### Evidence 5 — two things confirmed in passing

**I-3's stream split, live and costly.** `loci.nvim`'s failing run wrote **0
bytes to `test.*.out`** and 13,300 bytes to `test.*.err`. A reader who opened
the `.out` file would have seen an empty file and no failure at all. This is
exactly what I-3 measured on devenv 2.1.2, now hit by accident on a real
failure rather than on a probe.

**A project name may contain a dot.** `loci.nvim` is the first. devman projects
`loci.nvim-check.yaml` and records `"dag":"loci.nvim-test"` in
`metadata.jsonl`, so `release`'s gate — which greps `<project>-test` — still
matches. **Dagu writes its run directory as `loci_nvim-test`**, substituting the
dot. Nothing broke, `doctor`'s projection and run-output checks both pass, and
it is written down because the two names differ and somebody will grep for the
wrong one.

### Verdict

**Wave 2 passes on what it was built to answer.** `PROPOSAL.md` §8 says
`nix-desktop` and `loci.nvim` passing is the proof the contract is not a Python
fiction. Both pass, both took `base` alone, and neither needed a group, a
language option, or a line of Python.

**Wave 2 fails on coverage: three of five.** The two that are missing are
blocked on a one-line change to a flake input that has nothing to do with the
plane, and that change is **not made here**.

### Charter impact

**None, and one sharp edge earns a sentence when the next stage edits §15.**
§15.1 already says a repository is invisible until you enter its shell once.
What wave 2 adds is that **a repository whose shell does not enter is invisible
permanently**, and the plane cannot report it — `doctor` lists what is
registered, and an unregistrable repository is nowhere. That is a gap in §10's
coverage, not a bug in it, and it belongs to whoever writes the adoption
checklist.

### Rule 7 — what this entry did to the machine

| Repository | Commit | State |
|---|---|---|
| `poddantic` | `a295423` | committed, **pushed** to `origin/main` |
| `nix-desktop` | `c775f2f` | committed, **pushed** to `origin/main` |
| `loci.nvim` | `7e6d984` | committed, **pushed** to `origin/main` |
| `webdantic` | — | edited, then **reverted**; tree clean, nothing committed |
| `parsedantic` | — | never edited |

**`loci.nvim` was on a detached HEAD** at exactly `main` and `origin/main`, so
`git checkout main` lost nothing. It was checked before the checkout, not after.

**One store path was deleted on purpose** —
`/nix/store/bskl00m5x9jins3amhyiqzwjmwr1gbaq-loci-nvim-tests` — to force the
plane to re-execute a cached check. It has since been rebuilt.

The registry went from 6 projects to 9, and `doctor` is clean.

---

## I-4 — The `base:test` sweep across 58, static · **run before wave 4, not during**

**Answer: 4 of 58 repositories have nothing to test. The other 54 have a suite
and 48 of them have no task pointing at it.** So wave 4's per-repository work is
overwhelmingly **one line in `devenv.nix`**, not authoring a test suite.

**This is the static classification only.** The owner's call, taken before the
sweep ran: report the table from inspection, state the split from it, and leave
the live run to the session that starts wave 4. **So no repository here carries
a measured pass or fail.** Wave 1's six do, and they are the only ones that do.

### Versions

Inspection of `devenv.nix` and the working tree in each of the 58 repositories
under `~/Documents/Projects` that hold one. `devman` is read at its **registered
path**, the worktree, not at the second checkout (I-9).

### Command

```bash
find . -maxdepth 2 -name devenv.nix -printf '%h\n' | wc -l      # 58
# then, per repository: the `"<x>:<y>"` task names in devenv.nix, whether
# `enterTest` is set, and whether a suite exists on disk
```

### Evidence — the 58, by what they would put in `base:test`

| Class | Count | What `base:test` would be | What wave 4 owes it |
|---|---|---|---|
| **adopted** | **6** | `base:test`, already defined | nothing — this is wave 1 |
| **a `<x>:test` task** | **1** | `devenv tasks run loci:test` | one alias line |
| **`enterTest` only** | **19** | `devenv test` | one alias line, **and a check that `devenv test` tests anything** |
| **a suite, no task** | **28** | none yet | one task line naming the suite |
| **no suite at all** | **4** | none | a decision, not a line |

```
adopted          6   devman nix-paseo observantic pydantree pyjutsu siteman
task             1   loci-core
enterTest       19   PyGentic atuout atuout-reconciler-test boomtube browsee
                     cairn clinch embeddy fleetman forgelab fornix grail
                     knappy nixbuild parsedantic templateer_v2 tyo3 webdantic
                     zelligate
suite, no task  28   allium-env argentic copyroom docman eventic flora
                     flora-core flora-qc foreman fsdantic gitman
                     image-gen-pipeline inferference interplay llgym loci.nvim
                     lodestar my-ai mypi-agent poddantic pytuin repoman
                     shellij structured-agents-v2 talkee terminal-state testee
                     vendomat
no suite         4   nix-desktop nix-nvim nix-secrets nixvim
```

### The split, stated explicitly, which is what `PLAN.md` §8 asks for

**Wave 4 is adoption plus one authoring line, not adoption plus repair.** That is
a different and smaller answer than wave 1 suggested, and the reason is that
wave 1's two failures are not the population's shape:

- **`pyjutsu` fails `test`** because `pyjutsu:build` needs a virtualenv `maturin`
  cannot find. That is a native-extension build, and `pyjutsu` is the only
  repository in the inventory with one.
- **`pydantree` fails `check`** on 256 `ruff` findings, almost all under
  `.scratch/` and `examples/`. That is a lint configuration, and it is not a
  `base:test` fact at all.

**Neither failure is the thing this investigation was sizing.** The sizing
question was "do these repositories have tests that pass", and the static answer
is that **54 of 58 have something to point at**.

**Three bounds on that, and they are why the live run still has to happen.**

1. **`devenv test` is not a safe default for the 19.** `PROPOSAL.md` §12's
   fourth rule rests on a measurement — `devenv test` exits 0 having tested
   nothing in 30 of 58 repositories. An `enterTest` that is set is not an
   `enterTest` that runs a suite. Those 19 are the group most likely to adopt a
   green workflow that tests nothing, which is the failure §12 rule 4 exists to
   forbid.
2. **A suite on disk is not a passing suite.** 28 repositories have `tests/` and
   `test_*.py` and nothing has run them. The static pass cannot tell a
   maintained suite from an abandoned one.
3. **The heuristic has a known blind spot, and `siteman` is it.** `siteman`
   shows "no suite" by file inspection and is nonetheless adopted: its
   `base:test` is `ci`, an offline end-to-end build of `examples/demo`, because
   it has no unit tests by design. **A repository can honour the contract with
   no `tests/` directory**, so the 4 in "no suite" are candidates for a
   decision, not a verdict.

### Verdict

**The bar `PLAN.md` §8 sets is met: the sizing question is answered before wave
4 rather than during it.** Wave 4 is 46 repositories × one `devenv.nix` line,
plus 19 `devenv test` invocations that need checking against §12 rule 4, plus 4
repositories that need a decision about what `base:test` means when there is
nothing to test.

**What is deliberately not answered: pass or fail, per repository.** That is the
live sweep, and it belongs to the session that starts wave 4, with the 19
`enterTest` repositories first because they are the ones that can adopt a lie.

### Charter impact

**None.** §16's "no ecosystem groups" already carries the population figure, and
R-6 landed it. This entry adds no claim the charter states.

### Rule 7 — what this entry did to the machine

**Nothing.** One `find` and one Python script that reads `devenv.nix` and lists
directories. No shell entered, no workflow run, no repository written to.

---

## R-8 — An edited override re-projects, and the obvious way to write it was too slow

**Answer: fixed, proved byte for byte, and it costs 2.82 ms per shell entry.**
The guard now compares each override's body against the tail of its projection.
An edit reaches Dagu at the next shell entry, which is what `STAGE_6_LOG.md` D6
promised and did not deliver.

**The first implementation was correct and broke criterion 7.** Writing the tail
test as `''${have%"$body"}` cost **11 ms per shell entry** on its own, against a
budget of 10. The same test written as a slice costs **2.82 ms**. That is the
finding worth carrying: in this hook, *how* a comparison is written matters more
than whether it forks.

### Versions

devenv **2.1.2**, Dagu **2.15.0**, devman **0.3.0**, bash 5.3p9, in `devman`
itself. Five overrides totalling 18.3 KB — `agent-review` 4399 B, `bench-entry`
6459 B, `plane-report` 4162 B, `stack-validate` 3282 B, and a 100 B probe.

### Evidence 1 — the bug, reproduced on purpose before it was fixed

A throwaway `.devman/workflows/_r8probe.yaml`, so that no tracked file was
dirtied. Adding it changes `local`, which the old guard already caught, so it
projected. Then it was **edited in place**, which is the case that fails:

```
$ sed -i 's/VERSION-ONE/VERSION-TWO/' .devman/workflows/_r8probe.yaml
$ grep -n VERSION .devman/workflows/_r8probe.yaml
5:    run: echo VERSION-TWO
$ devenv shell -- true                                     # 1.8 s
$ grep -n VERSION ~/.local/share/devman/projects/devman/workflows/_r8probe.yaml
12:    run: echo VERSION-ONE                                <- what Dagu reads
```

**Two shell entries and a save, and the plane still holds the previous
version.** No message, no warning, and `devman doctor` reports nothing wrong.

### Evidence 2 — the fix, on a shell entry that changes nothing else

The first entry after restoring the module is not proof: the module is part of
`plan`, so the entry changed and the projection would have been rebuilt anyway.
The decisive test is an edit with **the module already in place**:

```
$ sed -i 's/VERSION-THREE/VERSION-FOUR/' .devman/workflows/_r8probe.yaml
$ devenv shell -- true                                     # 2.3 s
$ grep -n VERSION ~/.local/share/devman/projects/devman/workflows/_r8probe.yaml
12:    run: echo VERSION-FOUR
```

Byte for byte, by the same test the guard uses and by `diff`:

```
$ src=$(<.devman/workflows/_r8probe.yaml)
$ have=$(<~/.local/share/devman/projects/devman/workflows/_r8probe.yaml)
$ [ "''${have: -''${#src}}" = "$src" ] && echo MATCH
MATCH

$ tail -n "$(wc -l < .devman/workflows/_r8probe.yaml)" \
    ~/.local/share/devman/projects/devman/workflows/_r8probe.yaml \
  | diff - .devman/workflows/_r8probe.yaml && echo IDENTICAL
IDENTICAL
```

### Evidence 3 — the cost, decomposed, and why the first version failed

§5.2 forbids a fork on the common path, so S-5a proposed bash parameter
expansion. **Forkless was not the hard part.** Each stage added to the existing
`local` loop, 300 firings each:

```
1  glob + [ -f ] only                    0.129 ms per firing
2  + one $(<file)  (the source)          0.296
3  + both $(<file) (source + projection) 0.495     <- the reads cost 0.37 ms
4  + ''${have%"$body"}                     6.057     <- +5.6 ms
5  + [ "''${have: -''${#body}}" = "$body" ]  1.256     <- +0.76 ms
```

**The two reads do not fork**, which is the part §5.2 put in doubt: bash reads
`$(<file)` internally. **Bash's pattern removal scans and a slice does not**, and
over 18 KB that is a factor of 7.4.

The shipped shape, 500 firings:

| | per firing | per shell entry (fires twice) |
|---|---|---|
| pre-R-8, names only | 0.132 ms | 0.26 ms |
| **R-8, tail slice** | **1.409 ms** | **2.82 ms** |
| the `%` version, for the record | 6.057 ms | **12.11 ms — over budget** |
| `sha256sum` per override, the forking version | 23.3 ms | 46.6 ms |

**Criterion 7's budget is 10 ms per entry, so the per-firing budget is 5 ms.**
R-8 uses 1.41 of it. The version that reads more naturally used 6.06 and would
have broken the criterion the same commit claimed to respect.

**A repository with no override pays the glob and nothing else.** That is every
repository in waves 2 and 4 until it writes one, and `devman` — with five — is
the worst case on the machine.

### Evidence 4 — the paired end-to-end measurement, which cannot see it

Criterion 7 asks for an interleaved paired difference. Three rounds, each
variant getting one discarded warm-up entry (the module change forces a re-eval
and a full re-projection) and six timed entries:

```
round 1  pre : 1752 1768 1673 1719 1789 1687 ms
round 1  R-8 : 1664 1775 1694 1711 1744 1799 ms
round 2  pre : 1819 1791 1716 1729 1742 1770 ms
round 2  R-8 : 1563 1558 1776 2056 1653 1753 ms
round 3  pre : 1798 1799 1774 1746 1667 1672 ms
round 3  R-8 : 1608 1745 1750 1755 1740 1760 ms

pre-R-8  n=18  mean 1745.1  median 1749.0  sd  47.9  range 1667-1819
R-8      n=18  mean 1728.0  median 1744.5  sd 109.1  range 1558-2056
paired delta: mean -17.1 ms, sd 134.8, range -256..+327
```

**R-8 measures 17 ms FASTER, which is noise and not a result.** A `devenv shell
-- true` is ~1.75 s with a 500 ms spread; 2.8 ms is not resolvable inside it.
This is exactly what §14's commentary on criterion 7 warns about — measuring the
absolute figure measures the machine. **The isolated loop above is the
measurement; this one is the control that shows why it had to be isolated**, and
it is recorded rather than dropped because a null result here is easy to
misreport as a pass.

### What else changed

**`modules/devenv.nix`, two comments that made the bug invisible.** The one above
`entryTemplate` said the projection was a symlink, so an edit was already what
Dagu reads. The one above the `.devman/workflows/` loop said an edit reaches
Dagu at the next shell entry. Both now say what is true and why it was not.

**`STAGE_6_LOG.md`, corrected where it stands**, as S-5a asked. D6's paragraph
gains a boxed correction, S3's `devenv shell -- true` comment gains the reason
it worked there and not for an override, and D6's row in the conditions table
becomes "partly met, and stage 7 found the gap". Nothing measured in stage 6 is
altered — the claim that failed is the one D6 exists to make.

### Verdict

**R-8 ships.** The plane is back to 25 workflows with the probe removed, `doctor`
is clean, and `devman`'s own `check` and `test` both succeeded on the changed
tree:

```
{"dag":"devman-check","run_id":"034CiMzNZCwRQmBOphsSiI","status":"succeeded",…}
{"dag":"devman-test", "run_id":"034CiMzjV6rOUtubVUYwrJ","status":"succeeded",…}
```

### Charter impact

**§5.2's cost budget is re-checked and holds**, which is the section S-5a named
as the one to look at if R-8 changed the guard. The hook still forks nothing on
the common path, and the added 2.82 ms per entry is inside criterion 7's 10 ms.
**No charter text changes.** §9.3's "the projection is reconstructable by
entering the shell" was already the promise; R-8 is what makes it true for an
edited override.

### Rule 7 — what this entry did to the machine

| | |
|---|---|
| `devman` | `modules/devenv.nix` — the guard and two comments |
| the registry | re-projected several times; ended at 25 workflows, `doctor` clean |
| a probe | `.devman/workflows/_r8probe.yaml`, created, edited four times, **deleted**; no `_r8probe` file or `dags/` link remains |
| runs added | 2 (`devman-check`, `devman-test`), both succeeded |
| the module file | swapped between two variants 6 times for the paired measurement, and left on R-8 |

---

## I-11 — The overnight scheduled runs, after wave 1's re-pins

**Answer: six `maintain` runs and exactly one `plane-report`, all succeeded,
and stage 6's three-minute silence did not reappear.** The longest gap between
the scheduled minute and a run starting was **596 ms**. Every one of the seven
started inside the same second Dagu dispatched it.

**`pyjutsu-maintain` succeeded**, which is what S-5 predicted when `doctor` left
`maintain`. It had failed 4 of its previous 5 runs.

### The night this measures, and a correction to the plan

**The plan expected this evidence on the night of 23 August. It was not there,
and the reason is chronology rather than a fault.** Wave 1's re-pins landed
between 19:30 and 21:07 on 23 August, and `plane-report` was authored at 19:42
that evening (`ccd91a0`). So:

| | |
|---|---|
| 23 Aug 00:05 | six `maintain` runs fired and succeeded — but ~15 h **before** wave 1, under the old two-step `maintain` (`prune` + `doctor`) |
| 23 Aug 00:20 | **no `plane-report`**, because the workflow did not exist for another 19 hours |
| **24 Aug 00:05** | six `maintain` runs, prune-only, **after** every re-pin — this entry |
| **24 Aug 00:20** | one `plane-report` — this entry |

The 23 August runs are recorded here because they were read first and would
otherwise look like the answer.

### Versions

Dagu **2.15.0** (`MainPID` 2216556, started 23 Aug 20:38:03), devenv **2.1.2**,
devman **0.3.0** from the machine closure. 6 projects, 25 workflows.

### Command

```bash
journalctl --user -u dagu --since "2026-08-24 00:00" --until "2026-08-24 00:30" \
  | grep "Dispatching planned run"
# then, per project, the report, the metadata.jsonl line and the run record
```

### Evidence 1 — the dispatch, and the gap per repository

Every line the daemon wrote in that half hour is a dispatch. There are seven.

```
00:05:00.003  devman-maintain
00:05:00.003  observantic-maintain
00:05:00.003  pyjutsu-maintain
00:05:00.003  nix-paseo-maintain
00:05:00.004  pydantree-maintain
00:05:00.010  siteman-maintain
00:20:00.002  devman-plane-report
```

The run's own log file names the millisecond it started, so the gap is exact:

| DAG | dispatched | started | gap |
|---|---|---|---|
| `nix-paseo-maintain` | 00:05:00.003 | 00:05:00.087 | **84 ms** |
| `devman-maintain` | 00:05:00.003 | 00:05:00.097 | **94 ms** |
| `pydantree-maintain` | 00:05:00.004 | 00:05:00.101 | **97 ms** |
| `pyjutsu-maintain` | 00:05:00.003 | 00:05:00.438 | **435 ms** |
| `siteman-maintain` | 00:05:00.010 | 00:05:00.489 | **479 ms** |
| `observantic-maintain` | 00:05:00.003 | 00:05:00.599 | **596 ms** |
| `devman-plane-report` | 00:20:00.002 | 00:20:00.065 | **63 ms** |

**The spread is six repositories starting inside 512 ms of each other**, which is
S-1's picture exactly: the scheduler dispatches all of them at once and nothing
throttles them. Six is far below where that matters.

### Evidence 2 — six reports, six records, all `succeeded`

Every project wrote its `maintain-<run-id>.md` and every `metadata.jsonl` gained
one line:

```
devman       034CVHpDuplH9fI001dbCL  succeeded   27 reports before, 27 after — 0 pruned
siteman      034CVHpE0rWjs1c19XBgWs  succeeded    8 reports before,  8 after — 0 pruned
nix-paseo    034CVHpDuhR8nVwJUtJCix  succeeded    5 reports before,  5 after — 0 pruned
pyjutsu      034CVHpE0dO0qHRPCHrfql  succeeded    7 reports before,  7 after — 0 pruned
pydantree    034CVHpE0kcmrL6OMGREkb  succeeded    5 reports before,  5 after — 0 pruned
observantic  034CVHpDuY0vj3KrElsHlx  succeeded    6 reports before,  6 after — 0 pruned
```

Each run record holds **one node**, named `prune`. The 23 August records hold
two, `prune` and `doctor`. That is R-1 landing, visible in the run data.

**Nothing was pruned anywhere, and that is correct** — `KEEP_DAYS` is 7 and no
report is older than two days. The prune path is exercised; its effect is zero
because there is nothing yet to remove.

### Evidence 3 — exactly one plane report

```
$ find .devman/.runs/reports -name 'plane-*.md' -newermt "2026-08-24 00:00" | wc -l
1
```

`plane-034CVeeG6jG8CqPSBwTnnQ.md`, 2.0 s, `doctor exit: 0`, holding the whole of
`devman doctor` — 6 projects, 25 workflows, nothing to report. **One report for
the machine, not six**, which is `PROPOSAL.md` §5's whole argument, running.

**And the report proves the handover point about the closure.** Its `doctor`
output has no `trigger target` line, because the `devman` the DAG ran is the one
in the machine closure and R-4d is not in it yet. The plane reports on itself
with the `devman` the machine has, which is the version a `nixos-rebuild switch`
changes.

### The question this investigation exists for

**`STAGE_6_LOG.md` S3's three-minute silence did not reappear.** Its case was a
DAG the daemon already knew *without* a schedule that then gained one: three
scheduled minutes passed with nothing, and a restart cured it.

**Two things happened here that would have shown it, and neither did:**

1. **Five repositories were re-pinned at 21:01–21:07 on 23 August**, after the
   daemon's last start at 20:38:03. Their `maintain` DAGs were re-projected —
   new file content, same name, same expression — and every one dispatched on
   the first scheduled minute after.
2. **`plane-report` is a new scheduled DAG**, projected at 20:56 on 23 August,
   also after the last start. It fired at its first scheduled minute, 63 ms late.

```
$ systemctl --user show dagu -p ActiveEnterTimestamp -p NRestarts
ActiveEnterTimestamp=Sun 2026-08-23 20:38:03 EDT
NRestarts=0
```

**The honest limit on this result.** The 20:38:03 start is the recovery from the
90-second outage S-1 caused, and `devman`'s own re-pin at 19:30 came *before*
it. So `devman-maintain` cannot be counted as a re-pin that needed no restart —
one happened in between, by accident. **The five that can be counted are
`siteman`, `nix-paseo`, `pyjutsu`, `pydantree` and `observantic`**, and they
are enough: five re-pins and one new scheduled DAG, no restart, no silence.

**What is still unmeasured is stage 6's exact transition** — a DAG the daemon
knows without a schedule that gains one. Nothing on the plane underwent it
tonight, so this entry does not close `OPEN_QUESTIONS` §7. It closes the
question the plan asked, which is whether a re-pin reproduces it. It does not.

### Rule 7 — what this entry did to the machine

**Nothing.** Every command is a read: `journalctl`, `find`, `sed`, and reads of
`status.jsonl` and `metadata.jsonl`. No workflow was run, no file projected, no
service touched.

**One thing another entry did, recorded here because it shows in this evidence.**
Editing `src/devman/doctor.py` for R-4f and R-4d fired the watcher three times
at 23:53:38, 23:53:40 and 23:53:41 — three `devman/format` runs, all succeeded.
They are in the plane report's watcher section above. That is the watcher
working, and it is why the report names `doctor.py` three times.

### Charter impact

**None.** §8's three arrows are unchanged and criterion 12's narrowing is
already R-6's. This entry is confirmation, not a new fact about the design.

---

## R-6 — The charter, and the three corrections that belong to the proposal

**Six charter sections change, not five.** `PROPOSAL.md` §9 drafted five. S-1
forced a sixth — criterion 12 — and that one had no drafted text because the
measurement that forced it came after §9 was written. **The charter asserted a
safety property the plane does not have.**

### Versions

The charter is `.scratch/projects/006-automation-plane/CONCEPT.md` at
`9a0f5f4`. No code and no group file changes in this entry; it is documentation
against measurements already recorded above.

### The six charter edits

| Section | What changed | Forced by |
|---|---|---|
| §7.1 | `check`, `validate`, `full-test` becomes `check` and `test`; the ladder is two rungs and the third is stated to carry no information | `PROPOSAL.md` §9, and §12 rule 4's measurement |
| §8, the boxed note | "Reactivity is its own group" becomes "a workflow that writes the repository's own files without being asked is its own group" | R-1/S-2 — `maintain` self-fires and must not be exiled |
| §14, criterion 12 | **narrowed** — queues bind the enqueue path and not `schedule:` | **S-1** |
| §14, criterion 14 | gains its mechanism — one `devenv tasks run` per workflow declares no order | I-3, and §1.1 |
| §16 | "Python and Nix, and nothing else yet" becomes "there are no ecosystem groups" | R-3 — the `python` group's content was a namespace prefix |
| §13 | gains "Stage 7 — the standard set" | the rollout |

### The one that was not drafted, and it is a narrowing of a safety claim

Criterion 12 read **"Queues are real"**, with the caveat that `dagu start`
bypasses queues. That caveat is true and incomplete. **Dagu's own scheduler
bypasses queues too**, and the charter never said so, so a reader took
`max_concurrency` to be a machine-wide bound on everything the plane runs.

The row and the commentary now say which path a queue binds:

```
$ sed -n '/^| 12 |/p' .scratch/projects/006-automation-plane/CONCEPT.md
| 12 | Queues bind the enqueue path | two workflows naming the `exclusive` queue
serialize **when enqueued** — `dagu start` and Dagu's own scheduler both bypass
queues entirely, so the measurement must use `dagu enqueue`, which is the path
§8's first two arrows take |
```

The commentary carries S-1's numbers — 58 enqueued never exceeding 4 and
draining in 311 s, 58 scheduled all at once with queue depth 0, and two
`exclusive` DAGs starting in the same second on the installed plane — and ends
on the rule that replaces the property: **what the plane schedules must be cheap
by construction.**

### The three corrections that belong to `PROPOSAL.md`

**These are not charter text. They are places the proposal argued from something
a gate later measured.**

**§1.1 — the stated loss is smaller, and there is a second trade (I-3).** §1.1
said the failing task's name moves "from a step name to a log line". It reaches
three places, including Dagu's recorded `error` field, which the UI renders. The
caveat is the stream split: on devenv 2.1.2 the name appears **0 times** on the
step's `.out` file, so the instruction to a developer is read `.err` or read the
`error` field. And §1.1 never named the second trade — under a devenv `after`
list siblings run **concurrently**, so the one-step shape trades `type: chain`'s
fail-fast for fan-out.

**§6 — "no automatic run breaks" is bounded (I-5).** True of the schedule, not
of the watcher. `format` is watcher-fired and does call a repository task. The
claim survives only because `devman` is the sole taker of `python-format` and
owns the group files. §6 now states the general rule: a repository may be
re-pinned ahead of its task rename **only while every automatically triggered
workflow calls no repository task**.

**§12 gains an eighth rule, and §5 loses its mechanism (S-1).** Rule 8 is
"anything expensive, on a schedule", with S-1's figures. §5's paragraph "The
schedule shape at 58 repositories" is corrected in place rather than deleted:
its conclusion holds, its stated reason does not, and its second-order effect
was backwards — a developer's `format` at 00:05 does **not** queue behind the
scheduled burst, because the burst is not in the queue. It competes for CPU
instead, bounded by nothing.

### Verdict

**R-6 is done for every measurement Gates 0–3 produced.** Two sections stay open
by design and are named rather than left silent:

- **§5.2's cost budget** — S-5a flagged it as the section to re-check *if* R-8
  changes the guard. R-8 has not landed at the time of this entry, so §5.2 is
  untouched here and R-8 owns it.
- **§15.2's whitelist** — untouched until wave 3 fires it against `fsdantic`.

### Charter impact

**This entry is the charter impact.** Recorded so that the next stage reads one
list rather than nine.

---

## Where stage 7 stands

**Done:** Gates 0–3 (I-3, I-5, I-6, S-3, S-2, S-6, S-5, S-4, S-1, I-2a), R-1,
R-2, R-3, R-5, I-2b and I-9, and then **R-6, R-4f, R-4d, R-8, I-11 and I-4**.

**Everything the gates produced is built or decided:**

| | |
|---|---|
| R-4a | **refused** on evidence (S-4). Do not reopen without a new measurement |
| R-4b | **not needed** on evidence (I-2a) |
| R-4c | **unbuilt.** It is gated on I-10, which is in the tail |
| R-4d | **built** — `entry.workflow in proj.workflow_names()` |
| R-4e | **held**, by S-4's decision, until the hazard bites in the wild |
| R-4f | **built** — 25 files, 2.33 s serial to 0.82 s across 8 workers |
| R-8 | **built** — an edited override re-projects, at 2.82 ms per shell entry |

**Outstanding:**

| | |
|---|---|
| R-7 | waves 2, 3 and 4 — **blocked on a pushed rev on `main`** |
| the live half of I-4 | pass/fail per repository, with the 19 `enterTest` repositories first |
| the tail | I-7, I-10, I-12, I-13. They gate nothing |

**Wave 4 is smaller than wave 1 suggested.** I-4 found 54 of 58 repositories
have a suite and 48 of those have no task naming it, so the per-repository cost
is one `devenv.nix` line. Wave 1's two failures — `pyjutsu`'s native build and
`pydantree`'s 256 `ruff` findings — are not the population's shape.

### What blocks wave 2

**Waves 2–4 pin `ref=main&rev=`, and `main` does not carry R-8, R-4d or R-4f.**
Those repositories consume the module and the CLI, so wave 2 cannot start until
a rev carrying them is on `main`. The owner's chosen route is a pull request
from `dagu-devenv-automation-eli5`, and it is open:
**https://github.com/Bullish-Design/devman/pull/129**, head `008ecb9`.

**Wave 2 starts when that merges**, and its order is `PROPOSAL.md` §8: five
repositories — `webdantic`, `poddantic`, `parsedantic`, `nix-desktop` and
`loci.nvim` — of which `nix-desktop` and `loci.nvim` passing is the proof the
universal contract is not a Python fiction. `nix-desktop` is one of I-4's four
with no suite, so it is also the first repository that has to decide what
`base:test` means with nothing to test.

**And the machine's `devman` is the closure's.** R-4d and R-4f are in the source
tree and not in the installed binary — the plane report of 24 August shows
`doctor` without the `trigger target` line, which is the proof. A
`nixos-rebuild switch` is what changes that.

### Wave 1's five re-pins were committed and not pushed, until now

**Found on 24 August while auditing what was published.** R-5's five repository
commits were made on 23 August at 21:01–21:07, on each repository's own `main`,
and **none of them reached `origin`**. The plane worked anyway, because a
projection reads the working tree rather than the remote, so nothing on this
machine noticed and nothing in this log said so.

They were pushed on 24 August, unchanged, each still pinning `02d00f6` — a rev
that was already on `origin/main`, so no commit needed rewriting:

| Repository | Commit | pushed |
|---|---|---|
| `siteman` | `d249bfa..541cf25` | `main -> main` |
| `nix-paseo` | `c1dd6ec..65f564c` | `main -> main` |
| `pyjutsu` | `71a765d..8323e09` | `main -> main` |
| `pydantree` | `d421a85..be150be` | `main -> main` |
| `observantic` | `e02d1b8..0f835d4` | `main -> main` |

All five are now clean and 0 ahead / 0 behind. `devman`'s own re-pin is on
`dagu-devenv-automation-eli5`, not on `main`, and PR #129 is what lands it.

**The lesson for waves 2–4, and it is a checklist item rather than a design
fact:** a wave's proof — registry count, `doctor`, `check`, `test` — passes
identically whether or not the repository's commit was pushed. **The push is not
observable from the plane.** Each wave's proof must include
`git rev-list --count @{u}..HEAD` per repository, or the next wave will end the
same way.

### A note on branches

Partway through Gate 2 something in this environment checked out `main` and
fast-forward merged `spike/007-gate-2` into it, and a routine `git push` sent it
to `origin`. The owner's decision was to leave `main` where it is. So:

| Branch | Carries |
|---|---|
| `origin/main` at `02d00f6` | the stage-7 group content, `plane-report`, `devman`'s own edits, and this log up to Gate 3 — **this is what wave 1 pins** |
| `dagu-devenv-automation-eli5` | all of the above, plus R-3, R-6, R-4f, R-4d, R-8, I-11 and I-4 |
| `spike/007-gate-2` | the Gate 2 spike history, now an ancestor of both |

## R-7 wave 4, batch 1 — ten adopted, four with the template-default `enterTest`

**Answer: batch 1 is done — ten repositories, all registered, all pushed. The
live half of §12 rule 4 has its first direct count: 4 of the first 10
`enterTest` repositories carried the devenv template default.** The work per
repository stayed one `devenv.nix` task line plus the input line; the costs that
surfaced were environment facts, not repair passes.

### Versions

devenv **2.1.2**, Dagu **2.15.0**, devman **0.3.0** from the machine closure.
Every repository pins `ref=main&rev=f20a9c11cd6b062aa6646e8b72b9767d7e90a522`.

### The pre-checks, per repository (wave 2b's two steps)

`devenv shell -- true` passed in all ten (I-4b's survey re-confirmed, not
trusted). `command -v <tool>` found the suite runner in six; **four needed the
`uv run` resolution** because `pytest` lives in `[project.optional-dependencies]
.dev` (boomtube, browsee, cairn) or the tool lives in the venv the task runner
cannot see (below).

### Two environment facts the batch bought, neither of which is a repair

**The task runner's PATH is not the interactive shell's PATH.** `fleetman`'s
venv has `pytest` (requirements `-e .[dev]`) and the interactive shell finds it,
but `devenv tasks run base:test` failed with `pytest: command not found`. The
task environment does not put the venv bin on PATH. The task is `uv run pytest
-q`. **A `command -v` inside the interactive shell is not a proof for the task
environment** — wave 2b's check needs the same scope for tools that live in a
devenv-managed venv.

**`forgelab` inverted it.** The interactive shell run failed with 45
`ModuleNotFoundError: No module named 'pyjutsu'`, and `repoman-sync` did not
help (toolchain is machine-level). The plane's own run — `devenv tasks run -v
base:test` under the daemon's environment — passed: **Ran 85 tests, OK**, three
times. The task environment reaches the machine repoman venv that holds the
`pyjutsu` wheel; the interactive shell does not. Recorded as the plane's
environment being the one that matters, and as a reminder that the opposite of
wave 2b's wrong guess is also a wrong guess: **the shell is not the task
environment either.**

### The template-default count (the live half of §12 rule 4)

| Repository | `enterTest` | `base:test` |
|---|---|---|
| `atuout` | custom (uv sync + ruff + ty + pytest) | `uv run pytest` |
| `atuout-reconciler-test` | custom (uv sync + ruff + mypy + pytest) | `uv run pytest` |
| `boomtube` | **template default** | `uv run --extra dev pytest` |
| `browsee` | **template default** | `uv run --extra dev --extra scrape pytest` |
| `cairn` | custom (sandbox gate) | `CAIRN_REQUIRE_SANDBOX_TESTS=1 uv run --extra dev pytest -q --cov=cairn --cov-report=term-missing` |
| `embeddy` | **template default** | `LD_LIBRARY_PATH=…zlib… uv run --group dev pytest` |
| `fleetman` | custom (`pytest -q`) | `uv run pytest -q` |
| `forgelab` | custom (unittest) | `PYTHONPATH=src python -m unittest discover -s tests` |
| `fornix` | custom (`uv run pytest -q`) | session-bus env + `uv run pytest -q` |
| `grail` | **template default** | `uv run pytest` |

**4 of 10 carried the template default** — the number §12 rule 4 was written
for, now measured directly. None of the four got `devenv test` as `base:test`.

### Evidence — per repository

| Repository | Commit | `check` | `test` |
|---|---|---|---|
| `atuout` | `3ae56d0` | ok — ruff clean | ok — **75 passed**, 1 skipped |
| `atuout-reconciler-test` | `b9b12a2` | ok — ruff clean | ok — **63 passed** |
| `boomtube` | `868d208` | ok — ruff clean (`src`) | ok — **225 passed** |
| `browsee` | `55f5d28` | ok — ruff clean (`src`) | **1 failed, 489 passed** — see below |
| `cairn` | `b2b4742` | ok — ruff clean | ok — **314 passed**, 8 deselected |
| `embeddy` | `42cff82` | ok — ruff clean | ok — **535 passed**, 3 skipped |
| `fleetman` | `98e1947` | ok — compileall | ok — **105 passed** |
| `forgelab` | `39f17b3` | ok — compileall | ok — **85 tests, OK** |
| `fornix` | `0e5ca5e` | ok — ruff clean (`src`) | **1 failed, 181 passed** — see below |
| `grail` | `7aad6f2` | **failed — 83 ruff findings** (recorded) | ok — **192 passed** |

All ten at `@{u}..HEAD = 0` (pushed; wave 1's lesson applied per repository).

**`browsee`'s one failure is a wall-clock time bomb, traced not guessed.** The
test `test_dispatch_moderate_confidence_uses_fallback` builds a skill whose
`last_success` is the fixture's hardcoded `2026-05-30T00:00:00Z`. The
dispatcher's 30-day staleness check compares it to `datetime.now`, so since
~2026-06-30 the confidence drops 0.6 → 0.4 and the expected mode
`replay_with_fallback` becomes `explore`. The fixture was added 2026-06-11 when
it was 12 days old. Not the plane's regression; recorded, not fixed.

**`fornix`'s one failure is a host btrfs quota.** `test_fork_and_remove_subvolume
_roundtrip` creates a subvolume under pytest's `/tmp` basetemp and deletes it;
`/tmp` is a btrfs volume with qgroups the user cannot manage, so the delete
returns EPERM (reproduced outside pytest: `btrfs qgroup show /tmp` →
`Operation not permitted`). The suite's own guard skips when `tmp_path` is not
btrfs, and it is. The e2e test that needed the user-session bus now passes —
the task states `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` defaults,
mirroring `enterShell`. The btrfs failure is the repository's environment, not
the plane's; recorded, not fixed.

**`grail`'s `check` failure is the repository's own lint debt.** 83 `ruff`
findings in the repo's own `src`/`tests` scope (select `E,F,I` per its
pyproject). `ruff check .` finds 321, most under `.context/monty-main/` —
vendored. Adoption and repair stay separate; the 83 are recorded. One side
effect worth naming: grail's suite rewrites tracked `.grail/*/check.json`
fixtures with the current pytest tmp path — the tree was restored after the
proof, and the repo's own suite dirties its tree on every run.

### The adoption shape, and where the batch spent its effort

Every repository got the same three pieces: the `devman` input (pinned `f20a9c1`
with `imports: devman/modules`), the `devman.enable` block with `groups =
["base"]`, and two task lines. The effort went to naming the honest suite:

- **`embeddy`** is a uv virtual workspace: its dev deps are `[dependency-groups]`
  (`--group dev`), not extras. Its `qdrant_client`/numpy wheel needs `libz.so.1`
  on the loader path, which the devenv shell does not provide — the task
  prepends `${pkgs.zlib}/lib`.
- **`browsee`**'s suite imports `websockets`, which lives in the `scrape` extra,
  not `dev` — 26 ImportError failures without it.
- **`boomtube`/`browsee`/`cairn`** lint is scoped to the repo's own
  `src = ["src"]` ruff config; full-tree `ruff check .` counts `.scratch/` and
  vendored trees that are not source.
- **`fleetman`/`forgelab`** declare no linter at all, so `base:check` is the
  stdlib compile of `src` (the direct shape, like `nix-desktop`).

### Evidence — the batch proof

```
$ ls ~/.local/share/devman/projects | wc -l        21   (was 11)
$ ls ~/.local/share/devman/dags/*.yaml | wc -l     70   (was 40)
$ devman doctor                                     Nothing to report.
```

**I-2b, a fourth point on `doctor`'s curve — five timings at 21 projects:**

```
5415  5914  5766  5760  5933 ms      mean 5758 ms over 70 workflows = 82.2 ms/file
```

I-2a 83.6, 87 at six projects, 78.9 at 34 workflows — **82.2 at 70 workflows.
The serial `check_load` line holds.** R-4f remains merged and uninstalled.

**I-1 pending, not provable from here:** the next 00:05 `maintain` sweep and the
single `plane-report` are scheduled for the night after this batch. The batch
recorded its registry and pushed commits instead of waiting.

### Verdict

Batch 1 passes. Ten of ten registered, ten of ten pushed, `doctor` clean at 21
projects. Two recorded test failures and one recorded lint debt are all
pre-existing and traced to their mechanism. **The template-default count for the
batch is 4 of 10, and none of them adopted `devenv test`.**

### Charter impact

**None.** §5.2's shell-entry registration and §12 rule 4's warning both held as
written; the batch supplied the number rule 4 lacked.

### Rule 7 — what this entry did to the machine

| Repository | Commit | State |
|---|---|---|
| `atuout` | `3ae56d0` | committed, **pushed** to `origin/main` |
| `atuout-reconciler-test` | `b9b12a2` | committed, **pushed** — see note |
| `boomtube` | `868d208` | committed, **pushed** to `origin/main` |
| `browsee` | `55f5d28` | committed, **pushed** to `origin/main` |
| `cairn` | `b2b4742` | committed, **pushed** to `origin/main` |
| `embeddy` | `42cff82` | committed, **pushed** to `origin/main` |
| `fleetman` | `98e1947` | committed, **pushed** to `origin/main` |
| `forgelab` | `39f17b3` | committed, **pushed** to `origin/main` |
| `fornix` | `0e5ca5e` | committed, **pushed** to `origin/main` |
| `grail` | `7aad6f2` | committed, **pushed** to `origin/main` |

**`atuout-reconciler-test` is a git worktree of `atuout` on branch
`reconciler-process-test`, which had no upstream.** Pushing created
`origin/reconciler-process-test` (set as upstream, `@{u}..HEAD = 0`). Recorded
here because it is a new remote branch the owner did not ask for; the 
checkout's in-progress work (`pyproject.toml`, `tests/test_reconciler_process
.py`) was not committed.

**Pre-existing changes left untouched:** `forgelab/AGENTS.md` (fornix direct-
workflow note), `atuout`'s untracked `.scratch/projects/002-atuin-ai-client/
reference/`, and `atuout-reconciler-test`'s in-progress test work. **Restored
after proof:** `grail/.grail/*/check.json` (rewritten by the suite's own run).
`devenv.lock` was committed where the repository tracks it; `atuout`,
`browsee` and `grail` ignore it, and the adoption there is the two devenv files
alone.

## R-7 wave 4, batch 2 — ten adopted, the alias repo, and two consumer-facing modules

**Answer: batch 2 is done — ten repositories, all registered, all pushed. The
template-default count is now 7 of the 15 `enterTest` repositories (3 of this
batch's 5). Every suite passed; batch 2 produced no recorded failure.**

### Versions

devenv **2.1.2**, Dagu **2.15.0**, devman **0.3.0** from the machine closure.
Every repository pins `ref=main&rev=f20a9c11cd6b062aa6646e8b72b9767d7e90a522`.

### The template-default count, extended

| Repository | `enterTest` | `base:test` |
|---|---|---|
| `knappy` | **template default** | `uv run --extra dev pytest` |
| `nixbuild` | **template default** | `nix flake check` (no suite) |
| `templateer_v2` | **template default** | `uv run --extra dev pytest` |
| `tyo3` | custom (maturin + pytest) | `VIRTUAL_ENV=…; maturin develop && … uv run --group dev pytest … -x` |
| `zelligate` | custom (`pytest`) | `uv run --extra dev pytest` |

**Cumulative template-default count: 7 of 15.** None of the seven adopted
`devenv test`.

### Evidence — per repository

| Repository | Commit | `check` | `test` |
|---|---|---|---|
| `knappy` | `4eecc77` | ok — ruff clean (`src`) | ok — **218 passed** |
| `nixbuild` | `6b1f13f` | ok — ruff clean (`src`) | ok — **nix flake check** all passed |
| `templateer_v2` | `9ce584f` | ok — ruff clean | ok — **444 passed**, 9 skipped |
| `tyo3` | `94d429f` | ok — ruff clean (`src`) | ok — suite green |
| `zelligate` | `06d0297` | ok — ruff clean (`src`) | ok — **273 passed** |
| `loci-core` | `f3542a3` | ok — via `loci:lint` alias | ok — via `loci:test` alias |
| `allium-env` | `0cc8bd9` | ok — ruff clean (`src`) | ok — **16 passed** |
| `argentic` | `8f32312` | ok — ruff clean (`src`+`consumer/src`) | ok — suite green |
| `copyroom` | `a45a50d` | ok — ruff clean (`src`) | ok — **603 passed** (152.8 s) |
| `docman` | `279b9cb` | ok — ruff clean (`src`) | ok — **18 passed** |

All ten at `@{u}..HEAD = 0`.

### What the batch spent its effort on

**`tyo3` needed two task-env facts, both measured.** First, `maturin develop`
fails in the task environment because `VIRTUAL_ENV` is unset there (the
interactive shell sets it) — the task exports
`VIRTUAL_ENV=$DEVENV_ROOT/.devenv/state/venv`. Second, the venv python has no
pytest and the nix `pytest` wrapper delegates into the venv once `VIRTUAL_ENV`
is set, so the run must use `uv run --group dev pytest` (tyo3's dev deps are a
uv `[dependency-groups]`, not an extra). The first cold maturin build took
**546 s**; the suite itself is seconds. A timeout here would have measured the
cache, not the repository — I-4b's rule, hit for real.

**`loci-core` is the alias case** (`PROPOSAL.md` §6 rule 6). It already owns
`loci:lint`/`loci:test`; `base`'s two names forward to them with
`devenv tasks run` rather than duplicating command bodies. Its checkout was on
a detached HEAD; the adoption landed on `main` (its default branch).

**`copyroom` and `docman` are consumer-facing modules.** Their root `devenv.nix`
is what a consumer's `imports: - copyroom` / `- docman` merges, so the devman
block and toolchain live in a **dev-only layer**: copyroom already had
`dev/devenv.nix` (wired via its root `devenv.yaml`'s `- ./dev`); docman had no
such layer and its root devenv provided no Python at all, so `dev/devenv.nix`
was created (venv + devman + tasks) and the root consumer surface left
untouched. A devman block in either root would have registered project
"copyroom"/"docman" inside every consumer's shell — the exact §12 rule 5
failure this avoids.

**`nixbuild` has no suite** (its pytest config points at a `../tests` that does
not exist). Its gate is the flake: `base:check` is the repo's configured linter
(`ruff check src`, from `src/pyproject.toml`) and `base:test` is `nix flake
check` (builds the CLI package). The direct shape, like `nix-desktop`.

**`argentic`'s local `main` had no upstream.** The push itself worked
(`ade3f09..8f32312 main -> main`); only the `@{u}` proof needed
`git push -u origin main` to resolve. Recorded because it is the second
repository whose push bookkeeping differed from the default.

### Evidence — the batch proof

```
$ ls ~/.local/share/devman/projects | wc -l        31   (was 21)
$ ls ~/.local/share/devman/dags/*.yaml | wc -l    100   (was 70)
$ devman doctor                                     Nothing to report.
```

**I-2b, a fifth point on `doctor`'s curve — five timings at 31 projects:**

```
8549  8297  9032  9047  9169 ms      mean 8819 ms over 100 workflows = 88.2 ms/file
```

83.6 (I-2a), 87 at six, 78.9 at 34, 82.2 at 70 — **88.2 at 100 workflows. The
serial `check_load` line holds; it has not crossed 30 s, so `plane-report` and
OPEN_QUESTIONS §2 stay unurgent.**

**I-1 pending:** the overnight `maintain` sweep and the single `plane-report`
after both batches remain scheduled for the coming night.

### Verdict

Batch 2 passes. Ten of ten registered, ten of ten pushed, `doctor` clean at 31
projects and 100 workflows. No recorded failures. The two consumer-facing
modules prove the dev-layer pattern the plane's own repo already uses.

### Charter impact

**None.** §12 rule 4's count is now 7 of 15 measured directly; nothing the
batch found contradicts a charter sentence.

### Rule 7 — what this entry did to the machine

| Repository | Commit | State |
|---|---|---|
| `knappy` | `4eecc77` | committed, **pushed** to `origin/main` |
| `nixbuild` | `6b1f13f` | committed, **pushed** to `origin/main` |
| `templateer_v2` | `9ce584f` | committed, **pushed** to `origin/main` |
| `tyo3` | `94d429f` | committed, **pushed** to `origin/main` |
| `zelligate` | `06d0297` | committed, **pushed** to `origin/main` |
| `loci-core` | `f3542a3` | committed, **pushed** to `origin/main` (was detached) |
| `allium-env` | `0cc8bd9` | committed, **pushed** to `origin/main` |
| `argentic` | `8f32312` | committed, **pushed** to `origin/main` (upstream set) |
| `copyroom` | `a45a50d` | committed, **pushed** to `origin/main` |
| `docman` | `279b9cb` | committed, **pushed** to `origin/main` |

**Left on the machine:** `tyo3`'s maturin build cache (546 s cold, warm now),
which is what made the batch's long pole short on re-run. Nothing was deleted.
`loci-core` and `argentic` were moved from detached HEAD to their local `main`
(the adoption branch); both were clean before and after.
