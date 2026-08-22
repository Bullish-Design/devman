# STAGE 4 — what was measured while giving the plane something to do

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules,
`STAGE_2_LOG.md` what stage 2 found while turning the plane on, and
`STAGE_3_LOG.md` what stage 3 found while making it react. This holds stage 4,
in the same shape: the answer, the versions, the exact command, the evidence,
and the charter impact.

**Stage 4 is the first stage whose deliverables are files rather than
machinery**, so one more column matters in every entry below: *what a person
reads afterwards*.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, installed, running as `systemd --user` unit `dagu` |
| devenv | 2.1.2 |
| devman | 0.3.0, `/run/current-system/sw/bin/devman` — `run`, `show`, `doctor`, `watch` |
| watchexec | 2.5.1, running as `systemd --user` unit `devman-watch` |
| Registry | `~/.local/share/devman/` — 6 projects, 19 workflows, 19 DAGs |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5` |

---

## S1 — What "done" means for stage 4, written before anything was built

**Why this entry exists.** Stages 1, 2 and 3 each closed on a table of
measurements somebody else wrote down first: §14's seventeen criteria.
**§14 contains no stage-4-only criterion**, so stage 4 is the first stage whose
success has no measured definition. `STAGE_4_PROMPT.md` §6 requires this entry
to be written first and to be what the stage is judged against. It was written
before the first deliverable file existed, and it has not been edited since —
later entries record where it was met and where it was not.

**The state it was written against**, checked rather than copied forward:

```
$ devman doctor
devman doctor — 6 projects, 19 workflows
ok  plane / queues / validate / queue names / literal dir / shadowing /
    stale entries / run output / cross-repo / watcher            (ten checks)
Nothing to report.                                               exit 0
```

### The nine conditions

**D1 — Six deliverables, and each one has run.** §13 names six:
`review workflows`, `release`, `maintenance`, `benchmark campaigns`,
`agent workflows`, `policy gating`. Each is a file in one of §7.3's three
homes. **A workflow that was written and never run is not delivered**: each one
runs at least once on the installed service, in a real repository, and the entry
quotes its `metadata.jsonl` line and its log.

**D2 — Measured by coverage, not by count.** Six files that all run in devman's
own checkout prove less than two a second repository takes unedited. So:

- at least one deliverable reaches **three or more** registered repositories
  with no edit to any of them beyond the group name and the task names that
  group asks for;
- at least one deliverable is run in a **second** repository, unedited, and the
  entry quotes both runs;
- every deliverable states **which of the three homes** it landed in — a group
  every repository takes, a group taken by name, or one repository's own
  `.devman/workflows/` — and which measurement or rule put it there (§16's
  promotion rule: a group begins when a second repository wants the same file).

**D3 — Every criterion that holds must still hold, measured rather than
asserted.** A criterion-by-criterion table against §14, in the shape of stage
2's S17 and stage 3's S12. Four are re-run by command rather than reasoned
about, because content pressures them hardest:

| # | Why stage 4 pressures it |
|---|---|
| 1 | new files evaluate under both interfaces; `nix flake check` must still pass |
| 10 | a release wants a version, a campaign wants a target, an agent wants a path — each is a route to an absolute path in a workflow |
| 14 | a campaign and a gate both want an order, and devenv already states one |
| 17 | a release and an agent run both want to know *which project* — the registry is the only answer, and reading it must stay the only way in |

Criterion 13 is re-run as well, because stage 4 adds workflows that **write into
a tree the watcher watches** while the watcher is running.

**D4 — Grow the plane only under a measurement, and record the measurement
first.** §7.1's list of global names stays at **four**, §10's command list at
**four** (`run`, `show`, `doctor`, `watch`), and §7.4's repo interface at
**three keys** — unless an entry below records the run that could not be written
without the growth, *before* the commit that grows it. The same rule covers a
new queue name, a new machine-module option and a new registry field.

**D5 — Six decisions answered with evidence, none deferred.**
`STAGE_4_PROMPT.md` §7 names them: how scheduled work is triggered; whether
stage 4 needs a secret and whether the machine module grows to supply one;
whether agent workflows fit the contract, and how an argument reaches a run;
whether policy gating needs a fifth global name; which queue a benchmark
campaign names; and where each deliverable lives. Each gets a stated answer,
with the command that decided it. "Left for stage 5" is not an answer.

**D6 — Every deliverable leaves something a person can read without re-running
it.** §10 of the prompt is explicit that a wrong answer from stage 4 is a
*successful run that did the wrong thing*, and that the plane will not grow a
check for it. So visibility is the deliverable's own job: every stage-4 run
leaves, in the triggering project's own tree, its `metadata.jsonl` line **and**
either a report under `.devman/.runs/reports/` or a log that holds the finding
rather than only the verdict. **A run whose only evidence is its exit code is
not delivered.**

**D7 — A gate that fails is a gate; a gate that skips is not.** Any deliverable
that decides whether something may proceed records a **failed** run when it
refuses. This is stated in advance because the plane already contains the
opposite pattern for a good reason — `python-format`'s step-level precondition
records `Succeeded` with a skipped step, so that a self-stopping loop does not
fill the history with things that look like failures (S6). A release that
silently skips is D6's failure mode arriving through the mechanism chosen to
avoid it.

**D8 — Nothing gives the registry a second entry path.** The rule that outranks
everything else, unchanged since stage 1. No `devman register`, no hand-written
entry, no `dagu profile` keyed by project, no fallback scan, no "just this once"
initialisation step. A deliverable that appears to need one stops and says so
here before it is written. Reading devman's own registry is not scanning;
walking the disk to find repositories is (§15.1).

**D9 — The charter changes only in its own commit, and the log entry comes
first.** Rule 4. Stages 1–3 did this six times; stage 2 once let a charter
change share a commit with the code that motivated it and had to record the
slip.

**D10 — The machine is left as it was found, and every touched repository is
named.** No throwaway project left in the registry, no directory named literally
`${DEVMAN_PROJECT_DIR}` or `${DEVMAN_SELF_DIR}` anywhere, `devman doctor` back
to `Nothing to report`, and every change to somebody else's repository committed
there and listed here (rule 7). No `nixos-rebuild switch` — a machine change is
proposed, evaluated, and handed over (rule 8 of the prompt's §8).

### What this deliberately does not promise

- **Not that stage 4 makes the first use of §9.4.** The prompt observes that
  secrets are specified and never used, and asks for a decision. D5 requires the
  decision and the measurement behind it; it does not require the answer to be
  yes. A secret declared because the section exists would be theatre, and §9.4's
  own argument is about what a workflow *needs*.
- **Not a seventeenth-and-a-half criterion.** §14 is the charter's, and D3 says
  its seventeen must still hold. This entry adds no permanent criterion; it
  defines when *this stage* is finished.
- **Not that every deliverable is portable.** §16's promotion rule says a group
  begins when a second repository wants the same file. A deliverable only
  devman wants belongs in devman's own `.devman/workflows/`, and D2 asks it to
  say so rather than to pretend otherwise.

**Charter impact:** **none.** This entry is stage 4's own definition of done,
not an amendment to §14.

---

## S2 — Decision 1: Dagu's own scheduler cannot trigger a devman workflow, and the plane must stop saying it can

**Answer:** a `schedule:` on any workflow the plane projects produces a run that
**writes a directory named literally `${DEVMAN_PROJECT_DIR}` into the daemon's
own tree, does its work in that directory, and then fails on the machine's exit
handler.** Measured, all three at once. §8's table names `schedule → Dagu's own
timer` as one of three trigger arrows; that arrow does not reach this plane.

**Scheduled work is therefore triggered the same way a commit is: by a local
process that runs `devman run` (S9 of stage 3).** The timer belongs to whoever
wants the schedule, exactly as the hook does, and devman supplies no option and
no command for it.

**Tested:** Dagu 2.15.0, on a **throwaway instance** — `DAGU_HOME=/tmp/s4-dagu`,
ports 8090 and 50065, its own `dags_dir` — carrying a byte copy of the installed
plane's `base.yaml` and a port-shifted copy of its `config.yaml`. A throwaway,
because the scheduler had to fire for real and the real plane's DAG directory is
the registry: writing a DAG into it by hand is the second entry path D8 forbids.

**Command** — the whole workflow, and it declares nothing unusual:

```yaml
# /tmp/s4-dagu/dags/s4_sched.yaml
schedule: "* * * * *"
steps:
  - name: probe
    run: |
      echo "cwd=$(pwd)"
      echo "PROJ=[$DEVMAN_PROJECT_DIR]"
```

```bash
mkdir -p /tmp/s4-daemon-cwd && cd /tmp/s4-daemon-cwd
DAGU_HOME=/tmp/s4-dagu dagu start-all          # the daemon's cwd is now visible
```

**Evidence — the daemon fired it twice, one minute apart:**

```
17:04:01 INFO msg="Dispatching planned run" dag=s4_sched scheduleType=Start
17:05:00 INFO msg="Dispatching planned run" dag=s4_sched scheduleType=Start
```

**Evidence — what one firing left behind:**

```
$ ls -a /tmp/s4-daemon-cwd
${DEVMAN_PROJECT_DIR}                          <- the S15 symptom, from a schedule

