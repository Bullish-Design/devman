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
