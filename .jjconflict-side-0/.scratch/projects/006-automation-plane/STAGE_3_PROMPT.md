# Kickoff — Stage 3, reactivity

## Your task

Build stage 3 of the devman automation plane, as `CONCEPT.md` §13 defines it.

Stage 1 shipped both module interfaces. Stage 2 turned the plane on, adopted
five real repositories, and answered §12.4 weakly. **Everything so far is
triggered by hand.** Stage 3 makes the plane react — and builds the first
devman command that has ever existed under this charter.

Work in the git worktree described in §4. Commit each piece as it works.

---

## 1. The one rule that keeps this session useful

> **Stages 1 and 2's code runs, on this machine, against five real
> repositories. Do not rewrite it because you would have written it
> differently. Change it when a measurement says to, and record the
> measurement.**

`STAGE_1_LOG.md` holds twelve entries and `STAGE_2_LOG.md` holds seventeen, both
in `FINDINGS.md`'s shape: the answer, the versions, the exact command, the
evidence, the charter impact. **Several exist because someone tried the obvious
thing first and it silently did not work.** If a piece of the design looks
needlessly indirect — the flat `dags/` directory, `builtins.readFile`, the
shell-form `$DEVMAN_PROJECT_DIR`, the `-v` on every group step, the
`DEVMAN_SELF_DIR` fallback — **read the entry before you simplify it.**

**What "done" means at this stage is still a measurement, not a feature.**
Criteria 13 and 14 are the last untested ones, and criterion 13 in particular
cannot be argued — only run.

---

## 2. Read these first

1. `.scratch/projects/006-automation-plane/STAGE_2_LOG.md` — **start here.**
   Seventeen entries, S1–S17. **S17 is the criterion-by-criterion table** and is
   the fastest way to see where the plane stands. S4, S12 and S15 are the three
   that will bite you if you skip them.
2. `.scratch/projects/006-automation-plane/STAGE_1_LOG.md` — twelve entries,
   short. S1, S2 and S8 explain three things in the code that look wrong.
3. `.scratch/projects/006-automation-plane/CONCEPT.md` — the specification.
   Re-read §8 (triggers — this stage's subject), §10 (the CLI), §7.1 (the
   contract, now **four** names), §9.2, §11, §13 stage 3, §14, §15.
   **It has been amended four times**; the status block says where and why.
4. `.scratch/projects/006-automation-plane/FINDINGS.md` — **do not read it end
   to end; it is 5,900 lines.** Read the final section, "Reconciliation input —
   every charter change, by section", then whatever it points you at. **D7, E2,
   E1 and E5 are the ones stage 3 needs** — D7 is the watcher, E1 is
   loop-breaking, E5 is what `doctor` can read rather than compute.
5. `nix/nixos-module.nix`, `modules/devenv.nix`, `groups/`,
   `.devman/workflows/README.md` — the code. Read the comments; each non-obvious
   line names the finding that forced it. **`.devman/workflows/README.md` is the
   hand-written trigger, and it is the specification for `devman run`.**

---

## 3. What stages 1 and 2 settled, so you do not re-derive it

`STAGE_2_LOG.md` S17 has the full table. The short version:

| # | Criterion | State |
|---|---|---|
| 1–12, 14–17 | everything except the watcher | **hold**, measured against the running service and five real repos |
| 13 | the watchers do not chase each other | **yours** — there is no watcher |
| 14 | the task graph exists once | holds, but its watcher half is untested |

**Yours: 13, the watcher half of 14, and the three commands in §10.** Plus
§12.4's measurement, which stage 2 answered with **one data point out of
eighteen** and which more repositories or a sharper group file would strengthen.

---

## 4. Where you are — read this before you open a file

