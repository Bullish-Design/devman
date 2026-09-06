# Kickoff — Stage 5, the first stage the charter does not name

## Your task

Build stage 5 of the devman automation plane. **`CONCEPT.md` §13 does not
define it.** Its rollout ends at stage 4, and stage 4 is shipped: six
deliverables, all files, running against six real repositories on this machine.

So your first job is not to build. **It is to decide what stage 5 is, write that
down as `STAGE_5_LOG.md` S1 before you build anything, and be judged against
what you wrote.** §6 below gives you the shortlist stage 4 left, the strongest
candidate, and the shape the answer has to take.

Stage 1 shipped both module interfaces. Stage 2 turned the plane on and adopted
five real repositories. Stage 3 made the plane react and built the CLI. Stage 4
gave the plane work worth doing — and, because that was the first stage whose
output a person acts on, it found three things three stages of green runs had
hidden.

Work in the git worktree described in §4. Commit each piece as it works.

---

## 1. The one rule that keeps this session useful

> **Stage 4 proved the plane by running it, and every one of its three real
> defects was invisible to `nix flake check`, to `dagu validate`, and to
> reasoning. Do not diagnose from a symptom that two hypotheses explain. Build
> the probe that separates them, or you will fix the wrong thing and ship it.**

That is not a generality. It is stage 4's most expensive hour, recorded in
`STAGE_4_LOG.md` S13:

- A benchmark step failed with `EPOCHREALTIME: parameter not set`. Two
  hypotheses explained it — the *daemon* inherits the developer's login shell,
  or the *trigger* passes it. S9 tested only the first, "fixed" the NixOS
  module, and cost the user a `nixos-rebuild switch` that changed nothing.
- The probe that settled it took four minutes: run the same workflow three
  times, changing only `$SHELL` in the caller. The trigger decided every time.
- S9's own probe **could not have found this**. It used `dagu start`, where the
  triggering process and the executing process are the same one.

The same rule with a different face, from S14: `devman doctor` called a queue
with one waiting item a fault, and had done since stage 3. Nothing noticed until
stage 4 gave the machine enough work for two runs to be in flight at once.

**Stages 1–4's code runs, on this machine, against six real projects. Do not
rewrite it because you would have written it differently.** Several pieces exist
because someone tried the obvious thing first and it silently did not work. If a
line looks needlessly indirect — the flat `dags/` directory, `builtins.readFile`,
the `-v` on every group step, the `--project-origin` on watchexec, the
`env.pop("SHELL")` in `run.py`, the `continue_on` in `review.yaml` — **read the
log entry before you simplify it.**

---

## 2. Read these first

1. `.scratch/projects/006-automation-plane/STAGE_4_LOG.md` — **start here.** It
   held fourteen entries, S1–S14, when this prompt was written. **Read all of
   it, however far it now runs.** S1 is stage 4's definition of done and the
   model for yours. S2 and S3 changed the charter. S12 is the criterion-by-
   criterion table and the six decisions. **S13 and S14 are the two you must
   read before you touch anything**, for the reason §1 gives.
2. `.scratch/projects/006-automation-plane/CONCEPT.md` — the specification.
   **It has been amended eight times**; the status block says where and why.
   Re-read §2 (what devman is — a closed list of three), §4 (what the machine
   never knows), §6 (Dagu composes, devenv executes), §7 (the contract, four
   names, closed), §8 (triggers, amended three times), **§9.1 (identity — and
   the promise in it that nothing has ever tested)**, §9.2, **§9.4 (secrets —
   specified, and still never used after four stages)**, §11, §14, §15, §16.
3. `.scratch/projects/006-automation-plane/STAGE_3_LOG.md` — S11 states stage
   3's four decisions, S12 is its criteria table, S16 and S18 are about the
   watcher and are the two most likely to matter to you.
4. `STAGE_2_LOG.md` and `STAGE_1_LOG.md` — skim. Stage 1's S1, S2, S7 and S8
   explain four things in the code that look wrong.
5. `.scratch/projects/006-automation-plane/FINDINGS.md` — **do not read it end
   to end; it is 5,871 lines.** Read the final section, "Reconciliation input —
   every charter change, by section", then whatever it points you at. **E3
   (secrets) is the one stage 5 most likely needs**, and A7 and E8 are what
   close every alternative to §9.1's registry.
