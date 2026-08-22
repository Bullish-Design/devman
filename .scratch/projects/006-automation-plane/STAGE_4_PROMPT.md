# Kickoff — Stage 4, higher-level automation

## Your task

Build stage 4 of the devman automation plane, as `CONCEPT.md` §13 defines it.

Stage 1 shipped both module interfaces. Stage 2 turned the plane on and adopted
five real repositories. Stage 3 made the plane react, built the CLI, and closed
§12.4. **Every layer below stage 4 is now built and running on this machine.**

§13 gates stage 4 on exactly that — *"only once every layer below is stable"* —
and its six items are all **content**: `review workflows`, `release`,
`maintenance`, `benchmark campaigns`, `agent workflows`, `policy gating`. Not
one of them names a module, a command, or an option. **Stage 4 is the first
stage whose deliverables are files rather than machinery**, and the sentence is
true with one exception you must decide about: §9.4's secrets are specified and
have never been used, and the machine module holds no secret plumbing at all.

Work in the git worktree described in §4. Commit each piece as it works.

---

## 1. The one rule that keeps this session useful

> **Stage 4's deliverables are files. Every one of them will look like it needs
> one small piece of machinery — a fifth global name, a fourth command, a
> per-workflow Nix option, a new key in a workflow. Write the file first. Grow
> the plane only when a measurement shows the file cannot be written without
> it, and record the measurement.**

This follows from what stage 3 learned. Each of stage 3's four design decisions
closed a machinery route and put the thing somewhere that already existed:
the trigger mapping became group content rather than a Nix option (S4), the
cross-repo parameter convention became a *value* the trigger reads rather than a
reserved name (S3), `doctor --prune` became a flag on a command rather than a
new one (S11), and VCS hooks turned out to need **nothing** in devman beyond
`devman run` (S9). §10's command list is closed at three. §7.1's name list is
closed at four, and it grew once — under a measurement, after a real run failed
(`STAGE_2_LOG.md`, S12).

**Stages 1–3's code runs, on this machine, against six real projects. Do not
rewrite it because you would have written it differently.** Several pieces exist
because someone tried the obvious thing first and it silently did not work. If a
line looks needlessly indirect — the flat `dags/` directory, `builtins.readFile`,
the `-v` on every group step, the `--project-origin` on watchexec, the
`DEVMAN_SELF_DIR` fallback — **read the log entry before you simplify it.**

---

## 2. Read these first

1. `.scratch/projects/006-automation-plane/STAGE_3_LOG.md` — **start here.**
   It held fourteen entries, S1–S14, when this prompt was written, and other
   sessions were still adding to it. **Read all of it, however far it now runs.**
   S6 and S8 are the two that changed the charter; S11 states stage 3's four
   decisions; S12 is the criterion-by-criterion table.
2. `.scratch/projects/006-automation-plane/CONCEPT.md` — the specification.
   **§13's stage 4 list is your subject.** Re-read §2 (what devman is — a closed
   list of three), §4 (what the machine never knows), §6 (Dagu composes, devenv
   executes), §7 (the contract), §8 (triggers, amended twice at stage 3), **§9.4
   (secrets — specified, never used, and probably yours)**, §11 (cross-repo),
   §14, §15 and §16. **It has been amended six times**; the status block says
   where and why.
3. `.scratch/projects/006-automation-plane/STAGE_2_LOG.md` — S17 is the
   criteria table stage 3's S12 is compared against, and S18 closes stage 2.
   Skim the rest; S4, S11, S12 and S15 are in §5 below.
4. `.scratch/projects/006-automation-plane/STAGE_1_LOG.md` — twelve entries,
   short. S1, S2, S7 and S8 explain four things in the code that look wrong.
5. `.scratch/projects/006-automation-plane/FINDINGS.md` — **do not read it end
   to end; it is 5,871 lines.** Read the final section, "Reconciliation input —
   every charter change, by section", then whatever it points you at. **E3
   (secrets), E2 (what actually invokes Dagu) and E8 (per-project mechanisms)
   are the three stage 4 needs**, and E7 (labels) is worth ten minutes.