| Fact | Value |
|---|---|
| Working directory | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| Branch | `dagu-devenv-automation-eli5`, pushed; `main` is at the same commit |
| Host | NixOS 26.11.20260705 (hostname `server`), Nix 2.34.7 |
| devenv | **2.1.2** installed. 2.2.0 behaves differently in one measured way — S4 |
| Dagu | 2.15.0, **installed and running** as `systemd --user` unit `dagu` |
| Ports | **8080 and 50055, held by the plane** |
| Registry | `~/.local/share/devman/` — 6 projects, 18 DAGs |
| `DAGU_HOME` | `~/.local/share/dagu/` — holds `config.yaml`, `base.yaml`, `data/`, `logs/` |
| home-manager | `/home/andrew/Documents/Projects/nix-meta`, `profiles/devman.nix` is the leaf |
| Machine pin | `nix-meta` pins devman `main` at an explicit rev in `flake.nix` |

### Talking to the running plane

A non-login shell has neither `DAGU_HOME` nor a session bus. Both are needed:

```bash
export DAGU_HOME=$HOME/.local/share/dagu
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
systemctl --user status dagu
dagu ls
```

### The six registered projects

| Project | Groups | Shape |
|---|---|---|
| `devman` | base | this repo; imports `./modules` locally, and owns `.devman/workflows/stack-validate.yaml` |
| `observantic` | python | plain Python library — ruff, mypy, pytest |
| `pydantree` | base + python | Python, uv workspace; `check` is **red** (920 ruff findings) |
| `pyjutsu` | base | Python **and Rust**, compiled extension |
| `siteman` | base | **no Python** — shell, shellcheck, Hugo. **Shadows `full-test.yaml`** |
| `nix-paseo` | base | **no application source** — a flake and NixOS modules |

**pydantree's `check` fails, and that is correct.** It is the repository's own
debt. Do not fix it to make a demo green; it is the only failing workflow you
have, and it is useful.

---

## 5. Nine facts that will bite you if you rediscover them

S-numbers are the stage logs; letters are `FINDINGS.md`.

**1. `devenv tasks run` captures a task's stdout and never prints it** — success
path and failure path alike. Every group step therefore passes `-v`. It is
load-bearing, not debug noise. `--show-output` documents itself as equivalent
and is not. Which stream the output lands on **differs between devenv 2.1.2 and
2.2.0**, so do not build anything that depends on one. (S4)

**2. `devenv test` loses BOTH streams**, with `-v` or without. Its exit code is
correct, so it works as a gate and never explains itself. (S4)

**3. `dagu start` ignores queues entirely.** Only `enqueue` is governed, and a
trigger must **export `DEVMAN_PROJECT_DIR` and pass it as a parameter** — the
environment reaches `log_dir`, the parameter reaches `working_dir`, and one is
not a substitute for the other. Re-measured on the real service in S11. (A1, A6,
E2, S11)

**4. Dagu supports no shell-style defaults.** `working_dir:
${A:-$B}` is kept literal and resolved as a **relative path**. The same gap
swallows `$(…)` and backticks. Only a handler's `run:` can use the shell form,
because that is a shell script. (S12, E2)

**5. `DEVMAN_SELF_DIR` is the fourth global name.** A cross-repo workflow must
not hold `DEVMAN_PROJECT_DIR`, so `base.yaml`'s exit handler falls back to
`DEVMAN_SELF_DIR`. Without it, a cross-repo run reports **Failed after both
children succeed**. (S12, and §7.1 was amended)

**6. A child run leaves nothing in the project it ran in.** `action: dag.run`
resolves `working_dir` from `with.params`, but the logs and the
`metadata.jsonl` line go to the **parent's** project, because `log_dir` is
resolved by the process that enqueues. (S12)

**7. `base.yaml` is read per run; `config.yaml` is read only at startup.** A
change to the first needs no restart, a change to the second does — and a missed
restart is silent (C7). (S12, §5.2)

**8. One rev is many store paths.** The same group file resolves to a different
store path in each repository, because the module takes `pkgs` from its
consumer. Compare group files by **content hash**, never by path. (S16, §3.1)

**9. A literally-named `${DEVMAN_PROJECT_DIR}` directory has already been
committed to this repository once, by the previous session.** The ignore rule
does not cover it, deliberately: it is the visible symptom of a broken trigger.
Never `git add -A` in a repository a workflow writes into. (S15, and §9.2's own
older cautionary tale)

