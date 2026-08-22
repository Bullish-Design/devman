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
