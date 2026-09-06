# Kickoff — Stage 2, convention and adoption

## Your task

Build stage 2 of the devman automation plane, as `CONCEPT.md` §13 defines it.

Stage 1 shipped both module interfaces, two workflow groups, and one adopted
repository. **It was never installed on the machine.** Everything stage 1
measured used a Dagu started by hand on moved ports. Stage 2 turns the plane on
and finds out what five real repositories do to it.

Work in the git worktree described in §4. Commit each piece as it works.

---

## 1. The one rule that keeps this session useful

> **Stage 1's code runs. Do not rewrite it because you would have written it
> differently. Change it when a measurement says to, and record the
> measurement.**

`STAGE_1_LOG.md` holds twelve entries, in `FINDINGS.md`'s shape: the answer, the
versions, the exact command, the evidence, the charter impact. Four of them
exist because someone tried the obvious thing first and it silently did not
work. If a piece of the design looks needlessly indirect — the flat `dags/`
directory, the `builtins.readFile`, the shell-form `$DEVMAN_PROJECT_DIR` — read
the entry before you simplify it.

**What "done" means at this stage is a measurement, not a feature.** §12.4 is
the last open question in the charter, and it can only be answered by five real
repositories. A stage 2 that ships polish and skips the measurement has failed.

---

## 2. Read these first

1. `.scratch/projects/006-automation-plane/STAGE_1_LOG.md` — **start here.**
   Twelve entries, S1–S12, and it is short. S12 is the list of what stage 1
   deliberately did not do, which is most of your scope.
2. `.scratch/projects/006-automation-plane/CONCEPT.md` — the specification.
   Re-read §7 (the contract), §9 (state), §12.4 (the open question), §13 stage
   2, §14. It was amended twice during stage 1 and the status block says where.
3. `.scratch/projects/006-automation-plane/FINDINGS.md` — the five
   investigations. **Do not read it end to end; it is 5,600 lines.** Read the
   final section, "Reconciliation input — every charter change, by section",
   which is the index, then whatever it points you at. A1, A6 and E2 are the
   ones stage 2 needs.
4. `nix/nixos-module.nix`, `modules/devenv.nix`, `groups/` — the code. Read the
   comments; each non-obvious line names the finding that forced it.

---

## 3. What stage 1 settled, so you do not re-derive it

| # | Criterion | State |
|---|---|---|
| 1 | one flake, two interfaces, one version | **partly** — `nix flake check` passes, but the machine imports nothing yet. See §7 decision 1 |
| 2 | a repo adopts in three lines | holds, with a caveat — see fact 4 |
| 3 | a repo may take no groups | holds |
| 4 | a repo may rename or replace every default | holds |
| 7 | devenv stays on the fast path | holds — −0.85 ms paired, budget 10 ms |
| 8 | registration is idempotent | holds |
| 9 | only opted-in repos register | holds |
| 10 | no workflow contains an absolute path | holds |
| 11 | identity survives a move | holds |
| 16 | devman adopts itself | **registration half only** |
| 17 | there is one way in | holds |

**Yours: 5, 6, 12, 15, and 16's second half.** Plus §12.4's measurement, which
is not a criterion but is the last open question in §16.

Criteria 13 and 14 belong to stage 3, with the watcher.

---

## 4. Where you are — read this before you open a file

| Fact | Value |
|---|---|
| Working directory | `/home/andrew/.paseo/worktrees/1n48r26y/special-dragon` |
| Branch | `dagu-devenv-automation-eli5`, at `1ae16c1`, pushed to `origin` |
| `main` | **not merged.** The branch is 47 commits ahead |
| Main checkout | `/home/andrew/Documents/Projects/devman`, on `spike/agent-factory-round-trip` — see fact 6 |
| Host | NixOS 26.11.20260705 (hostname `server`), Nix 2.34.7 |
| devenv | 2.1.2 installed; 2.2.2 is in the store and behaves identically (C1, C2) |
| Dagu | 2.15.0, via `nix/dagu.nix`. **Not on PATH. Not running.** |
| Machine nixpkgs | `/nix/store/ifpab9hxqmk2biwy594da8ipxzsp3y4s-source` |
| home-manager | `/home/andrew/Documents/Projects/nix-meta` — `flake.nix` is the entrypoint, `profiles/terminal.nix` and `machines/server.nix` are the leaves |

