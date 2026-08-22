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