6. The code. `nix/nixos-module.nix`, `modules/devenv.nix`, `src/devman/*.py`,
   `groups/*/`, `.devman/workflows/`, `flake.nix`, `nix/tests/dagu-service.nix`.
   Read the comments; each non-obvious line names the finding that forced it.
   `groups/base/README.md` and `groups/python-format/README.md` are where a
   repository is told how to use each group.

---

## 3. What stages 1–3 settled, so you do not re-derive it

| Question | Answer | Where |
|---|---|---|
| Where the glob-to-workflow mapping lives | `groups/<group>/triggers.toml`, resolved at evaluation time, recorded in the registry entry. **Reactivity is its own group** | S4, S7 |
| Whether `devman run` resolves cross-repo parameters | **Yes** — a declared parameter whose *default* names a registered project is filled with that project's path. The name is not a contract; the value is | S3 |
| What `doctor` does about a stale entry | reports by default, prunes behind `--prune`, and unprojects what it prunes | S11 |
| Where the CLI ships from | `nixosModules.default` **only**, wrapped with `--registry` and `--dagu-home` as flags rather than `DEVMAN_*` variables | S11 |
| VCS hooks | the repository's own `git-hooks.hooks.*` entry running `devman run <workflow>`. **devman supplies no option and no `hook install`** | S9 |
| Retention | `hist_retention_days` prunes Dagu's history **and** the per-project log tree; `metadata.jsonl` survives it | S10 |
| §7.1's global names | **four**, and the list is closed | `STAGE_2_LOG.md` S12 |

> **§12.4 is closed and stage 4 must not reopen it.** Whole-file shadowing
> stays. **A repository that must change a default writes a whole workflow file
> of its own.** No field merging, no group files split for the purpose, no
> further measurement of the override rate. Closed by the owner on 2026-08-22
> (S14, changing §12.4 and §16).

### The criteria, as stage 3 left them

**All seventeen hold** (`STAGE_3_LOG.md`, S12), measured against the installed
service, six real projects and 19 DAGs. Two of them carry a caveat you inherit:

| # | Criterion | State stage 4 inherits |
|---|---|---|
| 7 | devenv stays on the fast path | **holds, not re-measured at stage 3.** The last paired figure is +7.08 ms at its 95% upper bound against a 10 ms budget (`STAGE_2_LOG.md`, S3) |
| 13 | the watchers do not chase each other | **holds against corrected wording.** §14's criterion 13 was rewritten at stage 3, in its own commit: it now counts runs **that do work**, because Dagu skips *after* enqueueing rather than before, so a correct plane produces one run that formats and one that skips (S6, and §14's note) |

**§14 has no stage-4-only criterion.** See §6 below, which is your problem to
solve rather than one you inherit solved.

---

## 4. Where you are — read this before you open a file

Every value below was checked on 2026-08-22. **Check them again**; other
sessions were re-pinning repositories while this was written.

| Fact | Value |
|---|---|
| Working directory | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| Branch | `dagu-devenv-automation-eli5`. `origin/main` and `origin/dagu-devenv-automation-eli5` sit on the same commit; the local branch runs ahead of both while sessions commit |
| Host | NixOS 26.11.20260705.d407951 (Zokor), hostname `server`, Nix 2.34.7 |
| devenv | **2.1.2**, at `~/.nix-profile/bin/devenv`. 2.2.0 differs in one measured way — `STAGE_2_LOG.md` S4 |
| Dagu | **2.15.0**, at `/run/current-system/sw/bin/dagu`, running as `systemd --user` unit `dagu` |
| devman | **0.3.0**, at `/run/current-system/sw/bin/devman` — `run`, `show`, `doctor`, `watch` |
| watchexec | **2.5.1**, running under `systemd --user` unit `devman-watch` |
| Ports | **8080 and 50055**, held by the plane |
| Queues | `light` 4, `normal` 2, `heavy` 1, **`gpu` 1**, `exclusive` 1 |
| Registry | `~/.local/share/devman/` — **6 projects, 19 workflows, 19 DAGs** |
| `DAGU_HOME` | `~/.local/share/dagu/` — `config.yaml`, `base.yaml`, `data/`, `logs/`, `suspend/` |
| home-manager | `/home/andrew/Documents/Projects/nix-meta`, `profiles/devman.nix` is the leaf |
| Machine pin | `nix-meta` pins devman at rev `b0712286…`, which is `b071228` on this branch |

