# STAGE 3 — what was measured while making the plane react

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules and
`STAGE_2_LOG.md` holds what stage 2 found while turning the plane on. This holds
stage 3, in the same shape: the answer, the versions, the exact command, the
evidence, and the charter impact.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, installed, running as `systemd --user` unit `dagu` |
| devenv | 2.1.2 |
| watchexec | 2.5.1 (nixpkgs) |
| Registry | `~/.local/share/devman/` — 6 projects, 18 DAGs |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5` |

---

## S1 — `dagu dry` creates the literally-named directory, so nothing may call it

**Answer:** `dagu dry` documents itself as a simulation "without producing any
side effects", and it **creates `log_dir`** — which, for a workflow whose
directory variable is unset, is a directory named literally
`${DEVMAN_SELF_DIR}`. That is S15's symptom, produced by the one command in the
CLI that looks safe to call. **No devman command may run `dagu dry`.**

**Why it was run at all.** `devman run` has to know a workflow's declared
parameters (§10, and the cross-repo convention `.devman/workflows/README.md`
writes out by hand). `dagu dry` prints them, which would have let devman read
Dagu's own view of a file rather than read the file — the same "read rather than
compute" rule E5 sets for `doctor`.

**Command**, run from `/tmp` so that whatever it created would be visible:

```bash
cd /tmp && dagu dry ~/.local/share/devman/dags/devman-stack-validate.yaml
```

**Evidence — it does print the parameters:**

```
msg="Dry-run completed" dag=devman-stack-validate
    params="[DEVMAN_SELF_DIR= OBSERVANTIC_DIR= SITEMAN_DIR=]"
Result: Succeeded
```

**Evidence — and it writes:**

```
$ find '/tmp/${DEVMAN_SELF_DIR}'
/tmp/${DEVMAN_SELF_DIR}
/tmp/${DEVMAN_SELF_DIR}/.devman
/tmp/${DEVMAN_SELF_DIR}/.devman/.runs
/tmp/${DEVMAN_SELF_DIR}/.devman/.runs/logs/devman-stack-validate/dag-run_.../dag-run_....log
```

A simulation that resolves no step still resolves `log_dir` and creates it. The
directory was removed by hand.

**What it decides.** `devman run` reads the workflow's own top-level `params:`
block instead. That is not §7.2's forbidden parse — §7.2 forbids the plane
*understanding* a workflow, and §10 already has `doctor` reading workflow text
for §11's `action: dag.run` check. Reading the parameters a file declares is
reading what the trigger is required to fill in.

**Charter impact:** **none.** §7.2 already records that an unresolved variable
is not an error in Dagu; this is a sixth documentation/behaviour gap in the same
family as E2's `$(…)` and backticks, and it names one more command `doctor`
should never call.

---

## S2 — An unset `DAGU_HOME` gives a trigger its own empty, example-seeded Dagu

**Answer:** a bare `dagu` in an ordinary shell does not talk to the plane. It
creates `~/.config/dagu/`, writes a `base.yaml` of its own, **seeds the five
example DAGs**, and lists nothing. So a trigger that inherits the ambient
`DAGU_HOME` enqueues into whichever Dagu the caller happened to have — and when
the caller has none, into a Dagu that has never heard of the registry.
**`devman run` must state `--dagu-home` rather than inherit it.**

**Command:** an ordinary non-login shell, with no `DAGU_HOME` exported.

**Evidence:**

```
$ echo "DAGU_HOME=$DAGU_HOME"
DAGU_HOME=
$ command -v dagu
/run/current-system/sw/bin/dagu          <- the plane's own client (installClient)
$ dagu ls
level=WARN msg="No auth.mode configured — defaulting to 'builtin'."
level=INFO msg="Creating example DAGs for first-time users" dir=/home/andrew/.config/dagu/dags
level=INFO msg="Rebuilding DAG definition index" dir=/home/andrew/.config/dagu/dags
NAME
                                          <- no DAGs. The registry is elsewhere.
$ ls -a ~/.config/dagu ~/.config/dagu/dags
.base-config-created  base.yaml  dags
.dag.index  .examples-created  example-01-basic-sequential.yaml  … (five)
```

The stray home was removed by hand afterwards.

**Two things follow, and the second is the sharper one.**

1. **`skip_examples` is per instance, not per machine** (S9 of stage 1). The
   plane sets it in its own `config.yaml`; a Dagu started against a different
   `DAGU_HOME` never reads that file, so the flag cannot protect it.
2. **The trigger's target must be stated by the plane, not by the caller's
   environment.** `STAGE_3_PROMPT.md` §4 tells a reader to `export DAGU_HOME`
   before talking to the plane, which is right for a person at a prompt and
   wrong as a dependency for a program. The watcher runs from a systemd unit,
   a VCS hook runs from git, and a developer runs `devman run` from a devenv
   shell — three environments, and only one of them is the plane's.

**And this repository sets the variable to something else.** `devenv.nix` still
carries `env.DAGU_HOME = "${config.devenv.state}/dagu"` from the investigation
period, when the plane was started by hand from `processes.dagu`. That process
is gone (§13 stage-1 cleanup 2) and the variable outlived it, so inside this
repository's shell `dagu ls` reports the devenv state directory's DAGU_HOME
rather than the plane's.

**Charter impact:** **none.** §8 already says a trigger is a local process
running `dagu enqueue`; this says which Dagu it must enqueue into and how it
says so.

---

## S3 — `devman run`, against the real plane, including a hostile environment

**Answer:** the CLI triggers both shapes of workflow correctly on the running
service, and it removes the two things `.devman/workflows/README.md` asked a
person to remember. **A stray `DEVMAN_PROJECT_DIR` in the caller's shell no
longer reaches the children.**

**Command — the ordinary case**, in a real adopted repository:

```bash
cd ~/Documents/Projects/observantic && devman run check
```

**Evidence:**

```
level=INFO msg="Enqueued dag-run" dag=observantic-check run-id=034BhwjMUai8gXhJLUc8xV
    params="[DEVMAN_PROJECT_DIR=/home/andrew/Documents/Projects/observantic]"

$ tail -1 .devman/.runs/metadata.jsonl
{"dag":"observantic-check", … "status":"succeeded",
 "log":"/home/andrew/Documents/Projects/observantic/.devman/.runs/logs/…"}
$ git status --porcelain
                                    <- the tree stays clean
```

**Command — the cross-repo case, with the failure deliberately armed.** §11's
whole rule is that a parent must not hold `DEVMAN_PROJECT_DIR`, because a parent
exports its parameters into every child's environment and that environment
outranks the child's own `with.params`. The hand-written trigger says
`env -u DEVMAN_PROJECT_DIR` for exactly this reason. So the test exports it:

```bash
DEVMAN_PROJECT_DIR=/tmp devman run stack-validate
```

**Evidence:**

```
$ dagu status devman-stack-validate
├─observantic-check (…) [succeeded]  subdag: … [DEVMAN_PROJECT_DIR="…/observantic"]
├─siteman-check     (…) [succeeded]  subdag: … [DEVMAN_PROJECT_DIR="…/siteman"]
└─onExit (0s) [succeeded]
Result: Succeeded

