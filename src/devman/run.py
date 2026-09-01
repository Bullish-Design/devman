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

from .registry import Project, Registry, RegistryError, dag_name_fault
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
    # The codec's one refusal, at the trigger. The module refuses the same name
    # at evaluation time, so this fires only for a projection written before the
    # codec landed — and it is still a refusal rather than a fallback, because
    # such a name has no unambiguous DAG to enqueue (§9.2).
    name_fault = dag_name_fault(workflow)
    if name_fault:
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n  {name_fault}"
        )

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

    # A DAG name is machine-global, so the file this resolved is not necessarily
    # the file Dagu will run: a second project owning the `dags/` link makes the
    # run execute another project's workflow, in this project's directory, and
    # report success (`STAGE_5_LOG.md`, S6). The codec ends that by construction
    # (§9.2, S-12); this still checks, because the link is what Dagu reads and
    # the codec is only what the projection wrote it with.
    dag = reg.dag_name(project, workflow)
    fault = reg.dag_link_fault(project, workflow)

    # The codec landed in S-12 and the projection runs on shell entry, so the
    # machine holds both name shapes until every repository has been entered
    # again. Falling back is what stops that being a flag day — but it is said
    # out loud, because a trigger quietly using a name the plane no longer
    # projects is exactly the silent-default habit §12 rule 4 refuses.
    if fault and reg.unmigrated(project, workflow):
        dag = reg.legacy_dag_name(project, workflow)
        fault = None
        print(
            f"devman run: '{project.name}' still projects under the pre-codec"
            f" DAG name — enqueueing {dag}.\n"
            f"  enter its shell once to re-project it as {reg.dag_name(project, workflow)}"
            " (§9.2)",
            file=sys.stderr,
        )

    if fault:
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  the DAG named {dag} points at {fault}\n"
            f"  it resolved to {path}, and that is not what would run\n"
            "  enter this repository's shell to re-project it; if it persists,"
            " two projects render one DAG name (§9.2)"
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
    known = reg.projects()

    # 009 P1-2 and P2-6, which are one defect: caller input used to be applied
    # to the parameter map AFTER the safety derivation, and no parameter was
    # constrained at all. `DEVMAN_PROJECT_DIR=/elsewhere` retargeted the run
    # itself; an ordinary name such as `OBSERVANTIC_DIR` retargeted a child of a
    # cross-repo parent, where no literal `working_dir` blunts it
    # (`.devman/workflows/stack-validate.yaml`). One rule closes both halves:
    #
    #   a reserved name accepts no override; a parameter whose default names a
    #   registered project accepts only another registered project's name; every
    #   other override must name a declared parameter.
    #
    # There is deliberately no blanket update of the map from `overrides` below.
    # Each override is consumed inside the declared loop, so a later refactor has
    # nothing to reintroduce. `test_the_blanket_update_is_gone` keeps it that way.
    held_reserved = sorted(k for k in overrides if k in (PROJECT_DIR, SELF_DIR))
    if held_reserved:
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  these names are the plane's, not the caller's:"
            f" {', '.join(held_reserved)}\n"
            f"  the directory a workflow runs in is the directory of the project"
            f" it resolved from ({project.path})\n"
            "  to run it elsewhere, name that project: devman run"
            f" {workflow} --project NAME (§7.2, §11)"
        )

    unknown = sorted(k for k in overrides if k not in declared)
    if unknown:
        # An override that names nothing is a typo, and Dagu finds it later,
        # elsewhere, and unexplained (E5).
        declared_names = ", ".join(sorted(declared)) or "none"
        raise RegistryError(
            f"refusing to enqueue '{workflow}' in '{project.name}'\n"
            f"  these overrides name no declared parameter: {', '.join(unknown)}\n"
            f"  this workflow declares: {declared_names}"
        )

    # The directory variable is passed whether the file declares it or not: an
    # ordinary workflow declares nothing at all and inherits `working_dir` and
    # `log_dir` from the machine's base.yaml, which name it (§7.2, E4).
    params: dict[str, str] = {dir_var: str(project.path)}

    for name, default in declared.items():
        if name == dir_var:
            continue
        # A parameter whose default names a registered project is filled with
        # that project's path. It is the convention `.devman/workflows/README.md`
        # writes out by hand, moved into the one place that triggers a workflow —
        # and it keeps criterion 10 (no absolute path in a workflow file), since
        # a project name is an identity and only the registry resolves it (§9.1).
        if default in known:
            # Such a parameter stays an identity when the caller overrides it.
            # An absolute path here is the wrong-tree run this design refuses.
            given = overrides.get(name, default)
            if given not in known:
                raise RegistryError(
                    f"refusing to enqueue '{workflow}' in '{project.name}'\n"
                    f"  {name} defaults to the registered project '{default}',"
                    f" so it names a project — '{given}' is not one\n"
                    f"  registered: {', '.join(sorted(known))}\n"
                    "  only the registry resolves a project name to a path (§9.1)"
                )
            params[name] = str(known[given].path)
        else:
            params[name] = overrides.get(name, default)

    # The second layer. These two are no longer reachable from caller input —
    # they fire on a registry entry whose path has gone, which is the state
    # `doctor --prune` reconciles.
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

    return dag, params, dir_var


def assert_target(project: Project, params: dict[str, str], dir_var: str) -> None:
    """The last line before the irreversible boundary.

    Earlier validation does not survive a later mutation, which is exactly what
    009 P1-2 was: `resolve()` derived the directory safely and then applied the
    caller's overrides on top of it. The safe invariant is not "the value is a
    directory". It is "the value is the directory of the project whose workflow
    was resolved".
    """
    target = params.get(dir_var, "")
    if target != str(project.path):
        raise RegistryError(
            f"refusing to enqueue in '{project.name}'\n"
            f"  {dir_var} would be '{target}', and the project resolved to"
            f" {project.path}\n"
            "  something changed the parameters after they were derived (P1-2)"
        )


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

    **`SHELL` is cleared for the same reason, and it is a third thing baked at
    enqueue time.** Dagu resolves a step's shell from `$SHELL` and falls back to
    the instance's `default_shell` only when `$SHELL` is unset — and, like
    `log_dir`, it reads that from whichever process enqueues. So without this
    line every workflow step on the machine runs under the login shell of
    whoever happened to trigger it: a developer's zsh at a prompt, the systemd
    user manager's copy of it under the watcher, and the machine's `bash` only
    when the daemon itself enqueues. A group file would then have to be correct
    in every shell any user of the machine might log in with.

    Clearing it rather than setting it is deliberate. The machine already states
    the shell once, as `default_shell` in `config.yaml` (§7.1's shape), and a
    second statement here would be a store path compiled into the CLI and a
    value to keep in step. Measured on the rebuilt machine: with `SHELL` set the
    step ran zsh, with it unset the step ran the `default_shell` bash
    (`STAGE_4_LOG.md`, S13).
    """
    env = dict(os.environ)
    env.pop(PROJECT_DIR, None)
    env.pop(SELF_DIR, None)
    env.pop("SHELL", None)
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
    # Before `command()` and before the `--print` branch, so neither path can
    # skip it.
    assert_target(project, params, dir_var)
    argv = command(reg, args.dagu_home, dag, params)

    if args.print_only:
        print(" ".join([f"{dir_var}={params[dir_var]}", *argv]))
        return 0

    return subprocess.run(argv, env=child_env(params, dir_var), check=False).returncode