### Talking to the running plane

A non-login shell has neither `DAGU_HOME` nor a session bus. Both are needed:

```bash
export DAGU_HOME=$HOME/.local/share/dagu
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
systemctl --user status dagu devman-watch
dagu ls
```

**That is right for a person at a prompt and wrong for a program.** `devman run`
states `--dagu-home` rather than inheriting it, for the reason in fact 3 below.

### The six registered projects

Built from `~/.local/share/devman/projects/`, not copied forward.

| Project | Groups | Own files | Shape |
|---|---|---|---|
| `devman` | `base`, `python-format` | `stack-validate` | this repo; imports `./modules` locally; **the only project with triggers** — `**/*.py` → `format` |
| `observantic` | `python` | — | plain Python library; `check` and `validate` only |
| `pydantree` | `base`, `python` | — | Python, uv workspace. `check` is **red** — 920 ruff findings (`STAGE_2_LOG.md`, S10) |
| `pyjutsu` | `base` | — | Python **and Rust**, compiled extension |
| `siteman` | `base` | `full-test` | **no Python** — shell, shellcheck, Hugo. Shadows `full-test.yaml` |
| `nix-paseo` | `base` | — | **no application source** — a flake and NixOS modules |

**pydantree's `check` fails, and that is correct.** It is the repository's own
debt and the only failing workflow you have. Do not fix it to make a demo green.

**Two entries still carry `"schema": 2`** — `nix-paseo` and `pydantree` — because
the registry is derived and an entry is rewritten only when that repository's
shell is next entered (§5.2, §9.3). They hold no `triggers` key at all. That is
the design working, not drift, and it is worth remembering before you conclude
that a registry field is missing.

### What `devman doctor` reports today

Ten checks, all `ok`, exit 0, `Nothing to report.` The two that will matter to
you:

```
ok  shadowing      devman/stack-validate: invented — no group version to diff
                   siteman/full-test: shadows base — 7 of 9 executable lines unchanged
ok  watcher        devman: **/*.py -> format  [python-format]
                   running since 2026-08-22T15:25:11-04:00, pid 1078382
                   fired 2026-08-22T15:26:47.868-04:00  devman/format  <- src/devman/_watch_probe.py
```

**Run `devman doctor` before you start and after every change.** It is the one
thing in this design allowed to tell the developer something (§5.2).

---

## 5. Ten facts that will bite you if you rediscover them

S-numbers are the stage logs; letters are `FINDINGS.md`.

