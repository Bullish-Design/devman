# STAGE 6 — what was measured while putting the schedule in the file

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules,
`STAGE_2_LOG.md` what stage 2 found while turning the plane on, `STAGE_3_LOG.md`
what stage 3 found while making it react, `STAGE_4_LOG.md` what stage 4 found
while giving it work worth doing, and `STAGE_5_LOG.md` what stage 5 found while
moving the repositories underneath it. This holds stage 6, in the same shape:
the answer, the versions, the exact command, the evidence, and the charter
impact.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, `systemd --user` unit `dagu` |
| devenv | 2.1.2 |
| devman | 0.3.0, `/run/current-system/sw/bin/devman` — the installed build predates stage 5's fixes |
| watchexec | 2.5.1, `systemd --user` unit `devman-watch` |
| Registry | `~/.local/share/devman/` — 6 projects, 36 workflows, 36 DAG links |
| Timer | `devman-maintain.timer`, enabled, daily, five hand-written `ExecStart` lines |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5`, at `d215e12` |

---

## S1 — What "done" means for stage 6, written before anything was built

**Why this entry exists.** §13's rollout ended at stage 4 and stage 5 wrote its
own definition of done. This is the second stage to do that, and the first whose
subject was set by the owner rather than by a shortlist: **a developer must not
have to remember to change anything outside the repository for automation to
work as declared.**

**What made it possible** is `STAGE_5_LOG.md` S12, measured at the owner's
prompting: Dagu's own scheduler resolves everything correctly when the
**projected file carries the values**. Stage 4's S2 had concluded that Dagu's
scheduler "cannot trigger anything this plane projects", and that conclusion was
true of the projection shape devman chose — a symlink to one shared group file
whose `working_dir` and `log_dir` interpolate from whoever enqueues — rather
than of Dagu.

### What stage 6 is, in one sentence

> **Stage 6 moves the schedule into the workflow file.** The projection stops
> being a symlink and becomes a small generated file that states the project's
> own `working_dir`, `log_dir` and directory parameter, so `schedule:` — Dagu's
> own key, in the workflow's own YAML — is fired by Dagu's own scheduler, and
> `devman-maintain.timer` is retired.

**And what it is not.** It is not a new trigger mechanism: `devman run`, the
watcher and VCS hooks are unchanged, and no new command, global name, queue or
registry field appears. The schedule is content, exactly as the queue name is.

### The ten conditions

**D1 — The projection materialises, and every workflow still loads and still
runs.** All 36 projected files pass `dagu validate` through `devman doctor`, and
at least one workflow per **home** (§7.3's three: a group everyone takes, a
group taken by name, a repository's own `.devman/workflows/`) is run through the
plane afterwards, with its `metadata.jsonl` line quoted.

**D2 — One real scheduled run, fired by Dagu, in a real repository.** Not a
throwaway instance and not `systemd-run`: the installed `dagu` daemon, a
registered repository, a `schedule:` line in a group file, and the evidence is
the daemon's own dispatch log plus the project's `metadata.jsonl` line plus the
log tree under that project. **A schedule that has not fired is not delivered.**

**D3 — The generated header is auditable, and it is the smallest thing that
works.** It states only what a trigger states today — the directory parameter,
`working_dir` and `log_dir` — and it never edits a workflow's steps. Two rules
it must keep, both measured before the projection is changed:

1. **A cross-repo workflow (§11) must not gain `DEVMAN_PROJECT_DIR`.** The
   header supplies `DEVMAN_SELF_DIR` there instead, and `doctor`'s §11 check is
   what proves it.
2. **A body that already states a field keeps its own.** The header adds, it
   does not overwrite.

**D4 — The timer is retired only after the schedule is proved**, and retiring it
is the developer's own act on their own file (§8). This log states the exact
command and the order.

**D5 — Every criterion that holds must still hold, measured rather than
asserted.** A criterion-by-criterion table against §14. **Six are re-run by
command**, because materialising the projection pressures them hardest:

| # | Why stage 6 pressures it |
|---|---|
| 5 | shadowing is exact — a generated file must still be diffable against the group version it shadows |
| 6 | a workflow is portable Dagu — the header is per project, so the *body* must stay unedited |
| 7 | the hook now **writes files** where it wrote symlinks. The added cost is measured, with a spread |
| 10 | no workflow contains an absolute path — the source files must stay clean while the projection holds one by construction |
| 13 | the watchers do not chase each other — a scheduled run writes into a watched tree while nobody is at the keyboard |
| 17 | there is one way in — a projection that generates files must still be derived from repositories and nothing else |

**D6 — What this costs is stated, not discovered later.** `STAGE_5_LOG.md` S12
names the loss in advance: a repository's own `.devman/workflows/x.yaml` stops
being live-edited, because Dagu reads a generated copy rather than a symlink to
it. This log states the remedy (`devenv shell -- true`), measures how long it
takes, and says plainly whether it is acceptable.

**D7 — Whatever a schedule inherits, a repository can refuse.** A `schedule:` in
a group file reaches every repository that takes the group. That is the same
promotion rule §16 already applies to the file itself, and the escape hatches are
§7.3's — do not take the group, or shadow the file whole. The entry that adds the
first schedule states which repositories it starts running work in, by name.

**D8 — Nothing gives the registry a second entry path.** Unchanged since stage 1
and the rule that outranks the rest. A generated projection is derived state,
like the symlinks it replaces; if generating it appears to need a fact no
repository stated, this log says so before the code is written.

**D9 — The charter changes only in its own commit, and the log entry comes
first.** Stage 6 is expected to move **three** sections — §7.2's "devman never
parses a workflow", §8's third trigger arrow, and §9.2's projection layout — and
each one waits for the measurement that forces it.

**D10 — The machine is left as it was found, and every touched repository is
named.** `devman doctor` back to `Nothing to report`, no throwaway in the
registry, every repository at a stated commit, and a machine change proposed and
handed over rather than activated.

### What this deliberately does not promise

- **Not a schedule for every repository.** The first one is `maintain`, because
  it is what the retired timer already ran and because its work is bounded and
  its output is a report. A scheduled workflow that rewrites source files is the
  case §8 warns about for reactivity, and stage 6 does not ship one.
- **Not catch-up after downtime.** Dagu's scheduler fires on a cron expression;
  a machine that was asleep at the appointed minute missed that minute. Whether
  the plane should notice is a question this stage records rather than answers.
- **Not a change to how anything else is triggered.** The watcher, the hook and
  `devman run` are untouched, and the refusals in `src/devman/run.py` still
  govern every path a person or a service takes.
- **Not §9.4's first use.** Nothing here publishes or needs a value outside
  `$HOME`, so stage 4's S7 decision stands for a third stage.

**Charter impact:** **none.** This entry is stage 6's own definition of done.

---

## S2 — The header, measured before the projection was changed

**Answer:** the generated header is **four lines and purely additive**, and the
shape was decided by measurement rather than by preference:

```yaml
env:
  - DEVMAN_PROJECT_DIR: /home/andrew/project      # or DEVMAN_SELF_DIR (§11)