$ ls -d /tmp/.devman
No such file or directory              <- nothing landed in the hostile directory
```

`devman run` clears **both** of §7.1's directory names from the child
environment and then sets the one the workflow needs. The `env -u` is now a
property of the trigger rather than a line somebody must not forget.

### Decision 2, answered: `devman run` does resolve a cross-repo workflow's parameters

`STAGE_3_PROMPT.md` §7 asks whether it should, and warns that the answer makes
parameter names a contract. **It does resolve them, and it does not make the
names a contract, because it reads the value rather than the name.**

> **A declared parameter whose default names a registered project is filled with
> that project's path.**

```yaml
params:
  - DEVMAN_SELF_DIR: ""
  - OBSERVANTIC_DIR: observantic       # <- the default IS the project name
  - SITEMAN_DIR: siteman
```

The alternative — reserving the shape `<PROJECT>_DIR` — would add a fifth entry
to §7.1's closed list, and a name shape is harder to check than a name. Reading
the value costs nothing: a project name is an identity, not a path, so
criterion 10 still holds and the file still contains no absolute path.

**And the refusals, which are the point.** Every one of these is a run that
would have written somewhere wrong:

```
$ devman run stack-validate                 # before the defaults were changed
devman: refusing to enqueue 'stack-validate' in 'devman'
devman:   these declared parameters have no value: OBSERVANTIC_DIR, SITEMAN_DIR
devman:   give each one a registered project name as its default, or pass NAME=VALUE
```

The others are: a directory variable that would be empty or is not a directory
(S15's literally-named directory, refused at the source), a workflow that fails
to load (§10 check 1, arriving at the trigger instead of at `doctor`), a
cross-repo parent that holds `DEVMAN_PROJECT_DIR` for itself, and a cross-repo
parent that declares no `DEVMAN_SELF_DIR`.

**How it knows the difference between the two shapes.** The workflow's own
top-level `params:` block: a file declaring `DEVMAN_SELF_DIR` is self-directed,
and everything else targets a project. That is a read of what the trigger is
required to fill in, not §7.2's forbidden parse — and §10 already has `doctor`
reading workflow text for §11's `action: dag.run` check.

**Charter impact:** **none.** §10 says `devman run` triggers a workflow in the
current project, and §11 leaves the mechanism to the trigger.

---

## S4 — Decision 1: the mapping is a group's own triggers file, and reactivity is its own group

**Answer:** `groups/<group>/triggers.toml` holds `<glob> = <workflow>`. It is
resolved at evaluation time by `modules/devenv.nix`, whole-file and in the order
the repository lists its groups, and recorded in the registry entry as **schema
3**. The watcher reads the entry and never a group file.

**Why not the three obvious homes**, each closed by something already measured:

| Home | Why not |
|---|---|
| the workflow file | Dagu rejects an unknown top-level key outright, and §7.2 says a workflow is Dagu configuration from the first line to the last (A5) |
| a Nix option in the repo interface | §7.4 says there is no per-workflow Nix option, and a machine-side option would make the machine learn a project fact (§4) |
| a file the watcher reads at run time | the watcher would then need §7.3's resolution too, and the plane would hold two implementations of it |

**Evidence — the entry, derived rather than written down:**

```json
{
  "schema": 3,
  "project": "s3-fmt",
  "groups": ["python-format"],
  "workflows": {"format":{"group":"python-format","shadows":[],"source":"/nix/store/…"}},
  "triggers": {"group":"python-format","map":{"**/*.py":"format"}}
}
```

### The part that is a design decision rather than a mechanism

**Reactivity is its own group.** §7.4 argues that there is no per-workflow Nix
option because *"an inherited workflow you never trigger costs nothing"*. That
argument does not survive contact with §8: **a triggered workflow costs
plenty** — it rewrites the developer's files while they are editing them. So
reactivity cannot ride along inside `python`, where taking the group for its
`check` would silently also mean "and format my files when I save".

`python-format` therefore holds one workflow and one `triggers.toml`, and taking
it is the whole opt-in. §7.4's own remedy — "to be rid of one, do not take its
group" — is free here, because there is nothing else in the group to lose.

**The limit, stated rather than fixed.** A repository cannot override a group's
globs: `.devman/` may hold only `workflows/` and `.runs/` (§15.2), and widening
that whitelist to add a fourth name is a charter change no measurement has
forced. A repository that wants different globs takes a different group, or
none. That is §7.3's promotion rule doing its ordinary work — a group begins
when a second repository wants the same file.

**The file was `triggers.nix` when this entry was written**, and S7 changed the
format. What it holds and where it sits did not change.

**Charter impact:** **none.** §8 already says the watcher is plane machinery and
the mapping is group content. This is what "group content" turned out to mean,
and §7.2's "a group is a directory, and devman reads only `workflows/*.yaml` in
it" needs no change: `triggers.toml` is read by the devenv module at evaluation
time, not by the plane at run time.

---

## S5 — watchexec searches for a project origin, and one watcher over many repos makes that expensive

**Answer:** left to itself, watchexec resolves a "project origin" from the paths
it watches and walks it. One watcher over several repositories therefore
resolves their **common ancestor** — `/tmp` here, `~/Documents/Projects` on this
machine, and **`$HOME` for a service systemd starts there**. Measured: the same
command line **spun a core at 99.4% for over a minute**, and sat at **0.3%**
with `--project-origin` given.

**Tested:** watchexec 2.5.1, two watched repositories under `/tmp`.

**Command — the two variants, identical but for one flag:**

```bash
cd /tmp && watchexec --emit-events-to=json-stdio --postpone --on-busy-update=queue \
  --watch /tmp/s3-ctl --watch /tmp/s3-fmt -- /tmp/probe.sh

cd /tmp && watchexec --project-origin=/home/andrew/.local/share/devman \
  --emit-events-to=json-stdio --postpone --on-busy-update=queue \
  --watch /tmp/s3-ctl --watch /tmp/s3-fmt -- /tmp/probe.sh
```

**Evidence:**

```
=== cwd=/tmp origin=(searched)                       cpu=99.4
=== cwd=/tmp origin=/home/andrew/.local/share/devman cpu=0.3
```

**It fired nothing while it was doing that**, which is the failure that matters:
the watcher looked healthy — the process was up, `devman watch` had printed what
it was watching, the state file was written — and a save produced **zero** runs.
`STAGE_3_PROMPT.md` §8 warns that zero is worse than two, because it looks like
success.

**The fix, and what it costs.** The watcher passes
`--project-origin=<registry root>`: devman's own directory, small, and where the
watcher's state already lives. The cost is that **no repository's `.gitignore`
is read**, because origin discovery is what finds them. So the watcher carries
an explicit ignore list — `.devman/.runs/`, `.git`, `.devenv`, `.direnv`,
`.venv`, `__pycache__`, `node_modules` — and a group's globs must be specific
enough to live without a repository's own ignore rules.

**Two smaller things measured on the way**, both worth the line they cost:

1. **The mode is `json-stdio`, not `json-stdin`.** The wrong spelling is
   rejected at start-up with the list of valid modes, which is the loud kind of
   failure.
2. **`--postpone` is required.** Without it watchexec runs the command once at
   start-up with an empty batch, so every mapped workflow would fire whenever
   the service restarts, with nobody having saved anything.

**Charter impact:** **none.** §8 names watchexec and D7 chose it; this is what
it takes to run one of them over many repositories.

---

## S6 — Criterion 13, measured four ways, and it does not hold as written

**Answer:** the watchers do not chase each other — **the sequence always
terminates, and your own edit always fires.** But criterion 13's wording, *"one
save, exactly one run"*, holds only when the workflow's write changes nothing.
When the formatter actually rewrites the file, one save produces **two runs, one
of which does the work and one of which skips**. That is not a defect in the
watcher; it is E1's recorded cost, arriving where E1 said it would.

**Tested:** watchexec 2.5.1, Dagu 2.15.0, devenv 2.1.2, on the running service.
Two throwaway projects, each importing `path:/tmp/s3-devman-src`:

| Project | Group | Workflow | Writes its watched files? |
|---|---|---|---|
| `s3-fmt` | `python-format` | `format` — `ruff format .` | **yes** |
| `s3-ctl` | `s3-control` (throwaway) | `look` — `ruff check --statistics` | no |

Runs are counted from `.devman/.runs/metadata.jsonl`, one line per run, and
every dispatch is recorded by the watcher in `<registry>/watch/fired.jsonl` with
millisecond timestamps. `dagu status --run-id` gives each run's step status,
which is what separates a run that worked from a run that skipped.

### Test 1 — a save the formatter does not change: **exactly one run**

```
SAVE (already-formatted content)      14:51:00.401
fired                                 14:51:00.860   s3-fmt/format
run  034BiLtIqSQhTv7XFy7jLQ           18:51:01Z      succeeded
```

One save, one dispatch, one run. Criterion 13 as written.

### Test 2 — a save the formatter rewrites: **two runs, one of them a skip**

```
SAVE (badly formatted)                14:51:43.951
fired                                 14:51:44.349   <- 0.40s after the save
run  034BiMziIo8bUgvhqPRdSx           18:51:45Z      format [succeeded]  "1 file reformatted"
fired                                 14:51:45.854   <- 1.9s after the save: the FORMATTER's write
run  034BiN23dw8G4rvUWVhn6b           18:51:48Z      format [skipped]
                                                     <- and then nothing. It stops.
```

The millisecond stamps are what make this readable: the second dispatch is 1.5
seconds after the first and half a second after the first run started, so it is
the formatter's own write and not a duplicate of the save.

**The second run's step is `skipped` and the run is `Succeeded`.** That is E1's
step-level precondition doing exactly what it was chosen for — and the reason
the group file uses the step-level form rather than the DAG-level one, which
would have recorded `Aborted` and filled the history with runs that look like
failures.

### Test 3 — the test a suppression window passes and must not: **your own edit fires**

`STAGE_3_PROMPT.md` §8 step 4: edit again immediately after the formatter's
write. A debounce window swallows this; a content hash does not.

```
SAVE 1 (badly formatted)              14:52:41.210
fired                                 14:52:41.622
run  034BiORlNK60XjUEc4r5UT           18:52:43Z   format [succeeded]
fired                                 14:52:43.947   <- the formatter's write
SAVE 2, 3.0s after save 1             14:52:44.228   <- while run 2 was still queued
fired                                 14:52:44.679
run  034BiOVOG8jUqGoC1JVQn6           18:52:46Z   format [succeeded]   <- WORKED AGAIN
run  034BiOWXK8lZfY4ee5U6IR           18:52:47Z   format [skipped]
fired                                 14:52:46.918
run  034BiOa5Er1opQr0ZmPFJ7           18:52:49Z   format [skipped]
```

```
$ cat sample.py
def f(x):
    return x + 1


def immediately(q):
    return q                          <- the second edit was formatted
```

Two saves, four runs, **two of which did work**, and it stopped. The run at
18:52:46 is the one that matters: it was enqueued by the *formatter's* event,
and by the time its precondition was evaluated the developer had edited the file
again, so the hash differed and it ran. A window would have suppressed that run
and left the second edit unformatted until something else happened.

### Test 4 — the control: a workflow that does not write its watched files

```
SAVE in s3-ctl                        14:53:42.447
fired                                 14:53:42.869   s3-ctl/look
run  034BiQ02xazTZde7HSehnf           18:53:43Z      succeeded
                                                     <- and nothing else, ever
```

**Exactly one run.** This is the control the prompt asks for, and it is what
separates "loop-breaking works" from "nothing ever runs twice": the same watcher,
the same glob, one run instead of two, because there is no second write.

The run did write inside the watched repository — `ruff check` left a
`.ruff_cache/` — and that produced no event, because the group's glob is
`**/*.py`. **The glob is the first filter and the ignore list is the second.**

### What this does to criterion 13

Criterion 13 was written before E1 measured where the skip happens. E1 records
the cost in one line — *"The check moved from the trigger to the run. §8.1 skips
before anything is enqueued. Dagu skips after. A skipped run still consumes a
queue slot and writes a history record"* — and criterion 13's wording was never
reconciled with it.

Counting runs, the failure criterion 13 exists to catch is **unbounded**: run,
write, run, write, forever. What was measured is **bounded and self-stopping**,
with the terminating run doing no work. So the criterion needs to say what it
means rather than be quietly failed or quietly reinterpreted:

> **13 — the watchers do not chase each other.** A file-writing workflow plus a
> watcher on those files: one save produces exactly one run **that does work**,
> and the sequence stops within one further run, which skips. A workflow that
> does not write its watched files produces exactly one run. Then edit again
> immediately: it must run again, which is what a content hash gives and a
> suppression window does not.

**The alternative was considered and rejected.** devman could compare the hash
*before* enqueueing and get "exactly one run" literally. That is §8.1 — the
section E1 deleted — rebuilt inside the plane, and §8 is explicit that the plane
owns neither loop-breaking mechanism. It would also move a per-workflow decision
into machinery that must not know what a workflow does.

**Charter impact:** **changes §14, criterion 13.** Applied in its own commit,
per rule 4.

---

## S7 — A group file inside a `path:` input is invisible to devenv's evaluation cache

**Answer:** editing a group file — a workflow or a triggers mapping — changes
**nothing** in a repository that takes the group through a `path:` flake input.
Every shell entry keeps projecting the previous content. `devenv update` does not
fix it. Deleting `.devenv/nix-eval-cache.db*` does. **The construct that reads
the file makes no difference**, which is what separates this from stage 1's S8.

**Tested:** devenv 2.1.2, a throwaway repository whose `devenv.yaml` declares
`devman: {url: "path:/tmp/s3-devman-src"}`.

**How it was found, and the first diagnosis was wrong.** The mapping was a
`triggers.nix` read with `import`. An edit to it did not reach the registry, and
`import` was the obvious suspect: stage 1's S8 measured that devenv's cache does
not track a group file whose *path* is interpolated, and that `builtins.readFile`
is a read it does track. Converting the mapping to TOML read with
`fromTOML (readFile …)` changed nothing, which is what forced the control.

**Command — the control that settles it.** Edit a *workflow* file, which
`modules/devenv.nix` has read with `builtins.readFile` since stage 1:

```bash
printf '\n# cache-probe-s7\n' >> /tmp/s3-devman-src/groups/s3-control/workflows/look.yaml
cd /tmp/s3-ctl && devenv shell -- true
grep -c 'cache-probe-s7' ~/.local/share/devman/projects/s3-ctl/workflows/look.yaml
```

**Evidence:**

```
after the edit, plain re-entry          0     <- stale
after `devenv update devman`            0     <- still stale
after rm .devenv/nix-eval-cache.db*     1     <- the eval cache was the blocker
```

The same three lines hold for the triggers mapping, in both formats.

**What it means, stated as two cases rather than one rule:**

| The group file reaches the repository through | An edit to it is |
|---|---|
| a local `imports: - ./modules` (devman itself, criterion 16) | **tracked** — S8 measured it, with `readFile` |
| a `path:` flake input | **not tracked**, whatever construct reads it |
| a `git+https` rev | not applicable — a changed group file is a changed rev, and the whole input re-resolves |

Stage 1 and stage 2 never met this, and the reason is worth writing down: this
repository imports `./modules` directly, so every group-file edit was in the
tracked case. **A throwaway repository built to test a group is in the untracked
one**, which is precisely where somebody iterating on a group will be.

**What to do about it: nothing in the module, one line in a test procedure.**
The cache is devenv's, the `path:` input is a testing convenience (B4 already
says it is not a pin), and a repository that pins a rev cannot meet the problem.
Iterating on a group against a throwaway means `rm -f .devenv/nix-eval-cache.db*`
between edits.

### And the mapping is TOML anyway, for reasons that survive the correction

The format changed while chasing this, and it stays changed:

1. **`fromTOML (readFile …)` is the construct S8 measured as tracked** in the
   case that matters — a repository importing groups locally. `import` is
   untested there, and a mapping that decides what happens when a developer
   saves must not go stale silently.
2. **A mapping is data.** A `.nix` file would let a group evaluate arbitrary Nix
   in every repository that takes it. A workflow is inert YAML for the same
   reason (§7.2), and TOML carries the comments a `.json` file could not.

### And the tracked half, confirmed rather than assumed

The same edit, in the repository that imports `./modules` directly:

```
$ printf '"**/*.pyi" = "format"\n' >> groups/python-format/triggers.toml
$ devenv shell -- true                       # no cache clearing
after edit:   {'**/*.py': 'format', '**/*.pyi': 'format'}
$ git checkout groups/python-format/triggers.toml && devenv shell -- true
after revert: {'**/*.py': 'format'}
```

Both directions, one shell entry each. That is stage 1's S8 cache-probe in its
stage-3 form, and it is the case the format choice was made for.

**Charter impact:** **none.** §9.3 says the registry is derived and the
repository is canonical; this is a second case, beside stage 1's S8, where the
derivation silently stops re-deriving — and the first one where the cause is the
input rather than the read.

---

## S8 — The runaway is real, and the workflow's own loop break cannot stop it

**Answer:** with the watcher's ignore list removed, **one save produced 107
dispatches and 60 runs in 45 seconds**, and it was still accelerating when the
watcher was killed. The loop was not the workflow rewriting its watched files —
it was **the plane's own log directory**, which Dagu creates inside the project
for every run (§9.2). With the ignore list in place, the same save produced two
dispatches and stopped.

**This is the failure §8's content-hash precondition cannot address**, and that
distinction is the entry:

> A workflow's `preconditions:` break the loop the workflow causes. **The
> watcher's ignore list breaks the loop the plane causes.** Neither substitutes
> for the other, because a run writes to `.devman/.runs/` whether its steps do
> any work or not.

**Tested:** watchexec 2.5.1, Dagu 2.15.0, in the throwaway `s3-ctl`, whose
trigger mapping was widened to `"**/*" = "look"` for the purpose. `look` runs
`ruff check` and writes none of the files it watches.

**Command — with the ignore list**, which is what the watcher ships:

```bash
devman watch          # --ignore **/.devman/.runs/** among six others
printf 'def g( y ):\n    return   y+3\n' > /tmp/s3-ctl/sample.py
```

**Evidence:**

```
dispatches: 2
runs: 2
$ cat ~/.local/share/devman/watch/fired.jsonl
… "path": "/tmp/s3-ctl/sample.py"
… "path": "/tmp/s3-ctl/.ruff_cache/0.16.2/.tmpMndMQT"     <- the TOOL's cache, not the plane's
```

**Command — the same save, with `**/.devman/.runs/**` removed** and everything
else identical:

```bash
watchexec --emit-events-to=json-stdio --postpone --on-busy-update=queue \
  --project-origin=$REG --ignore '**/.git/**' --ignore '**/.devenv/**' \
  --ignore '**/.direnv/**' --watch /tmp/s3-ctl -- devman … watch --dispatch
```

**Evidence:**

```
dispatches: 107
runs:        60          (in 45 seconds, then killed)

15:02:09.409  /tmp/s3-ctl/sample.py                                   <- the save
15:02:09.821  …/.devman/.runs/logs/s3-ctl-look/dag-run_…034BicqRYq…   <- run 1's log dir
15:02:10.182  …/.devman/.runs/logs/s3-ctl-look/dag-run_…034Bicr75I…   <- run 2's
15:02:10.539  …/.devman/.runs/logs/s3-ctl-look/dag-run_…034Bicreud…
…                                                                      every 0.37s
```

Each run created its log directory; each directory was an event; each event was
a run. The `light` queue's limit of 4 slowed the acceleration and did not stop
it — 19 runs were still queued when the watcher was killed, and they drained
without producing more, which is what confirms the watcher was the engine.

**No workflow could have stopped this.** A precondition hashing the `.py` files
would have found them unchanged and skipped the step — and a skipped run still
creates its log directory, so the loop would have run at the same rate doing
nothing at all. §8 assigns loop-breaking to the workflow, and that is right for
the loop §8 describes; this one is the plane's and belongs to the watcher.

**The second finding, from the ignore-list run: a tool's cache is not in the
list.** `ruff check` wrote `.ruff_cache/`, inside the watched repository, and
fired a second dispatch. It stopped there only because the second run found its
cache warm and wrote nothing new — luck, not design. **A group's glob is the
first filter and the more important one:** `**/*.py` never sees `.ruff_cache/`,
and the over-broad `**/*` used here is exactly the mistake the ignore list
cannot fully cover.

**Charter impact:** **changes §8.** Applied in its own commit, per rule 4.

---

## S9 — VCS hooks are the repository's own three lines, and devman supplies no option

**Answer:** §13's "VCS hooks" needs nothing in devman beyond `devman run`. A
repository installs the hook through devenv's own `git-hooks` module, and the
hook is one command. **It works from a plain shell with neither `devenv` nor
`DAGU_HOME` in the environment**, which is the property S2 built into the CLI.

**Command — the repository's whole side of it:**

```nix
git-hooks.hooks.devman-validate = {
  enable = true;
  name = "devman validate";
  entry = "devman run validate";
  stages = [ "post-commit" ];
  pass_filenames = false;
  always_run = true;
};
```

**Evidence — a commit made from an ordinary shell:**

```
$ git commit -m "a change that should trigger validate"
Using config file: /tmp/s3-hook/.pre-commit-config.yaml
devman validate..........................................................Passed
[master e1d4698] a change that should trigger validate

$ cat .devman/.runs/metadata.jsonl
{"dag":"s3-hook-validate", … "status":"succeeded","started_at":"2026-08-22T19:08:03Z"}
```

**Why this is the answer rather than a devman feature.** §7.4 gives Nix
selection and identity, and YAML the workflows; a hook is selection. Every
alternative was worse:

| Alternative | Why not |
|---|---|
| registration installs `.git/hooks/post-commit` | the hook must fork nothing (C1) and it would overwrite a hook the developer wrote, silently, in their own repository |
| a `devman.hooks` Nix option | a per-workflow option, which §7.4 refuses, and a second way to express a trigger |
| a `devman hook install` command | §10's list is closed at three, and this needs no fourth |

### Three costs, all of them the repository's to accept

1. **It costs a second devenv input.** devenv 2.1.2 refuses to evaluate
   `git-hooks` until the repository runs
   `devenv inputs add git-hooks github:cachix/git-hooks.nix --follows nixpkgs`,
   and §3.2 prices an input at about 20 ms on every shell entry, forever.
2. **It writes `.pre-commit-config.yaml` into the working tree**, generated and
   marked `# DO NOT MODIFY`. That is git-hooks.nix's file, not devman's.
3. **An enqueued run reads the tree later, not the tree that was committed.**
   The hook returns immediately — that is the point, and it is why the trigger
   is `enqueue` — so the workflow starts a second or two afterwards, against
   whatever the working tree holds by then. For `validate` after a commit that
   is almost always the same thing. It is not a gate, and a repository that
   wants a gate wants a `pre-commit` hook that runs the task directly.

**This repository does not adopt one**, and that is a decision rather than an
omission: devman's own `validate` is `ruff check` and `nix flake check`, the
second of which takes minutes, and the input cost buys nothing here. The recipe
is in `groups/base/README.md` where a repository that wants it will look.

**Charter impact:** **none.** §8's table already gives the hook layer one job —
"detect that something happened" — and `devman run` is the layer below it.

---

## S10 — Retention, observed on the real service: 110 log trees to 1, and the record survives

**Answer:** retention prunes **both halves** — Dagu's machine-side history and
the per-project log tree under `log_dir` — and **`metadata.jsonl` survives it**,
exactly as D5 predicted and §9.2 states. Stage 2 left this "set but never
observed"; it is now observed, on the installed service, with a control.

**Command.** `hist_retention_days: 7` cannot be waited out, so the throwaway's
workflow overrides it per DAG with the other predicate — D5 established that both
end in the same `removeDAGRun`:

```yaml
hist_retention_runs: 1        # in the throwaway group's look.yaml
```

Then one run, through the ordinary trigger:

```bash
cd /tmp/s3-ctl && devman run look
```

**Evidence:**

```
                          before      after
per-project log trees        110          1
machine-side run records     110          1
metadata.jsonl lines         110        111     <- the record of what ran survives
```

**The control**, in the other throwaway, which overrides nothing and therefore
keeps `base.yaml`'s seven days:

```
s3-fmt   log trees 9   machine-side run records 9   metadata.jsonl 9
```

Nothing there is seven days old, so nothing was pruned. That is what makes the
comparison a measurement rather than a coincidence.

**§9.2's trap, seen rather than argued.** Those 110 runs accumulated over an
afternoon under `hist_retention_days: 7` and none of them aged out, because
**retention is per DAG and runs when that DAG runs**. A project whose workflows
stop running keeps its `.runs/` forever, and no setting changes that.

### So `doctor` check 6 asks about the newest run, not the oldest

The first implementation looked for log trees older than the window, which is
the wrong question: a busy project has old runs and prunes them on every run. The
right question is whether anything still runs here.

```
!!  run output   s3-fmt: 9 run log trees, newest 52 days old, retention 7 —
                 its workflows have stopped running, so nothing here will age out
```

Measured by backdating a throwaway's log tree, which is the only way to see this
check fire without waiting a week. `devman doctor` exits 1 when it has findings.

**Charter impact:** **none.** §9.2, §16 and D5 all say this; it had never been
run on the installed plane.

---

## S11 — The four decisions `STAGE_3_PROMPT.md` §7 asked for, stated

**1. Where the glob-to-workflow mapping lives.** `groups/<group>/triggers.toml`,
resolved at evaluation time and recorded in the registry entry — **S4**, with the
format corrected in **S7**. Reactivity is its own group, because §7.4's argument
for having no per-workflow option does not survive a workflow that triggers
itself.

**2. Whether `devman run` resolves a cross-repo workflow's parameters.** **Yes,
by reading the parameter's default value rather than its name** — S3. A declared
parameter whose default names a registered project is filled with that project's
path, so parameter *names* stay the workflow's own business and §7.1's closed
list of four stays closed.

**3. What `doctor` does about a stale entry: it reports by default and prunes
behind `--prune`.**

§10 allows either. The reason for the flag is not caution about the registry —
§9.3 makes pruning safe, and a wrongly pruned entry restores itself on the next
shell entry. It is that **`doctor` is the command a developer runs to find out
what is wrong**, often when something is already broken, and a diagnostic that
deletes state by default is one a person hesitates to run. §9.1 also records the
one case where "the path is gone" is a lie rather than a fact: an unmounted disk.
Reporting costs a sentence; pruning without being asked costs that project's
projection until somebody notices.

**Evidence — both halves, on the three throwaways this stage created:**

```
$ devman doctor
!!  stale entries  s3-ctl -> /tmp/s3-ctl (gone) — its workflows still project and
                   would pass, vacuously, in a directory Dagu creates
                   … s3-fmt, s3-hook …
                   run `devman doctor --prune` to remove them

$ devman doctor --prune
!!  stale entries  s3-ctl -> /tmp/s3-ctl (gone) — pruned, 3 links removed
                   s3-fmt -> /tmp/s3-fmt (gone) — pruned, 3 links removed
                   s3-hook -> /tmp/s3-hook (gone) — pruned, 7 links removed

DAGs before: 24        DAGs after: 19
```

That is §10's "`doctor` must also unproject the pruned project's workflows",
and it is how stage 3's throwaways were removed — by the command that exists for
it, rather than by hand as stage 2 had to.

**4. Which name the CLI ships under, and where it comes from.** **`devman`, from
`nixosModules.default` only.**

The name is free: stage 1 removed `devman 0.2.0` from the profile and the user
activated the removal (`STAGE_1_LOG.md`, S11). `command -v devman` found nothing
before this stage.

It ships from the machine interface alone, and the reason is §3.1's second rule —
**what the two interfaces share must be text**, with `nix/dagu.nix` the single
measured exception. A Python program is not text. Two further arguments point the
same way:

- Shipping it from the devenv module as well would put **two `devman` binaries
  on one PATH**, resolved by profile order. That is precisely the hazard §3.3
  records against `devman 0.2.0`, recreated with two versions of the new one.
- **A devenv shell inherits the machine profile's PATH**, so one machine-side
  install already reaches every repository shell on that machine. The second
  copy would buy nothing and cost a build under each repository's nixpkgs.

`packages.default` is the CLI, which is what §3.1's table says it should be;
`packages.dagu` stays beside it.

The wrapper carries `--registry` and `--dagu-home` as **flags**, not as
`DEVMAN_*` variables: Dagu passes every `DEVMAN_*` in the enqueueing process's
environment through to the run, so a fifth name would arrive in every workflow's
environment (§7.1, A2).

---

## S12 — Stage 3 against §14, criterion by criterion

Run against the installed service, six real projects, 19 DAGs, and three
throwaways built and pruned. Compare stage 2's S17.

| # | Criterion | Result |
|---|---|---|
| 1 | one flake, two interfaces, one version | **holds** — `nix flake check` passes, machine re-pinned to `main@60813cf`; the CLI and the watcher come from the same rev as the groups |
| 2 | a repo adopts in three lines | **holds** — devman's own adoption of `python-format` is one word in `groups` and one task |
| 3 | a repo may take no groups | **holds** — unchanged from stage 2 |
| 4 | a repo may rename or replace every default | **holds** — unchanged; `devman show <name>` now prints the file to start an override, and stderr carries the provenance so the redirect stays byte-exact |
| 5 | shadowing is exact | **holds** — and `doctor` now reports the drift: siteman's `full-test` keeps 7 of 9 executable lines, which reproduces S14's measurement from the registry rather than from a script |
| 6 | a workflow is portable Dagu | **holds** — unchanged |
| 7 | devenv stays on the fast path | **holds, not re-measured.** Registration gained one `builtins.fromTOML` at evaluation time and one more field in the entry; nothing new forks in the hook. The paired delta was +7.08 ms at its 95% upper bound with schema 2 (S3 of stage 2) |
| 8 | registration is idempotent | **holds** — unchanged |
| 9 | only opted-in repos register | **holds** — unchanged |
| 10 | no workflow contains an absolute path | **holds** — including the cross-repo workflow, whose parameter defaults are project *names* (S3) |
| 11 | identity survives a move | **holds** — unchanged, untested again here |
| 12 | queues are real | **holds** — and S8's runaway is the proof at scale: 60 runs went through the `light` queue's limit of 4, and 19 were still waiting when the watcher was killed |
| 13 | the watchers do not chase each other | **holds, against the corrected wording** — one save, one run that works, one run that skips, then nothing; the control produces exactly one run; the immediate second edit fires (S6). The criterion's wording changed, in its own commit |
| 14 | the task graph exists once | **holds** — see below |
| 15 | a rebuild is inconvenient, not catastrophic | **holds** — `<registry>/watch/` is the only new machine-side state, and deleting it costs the answer to "what did it last fire", which the next event restores |
| 16 | devman adopts itself | **holds, further** — devman now takes the reactive group as well, and `devman run format` ran `ruff format` in this repository through the plane |
| 17 | there is one way in | **holds** — and it survived a new pressure: the CLI adds `run`, `show`, `doctor` and `watch`, and **not one of them writes a registry entry.** `doctor --prune` only removes. Nothing in stage 3 gives the registry a second entry path |

### Criterion 14, and the question the prompt asked about it

> *"check the watcher's glob-to-workflow mapping does not become a second graph"*

It does not, and the reason is structural rather than careful. A `triggers.toml`
line maps **one glob to one workflow name**. It cannot express an order, a
dependency, or a condition: there is nowhere to put one. What runs after
`format` is `format`'s own business, stated in `format.yaml` as Dagu steps, and
what those steps depend on is devenv's, stated as task dependencies.

The mapping says *when*, the workflow says *what*, and devenv says *how*. That
is §6's split with one more layer on top, and the new layer holds no edges.

### What stage 3 did not do

| Item | Why |
|---|---|
| activate the machine change | `nixos-rebuild switch` is the user's. `nix-meta` is committed at `2b30d1f` and checked by evaluation: the unit's ExecStart is `devman watch`, and the toplevel builds |
| re-measure criterion 7 | nothing new forks in `enterShell`; the added work is one `fromTOML` at evaluation time. Worth a sweep when something else forces one |
| a second reactive group | `python-format` is the only one, and §16's promotion rule applies — a group begins when a *second* repository wants the same file |
| repository-level trigger overrides | §15.2's whitelist allows `.devman/workflows/` and `.devman/.runs/` only, and widening it is a charter change no measurement has forced (S4) |
| pushing the five adopted repositories | still five commits waiting in five working trees, as stage 2 left them |
| `hist_retention_days` observed at its own predicate | seven days cannot be waited out; S10 used `hist_retention_runs` on the real service, which D5 established shares the same code path |

---

## S13 — The plane acting on its own, on the real machine

**Answer:** the user activated the generation, and **the watcher reproduced S6's
measurement in a real repository, from a systemd service, with nobody asking**.
One save of a badly-formatted file: one run that formatted it, one run that
skipped, and then nothing. The working tree was clean afterwards and `doctor`
had nothing to report.

**Tested:** the installed generation, `devman 0.3.0` on `PATH`,
`systemd --user` units `dagu` and `devman-watch` both active. The repository is
devman itself, which takes `[ base python-format ]` (criterion 16).

**Command:** a save. That is the whole of it, and it is the point.

```bash
printf 'def probe(  x ):\n  return   x\n' > src/devman/_watch_probe.py
```

**Evidence — what the plane did, unasked:**

```
saved                    15:26:47.420
fired                    15:26:47.868   devman/format  <- src/devman/_watch_probe.py
run 034BjEKysR98…        19:26:49Z      format [succeeded]
fired                    15:26:51.438   <- the formatter's own write
run 034BjEQb4pKc…        19:26:52Z      format [skipped]
                                        <- and it stopped

$ cat src/devman/_watch_probe.py
def probe(x):
    return x
```

**Evidence — the unit, as `switch-to-configuration` left it:**

```
● devman-watch.service - devman watcher — one watchexec for every registered repository
     Active: active (running) since Sat 2026-08-22 15:25:11 EDT
   Main PID: 1078382 (.devman-wrapped)
     CGroup: ├─ …/devman --registry …/devman --dagu-home …/dagu watch
             └─ …/watchexec --emit-events-to=json-stdio --postpone
                --on-busy-update=queue --project-origin=…/devman
                --ignore "**/.devman/.runs/**" … --watch …/special-dragon
                -- …/devman … watch --dispatch
```

Both flags reached the wrapper, the origin is stated (S5), and the watch set is
the one registered project that declares triggers — not every registered
project, which is what "reactivity is opt-in by group" means on a running
machine (S4).

**And the tree it acted in:**

```
$ rm src/devman/_watch_probe.py     # one more run, which found nothing to do
$ git status --porcelain
                                    <- nothing. No stray file, no literal directory.
$ devman doctor
Nothing to report.
```

### What it costs while nothing happens

```
idle CPU over 120 s: 67 ms   (0.056% of one core)
resident memory:     19 MB
```

Both processes together. Worth recording because §15.3 accepts one shared
instance as an availability risk and §8 adds a second always-on process to the
same argument; the cost of the second one is not the reason to worry about it.

**Charter impact:** **none.** This is §8 working as written, on hardware, and
criteria 13 and 16 measured against the shipped configuration rather than a
throwaway.

---

## S14 — §12.4 is closed by decision, not by measurement

**Answer:** whole-file shadowing stays as §7.3 defines it. **A repository that
must change a default writes a whole workflow file of its own.** There will be
no field merging, no smaller group files split for the purpose, and no further
measurement of the override rate.

**Who decided and why.** The owner, on 2026-08-22, after S14 of stage 2 reported
one override in eighteen workflows. The reasoning is that the cost §12.4 worries
about — a file copied to change one line — is a cost the repository pays once, in
its own tree, and every alternative moves complexity into the plane, which is the
thing the plane exists to avoid.

**What that closes.** §12.4 asked whether the coarseness is liveable and named
two remedies if it is not. Neither will be applied:

| Remedy §12.4 named | Status |
|---|---|
| smaller group files, split into what varies and what does not | **not taken.** One override in eighteen is not the "common" case the remedy was reserved for |
| a merge algorithm | **not taken**, and §7.3 already refused it. The one real override was a *deletion*, which merge semantics express badly |

**What does not change.** §15.6 stands: an overriding file stops tracking its
group, and `devman doctor` reports how far each has diverged. That report is now
a command rather than a measurement exercise — it reproduces stage 2's figures
from the registry — so the fact stays visible without anybody running a study.

**Charter impact:** **changes §12.4 and §16.** Applied in its own commit, per
rule 4.

---

## S15 — Criterion 7, re-measured against schema 3 and the triggers file

**Answer:** the cost is still not distinguishable from zero. **300 paired
entries: -0.17 ms, 95% CI [-6.24, +5.91].** Criterion 7 allows 10 ms, and it
holds.

**Tested:** devenv 2.1.2, warm cache, 10 warm-up entries per variant discarded.
Two throwaway repositories under `/tmp`, byte-identical apart from
`devman.enable`, **both importing the module**, so the delta is registration
alone rather than the cost of the input. Both take `[ "base" "python"
"python-format" ]`, so the enabled one performs the evaluation work stage 3
added: one `builtins.fromTOML (builtins.readFile …)` for `python-format`'s
`triggers.toml`, and a `triggers` field in the entry. The enabled repository
registered at schema 3 with `{"group": "python-format", "map": {"**/*.py":
"format"}}` before the sweep started, so the work was in the measurement.

**Command:** the variants interleave one entry at a time, because C2 found load
drift larger than the effect and a sequential sweep once reported the enabled
repository as the faster one.

```bash
N=300 python3 /tmp/s3b-paired.py \
  "off_enable-false|/tmp/s3b-time/off" "on_schema3-triggers|/tmp/s3b-time/on"
