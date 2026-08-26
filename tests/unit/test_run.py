"""The enqueue refusal contract, and the environment the child runs in.

`run.resolve()` is the one place that decides whether a trigger fires, and every
refusal in it exists because a run once succeeded and did its work in the wrong
place. **The refusals are the contract. A test that only checked the happy path
would let a refactor delete every one of them and stay green.**
"""

from __future__ import annotations

import os

import pytest
from helpers import ORDINARY

from devman import run
from devman.registry import RegistryError
from devman.workflow import PROJECT_DIR, SELF_DIR

pytestmark = pytest.mark.unit

CROSS_REPO = f"""
params:
  - {SELF_DIR}: /tmp
steps:
  - name: a
    action: dag.run
    with:
      dag: child
      params: {{{PROJECT_DIR}: /elsewhere}}
"""


# ---------------------------------------------------------------------------
# what resolve() returns when it does not refuse


def test_an_ordinary_workflow_gets_the_project_dir(plane):
    """An ordinary workflow declares nothing at all and inherits `working_dir`
    and `log_dir` from the machine's `base.yaml`, which name the variable. So it
    is passed whether the file declares it or not (§7.2, E4)."""
    proj = plane.add("p", workflows={"check": ORDINARY})

    dag, params, dir_var = run.resolve(plane.reg, proj, "check", {})

    assert dag == plane.reg.dag_name(proj, "check")
    assert dir_var == PROJECT_DIR
    assert params == {PROJECT_DIR: str(proj.path)}


def test_a_cross_repo_parent_names_its_own_directory(plane):
    """§11: a workflow that directs others targets no project, so it names its
    own directory `DEVMAN_SELF_DIR` and directs each child with `with.params`."""
    proj = plane.add("p", workflows={"stack": CROSS_REPO})

    _, params, dir_var = run.resolve(plane.reg, proj, "stack", {})

    assert dir_var == SELF_DIR
    assert params == {SELF_DIR: str(proj.path)}
    assert PROJECT_DIR not in params


def test_a_default_naming_a_registered_project_is_filled_with_its_path(plane):
    """§8's convention, moved into the one place that triggers a workflow. It
    keeps criterion 10 — no absolute path in a workflow file — because a project
    name is an identity and only the registry resolves it (§9.1)."""
    target = plane.add("observantic")
    text = f"params:\n  - TARGET: observantic\n{ORDINARY}"
    proj = plane.add("p", workflows={"check": text})

    _, params, _ = run.resolve(plane.reg, proj, "check", {})

    assert params["TARGET"] == str(target.path)
    assert params["TARGET"] != "observantic"


def test_a_typed_default_naming_a_project_is_filled_too(plane):
    """S-10's silent half. Read as three parameters, `TARGET` was never seen and
    kept the literal string — the run succeeded in the right directory and the
    child got a project name where a path was promised."""
    target = plane.add("observantic")
    text = (
        "params:\n"
        "  - name: TARGET\n"
        "    type: string\n"
        "    default: observantic\n" + ORDINARY
    )
    proj = plane.add("p", workflows={"check": text})

    _, params, _ = run.resolve(plane.reg, proj, "check", {})

    assert params == {PROJECT_DIR: str(proj.path), "TARGET": str(target.path)}


def test_a_default_naming_no_project_is_passed_through(plane):
    text = f"params:\n  - LEVEL: warn\n{ORDINARY}"
    proj = plane.add("p", workflows={"check": text})

    _, params, _ = run.resolve(plane.reg, proj, "check", {})

    assert params["LEVEL"] == "warn"


def test_an_override_wins_over_a_default(plane):
    text = f"params:\n  - LEVEL: warn\n{ORDINARY}"
    proj = plane.add("p", workflows={"check": text})

    _, params, _ = run.resolve(plane.reg, proj, "check", {"LEVEL": "debug"})

    assert params["LEVEL"] == "debug"


# ---------------------------------------------------------------------------
# the refusals, one test each — and each asserts WHICH branch fired


def test_a_file_that_does_not_load_is_refused_at_the_trigger(plane):
    """`dagu ls` lists a DAG that cannot load with no indication at all, so
    enqueueing it would fail later, elsewhere, and unexplained (E5)."""
    proj = plane.add("p", workflows={"check": "steps: [\n"})

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "check", {})
    assert "not loadable as YAML" in str(exc.value)
    assert "devman doctor" in str(exc.value)


