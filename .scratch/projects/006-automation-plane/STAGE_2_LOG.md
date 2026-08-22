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

---

## S8 — §11's `doctor` check forbids the thing §11 recommends

**Answer:** `CONCEPT.md` §11 states A6's role-based rule in its body and A4's
superseded rule in its closing line. Writing the first real cross-repo workflow
made them collide: the file §11's body prescribes is a file §11's last sentence
declares broken.

**The two sentences, both in §11, four paragraphs apart:**

> **`DEVMAN_PROJECT_DIR` names the project a run targets, and is set only by
> whatever triggers the run. […] A parent directs a child with `with.params`.**

> `doctor` checks it mechanically (§10) — any workflow containing
> `action: dag.run` must **not also mention** `DEVMAN_PROJECT_DIR`.

A parent cannot direct a child with `with.params` without mentioning the name.
The second sentence is A4's original rule — "must not define
`DEVMAN_PROJECT_DIR`, in `params`, in `env:`, or in `working_dir`" — which A6
explicitly superseded:

> **Recommended over A4's rule** […] This keeps the contract at one name for the
> common case, keeps cross-repo workflows ordinary files, and gains the ability
> to point a child at a different project.

The reconciliation applied A6's rule to §11's body and left A4's rule in the
`doctor` sentence.

**Command:** the check, run as written, against the file §11 asks for.

**Evidence:**

```
$ grep -c 'action: dag.run' .devman/workflows/stack-validate.yaml
2
$ grep -n 'DEVMAN_PROJECT_DIR' .devman/workflows/stack-validate.yaml
54:        DEVMAN_PROJECT_DIR: ${OBSERVANTIC_DIR}
61:        DEVMAN_PROJECT_DIR: ${SITEMAN_DIR}
```

Both mentions are inside a step's `with.params`. The rule as written reports the
only correct cross-repo workflow in the repository as broken, and a `doctor`
that cries wolf on the one file it was written for is worse than no check.

**What the check should be**, and it is still mechanical and still one grep:

> A workflow containing `action: dag.run` must not define `DEVMAN_PROJECT_DIR`
> **for itself** — not in top-level `params:`, not in `env:`, not in
> `working_dir`, not in `log_dir`. Inside a step's `with.params` the name is
> **correct**: that is how a parent directs a child.

The distinction is exactly the one A6 measured. A parent that *holds* the name
drags every child into its own directory, silently. A parent that *passes* the
name in `with.params` directs one child deliberately, which is the behaviour
§11's "synchronized releases and coordinated migrations" depend on.

**Charter impact:** **changes §11.** Applied in its own commit, per
`STAGE_2_PROMPT.md` rule 4.

---

## S9 — Criterion 5, shadowing is exact

**Answer:** **holds.** A group file copied into `.devman/workflows/` unedited
projects byte-for-byte identically. Edit one step and exactly that step changes.

**Measured in a throwaway repository on purpose.** The five adopted repositories
are §12.4's sample, and a shadow created to test the mechanism rather than
because a repository needed one would be a fabricated data point in the very
measurement this stage exists to make.

**Command:** a repo taking `[ "base" "python" ]`, so the file being copied is
already the winner of a shadow.

```bash
cp "$(readlink -f $REG/projects/s2-projS/workflows/check.yaml)" .devman/workflows/check.yaml
devenv shell -- true
diff "$SRC" "$REG/projects/s2-projS/workflows/check.yaml"
```

**Evidence — the unedited copy:**

```
$ readlink $REG/projects/s2-projS/workflows/check.yaml
/tmp/s2t/projS/.devman/workflows/check.yaml      <- the repo's file now wins
$ readlink $REG/dags/s2-projS-check.yaml
../projects/s2-projS/workflows/check.yaml        <- the flat view follows
$ diff "$SRC" "$REG/.../check.yaml" && echo IDENTICAL
IDENTICAL
```

and the registry records both halves of what `doctor` needs:

```
"local": ["check"]
check -> {'group': 'python', 'shadows': ['base'],
          'source': '/nix/store/...-devman-python-check.yaml'}
```

`local` names the winner; `source` names what it shadows.

**Evidence — one step edited:**

```diff
--- /nix/store/...-devman-python-check.yaml
+++ /tmp/s2t/registry/projects/s2-projS/workflows/check.yaml
@@ -8,4 +8,4 @@
    - name: typecheck
-    run: devenv tasks run python:typecheck
+    run: devenv tasks run python:typecheck --verbose
```