6. The code, and the group READMEs. `groups/base/README.md` and
   `groups/release/README.md` are where a repository is told how to use each
   group, and both now carry stage-4 recipes — the timer, the gate, and what
   the gate cannot check.

---

## 3. What stages 1–4 settled, so you do not re-derive it

| Question | Answer | Where |
|---|---|---|
| §7.1's global names | **four**, and the list is closed. It grew once, under a measurement | `STAGE_2_LOG.md` S12 |
| §10's commands | **four** — `run`, `show`, `doctor`, `watch`. `watch` is systemd's entry point, not a person's | `STAGE_3_LOG.md` S11 |
| §7.4's repo interface | **three keys** — `enable`, `project`, `groups` | §7.4 |
| Where a glob-to-workflow mapping lives | `groups/<group>/triggers.toml`, resolved at evaluation time. **Reactivity is its own group** | `STAGE_3_LOG.md` S4 |
| Whether `devman run` resolves cross-repo parameters | **Yes** — a declared parameter whose *default* names a registered project is filled with that project's path. The name is not a contract; the value is | `STAGE_3_LOG.md` S3 |
| VCS hooks | the repository's own `git-hooks.hooks.*` running `devman run`. devman supplies no option | `STAGE_3_LOG.md` S9 |
| **Schedules** | **a systemd user timer running `devman run --project <name>`.** Dagu's `schedule:` cannot trigger anything this plane projects | `STAGE_4_LOG.md` S2, S6 |
| Whole-file shadowing | **closed by the owner.** A repository that must change a default writes a whole workflow file of its own | `STAGE_3_LOG.md` S14 |
| Whether stage 4 needed a secret | **No.** Everything ran under the developer's own `$HOME`, git credentials and SSH agent (§4) | `STAGE_4_LOG.md` S7 |

> **Three closures stage 5 must not reopen.** §12.4's whole-file shadowing is
> closed by decision. §10's command list is closed at four. §7.1's name list is
> closed at four. Each may still grow — but only the way the fourth name grew:
> **a real run failed first, and the log entry recording it was written before
> the commit.**

### The seventeen criteria, as stage 4 left them

**All seventeen hold** (`STAGE_4_LOG.md`, S12), measured against the installed
service, six real projects and 34 DAGs. 1, 10, 12, 13 and 17 were re-run by
command rather than reasoned about. Two carry a caveat you inherit:

| # | Criterion | State stage 5 inherits |
|---|---|---|
| 7 | devenv stays on the fast path | **holds, not re-measured since stage 3.** The last paired figure is -0.17 ms, 95% CI [-6.24, +5.91], against a 10 ms budget (`STAGE_3_LOG.md` S15). `.devman/workflows/bench-entry.yaml` now exists as the harness for the absolute half |
| 11 | identity survives a move or a rename | **holds, and has not been tested since stage 2.** See §6 — it is the criterion the strongest stage-5 candidate exists to attack |

---

## 4. Where you are — read this before you open a file

Every value below was checked on 2026-08-22, after the user's second
`nixos-rebuild switch` of that day. **Check them again**; other sessions were
working in this repository while this was written.

| Fact | Value |
|---|---|
| Working directory | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| Branch | `dagu-devenv-automation-eli5`. `origin/main` and the branch are pushed together and sit on the same commit |
| Host | NixOS 26.11.20260705.d407951 (Zokor), hostname `server`, Nix 2.34.7 |
| devenv | **2.1.2**, at `~/.nix-profile/bin/devenv`. It prints an out-of-date notice for 2.2.2 on every entry; 2.2.0 differs in one measured way (`STAGE_2_LOG.md` S4) |
| Dagu | **2.15.0**, `systemd --user` unit `dagu`, ports 8080 and 50055 |
| devman | **0.3.0**, at `/run/current-system/sw/bin/devman` — `run`, `show`, `doctor`, `watch` |
| watchexec | **2.5.1**, `systemd --user` unit `devman-watch` |
| Queues | `light` 4, `normal` 2, `heavy` 1, **`gpu` 1 — still named by no workflow**, `exclusive` 1 |
| Registry | `~/.local/share/devman/` — **6 projects, 34 DAGs** |
| Groups | **four**: `base`, `python`, `python-format`, `release` |
| **Timer** | **`devman-maintain.timer`, enabled, daily, in `~/.config/systemd/user/`** — five `ExecStart` lines, one per project taking `base` |
| home-manager | `/home/andrew/Documents/Projects/nix-meta`, `profiles/devman.nix` is the leaf, `flake.nix` holds the pin |

