# STAGE 5 — what was measured while asking identity the questions it has never been asked

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules,
`STAGE_2_LOG.md` what stage 2 found while turning the plane on, `STAGE_3_LOG.md`
what stage 3 found while making it react, and `STAGE_4_LOG.md` what stage 4
found while giving it work worth doing. This holds stage 5, in the same shape:
the answer, the versions, the exact command, the evidence, and the charter
impact.

**`CONCEPT.md` §13's rollout ends at stage 4.** So the first entry below is not
a measurement. It is what stage 5 decided to be, written before anything was
built, and what the rest of the stage is judged against.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, `systemd --user` unit `dagu`, up since 2026-08-22 19:18:26 EDT |
| devenv | 2.1.2 |
| devman | 0.3.0, `/run/current-system/sw/bin/devman` — `run`, `show`, `doctor`, `watch` |
| watchexec | 2.5.1, `systemd --user` unit `devman-watch` |
| Registry | `~/.local/share/devman/` — 6 projects, 33 workflows, 34 DAG links |
| Timer | `devman-maintain.timer`, enabled, daily, five `ExecStart` lines |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5`, at `df9cfe5` |

---

## S1 — What "done" means for stage 5, written before anything was built

**Why this entry exists.** §13 names four stages and stage 4 shipped the last of
them. §14 contains no stage-5 criterion. `STAGE_5_PROMPT.md` §6 therefore asks
this stage to decide what it is, write it down first, and be judged against what
it wrote. This entry was written before the first probe ran and it has not been
edited since; later entries record where it was met and where it was not.

**The state it was written against**, checked rather than copied forward:

```
$ devman doctor
devman doctor — 6 projects, 33 workflows
ok  plane / queues / validate / queue names / literal dir / shadowing /
    stale entries / run output / cross-repo / watcher            (eleven checks)
Nothing to report.                                               exit 0
```

### What stage 5 is, in one sentence

> **Stage 5 moves the plane's repositories.** It asks §9.1's identity model the
> four questions it claims to answer — a move, a rename, a second checkout, and
> a duplicate identity — against **real registered repositories with real run
> history, a live watcher and a live timer**, and it ships the fixes that asking
> produces.

**And what it is not.** It is not new automation content: no stage-5 deliverable
is a workflow that does work for a repository. Stage 4 gave the plane work; this
stage takes the ground out from under the work and watches what falls over.

**Why this one.** Every other candidate on `STAGE_5_PROMPT.md` §6's shortlist is
something the plane *does*. This is something the charter *claims*: §9.1 ends
with "this is what makes moving a repo, a second machine, a second checkout, and
a future remote worker all work without editing a workflow", and criterion 11
was last exercised at **stage 1**, against a throwaway `projA` in `/tmp` that had
no run history, no projection, no watcher and no timer. C5 in `FINDINGS.md`
tested the refusal against a *scratch copy* of the module and two empty
directories. **Four stages of the plane have grown on top of a promise last
checked when the plane was one module and three test repositories.**

### The ten conditions

**D1 — Four movements, each performed on a real registered repository, on the
installed plane.** Not on throwaways in `/tmp`, because the throwaway is what
stage 1 and C5 already did and it is what left the promise untested:

1. **a move** — the same repository, the same `devman.project`, a new path;
2. **a rename** — criterion 11's literal wording, the directory renamed;
3. **a second checkout claiming the same identity** — §9.1's refusal, on a
   repository that is really registered rather than a `/tmp` pair;
4. **a second checkout claiming a distinct identity** — §9.1's own stated
   remedy ("the second checkout states a distinct `project`"), which no
   measurement anywhere has ever run.

Each one states the command, the registry entry before and after, and **a
workflow run through the plane after the movement**, with its `metadata.jsonl`
line quoted. A movement whose only evidence is a registry entry is not measured:
stage 4's S2 is the record of a run that wrote the right JSON and did its work in
the wrong directory.

**D2 — Every movement is asked on six surfaces, not one.** The registry entry is
the first and the least interesting. Each movement also states what happened to:

| # | Surface | Why it can differ from the registry |
|---|---|---|
| 1 | the registry entry | §9.1's own test |
| 2 | the projection — `projects/<p>/workflows/`, `dags/<p>-<w>.yaml`, `dagu ls` | it is rebuilt by a script, not by the guard |
| 3 | run history, both halves | repo-side `.runs/` travels with the tree; Dagu's history is machine-side and keyed by DAG name (§9.2) |
| 4 | the watcher | it holds paths on a **command line** fixed when watchexec starts (§8, `STAGE_3_LOG.md` S16) |
| 5 | `devman-maintain.timer` | five hard-coded project names in the developer's own unit (`STAGE_4_LOG.md` S15) |
| 6 | `devman doctor` | the only thing allowed to tell the developer anything (§5.2) |

**Surface 4 is the reason this stage exists rather than the reason it is
interesting.** Everything above the registry has been built since criterion 11
was last run.

**D3 — No defect is diagnosed from a symptom that two hypotheses explain.**
`STAGE_5_PROMPT.md` §1, which is stage 4's S13 written as a rule. Every finding
below states the two readings and the probe that separates them, and a probe
that cannot separate them is recorded as not a measurement. Probes run against a
throwaway registry, a throwaway `DAGU_HOME` on its own ports, or the built CLI
under `--registry` — never by editing the live plane's state by hand.

**D4 — Every fix ships in the plane, and a fix that needs a rebuild is proved
before it is handed over.** `src/devman/` and `nix/nixos-module.nix` move the
machine closure, so a fix there is built with `nix build .#devman
--print-out-paths` and run directly against the live service with `--registry`
and `--dagu-home` (stage 4's S13 and S14 are the pattern). **No
`nixos-rebuild switch` is run by this session.**

**D5 — Five decisions answered, none deferred.** `STAGE_5_PROMPT.md` §7 names
six; the first is this entry. The rest each get a stated answer and the
measurement or the rule that decided it:

| # | Decision |
|---|---|
| 2 | whether §9.4 gets its first use, and what the module gains if it does |
| 3 | where `review` and `maintain` live, given that observantic has neither |
| 4 | whether `doctor` grows a check for a workflow that defines `handler_on` |
| 5 | what the machine module may still not learn — every option stage 5 *wanted* is written down before it is refused or written |
| 6 | whether `devman-maintain.timer` stays as it is |

"Left for stage 6" is not an answer.

**D6 — Every criterion that holds must still hold, measured rather than
asserted.** A criterion-by-criterion table against §14, in the shape of stage
3's S12 and stage 4's S12. **Five are re-run by command rather than reasoned
about**, because movement pressures them hardest:

| # | Why stage 5 pressures it |
|---|---|
| 11 | it *is* the subject. Move and rename a real repository and run its workflows |
| 8 | a movement is a registration, and the guard decides whether it happens twice |
| 13 | the watcher's watch set is derived from paths that stage 5 changes underneath it |
| 15 | "delete the state, re-enter, everything runs" is what makes a wrong move recoverable |
| 17 | a move is where a `devman register` gets invented, and it is the one thing that outranks everything else |

**D7 — Whatever stage 5 leaves must be readable without re-running it.** Stage
4's D6, which does not expire. Stage 5's deliverables are probes, fixes and
decisions rather than workflows, so the readable artefact is this log **plus
`devman doctor`'s own output**: where a fix adds a check, the entry quotes the
check firing and the check silent, and the check's text names the failure rather
than the rule.

**D8 — Nothing gives the registry a second entry path.** The rule that outranks
everything else, unchanged since stage 1. Stage 5's temptation has a shape and
it is named here in advance: **a `devman move`, a `devman rehome`, a `doctor
--rehome`, a "the path is gone, ask the user where it went" prompt, or a
registry field holding a previous path.** Each is a second way into the registry
wearing the clothes of a repair. If a movement appears to need one, this log
says so before anything is written. Reading devman's own registry is not
scanning; walking the disk to find a moved repository is (§15.1).

**D9 — The charter changes only in its own commit, and the log entry comes
first.** Rule 4. Stages 1–4 did this eight times.

**D10 — The machine is left as it was found, and every touched repository is
named.** Every moved repository ends the stage at a stated path with its own
commit named (rule 7), no throwaway is left in the registry, no directory named
literally `${DEVMAN_PROJECT_DIR}` or `${DEVMAN_SELF_DIR}` exists anywhere,
`devman doctor` is back to `Nothing to report`, and the timer still fires. A
machine change is proposed, evaluated and handed over.

### What this deliberately does not promise

- **Not a second machine.** §9.1 claims one and stage 5 does not test one. The
  honest reason is that the part a second machine tests which this host cannot —
  the NixOS module installing the service, `linger`, activation restarting a
  user unit — is a `nixos-rebuild switch` on a second host, and this session may
  not run one anywhere (`STAGE_5_PROMPT.md` §8). A second registry and a second
  Dagu on *this* host would test the part that is already stage 1's shape, so it
  buys a sentence rather than a measurement. **This is a gap stage 5 leaves
  open, and it is written into the closing entry rather than quietly dropped.**
- **Not a publish, and therefore not §9.4's first use.** Stage 4's S7 decided
  "no secret" by measurement, and wrote its own trigger condition: a value that
  is **not** in `$HOME`. Nothing in a move, a rename or a second checkout needs
  one. Publishing would force the decision, and publishing is irreversible, wants
  a credential, and would be fired by a timer with nobody watching — so stage 5
  does not publish, and D5's decision 2 records that rather than pretending the
  question was closed.
- **Not a new criterion.** §14 is the charter's. D6 says its seventeen must still
  hold; this entry defines when *this stage* is finished, and nothing more.
- **Not a rewrite of anything that works.** `STAGE_5_PROMPT.md` §1 is explicit,
  and so is the list of six lines that look needlessly indirect and are not.

**Charter impact:** **none.** This entry is stage 5's own definition of done, not
an amendment to §14.

---

## S2 — One repository moving stops reactivity for every repository, and nothing brings it back

**Answer:** watchexec exits immediately when **any** `--watch` path does not
exist. The supervisor exits with it, `Restart=on-failure` tries five times,
`startLimitBurst` gives up, and `devman-watch` is left **failed** — 30 seconds
after the first restart, for every registered repository at once. **It does not
recover when the moved repository comes back**, because a failed unit is
restarted by nothing except a person or an activation.

This was invisible for two stages because the watch set has had **one** entry
since stage 3, and that entry is this repository, which has never moved.

**Tested:** the installed plane. devman 0.3.0, watchexec 2.5.1, Dagu 2.15.0.

### The probe repository, and the two things it proved before it broke anything

`~/s5-probe` — a throwaway taking `base` and `python-format`, `project =
"s5-probe"`, registered the only way there is (§5.2, criterion 17):

```bash
cd ~/s5-probe && devenv shell -- true
```

**Evidence — the watcher picked up a second repository by itself**, which S16 of
stage 3 built and which no measurement had ever exercised with two:

```
$ devman doctor
ok  watcher        devman:   **/*.py -> format  [python-format]
                   s5-probe: **/*.py -> format  [python-format]
                   watching this set since 2026-08-22T19:49:12.625-04:00