Two changed lines in the unified diff, and nothing else moved.

**One thing worth stating, because it is not obvious from §7.3.** The edit was
live **without re-projection**. The projection is a symlink into the working
tree, so editing a shadowing file changes what Dagu reads immediately; the
rendered entry does not change, so the guard takes the silent branch and the
projection script never runs. The entry only has to notice a file being **added
or removed**, which is what `local` is for.

**Charter impact:** **none.** Criterion 5 holds.

---

## S10 — The plane, running, and criterion 6

**Answer:** the service came up on the real ports and **criterion 6 holds**. One
group file, unedited, ran correctly in all five adopted repositories — four
Python/Rust/shell/Nix toolchains, and not one of them needed the file changed.

**Command:** `nixos-rebuild switch` (the user's), then the hand trigger from
`.devman/workflows/README.md`.

**Evidence — the service:**

```
$ systemctl --user is-active dagu
active
$ ss -ltnp | grep -E ':(8080|50055)'
LISTEN 127.0.0.1:50055  users:(("dagu",pid=655128,fd=3))
LISTEN 127.0.0.1:8080   users:(("dagu",pid=655128,fd=11))
$ dagu ls | wc -l ; dagu ls | grep -c '^example-'
18
0
```

`skip_examples` held (stage 1 S9), `$HOME` expanded correctly in `dags_dir`, and
there were **no duplicate-name warnings** with five projects each projecting a
`check.yaml`. S1 predicted that collision would fire "the moment a second
repository adopts the plane"; the flat `dags/` view carried it five deep.

**Evidence — criterion 6, five repositories, one unedited `check.yaml`:**

| repo | group | result |
|---|---|---|
| observantic | python | Succeeded |
| siteman | base | Succeeded |
| nix-paseo | base | Succeeded |
| pyjutsu | base | Succeeded |
| pydantree | python | **Failed** — 920 ruff findings |

pydantree's failure is a **correct run of a correct file**. Criterion 6 asks
that a group file runs correctly, not that every repository passes.

### The evidence that S4's fix was worth making

The whole point of S4 was that the log used to hold `{}`. It now holds the
tool's own output, on both paths:

```
$ cat observantic/.devman/.runs/logs/.../lint.*.out
All checks passed!
{}
$ cat observantic/.devman/.runs/logs/.../typecheck.*.out
Success: no issues found in 10 source files
{}

$ wc -l < pydantree/.devman/.runs/logs/.../lint.*.out
15824                                    <- ruff's 920 findings, in the log
```

### The trigger, checked the way §8 says to

A green run is not evidence the trigger was right. It was:

```
$ tail -1 observantic/.devman/.runs/metadata.jsonl
{"dag":"observantic-check", ... "status":"succeeded",
 "log":"/home/andrew/Documents/Projects/observantic/.devman/.runs/logs/..."}
$ find / -type d -name '${DEVMAN_PROJECT_DIR}'
(nothing)
$ git status --porcelain          # in each of the five
(clean)
```

Logs in the project that triggered the run, `metadata.jsonl` written by
`base.yaml`'s handler and by no workflow, no literally-named directory, and no
repository dirtied by a run.

**Charter impact:** **none.** Criterion 6 holds.

---

## S11 — Criterion 12, three ways

**Answer:** **holds.** Two workflows in two different projects, both naming
`exclusive`, serialize strictly when enqueued — and the control shows it is the
queue doing it rather than everything serializing.

**Command:** two throwaway projects, `groups = [ ]`, each carrying its own
`exclusive.yaml` and `light.yaml`, registered through the ordinary shell-entry
path and triggered through the real trigger. Each step records an epoch
timestamp at start and at end.

**Evidence — `exclusive`, `max_concurrency: 1`, enqueued:**

```
START s2q-a 1787418909.562398254
END   s2q-a 1787418914.573887734
START s2q-b 1787418915.571360665     <- 0.997s AFTER a ended
END   s2q-b 1787418920.581408341
```

**Evidence — `light`, `max_concurrency: 4`, the control:**

```
START s2q-b 1787418949.583006689
START s2q-a 1787418949.585829576     <- 3ms apart, fully overlapped
END   s2q-b 1787418954.592264384
END   s2q-a 1787418954.593605742
```

The queue enforces the configured number, not a fixed one.

**Evidence — the same two `exclusive` DAGs via `dagu start` instead:**

```
START s2q-b 1787418987.082046559
START s2q-a 1787418987.088674604     <- 6ms apart. The queue is bypassed.
END   s2q-b 1787418992.092759400
END   s2q-a 1787418992.099545848
```

A6 measured this on a hand-started Dagu; it reproduces on the real service. It
is why the trigger convention is `enqueue` and why `devman run` must never grow
a `--now` that calls `start`.

Two different projects, not two runs of one DAG: `max_active_runs` governs one
DAG and is deprecated, while the queue governs across DAGs, and across-DAGs is
the claim.

**Charter impact:** **none.** Criterion 12 holds.

---

## S12 — Criterion 16 ran, and took the whole DAG down with it

**Answer:** the cross-repo workflow's children both succeeded in the right
directories — and the run reported **Failed**, because `base.yaml`'s exit handler
cannot write anywhere. §11's rule and §9.2's handler were incompatible, and
nothing but running it would have shown that.

**Evidence — the first run:**

```
├─observantic-check (…) [succeeded]  subdag: … [DEVMAN_PROJECT_DIR="…/observantic"]
├─siteman-check     (1.0s) [succeeded]  subdag: … [DEVMAN_PROJECT_DIR="…/siteman"]
└─onExit (0s) [failed]
  │   /tmp/dagu_script-291123385.sh:1: no such file or directory:
  │   /.devman/.runs/metadata.jsonl
  └─error: exit status 1

Result: Failed
```

§11 forbids a cross-repo workflow from holding `DEVMAN_PROJECT_DIR`, because a
parent exports its parameters into every child's environment and outranks the
child's own `with.params`. `base.yaml`'s handler appends to
`"$DEVMAN_PROJECT_DIR/.devman/.runs/metadata.jsonl"`. With the variable unset
that is `/.devman/.runs/metadata.jsonl`, the append fails, and a failed exit
handler fails the run. **Every cross-repo workflow would have reported Failed,
forever, after doing its work perfectly.**

### The fix, and the measurement that constrained it

`${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}` in the handler. It works because a
handler's `run:` is a bash script (S2).

**It does not generalise to `working_dir`, and that was measured rather than
assumed.** Dagu does **not** support shell-style defaults:

```yaml
working_dir: ${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}
```

```
$ pwd -P        # inside the step
/home/andrew/.paseo/worktrees/1n48r26y/special-dragon/${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}
```

The whole string is kept literal and treated as a **relative path**. That is the
same documentation/behaviour gap E2 found for `$(…)` and backticks, in a third
form. So a cross-repo workflow still states its own `working_dir` and `log_dir`,
and only the handler gets the fallback.

**Evidence — after the fix**, applied by hand to `base.yaml` and re-run:

```
└─onExit (0s) [succeeded]
Result: Succeeded

$ tail -1 devman/.devman/.runs/metadata.jsonl
{"dag":"devman-stack-validate", … "status":"succeeded", …}
```

**And `base.yaml` is read per run, not at startup.** The service was not
restarted between the failing and the succeeding run. That is worth recording
beside §5.2's "the instance `config.yaml` is read only at startup", because the
two files behave differently and only one of them needs a restart.

### `DEVMAN_SELF_DIR` is now a global name, so §7.1's list is four

§11 already required "a second name" and never said which. A workflow choosing
its own would silently not be recorded, because the machine's handler has to
know it. The machine states it once, which is §7.1's own design principle.

### What a child run does NOT produce, which §9.2 half-predicted

A child triggered by `action: dag.run` does its work in the right directory and
leaves **nothing** in that project:

```
$ cat observantic/.devman/.runs/metadata.jsonl        # after the cross-repo run
{"dag":"observantic-check", "run_id":"034Bfuyz…"}     <- only the standalone run
$ ls observantic/.devman/.runs/logs/
observantic-check                                     <- only the standalone run

$ grep -rl <child-run-id> $DAGU_HOME/data
…/dag-runs/devman-stack-validate/dag-runs/…/sub/<child-run-id>/…/status.jsonl
```

§9.2 predicted this for **history** — "a child run is stored nested under its
parent's record". It is also true of the **logs and `metadata.jsonl`**, for the
same reason A3 and E2 give: `log_dir` is resolved by the process that enqueues,
and for a child that process is the parent's. The run output of a cross-repo run
lands entirely in the parent's project, which is defensible — one run, one
place — but a developer looking in `observantic` for why a stack validation
failed will find nothing, so it has to be written down.

**Charter impact:** **changes §7.1, §9.2 and §11.** Applied in its own commit.

---

## S13 — Criteria 15 and 17, at eight projects

**Answer:** **both hold.** Deleting Dagu's state *and* the registry, then
entering eight shells, restored the plane **byte for byte**.

**Command:**

```bash
rm -rf ~/.local/share/dagu ~/.local/share/devman
systemctl --user restart dagu
# then `devenv shell -- true` in each of the eight registered checkouts
```

**Evidence — immediately after the delete:**

```
$ dagu ls
Rebuilding DAG definition index dir=/home/andrew/.local/share/devman/dags
No DAGs found
```

The service came back up and recreated its two directories from `ExecStartPre`;
the registry was empty, so the plane knew nothing.

**Evidence — after eight shell entries:**

```
before: 44 links, 8 entries, 22 DAGs
after : 44 links, 8 entries, 22 DAGs

LINKS:   identical
ENTRIES: identical
DAGU LS: identical
```

Every symlink and its target, every `metadata.json`, and Dagu's own view — all
three compared byte for byte, all three unchanged. Stage 1's S10 proved this
with three throwaway repositories; this is eight, five of them real.

**And every workflow runs again**, which is the half of criterion 15 that a
directory comparison does not show:

```
observantic-check  Result: Succeeded
siteman-check      Result: Succeeded
```

**What was NOT lost, which is the point of §9.2's two locations.** Run output is
repo-side, so deleting all machine-side state cost nothing:

```
observantic  metadata.jsonl 2 lines   logs/ 1 workflow
siteman      metadata.jsonl 2 lines   logs/ 1 workflow
```

**One thing the exercise demonstrated by accident.** The restart reinstalled
`base.yaml` from the Nix store, discarding the hand-applied S12 fix. That is
`ExecStartPre` doing its job — the store is the source of truth for that file,
and the fix has to ship in the module and arrive by rebuild.

**Charter impact:** **none.** Criteria 15 and 17 hold.

---

## S14 — §12.4, the measurement

> **§12.4 — how many files were overridden across five repos, and how much of
> each is unchanged from the group version?**

**Answer: one file, out of eighteen projected workflows across six projects.
Seven of its nine executable lines are unchanged.** §12.4 asked whether
whole-file shadowing is coarse enough to live with. On this sample it is —
**and the sample is one, so the question is answered weakly and should stay
open.**

**Command:** the measurement reads devman's own registry. Schema 2 (S1) records
per workflow the group that won and the store path of its file; `local` records
which names the repository shadowed or invented. Read together they are exactly
what §12.4 asks for, which is why schema 2 was built before this was run.

```bash
python3 /tmp/s2-124.py     # reads ~/.local/share/devman/projects/*/metadata.json
```

**Evidence:**

```
projects measured  : 6
workflows projected: 18
files OVERRIDDEN   : 1
files INVENTED     : 1   (new names, nothing to diff)

executable lines only (blank and comment lines dropped):
project     workflow    shadows   group repo same  unchanged  whole file
siteman     full-test   base          9    7    7      77.8%       59.3%
```

The two throwaway projects built for S11 are excluded; they are instruments.

**Both percentages are given because the gap between them is the story.** The
group files are mostly comment — 27 lines, 9 of them executable — so a
whole-file figure measures documentation rather than duplication. §12.4's
failure mode is "a file copied to change one line", and on the executable
content this file is exactly that: **77.8% unchanged, and the change is a
deletion, not an edit.**

### The one override, and why it is honest

Four of the five repositories overrode nothing. The fifth did, and it took real
pressure to get there rather than a decision to produce a data point:

```
siteman full-test, unshadowed:  lint 1.0s   test 3.0s   devenv-test 14.0s   = 20.5s
siteman `devenv shell -- ci`:                                                 2.9s
siteman full-test, shadowed:    lint 2.0s   test 3.0s                       = 9.5s
```

`base/full-test.yaml`'s third step is `devenv test`. siteman's `enterTest` **is**
`ci`, which `base:test` already ran two steps earlier — so the step spent 14
seconds re-running finished work and, because `devenv test` captures both of
`enterTest`'s streams (S4), printed nothing while doing it.

### What the shape of the single data point suggests

§12.4 states what the answer decides: *"If it is common, the fix is smaller group
files — split `check.yaml` into what varies and what does not — not a merge
algorithm."*

One override in eighteen is **not common**, so nothing is forced. But the shape
is worth recording, because if it repeats it points at a specific remedy rather
than a general one:

> The override deleted a **step that did not apply**. It did not edit a step. A
> merge algorithm would not have helped — there was nothing to merge. Smaller
> group files would have: had `full-test` been two files, siteman would have
> taken one and shadowed nothing.

So the single data point argues for §12.4's own predicted fix, and against the
one it rules out. That is weak evidence and it is stated as weak.

### Why this is a "for want of pressure" result and not a clean pass

`STAGE_2_PROMPT.md` §6 anticipated the zero case: *"If nobody overrode anything,
that is also a result — it means the groups fit, and it means §12.4 stays open
for want of pressure rather than being answered."* This is very nearly that
case, and three things about the sample limit what it can support:

1. **The group files are small.** `check` is one step. There is little in them
   to disagree with, so the low override rate partly measures how little the
   groups attempt.
2. **The repositories were adopted by the same person, in one sitting**, who
   chose each repository's task names knowing what the group files said. A
   repository adopted by someone defending an existing CI would push harder.
3. **`full-test` is the only workflow with a step a repository cannot redefine**
   through task names — and it is the only file anybody overrode. That is not a
   coincidence and it is the whole mechanism §7.1 rests on: a step that names a
   *task* bends to the repository, and a step that names a *command* does not.

Point 3 is the transferable finding. **The group files that survived contact are
the ones made entirely of task names.**

**Charter impact:** **none, and §16 should say so.** §12.4 remains the open
question; it now has one data point instead of none, and a sharper statement of
what would close it.

---

## S15 — §9.2's exact failure, reproduced by the author of the fix

**Answer:** a probe run with `DEVMAN_PROJECT_DIR` unset created a directory
named literally `${DEVMAN_PROJECT_DIR}` **inside this repository**, and it was
committed. That is the failure §9.2 records as already having happened here
once — "two Dagu run logs were committed before anyone noticed" — recurring by a
route the fix for the first one does not cover.

**How it happened.** S12's probe deliberately ran without
`DEVMAN_PROJECT_DIR` to test whether Dagu supports shell-style defaults. It does
not, so `working_dir` resolved to a relative path and `log_dir` — inherited from
`base.yaml`, which names the unset variable — was created literally:

```
${DEVMAN_PROJECT_DIR}/.devman/.runs/logs/s2-fallback-probe/.../where.*.out
```

A later `git add -A` swept it in. Five files, two lines of content.

### Why the ignore rule did not stop it

`.git/info/exclude` holds `.devman/.runs/`, written by registration. The stray
path is `${DEVMAN_PROJECT_DIR}/.devman/.runs/…` — a different prefix, so the
pattern does not match. **The rule protects the correctly-named directory and
nothing else**, which is exactly right and exactly insufficient.

### What was NOT done about it, and why

Adding `${DEVMAN_PROJECT_DIR}/` to the exclude rule would stop the accident and
is the wrong fix. **The directory is a symptom of a broken trigger**, and
`git status` showing it as untracked is the only cheap signal that a trigger
forgot the environment variable. Ignoring it would make an error condition
invisible in the one place a developer looks daily.

§10's `doctor` check 3 exists for this — "look for a directory named literally
`${DEVMAN_PROJECT_DIR}`" — and it has now fired against a real occurrence rather
than a hypothetical one. Two things follow, both for stage 3:

1. **`devman run` should refuse to enqueue when `DEVMAN_PROJECT_DIR` is unset
   and the workflow does not set `DEVMAN_SELF_DIR`.** Prevention belongs in the
   one place that triggers a workflow, not in an ignore file.
2. **`doctor` check 3 should search the registered repositories**, not only the
   daemon's working directory. This one landed inside a project.

### And a process note, recorded because the rule is explicit

`STAGE_2_PROMPT.md` rule 4 says a `CONCEPT.md` change goes in its own commit.
Commit `26f50cd` carried the charter change **and** `nix/nixos-module.nix`'s
handler fix together, because the same `git add -A` that swept up the stray
directory also swept up the module. Splitting it afterwards would have meant
rewriting already-pushed history, which is a worse trade than the untidiness, so
the split was not made. The module fix and the charter change are described
separately above (S12) and the commit message describes only one of them.

**Charter impact:** **none.** §9.2's rule and §10's check 3 are both confirmed
by this, and neither changes.
