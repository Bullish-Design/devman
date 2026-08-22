# STAGE 2 — what was measured while turning the plane on

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules. This
holds stage 2, in the same shape: the answer, the versions, the exact command,
the evidence, and the charter impact.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Machine nixpkgs | `/nix/store/ifpab9hxqmk2biwy594da8ipxzsp3y4s-source` |
| Dagu | 2.15.0, from `nix/dagu.nix` |
| devenv | 2.1.2 |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5`, merged to `main` mid-session |

---

## S1 — The registry recorded the inputs to §7.3's resolution, never its outcome

**Answer:** schema 1 could not answer four of `CONCEPT.md` §10's six `doctor`
checks, and check 4 — "shadowed files and their drift" — was not computable from
it at all. **Schema 2 adds a `workflows` map** recording, per workflow name, the
group that won, the groups it displaced, and the store path of the winning file.
§12.4's measurement reads the same field.

**What schema 1 held:**

```json
{ "schema": 1, "project": "devman", "path": "...", "groups": ["base"],
  "plan": "/nix/store/...", "local": [] }
```

`groups` and `local` are the **inputs** to §7.3. Nothing recorded the outcome.
To diff a repository's `.devman/workflows/check.yaml` against the group version
it shadows, something has to say which group version that was — and with two
groups in the list, `groups` alone does not: `check` may come from either.

**Command:** a throwaway repository taking both groups, so the shadowing is
live.

```bash
# /tmp/s2t/projS/devenv.nix — groups = [ "base" "python" ]
devenv shell -- true
cat /tmp/s2t/registry/projects/s2-projS/metadata.json
```

**Evidence:**

```json
{
  "schema": 2,
  "project": "s2-projS",
  "path": "/tmp/s2t/projS",
  "groups": ["base","python"],
  "plan": "/nix/store/m6339aijmhs5rjqfcs86sq37vbwswrdv-devman-project-s2-projS",
  "local": [],
  "workflows": {
    "check":     {"group":"python","shadows":["base"],"source":".../devman-python-check.yaml"},
    "full-test": {"group":"base",  "shadows":[],      "source":".../devman-base-full-test.yaml"},
    "validate":  {"group":"python","shadows":["base"],"source":".../devman-python-validate.yaml"}
  }
}
```

That is §7.3's table from the `python` group README, on disk, derived rather
than written down.

**`local` and `workflows` are read together.** A name in `local` is the winner;
`workflows.<name>.source` is then what it shadows, which is the left-hand side
of the drift diff. Nix knows the group half at evaluation time. Which files sit
in a working tree is a run-time fact, so `local` is still filled by the hook.

**What it costs.** Nothing forks. The entry is a larger string, expanded twice
per shell entry by the same two bash parameter substitutions. Re-measured
against criterion 7 in S3.

**Charter impact:** **none.** §10 states what `doctor` must compute; §9.2 calls
`metadata.json` "identity and path" without fixing a schema. This makes §10
check 4 computable rather than changing what it asks for.

---

## S2 — `artifacts/` and `reports/` had no owner

**Answer:** §9.2's `.devman/.runs/` layout names `logs/`, `artifacts/` and
`reports/`. Stage 1 shipped only what Dagu makes for itself: `log_dir` creates
`logs/`, and `base.yaml`'s exit handler appends `metadata.jsonl`. Nothing
created the other two. **Registration now creates all three**, on the projection
script's rare path.

**A step addresses them with the names §7.1 already makes global**, so the
closed list of three stays closed:

```yaml
run: mytool --out "$DEVMAN_PROJECT_DIR/.devman/.runs/artifacts/x.json"
```

`DEVMAN_PROJECT_DIR` is global name 2 and `.devman/.runs/` is global name 3. No
fourth name, and no absolute path in any workflow file (criterion 10). A
relative path works too, because a step's `working_dir` is the project — but it
breaks the moment a step `cd`s, and the variable does not.

**Where the `mkdir` goes, and why not in `base.yaml`.** The registration hook
may not fork (C1, C2), and `mkdir` forks. The projection script may: it runs
only when the rendered entry differs from disk. Putting it in `base.yaml`'s
handler instead would fork once per run, for a directory that changes once per
repository.

**Evidence**, in this repository, after one shell entry:

```
$ find .devman -maxdepth 2 | sort
.devman
.devman/.runs
.devman/.runs/artifacts
.devman/.runs/logs
.devman/.runs/metadata.jsonl
.devman/.runs/reports
$ git status --porcelain
 M modules/devenv.nix          <- the tree is otherwise clean