```

**Evidence — and reactivity works in it**, one save, one run, unedited group
files:

```
$ printf 'y  =  2\n' >> ~/s5-probe/a.py
{"at":"19:49:38.272","project":"s5-probe","workflow":"format",
 "path":"/home/andrew/s5-probe/a.py","outcome":"enqueued"}
$ tail -1 ~/s5-probe/.devman/.runs/metadata.jsonl
{"dag":"s5-probe-format","run_id":"034BpgG8sIRVVOfNEyHZJN","status":"succeeded", …}
```

### The move, and the two hypotheses it had to separate

**Command:**

```bash
mv ~/s5-probe ~/s5-probe-moved
```

**Nothing happened for the next 42 seconds**, and that is the first half of the
finding:

```
19:50:05 active running success 0        <- NRestarts, Result
19:50:41 active running success 0
```

**Two readings, and they are not the same claim.** Either the plane tolerates a
move, or the watcher is holding an inode rather than a path and the damage waits
for the next restart. A save in the moved tree separates them:

```
$ printf 'z  =  3\n' >> ~/s5-probe-moved/a.py
{"at":"19:51:01.817","project":"s5-probe","workflow":"format",
 "path":"/home/andrew/s5-probe/a.py","outcome":"refused (1)"}   <- the OLD path

$ journalctl --user -u devman-watch
devman: refusing to enqueue in 's5-probe'
devman:  its registered path /home/andrew/s5-probe is not a directory
devman:  run `devman doctor --prune` to reconcile the registry (§10 check 5)
```

**That part is the design working, and it is worth saying before the part that
is not.** watchexec kept watching the moved *inode* and reported the path it was
given, the dispatcher matched it, and `devman run` **refused** — the check at
`src/devman/run.py:196`, which exists because Dagu creates a missing
`working_dir` and reports success (§9.2). A run in a directory that is no longer
the project is exactly what it prevents, and the refusal is recorded in
`fired.jsonl` and in the journal.

### The restart, which is where it breaks

**Command** — one restart, which is what a rebuild, a reboot, or another
repository adopting a reactive group each cause:

```bash
systemctl --user restart devman-watch
```

**Evidence:**

```
19:51:28 activating auto-restart exit-code 0
19:51:33 activating auto-restart exit-code 1
19:51:38 activating auto-restart exit-code 2
19:51:43 activating auto-restart exit-code 3
19:51:48 activating auto-restart exit-code 4
19:51:53 failed      failed       start-limit-hit 5