$ cat '.../${DEVMAN_PROJECT_DIR}/.../probe....out'
cwd=/tmp/s4-daemon-cwd/${DEVMAN_PROJECT_DIR}   <- working_dir did not resolve either
PROJ=[]

$ dagu status s4_sched
├─probe  (0s) [succeeded]
└─onExit (0s) [failed]  error: exit status 1
Result: Failed
$ cat '.../onExit....err'
/tmp/dagu_script-161377995.sh:1: no such file or directory: /.devman/.runs/metadata.jsonl
```

**Three failures in one run, and they are not the same failure.**

1. **`log_dir` did not resolve.** Known — fact 1, A3, E2, E8. The enqueueing
   process is the daemon and the daemon has one environment for the machine.
2. **`working_dir` did not resolve either**, which fact 1 does *not* say. A3's
   table records `params` resolving `working_dir` and leaving `log_dir` literal,
   but that is a run **given** a parameter. Under `schedule:` there is no
   trigger to give one, and E2's table already records the schedule surface as
   carrying **"defaults only"**. The declared default of `DEVMAN_PROJECT_DIR`
   is empty, so *both* fields stay literal and the step runs in a directory
   named after the variable that failed.
3. **`base.yaml`'s exit handler failed and took the run down with it.** With
   both of §7.1's directory names empty, the handler's fallback
   `"${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}/.devman/.runs/metadata.jsonl"`
   expands to `/.devman/.runs/metadata.jsonl` — which is stage 2's S12 failure,
   arriving by a second route.

**The third one is the only reason this is survivable**, and it is worth saying
plainly. Failure 1 and failure 2 are both silent: a `Succeeded` run that did its
work in the wrong directory is §10-of-the-prompt's *successful run that did the
wrong thing*. What makes a scheduled run visible is an accident of the exit
handler — the run reports `Failed`. **Remove `base.yaml`'s handler and a
scheduled workflow would report success forever, in a garbage directory.**

**And the real plane's daemon runs in `$HOME`:**

```
$ pid=$(systemctl --user show dagu -p MainPID --value)
$ readlink /proc/$pid/cwd
/home/andrew
```

So a `schedule:` on a projected workflow does not litter a scratch directory. It
creates `~/${DEVMAN_PROJECT_DIR}/` and fills it, on the developer's own machine.

### The three shapes, and why the second one wins

`STAGE_4_PROMPT.md` §7 names three and asks for a measurement before the choice.

| Shape | Verdict |
|---|---|
| `schedule:` in the workflow, accepting machine-side logs | **rejected.** It does not give machine-side logs. It gives a literally-named directory, an unresolved `working_dir`, and a failed handler. §9.2 would not be "changed", it would be abandoned |
| a local trigger — a fourth arrow in §8 | **taken.** `devman run` already resolves the project, exports the variable, passes the parameter and refuses when it cannot |
| some arrangement that makes the daemon's enqueue resolve per project | **closed.** A3, E2 and E8 each failed to find one; this adds `schedule:` as the fourth surface with the same defect |

**Whose timer, and why devman ships none.** The plane needs the schedule to
reach `devman run`, and it does not need to own the clock. S9 answered the same
question for commits: the hook is the repository's own three lines and devman
supplies no option and no `hook install`. A schedule is selection, like a hook,
and every alternative is worse in the same way:

| Alternative | Why not |
|---|---|
| `services.devman-dagu.schedules = { … project; workflow; }` | the machine module would hold a project name and a workflow name — the one thing §4 says it never learns |
| a `devman schedule` command | §10's list is closed, and this needs no addition to it |
| a `devman.schedules` option in the repo interface | a per-workflow Nix option, which §7.4 refuses, and a second way to express a trigger |

So a schedule is a **systemd user timer the developer writes**, running
`devman run <workflow> --project <name>`. It inherits every refusal in
`src/devman/run.py`, which is the property the Dagu scheduler cannot have: a
timer that fires a workflow whose parameters cannot be filled gets a non-zero
exit and a message naming what is missing, instead of a directory named after a
variable.

The recipe is in `groups/base/README.md`, beside the hook recipe, where a
repository that wants one will look. It is proved end to end in S6.

**Charter impact:** **changes §8.** Its diagram's third line names Dagu's own
timer as a trigger arrow, and it is not one. Applied in its own commit, per
rule 4, before the first scheduled deliverable was written.

**Cleanup:** the throwaway instance stopped, `/tmp/s4-dagu`, `/tmp/s4-proj` and
`/tmp/s4-daemon-cwd` removed with the literal directory inside the last.

> **One thing went wrong doing this, and rule 1 says to report it.** The
> throwaway daemon was stopped with `pkill -f "dagu start-all"`, which is also
> the installed service's command line, so it stopped the **real** Dagu as well.
> The service exited 0, so `Restart=on-failure` did not bring it back; it was
> restarted by hand 20 seconds later, `devman doctor` reported `Nothing to
> report`, and no run was in flight. A throwaway instance is only isolated by
> its `DAGU_HOME` and its ports — **not by its process name** — so stop one by
> pid.

---

## S3 — Three things every stage-4 workflow file has to know, and one of them deletes the run record

**Answer:** measured on the same throwaway instance, against a byte copy of the
installed `base.yaml`, before any deliverable was written.

**1. A workflow that declares one parameter must declare every parameter it will
be given.** Dagu rejects an undeclared one at load time, and `devman run` always
passes the directory variable.

**Command:**

```yaml
params:
  - TASK: "a free-text default"        # and nothing else
```

```bash
DEVMAN_PROJECT_DIR=/tmp/s4-proj dagu enqueue s4_ctx -- DEVMAN_PROJECT_DIR=/tmp/s4-proj
```

**Evidence:**

```
Error: failed to load DAG from s4_ctx: failed to build DAG: field 'params':
  unknown parameter(s): "DEVMAN_PROJECT_DIR"; accepted parameters are: TASK
```

`src/devman/run.py:92` sets `params[dir_var]` unconditionally — an ordinary
workflow declares no parameters at all and still receives `DEVMAN_PROJECT_DIR`,
because `working_dir` and `log_dir` come from `base.yaml` and name it. So the
rule for a stage-4 file is **declare none, or declare `DEVMAN_PROJECT_DIR`
first.** It is loud rather than silent, which is why it is a rule and not a
hazard: the run refuses to load and the message names the parameter.

**2. `${context.run.id}` interpolates in an ordinary step's `run:`, and a
parameter reaches the step's shell environment.** `nix/nixos-module.nix` records
the first only for a *handler's* `run:`. Both hold for a step:

```
ctx_runid=[034Bld6un3RauljHRYx6Dv]      <- ${context.run.id}
ctx_dag=[s4_ctx]                        <- ${context.dag.name}
shell_TASK=[hello world; echo INJECTED] <- "$TASK", the shell's own expansion
cwd=/tmp/s4-proj
```

That is what lets a report name itself after the run that wrote it, so a reader
can find the log tree from the report and the report from the log tree (D6).
**Use the shell form `"$TASK"`, not Dagu's `${TASK}`**, for a value a person
typed: the two produce the same string here, and only the first is quoted by the
shell. The probe passed `hello world; echo INJECTED` and it stayed one value.

**3. A workflow that defines its own `handler_on.exit` silently stops recording
its runs.** This is the sharp one.

**Command** — a DAG whose only unusual line is a handler of its own:

```yaml
handler_on:
  exit:
    name: my-own-exit
    run: echo "MY OWN HANDLER RAN"
steps:
  - name: probe
    run: echo hello
```

**Evidence:**

```
metadata.jsonl lines: before=1  after=1        <- nothing was appended
onExit....out: MY OWN HANDLER RAN              <- the workflow's handler ran instead
Result: Succeeded
```

`base.yaml` is inherited **whole-field**, so a DAG that sets `handler_on`
replaces the machine's and `metadata.jsonl` gains no line. The run succeeds, the
logs land in the right project, `dagu status` is clean, and the one file §9.2
promises survives every retention setting simply has a hole in it. Nothing
reports this — §7.3's whole-file shadowing arriving one level lower down, in the
machine's own defaults rather than in a group's.

**So no stage-4 workflow defines `handler_on`**, and the deliverables below use
an ordinary step to write what they want a person to read. A workflow that
genuinely needs an exit handler has to re-state `base.yaml`'s `printf` as well,
which is an absolute promise nobody can keep across a machine-module change.

**Charter impact:** **none for 1 and 2.** **3 adds a sentence to §9.2**, which
currently says `metadata.jsonl` "is written by Dagu, and no workflow carries a
line of it" — true, and it omits that a workflow can take the writer away.
Applied in its own commit with the §8 change, per rule 4.

---

## S4 — `review`: the first workflow whose output is a document

**Answer:** `groups/base/workflows/review.yaml`. It runs `base:lint` and
`base:test` like `validate` does, and the difference is what it leaves behind:
`.devman/.runs/reports/review-<run id>.md`, holding the head commit, the
uncommitted files, the diffstat against `HEAD`, the last five commits, and one
verdict line per check.

**Home: `base`, and it needed no repository to change at all.** It calls the two
task names `base` already asks for, so the five repositories that take the group
have it the moment they re-pin. That is D2's coverage condition met by one file
rather than by six.

**Command:**

```bash
devman run review
```

**Evidence — the run:**

```
level=INFO msg="Enqueued dag-run" dag=devman-review run-id=034Bln299La34UauzhWjb2
    params="[DEVMAN_PROJECT_DIR=/home/andrew/.paseo/worktrees/1n48r26y/special-dragon]"