def test_a_cross_repo_parent_holding_the_project_dir_is_refused(plane):
    """§11's first branch. A parent exports its parameters into every child's
    environment and that environment outranks the child's own `with.params`, so
    a parent holding the name drags every child into its own directory — the
    children run, succeed, and do the work in the wrong place."""
    text = (
        f"params:\n  - {PROJECT_DIR}: /tmp\n"
        "steps:\n  - name: a\n    action: dag.run\n    with: {dag: child}\n"
    )
    proj = plane.add("p", workflows={"stack": text})

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "stack", {})
    assert f"defines {PROJECT_DIR} for itself, in: params" in str(exc.value)


def test_the_first_branch_fires_for_a_typed_parent(plane):
    """**The branch, not merely the refusal.** S-10 measured the wrong branch
    firing for the right file: `held` came back empty so §11's first branch
    missed, and `SELF_DIR not in declared` was true for the same reason, so the
    second fired. The developer was told to add a parameter the file already had.

        !!  cross-repo  ... declares no DEVMAN_SELF_DIR parameter   # old, misleading
        !!  cross-repo  ... holds DEVMAN_PROJECT_DIR in: params     # new, correct
    """
    text = (
        "params:\n"
        f"  - name: {PROJECT_DIR}\n"
        "    type: string\n"
        "    default: /tmp\n"
        "steps:\n  - name: a\n    action: dag.run\n    with: {dag: child}\n"
    )
    proj = plane.add("p", workflows={"stack": text})

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "stack", {})
    message = str(exc.value)
    assert f"defines {PROJECT_DIR} for itself, in: params" in message
    assert f"declares no {SELF_DIR} parameter" not in message


def test_a_cross_repo_parent_without_a_self_dir_is_refused(plane):
    """§11's second branch, on a file that really does declare nothing."""
    text = "steps:\n  - name: a\n    action: dag.run\n    with: {dag: child}\n"
    proj = plane.add("p", workflows={"stack": text})

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "stack", {})
    assert f"declares no {SELF_DIR} parameter" in str(exc.value)


def test_an_empty_directory_variable_is_refused(plane):
    """Dagu would create a directory named literally `${DEVMAN_PROJECT_DIR}` and
    report success. That has happened in this repository twice, once committed
    (§9.2, `STAGE_2_LOG.md` S15)."""
    proj = plane.add("p", workflows={"check": ORDINARY})

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "check", {PROJECT_DIR: ""})
    message = str(exc.value)
    assert f"{PROJECT_DIR} would be empty" in message
    assert f"${{{PROJECT_DIR}}}" in message


def test_a_directory_variable_that_is_not_a_directory_is_refused(plane, tmp_path):
    proj = plane.add("p", workflows={"check": ORDINARY})
    not_a_dir = tmp_path / "gone"

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "check", {PROJECT_DIR: str(not_a_dir)})
    assert "which is not a directory" in str(exc.value)


def test_an_empty_declared_parameter_is_refused(plane):
    """A typed definition with no default declares the parameter empty (S-10),
    and §8 says a trigger fills every parameter a file declares."""
    text = "params:\n  - name: TARGET\n    type: string\n" + ORDINARY
    proj = plane.add("p", workflows={"check": text})

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "check", {})
    message = str(exc.value)
    assert "these declared parameters have no value: TARGET" in message
    assert "pass NAME=VALUE" in message


def test_an_empty_parameter_can_be_filled_by_an_override(plane):
    text = "params:\n  - name: TARGET\n    type: string\n" + ORDINARY
    proj = plane.add("p", workflows={"check": text})

    _, params, _ = run.resolve(plane.reg, proj, "check", {"TARGET": "x"})

    assert params["TARGET"] == "x"


def test_a_projection_identity_mismatch_is_refused(plane):
    """The file this resolved is not necessarily the file Dagu will run: a second
    project rendering the same flat name owns the `dags/` link. The run then
    executes another project's workflow, in this project's directory, and reports
    success (`STAGE_5_LOG.md`, S6)."""
    plane.add("devman", workflows={"b-check": ORDINARY})
    devman_b = plane.add("devman-b", workflows={"check": ORDINARY})
    plane.link("devman-b", "check", "../projects/devman/workflows/b-check.yaml")

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, devman_b, "check", {})
    message = str(exc.value)
    assert plane.reg.dag_name(devman_b, "check") in message
    assert "that is not what would run" in message