$ journalctl --user -u devman-watch
devman watch: devman   ['**/*.py'] -> format [python-format]
devman watch: s5-probe ['**/*.py'] -> format [python-format]
Error:   × No such file or directory (os error 2)
devman-watch.service: Start request repeated too quickly.
Failed to start devman watcher — one watchexec for every registered repository.
```

**Thirty seconds, five restarts, and reactivity is off for the whole machine.**
watchexec's message names **no path**, so the journal does not say which
repository is missing. `devman`'s own saves stopped firing, and `devman` had not
moved.

**And it does not heal.** Re-entering the moved repository's shell fixes the
registry, and the unit stays down:

```
$ cd ~/s5-probe-moved && devenv shell -- true
$ grep '"path"' ~/.local/share/devman/projects/s5-probe/metadata.json
  "path": "/home/andrew/s5-probe-moved",          <- identity survived the move
$ systemctl --user show devman-watch -p ActiveState -p Result --value
failed  start-limit-hit                            <- the watcher did not
```

`Restart=on-failure` is the right setting and it is not the problem: it did what
it says, five times, against a condition that could not resolve itself.

### What `devman doctor` said, and the sentence it did not have

```
!!  stale entries  s5-probe -> /home/andrew/s5-probe (gone) — its workflows still
                   project and would pass, vacuously, in a directory Dagu creates
!!  watcher        devman: **/*.py -> format  [python-format]
                   s5-probe: **/*.py -> format  [python-format]
                   it is NOT running — the last one started … as pid 2041626 and is gone
                   nothing is watching these repositories: systemctl --user start devman-watch
```

**Both facts, four lines apart, and no connection between them.** A developer
reading that runs the command it suggests, and the unit fails again inside 30
seconds. Worse, the watcher check lists `s5-probe` as something being watched.

### The fix: a stale entry is dropped from the watch set, by name

`watch_map` skips a project whose registered path is not a directory, and
`unwatchable` names it — in the journal when the supervisor starts, and in
`doctor`. Skipping is right rather than merely safe: watching a path that does
not exist watches nothing, and §10 check 5 already owns a registered path that
is gone.

**Evidence — both branches, against the built CLI and one throwaway registry
holding one live project and one stale one:**

```
$ timeout 10 devman --registry /tmp/s5-reg watch          # installed 0.3.0
devman watch: devman   ['**/*.py'] -> format [python-format]
devman watch: s5-probe ['**/*.py'] -> format [python-format]
Error:   × No such file or directory (os error 2)
exit=1                                                    <- dead in under a second

$ timeout 10 /nix/store/lgz81gz…-devman-0.3.0/bin/devman --registry /tmp/s5-reg watch
devman watch: devman ['**/*.py'] -> format [python-format]
devman watch: skipping s5-probe — its registered path /home/andrew/s5-gone is not
              a directory, and watchexec exits on one. Enter its shell to
              re-register it, or `devman doctor --prune`
exit=124                                                  <- still alive at 10s
```

**Evidence — and it still fires for the repository that is there**, which is the
claim that matters. The fixed supervisor, run against that same registry with
the stale entry still in it:

```
$ printf '# s5 probe touch\n' >> src/devman/_s5_touch.py
$ cat /tmp/s5-reg/watch/fired.jsonl
{"at":"19:55:51.237","project":"devman","workflow":"format",
 "path":"…/src/devman/_s5_touch.py","outcome":"enqueued"}
```

`doctor` gains one line in the same place, so the two facts are connected:

```
s5-probe: NOT watched — /home/andrew/s5-gone is not a directory.
          Enter its shell to re-register it, or `devman doctor --prune`
```

**The watcher check stays `ok` when the watcher is healthy**, and the stale entry
stays the one `!!`. That is S14's lesson applied rather than restated: the
watcher is working correctly on the repositories that exist, and calling it a
fault would be calling a busy queue wedged.

### What this cost, and what it needs

`src/devman/` moves the machine closure, so **this needs a rebuild and has not
had one**. Proved by the built CLI above and by both checks:

```
$ nix build .#checks.x86_64-linux.dagu-service   --no-link    # exit 0
$ nix build .#checks.x86_64-linux.groups-validate --no-link   # exit 0
```

**Charter impact:** **none.** §8 already says one watcher serves every
repository and §15.3 already accepts that as a shared availability failure. This
is the plane finally not *causing* one out of an ordinary `mv`.

---

## S3 — A second checkout: the refusal is exactly right, and the checkout *inside* the first one ran in the wrong tree

**Answer:** §9.1's refusal fired word for word on a real registered repository,
and §9.1's stated remedy — "the second checkout states a distinct `project`" —
works and had never been run. **One case was silent and is now a refusal:** a
second checkout **nested inside** a registered one. `devman run` there resolved
to the outer project and enqueued a run against the outer tree, with nothing
said.

**Tested:** the installed plane, this repository, `git worktree`. `FINDINGS.md`
C5 measured the refusal against a scratch copy of the module and two empty
directories in `/tmp`; this is the first time it has been asked of a repository
that is really in the plane, with 10 projected workflows and a live watcher.

### The refusal, on a real repository

**Command:**

```bash
git worktree add --detach ~/s5-devman-b HEAD
cd ~/s5-devman-b && devenv shell -- true
```

**Evidence:**

```
devman: refusing to register 'devman'
devman:   already registered at /home/andrew/.paseo/worktrees/1n48r26y/special-dragon, which still exists
devman:   this repo is        /home/andrew/s5-devman-b
devman:   set a different devman.project in one of them
```

**And it refused without breaking anything.** The shell opened, the registry
entry still names the first checkout, and the projection is untouched:

```
$ grep '"path"' ~/.local/share/devman/projects/devman/metadata.json
  "path": "/home/andrew/.paseo/worktrees/1n48r26y/special-dragon"
$ readlink ~/.local/share/devman/dags/devman-check.yaml
../projects/devman/workflows/check.yaml
```

**And the refused checkout cannot trigger anything either**, which matters more
than the message: a registration that refuses would be theatre if the CLI then
ran from there anyway.

```
$ cd ~/s5-devman-b && devman run check --print
devman: /home/andrew/s5-devman-b is not inside a registered repository
devman:  enter its devenv shell once to register it (§5.2), or name a
devman:  project with --project                                          exit 1
```

### §9.1's remedy, run for the first time

**Command** — one word changed in the second checkout's own `devenv.nix`:

```bash
sed -i 's/project = "devman";/project = "devman-b";/' ~/s5-devman-b/devenv.nix
cd ~/s5-devman-b && devenv shell -- true
devman run check
```

**Evidence — two checkouts of one repository, both in the plane:**

```
devman   -> "path": "/home/andrew/.paseo/worktrees/1n48r26y/special-dragon"
devman-b -> "path": "/home/andrew/s5-devman-b"