### Talking to the running plane

A non-login shell has neither `DAGU_HOME` nor a session bus. Both are needed:

```bash
export DAGU_HOME=$HOME/.local/share/dagu
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
systemctl --user status dagu devman-watch
systemctl --user list-timers devman-maintain.timer
dagu ls
```

**That is right for a person at a prompt and wrong for a program.** `devman run`
states `--dagu-home` rather than inheriting it, and clears `SHELL` rather than
passing it on, for the reasons in facts 3 and 4 below.

### The six registered projects, and what each one now has

Built from `~/.local/share/devman/projects/`, not copied forward.

| Project | Groups | Workflows |
|---|---|---|
| `devman` | `base`, `python-format`, `release` | check, validate, full-test, format, **review, maintain, release**, plus its own `stack-validate`, **`agent-review`** and **`bench-entry`** |
| `siteman` | `base` | check, validate, **review**, **maintain**, and its own `full-test` override |
| `pyjutsu` | `base` | check, validate, full-test, **review**, **maintain** |
| `nix-paseo` | `base` | check, validate, full-test, **review**, **maintain** |
| `pydantree` | `base`, `python` | check, validate, full-test, **review**, **maintain** |
| `observantic` | `python`, `release` | check, validate, **release** — **and no `review` and no `maintain`**, because it does not take `base` |

**observantic's gap is real and it is §16's promotion rule asking a question.**
`review` and `maintain` reach five of six projects only because five take
`base`. Whether they should also live in `python`, or whether observantic should
take `base`, is a decision nobody has made — see §7.

**pydantree's `check` fails, and that is correct.** It is the repository's own
debt — 920 ruff findings (`STAGE_2_LOG.md` S10) — and the only failing workflow
you have. Do not fix it to make a demo green.

### What `devman doctor` reports today

Eleven checks, all `ok`, exit 0, `Nothing to report.` The three that will matter
to you:

```
ok  queues         5 queues, 0 running, none waiting
ok  shadowing      devman/agent-review: invented — no group version to diff
                   devman/bench-entry:  invented — no group version to diff
                   devman/stack-validate: invented — no group version to diff
                   siteman/full-test: shadows base — 7 of 9 executable lines unchanged
ok  watcher        devman: **/*.py -> format  [python-format]
```

**Run `devman doctor` before you start and after every change.** It is the one
thing in this design allowed to tell the developer something (§5.2), and stage 4
found it wrong once (S14).

---

## 5. Twelve facts that will bite you if you rediscover them

S-numbers with no stage are `STAGE_4_LOG.md`; letters are `FINDINGS.md`.

**1. Dagu's own scheduler cannot trigger anything this plane projects.** Under
`schedule:` the daemon enqueues, so `log_dir` **and** `working_dir` both stay
literal: the run works inside a directory named `${DEVMAN_PROJECT_DIR}` in the
daemon's cwd — `$HOME` on this machine — and then `base.yaml`'s exit handler
fails and takes the run down. §8's third arrow is a **systemd user timer running
`devman run --project <name>`**, and one is installed. (S2, S6)

**2. `dagu dry` writes.** It documents itself as a simulation "without producing
any side effects" and it **creates `log_dir`**. **No devman command may call
it.** (`STAGE_3_LOG.md` S1)

**3. An unset `DAGU_HOME` builds a second Dagu** — `~/.config/dagu/`, its own
`base.yaml`, five seeded example DAGs, and no knowledge of the registry.
`skip_examples` is per instance, so the plane's config cannot protect it. A
trigger must **state** its target. (`STAGE_3_LOG.md` S2)

**4. THREE things are baked from the environment of the process that ENQUEUES:
`log_dir`, `$SHELL`, and the exported directory variable.** Not the daemon's,
not the executor's — the trigger's. `devman run` therefore exports
`DEVMAN_PROJECT_DIR`, passes it as a parameter, and **clears `SHELL`** so that
`config.yaml`'s `default_shell` governs. Setting `SHELL` on the Dagu unit
instead does nothing for any run the plane makes, and one commit tried it. (S13,
A3, A7)