### What exists and works

| Path | State |
|---|---|
| `flake.nix` | `packages`, `overlays.default`, `nixosModules.default`, `checks.groups-validate`, `checks.dagu-service` |
| `nix/nixos-module.nix` | stage 1, complete against §4: ports as options, bounded restart, `dags_dir` at the registry, `base.yaml` with `handler_on.exit`, `linger`, `servicePath`, `skip_examples` |
| `modules/devenv.nix` | stage 1, complete against §5, §7.3, §9, §15.2: group resolution, the directory projection, both refusals, the fork-free ignore rule |
| `nix/tests/dagu-service.nix` | a NixOS VM test that starts the service and runs one real DAG. `nix flake check` passes |
| `groups/base`, `groups/python` | `check`, `validate`, `full-test`; python shadows the first two |
| `.devman/` here | holds `.runs/` only. `context/` moved to `.scratch/context/` — §15.2 is a whitelist |

### What the last session changed on the machine, and what it did not

- **`devman 0.2.0` is gone.** `programs.nix-terminal.devman.enable = false` in
  `nix-meta/profiles/terminal.nix`, committed there as `03b80a7`, and **the
  rebuild is done** — `command -v devman` is empty. `nv` and `claude` are
  unaffected.
- **The registry exists**, at `~/.local/share/devman/`, holding one project:

  ```
  projects/devman/metadata.json
  projects/devman/workflows/{check,validate,full-test}.yaml   -> the store
  dags/devman-{check,validate,full-test}.yaml                 -> the line above
  dags/.dag.index, dags/wiki/                                 <- Dagu's own
  ```

- **`services.devman-dagu` is not in `nix-meta`.** Nothing imports the NixOS
  module. There is no `dagu` on `PATH` and no user service. That is decision 1.

---

## 5. Seven facts that will bite you if you rediscover them

All measured. S-numbers are `STAGE_1_LOG.md`; letters are `FINDINGS.md`.

**1. The plane is not running, so nothing you assume about it is tested.**
Every stage-1 run used a hand-started Dagu with `DAGU_HOME=/tmp/...` on ports
18080 and 51055. The real service on 8080/50055 has never run on this machine.
Install it first (§7 decision 1); everything else in stage 2 needs it.

**2. A DAG is keyed by its file's base name, not its path.** Two projects both
projecting `check.yaml` are reported as a duplicate and **both** vanish from
`dagu ls`, from the web UI and from the scheduler while staying runnable by
path. That is why `dags/<project>-<workflow>.yaml` is flat. It fires the moment
a second repository adopts the plane — which is this session. (S1)

**3. `dagu start` ignores queues entirely.** Only `enqueue` is governed, and a
trigger must **export `DEVMAN_PROJECT_DIR` and pass it as a parameter**: the
environment reaches `log_dir`, the parameter reaches `working_dir`, and one is
not a substitute for the other. There is no `devman run` yet — §10 defers it to
stage 3 and says to prove the conventions by hand first. (A3, A6, E2)

**4. "Three lines" is three lines plus the group's task names.** devenv rejects
a bare task name — `Invalid task name: lint. Task names must be in format
'namespace:name'` — so taking `base` means adding `base:lint` and `base:test`
to that repo's `devenv.nix`. Adopting five repos is five edits, not five
three-line blocks. Say so in the report rather than letting criterion 2 read as
cheaper than it is. (S7)

**5. `${DEVMAN_PROJECT_DIR}` does not interpolate inside a handler's `run:`,
though `${context.*}` does.** `base.yaml` uses the shell form on purpose. (S2)

**6. Two checkouts of this repository will collide, and that is correct.**
`/home/andrew/Documents/Projects/devman` is the main checkout, currently on
another branch. The moment it carries a `devman.project = "devman"` and someone
enters its shell, §9.1 refuses it — the registry holds one `path` per project
and this worktree already has it. Do not "fix" the refusal. Decide which
checkout owns the name (§7 decision 3).