$ ls ~/.local/share/devman/dags/ | grep '^devman-b'
devman-b-agent-review.yaml  devman-b-bench-entry.yaml  devman-b-check.yaml
devman-b-format.yaml        devman-b-full-test.yaml    devman-b-maintain.yaml
devman-b-release.yaml       devman-b-review.yaml       devman-b-stack-validate.yaml
devman-b-validate.yaml

level=INFO msg="Enqueued dag-run" dag=devman-b-check run-id=034Bq0AJLe6sSpBas2elOg
    params="[DEVMAN_PROJECT_DIR=/home/andrew/s5-devman-b]"
```

Ten workflows, its own DAG names, its own `.devman/.runs/`, and the first
checkout untouched. §9.2's "run output belongs to a **working tree**, not a
project" is what makes that work rather than a coincidence.

### The case that was silent: a checkout inside a checkout

`git worktree add .worktrees/feature` is an ordinary layout, and it puts a whole
other working tree **inside** a registered path. Such a checkout can never
register — §9.1 refuses the duplicate identity — so `Registry.project_for`
answers with the only registered path that contains it: **the outer one.**

**Command:**

```bash
git worktree add --detach .worktrees/s5-inner HEAD
cd .worktrees/s5-inner && devman run check --print
```

**Evidence — the installed 0.3.0:**

```
DEVMAN_PROJECT_DIR=/home/andrew/.paseo/worktrees/1n48r26y/special-dragon \
  dagu … enqueue devman-check -- DEVMAN_PROJECT_DIR=/home/andrew/…/special-dragon
exit=0
```

**The developer is standing in one working tree and the run happens in
another**, on another commit, with a zero exit code and no message. That is
`STAGE_4_PROMPT.md` §10's failure — a successful run that did the wrong thing —
reached by typing an ordinary command in an ordinary directory.

**Two readings, and only one of them is a defect.** "The deepest registered path
containing this directory" is also what makes `devman run check` work from
`src/devman/`, which must keep working. The separating fact is whether the
directory between the caller and the project root is **a checkout of its own**:
`src/devman/` is a subdirectory, `.worktrees/s5-inner` holds a `.git`.

**The fix** walks up from the caller to the project root and refuses when it
crosses a `.git` — a file in a linked worktree, a directory in a clone, and
either way not part of the project the registry would answer with:

```
$ cd .worktrees/s5-inner && devman run check --print          # the built CLI
devman: refusing to resolve 'devman' from this directory
devman:  /home/andrew/…/special-dragon/.worktrees/s5-inner
devman:  is a checkout of its own, inside 'devman' at /home/andrew/…/special-dragon
devman:  a run triggered here would do its work in the outer checkout, not this one
devman:  give this checkout a distinct devman.project and enter its shell (§9.1),
devman:  or say --project explicitly                                       exit 1

$ cd src/devman && devman run check --print                   # must still work
DEVMAN_PROJECT_DIR=/home/andrew/…/special-dragon dagu … enqueue devman-check
exit=0

$ cd .worktrees/s5-inner && devman run check --project devman --print
DEVMAN_PROJECT_DIR=/home/andrew/…/special-dragon dagu … enqueue devman-check
exit=0                                        <- an explicit --project is not guessing
```

**It is not a scan.** §15.1 forbids walking the disk to find repositories; this
walks **up** a path the registry already names, one `exists` per level, and
finds no repository — it asks whether the directory the caller is standing in is
its own checkout. `doctor`'s literal-directory check has the same shape
downwards.

**A submodule answers the test too, and that is intended.** A run triggered
inside a submodule and executed in the parent checkout is the same ambiguity, and
this plane's habit everywhere else is to refuse rather than to guess.

**One thing this session did to itself, and rule 1 says to report it.** With
`.worktrees/s5-inner` in place, three of this session's own commands ran there
by accident — including a `nix build .#devman`, which quietly built the flake at
`HEAD` instead of the working tree and produced a store path with none of the
edits in it. The measurement above is what that looked like from the other side:
**a tool that resolves "the project" from the current directory has no way to
know which checkout you meant.**

**Charter impact:** **none.** §9.1 already says the second checkout states a
distinct project; this is the CLI enforcing at the trigger what registration
already enforces at the shell.

---

## S4 — Criterion 11, on a real repository with real run history

**Answer:** **it holds.** `pyjutsu` was moved **and** renamed in one command and
re-entered: the identity survived, the entry was replaced rather than
duplicated, the projection was rebuilt, both halves of the run history survived,
and `devman run review` ran in the new location. Criterion 11 was last exercised
at **stage 1**, against a throwaway `projA` with none of those things.

**Tested:** the installed plane. `pyjutsu` — 5 projected workflows, 5 recorded
runs, 4 reports, 2 log trees, on `main@099c032`, its tree clean.

**Command** — a move and a rename at once, which is criterion 11's own wording:

```bash
mv ~/Documents/Projects/pyjutsu ~/s5-elsewhere/pyjutsu-renamed
cd ~/s5-elsewhere/pyjutsu-renamed && devenv shell -- true
```

**Evidence — the entry was replaced, not duplicated:**

```
before re-entry:  "path": "/home/andrew/Documents/Projects/pyjutsu"     <- stale
after  re-entry:  "path": "/home/andrew/s5-elsewhere/pyjutsu-renamed"
projects/: devman  devman-b  nix-paseo  observantic  pydantree  pyjutsu  s5-probe  siteman
```

One `pyjutsu`, not two. §9.1's `[ -d ]` on the recorded path is the whole of the
test: the old path was gone, so this is a move rather than a collision, so the
entry is replaced. The refusal in S3 and the replacement here are the same three
lines of shell taking different branches.

**Evidence — the projection was rebuilt at the new path:**

```
$ ls ~/.local/share/devman/projects/pyjutsu/workflows/
check.yaml  full-test.yaml  maintain.yaml  review.yaml  validate.yaml
$ readlink ~/.local/share/devman/dags/pyjutsu-review.yaml
../projects/pyjutsu/workflows/review.yaml
```

**Evidence — both halves of the run history survived, and they survive
differently.** Repo-side output travels with the tree because it is *in* the
tree; machine-side history stays where it is because it is keyed by DAG name and
a move does not change the name:

