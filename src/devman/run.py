"""`devman run <workflow>` — the one place that triggers a workflow (§8, §10).

    filesystem change → watchexec ─┐
    commit / push     → hook      ─┼→ devman run → dagu enqueue → Dagu → devenv
    a developer at a prompt       ─┘

The middle layer is not a thin detector. It resolves the project, exports
`DEVMAN_PROJECT_DIR`, and passes it as a parameter — the environment reaches
`log_dir` and the parameter reaches `working_dir`, and one is not a substitute
for the other (A3, E2). Everything below exists because one of those two halves
was missing somewhere.

**`enqueue`, never `start`.** `dagu start` ignores queues entirely: two DAGs
naming `exclusive` ran 6 ms apart under `start` and serialized strictly under
`enqueue`, on the real service (A6, `STAGE_2_LOG.md` S11). Queue names are the
plane's whole lever on concurrency, so this file must never grow a `--now`.

**And it refuses rather than enqueueing a run that would write to the wrong
place.** A trigger that passes the parameter and forgets the environment leaves
a directory named literally `${DEVMAN_PROJECT_DIR}` in whatever tree the daemon
started in — which has already happened in this repository, twice, once
committed (§9.2, `STAGE_2_LOG.md` S15). Prevention belongs here, in the one
place that triggers a workflow, and not in an ignore file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .registry import Project, Registry, RegistryError
from .workflow import PROJECT_DIR, SELF_DIR, Workflow


def resolve(
    reg: Registry,
    project: Project,
    workflow: str,
    overrides: dict[str, str],
) -> tuple[str, dict[str, str], str]:
    """Everything the trigger needs, or a `RegistryError` saying what is missing.

    Returns `(dag name, parameters, the name of the directory variable)`.
    """
    path = reg.workflow_file(project, workflow)
    wf = Workflow.read(path)
    if wf.error:
        # §10 check 1's failure, arriving at the trigger instead of at `doctor`.
        # `dagu ls` lists a DAG that cannot load with no indication at all, so
        # enqueueing it would fail later, elsewhere, and unexplained (E5).
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  {path}\n"
            f"  {wf.error}\n"
            f"  run `devman doctor` to see every projected file that fails"
        )

    declared = wf.params()
    cross_repo = wf.triggers_other_dags()
    held = wf.holds_project_dir()

    # §11's rule, at the trigger. A parent exports its parameters into every
    # child's environment and that environment outranks the child's own
    # `with.params`, so a parent HOLDING the name drags every child into its own
    # directory — the children run, succeed, and do the work in the wrong place,
    # and nothing reports it.
    if cross_repo and held:
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  it triggers other workflows and defines {PROJECT_DIR} for itself,"
            f" in: {', '.join(held)}\n"
            f"  a parent names its own directory {SELF_DIR} and directs each child"
            f" with with.params (§11)"
        )
    if cross_repo and SELF_DIR not in declared:
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  it triggers other workflows and declares no {SELF_DIR} parameter\n"
            f"  such a workflow targets no project, so it names its own directory"
            f" (§11)"
        )

    dir_var = SELF_DIR if SELF_DIR in declared else PROJECT_DIR
    params: dict[str, str] = {}

    # The directory variable is passed whether the file declares it or not: an
    # ordinary workflow declares nothing at all and inherits `working_dir` and
    # `log_dir` from the machine's base.yaml, which name it (§7.2, E4).
    params[dir_var] = str(project.path)

    known = reg.projects()
    for name, default in declared.items():
        if name == dir_var:
            continue
        # A parameter whose default names a registered project is filled with
        # that project's path. It is the convention `.devman/workflows/README.md`
        # writes out by hand, moved into the one place that triggers a workflow —
        # and it keeps criterion 10 (no absolute path in a workflow file), since
        # a project name is an identity and only the registry resolves it (§9.1).
        params[name] = str(known[default].path) if default in known else default

    params.update(overrides)

    value = params.get(dir_var, "")
    if not value or not Path(value).is_dir():
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  {dir_var} would be "
            + (f"'{value}', which is not a directory" if value else "empty")
            + "\n"
            "  Dagu would create a directory named literally"
            f" ${{{dir_var}}} and report success (§7.2, §9.2)"
        )

    empty = sorted(k for k, v in params.items() if not v)
    if empty:
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  these declared parameters have no value: {', '.join(empty)}\n"
            "  give each one a registered project name as its default, or pass"
            " NAME=VALUE"
        )

    return reg.dag_name(project, workflow), params, dir_var


def command(reg: Registry, dagu: str, dag: str, params: dict[str, str]) -> list[str]:
    """The exact `dagu enqueue` a trigger runs.

    `--dagu-home` is stated rather than inherited. An unset `DAGU_HOME` makes
    `dagu` build a fresh home, seed five example DAGs, and know nothing about
    the registry; a wrong one enqueues into somebody else's Dagu (S2).
    """
    argv = [dagu_binary(), "--dagu-home", str(Path(dagu).expanduser()), "enqueue", dag]
    if params:
        argv.append("--")
        argv += [f"{k}={v}" for k, v in params.items()]
    return argv


def dagu_binary() -> str:
    """The Dagu client. The package wraps this CLI with the plane's own on PATH,
    so `devman run` and the service cannot drift to two Dagu versions."""
    return shutil.which("dagu") or "dagu"


def child_env(params: dict[str, str], dir_var: str) -> dict[str, str]:
    """The environment `dagu enqueue` runs in.

    `log_dir` is baked at enqueue time from the enqueueing process's environment
    (A3, A7), so the directory variable has to be exported here as well as
    passed as a parameter. Both of §7.1's directory names are cleared first: a
    cross-repo workflow that inherits a stray `DEVMAN_PROJECT_DIR` from the
    caller's shell sends every child into that directory, successfully and
    silently. That is the `env -u DEVMAN_PROJECT_DIR` in the hand-written
    trigger, made unnecessary to remember.
    """
    env = dict(os.environ)
    env.pop(PROJECT_DIR, None)
    env.pop(SELF_DIR, None)
    env[dir_var] = params[dir_var]
    return env


def main(args, reg: Registry) -> int:
    overrides: dict[str, str] = {}
    for item in args.params:
        if "=" not in item:
            print(f"devman run: '{item}' is not NAME=VALUE", file=sys.stderr)
            return 2
        key, _, value = item.partition("=")
        overrides[key] = value

    project = reg.project(args.project) if args.project else reg.project_for(Path.cwd())
    if not project.exists:
        raise RegistryError(
            f"refusing to enqueue in '{project.name}'\n"
            f"  its registered path {project.path} is not a directory\n"
            "  run `devman doctor --prune` to reconcile the registry (§10 check 5)"
        )

    dag, params, dir_var = resolve(reg, project, args.workflow, overrides)
    argv = command(reg, args.dagu_home, dag, params)

    if args.print_only:
        print(" ".join([f"{dir_var}={params[dir_var]}", *argv]))
        return 0

    return subprocess.run(argv, env=child_env(params, dir_var), check=False).returncode