---

## 6. What stage 3 must deliver

From §13:

```
one watchexec user service, reading the registry (§8)
VCS hooks
retention policy — hist_retention_days in base.yaml (§9.2)
devman run / show / doctor (§10)
```

### The criteria stage 3 must meet

| # | Criterion | How you will know |
|---|---|---|
| 13 | the watchers do not chase each other | a file-writing workflow plus a watcher on those files, **one save, exactly one run** |
| 14 | the task graph exists once | no default workflow re-states a dependency devenv already declares — check the watcher's glob-to-workflow mapping does not become a second graph |

### And the two things stage 2 hands you as requirements, not suggestions

> **`devman run` must refuse to enqueue when neither `DEVMAN_PROJECT_DIR` nor
> `DEVMAN_SELF_DIR` would be set.** That is what would have prevented S15's
> literally-named directory at the source. Prevention belongs in the one place
> that triggers a workflow.

> **`doctor` check 3 must search the registered repositories**, not only the
> daemon's working directory. The one real occurrence landed inside a project.

---

## 7. Four decisions this session must make, not defer

**1. What the watcher's glob-to-workflow mapping looks like, and where it
lives.** §8 says "the watcher is plane machinery; the mapping is group content",
so a group declares its own reactivity. But **§7.2 says a workflow is Dagu
configuration from the first line to the last, and Dagu rejects unknown
top-level keys outright (A5)** — so the mapping cannot go in the workflow file.
It is not a Nix option either, or the machine learns a project fact (§4). Decide
where it goes and say why. This is the sharpest design question in the stage.

**2. Whether `devman run` resolves a cross-repo workflow's parameters.**
`.devman/workflows/stack-validate.yaml` declares `OBSERVANTIC_DIR` and
`SITEMAN_DIR` as parameters, and the README resolves them from the registry by
hand. Either `devman run` learns that convention — which makes parameter names a
contract — or cross-repo workflows are triggered some other way. Pick one.

**3. What `devman doctor` does about a stale entry.** §10 says it **may prune**
rather than only report, and that pruning is safe because the registry is
derived. Decide whether stage 3's `doctor` prunes by default, behind a flag, or
not at all. Note that the two throwaway probe projects from stage 2 were removed
by hand precisely because nothing prunes yet.

**4. Which name the CLI ships under, and where it comes from.** §3.3 and §10:
`devman 0.2.0` is gone from the profile, so the name is free. But nothing
installs a devman CLI today — `services.devman-dagu.installClient` puts *Dagu*
on `PATH`, not devman. Decide whether the CLI ships from
`nixosModules.default`, from the devenv module, or both, and remember §3.1's
second rule: **what the two interfaces share must be text.** A Python CLI shared
by both is not text.

---

## 8. How to measure criterion 13, which is the one people get wrong

Not "it seemed to only run once".

1. **A workflow that writes a file inside its own trigger's watch scope.** A
   formatter is the honest case: `ruff format` on save. Anything that does not
   write the watched files cannot exhibit the failure.
2. **Count runs, not events.** `dagu status` and the project's
   `.devman/.runs/metadata.jsonl` both count runs; the jsonl is one line per run
   and survives retention (§9.2), so it is the better counter.
3. **One save must produce exactly one run.** Two is the failure. Zero is a
   different failure and is worse, because it looks like success.
4. **Then edit the file again immediately** and confirm it runs again. §8 is
   explicit that a content hash is required rather than a timer or a suppression
   window, precisely so that your own edit right after the formatter's write
   still fires. A debounce window passes step 3 and fails this one.
5. **Use `type: build` with `inputs:`/`outputs:`, or step-level
   `preconditions:` comparing a content hash.** Both are Dagu's own; the plane
   owns neither (§8, E1).

Do the same against a workflow that does **not** write its watched files, so the
result distinguishes "loop-breaking works" from "nothing ever runs twice".

---

## 9. The machine, and what you may and may not do to it