**5. `devman run` refuses a declared parameter that would have no value**, a
directory variable that is empty or not a directory, a workflow that fails to
load, a cross-repo parent that holds `DEVMAN_PROJECT_DIR`, and a cross-repo
parent that declares no `DEVMAN_SELF_DIR`. Read `src/devman/run.py:95-125`
before you write a workflow that takes an argument. **A free-text parameter with
an empty default is refused at the trigger** — which is why `agent-review`'s
prompt has a real default. (`STAGE_3_LOG.md` S3, S7)

**6. A workflow that declares ONE parameter must declare EVERY parameter it will
be given.** Dagu rejects an undeclared one at load time, and `devman run` always
passes the directory variable. Declare none, or declare `DEVMAN_PROJECT_DIR`
first. It is loud, not silent. (S3)

**7. A workflow that defines its own `handler_on` silently stops recording its
runs.** `base.yaml` is inherited whole-field, so such a DAG replaces the
machine's exit handler: the run succeeds, the logs land correctly, `dagu status`
is clean, and `metadata.jsonl` gains no line. **Nothing checks this**, and §9.2
now warns about it in prose only. (S3)

**8. There are two loops, and a workflow can break only one.** A workflow's
`preconditions:` break the loop the workflow causes. **The watcher's ignore list
breaks the loop the plane causes** — every run creates a log directory inside
the project. With one ignore removed, one save produced **107 dispatches and 60
runs in 45 seconds**. A group's glob is the first filter and the more important
one. (`STAGE_3_LOG.md` S8)

**9. The watcher reads its watch *set* at service start, and re-reads the
registry every five seconds** to replace its watchexec child. It must never
restart its own unit: `systemctl --user restart` from inside a unit does not
return, and systemd does not count such a restart, so `startLimitBurst` will not
stop the loop. watchexec also needs `--project-origin`, or one watcher over
several repositories walks their common ancestor and **spins a core at 99.4%
while firing nothing**. (`STAGE_3_LOG.md` S5, S16)

**10. A second watcher is invisible and looks exactly like a loop.** A
hand-started `devman watch` killed at the shell leaves an orphaned watchexec
reparented to init, still dispatching, surviving a rebuild. `doctor` counts them
from `/proc` now. (`STAGE_3_LOG.md` S18)

**11. `devenv tasks run` captures a task's stdout and never prints it**, success
and failure alike. Every group step therefore passes `-v`. It is load-bearing.
**`devenv test` loses BOTH streams**, with `-v` or without, so it works as a gate
and never explains itself. (`STAGE_2_LOG.md` S4)

**12. Never `git add -A` in a repository a workflow writes into.** A literally
named `${DEVMAN_PROJECT_DIR}` directory has already been committed to this
repository once. The ignore rule does not cover it, deliberately: it is the
visible symptom of a broken trigger. (`STAGE_2_LOG.md` S15)

**And one that is not a hazard but will save you an hour.** A group file inside a
`path:` flake input is invisible to devenv's evaluation cache — editing it
changes nothing, `devenv update` does not help, and deleting
`.devenv/nix-eval-cache.db*` does. A repository importing `./modules` locally
(this one) is in the tracked case; a throwaway built to test a group is not.
(`STAGE_3_LOG.md` S7)

---

## 6. What stage 5 is, and how to decide it

**§13's rollout ends at stage 4.** There is no list to work from and no
stage-5-only criterion in §14. You are in the position stage 4 was in, one step
further out: stage 4 at least had six words from §13.

**So write `STAGE_5_LOG.md` S1 first**, before you build anything, in the shape
of `STAGE_4_LOG.md` S1 — numbered conditions, each one checkable, plus an
explicit list of what it deliberately does not promise. Then be judged against
it.

### The shortlist stage 4 left, with what each is worth

| Candidate | What it would close | What it costs |
|---|---|---|
| **A second machine, or a second checkout** | §9.1 promises identity "makes moving a repo, a second machine, a second checkout, and a future remote worker all work". **Four stages and nothing has tested it.** Criterion 11 has not been re-run since stage 2 | a VM or a second user; the registry, the ports and the watcher have all only ever seen one of each |
| **Publishing a release** | `release` builds and stops. Publishing is the first thing that genuinely needs §9.4, which is specified and unused after four stages (S7) | irreversible actions, and a credential in a workflow a timer can fire with nobody watching |
| **`doctor` catches what stage 4 could only document** | fact 7 above: a workflow defining `handler_on` loses its run record silently. §9.2 warns in prose; nothing checks | one check, and the judgement about which other silent losses deserve one |
| **`review` and `maintain` for the repository that cannot have them** | observantic takes `python` and gets neither. §16's promotion rule has a question to answer | a group-layout decision that touches five repositories |
| **A campaign over every registered project** | `bench-entry` measures one target per run. Criterion 7's absolute half is still unmeasured since stage 3 | nothing structural — this is content |