$ dagu status devman-review
Succeeded — dag: devman-review (11.0s)
├─changes (0s) [succeeded]
├─lint    (…)  [succeeded]
└─test    (…)  [succeeded]

$ tail -1 .devman/.runs/metadata.jsonl
{"dag":"devman-review","run_id":"034Bln299La34UauzhWjb2","attempt":"d5754e",
 "status":"succeeded","started_at":"2026-08-22T21:11:07Z","log":"…/devman-review/…"}
```

**Evidence — what a person reads afterwards** (`.devman/.runs/reports/review-034Bln299La34UauzhWjb2.md`):

```markdown
# review — devman-review
- run id: `034Bln299La34UauzhWjb2`
- head: `6a2acd7` on `dagu-devenv-automation-eli5`
## uncommitted
```
?? groups/base/workflows/review.yaml
```
## last five commits
```
6a2acd7 CONCEPT §8, §9.2: a schedule is a user timer, and a workflow's own …
```
## verdict
- `base:lint` pass
- `base:test` pass
```

The report records the workflow that produced it, which was uncommitted at the
time. That is the point of the file rather than an accident of when it ran.

**Two things it does on purpose.**

1. **Both check steps carry `continue_on: {failure: true}`.** A `chain` stops at
   the first failed step, so without it a failing lint leaves a report with no
   verdict — the one case a reader most needs one. Measured on the throwaway:
   with `continue_on`, step `a` failed, step `b` ran, and the DAG reported
   **`Partially Succeeded`** with a non-zero exit. That is not `succeeded` in
   `metadata.jsonl`, so a review that found something is still not a success.
   It does **not** say `mark_success`.
2. **It defines no `handler_on`.** One would replace `base.yaml`'s and the run
   would write no `metadata.jsonl` line at all (S3).

**What it costs, stated:** `git` on the service PATH. `servicePath` supplies it
from the machine's profiles, and it worked first time — `head: 6a2acd7` above is
`git rev-parse` running inside a Dagu step. A repository with no `.git` gets
`(no git)` in each section rather than a failed step.

**Charter impact:** **none.** §7.2 says a workflow is Dagu configuration and
§7.4 says invent by adding a file; this is a group file doing both.

---

## S5 — `release` and the policy gate, and the bug that only a real run found

**Answer:** `groups/release/workflows/release.yaml`, in a group of its own. Its
first step is a **gate that fails**, and the two conditions it reads are files
this repository already has. **Policy gating needs no fifth global name.**

**Home: a `release` group, not `base`.** §16's promotion rule decided it — a
group begins when a *second* repository wants the same file — and two do:
`devman` builds a package and `observantic` builds a wheel. `base` reaches five
repositories and three of them have nothing to release, so a `release.yaml`
there is a workflow that fails on a task those three have no reason to define.
Unlike `python-format`, inheriting this one is free: nothing fires it, so §7.4's
"an inherited workflow you never trigger costs nothing" holds, and the reason it
did not hold for reactivity was that a *triggered* workflow rewrites your files
while you edit them (S4 of stage 3).

### Decision 4, answered: `metadata.jsonl` is enough, and §7.1 stays closed at four

The gate reads two things, both content:

| Condition | Source |
|---|---|
| the working tree is clean | `git status --porcelain` |
| the last recorded run of this project's `validate` succeeded | `.devman/.runs/metadata.jsonl` |

Neither is a new name. `.devman/.runs/` is already §7.1's third global name, the
file is already written by `base.yaml`'s exit handler for every run on both
paths, and it already survives every retention setting because nothing in Dagu
owns it (§9.2). **A precondition is a shell command inside a workflow file,
which is content**, and so is a step that exits 1. Nothing here wants a fifth
name, a new command, or a new registry field.

### And a gate FAILS. It does not skip.

`python-format`'s loop break is a step-level `preconditions:`, which records
`Succeeded` with a skipped step — right there, because a self-stopping loop must
not fill the history with things that look like failures (E1, S6 of stage 3).
**A refused release is the opposite case.** A release that is refused and reports
success is `STAGE_4_PROMPT.md` §10's failure exactly: a successful run that did
the wrong thing, which the plane has no check for and is not growing one. So the
gate writes what it found and exits 1.

**Evidence — the refusal, on the real plane:**

```
$ devman run release
$ dagu status devman-release
Failed — ├─gate (0s) [failed]

.devman/.runs/reports/release-034BluLi0xlqcR5XpHIK6a.md:
## gate
- clean tree: **NO** — refusing
```
M devenv.nix
?? groups/release/
```
- last validate: **NONE RECORDED** for `devman-validate` — refusing.
  Run `devman run validate` first

$ tail -1 .devman/.runs/metadata.jsonl
{"dag":"devman-release", … "status":"failed", …}
```

**Evidence — the same workflow after the two conditions were met**, with nothing
edited in between except the tree being committed and `devman run validate` run:

```
$ devman run validate    # Succeeded, 47.0s
$ devman run release
$ dagu status devman-release
Succeeded — gate [succeeded], build [succeeded], record [succeeded]   (3.0s)

.devman/.runs/reports/release-034Blzg9VUzKaEv3Vxx0TL.md:
## gate
- clean tree: yes
- last validate: succeeded — `{"dag":"devman-validate","run_id":"034BlvLPKX1SdIiqkXQJG0", … "status":"succeeded", …}`
## built
- head: `8a2f589d5e13fb5d0b5b04b1538240d8d725a2ff`
- describes as: `8a2f589`
```
lrwxrwxrwx 1 andrew users 56 Aug 22 17:19 devman -> /nix/store/s5ab2fckx3sd4w3jf59nsw2gcp79h4rx-devman-0.3.0
```

$ git status --porcelain
                                   <- the tree stayed clean; the artifact is under .runs/
```

### The bug, and it took a real run to find it

The first version matched `"dag":"[^"]*-validate"`. That looked safe —
`metadata.jsonl` is per working tree, so every line in it is already this
project's. **It matched `devman-stack-validate`**, the cross-repo workflow (§11),
and reported a different workflow's success as this one's:

```
- last validate: succeeded — `{"dag":"devman-stack-validate", … "status":"succeeded", …}`
```

A DAG name is `<project>-<workflow>` and a workflow name may itself contain a
hyphen, so **the name cannot be split from the right in general**. The fix uses
what the run already knows about itself: `${context.dag.name}` is this run's own
`<project>-release`, so stripping its last hyphenated component gives the
project and the wanted name is exact. It holds no project identity and no
absolute path, so criterion 10 stays true.

This is rule 6 earning its place. `dagu validate` passed on the broken version,
`nix flake check` passed, and the gate reported a green light it had no business
reporting. Only running it against a repository that owns a `stack-validate`
showed it.

### What it deliberately does not do

**It builds. It does not publish.** No tag is pushed, no wheel is uploaded, no
GitHub release is cut. Each is irreversible and each wants a credential; see S7
for the decision that follows from that.

**The gate cannot say "on this commit".** `metadata.jsonl` records a run's dag,
id, status and time, and no commit. The report prints the matched line so a
person can judge how old it is. Inventing a freshness rule the data cannot
support would be §15.7 with extra steps.

**Charter impact:** **none.** §7.1's list stays closed at four names, §10's
command list at four, and §7.4's repo interface at three keys.

---

## S6 — `maintain`, and decision 1 proved end to end from a real timer

**Answer:** `groups/base/workflows/maintain.yaml`, and a **systemd user timer**
is what fires it. Both halves ran on the installed service.

**What maintenance is here, and why it is two things.** `hist_retention_days`
prunes Dagu's machine-side history and the per-project **log** tree, and nothing
else (D5, S10). `.devman/.runs/reports/` and `.runs/artifacts/` are created at
registration and owned by nobody — and stage 4 is what starts filling them, since
`review` writes a report on every run and `release` writes one plus an artifact.
§9.2's trap makes it worse: retention is per DAG and runs when that DAG runs, so
a project whose workflows stop running keeps everything it ever wrote.

So `maintain` does the part with no other owner, and then asks `devman doctor` —
the one thing in this design allowed to tell the developer something (§5.2) —
for everything else.

**It prunes reports and never artifacts.** A report is regenerable text; an
artifact is the thing you were about to ship. Deleting one unattended is
§10-of-the-prompt's failure arriving inside the deliverable meant to prevent it.
Artifacts are counted and reported, and a person removes them.

**Command — by hand first:**

```bash
devman run maintain
```

**Evidence:**

```
level=INFO msg="Enqueued dag-run" dag=devman-maintain run-id=034Bm0gPWPmpUlYVo8uPX0
    params="[DEVMAN_PROJECT_DIR=… KEEP_DAYS=7]"
Succeeded — dag: devman-maintain (2.0s)

.devman/.runs/reports/maintain-034Bm0gPWPmpUlYVo8uPX0.md:
## this project
- reports: 4 before, 4 after — 0 pruned
- artifacts: 1 entries, **never pruned here** — remove them by hand
- log trees: 59, pruned by the machine's hist_retention_days when this project's DAGs run
## the plane
```
devman doctor — 6 projects, 22 workflows
ok  plane / queues / validate / queue names / literal dir / shadowing /
    stale entries / run output / cross-repo / watcher
