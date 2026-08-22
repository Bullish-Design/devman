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

The absolute entry cost is **856 ms**, against S4's 218 ms. Nothing in the
module explains that: the machine was at load average 4.4, largely from the
agent session doing this work, and these repositories carry a `path:` devman
input that S4's did not. Criterion 7 is a paired delta precisely because the
absolute figure measures the machine.

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

### Why `-v` costs almost nothing, which is the part that decided it

`-v` adds 41 lines of devenv machinery. They do not land where a developer
looks, because the two streams separate:

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