**7. `fsdantic` already has a `.devman/`, holding `store/`.** It is D6's second
survey specimen, and §15.2's whitelist will refuse it. **That is the rule
working.** Do not widen the whitelist to adopt it; either skip that repo or move
its directory, as this one did with `context/`. (D6, and `.scratch/context/README.md`)

---

## 6. What stage 2 must deliver

From §13, minus what stage 1 already shipped.

```
the plane, installed          services.devman-dagu on this machine, from a pinned rev
Dagu queues and concurrency   criterion 12 — measured, through the real trigger path
artifact and run-state layout §9.2's .runs/{logs,artifacts,reports}
five adopted repositories     criteria 5, 6, and §12.4's measurement
cross-repo workflows          criterion 16's second half, §11's one rule
the metadata schema           what doctor will need, decided before doctor exists
```

### The criteria stage 2 must meet

| # | Criterion | How you will know |
|---|---|---|
| 5 | shadowing is exact | copy a group file into `.devman/workflows/`, re-enter: the projection is identical. Edit one step: only that step changes |
| 6 | a workflow is portable Dagu | one group file, unedited, runs correctly in **every** repo that takes the group |
| 12 | queues are real | two workflows naming `exclusive` serialize **when enqueued**. Use the real trigger path — fact 3 |
| 15 | a rebuild is inconvenient, not catastrophic | delete Dagu state, re-enter every registered shell, every workflow runs again |
| 16 | devman adopts itself | this repo's `.devman/workflows/` holds a cross-repo workflow that triggers two other projects, and it runs |

### And the measurement, which is the point of the stage

> **§12.4 — how many files were overridden across five repos, and how much of
> each is unchanged from the group version?**

§12.4 states what the answer decides: *"A file copied to change one line is the
failure mode. If it is common, the fix is smaller group files — split
`check.yaml` into what varies and what does not — not a merge algorithm."*

So report the diff, per overridden file, as a percentage of lines unchanged.
One number per file, and the list. **If nobody overrode anything, that is also
a result** — it means the groups fit, and it means §12.4 stays open for want of
pressure rather than being answered.

---

## 7. Four decisions this session must make, not defer

**1. How the machine imports the plane, and from what rev.** The branch is not
merged. Two shapes work:

```nix
# nix-meta/flake.nix
devman.url = "git+https://github.com/Bullish-Design/devman?ref=dagu-devenv-automation-eli5&rev=1ae16c1...";
# or, after merging to main
devman.url = "git+https://github.com/Bullish-Design/devman?ref=main&rev=<sha>";
```

`git+https` records `rev` and `narHash`; `git+file` records neither and silently
follows the branch head (B4). A `github:` input hits the API rate limit on every
evaluation (§3.2). **Merging to `main` first is the cleaner shape** and matches
§3.2's example, but it is the user's call — ask.

**2. Whether this repository keeps importing `./modules`.** It self-adopts
through a local relative import, which costs no input and needs no rev. But
criterion 1 says *"the machine and this repo import the same rev"*, and a local
import is not a rev. Two readings, and you should pick one and say which:

- the local checkout *is* the rev, so criterion 1 holds and the local import is
  the honest expression of it; or
- self-adoption should pin the same input the machine does, paying ~20 ms per
  entry (§3.2) and the S8 staleness disappears.

**3. Which checkout owns `project = "devman"`.** See fact 6. The registry holds
one `path` per project. Options: the main checkout owns it and worktrees state a
different `project`; or the reverse; or worktrees do not set `devman.enable`.
Whatever you choose, §9.1's refusal must stay the mechanism.

**4. Which five repositories.** `~/Documents/Projects` holds 68 directories, and
`devenv.nix` appears in most. Pick for **variety of decomposition**, not for
convenience — §12.4 is asking whether one `check.yaml` fits several shapes, and
five Python libraries answer a narrower question than four plus a Nix flake
repo. State the five and why. `fsdantic` is a special case (fact 7).

---

## 8. How to measure criterion 12, which is the one people get wrong

Not a wall-clock number. A serialization proof.

1. **Two DAGs, both naming `exclusive`, both enqueued.** `max_concurrency` is 1,
   so the second must not start before the first ends. Have each step record a
   monotonic timestamp at start and at end, and show the four numbers.