**You may propose a `nixos-rebuild switch` — you may not run one.** The user
runs it. The pattern that has worked twice: make the edit in `nix-meta`, prove
it by evaluation with the old value stashed back in as a control, commit only
your files, hand over.

```bash
# check a nix-meta change without activating it
nix eval .#nixosConfigurations.server.config.systemd.user.services.dagu --json
nix build .#nixosConfigurations.server.config.system.build.toplevel --no-link

# this repo's own checks, which need no machine
nix build .#checks.x86_64-linux.dagu-service --no-link
nix build .#checks.x86_64-linux.groups-validate --no-link
```

**A change to `groups/` or `modules/devenv.nix` does NOT need a rebuild** — it
reaches repositories through their own pinned input. Only `nix/nixos-module.nix`
moves the machine closure. Stage 2 demonstrated this: a groups-only re-pin
produced a byte-identical system.

**`nix-meta` has an unrelated uncommitted change** in `machines/server.nix` (a
disk mount). Leave it alone; scope every commit there to the files you touched.

**The watcher is a second user service from the same module** (§8, D7). It does
not need new ports. `watchexec` 2.5.1 is in nixpkgs.

**Do not run `nixos-rebuild switch`, and do not edit `/etc/nixos/`.**

---

## 10. Rules

1. **Report what happened, not what should have happened.** Record versions and
   exact commands. An error message is evidence; a summary of one is not.
2. **A timing without a spread is not a timing.**
3. **Throwaway is fine for tests. Not for the modules or the CLI** — those ship.
4. **`CONCEPT.md` is the specification.** If you must change it, change it
   deliberately, in its own commit, and say which measurement forces it. Add the
   `S`-numbered entry to `STAGE_3_LOG.md` **first**. Stages 1 and 2 did this four
   times; follow that shape. **Do not let the charter change share a commit with
   the code change that motivated it** — stage 2 did that once by accident and
   had to record the slip (S15).
5. **Commit and push at regular intervals**, on the current branch. Commit each
   working piece rather than saving one commit for the end.
6. **Prefer running code to evaluating code.** A module that `nix flake check`
   passes but was never entered has not been tested. Stage 1 found four things
   this way and stage 2 found the cross-repo handler failure this way — an
   evaluation would never have shown it.
7. **Changing a real repository is a change to someone else's repo.** Commit
   there, and say what you changed.
8. **Never `git add -A` in a repository a workflow writes into.** See fact 9.

---

## 11. The single most important instruction

**The watcher is the first component that acts without a person asking it to.**

Everything before it was pull: a developer entered a shell, or typed a trigger.
From now on the plane does work on its own, in the developer's own checkouts,
using the developer's own credentials. Two consequences, and neither is
paranoia:

**A loop is not a performance problem, it is a runaway.** A formatter that
chases itself does not merely waste CPU — it rewrites the developer's files
repeatedly while they are editing them. Criterion 13 is the gate on shipping the
watcher at all, and §8 already names the mechanism. **Measure it before you
enable anything on a real repository.** Use a throwaway project first.

**One watcher serves every registered repository** (§8, D7), so a mistake in it
is a mistake in all six at once. §15.3 already accepts that one Dagu instance is
a shared availability failure; the watcher makes it a shared *write* failure,
which is a different thing. `doctor` must be able to say what the watcher is
watching and what it last fired.

And the rule that outranks it, unchanged from stages 1 and 2: **if anything you
build gives the registry a second entry path — a `devman register`, a
hand-written entry, a fallback scan, a "just this once" initialisation step —
stop and say so before writing it.** Criterion 17 is what lets the registry be
derived, and §15.1 still forbids solving any problem by scanning the filesystem
for repositories. Reading devman's own registry is not scanning; walking the
disk to find repos is.

**A note on `devman doctor` specifically.** It is the first thing in this design
that is allowed to *tell the developer something*, because §5.2 establishes that
registration cannot report on the path that writes. Everything the plane knows
and nobody has been able to see — shadowed files and their drift, a misspelled
queue, a stale entry, a `.runs/` that stopped ageing, a literally-named
directory — arrives through it. Build it early, not last: you will use it to
debug the watcher.