```
repo-side   ~/s5-elsewhere/pyjutsu-renamed/.devman/.runs/metadata.jsonl   5 lines
            .devman/.runs/reports/                                        4 files
machine-side ~/.local/share/dagu/data/dag-runs/pyjutsu-maintain/…/22/
            dag-run_20260822_232308Z_034Bp1wG5SOs46lNVfWnKn      ) all four
            dag-run_20260822_232438Z_034Bp4DmT5plJ97J9Gm8Ve      ) recorded
            dag-run_20260822_232535Z_034Bp5f4YQDOc7SYPo0wE1      ) before
            dag-run_20260822_232835Z_034BpAEvDv2B5dtTH0TFD0      ) the move
```

**One thing a move leaves behind, and it is honest to say it.** Every
`metadata.jsonl` line written before the move records an absolute `log` path
that no longer exists:

```
{"dag":"pyjutsu-check", … "log":"/home/andrew/Documents/Projects/pyjutsu/.devman/.runs/logs/…"}
```

The logs themselves moved with the tree; the *recorded* path did not, because a
line is a record of what was true when the run happened. Nothing rewrites it and
nothing should: §9.3 makes the registry derived and the repository canonical, and
a history that edits itself to stay plausible is worse than one that is dated.

**Evidence — a workflow ran in the new location:**

```
$ cd ~/s5-elsewhere/pyjutsu-renamed && devman run review
level=INFO msg="Enqueued dag-run" dag=pyjutsu-review run-id=034Bq2FKH3zqR0BMNwzngX
    params="[DEVMAN_PROJECT_DIR=/home/andrew/s5-elsewhere/pyjutsu-renamed]"

.devman/.runs/reports/review-034Bq2FKH3zqR0BMNwzngX.md
# review — pyjutsu-review
- head: `099c032` on `main`
## verdict
- `base:lint` pass
- `base:test` FAIL
```

### `base:test` failed, and that is where two hypotheses had to be separated

A failing check in the first run after a move is exactly the symptom that
invites the wrong conclusion. Two readings: **the move broke the repository's
own build environment** (a devenv venv full of absolute paths is a real thing),
or **it fails identically at the old path** and the move cost nothing.

**The probe is the restore**, which had to happen anyway (D10):

```bash
mv ~/s5-elsewhere/pyjutsu-renamed ~/Documents/Projects/pyjutsu
cd ~/Documents/Projects/pyjutsu && devenv shell -- true && devman run review
```

**Evidence — the same failure, at the original path:**

```
{"dag":"pyjutsu-review","run_id":"034Bq4xqBy4W7OzXhPr8F5","status":"partially_succeeded"}
## verdict
- `base:lint` pass
- `base:test` FAIL
```

```
💥 maturin failed
  Caused by: Couldn't find a virtualenv or conda environment …
✖ Running pyjutsu:build — dep pyjutsu:test status=Completed(DependencyFailed)
```

**So it is pyjutsu's own debt, like pydantree's 920 ruff findings, and the move
cost it nothing.** Corroborated rather than assumed: the moved checkout's
`.devenv/state/venv` holds no reference to the old path — the shell entry that
re-registered it rebuilt the venv at the new location, which is devenv doing its
job and is the reason the entry took 18 s instead of 2 s.

**And the report is the thing a person reads.** `review` recorded
`partially_succeeded` in both places, because its check steps carry
`continue_on` and stage 4's S8 measured that such a run does not open the release
gate. A move did not turn a red repository green.

**Charter impact:** **none.** Criterion 11 holds, and now against a repository
with something to lose.

---

## S5 — Decision 3: `review` and `maintain` are not ecosystem content, so observantic takes `base`

**Answer:** **observantic takes `base` as well**, and no file is copied into
`python`. Stage 4 left the one repository that most looks like a publishable
library with no `review` and no `maintain`, because both live in `base` and it
took `python` and `release` only (`STAGE_4_LOG.md`, S15).

**Three answers existed and §16's promotion rule decides between them.** That
rule says a *group* begins when a second repository wants the same file. It says
nothing about copying a file into a second group, and that is the option to
reject first:

| Answer | Verdict |
|---|---|
| copy `review` and `maintain` into `python` | **no.** One file in two groups is two files to keep in step, and §3.1 exists to prevent exactly that drift. A repository taking `base` and `python` would then resolve `python`'s copy, so the group that shadows would decide which copy runs |
| observantic takes `base` too | **taken.** One word in `groups`, two task aliases, and `python` still shadows `check` and `validate` |
| leave the gap and say why | **no**, and the reason is what the other two make visible: neither workflow is ecosystem content |

**What settles it is what the two files contain.** `review` runs `git` and the
two names `base` asks for. `maintain` prunes `.devman/.runs/` and runs `devman
doctor`. **Neither mentions Python, and neither would differ by one line if it
lived in `python`** — which is the test for whether a file belongs to an
ecosystem group at all. `base` is the group that carries the leverage precisely
because it holds what every repository has (§16: `devenv.nix` at 80% coverage,
against `pyproject.toml`).

**Command — the change to observantic** (rule 7: it is somebody else's
repository, committed there and named here):

```nix
groups = [ "base" "python" "release" ];

# base's two names, aliased onto the tasks this repository already defines.
"base:lint".after = [ "python:lint" ];
"base:test".after = [ "python:test" ];
```

That is pyjutsu's pattern, unchanged: a devenv task with only `after` and no
`exec` runs its dependency and fails when the dependency fails, so it duplicates
no command body.

**Evidence — what observantic now projects**, and §7.3 doing its job:

```
check     python  (shadows base)      review     base
validate  python  (shadows base)      maintain   base
release   release                     full-test  base
```

**Evidence — both new workflows ran, unedited, on the installed plane:**

```
$ devman run review
level=INFO msg="Enqueued dag-run" dag=observantic-review run-id=034BqE3NClDMTbqz4wlAG2
{"dag":"observantic-review", … "status":"succeeded", …}

.devman/.runs/reports/review-034BqE3NClDMTbqz4wlAG2.md
## verdict
- `base:lint` pass
- `base:test` pass

$ devman run maintain
{"dag":"observantic-maintain","run_id":"034BqEovCGsaiOYBf0oXwv", … "status":"succeeded", …}

.devman/.runs/reports/maintain-034BqEovCGsaiOYBf0oXwv.md
- reports: 3 before, 3 after — 0 pruned
- artifacts: 3 entries, **never pruned here** — remove them by hand
- log trees: 8, pruned by the machine's hist_retention_days when this project's DAGs run
```

**`review` and `maintain` now reach six of six registered repositories.** The
artifact line is the one worth reading: observantic has three built wheels and
sdists under `.devman/.runs/artifacts/` from stage 4's releases, and until today
no workflow in that repository ever counted them.

**And it creates one drift, which is decision 6's subject and is recorded rather
than fixed here** (S9): `devman-maintain.timer` has five `ExecStart` lines and
observantic is still not one of them.