Nothing to report.
```
```

### Decision 1, proved: a systemd user timer, and devman ships none

S2 measured that Dagu's own scheduler cannot trigger anything this plane
projects. This is the other half — the shape §8 now names, run for real.

**Command** — a transient timer, which is the same unit a `.timer` file
installs:

```bash
systemd-run --user --unit=s4-nightly --collect --on-active=5s \
  /run/current-system/sw/bin/devman run maintain --project devman KEEP_DAYS=30
```

**Evidence:**

```
$ journalctl --user -u s4-nightly -o cat
Started [systemd-run] /run/current-system/sw/bin/devman run maintain --project devman KEEP_DAYS=30.
level=INFO msg="Enqueued dag-run" dag=devman-maintain run-id=034Bm1fNVg4gfgFUqF3wGl
    params="[DEVMAN_PROJECT_DIR=/home/andrew/.paseo/worktrees/1n48r26y/special-dragon KEEP_DAYS=30]"

metadata lines: 57 -> 58
{"dag":"devman-maintain","run_id":"034Bm1fNVg4gfgFUqF3wGl", … "status":"succeeded",
 "log":"/home/andrew/.paseo/worktrees/1n48r26y/special-dragon/.devman/.runs/logs/devman-maintain/…"}
```

**Everything S2's measurement said was missing is there.** The timer has no
working directory in any repository, so `--project` names one; `devman run`
resolved its path from the registry, exported `DEVMAN_PROJECT_DIR`, passed it as
a parameter, and passed a second parameter through unchanged. The logs landed
under the project. Compare S2's scheduled run, which worked in
`${DEVMAN_PROJECT_DIR}/` and failed on the exit handler.

**devman ships no timer, no option and no command for this**, and that is S9's
answer to the same question about hooks, applied unchanged. The recipe is in
`groups/base/README.md`.

### Two things this deliverable had to state rather than solve

1. **`KEEP_DAYS` cannot default to the machine's `hist_retention_days`.** That
   is Dagu's own field in `base.yaml`, inherited into a run rather than readable
   from one, and reading the file from a step would put a machine-specific
   absolute path into a group workflow (§9.1, criterion 10). The default is
   stated in the group, matching the module's own default, and the group's
   README says the two numbers live in two places.
2. **Declaring one parameter means declaring `DEVMAN_PROJECT_DIR` too** (S3).
   `maintain` is the first shipped workflow to do it. It is not §11's forbidden
   case: it triggers no other DAG, so it targets its own project and holding the
   name is correct — which is exactly the distinction §11 was amended to make at
   stage 2 (`STAGE_2_LOG.md`, S8).

**Charter impact:** **none beyond S2's**, which changed §8 in its own commit.

---

## S7 — Decisions 2 and 3: an agent workflow fits the contract, and it needed no secret

**Answer:** `.devman/workflows/agent-review.yaml`. It is Dagu steps calling
`devenv tasks run agent:review`, like everything else (§6). It ran on the
installed service and produced a real review of the last commit. **And it
authenticated with no secret at all**, which settles decision 2 by measurement
rather than by preference.

**Home: this repository's own `.devman/workflows/`.** §16's promotion rule — a
group begins when a *second* repository wants the same file — and one ships an
agent CLI: this one, which carries `claude-code` and `codex-cli` in
`devenv.nix`'s packages. Nothing about the file would change on promotion,
because it names a task and never a tool (§7.1).

### Decision 3a — how an argument reaches a run: a real default, overridden by `NAME=VALUE`

`devman run` refuses a declared parameter that would have no value
(`src/devman/run.py:118`), so a free-text parameter with an empty default is
refused at the trigger. **That is correct rather than inconvenient**: an agent
run with an empty prompt is a run that does something nobody asked for. So each
input carries a real default and a person overrides it:

```bash
devman run agent-review
devman run agent-review AGENT_REF=HEAD~3
devman run agent-review AGENT_PROMPT='List every place this breaks a repo with no git.'
```

`DEVMAN_PROJECT_DIR` is declared first, because Dagu rejects a parameter a DAG
did not declare and `devman run` always passes the directory variable (S3).

**The value is passed to the task through the environment, never interpolated
into a command.** S3 measured that a parameter reaches the step's shell
environment, so the step exports `AGENT_REPORT` and the task reads
`"$AGENT_PROMPT"`. Nothing a person typed is expanded by a shell.

### Decision 3b — the queue is `exclusive`, and what actually keeps it away from the watcher

`heavy` says "this costs a lot of machine". `exclusive` says "this must not
overlap with other exclusive work". Both are `max_concurrency: 1` here, and the
second is the stronger claim, so it is the honest one.

**But the queue is not what keeps an agent run out of the watcher's way.** That
is a property of what it writes: one file, under `.devman/.runs/reports/`, which
the watcher ignores and git ignores. An agent workflow that rewrote source files
would fire `format` on every write and would have to be reasoned about the way
`python-format` is. This one has nothing to reason about, and that is a design
choice rather than luck.

### Decision 2 — stage 4 needs no secret, and the machine module grows nothing

**Command:**

```bash
devman run agent-review
```

**Evidence:**

```
level=INFO msg="Enqueued dag-run" dag=devman-agent-review run-id=034Bm7noro2o763kRSY095
    params="[DEVMAN_PROJECT_DIR=… AGENT_REF=HEAD AGENT_PROMPT=Review this change. …]"
Succeeded — dag: devman-agent-review, review [succeeded]

$ tail -1 .devman/.runs/metadata.jsonl
{"dag":"devman-agent-review","run_id":"034Bm7noro2o763kRSY095", … "status":"succeeded", …}
```

**Evidence — what it left behind** (`.devman/.runs/reports/agent-review-034Bm7noro2o763kRSY095.md`, abridged):

```markdown
# agent review — devman-agent-review
- reviewed: `HEAD` = `9ebba37`
## answer
**Correctness:**
1. **S5 regex fix — incomplete explanation.** … If a workflow were "release-v2",
   the dag would be "devman-release-v2", and stripping the last component yields
   "devman-release" — wrong. …
2. **S4 exit status and release gate interaction.** … it doesn't explicitly
   confirm that S5's gate check for `last validate: succeeded` correctly rejects
   a "Partially Succeeded" run …
```

**The second point was worth acting on and is measured in S8.** That is what a
review workflow is for, and it is the first thing in four stages that read this
work and disagreed with it.

**No secret was declared and none was needed.** The step ran under the Dagu user
service, and §4's whole argument for a *user* service is that it already has the
developer's `$HOME`, Nix profile, `~/.cache`, git credentials and SSH agent. The
agent CLI reads its own credential file out of that `$HOME`, so §9.4's mechanism
had nothing to add: there is no environment variable to mask and no missing
value to fail on.

**So §9.4 stays unused after stage 4, deliberately**, and the word `secret`
still appears nowhere in `nix/`, `modules/`, `groups/` or `src/`.
`STAGE_4_PROMPT.md` §10 expects stage 4 to make its first use; the measurement
says otherwise, and rule 1 of that prompt is explicit — write the file first,
and grow the plane only when a measurement shows the file cannot be written
without it. A `secrets:` block declared because §9.4 exists would be a
declaration with nothing behind it.

**What would change the answer, stated exactly**, so the next stage does not
re-derive it:

| If a workflow needs | Then |
|---|---|
| a value that is not in `$HOME` — a PyPI token, a CI token, a hosted key | declare `secrets: [{name, provider: env, key}]` in **that** workflow, never in `base.yaml` (§9.4) |
| the module to supply it | `services.devman-dagu` gains **one** option: an `EnvironmentFile=` path on the Dagu unit, written by agenix or sops-nix |

The option is an `EnvironmentFile` rather than an `environment.X = value`,
because a value in a NixOS module is a value in the Nix store and the store is
world-readable. E3 recommends `provider: env` over `provider: file` for the
workflow's half, because a file path is machine-specific and collides with §9.1;
the module's half is what keeps that portable. **Neither is written today.**

And E8's `dagu profile set-secret` stays refused for a reason that outranks
convenience: it scopes a secret by project identity, which is a second store
keyed the way devman's registry is keyed — D8's forbidden second entry path,
arriving as a feature.

**Charter impact:** **none.** §9.4 is unchanged and still unused. That is now a
recorded decision rather than an omission.

---

## S8 — A partially-succeeded run does not open the gate, and the agent is why it was checked

**Answer:** `base.yaml`'s exit handler records a partially-succeeded run as
`"status":"partially_succeeded"`, and the release gate matches the full string
`"status":"succeeded"`, which that does not contain. **The gate refuses.**

**Why it was measured at all.** S7's agent run raised it: *"it doesn't explicitly
confirm that S5's gate check for `last validate: succeeded` correctly rejects a
'Partially Succeeded' run"*. The two strings share a substring, and if the match
had been on `succeeded` alone the gate would have opened on a failed validate —
silently, which is the exact failure D7 exists to prevent.