```

**Evidence — two sweeps, the second is the one the answer quotes:**

```
 16:16:57 load average: 4.99, 3.70, 3.01
variant                      mean      sd   median    min    max   runs=150
off_enable-false            267.5    87.8    283.6    137    605
on_schema3-triggers         266.1    82.0    287.4    136    481

paired delta = -1.42 ms   sd 59.77   95% CI [-10.98, +8.15]   spread [-280.5, +173.8]
 16:18:23 load average: 12.74, 6.37, 4.00

 16:18:31 load average: 13.24, 6.58, 4.08
variant                      mean      sd   median    min    max   runs=300
off_enable-false            254.8    89.6    254.1    131    530
on_schema3-triggers         254.6    94.2    253.4    131    778

paired delta = -0.17 ms   sd 53.68   95% CI [-6.24, +5.91]   spread [-157.6, +270.3]
 16:21:10 load average: 11.28, 8.99, 5.43
```

**The 150-run sweep is reported rather than dropped.** Its interval reaches
+8.15 ms — inside the budget, but with 1.85 ms to spare, which bounds nothing
usefully. That is why the answer quotes 300, as stage 2 did for the same reason.
A run count chosen after seeing an interval is worth stating.

**The machine was loaded, and that is the point of the design.** Load average
was 4.99 at the start of the first sweep and 13.24 at the start of the second;
other agents were running work on this machine throughout. The absolute entry
cost moved with it — 267 ms, then 255 ms, against stage 2's 856 ms and stage 1's
218 ms on the same module. **Criterion 7 is a paired difference precisely
because the absolute figure measures the machine, not the module.** Interleaving
one entry at a time is what keeps that drift inside both variants instead of
inside the delta.

The sign of the point estimate is negative for the third stage running, and it
is meaningless for the third time: the effect is far smaller than the noise. The
spread, [-157.6, +270.3] ms, is two orders of magnitude wider than the budget.

**Nothing new forks in the hook**, and the measurement is what says so rather
than the argument. `builtins.fromTOML` runs at evaluation time and the guard in
`enterShell` compares one string; the entry grew one field.

**Charter impact:** **none.** Criterion 7 still holds.

**Cleanup:** both throwaway repositories and the copied source tree removed,
`devman doctor --prune` run, registry back to six projects.

---

## S16 — The watcher picks up a new project by itself, and it must not restart its own unit

**Answer:** option 2, implemented. `devman watch` is now a **supervisor** around
watchexec: it re-reads the registry every five seconds and replaces its
watchexec child when the set of watched paths changes. A repository that adopts
a reactive group is watched about five seconds later, with nothing restarted.
Proved by running it: a save in a project registered *after* the watcher started
enqueued a run that succeeded.

**Why not option 1** — leave it and let `doctor` say so. §5.2 already establishes
that registration cannot report, so the developer's first contact with the plane
is a quiet shell entry. Adding "and now go and restart a service you were not
told about" to that is the same failure twice. The gap also has no floor: a
machine whose registry declares no triggers at all ran `devman watch` to
completion and exited 0, so the *first* repository to adopt reactivity needed a
manual start, not merely a restart.

**Why not the obvious implementation, and this is the part that had to be
tested.** `systemctl --user restart devman-watch` issued from inside the unit's
own process **does not return**. systemd stops the unit, which kills the process
that asked, so every line after the call is dead code.

**Command — a transient unit whose only job is to restart itself:**

```bash
systemd-run --user --unit=s16-selfrestart --collect -p Type=simple \
  /tmp/s16-selfrestart.sh     # started; sleep 2; restart itself; echo RETURNED