| Repository | Commit | What changed |
|---|---|---|
| `observantic` | `d57cc8b` | `devenv.nix` — `"base"` in `groups`, two task aliases |

**Charter impact:** **none.** §16's promotion rule decided it, unamended.

---

## S6 — Two projects, one DAG name: the run that executed another repository's workflow and reported success

**Answer:** **`<project>-<workflow>` is not injective, and nothing checked it.**
`devman-b` + `check` and `devman` + `b-check` render the same flat name. The
second projection takes the first's `dags/` link with `ln -sfn`, and every
trigger for that name then runs **one** file, in whichever project asked. The
run succeeds, the logs land correctly, and `devman show` prints the file that
did **not** run.

**This is stage 5's own subject producing a defect.** S3 established that a
second checkout states a distinct `project`, and the obvious name for a second
checkout of `devman` is `devman-b`.

**Tested:** the installed plane, both projects registered the only way there is.

**Command** — one throwaway workflow in this repository, and one shell entry:

```bash
cat > .devman/workflows/b-check.yaml <<'YAML'
queue: light
steps:
  - name: whoami
    run: echo "I am devman's own b-check, running in $PWD"
YAML
devenv shell -- true
```

**Evidence — the link changed owner:**

```
$ ls -l ~/.local/share/devman/dags/devman-b-check.yaml
devman-b-check.yaml -> ../projects/devman/workflows/b-check.yaml

$ readlink ~/.local/share/devman/projects/devman-b/workflows/check.yaml
/nix/store/hks3gb8…-devman-base-check.yaml         <- devman-b's own file, still there
```

**Evidence — and the run went to the wrong file, in the right directory:**

```
$ devman run check --project devman-b
level=INFO msg="Enqueued dag-run" dag=devman-b-check run-id=034BqGySNV89AihEO7VXz2
    params="[DEVMAN_PROJECT_DIR=/home/andrew/s5-devman-b]"

$ cat ~/s5-devman-b/.devman/.runs/logs/devman-b-check/…/whoami….out
I am devman's own b-check, running in /home/andrew/s5-devman-b

$ devman show check --project devman-b --path
/nix/store/hks3gb8…-devman-base-check.yaml         <- what devman says would run
```

**Three statements about one run, and only the first is true.** Dagu ran
`b-check`. `devman show` named `check`. The exit code said everything was fine.
This is the failure `STAGE_4_PROMPT.md` §10 names — a successful run that did the
wrong thing — and it needs no exotic setup: two projects, one of whose names is a
prefix of the other, and one workflow whose name begins with the difference.

**§9.2 half-knew.** `Registry.unproject` already refuses to remove a link that
points elsewhere, with the comment *"`<project>-<workflow>` is ambiguous when one
project name is a prefix of another, and the link target is not"*. The ambiguity
was written down where it was inconvenient and nowhere else.

### The fix, in the two places that were lying

**`doctor` gains a `projection` check.** For every projected workflow it reads
`dags/<project>-<workflow>.yaml` and compares the target against that project's
own file. One `readlink` each, no daemon needed:

```
!!  projection     devman-b-check: the DAG of that name points at
                   ../projects/devman/workflows/b-check.yaml
                   a trigger enqueues by name, so these run the wrong file and
                   report success — rename one project or one workflow (§9.2)
```

**And `devman run` refuses**, because a trigger states its target and this is the
one thing it could not previously state:

```
$ devman run check --project devman-b
devman: refusing to enqueue 'check' in 'devman-b'
devman:  the DAG named devman-b-check points at ../projects/devman/workflows/b-check.yaml
devman:  it resolved to …/projects/devman-b/workflows/check.yaml, and that is not what would run
devman:  two projects render one flat DAG name — rename one project or one workflow
devman:  (§9.2), then re-enter both shells                                       exit 1
```

**Evidence — the silent branch, on the healthy plane:**

```
ok  projection     39 DAG names each point at their own project's file
```

**What the fix does not do: it does not rename anything.** The plane cannot
choose which of two projects owns a name, and §9.1 makes identity the
repository's own statement. So both surfaces report and refuse, and a person
renames — the same shape as §9.1's duplicate-identity refusal, one level down.

**Charter impact:** **changes §9.2.** Its `dags/` block presents
`<project>-<workflow>` as *the* machine-global key and does not say the mapping
is not injective. Applied in its own commit, per rule 4, after this entry was
written.

---

## S7 — §9.3 promised reconstruction and delivered it only for total loss

**Answer:** *"Everything under `~/.local/share/devman/` is reconstructable by
re-entering every registered repo's shell"* was true for deleting **all** of it
and false for deleting **one link**. The guard compared the rendered registry
*entry* against disk, plus one `[ -d dags ]`. A missing `dags/` link left the
entry matching, so re-entering the shell did nothing and the workflow stayed
unrunnable by name.

**Found by the repair, not by looking.** S6's colliding projection removed
`devman-b`'s link as collateral damage; re-entering that checkout's shell — the
one remedy §9.3 offers — did not bring it back.

**Command — the same fault, produced deliberately on a second project:**

```bash
rm ~/.local/share/devman/dags/s5-probe-review.yaml
cd ~/s5-probe-moved && devenv shell -- true
ls ~/.local/share/devman/dags/s5-probe-review.yaml
```

**Evidence:**

```
"…/dags/s5-probe-review.yaml": No such file or directory (os error 2)
```

**Why, read rather than assumed** (`modules/devenv.nix`):

```bash
if [ "$devman_disk" != "$devman_rendered" ] || [ ! -d "$devman_reg/dags" ]; then
```

The `[ -d ]` is there for exactly this reason — stage 2's S13 deleted the whole
registry and re-entry rebuilt it byte for byte — and it checks the directory
rather than what is in it. **Total loss was tested and partial loss was not.**

### The fix: one `[ -L ]` per projected workflow, and no fork

```bash
devman_relink=""
for devman_n in $devman_names; do
  [ -L "$devman_reg/dags/<project>-$devman_n.yaml" ] || devman_relink=1
done
```

`$devman_names` is the group-resolved set, known at evaluation time, plus the
repository's own `.devman/workflows/` names, which the hook already walks.

**Evidence — the same command, with the fixed module:**

```
$ rm ~/.local/share/devman/dags/s5-probe-review.yaml
$ cd ~/s5-probe-moved && devenv shell -- true
$ readlink ~/.local/share/devman/dags/s5-probe-review.yaml
../projects/s5-probe/workflows/review.yaml                     <- rebuilt
```

**It tests existence and not the target, deliberately.** Reading a symlink costs
a fork, and §5.2's rule that the hook must fork nothing is not a preference — it
is why criterion 7 holds. A link pointing at *another project's* file is S6's
`doctor` check, on a path that is allowed to spend a process.