```

The tree stays clean because registration writes `.devman/.runs/` to
`.git/info/exclude`, and git does not track an empty directory, so a repository
whose `.devman/` holds only `.runs/` shows nothing at all.

**The limit, stated rather than fixed.** The three directories are created when
the entry changes, not on every entry. Delete `.runs/` by hand and Dagu remakes
`logs/` on the next run while `artifacts/` and `reports/` stay missing until the
repository re-registers. That is §9.3's "inconvenient, not catastrophic" at its
smallest scale, and making it a per-entry check would cost a fork on the hot
path to defend against a hand-deletion.

**Charter impact:** **none.** §9.2 already names the three directories.

---

## S3 — Criterion 7, re-measured against schema 2

**Answer:** the entry grew by roughly 600 bytes and the cost is still not
distinguishable from zero. **300 paired entries: -2.57 ms, 95% CI
[-12.23, +7.08].** Criterion 7 allows 10 ms.

**Tested:** devenv 2.1.2, warm cache, 10 warm-up entries per variant discarded,
two repositories byte-identical apart from `devman.enable`, both importing the
module so the delta is registration alone rather than the cost of the input.

**Command:** the variants interleave one entry at a time, because C2 found load
drift larger than the effect.

```bash
N=300 python3 /tmp/s2-paired.py \
  "off_enable-false|/tmp/s2-time/off" "on_schema2|/tmp/s2-time/on"
```

**Evidence:**

```
variant                      mean      sd   median    min    max   runs=300
off_enable-false            856.2    70.3    849.6    733   1346
on_schema2                  853.6    62.3    847.1    744   1346

paired delta = -2.57 ms   sd 85.32   95% CI [-12.23, +7.08]   spread [-511.9, +572.9]
```

**Two honest caveats, and the first matters more than the number.**

The absolute entry cost is **856 ms**, against the 218 ms `STAGE_1_LOG.md` S4
recorded. Nothing in the module explains that: the machine was at load average
4.4, largely from the agent session doing this work, and these repositories
carry a `path:` devman input that stage 1's did not. Criterion 7 is a paired
delta precisely because the absolute figure measures the machine.

An 80-run sweep taken first gave a 95% CI of **[-51.18, +13.92]** — wider than
the budget it is meant to test, so it bounded nothing. That is why this entry
reports 300. A run count chosen after seeing the interval is worth stating.

The upper bound of the 300-run interval is **+7.08 ms**, inside the 10 ms
budget. The sign of the point estimate is again negative and again meaningless:
the effect is far smaller than the noise.

**Charter impact:** **none.** Criterion 7 still holds.

---

## S4 — `devenv tasks run` captures a task's stdout, so every workflow logged `{}`

**Answer:** the plane's logs were empty of everything a developer reads.
`devenv tasks run <task>` captures the task's **stdout** and never prints it —
on the success path and the failure path alike — so a step running
`ruff check .` produced a log containing `{}` and nothing else. **`-v` fixes it,
and it fixes it cleanly**, because the task's stdout and devenv's debug log go
to different streams and Dagu files those separately. Every group file changed.

**Tested:** devenv 2.1.2.

**Command:** a real tool rather than an `echo`, in this repository, whose
`base:lint` is `ruff check .`.

**Evidence:**

```
$ devenv shell -- ruff check .
All checks passed!                 <- what the tool says

$ devenv tasks run base:lint
{}                                 <- what the workflow step logged
```

The `{}` is devenv's task-output object. The tool's own line is gone.

### It is not a success-path cosmetic

A task that writes to both streams and exits 3:

```
$ devenv tasks run python:lint          ; echo "EXIT=$?"
STDERR-marker
✖ Running tasks in 13.8ms (failed)
  × Some tasks failed