```

**Evidence:**

```
16:19:44 s16-selfrestart.sh[1275407]: issuing restart of my own unit at 16:19:44
16:19:44 systemd[1034]: Stopping [systemd-run] /tmp/s16-selfrestart.sh...
16:19:44 systemd[1034]: Started  [systemd-run] /tmp/s16-selfrestart.sh.
16:19:44 s16-selfrestart.sh[1275859]: started pid 1275859 at 16:19:44
16:19:46 s16-selfrestart.sh[1275859]: issuing restart of my own unit at 16:19:46
   … 15 restarts in 30 seconds, every 2 seconds, until stopped by hand …

$ journalctl --user -u s16-selfrestart | grep -c "RETURNED"
0
$ systemctl --user show s16-selfrestart -p ActiveState -p Result -p NRestarts
ActiveState=active
Result=success
NRestarts=0
```

Two facts in that block, and the second is worse than the first. **`RETURNED`
appears zero times in fifteen restarts**, so a supervisor written that way can
run no code after the call. And **`NRestarts=0`** — systemd does not count a
restart it was asked for, so `startLimitBurst = 5` does not stop the loop, and
`ActiveState=active` with `Result=success` is what every monitor would see. That
is the silent-success failure `STAGE_3_PROMPT.md` §8 warns about, arriving in
the supervisor rather than in the watcher.

**So the supervisor replaces its own child and never touches its unit.**

**What changed, in three files:**

| File | Change |
|---|---|
| `src/devman/watch.py` | `supervise()` replaces `subprocess.run(argv)`. It polls `watch_map`, restarts watchexec on a changed **path** set, and rewrites the state file after the child is up |
| `src/devman/doctor.py` | the discrepancy check stays and stays `!!`; its advice now says the supervisor re-reads every five seconds. A second stamp, `watching_since`, separates "this process started" from "this watch set started" |
| `nix/nixos-module.nix` | the comment that stated the limit now states the mechanism, and why the unit must not restart itself |

**Only a changed path set restarts watchexec.** A changed glob does not: the
dispatcher calls `watch_map` again for every batch, so the mapping was already
live. The state file is rewritten whenever anything visible changes, so `doctor`
never prints a stale glob.

**Command — the proof, end to end, with the built CLI and the installed service
stopped:**

```bash
systemctl --user stop devman-watch
/nix/store/…-devman-0.3.0/bin/devman watch &      # supervisor, real registry
cd /tmp/s16-fmt && devenv shell -- true           # a NEW reactive project
printf 'z = 3\n' >> /tmp/s16-fmt/hello.py         # a save, nothing restarted
```

**Evidence — one supervisor, three watch sets, no restart:**

```
16:25:17  supervisor starts, pid 1312222
          watching ['devman', 's16-fmt']   started_at 16:25:17.981  watching_since 16:25:17.982