**What it costs, measured** (rule 2 — a timing without a spread is not a
timing). The loop, over this repository's ten projected workflows, 200 firings
per repeat, five repeats:

```
0.1878  0.1058  0.1085  0.0880  0.1674   ms per firing
```

Mean **0.13 ms**, range 0.088–0.188. `enterShell` fires twice per entry (§5.2),
so about **0.26 ms per shell entry** against criterion 7's 10 ms budget, and it
adds no process.

**And it reaches repositories without a rebuild**, because `modules/devenv.nix`
is the repo interface: each repository picks it up at its own next re-pin (§3.2).

**Charter impact:** **none**, and that is the point — the fix makes §9.3's
sentence true rather than making the sentence wrong. It is worth recording that
the sentence was *load-bearing and unverified for partial damage* for four
stages, and that the check which existed (`[ -d dags ]`) was written by somebody
who had this exact failure in mind and stopped one level too high.

---

## S8 — Decision 4: `doctor` checks for a workflow that defines `handler_on`, and it is not §15.7

**Answer:** **yes, and it ships.** A workflow defining its own `handler_on`
replaces `base.yaml`'s whole-field and stops recording its runs — measured at
stage 4 (S3), written into §9.2 in prose, and checked by nothing until now.

**Where it falls on §15.7.** §15.7 says nothing checks that a default still
fits: the plane holds no opinion about what a workflow *does*, what it costs, or
whether a four-minute `check` is still a `check`. **This check has no opinion
about any of that.** It is §11's check one field over: a workflow that silently
takes away something the *machine* promised. The distinction that decides it:

| §15.7 refuses a check about | This check is about |
|---|---|
| what the work is, and what it costs | whether the run is recorded at all |
| a heuristic that cannot know your machine | one field, present or absent |
| a rule the plane cannot check | a rule the plane can check exactly |

`metadata.jsonl` is not decoration: §9.2 promises it survives every retention
setting, stage 4's release gate reads it to decide whether a release may
proceed, and `maintain` counts from it. A workflow that removes the writer takes
all three away, and the run reports success.

**Evidence — the firing branch**, against a throwaway registry carrying one such
file:

```
!!  handlers       devman-_s5_handler defines handler_on (exit) — it replaces
                   base.yaml's, so its runs append no line to
                   .devman/.runs/metadata.jsonl (§9.2)
```

**Evidence — the silent branch**, against the real registry:

```
ok  handlers       no workflow defines handler_on, so every run is recorded
```

**It reports every key, not only `exit`.** `handler_on` is one field, so a DAG
defining `success` alone still replaces the block, exit handler included. The
check names what it found so the message is a fact rather than a rule.

**Charter impact:** **none.** §9.2 already warns about this in prose; the warning
now has a check behind it, which is what §10's list of "six things it must
compute itself" is for.

---

## S9 — Decisions 2, 5 and 6, stated

### Decision 2 — §9.4 stays unused, and stage 5 is not the stage that changes it

**Answer: no secret, and the machine module grows nothing.** Stage 4 decided the
same by measurement and wrote its own trigger condition into S7: *a value that
is not in `$HOME`*, which is what publishing needs. **Stage 5 publishes
nothing.** A move, a rename, a second checkout and a duplicate identity all run
under the developer's own `$HOME`, git credentials and SSH agent (§4), exactly
as stage 4's deliverables did.

**That this was a choice and not an oversight is what S1 wrote down in advance**:
publishing is irreversible, wants a credential, and would be fired by a timer
with nobody watching. Stage 5 deliberately took a subject that does not need one,
because the alternative was to acquire a credential in order to justify a
section.

So §9.4 is **specified and unused after five stages**, and the word `secret`
still appears nowhere in `nix/`, `modules/`, `groups/` or `src/`. S7 of stage 4
still names exactly what would change the answer and what the module would gain:
one `EnvironmentFile=` option on the Dagu unit, never an `environment.X = value`,
because a value in a NixOS module is a value in the world-readable store.

### Decision 5 — what the machine module may still not learn

§4's table is the load-bearing wall, and `STAGE_5_PROMPT.md` §7 asks for what
this stage *wanted* before it refused it. **Stage 5 wanted three things. All
three were refused, and two were refused into an existing mechanism rather than
into nothing:**

| What stage 5 wanted | Why it was refused | Where the need went |
|---|---|---|
| **`devman move <project> <path>`**, when S4's registry entry still named the old path | It is D8's forbidden second entry path wearing the clothes of a repair. The registry is derived (§9.3): the repository states where it is by being entered, and a command that writes a path makes the registry canonical for one field | nowhere — S4 measured that entering the shell already does it, in one command the developer was going to run anyway |
| **`doctor` reading `~/.config/systemd/user/*.timer`**, so it could report that observantic gained `maintain` and the timer does not know | The machine module would not hold the fact, but `doctor` would — and §8 says a schedule is the developer's, exactly as a hook is the repository's. A `doctor` that reads the developer's units has an opinion about what should be scheduled, which is §4's line from the other side | decision 6 below: the drift is real, one direction of it is loud, and the recipe says so |
| **a `previous_path` field in the registry entry**, so a move could be reported rather than inferred | It makes the registry hold history, and §9.3 says the registry is derived from what is true now. A derived store with memory is a store that can be wrong about the past | `metadata.jsonl`, which already records each run's log path as it was, and which S4 shows is exactly where a stale path is legible |

**And one thing stage 5 wanted that was not a machine option, and was still
refused for the same reason.** The nested-checkout fix (S3) could have *guessed*:
resolve the inner checkout's own root and treat it as the project. It refuses
instead, because guessing which checkout a developer meant is identity inferred
from the filesystem, which is §9.1's first sentence.

### Decision 6 — the timer stays as it is, and stage 5 made its drift visible

**Answer: it stays.** `devman-maintain.timer` remains hand-written in
`~/.config/systemd/user/`, with one `ExecStart` line per project. devman ships no
timer, no option and no command, and `doctor` learns nothing about it.

**The drift is real and this stage caused an instance of it.** S5 gave
observantic the `base` group, so it now projects `maintain`, and the timer's five
lines do not include it. Nothing said so.

**The two directions are not equally silent, and that is what decides it.**

| Drift | What happens | Loud? |
|---|---|---|
| a project is renamed, or leaves the plane, while a timer line names it | `devman run maintain --project X` exits **1**, and the unit records the failure | **yes** |
| a project gains `maintain` and no line names it | nothing happens, ever | **no** |

**Evidence — the loud direction, measured:**