**Command** — a throwaway instance carrying a byte copy of the installed
`base.yaml`, and a DAG whose first step fails under `continue_on`:

```bash
DEVMAN_PROJECT_DIR=/tmp/s4-proj dagu start s4_partial -- DEVMAN_PROJECT_DIR=/tmp/s4-proj
```

**Evidence:**

```
Result: Partially Succeeded

$ tail -1 /tmp/s4-proj/.devman/.runs/metadata.jsonl
{"dag":"s4_partial", … "status":"partially_succeeded", …}
```

`review`'s two check steps carry `continue_on: {failure: true}`, so this is not
a hypothetical: a review whose lint failed writes exactly that status into the
same file the release gate reads. The gate's `case` pattern is
`*'"status":"succeeded"'*`, and `"status":"partially_succeeded"` has `_` where
the pattern needs `"`. It does not match.

**Charter impact:** **none.** Recorded in `groups/release/README.md`, because it
is the kind of thing that is correct today and silently wrong after one careless
edit.

---

## S9 — `$SHELL` outranks `default_shell`, so three stages ran under the wrong shell

**Answer:** the machine module sets `default_shell` to bash and says every step
runs "under one known shell, whatever the developer's login shell is". **False.**
Dagu prefers `$SHELL`, the systemd user manager carries the developer's login
`SHELL`, the daemon inherits it, and every step and handler on this machine has
been running under **zsh** since stage 1.

**How it surfaced.** The benchmark campaign's first version read bash's
fork-free `$EPOCHREALTIME`. The run failed:

```
├─campaign (5.0s) [failed]
│ └─stderr: /tmp/dagu_script-138458934.sh:17: EPOCHREALTIME: parameter not set
```

`parameter not set` is zsh's wording; bash says `unbound variable`. Stage 3's S2
onExit failure carried the same fingerprint — `/tmp/dagu_script-….sh:1: no such
file or directory:` — and nobody read it as a shell identity.

**Command — the daemon's own environment, against its own config:**

```bash
$ systemctl --user show-environment | grep ^SHELL
SHELL=/run/current-system/sw/bin/zsh
$ tr '\0' '\n' < /proc/$(systemctl --user show dagu -p MainPID --value)/environ | grep ^SHELL=
SHELL=/run/current-system/sw/bin/zsh
$ grep default_shell ~/.local/share/dagu/config.yaml
default_shell: /nix/store/0641h8qfqaxnwrsw2nzrz6i1wbzyx92l-bash-interactive-5.3p9/bin/bash
```

**Command — the precedence, isolated.** A throwaway `DAGU_HOME` whose
`config.yaml` names the same bash, and one DAG that prints which shell it is in:

```bash
DAGU_HOME=$R SHELL=/run/current-system/sw/bin/zsh dagu start sh
DAGU_HOME=$R env -u SHELL                          dagu start sh
```

**Evidence:**

```
SHELL=zsh   BASH_VERSION=[unset]              ZSH_VERSION=[5.9.1]
SHELL unset BASH_VERSION=[5.3.9(1)-release]   ZSH_VERSION=[unset]
```

**`default_shell` applies only when `$SHELL` is unset.** The module's comment
guessed the opposite — "a user unit usually has no SHELL at all" — and a
systemd user manager started from a login session has one.

**Why three stages missed it.** Every workflow written so far is POSIX-shaped:
`devenv tasks run`, `find`, `sha256sum`, `printf`, `test`. Those behave
identically in both shells, so the plane ran correctly under a shell nobody
chose, and the first file to use a bash-only expansion was the one that found
out. That is the same silence §5.2 warns about for a missed config restart, in
a different field.

**The fix, and it is one line.** `systemd.user.services.dagu.environment.SHELL`
states the shell instead of inheriting it — S2's rule about `DAGU_HOME`, applied
where it was also needed:

```nix
environment = {
  DAGU_HOME = cfg.dagHome;
  SHELL = "${pkgs.bash}/bin/bash";
};
```