EXIT=1
```

The exit code is right and propagates, so the gate always worked. **What is
lost is the reason**, and ruff, mypy, basedpyright and pytest all write their
findings to stdout.

### The flag whose help is wrong

`--show-output` documents itself as "Show task output for all tasks (equivalent
to `--verbose` for tasks)". It is not:

```
mode 'plain'          STDOUT-marker occurrences: 0
mode '--show-output'  STDOUT-marker occurrences: 0
mode '-v'             STDOUT-marker occurrences: 1
```

### Why `-v` costs almost nothing on 2.1.2, and rather more on 2.2.0

`-v` adds 41 lines of devenv machinery. On **2.1.2** they do not land where a
developer looks, because the two streams separate:

```
$ devenv tasks run -v python:lint 2>/dev/null      # STDOUT only
STDOUT-marker
{}

$ devenv tasks run -v python:lint 2>&1 1>/dev/null | wc -l   # STDERR only
43
```

Dagu writes a step's `.out` and `.err` to separate files, so the file holding
the findings gains one `{}` line and the noise stays in the other. On the
failure path the same separation holds, and the exit code is still 1.

**It does not hold on devenv 2.2.0, and that is worth knowing before the
machine's devenv moves.** 2.2.0 was built from `github:cachix/devenv/v2.2`
(`2.2.0+ffce215`) and run against the same repository:

| devenv | plain | `--show-output` | `-v` |
|---|---|---|---|
| 2.1.2 | stdout lost | stdout lost | task stdout on **stdout** |
| 2.2.0 | stdout lost | stdout lost | task stdout on **stderr** |

```
$ devenv-2.2.0 tasks run -v python:lint 2>/dev/null | grep -c STDOUT-marker
0
$ devenv-2.2.0 tasks run -v python:lint 2>&1        | grep -c STDOUT-marker
1
```

So `-v` restores the findings on both versions, and only 2.1.2 keeps them clean
of the debug log. The group files say so rather than resting on the separation.
This machine runs **2.1.2** today; `nix-meta` pins devenv v2.2 as a flake input,
and `profiles/developer.nix` installs nixpkgs' `devenv`, which is 2.1.2.

### The step this does not fix

`devenv test` captures **both** of `enterTest`'s streams and prints neither,
with `-v` or without:

```
$ devenv test          ; echo "EXIT=$?"     # enterTest writes to both, exits 7
✖ Tests failed :(
  × Tests failed
EXIT=1                                       <- correct, and unexplained
$ devenv test -v 2>&1 | grep -c TEST-STDOUT
0
```

`base/full-test.yaml`'s third step keeps it. The exit code is correct, so the
gate works, and the developer re-runs `devenv test` by hand to see why. The
alternative — replacing it with the repository's own test command — is a second
call path, which §6 exists to forbid.

### Which of the three legitimate answers this is

Answer 3: **the group file was wrong and should change for everyone**
(`STAGE_2_PROMPT.md` §11). It is not a per-repository misfit — no repository
would want the other behaviour — and it needs neither a devman-specific key nor
a Nix option that rewrites the file. All five shipped workflows changed, and
`nix flake check`'s `groups-validate` still passes.

**Charter impact:** **none**, and worth a sentence if §6 is next edited. §6's
"prefer `devenv tasks run python:test`" is right, and the plain form of that
command hides the output of what it ran.

---

## S5 — Two groups cost two names, not two bodies

**Answer:** a devenv task needs no `exec`. One declaring only `after` runs its
dependency and then does nothing itself, and a failing dependency still fails
the run. So S7's "five names for three commands" is a naming cost rather than a
duplication cost.

**Tested:** devenv 2.1.2.

**Command:**

```nix
tasks."python:lint".exec = "echo RAN-python-lint";
tasks."base:lint".after  = [ "python:lint" ];      # no exec at all
```

```bash
devenv tasks run -v base:lint
```

**Evidence:**

```
• Running python:lint
• execute command
RAN-python-lint
✓ Running python:lint in 16.6ms
Running task 'base:lint' with exec_if_modified: [], status: false
• Running base:lint
✓ Running base:lint in 4.80µs (no command)
```

And the failure propagates rather than being swallowed by the empty task:

```
✖ Running python:lint in 8.97ms (failed)
✖ Running base:lint in 1.52µs (dependency failed)
EXIT=1
```

**What it does not change.** §7.4's "to be rid of one, do not take its group"
is still the cheapest answer, and an inherited workflow that is never triggered
still costs nothing. What it removes is the objection to taking both groups
deliberately — for base's `full-test` — which S7 priced at five bodies and is
really five names and two extra lines.

**Charter impact:** **none.** Both group READMEs record it.

---

## S6 — Five repositories, chosen for decomposition rather than convenience

**Answer:** five adopted, plus devman itself. **Nothing in any group file
mentions ruff, mypy, pytest, shellcheck, shfmt, Hugo, maturin, cargo or Nix**,
and the same three unedited files now serve four different toolchains.

`~/Documents/Projects` holds 68 checkouts and `devenv.nix` appears in most, so
the choice was deliberate. Five Python libraries would have answered a narrower
question than §12.4 asks.

| # | Repo | Shape | Groups | What the names map onto |
|---|---|---|---|---|
| 1 | `observantic` | plain Python library, no verification tasks of its own | `python` | `uv run ruff check .`, `uv run mypy`, `uv run pytest` |
| 2 | `pydantree` | Python library, uv workspace, own venv tasks, **no tool config** | `base`+`python` | `ruff check .`, **`mypy src`**, `pytest`, plus two alias tasks |
| 3 | `pyjutsu` | Python **and Rust**, compiled extension, own `pyjutsu:` namespace | `base` | aliases onto `pyjutsu:lint` / `pyjutsu:test` |
| 4 | `siteman` | **no Python at all** — shell scripts, shellcheck, shfmt, Hugo | `base` | `fmt-check && lint`, `ci` |
| 5 | `nix-paseo` | **no application source** — a flake and NixOS modules | `base` | `nix flake check --no-build`, `nix flake check` |

`fsdantic` was passed over deliberately. It carries a `.devman/store/`, so
§15.2's whitelist refuses it — that is the rule working, and widening the
whitelist to adopt one repository would delete the sentence the rule exists for.

### What "three lines" actually cost, per repository

`STAGE_2_PROMPT.md` fact 4 says three lines plus the group's task names, and
that held. The full cost of each adoption:

| Repo | devenv.yaml | devenv.nix | Total |
|---|---|---|---|
| observantic | input + 1 import line | 3 lines + 3 tasks | 5 declarations |
| pydantree | input + 1 import line | 3 lines + 3 tasks + 2 aliases | 7 |
| pyjutsu | input + 1 import line | 3 lines + 2 aliases + 1 ordering fix | 5 |
| siteman | input + 1 import line | 3 lines + 2 tasks | 4 |
| nix-paseo | input + 1 import line | 3 lines + 2 tasks | 4 |

**No repository wrote a line of Dagu YAML**, and none needed a per-workflow
option. Criterion 2 holds with fact 4's caveat, which is a real one and belongs
in the sentence rather than in a footnote.

### The three things a real repository needed that a throwaway did not

1. **`mypy src`, not `mypy`.** pydantree has no `[tool.mypy]` in
   `pyproject.toml`, so a bare invocation has nothing to check. The group file
   names a task and never a tool or its arguments — which is exactly why it did
   not have to change.
2. **An ordering that already existed twice.** pyjutsu's `enterTest` ran
   `maturin develop` before pytest, while `pyjutsu:test` did not, so
   `devenv tasks run pyjutsu:test` tested whatever was last built. §6 says a
   repo with genuinely internal ordering expresses it as a task dependency and
   exposes one task; `pyjutsu:test` now declares `after = [ "pyjutsu:build" ]`.
   **This is a change to someone else's repository beyond adoption**, committed
   there and not pushed.
3. **A repository with no unit tests at all.** siteman's `base:test` is its `ci`
   script, because its test *is* an offline end-to-end build. This is the one
   adoption that creates redundancy — see S9.

### The registry, with five projects in it

```
$ ls ~/.local/share/devman/dags/ | wc -l
17
```

Six projects, seventeen uniquely-named DAGs. **Five of them project a
`check.yaml`**, which under the layout `CONCEPT.md` §9.2 originally described
would have collided: `duplicate DAG name "check"`, and all five gone from
`dagu ls`, from the web UI and from the scheduler. S1 predicted this would fire
"the moment a second repository adopts the plane". It is now five deep and the
flat `dags/<project>-<workflow>.yaml` view holds.

**Charter impact:** **none.**

---

## S7 — The two decisions with no measurement to force them

### Decision 2 — this repository keeps importing `./modules`

`STAGE_2_PROMPT.md` §7 offers two readings and asks for one. **Taken: the local
checkout is the rev, so criterion 1 holds and the local import is the honest
expression of it.**

The reason is not the ~20 ms an input costs. It is that a pinned self-import
makes the plane unable to develop itself: every group-file edit would need a
commit, a push and a re-pin before it could be run once. S4 is the case in
point — the `-v` fix was found by editing a group file and re-entering a shell,
which a pinned self-import forbids. S8 of stage 1 built `builtins.readFile`
into the module for exactly this path, and measured that it works.

**The honest statement of criterion 1 that follows:** the machine and this
repository import the same rev **whenever this repository's working tree is
clean and pushed**. It was, at `b5e4aad`, when the five repositories were
pinned. The failure mode is real and worth naming: a dirty tree means devman
runs group files that no other repository has, and nothing says so.

### Decision 3 — the main checkout owns `project = "devman"`

The registry holds one `path` per project, so two live checkouts cannot both be
it. **Decided: the tracked `devenv.nix` names `devman`, and it belongs to the
durable checkout — `/home/andrew/Documents/Projects/devman`.** A paseo worktree
is transient, and a registry entry pointing at a deleted worktree is a workflow
that keeps passing in an empty directory, which nothing but §10's stale-entry
check ever notices.

The entry currently points at this worktree, because the main checkout is on
`spike/agent-factory-round-trip` and does not carry the module. That resolves
itself when the branch lands: whichever checkout enters a shell second is
refused, and the refusal names both paths.

**§9.1's refusal stays the mechanism, and it was tested against a real second
checkout** rather than a throwaway:

```
$ git worktree add --detach /tmp/s2-devman-second HEAD
$ cd /tmp/s2-devman-second && devenv shell -- true
devman: refusing to register 'devman'
devman:   already registered at /home/andrew/.paseo/worktrees/1n48r26y/special-dragon, which still exists
devman:   this repo is        /tmp/s2-devman-second
devman:   set a different devman.project in one of them

$ devenv shell -- echo "SHELL STILL OPENED"
SHELL STILL OPENED                       <- a refusal does not stop the shell
```

The registry's `path` was unchanged afterwards.

**And the escape hatch, for a worktree that does want its own membership.**
`devenv.local.nix` is read and is untracked, which is the right shape — but the
tracked `devenv.nix` defines `devman.project` at normal priority, so overriding
it needs `lib.mkForce`. Without it devenv refuses to evaluate at all:

```
error: The option `devman.project' has conflicting definition values:
       - In `<unknown-file>': "devman-worktree-probe"
       - In `<unknown-file>': "devman"
```

That failure is loud, which is the right kind. With `mkForce` the second
checkout registers as a distinct project.

**A prefix collision, tested for free while that probe existed.** The projection
removes a `dags/` link only when it still points at its own project's file,
because `<project>-<workflow>` is ambiguous when one project name is a prefix of
another. `devman` and `devman-worktree-probe` are exactly that pair, and it is
the first time the case has been live rather than commented:

```
probe links before:                          3
probe links after devman re-projected:       3
```

**Charter impact:** **none.** Both decisions are choices the charter leaves open.