2. **Use `dagu enqueue`, never `dagu start`.** A1 measured `start` running both
   at once, 0.3 s apart, with the queue ignored. If your evidence shows overlap,
   check which command produced it before you conclude the queue is broken.
3. **Export the variable *and* pass the parameter.** Without the export, the run
   still succeeds and writes its logs into a directory literally named
   `${DEVMAN_PROJECT_DIR}` in whatever tree the daemon started in (A3). A green
   run is not evidence that the trigger was right — check where the logs landed.
4. **Two different projects, not two runs of one DAG.** `max_active_runs`
   governs one DAG; the queue governs across DAGs, and across-DAGs is the claim.

Do the same for a second queue with a limit above 1, so the result distinguishes
"the queue serializes" from "everything serializes".

---

## 9. The machine, and what you may and may not do to it

**You may now propose a `nixos-rebuild switch` — you may not run one.** The
user runs it. Last session's pattern worked well: make the edit in `nix-meta`,
prove it by evaluation with the old value stashed back in as a control, commit
only your file, and hand over.

```bash
# check a nix-meta change without activating it
nix eval .#nixosConfigurations.server.config.systemd.user.services.dagu --json
nix build .#nixosConfigurations.server.config.system.build.toplevel --no-link

# and this repo's own VM test, which needs no machine at all
nix build .#checks.x86_64-linux.dagu-service --no-link
```

**`nix-meta` has an unrelated uncommitted change** in `machines/server.nix` (a
disk mount). Leave it alone; scope every commit there to the files you touched.

Once the service is installed, it holds **8080 and 50055**. Anything else
wanting those ports fails loudly with `bind: address already in use` (D3). The
ports are options, so move the *other* thing, or move devman's.

---

## 10. Rules

1. **Report what happened, not what should have happened.** Record versions and
   exact commands. An error message is evidence; a summary of one is not.
2. **A timing without a spread is not a timing.**
3. **Throwaway is fine for tests. Not for the modules** — those ship.
4. **`CONCEPT.md` is the specification.** If you must change it, change it
   deliberately, in its own commit, and say which measurement forces it. Stage 1
   did this twice; follow that shape, and add an `S`-numbered entry to
   `STAGE_2_LOG.md` first.
5. **Do not run `nixos-rebuild switch`, and do not edit `/etc/nixos/`.**
6. **Commit and push at regular intervals**, on the current branch. Commit each
   working piece rather than saving one commit for the end.
7. **Prefer running code to evaluating code.** A module that `nix flake check`
   passes but was never entered has not been tested. Stage 1 found four things
   this way that evaluation would never have shown.
8. **Adopting a real repository is a change to someone else's repo.** Commit
   there, do not push, and say what you changed.

---

## 11. The single most important instruction

**Criterion 6 is this stage's load-bearing one — "one group file, unedited,
runs correctly in every repo that takes the group."**

Everything the plane claims about groups rests on it. A group file that needs a
per-repo tweak is not a group file; it is a template, and a template means
devman starts parsing workflows, which §7.2 says it never does.

**So when a group file does not fit a repo, resist the two easy fixes.** Do not
add a devman-specific key to the file — Dagu rejects unknown top-level keys
outright (A5), and the charter deleted `x-devman` for this reason. Do not add a
Nix option that rewrites the file at projection time — that is the failure mode
§12.1 named, and it makes §7.2 false.

The three legitimate answers, in order of preference:

1. **The repo defines the group's task names.** That is what taking a group
   means (§7.1). Most misfits are this.
2. **The repo shadows the file** (§7.3), and you record it for §12.4 — that is
   exactly the data the measurement wants.
3. **The group file is wrong and should change for everyone**, which is a commit
   to `groups/` with a reason.

If you find yourself wanting a fourth, stop and say so before writing it.

And the rule that outranks it, unchanged from stage 1: **if anything you build
gives the registry a second entry path — a `devman register`, a hand-written
entry, a fallback scan, a "just this once" initialisation step — stop and say so
before writing it.** Criterion 17 is what lets the registry be derived, and
§15.1 still forbids solving any problem by scanning the filesystem for
repositories. Reading devman's own registry is not scanning; walking the disk to
find repos is.