**The strongest candidate is the first**, and the reason is not that it is
hardest. It is that **every other item on the list is something the plane does,
and that one is something the charter *claims*.** §9.1's whole design — identity
stated rather than defaulted, refusal when a path still exists, replacement when
it does not — exists to make a move, a second checkout and a second machine
work. Four stages have run against one checkout of each of six repositories on
one machine. §9.3's promise that "everything under `~/.local/share/devman/` is
reconstructable" has been exercised once, at stage 3, by pruning throwaways.

**But it is your decision, and a defensible smaller stage beats an
over-reaching one.** What S1 must say either way:

1. **What stage 5 is, in one sentence, and what it is not.**
2. **How you will know it is done**, as conditions somebody else could check.
3. **Which of §14's seventeen criteria your subject pressures**, and which of
   those you will re-run by command rather than reason about.
4. **What you will not do**, and why that is a choice rather than an omission.

### Three things any stage 5 must carry, whatever you choose

1. **Every criterion that holds must still hold, measured rather than asserted.**
2. **A workflow or a check that was written and never run is not delivered.**
   Each deliverable runs at least once, on the real plane, in a real repository,
   with its evidence quoted.
3. **Whatever you build must leave enough behind that a person can see what it
   did without re-running it.** That is stage 4's D6, and it does not expire.

---

## 7. The decisions this session must make, not defer

**1. What stage 5 is.** §6. This is the decision the others hang off, and it
belongs in S1 before any code.

**2. Whether §9.4 gets its first use, and what the module gains if it does.**
Stage 4 decided **no**, by measurement: every deliverable ran under the
developer's own `$HOME`, and the agent workflow authenticated with no secret
(S7). That decision has an explicit trigger written into it — a value that is
**not** in `$HOME`, which is what publishing needs. S7 also names the exact
shape: a `secrets:` block **in the workflow that needs it, never in
`base.yaml`**, `provider: env` rather than `provider: file` (E3), and **one**
module option — an `EnvironmentFile=` path on the Dagu unit, **never** an
`environment.X = value`, because a value in a NixOS module is a value in the
world-readable store. **If you publish anything, this decision is forced. If you
do not, say so and leave §9.4 alone.**

**3. Where `review` and `maintain` should live.** They are in `base`, which
reaches five of six. observantic takes `python` only and has neither, so the
repository that most looks like a library gets no review workflow. Three
answers, and §16's promotion rule is the test: put copies in `python`, have
observantic take `base` as well, or leave it and say why one repository's gap is
acceptable. **Deciding "leave it" is a decision; not noticing is not.**

**4. Whether `doctor` grows a check for a workflow that defines `handler_on`.**
Fact 7. It is a silent loss of the one record §9.2 promises survives everything.
`doctor` already reads workflow text for §11's `action: dag.run` check, so the
mechanism exists and the cost is one function. Against it: §15.7 is explicit
that the plane does not police what a workflow does, and this would be the first
check about a workflow's *content* rather than its resolution. Decide, and say
which side of §15.7 it falls on.

**5. What the machine module may still not learn.** §4's table is the load
bearing wall. If your stage 5 makes you want a machine-side option that names a
project, a workflow, a schedule or a task — **stop and write down what you
wanted and why, before you write it.** Stage 4 wanted one three times (a
schedule option, a secret value, a shell) and every time the answer was
somewhere else: the developer's own timer, an `EnvironmentFile`, and the
trigger.

**6. Whether the timer stays as it is.** `devman-maintain.timer` is installed in
`~/.config/systemd/user/`, hand-written, with **five hard-coded project names**.
That is deliberate — §8 says a schedule is the developer's, exactly as a hook is
the repository's — and it will drift the first time a project is added or
renamed. Decide whether that drift is acceptable, whether `doctor` should notice
it, or whether the recipe in `groups/base/README.md` should change shape. **Do
not solve it with a machine-side schedule option** without re-reading S2 first.