**1. Dagu's own scheduler cannot write a run's logs into the project.**
`log_dir` is resolved by the process that **enqueues**, from that process's
environment. Under a `schedule:` that process is the daemon, which has one
environment for the whole machine. Measured three ways: a parameter resolves
`working_dir` and leaves `log_dir` literal (A3), every HTTP surface does the same
(E2), and `--profile` does the same (E8). E2's table records `schedule:` as
carrying **"defaults only"**. The symptom is §9.2's: a directory named literally
`${DEVMAN_PROJECT_DIR}` in the daemon's tree, and a run that reports success.
**Maintenance and benchmark campaigns are scheduled work**, so measure this
before you design either. §8's diagram still lists `schedule → Dagu's own timer`.

**2. `dagu dry` writes.** It documents itself as a simulation "without producing
any side effects" and it **creates `log_dir`** — which, for a workflow whose
directory variable is unset, is the literally-named directory. **No devman
command may call it.** (S1)

**3. An unset `DAGU_HOME` builds a second Dagu.** A bare `dagu` in an ordinary
shell creates `~/.config/dagu/`, writes its own `base.yaml`, **seeds five example
DAGs**, and lists nothing. `skip_examples` is per instance, so the plane's own
config cannot protect it. A trigger must **state** its target, never inherit it.
(S2)

**4. `devman run` refuses a declared parameter that would have no value.** It
fills a parameter whose default names a registered project with that project's
path, passes everything else through unchanged, and then refuses if any value is
empty or if the directory variable is not a directory. Read
`src/devman/run.py:95-125` before you write a workflow that takes an argument —
a free-text parameter with an empty default is refused at the trigger. (S3)

**5. There are two loops, and a workflow can break only one of them.** A
workflow's `preconditions:` break the loop the workflow causes. **The watcher's
ignore list breaks the loop the plane causes** — every run creates a log
directory inside the project, so a run whose every step is skipped still produces
an event. With one ignore removed, one save produced **107 dispatches and 60 runs
in 45 seconds**. A group's glob is the first filter and the more important one.
(S8, changing §8)

**6. The watcher reads its watch *set* at service start.** The mapping is
re-read on every event, so changing which glob fires which workflow is live; the
list of watched paths is not. A repository that newly adopts reactivity is
watched after `systemctl --user restart devman-watch`, and not before.
`nix/nixos-module.nix` states this at the unit, and `doctor` reports the running
watcher's own record. watchexec also needs `--project-origin`: without it, one
watcher over several repositories walks their common ancestor and **spun a core
at 99.4% while firing nothing**. (S5)

**7. `devenv tasks run` captures a task's stdout and never prints it** — success
path and failure path alike. Every group step therefore passes `-v`. It is
load-bearing, not debug noise; `--show-output` documents itself as equivalent and
is not. **`devenv test` loses BOTH streams**, with `-v` or without, so it works
as a gate and never explains itself. (`STAGE_2_LOG.md`, S4)

**8. `dagu start` ignores queues entirely.** Only `enqueue` is governed, and a
trigger must **export `DEVMAN_PROJECT_DIR` and pass it as a parameter** — the
environment reaches `log_dir`, the parameter reaches `working_dir`, and one is
not a substitute for the other. (A1, A3, E2, `STAGE_2_LOG.md` S11)

**9. Dagu supports no shell-style defaults.** `working_dir: ${A:-$B}` is kept
literal and resolved as a **relative path**. The same gap swallows `$(…)` and
backticks. Only a handler's `run:` can use the shell form, because that is a
shell script. (`STAGE_2_LOG.md` S12, E2)

**10. Never `git add -A` in a repository a workflow writes into.** A literally
named `${DEVMAN_PROJECT_DIR}` directory has already been committed to this
repository once. The ignore rule does not cover it, deliberately: it is the
visible symptom of a broken trigger. (`STAGE_2_LOG.md` S15, and S1 above)

**And one that is not a hazard but will save you an hour.** A group file inside a
`path:` flake input is invisible to devenv's evaluation cache — editing it
changes nothing, `devenv update` does not help, and deleting
`.devenv/nix-eval-cache.db*` does. A repository importing `./modules` locally
(this one) is in the tracked case; a throwaway built to test a group is not. (S7)

---

## 6. What stage 4 must deliver, and what "done" means

From §13:

```
review workflows   release   maintenance   benchmark campaigns
agent workflows    policy gating
```

**§14's seventeen criteria contain no stage-4-only entry.** Stages 1, 2 and 3
each closed on a table of measurements someone else wrote down first. You do not
have that, and this is the first stage where the question has no measured answer.

So **write your definition of done first**, as `STAGE_4_LOG.md` S1, before you
build anything, and be judged against something you wrote in advance. Three
things it must cover, and the rest is yours:

1. **Every criterion that holds must still hold, measured rather than asserted.**
   1, 10, 14 and 17 are the ones content pressures hardest: a release workflow
   wants an absolute path, a campaign wants a dependency graph, and an agent
   workflow wants a way in.
2. **A workflow that was written and never run is not delivered.** Each
   deliverable runs at least once, on the real plane, in a real repository, with
   the run's `metadata.jsonl` line and its log quoted as evidence (rule 1).
3. **A content stage is measured by coverage, not by count.** Six workflow files
   that all run `devenv tasks run` in one project prove less than two that a
   second project takes unedited. That is criterion 6's shape, applied to work
   nobody has done yet.

---

## 7. The decisions this session must make, not defer

**1. How scheduled work is triggered. This is the sharpest question in the
stage.** Maintenance and benchmark campaigns are scheduled by definition. §8's
table names Dagu's own timer, and fact 1 above says the scheduler cannot resolve
`log_dir` into the project. Three shapes exist and each costs something: put
`schedule:` in the workflow and accept machine-side logs, which changes §9.2;
trigger from something local, which adds a fourth arrow to §8's three; or measure
that some arrangement makes the daemon's own enqueue resolve per project, which
A3, E2 and E8 each failed to find. **Measure before you choose**, and if the
answer changes the charter, write the log entry first (rule 4).

**2. Whether stage 4 needs a secret, and whether the machine module grows to
supply it.** §9.4 is fully specified and **the word `secret` appears nowhere in
`nix/`, `modules/`, `groups/` or `src/`.** E3 measured Dagu's own mechanism: a
per-workflow `secrets:` block, resolved at run time, **masked in logs**, and
failing the run by name when missing — none of which a plain environment variable
does. E3 also recommends `provider: env` over `provider: file`, because a file
path is machine-specific and collides with §9.1. The decision is what the module
does: `provider: env` reads the **daemon's** environment, so the module would
gain an option that sets variables on the Dagu user service. Decide whether a
release or a review workflow genuinely needs one, or whether it can use the git
credentials and SSH agent the user service already has (§4). **Two traps.** §9.4
forbids a `secrets:` block in `base.yaml`, because that grants every workflow on
the machine every secret. And E8's `dagu profile set-secret` scopes a secret by
project identity, which is a second store keyed the way devman's registry is
keyed — see the rule at the end of §10.

**3. Whether agent workflows fit the contract.** An agent workflow should be
Dagu steps calling `devenv tasks run <group>:<task>`, like everything else (§6),
and this repository already carries `claude-code` and `codex-cli` in
`devenv.nix`'s packages. Two things to settle. **Input**: an agent run usually
takes a prompt, an issue number or a branch, and fact 4 says `devman run` refuses
a declared parameter with an empty default. Decide how an argument reaches a run,
and whether it is passed as `NAME=VALUE` or has no place in a workflow at all.
**Concurrency**: an agent run is long, writes into the developer's tree, and
competes with the watcher that is watching that tree. Name its queue on purpose.

**4. Whether policy gating fits the four global names.** §7.1's list is closed at
four and grew exactly once, under a measurement. Gating needs to know whether
something passed, and two sources already exist, neither of them a new name: the
project's own `.devman/.runs/metadata.jsonl`, which holds one line per run and
survives retention (§9.2), and Dagu's machine-side history. A precondition is a
shell command inside a workflow file, which is content. **Decide whether that is
enough. If it is not, name the missing fifth name exactly, and say why no file
can hold it.**

**5. Whether a benchmark campaign needs a queue the machine does not declare.**
`gpu` is declared with `max_concurrency: 1` and **no workflow anywhere names it**
— the only two occurrences in the tree are the module's default and §7.1's list.
Decide whether a campaign names `gpu`, `heavy` or `exclusive`, and remember
§15.4: adding a queue name is cheap, renaming one is a migration across every
workflow that names it, and a misspelled name is accepted **silently** with no
limit at all.

**6. Where review and release workflows live.** Three homes, and §16's promotion
rule is the test: *a group begins when a second repository wants the same file*.
`base` reaches five of six projects, so a `release.yaml` there gives every
repository a release workflow. §7.4 says an inherited workflow you never trigger
costs nothing — but S4 already found the limit of that argument, which is why
reactivity became its own group. Decide **per deliverable**, and say which of the
three each one landed in and why.

---

## 8. The machine, and what you may and may not do to it

**You may propose a `nixos-rebuild switch` — you may not run one.** The user
runs it. The pattern that has worked three times: make the edit in `nix-meta`,
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
reaches repositories through their own pinned input, and stage 2 demonstrated
that a groups-only re-pin produced a byte-identical system. **Only
`nix/nixos-module.nix` moves the machine closure**, and a change there that adds
a secret or a queue needs both a rebuild and a service restart, because
`config.yaml` is read once at startup and a missed restart is silent (§5.2, C7).

**`nix-meta` has an unrelated uncommitted change** in `machines/server.nix` (a
disk mount). Leave it alone; scope every commit there to the files you touched.

**Do not run `nixos-rebuild switch`, and do not edit `/etc/nixos/`.**

---

## 9. Rules

1. **Report what happened, not what should have happened.** Record versions and
   exact commands. An error message is evidence; a summary of one is not.
2. **A timing without a spread is not a timing.**
3. **Throwaway is fine for tests. Not for the modules, the groups or the CLI** —
   those ship.
4. **`CONCEPT.md` is the specification.** If you must change it, change it
   deliberately, in its own commit, and say which measurement forces it. Add the
   `S`-numbered entry to `STAGE_4_LOG.md` **first**. Stages 1–3 did this six
   times; follow that shape. **Do not let the charter change share a commit with
   the code change that motivated it** — stage 2 did that once by accident and
   had to record the slip.
5. **Commit and push at regular intervals**, on the current branch. Commit each
   working piece rather than saving one commit for the end.
6. **Prefer running code to evaluating code.** A module that `nix flake check`
   passes but was never entered has not been tested. Stage 1 found four things
   this way, stage 2 found the cross-repo handler failure this way, and stage 3
   found the runaway this way. No evaluation would have shown any of them.
7. **Changing a real repository is a change to someone else's repo.** Commit
   there, and say what you changed.
8. **Never `git add -A` in a repository a workflow writes into.** See fact 10.
9. **Other sessions are working in this repository.** Stage the files you wrote,
   by name, and leave the rest alone.

---

## 10. The single most important instruction

**Stage 4 is the first stage whose output matters, not merely whether it ran.**

Every criterion so far is a property of the plane: the logs landed in the right
project, the queue serialized, one save made one run. A green `check` tells you
the plane works. **A review, a release, a campaign and an agent run each produce
something a person then acts on** — a merged branch, a published artifact, a
rewritten file, a number somebody trusts. Two consequences, and neither is
caution for its own sake:

**A wrong answer from stage 4 is not a failed run. It is a successful run that
did the wrong thing**, and the plane has no check for that and is not going to
grow one — §15.7 is explicit that nothing checks whether a default still fits,
and that the trade is deliberate. What the plane owes instead is visibility:
`metadata.jsonl`, the per-project log tree, and `devman doctor`. Every stage-4
workflow must leave enough behind that a person can see what it did without
re-running it.

**And stage 4 is the first stage that will want credentials.** A release wants a
token; an agent wants an API key. §9.4 has been specified since the charter was
written and has never once been used, so its first use is yours — in workflows
that a schedule or a watcher fires **with nobody watching**, in the developer's
own checkouts, under the developer's own identity. E3 measured the difference
that matters: Dagu masks a declared secret in logs and output, and fails a run
whose secret is missing before any step runs. A plain injected environment
variable does neither, and a step that echoes a token writes it into
`.devman/.runs/`, and from there into a screenshot or a bug report. **Declare a
secret; do not inject one.** And never put the block in `base.yaml`.

And the rule that outranks everything else, unchanged since stage 1: **if
anything you build gives the registry a second entry path — a `devman register`,
a hand-written entry, a `dagu profile` keyed by project, a fallback scan, a "just
this once" initialisation step — stop and say so before writing it.** Criterion
17 is what lets the registry be derived, what lets §9.3 promise reconstruction,
and what lets §5.2 have no manual register command. §15.1 still forbids solving
any problem by scanning the filesystem for repositories. Reading devman's own
registry is not scanning; walking the disk to find repositories is.