def test_a_missing_dag_link_is_refused(plane):
    proj = plane.add("p", workflows={"check": ORDINARY}, link=False)

    with pytest.raises(RegistryError) as exc:
        run.resolve(plane.reg, proj, "check", {})
    assert "there is no dags/ link" in str(exc.value)


# ---------------------------------------------------------------------------
# command() — enqueue, never start


def test_the_command_is_enqueue_with_a_stated_dagu_home(plane, tmp_path):
    """`dagu start` ignores queues entirely: two DAGs naming `exclusive` ran 6 ms
    apart under `start` and serialised strictly under `enqueue`, on the real
    service (A6, `STAGE_2_LOG.md` S11). Queue names are the plane's whole lever
    on concurrency, so this must never grow a `--now`.

    `--dagu-home` is stated rather than inherited: an unset `DAGU_HOME` makes
    `dagu` build a fresh home and seed five example DAGs (S2).
    """
    argv = run.command(plane.reg, str(tmp_path / "home"), "p-check", {"A": "x"})

    assert os.path.basename(argv[0]) == "dagu"
    assert argv[1:5] == ["--dagu-home", str(tmp_path / "home"), "enqueue", "p-check"]
    assert argv[5:] == ["--", "A=x"]
    assert "start" not in argv


def test_the_command_expands_a_tilde_in_the_dagu_home(plane):
    argv = run.command(plane.reg, "~/.local/share/dagu", "p-check", {})
    assert argv[2] == os.path.expanduser("~/.local/share/dagu")


def test_no_parameters_means_no_separator(plane, tmp_path):
    argv = run.command(plane.reg, str(tmp_path), "p-check", {})
    assert "--" not in argv


# ---------------------------------------------------------------------------
# child_env() — three things baked at enqueue time


def test_the_inherited_directory_names_are_cleared(monkeypatch, tmp_path):
    """A cross-repo workflow that inherits a stray `DEVMAN_PROJECT_DIR` from the
    caller's shell sends every child into that directory, successfully and
    silently. This is the `env -u DEVMAN_PROJECT_DIR` in the hand-written
    trigger, made unnecessary to remember."""
    monkeypatch.setenv(PROJECT_DIR, "/somebody/elses/repo")
    monkeypatch.setenv(SELF_DIR, "/another/one")

    env = run.child_env({SELF_DIR: str(tmp_path)}, SELF_DIR)

    assert env[SELF_DIR] == str(tmp_path)
    assert PROJECT_DIR not in env


def test_shell_is_cleared(monkeypatch, tmp_path):
    """**Pin this hardest. It looks exactly like the cleanup a refactor would
    delete, and it is stage-4-measured** (`STAGE_4_LOG.md`, S13).

    Dagu resolves a step's shell from `$SHELL` and falls back to the instance's
    `default_shell` only when `$SHELL` is unset — and it reads that from
    whichever process enqueues. Without this line every workflow step on the
    machine runs under the login shell of whoever happened to trigger it: a
    developer's zsh at a prompt, the systemd user manager's copy of it under the
    watcher, and the machine's `bash` only when the daemon itself enqueues. A
    group file would then have to be correct in every shell any user of the
    machine might log in with.

    Clearing rather than setting is deliberate: the machine already states the
    shell once, as `default_shell` in `config.yaml`, and a second statement here
    would be a store path compiled into the CLI.
    """
    monkeypatch.setenv("SHELL", "/run/current-system/sw/bin/zsh")

    env = run.child_env({PROJECT_DIR: str(tmp_path)}, PROJECT_DIR)

    assert "SHELL" not in env


def test_everything_else_in_the_environment_survives(monkeypatch, tmp_path):
    """Three names are removed and nothing else is. `child_env` is not a
    sanitiser — the run needs PATH, HOME and the rest."""
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("SOME_TOKEN", "keep-me")

    env = run.child_env({PROJECT_DIR: str(tmp_path)}, PROJECT_DIR)

    assert env["PATH"] == "/usr/bin"
    assert env["SOME_TOKEN"] == "keep-me"


def test_the_process_environment_is_not_mutated(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    run.child_env({PROJECT_DIR: str(tmp_path)}, PROJECT_DIR)
    assert os.environ["SHELL"] == "/bin/zsh"