**It needs a rebuild and it has not had one.** `nix/nixos-module.nix` is the
only file that moves the machine closure, so this is proposed rather than
applied (rule 8 of the prompt's §8). Proved by evaluation and by the VM test:

```
$ nix build .#checks.x86_64-linux.groups-validate --no-link     # exit 0
$ nix build .#checks.x86_64-linux.dagu-service   --no-link      # exit 0
```

**And every stage-4 file is written to run under either shell**, because the
plane must work on the generation the developer has rather than the one they
will have. The campaign uses `date +%s%N`, which costs one fork per sample and
biases a ~1700 ms figure by about a millisecond — stated in the file rather than
corrected, because the report exists to compare a target against itself.

**Charter impact:** **none.** §7.1's contract says nothing about the shell, and
this is the machine module failing to deliver what it already promised in a
comment.

---

## S10 — The benchmark campaign, and decision 5: `exclusive`, and what it does not buy

**Answer:** `.devman/workflows/bench-entry.yaml`. It measures what §14's
criterion 7 is about and what §15.7 says nothing will ever check for you — how
long it costs to enter a repository's shell — over a named registered project,
with n, mean, median, standard deviation, min, max, and the load average at both
ends.

**Command:**

```bash
devman run bench-entry RUNS=20
```

**Evidence:**

```
level=INFO msg="Enqueued dag-run" dag=devman-bench-entry run-id=034BmEgoi5qH71gKckHXOR
    params="[DEVMAN_PROJECT_DIR=… TARGET=/home/andrew/Documents/Projects/observantic RUNS=20 WARMUP=3]"
Succeeded

$ tail -1 .devman/.runs/metadata.jsonl
{"dag":"devman-bench-entry","run_id":"034BmEgoi5qH71gKckHXOR", … "status":"succeeded", …}
```

```markdown
# bench-entry — devman-bench-entry
- target: `/home/andrew/Documents/Projects/observantic`
- devenv: `devenv 2.1.2 (x86_64-linux)`
- warm-up entries discarded: 3
- load average before: 2.63 3.11 3.58
- load average after:  2.71 3.08 3.55

| n | mean | median | sd | min | max |
|---|---|---|---|---|---|
| 20 | 1735.5 | 1730.5 | 62.6 | 1654 | 1830 |
```

**`TARGET=observantic` became a path and the file holds neither.** The parameter's
default is a project *name*, and `devman run` fills a declared parameter whose
default names a registered project with that project's path (S3 of stage 3). The
resolved path appears in the *report*, which is run output under `.devman/.runs/`
and git-ignored; criterion 10 is about workflow files, and this one has no
absolute path in it.

**The number itself is not the finding, and the file says so.** 1735 ms is an
order of magnitude above stage 3's 255 ms for a throwaway two-input repository —
`observantic` carries more inputs and a uv venv, and the entry is made from a
Dagu step rather than a warm interactive shell. The report exists to compare a
target against itself over time, and it prints the spread first for the reason
stage 3's S15 records: the same repository moved 12 ms between load average 5
and 13, against a plane cost of -0.17 ms. **A single number here would be a
number somebody trusts and should not.**

### Decision 5 — the queue is `exclusive`, `gpu` stays unnamed, and neither buys quiet

`gpu` is declared by the machine with `max_concurrency: 1` and named by no
workflow anywhere. **It stays that way.** Nothing in these six repositories is
GPU work, and naming a queue for a resource you do not use misdeclares it —
§15.4 makes a queue name a one-way door, and Dagu accepts a wrong one silently
with no limit at all. Adding a name is cheap; naming the wrong one is invisible.

`exclusive` is the honest name for a campaign, because a campaign must not
overlap with another campaign or with an agent run. **It does not give the
campaign the machine**, and that is the part worth writing down: Dagu's queues
are independent, so `light`, `normal` and `heavy` runs proceed beside an
exclusive one. The plane can serialize a *class* and cannot quiesce a *host*.
That is why the load average is in the report rather than assumed away, and it
is a limit of the design rather than of this file — §7.1 gives the machine
queues and nothing else, and a "stop everything" primitive would be the machine
learning what a workflow is for.

**Charter impact:** **none.** §7.1's queue list is unchanged and still five.

---

## S11 — What a second repository took, and what it had to change

**Answer:** D2's coverage condition, measured rather than argued. Two
repositories took stage-4 files, and the amount each had to change is the
finding.

| Repository | Took | Edits to that repository |
|---|---|---|
| `siteman` — shell, shellcheck and Hugo, **no Python at all** | `base/review`, `base/maintain` | **one line**: the `rev=` in `devenv.yaml` |
| `observantic` — a Python library | `release` | three lines: the group name, one task, and the `rev=` |

**Command — siteman, which changed nothing but its pin:**

```bash
cd ~/Documents/Projects/siteman
sed -i 's/rev=9610f97…/rev=a77dc309…/' devenv.yaml && devenv update devman && devenv shell -- true
devman run review && devman run maintain
```

**Evidence:**

```
$ ls ~/.local/share/devman/projects/siteman/workflows/
check.yaml  full-test.yaml -> siteman's own override  maintain.yaml  review.yaml  validate.yaml

review:   Succeeded — 2026-08-22T17:35:11-04:00
maintain: Succeeded — 2026-08-22T17:35:11-04:00

.devman/.runs/reports/review-034BmNgds6MsfJCaMZWCfg.md:
# review — siteman-review
- head: `032a387` on `main`
## uncommitted
```
 M devenv.lock
 M devenv.yaml
```
## verdict
- `base:lint` pass          <- fmt-check && lint
- `base:test` pass          <- ci

.devman/.runs/reports/maintain-034BmNh0ma9Wcg2rmnzEZu.md:
- reports: 1 before, 1 after — 0 pruned
- artifacts: 0 entries, **never pruned here** — remove them by hand
- log trees: 6, pruned by the machine's hist_retention_days when this project's DAGs run
```

**That is criterion 6 in its sharpest form.** `review` calls `git`, `base:lint`
and `base:test`, and it ran unedited in a repository with no Python, whose
`base:lint` is `fmt-check && lint` and whose `base:test` is a Hugo CI script.
The group file knows none of that.

**Command — observantic, the second repository that made `release` a group:**

```bash
devman run release          # before the gate could pass
devman run validate
devman run release
```

**Evidence — the refusal, then the build:**

```
Failed — .devman/.runs/reports/release-034BmQxc4NTJKVtk4UeHx1.md
## gate
- clean tree: **NO** — refusing
```
 M devenv.lock
 M devenv.nix
 M devenv.yaml
```
- last validate: **NONE RECORDED** for `observantic-validate` — refusing.

… commit, then `devman run validate` (Succeeded) …

Succeeded — .devman/.runs/reports/release-034BmSyRCwu56fFmVWb2S1.md
## gate
- clean tree: yes
- last validate: succeeded — `{"dag":"observantic-validate", … "status":"succeeded", …}`
## built
- head: `81097eba345658bd66ee6b632da7283abc7b4e91`
- describes as: `v0.3.0-7-g81097eb`
```
-rw-r--r-- 1 andrew users  33013 Aug 22 17:38 observantic-0.3.0-py3-none-any.whl
-rw-r--r-- 1 andrew users 185712 Aug 22 17:38 observantic-0.3.0.tar.gz
```

$ git status --porcelain
                                   <- clean. The wheel is under .devman/.runs/artifacts/
```

**A real wheel and a real sdist, built by an unedited group file, in a
repository that had never released through the plane, with the tree left
clean.** The gate refused first, for two reasons, each named.

### The changes made to other people's repositories (rule 7)

| Repository | Commit | What changed |
|---|---|---|
| `siteman` | `ee8fb37` | `devenv.yaml` + `devenv.lock` — re-pin to `main@a77dc30` |
| `observantic` | `81097eb` | `devenv.yaml` + `devenv.lock` re-pin; `devenv.nix` gains `"release"` in `groups` and one `release:build` task |

Nothing else in either repository was touched. Both were committed in their own
trees; neither is pushed, which matches how stages 2 and 3 left the other five.

**Three repositories were not re-pinned** — `pyjutsu`, `nix-paseo` and
`pydantree`. They keep `main@9610f97` and therefore do not yet see `review` or
`maintain`. That is the plane working as designed: a group file reaches a
repository through that repository's own pin (§3.2), and re-pinning three more
would have proved nothing S11 has not already proved.

---

## S12 — Stage 4 against §14, criterion by criterion

Run against the installed service, six real projects and **27 DAGs** — 19 at the
start of the stage. Compare stage 3's S12.

| # | Criterion | Result |
|---|---|---|
| 1 | one flake, two interfaces, one version | **holds, re-measured.** `nix build .#checks.x86_64-linux.groups-validate` and `.dagu-service` both exit 0 with stage 4's files in the tree, and `nix-meta` re-pinned to `main@e1a5f6a` builds `system.build.toplevel` (exit 0) |
| 2 | a repo adopts in three lines | **holds** — `observantic` took `release` by adding one word to `groups` and one task |
| 3 | a repo may take no groups | **holds** — unchanged. `agent-review` and `bench-entry` are `.devman/workflows/` files, which is the `groups = [ ]` case with groups beside it |
| 4 | a repo may rename or replace every default | **holds** — unchanged. Nothing in stage 4 reserves a workflow name; the release gate reads `<project>-validate` and *refuses loudly* in a repository that renamed it, which is the criterion working rather than failing |
| 5 | shadowing is exact | **holds** — unchanged; `doctor` still reports siteman's `full-test` keeping 7 of 9 executable lines |
| 6 | a workflow is portable Dagu | **holds, and harder than before.** `review` and `maintain` ran unedited in `siteman`, which has **no Python at all** and whose `base:test` is a Hugo CI script; `release` ran unedited in `observantic` and built a real wheel (S11) |
| 7 | devenv stays on the fast path | **holds, not re-measured, and now measurable on demand.** Stage 3's paired figure was -0.17 ms, 95% CI [-6.24, +5.91], against a 10 ms budget. Stage 4 added no evaluation work to the hook — the new group files are read by the same `readDir`/`readFile` the module already ran. `bench-entry` is the harness for the absolute half of it |
| 8 | registration is automatic and idempotent | **holds** — unchanged. Every projection in this stage came from a shell entry |
| 9 | only opted-in repos register | **holds** — unchanged |
| 10 | no workflow contains an absolute path | **holds, re-measured.** `grep -rn '/home/\|/nix/store\|/run/\|/etc/' groups/*/workflows/*.yaml .devman/workflows/*.yaml` → **zero hits**, including the release gate, the campaign and the agent workflow. `bench-entry` names its target as a project *name* and `devman run` resolves it (S10) |
| 11 | identity survives a move | **holds** — unchanged, untested again here |
| 12 | queues are real | **holds, re-measured with a stage-4 workflow.** Two `bench-entry` runs enqueued 0.3 s apart on the `exclusive` queue: the first started 17:42:45 and ran 7.0 s, the second started **17:42:54** — after the first finished |
| 13 | the watchers do not chase each other | **holds, re-measured.** One save of a badly-formatted file with all of stage 4's workflows projected: **2 dispatches, 2 runs**, `format [succeeded]` then `format [skipped]`, then nothing, and the file was formatted. Stage 4's workflows write only under `.devman/.runs/`, which the watcher ignores, so they add no event source |
| 14 | the task graph exists once | **holds** — see below |
| 15 | a rebuild is inconvenient, not catastrophic | **holds** — stage 4 added **no** machine-side state. Reports and artifacts are repo-side under `.devman/.runs/`, which §9.2 already calls run output, and `maintain` is what keeps them bounded |
| 16 | devman adopts itself | **holds, further** — devman now takes `release` as well, and `devman run release` built `packages.devman` through the plane, gated on its own recorded `validate` |
| 17 | there is one way in | **holds, and it survived the stage that pressures it hardest.** A release, an agent run and a campaign each need to know *which project*, and all three get it from `devman run` reading the registry. `grep` over `src/devman/` finds no writer of `projects/<p>/metadata.json` — `doctor --prune` only `unlink`s. **Nothing in stage 4 gives the registry a second entry path** |

### Criterion 14, under the pressure stage 4 puts on it

> *"no default workflow re-states a dependency devenv already declares"*

Three of stage 4's six deliverables want an order, so this is worth stating
rather than asserting.

- **`review`** runs `changes`, then `base:lint`, then `base:test`. That is Dagu
  composing two independent devenv tasks and adding a third step of its own. No
  repository declares `lint` before `test` in devenv; `pyjutsu` and `pydantree`
  declare their *internal* order with `after`, and this workflow does not
  restate it — it calls the one task each exposes.
- **`release`** runs `gate`, then `build`, then `record`. `release:build` is one
  task, whose internals are the repository's; the other two steps are the
  workflow's own and exist in no devenv file.
- **`bench-entry`** has one step. The loop inside it is a measurement, not a
  graph.

**And the policy gate is the case that could have gone wrong.** A gate is a
dependency — "release depends on validate having passed" — and the tempting
expression is a devenv task dependency or a Dagu `depends:` on another DAG.
Neither was used. The gate reads a *record* of a past run rather than causing
one, so the dependency exists in exactly one place and it is not an edge in
anybody's graph. A `release` that ran `validate` itself would have restated
`validate`'s two steps inside a third file.

### The six decisions `STAGE_4_PROMPT.md` §7 asked for, stated

**1. How scheduled work is triggered.** A **systemd user timer running `devman
run`**, and devman ships no timer, no option and no command for it. Dagu's own
`schedule:` cannot trigger anything this plane projects: the daemon enqueues, so
`log_dir` **and** `working_dir` both stay literal, the run works in a directory
named `${DEVMAN_PROJECT_DIR}` in `$HOME`, and `base.yaml`'s exit handler then
fails and takes the run down (S2). Proved the other way in S6, from a real
timer. **Changes §8**, in its own commit.

**2. Whether stage 4 needs a secret.** **No, and the machine module grows
nothing.** Every deliverable runs under the developer's own identity in the
developer's own checkout, and §4's whole argument for a *user* service is that it
already has that `$HOME`, its git credentials and its SSH agent. The agent
workflow — the one deliverable that would want a hosted key — authenticated with
none (S7). §9.4 stays specified and unused, and S7 names exactly what would
change the answer and what the module would gain if it did: **one**
`EnvironmentFile=` option, never an `environment.X = value`, because a value in
a NixOS module is a value in the world-readable store.

**3. Whether agent workflows fit the contract.** **Yes.** Steps calling `devenv
tasks run agent:review`, like everything else. Input arrives as a declared
parameter with a **real default**, overridden by `NAME=VALUE`, because `devman
run` refuses a parameter that would have no value — and that refusal is correct:
an agent run with an empty prompt is a run nobody asked for. The queue is
`exclusive`, named for the stronger claim. What keeps it away from the watcher is
not the queue but what it writes: one file under `.devman/.runs/` (S7).

**4. Whether policy gating fits the four global names.** **It does, and §7.1
stays closed at four.** The gate reads `git status --porcelain` and this
project's own `.devman/.runs/metadata.jsonl`, which the machine already writes
for every run on both paths and which survives retention. No fifth name, no new
command, no new registry field. **A gate fails rather than skips** — the opposite
of `python-format`'s precondition, for the reason S1's D7 states in advance
(S5, S8).

**5. Which queue a benchmark campaign names.** **`exclusive`**, and `gpu` stays
named by nothing. Nothing here is GPU work, and §15.4 makes a wrong queue name
invisible rather than merely inconvenient. **And `exclusive` does not buy quiet**:
Dagu's queues are independent, so light, normal and heavy runs proceed beside an
exclusive one. The plane serializes a class and cannot quiesce a host, which is
why the report carries the load average at both ends (S10).

**6. Where each deliverable lives.**

| Deliverable | Home | Why |
|---|---|---|
| `review` | `groups/base/` | needs no task beyond the two `base` already asks for, so it reaches five repositories with **no edit to any of them** |
| `maintain` | `groups/base/` | same — and every repository has a `.devman/.runs/` that nothing else prunes |
| `release` | `groups/release/` | §16's promotion rule: a second repository wanted the same file. `base` reaches three repositories that have nothing to release |
| policy gating | inside `release.yaml` | it is a step, which is content. It was never a file of its own |
| `agent-review` | `.devman/workflows/` | one repository ships an agent CLI. §16's promotion rule, applied honestly |
| `bench-entry` | `.devman/workflows/` | a campaign measuring a *named other* project belongs to no project, and §11 says such a workflow belongs to devman |

### Stage 4 against its own definition of done (S1)

| | Condition | Result |
|---|---|---|
| D1 | six deliverables, each run | **met.** review S4/S11, release S5/S11, maintain S6/S11, campaign S10, agent S7, gating S5/S8 — each with its `metadata.jsonl` line and its log or report quoted |
| D2 | coverage, not count | **met.** `review` and `maintain` reach five repositories with no repository edit; `siteman` ran both unedited after a one-line pin bump; `observantic` ran `release` unedited (S11) |
| D3 | every criterion still holds, measured | **met.** The table above; 1, 10, 12, 13 and 17 re-run by command |
| D4 | grow only under a measurement | **met.** §7.1 still four names, §10 still four commands, §7.4 still three keys, the queue list still five. One module line changed, and S9 records the failed run that forced it |
| D5 | six decisions, none deferred | **met**, above |
| D6 | every run leaves something readable | **met.** Every deliverable writes `.devman/.runs/reports/<workflow>-<run id>.md` and every run appends to `metadata.jsonl` |
| D7 | a gate fails, it does not skip | **met.** Two refused releases recorded `"status":"failed"`, in two repositories (S5, S11), and S8 checks the near-miss |
| D8 | no second entry path | **met.** Criterion 17 above |
| D9 | charter changes in their own commit | **met.** One charter commit, `6a2acd7`, after S2 and S3 were written |
| D10 | machine left as found | **met**, and detailed below |

### D10 — what was left behind, and what was not

```
$ devman doctor
devman doctor — 6 projects, 27 workflows
ok  plane / queues / validate / queue names / literal dir / shadowing /
    stale entries / run output / cross-repo / watcher
Nothing to report.                                                   exit 0
```

- **6 projects**, the same six. No throwaway was ever registered — every probe
  ran against a throwaway `DAGU_HOME` on its own ports, so `doctor --prune` was
  never needed.
- **No directory named literally `${DEVMAN_PROJECT_DIR}` or `${DEVMAN_SELF_DIR}`
  anywhere.** The one S2 created was inside `/tmp/s4-daemon-cwd`, removed with
  the rest of the throwaway state.
- **Every touched repository is committed and named** in S11, plus `nix-meta` at
  `62e3b5a`. `nix-meta`'s unrelated `machines/server.nix` change was left alone.
- **No `nixos-rebuild switch` was run.** The machine change is proposed, proved
  by evaluation and by the VM test, and handed over.

### What stage 4 did not do

| Item | Why |
|---|---|
| activate the machine change | `nixos-rebuild switch` is the user's. Until they run it, every step still runs under zsh — which is why every stage-4 file is written for either shell (S9) |
| re-pin `pyjutsu`, `nix-paseo`, `pydantree` | they keep `main@9610f97` and do not yet see `review` or `maintain`. Re-pinning three more would prove nothing S11 has not |
| publish anything | `release` builds and does not push a tag or upload a wheel. Each is irreversible and each wants a credential, and S7's decision follows from that rather than the other way round |
| re-measure criterion 7 | nothing new forks in `enterShell` and no evaluation work was added. `bench-entry` now exists for whoever needs the absolute figure |
| a `doctor` check for a workflow that defines `handler_on` | S3 measured that such a workflow silently stops recording its runs. It is written into §9.2 and into every stage-4 file's comments; whether `doctor` should check it mechanically is a stage-5 question, and no shipped workflow does it |
| push the adopted repositories | seven commits now wait in seven working trees, as stages 2 and 3 left them |

---

## S13 — S9's fix was in the wrong place: a step's shell follows the process that ENQUEUES

**Answer:** the user activated the generation, and the step still ran zsh.
**S9's diagnosis was half right and its fix was wrong.** Dagu does prefer
`$SHELL` over `default_shell` — that part held — but it reads `$SHELL` from
**whichever process enqueues the run**, exactly as it reads `log_dir` (A3, A7).
Setting `SHELL` on the Dagu unit therefore governs only the runs the *daemon*
enqueues, which under §8 is none.

**The fix is in `devman run`**, beside the two directory names it already
clears, and it is one line.

**Tested:** the rebuilt generation. `systemctl --user show dagu -p Environment`
carries `SHELL=…bash-interactive-5.3p9/bin/bash`, and so does
`/proc/<mainpid>/environ`. The daemon restarted at 17:52:03.

**Command — a throwaway workflow in this repository's own
`.devman/workflows/`**, projected by an ordinary shell entry, run through the
plane, and deleted afterwards:

```yaml
steps:
  - name: which-shell
    run: |
      echo "BASH_VERSION=[${BASH_VERSION:-unset}]"
      echo "ZSH_VERSION=[${ZSH_VERSION:-unset}]"
      echo "EPOCHREALTIME=[${EPOCHREALTIME:-unset}]"
```

**Evidence — three triggers, differing only in the caller's `SHELL`:**

```
$ devman run _s4-shellprobe                       # this shell: SHELL=…/zsh
BASH_VERSION=[unset]      ZSH_VERSION=[5.9.1]     EPOCHREALTIME=[unset]

$ SHELL=…/bash devman run _s4-shellprobe
BASH_VERSION=[5.3.9(1)-release]   ZSH_VERSION=[unset]   EPOCHREALTIME=[1787435639.892207]

$ env -u SHELL devman run _s4-shellprobe          # falls back to default_shell
BASH_VERSION=[5.3.9(1)-release]   ZSH_VERSION=[unset]   EPOCHREALTIME=[1787435648.900362]
```

The daemon's own `SHELL` was bash in all three. **It decided nothing.** The
trigger's did.

**So the shell joins `log_dir` on the short list of things baked at enqueue
time**, and it has the same consequence: the machine cannot state it once
unless the trigger stops passing its own. Three callers, three shells — a
developer's login shell at a prompt, the systemd user manager's copy of it under
the watcher, and the daemon's only under a `schedule:` the plane does not use.
A group file would otherwise have to be correct in every shell any user of that
machine might log in with.

### The fix, and why it clears rather than sets

```python
env.pop(PROJECT_DIR, None)
env.pop(SELF_DIR, None)
env.pop("SHELL", None)          # <- S13
```

Clearing lets `config.yaml`'s `default_shell` govern, which is §7.1's own shape:
the machine states it once, in the file it writes. Setting it here would compile
a store path into the CLI and create a second value to keep in step — the drift
§3.1 exists to prevent.

It covers every path into the plane, because they all go through `devman run`:
a person at a prompt, a VCS hook (S9 of stage 3), a systemd timer (S6), and the
watcher, whose dispatcher re-invokes `devman run` as a subprocess and hands it
its own environment.

**Evidence — the built CLI, from an unmodified zsh shell, against the running
service:**

```
$ echo $SHELL
/run/current-system/sw/bin/zsh
$ /nix/store/p9hda2r2jzkv71j40hx7wb9n3ampg8q3-devman-0.3.0/bin/devman … run _s4-shellprobe
BASH_VERSION=[5.3.9(1)-release]   ZSH_VERSION=[unset]   EPOCHREALTIME=[1787435778.032981]
"status":"succeeded"
```

### And the unit's `SHELL` line is reverted

It was present for one commit, `a77dc30`, and this measurement says it does
nothing for any run the plane makes. **D4 says grow only under a measurement**,
and the measurement now points elsewhere, so the line goes rather than staying
as harmless insurance. `default_shell` in `config.yaml` is the one statement of
the shell, and the comment above it now records what it competes with.

**What this cost, stated plainly:** one rebuild that changed nothing
operationally, and a `nix-meta` commit that has to be re-pinned again. The
mistake was diagnosing from a symptom that two hypotheses explained — the daemon
inherits the login shell, and the *trigger* does — and testing only the first.
S9's own throwaway probe used `dagu start`, where the triggering process and the
executing process are the same one, so it could not tell them apart. **A probe
that cannot separate two hypotheses is not a measurement of either.**

**Charter impact:** **none**, and that is worth stating: §7.1's four names are
unchanged, because the shell is not a name the plane shares — it is a property
of the machine that the trigger must stop overriding. It belongs beside
`--dagu-home`, which S2 of stage 3 forced for the same reason: **a trigger
states its target and never inherits it.**

---

## S14 — `maintain` reported itself as a fault, because `doctor` confused waiting with wedged

**Answer:** four `maintain` runs fired together filled the `light` queue for
about a second. `devman doctor`'s queue check reported that as a finding, exited
1, and **failed three of the four runs.** The plane was healthy throughout. The
defect is `doctor`'s, not `maintain`'s, and it had been there since stage 3 —
invisible until stage 4 gave the machine enough work to have two runs in flight
at once.

**Command** — the ordinary thing to do after re-pinning four repositories:

```bash
for p in siteman pyjutsu nix-paseo pydantree; do devman run maintain --project $p; done
```

**Evidence:**

```
siteman   maintain: Failed
pyjutsu   maintain: Failed
nix-paseo maintain: Failed
pydantree maintain: Succeeded        <- ran last, by which time the queue had drained

$ dagu status siteman-maintain
├─prune  (0s) [succeeded]
├─doctor (2.0s) [failed]  error: exit status 1
Result: Failed
```

**Evidence — what `doctor` said, out of the report the failed run still wrote:**

```
!!  queues        light: 1 waiting, limit 4
                    held by nix-paseo-maintain 034Bp1wcVPXjfNExhc5Wua since 19:23:08
                    held by pyjutsu-maintain   034Bp1wG5SOs46lNVfWnKn since 19:23:08
                    held by siteman-maintain   034Bp1vtlNRyXDLN5m40HL since 19:23:08
…
4 findings.
```

**One waiting item against a limit of four, with three runs in flight.** That is
a queue doing its job. Run from a prompt thirty seconds later the same `doctor`
exited 0.

### Why the check was wrong, read rather than assumed

`check_queues` flagged `!!` for **any** queue with a queued item:

```python
waiting = [q for q in queues if q.get("queuedCount")]
if not waiting:
    ... ok ...
rep.add("queues", "!!", lines)      # <- everything else
```

§15.3 asks this check to diagnose a **wedged** plane, and §10 records why it
reads rather than computes: *"a wedged queue, and why — every waiting item
carries a reason and a message"*. Measured on 2.15.0, a merely-queued item
carries **no conditions at all**:

```
$ curl -s http://127.0.0.1:8080/api/v1/queues/light/items
{"items":[{"dagRunId":"034Bp4Doo5QpvV8bFwpyll","name":"siteman-maintain",
           "queuedAt":"2026-08-22T19:24:38-04:00","startedAt":"",
           "status":5,"statusLabel":"queued","triggerType":"manual"}]}
```

So there was no reason to print, and the check printed a verdict instead.

### The fix: whether anything is draining the queue

| State | Verdict |
|---|---|
| queued **and** something running | **`ok`**, with the counts — a developer wondering why a run has not started can still see it |
| queued **and nothing running** | **`!!`** — nothing will drain it |
| an item carrying a failed condition | **`!!`**, with Dagu's own reason and message |

The third branch stays because it is the path E5 measured; it is Dagu reporting
rather than devman guessing.

**Evidence — all three branches, against the built CLI:**

```
draining (2 waiting, 3 running)    -> ok
        light: 2 waiting, 3 running, limit 4 — draining
wedged (2 waiting, 0 running)      -> !!
        light: 2 waiting, 0 running, limit 4 — NOTHING RUNNING — wedged
failed condition on an item        -> !!
        light: 1 waiting, 2 running, limit 4 — draining
          a-check: Blocked — another run holds it
```

**Evidence — and against the live plane under real contention**, five `maintain`
runs fired at once:

```
ok  queues         light: 4 waiting, 2 running, limit 4 — draining
                     held by nix-paseo-maintain 034Bp5f21QejxVs74NMI1e
                     held by pydantree-maintain 034Bp5ezCA3CYluJaatNoH
```

### What this says about stage 4 rather than about one function

**`maintain` is the first workflow that observes the plane from inside it**, and
that is what exposed this. Every earlier workflow ran commands in a repository;
this one asks the plane how it is, while being a thing the plane is doing. Two
consequences worth carrying forward:

1. **A diagnostic that a workflow's exit code depends on must distinguish "busy"
   from "broken".** `maintain` propagating `doctor`'s exit code is right — a
   maintenance run that finds a real problem should be red — and it is only
   useful if `doctor` is right about what a problem is.
2. **The failure was self-inflicted and self-reported**, which is the shape D6
   asked for: three runs failed, and each still wrote the report that explains
   why, because the `prune` step had already written it before the `doctor` step
   ran.

**Charter impact:** **none.** §15.3 already says `doctor` must diagnose a wedged
plane, and this is `doctor` finally distinguishing one.

---

## S15 — Stage 4 closed out: the timer installed, five repositories on one rev, and what is left running

**Answer:** the last of stage 4's work, done after the user's second rebuild.
Nothing here is a new measurement; it is what the stage left on the machine.

**1. The nightly timer exists.** §8's third arrow was proved by a transient unit
in S6; this is the permanent one, hand-written in the developer's own
`~/.config/systemd/user/`, exactly as §8 says a schedule should be:

```
$ systemctl --user list-timers devman-maintain.timer
NEXT                        LEFT      UNIT                   ACTIVATES
Sun 2026-08-23 00:05:37 EDT 4h 37min  devman-maintain.timer  devman-maintain.service
```

Five `ExecStart` lines, one per project that takes `base`. `observantic` is
absent because it takes `python` and `release` only, so it has no `maintain`.

**Evidence — fired once by hand, before the timer's first real firing:**

```
$ systemctl --user start devman-maintain.service
$ systemctl --user show devman-maintain.service -p Result -p ExecMainStatus --value
success 0

$ journalctl --user -u devman-maintain.service -o cat
Enqueued dag-run dag=siteman-maintain   params="[DEVMAN_PROJECT_DIR=…/siteman KEEP_DAYS=7]"
Enqueued dag-run dag=pyjutsu-maintain   params="[DEVMAN_PROJECT_DIR=…/pyjutsu KEEP_DAYS=7]"
Enqueued dag-run dag=nix-paseo-maintain params="[DEVMAN_PROJECT_DIR=…/nix-paseo KEEP_DAYS=7]"
Enqueued dag-run dag=pydantree-maintain params="[DEVMAN_PROJECT_DIR=…/pydantree KEEP_DAYS=7]"
Finished devman maintenance — prune old reports, then devman doctor.
Consumed 1.330s CPU time over 1.303s wall clock time, 29.8M memory peak.
```

**Five of those runs then failed, and the timer was not why.** They failed on
S14's queue check, because the `doctor` fix is committed and **not yet
installed** — the CLI ships from `nixosModules.default`, so it needs a rebuild:

```
$ grep -c 'NOTHING RUNNING' $(…installed devman…)/site-packages/devman/doctor.py
0
```

That is worth recording rather than tidying away: **a `src/devman/` change moves
the machine closure**, and stage 4 needed three rebuilds — one for the groups,
one for a shell fix that turned out to be in the wrong place (S13), and one for
the `doctor` fix. Only the first was avoidable.

**2. All five adopted repositories now sit on one rev**, and `review` and
`maintain` reach four of them:

| Project | Groups | What it gained |
|---|---|---|
| `siteman` | `base` | review, maintain |
| `pyjutsu` | `base` | review, maintain |
| `nix-paseo` | `base` | review, maintain |
| `pydantree` | `base`, `python` | review, maintain |
| `observantic` | `python`, `release` | release — **and neither review nor maintain** |

**observantic's gap is real and it is left open on purpose.** `review` and
`maintain` live in `base`, which observantic does not take, so the repository
that most looks like a publishable library has no review workflow. Three answers
exist — copies in `python`, observantic taking `base` too, or leaving it — and
§16's promotion rule decides between them. **No measurement forces one**, and
stage 4's rule 1 says not to grow the plane without one. It is written into
`STAGE_5_PROMPT.md` §7 as a decision rather than a defect.

**3. The registry ended at 6 projects and 34 DAGs**, from 19 at the start of the
stage. `devman doctor` reports eleven checks, all `ok`, exit 0.

**Charter impact:** **none.**