```
$ devman run maintain --project pyjutsu-renamed
devman: no project named 'pyjutsu-renamed' in /home/andrew/.local/share/devman
devman:  registered: devman, nix-paseo, observantic, pydantree, pyjutsu, siteman
devman:  a repository joins by entering its shell once (§5.2)          exit 1
```

That is the property S2 of stage 4 chose the local trigger *for*: a schedule that
cannot be resolved gets a non-zero exit and a message naming what is missing,
instead of a successful run in a garbage directory. A `systemd` timer whose
service exits non-zero is visible in `systemctl --user list-units --failed` and
in the journal.

**The silent direction is a gap in the recipe, not in the plane.** The remedy is
one line in a file the developer owns, and the alternative — the machine
enumerating which projects take which group — is the machine holding a project
fact (§4). `groups/base/README.md` now says it in the recipe, beside the timer:
**a project that gains `base` gains `maintain`, and the timer does not notice.**

**And the one-line change this session did not make.** Adding observantic to
`~/.config/systemd/user/devman-maintain.service` is the developer's, by §8's own
rule, so it is in the handover (S11) rather than applied here.

**Charter impact:** **none** for any of the three. §8, §9.3 and §4 all stand
unamended, and the entries above are the record of what they cost when they were
tested.

---

## S10 — Stage 5 against §14, criterion by criterion

Run against the installed service, **6 projects and 36 DAGs** — 33 at the start
of the stage, and 39 at its widest, with two throwaway checkouts registered.
Compare stage 4's S12.

| # | Criterion | Result |
|---|---|---|
| 1 | one flake, two interfaces, one version | **holds, re-measured.** `nix build .#checks.x86_64-linux.groups-validate` and `.dagu-service` both exit 0 with stage 5's four fixes in the tree, including the changed `modules/devenv.nix` |
| 2 | a repo adopts in three lines | **holds** — `observantic` took `base` by adding one word to `groups` and two task aliases (S5) |
| 3 | a repo may take no groups | **holds** — unchanged |
| 4 | a repo may rename or replace every default | **holds, and stage 5 found its edge.** Nothing reserves a workflow name — and S6 measured what happens when a *name* two projects render collides. The plane now refuses rather than running the wrong file, and it still does not police what a name means |
| 5 | shadowing is exact | **holds** — `doctor` still reports siteman's `full-test` keeping 7 of 9 executable lines; observantic's `python` shadowing `base` was re-derived from scratch when it took the new group (S5) |
| 6 | a workflow is portable Dagu | **holds, further.** `review` and `maintain` ran unedited in `observantic`, a sixth repository whose task names are `python:*` (S5), and unedited in a repository that had been moved and renamed (S4) |
| 7 | devenv stays on the fast path | **holds, and the added work is measured rather than assumed.** Stage 5 changed the hook for the first time since stage 3: one `[ -L ]` per projected workflow, **0.13 ms mean per firing** (0.088–0.188 over five repeats of 200), so about 0.26 ms per entry against a 10 ms budget, and it forks nothing (S7). **The paired delta itself was not re-run**; stage 3's figure of -0.17 ms, 95% CI [-6.24, +5.91], still stands as the last one |
| 8 | registration is automatic and idempotent | **holds, re-measured.** Two `devenv shell -- true` in a row: `metadata.json` mtime `20:21:57.488514227` before and after — the second entry wrote nothing |
| 9 | only opted-in repos register | **holds** — unchanged. Both throwaway checkouts registered by declaring `devman.enable`, and both left by being deleted and pruned |
| 10 | no workflow contains an absolute path | **holds, re-measured.** `grep -rn '/home/\|/nix/store\|/run/\|/etc/' groups/*/workflows/*.yaml .devman/workflows/*.yaml` → **zero hits** |
| 11 | **identity survives a move or a rename** | **holds, re-run by command for the first time since stage 1** — and against a repository with 5 recorded runs, 4 reports and a live projection instead of a throwaway (S4). Moved and renamed in one `mv`, re-entered, entry replaced not duplicated, projection rebuilt, both halves of the history intact, `devman run review` ran in the new location |
| 12 | queues are real | **holds** — unchanged, not re-measured. Nothing in stage 5 changes what a queue does; stage 4's paired `bench-entry` runs on `exclusive` are the last measurement |
| 13 | the watchers do not chase each other | **holds, re-measured.** One save of a badly-formatted file: **2 dispatches, 2 runs** — the first formatted it, the second logged `Preconditions failed for "format"` and did nothing, and the sequence stopped. The last clause ("edit again immediately") was not re-run; stage 3's S6 measured it four ways |
| 14 | the task graph exists once | **holds** — stage 5 shipped no workflow. `observantic`'s two aliases are devenv `after` edges onto tasks it already had, which states no order the group restates |
| 15 | a rebuild is inconvenient, not catastrophic | **holds for total loss; it did NOT hold for partial loss, and the fix is committed** (S7). Deleting all of `dags/` and re-entering restored **10 of 36** links, because the five repositories still pinned to `main@df9cfe5` have the old guard. The documented remedy works for them today — delete the entry as well, re-enter, and the projection is rebuilt: measured, all five, 36 of 36 restored. `siteman` is re-pinned to the fixed rev and re-verified by removing one link |
| 16 | devman adopts itself | **holds, and it took the sharpest edge.** A second checkout of this repository is what produced S3's silent wrong-tree run and S6's colliding DAG name. Both were found because devman is a project like any other |
| 17 | **there is one way in** | **holds, and stage 5 is the stage that most wanted to break it.** Three routes into the registry were wanted and refused (S9, decision 5). `grep` over `src/devman/` still finds no writer of `projects/<p>/metadata.json` — `Registry.unproject` only `unlink`s, under `doctor --prune`. Every repair in this stage was "enter the shell", and the one that could not be — a missing `dags/` link — was fixed by making the *shell entry* notice, not by adding a command |

### Criterion 15, in the state stage 5 leaves it

This is the one to read twice, because it is the only criterion whose answer
changed mid-stage.

- **Total loss** — delete `~/.local/share/devman/` — was measured at stage 2 (S13,
  eight projects, byte-for-byte) and is unaffected.
- **Partial loss** — delete one `dags/` link — was **not** repaired by the
  remedy §9.3 names, on any repository, until S7's fix.
- **Today**: repositories on `main@ecd6662` or later repair themselves on the
  next shell entry. Repositories still on `main@df9cfe5` need their entry deleted
  as well, which is the same command list one step longer, and which restored all
  five here.

### The five criteria S1 promised to re-run by command

D6 named 11, 8, 13, 15 and 17. **All five were run rather than reasoned about**,
and the table above quotes the command or the number for each. Criterion 7 was
re-measured in the narrow sense that matters — the work stage 5 added to the hook
— and not in the paired sense, which is stated rather than glossed.