16:25:26  devman doctor --prune, after the project directory was moved away
          !!  stale entries   s16-fmt -> /tmp/s16-fmt (gone) — pruned, 9 links removed
          !!  watcher         it is watching ['devman', 's16-fmt'] and the registry now says ['devman']

16:25:33  watching ['devman']               watching_since 16:25:33.003   pid 1312222 unchanged
          child watchexec 1313067, --watch <devman> only

16:25:43  cd /tmp/s16-fmt && devenv shell -- true       (re-registers, schema 3)
16:25:48  watching ['devman', 's16-fmt']   watching_since 16:25:48.026   pid 1312222 unchanged

16:25:50  printf 'z = 3\n' >> /tmp/s16-fmt/hello.py
16:25:51  {"at":"…16:25:51.400","project":"s16-fmt","workflow":"format",
           "path":"/tmp/s16-fmt/hello.py","outcome":"enqueued"}
16:25:53  dagu's own history, ~/.local/share/dagu/data/dag-runs/s16-fmt-format:
           two runs started 16:25:53, both status 4 (succeeded)
```

The two runs are S6's counted behaviour, not a new fault: one save produces two
watchexec batches, and the second run's content-hash precondition skips the work.
An earlier cycle of the same test, against the first build, wrote
`{"dag":"s16-fmt-format","status":"succeeded", …}` into
`/tmp/s16-fmt/.devman/.runs/metadata.jsonl`, so the run landed in the project
that triggered it.

**Both directions, five seconds each, one process throughout.** The `!!` at
16:25:26 is `doctor` catching the seven seconds before the next poll, which is
the check still working rather than a fault.

**The empty case now waits instead of exiting**, which is what makes the *first*
adoption work:

```
$ devman watch --registry /tmp/s16-empty --poll-seconds 2
devman watch: no registered project takes a group that declares triggers.
  Nothing to watch yet. …
  Staying up and re-reading the registry every 2s, so a repository
  that adopts a reactive group is watched without a restart.
