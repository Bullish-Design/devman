# STAGE 3 — what was measured while making the plane react

`STAGE_1_LOG.md` holds what stage 1 found while building the two modules and
`STAGE_2_LOG.md` holds what stage 2 found while turning the plane on. This holds
stage 3, in the same shape: the answer, the versions, the exact command, the
evidence, and the charter impact.

**Environment for every entry below**, unless it says otherwise:

| Fact | Value |
|---|---|
| Host | NixOS 26.11.20260705, hostname `server`, Nix 2.34.7 |
| Dagu | 2.15.0, installed, running as `systemd --user` unit `dagu` |
| devenv | 2.1.2 |
| watchexec | 2.5.1 (nixpkgs) |
| Registry | `~/.local/share/devman/` — 6 projects, 18 DAGs |
| Date | 2026-08-22 |
| devman rev | branch `dagu-devenv-automation-eli5` |

---

## S1 — `dagu dry` creates the literally-named directory, so nothing may call it

**Answer:** `dagu dry` documents itself as a simulation "without producing any
side effects", and it **creates `log_dir`** — which, for a workflow whose
directory variable is unset, is a directory named literally
`${DEVMAN_SELF_DIR}`. That is S15's symptom, produced by the one command in the
CLI that looks safe to call. **No devman command may run `dagu dry`.**

**Why it was run at all.** `devman run` has to know a workflow's declared
parameters (§10, and the cross-repo convention `.devman/workflows/README.md`
writes out by hand). `dagu dry` prints them, which would have let devman read
Dagu's own view of a file rather than read the file — the same "read rather than
compute" rule E5 sets for `doctor`.

**Command**, run from `/tmp` so that whatever it created would be visible:

```bash
cd /tmp && dagu dry ~/.local/share/devman/dags/devman-stack-validate.yaml
```

**Evidence — it does print the parameters:**

```
msg="Dry-run completed" dag=devman-stack-validate
    params="[DEVMAN_SELF_DIR= OBSERVANTIC_DIR= SITEMAN_DIR=]"
Result: Succeeded
```

**Evidence — and it writes:**

```
$ find '/tmp/${DEVMAN_SELF_DIR}'
/tmp/${DEVMAN_SELF_DIR}
/tmp/${DEVMAN_SELF_DIR}/.devman
/tmp/${DEVMAN_SELF_DIR}/.devman/.runs
/tmp/${DEVMAN_SELF_DIR}/.devman/.runs/logs/devman-stack-validate/dag-run_.../dag-run_....log
```

A simulation that resolves no step still resolves `log_dir` and creates it. The
directory was removed by hand.

**What it decides.** `devman run` reads the workflow's own top-level `params:`
block instead. That is not §7.2's forbidden parse — §7.2 forbids the plane
*understanding* a workflow, and §10 already has `doctor` reading workflow text
for §11's `action: dag.run` check. Reading the parameters a file declares is
reading what the trigger is required to fill in.

**Charter impact:** **none.** §7.2 already records that an unresolved variable
is not an error in Dagu; this is a sixth documentation/behaviour gap in the same
family as E2's `$(…)` and backticks, and it names one more command `doctor`
should never call.

---

## S2 — An unset `DAGU_HOME` gives a trigger its own empty, example-seeded Dagu

**Answer:** a bare `dagu` in an ordinary shell does not talk to the plane. It
creates `~/.config/dagu/`, writes a `base.yaml` of its own, **seeds the five
example DAGs**, and lists nothing. So a trigger that inherits the ambient
`DAGU_HOME` enqueues into whichever Dagu the caller happened to have — and when
the caller has none, into a Dagu that has never heard of the registry.
**`devman run` must state `--dagu-home` rather than inherit it.**

**Command:** an ordinary non-login shell, with no `DAGU_HOME` exported.

**Evidence:**

```
$ echo "DAGU_HOME=$DAGU_HOME"
DAGU_HOME=
$ command -v dagu
/run/current-system/sw/bin/dagu          <- the plane's own client (installClient)
$ dagu ls
level=WARN msg="No auth.mode configured — defaulting to 'builtin'."
level=INFO msg="Creating example DAGs for first-time users" dir=/home/andrew/.config/dagu/dags
level=INFO msg="Rebuilding DAG definition index" dir=/home/andrew/.config/dagu/dags
NAME
                                          <- no DAGs. The registry is elsewhere.
$ ls -a ~/.config/dagu ~/.config/dagu/dags
.base-config-created  base.yaml  dags
.dag.index  .examples-created  example-01-basic-sequential.yaml  … (five)
```

The stray home was removed by hand afterwards.

**Two things follow, and the second is the sharper one.**

1. **`skip_examples` is per instance, not per machine** (S9 of stage 1). The
   plane sets it in its own `config.yaml`; a Dagu started against a different
   `DAGU_HOME` never reads that file, so the flag cannot protect it.
2. **The trigger's target must be stated by the plane, not by the caller's
   environment.** `STAGE_3_PROMPT.md` §4 tells a reader to `export DAGU_HOME`
   before talking to the plane, which is right for a person at a prompt and
   wrong as a dependency for a program. The watcher runs from a systemd unit,
   a VCS hook runs from git, and a developer runs `devman run` from a devenv
   shell — three environments, and only one of them is the plane's.

**And this repository sets the variable to something else.** `devenv.nix` still
carries `env.DAGU_HOME = "${config.devenv.state}/dagu"` from the investigation
period, when the plane was started by hand from `processes.dagu`. That process
is gone (§13 stage-1 cleanup 2) and the variable outlived it, so inside this
repository's shell `dagu ls` reports the devenv state directory's DAGU_HOME
rather than the plane's.

**Charter impact:** **none.** §8 already says a trigger is a local process
running `dagu enqueue`; this says which Dagu it must enqueue into and how it
says so.