working_dir: /home/andrew/project
log_dir: /home/andrew/project/.devman/.runs/logs
```

**`env:` rather than `params:`, and that is the whole finding.** `STAGE_5_LOG.md`
S12 proved a *params* header works, but three shipped workflows already declare
a `params:` block — `maintain`, `agent-review` and `bench-entry` — so a params
header would have to **edit** a block the workflow owns. An `env:` header only
prepends.

**Tested:** Dagu 2.15.0 on a throwaway `DAGU_HOME=/tmp/s6-env`, ports 8093 and
50068, carrying a byte copy of the installed plane's `base.yaml`, with two DAGs
differing only in the dangerous part.

**Command:**

```yaml
# A — env only
env:
  - DEVMAN_PROJECT_DIR: /tmp/s6-proj
working_dir: /tmp/s6-proj
log_dir: /tmp/s6-proj/.devman/.runs/logs

# B — the same header, plus a params block that leaves the SAME NAME empty,
#     which is exactly what groups/base/workflows/maintain.yaml declares
params:
  - DEVMAN_PROJECT_DIR: ""
  - KEEP_DAYS: "7"
```

**Evidence — six scheduled dispatches, three of each:**

```
A cwd=/tmp/s6-proj PROJ=[/tmp/s6-proj]
B cwd=/tmp/s6-proj PROJ=[/tmp/s6-proj] KEEP=[7]
```

**`env:` outranks an empty `params:` default, and the workflow's other
parameters keep theirs.** That is what makes the header additive: it never has
to touch a `params:` block, so a workflow that declares parameters and one that
declares none are projected the same way.

**Evidence — and the machine's inherited exit handler still recorded every
run**, which is the half S2-of-stage-4 lost:

```
$ cat /tmp/s6-proj/.devman/.runs/metadata.jsonl
{"dag":"envparam", … "status":"succeeded", …}
{"dag":"envonly",  … "status":"succeeded", …}
… six lines, three each …
```

### The two rules the header keeps, and why they are rules

**1. A cross-repo workflow gets `DEVMAN_SELF_DIR`, never `DEVMAN_PROJECT_DIR`.**
§11 is explicit: a workflow that triggers other workflows must not hold the name
it passes to its children, because a parent's environment outranks every child's
own value. The projection detects it the same way `doctor` does — the file
mentions `DEVMAN_SELF_DIR` — and `doctor`'s §11 check is what proves the result:

```
$ head -5 ~/.local/share/devman/projects/devman/workflows/stack-validate.yaml
# devman: generated projection — do not edit.
# Edit the source and re-enter the shell:
#   …/.devman/workflows/stack-validate.yaml
env:
  - DEVMAN_SELF_DIR: /home/andrew/.paseo/worktrees/1n48r26y/special-dragon