16:27:02  (an entry with triggers is written into that registry)
devman watch: late ['**/*.py'] -> format [python-format]
```

**`doctor` still tells a dead watcher from a watching one**, which was the
constraint on the whole change. The state file is written *after* the child
starts, so a wedged supervisor still reports as a discrepancy:

```
$ kill <supervisor>; devman doctor
!!  watcher   devman: **/*.py -> format  [python-format]
              s16-fmt: **/*.py -> format  [python-format]
              it is NOT running — the last one started 2026-08-22T16:25:17.981-04:00
                as pid 1312222 and is gone
              nothing is watching these repositories: systemctl --user start devman-watch
```

**What it costs, stated plainly:**

1. **One wake-up every five seconds, forever.** The work in it is
   `watch_map` — one `readdir` plus one small `metadata.json` per registered
   project — **measured at 0.440 ms for six projects on a machine at load
   average 11**, which is 0.009% of one core. It reads devman's own registry and
   never the disk at large, so §15.1's ban on scanning is untouched.
2. **Up to five seconds of delay** between `devenv shell` and the first save
   firing. A developer who has just entered a shell is not saving inside the same
   five seconds.
3. **A watchexec restart drops the batch in flight.** Watchexec gets SIGTERM and
   five seconds, then SIGKILL. A dispatch is an enqueue and takes well under
   that, and the registry only changes at shell entry, so the two coincide rarely.
4. **The service now stays up on a machine with nothing to watch.** The unit is
   no longer `Result=success, inactive` there; it is active and waiting. That is
   a behaviour change in `nix/tests/dagu-service.nix`, and the test now asserts
   the new one — plus a project appearing, a save firing, and `NRestarts`
   unchanged across both.
5. **It is a poll, not an inotify watch.** An inotify watch on
   `<registry>/projects/` would save 0.44 ms every five seconds and cost a second
   event source to get wrong.

**Charter impact:** **none.** §8 says the watcher is plane machinery that reads
the registry; this is that process reading it more than once. The registry still
changes only at shell entry, and nothing here scans for repositories.

**Cleanup:** the throwaway project removed, `devman doctor --prune` run, registry
back to six projects, `systemctl --user restart devman-watch` issued. The
installed service runs the machine's own generation, so it does not carry this
change until the user rebuilds.

---

## S17 — §3.1's `lib/` was never built, and nothing wants it

**Answer:** §3.1's shape diagram lists a `lib/` directory holding "registry
schema, registration helpers". **It does not exist and it never did.** The
registry schema lives where it is written — in `modules/devenv.nix`, as the
entry template the hook renders — and there are no registration helpers to
share, because the hook may not fork and the projection script is generated per
project.

**How it surfaced.** Rewriting `README.md` meant describing the repository's
layout. The charter was the obvious source, and it names a directory that is not
there.

**Command:**

```bash
$ ls -d lib
ls: cannot access 'lib': No such file or directory
$ grep -n '"schema"' modules/devenv.nix
271:      "schema": 3,
```

**Why nothing wants it.** §3.1's second rule says what the two interfaces share
must be **text**. The schema is text, and it is stated once, in the module that
writes it; the CLI reads that text back with `json.loads` and needs no shared
code to do it. A `lib/` of Nix helpers shared by both interfaces would be the
one thing the rule warns against — evaluated under two nixpkgs, differing
silently.

**Charter impact:** **changes §3.1's diagram.** Applied in its own commit, per
rule 4. The line is removed rather than the directory created: three stages have
run without it.