---

## 8. The machine, and what you may and may not do to it

**You may propose a `nixos-rebuild switch` — you may not run one.** The user
runs it. The pattern that has worked five times: make the edit in `nix-meta`,
prove it by evaluation, commit only your files, hand over.

```bash
# check a nix-meta change without activating it
nix eval .#nixosConfigurations.server.config.systemd.user.services.dagu --json
nix build .#nixosConfigurations.server.config.system.build.toplevel --no-link

# this repo's own checks, which need no machine
nix build .#checks.x86_64-linux.dagu-service --no-link
nix build .#checks.x86_64-linux.groups-validate --no-link
```

**A change to `groups/` or `modules/devenv.nix` does NOT need a rebuild** — it
reaches repositories through their own pinned input. **`nix/nixos-module.nix`
moves the machine closure, and so does anything under `src/devman/`**, because
the CLI ships from `nixosModules.default` only. Stage 4 learned that the
expensive way: a `doctor` fix was committed, and every run kept failing until
the user rebuilt.

**Two things you can do instead of asking for a rebuild.** Build the CLI and run
it directly — `nix build .#devman --print-out-paths`, then invoke it with
`--registry` and `--dagu-home` — which is how S13 and S14 were proved before
handover. And test a check's branches by importing `devman.doctor` and stubbing
`_get`, which is how S14's wedged branch was exercised without wedging the
plane.

**`nix-meta` has an unrelated uncommitted change** in `machines/server.nix` (a
disk mount). Leave it alone; scope every commit there to the files you touched.

**Do not run `nixos-rebuild switch`, and do not edit `/etc/nixos/`.**

---

## 9. Rules

1. **Report what happened, not what should have happened.** Record versions and
   exact commands. An error message is evidence; a summary of one is not.
2. **A timing without a spread is not a timing.**
3. **Throwaway is fine for tests. Not for the modules, the groups or the CLI** —
   those ship. A throwaway Dagu is isolated by its `DAGU_HOME` **and its ports,
   not by its process name**: stage 4 stopped one with `pkill -f "dagu
   start-all"` and stopped the real service too. Stop one by pid.
4. **`CONCEPT.md` is the specification.** If you must change it, change it
   deliberately, in its own commit, and say which measurement forces it. Add the
   `S`-numbered entry to `STAGE_5_LOG.md` **first**. Stages 1–4 did this eight
   times; follow that shape. **Do not let the charter change share a commit with
   the code change that motivated it.**
5. **Commit and push at regular intervals**, on the current branch, and push
   `main` with it — the two move together in this repository.
6. **Prefer running code to evaluating code.** Every real defect in four stages
   was found this way and by nothing else.
7. **Changing a real repository is a change to someone else's repo.** Commit
   there, push, and say what you changed.
8. **Never `git add -A` in a repository a workflow writes into.**
9. **Other sessions are working in this repository.** Stage the files you wrote,
   by name, and leave the rest alone.

---

## 10. The single most important instruction

**Four stages built a plane that works. Stage 5's risk is no longer that
something fails — it is that something has been quietly wrong the whole time and
nothing has yet asked it a question it cannot answer.**

Stage 4 asked three such questions by accident. Every one had been true since
stage 1 or stage 3, every one was invisible to the checks, and every one was
found by *doing more work on the machine than had ever been done at once*:

- the shell every step runs under was the login shell of whoever triggered it,
  for four stages;
- `doctor` called an ordinary busy queue a fault, from the moment the check was
  written, because two runs had never overlapped before;
- a workflow can delete its own run record by defining an exit handler, and
  nothing notices.

**So the most valuable thing stage 5 can do is put the plane somewhere it has
never been.** A second checkout. A second machine. A workflow that publishes. A
queue under real contention. Ten projects instead of six. Each of those is a
question the design claims an answer to and has never been asked.

And the rule that outranks everything else, unchanged since stage 1: **if
anything you build gives the registry a second entry path — a `devman register`,
a hand-written entry, a `dagu profile` keyed by project, a fallback scan, a "just
this once" initialisation step — stop and say so before writing it.** Criterion
17 is what lets the registry be derived, what lets §9.3 promise reconstruction,
and what lets §5.2 have no manual register command. §15.1 still forbids solving
any problem by scanning the filesystem for repositories. Reading devman's own
registry is not scanning; walking the disk to find repositories is.