$ devman doctor
ok  cross-repo     1 workflows trigger others, all name DEVMAN_SELF_DIR
```

**2. A body that states a field keeps its own.** `stack-validate` declares its
own `working_dir` and `log_dir` (§11 requires it, because the inherited ones name
`DEVMAN_PROJECT_DIR`), and the header adds neither. The same guard covers a body
with its own `env:`, which no shipped workflow has: the header steps aside, and
that file must then state the variable itself.

**Charter impact:** **none yet.** The projection had not changed when this was
measured. §7.2, §8 and §9.2 move in S4, after the real plane proved it.

---

## S3 — A scheduled run on the installed plane, fired by Dagu, with nobody triggering it

**Answer:** **it works.** `groups/base/workflows/maintain.yaml` gained
`schedule:`, this repository re-projected, and the installed daemon dispatched
the workflow, ran it in the right directory, wrote its report and appended to
`metadata.jsonl` — with no timer, no `devman run`, and no process of mine
involved.

**Tested:** the installed service. Dagu 2.15.0, `systemd --user` unit `dagu`,
devman 0.3.0 from the closure the user activated between stage 5 and stage 6
(`/nix/store/7ql2i1j…`, so stage 5's `projection` and `handlers` checks are live).

**Command** — the schedule was temporarily set to every minute, so that a
measurement did not have to wait until 00:05, then set back:

```bash
sed -i 's|^schedule: "5 0 \* \* \*"|schedule: "* * * * *"|' groups/base/workflows/maintain.yaml
rm -f .devenv/nix-eval-cache.db*        # a group file inside a path: input (S7, stage 3)
devenv shell -- true                    # the only way a projection is ever rebuilt
```

**Evidence — the daemon's own scheduler:**

```
$ journalctl --user -u dagu
22:56:01 INFO msg="Dispatching planned run" dag=devman-maintain scheduleType=Start
                                            scheduledTime=2026-08-22T22:56:00-04:00
22:57:00 INFO msg="Dispatching planned run" dag=devman-maintain scheduleType=Start
```

**Evidence — Dagu says who triggered it, and it was not a person:**

```
$ curl -s .../api/v1/dags/devman-maintain/dag-runs
034BuHL9m0vVSMlfnlSJjM  status 4  trigger: scheduler
034BuFr2nmmgjDSo24aook  status 4  trigger: scheduler
034BpAE5ko4TCqewEc1w2O  status 2  trigger: manual      <- an earlier run of mine
```

**Evidence — where the work happened, and what it left:**

```
$ tail -2 .devman/.runs/metadata.jsonl
devman-maintain 034BuFr2nmmgjDSo24aook succeeded
   log: /home/andrew/.paseo/worktrees/…/special-dragon/.devman/.runs/logs/devman-maintain/…
devman-maintain 034BuHL9m0vVSMlfnlSJjM succeeded

$ head .devman/.runs/reports/maintain-034BuHL9m0vVSMlfnlSJjM.md
# maintain — devman-maintain
- run id: `034BuHL9m0vVSMlfnlSJjM`
- started: 2026-08-23T02:57:00Z
- keep days: 7                          <- the param default, with no trigger to pass it
## this project
- reports: 14 before, 14 after — 0 pruned
- artifacts: 1 entries, **never pruned here** — remove them by hand
```

**Every one of stage 4's S2 failures is absent, on the real machine**: the run
worked in the project rather than in a directory named `${DEVMAN_PROJECT_DIR}`,
the logs landed under the project, the machine's exit handler resolved its
fallback and appended the record, and `KEEP_DAYS` took the default the workflow
states.

### The thing that nearly became a wrong conclusion

**The first three minutes produced nothing**, and the tempting reading was "the
scheduler builds its cron table at start-up, so every adoption needs a daemon
restart" — which would have put back exactly the manual step this stage exists to
remove. A restart did make it fire immediately, which *fits* that reading.

**It is not the explanation, and one more probe separated them.** Two further
measurements, each on the installed plane:

| Probe | Result |
|---|---|
| **change** an existing schedule (`* * * * *` → `5 0 * * *`), no restart | firing stopped **within one minute**, and stayed stopped for six |
| **add a whole new scheduled DAG** — `.devman/workflows/_s6-sched.yaml`, projected by an ordinary shell entry, no restart | dispatched **on the next minute boundary**, three minutes in a row, `trigger: scheduler` each time |

```
$ cat .devman/.runs/logs/devman-_s6-sched/…/tick….out
scheduled tick in /home/andrew/.paseo/worktrees/1n48r26y/special-dragon at 23:07:00
scheduled tick in /home/andrew/.paseo/worktrees/1n48r26y/special-dragon at 23:08:00
```

**So the case that matters for the promise — a repository adopting a scheduled
workflow — needs no restart, and neither does removing one.** What was measured
once, and not explained, is a DAG the daemon already knew **without** a schedule
that then gained one: three scheduled minutes passed with nothing, and a restart
cured it. That is the *transition* this stage causes, not the steady state, and
the handover states it as one restart rather than as a rule.

**Rule 1 of the prompt series says to report what happened.** The three-minute
silence is recorded here rather than tidied away, together with the fact that the
mechanism behind it is **not known** — only that it does not affect adoption,
removal, or a changed expression.

**Cleanup:** the probe workflow was deleted and re-projected; `dags/` holds no
`_s6-sched` link, and the next minute produced no dispatch.

**Charter impact:** **none yet.** S4 applies the three sections this forces.
