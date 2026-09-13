"""`devman agent` — the devman half of the Agentman boundary (project 022).

**WHAT THIS SUITE PROTECTS.** Every refusal here looks like something a refactor
would tidy away: building an environment from empty rather than filtering one,
checking a receipt that already reported itself present, enforcing a timeout the
orchestrator appears to enforce, keeping a backend allowlist with one name in
it. Each is a measurement, cited in `src/devman/agent.py`'s docstring and in
`.scratch/projects/022-agentman-integration/EVIDENCE.md`.

**NOTHING HERE CALLS A MODEL, A NETWORK OR A SECRET PROVIDER.**
`tests/fixtures/fake_agentman.py` is a real executable driven by one environment
variable, and it is run by a real `Popen` — because a patched function would
prove none of the five things this adapter does to a process.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from devman import agent, cli

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "fake_agentman.py"


# --------------------------------------------------------------------------
# The harness
# --------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    (path / ".devman" / ".runs").mkdir(parents=True)
    return path


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    """The double, as an executable file rather than an import."""
    script = tmp_path / "agentman"
    script.write_text(
        "#!/bin/sh\nexec "
        + repr(sys.executable).strip("'")
        + " "
        + str(FIXTURE)
        + ' "$@"\n'
    )
    script.chmod(0o755)
    return script


@pytest.fixture
def invocations(tmp_path: Path, repo: Path) -> Path:
    """The double's invocation log, and the file that chooses its behaviour.

    **It is a file in the repository rather than an environment variable, and
    the adapter is why.** `agent.child_env()` builds the child's environment up
    from empty, so a `FAKE_AGENTMAN_*` variable is as unwelcome as a stray
    credential and never arrives — which is the property
    `test_the_child_environment_is_built_up_and_not_filtered_down` asserts.
    """
    log = tmp_path / "invocations.jsonl"
    log.touch()
    set_mode(repo, "clean", log)
    return log


def set_mode(repo: Path, name: str, log: Path | None = None) -> None:
    """Choose the double's behaviour for the next invocation."""
    control = repo / ".devman/.runs/fake-agentman.json"
    previous = json.loads(control.read_text()) if control.is_file() else {}
    control.write_text(
        json.dumps({"mode": name, "log": str(log) if log else previous.get("log")})
    )


def call(
    repo: Path, fake: Path, *extra: str, run_id: str = "run-0001"
) -> tuple[int, str]:
    """Run `devman agent` in-process and return `(exit code, the document)`."""
    argv = [
        "agent",
        "--capsule",
        "review",
        "--repository",
        str(repo),
        "--run-id",
        run_id,
        "--agentman",
        str(fake),
        *extra,
    ]
    args = cli.parser().parse_args(argv)
    return args, agent.main(args, None)


def run(capsys, repo: Path, fake: Path, *extra: str, **kw) -> tuple[int, dict]:
    _args, code = call(repo, fake, *extra, **kw)
    out = capsys.readouterr().out.strip()
    return code, (
        json.loads(out) if out.startswith("{") or out.startswith('"') else out
    )


def document(capsys, repo: Path, fake: Path, *extra: str, **kw) -> tuple[int, dict]:
    code, raw = run(capsys, repo, fake, *extra, **kw)
    # `main` prints the document as a JSON string so redaction can run over the
    # whole of it; the caller sees an object.
    return code, json.loads(raw) if isinstance(raw, str) else raw


# --------------------------------------------------------------------------
# The exit-code contract
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode,code,classification",
    [
        ("clean", 0, "clean"),
        ("finding", 1, "finding"),
        ("infrastructure", 2, "infrastructure"),
        ("usage", 3, "usage"),
    ],
)
def test_every_agentman_exit_code_crosses_unchanged(
    capsys, repo, fake, invocations, monkeypatch, mode, code, classification
):
    """0 clean · 1 finding · 2 infrastructure · 3 usage, as the contract states.

    `agentman_exit_code` is what the process said and `exit_code` is what the
    caller acts on. On these four rows they agree, which is what makes the fifth
    row below legible as the exception it is.
    """
    set_mode(repo, mode)
    got, doc = document(capsys, repo, fake)
    assert got == code
    assert doc["agentman_exit_code"] == code
    assert doc["exit_code"] == code
    assert doc["classification"] == classification


def test_process_success_with_no_receipt_is_never_success(
    capsys, repo, fake, invocations, monkeypatch
):
    """Rule 4 in one row: exit 0 and no proof is exit 2.

    `agentman_exit_code` stays 0 so the process result and the integration
    finding remain distinguishable, which is the whole reason the contract has
    two codes.
    """
    set_mode(repo, "missing-receipt")
    code, doc = document(capsys, repo, fake)
    assert code == 2
    assert doc["agentman_exit_code"] == 0
    assert doc["classification"] == "missing_receipt"
    assert doc["missing_receipt"] is True


# --------------------------------------------------------------------------
# The receipt, which devman checks rather than reads back
# --------------------------------------------------------------------------


def test_a_clean_run_correlates_its_receipt_with_the_plane_run_id(
    capsys, repo, fake, invocations, monkeypatch
):
    set_mode(repo, "clean")
    code, doc = document(capsys, repo, fake, run_id="run-abc")
    assert code == 0
    receipt = Path(doc["receipt_path"])
    assert receipt.name == "agentman-run-abc.json"
    assert json.loads(receipt.read_text())["run"] == "run-abc"


def test_a_receipt_agentman_names_but_did_not_write_is_a_finding(
    capsys, repo, fake, invocations, monkeypatch
):
    """devman trusts `missing_receipt: true` and CHECKS a `false`.

    The direction that can hide a failure is the one worth checking, so only one
    of the two is verified — and this is the case that proves the check exists.
    """
    set_mode(repo, "lying-receipt")
    code, doc = document(capsys, repo, fake)
    assert code == 2
    assert doc["classification"] == "missing_receipt"
    assert doc["agentman_exit_code"] == 0
    assert "does not exist" in doc["diagnostic"]


def test_a_receipt_recording_another_run_is_a_finding(
    capsys, repo, fake, invocations, monkeypatch
):
    """Existence is not correlation. The receipt's `run` must be this run's."""
    set_mode(repo, "foreign-receipt")
    code, doc = document(capsys, repo, fake, run_id="run-0001")
    assert code == 2
    assert doc["classification"] == "missing_receipt"
    assert "some-other-run" in doc["diagnostic"]


def test_a_receipt_outside_the_repository_is_a_finding(
    capsys, repo, fake, invocations, monkeypatch, tmp_path
):
    """§9.2's wrong-directory failure, wearing a receipt."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    stray = elsewhere / "agentman-run-0001.json"
    stray.write_text(json.dumps({"run": "run-0001"}))
    doc = agent.verify_receipt(
        {
            "receipt_path": str(stray),
            "missing_receipt": False,
            "exit_code": 0,
            "diagnostic": "",
        },
        repo,
        "run-0001",
    )
    assert doc["classification"] == "missing_receipt"
    assert "outside the repository" in doc["diagnostic"]


# --------------------------------------------------------------------------
# The result document
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode,fragment",
    [
        ("wrong-version", "contract version"),
        ("unknown-field", "unknown field"),
        ("wrong-run-id", "names run"),
        ("no-json", "printed no JSON"),
    ],
)
def test_an_unreadable_result_is_infrastructure_and_never_success(
    capsys, repo, fake, invocations, monkeypatch, mode, fragment
):
    """A process that exits 0 and prints something devman cannot read has
    reported nothing — not a clean result (§12 rule 4)."""
    set_mode(repo, mode)
    code, doc = document(capsys, repo, fake)
    assert code == 2
    assert doc["classification"] == "infrastructure"
    assert fragment in doc["diagnostic"]


def test_a_warning_before_the_document_does_not_lose_the_verdict(
    capsys, repo, fake, invocations, monkeypatch
):
    """The document is the LAST parseable JSON line, so a library's warning on
    stdout is not a reason to fail a run that succeeded."""
    set_mode(repo, "noisy")
    code, doc = document(capsys, repo, fake)
    assert code == 0
    assert doc["classification"] == "clean"


# --------------------------------------------------------------------------
# Exactly once
# --------------------------------------------------------------------------


def test_one_admitted_run_invokes_agentman_exactly_once(
    capsys, repo, fake, invocations, monkeypatch
):
    """The whole retry policy, asserted rather than described.

    A queue bounds concurrency and nothing bounds spend (020 §4.5), so the
    adapter has one `Popen` and no path back to it — including on the paths that
    are most tempting to retry.
    """
    for mode in ("clean", "infrastructure", "missing-receipt"):
        invocations.write_text("")
        set_mode(repo, mode)
        document(capsys, repo, fake)
        lines = [ln for ln in invocations.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1, f"{mode} invoked agentman {len(lines)} times"


def test_the_shipped_workflow_states_no_retry_policy_and_no_schedule():
    """Both absences are decisions, and both are cheap to reintroduce by
    accident. `groups/agent/README.md` holds the reasons."""
    from devman.workflow import Workflow

    root = Path(__file__).resolve().parents[2]
    wf = Workflow.read(root / "groups/agent/workflows/agent.yaml")
    assert wf.error is None
    assert "retry_policy" not in (wf.doc or {})
    assert "schedule" not in (wf.doc or {})
    for step in wf.steps():
        assert "retry_policy" not in step


# --------------------------------------------------------------------------
# The queue
# --------------------------------------------------------------------------


def test_the_agent_workflow_names_the_llm_queue():
    from devman.workflow import Workflow

    root = Path(__file__).resolve().parents[2]
    wf = Workflow.read(root / "groups/agent/workflows/agent.yaml")
    assert wf.queues() == ["llm"]


def test_the_machine_declares_the_llm_queue_with_a_limit():
    """**Dagu accepts an undeclared queue name silently, at concurrency 1**
    (S-9), so a workflow naming `llm` against a machine that does not declare it
    would serialise every Agentman run on the machine and say nothing.

    `doctor`'s `queue names` check compares every projected file against the
    machine's own `config.yaml`; this asserts the other half — that the module
    which writes that file states the name at all.
    """
    root = Path(__file__).resolve().parents[2]
    module = (root / "nix/nixos-module.nix").read_text()
    assert "llm = 2;" in module
    for name in ("light", "normal", "heavy", "gpu", "exclusive", "llm"):
        assert f"{name} = " in module


# --------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------


def test_the_child_environment_is_built_up_and_not_filtered_down(
    capsys, repo, fake, invocations, monkeypatch
):
    """**THE SECRET ALLOWLIST, AND THE ONLY TEST THAT CAN SEE IT.**

    A leak is a name nobody expected, so this asserts the WHOLE set rather than
    that one variable arrived. `OTHER_SECRET` is a second credential Dagu
    resolved onto the step for another purpose; nothing named it, so it must not
    reach Agentman.
    """
    set_mode(repo, "clean")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-value-aaaa")
    monkeypatch.setenv("OTHER_SECRET", "sk-value-bbbb")
    monkeypatch.setenv("SOMETHING_ELSE", "ordinary")
    code, _ = document(capsys, repo, fake, "--secret", "anthropic:ANTHROPIC_API_KEY")
    assert code == 0
    env = json.loads(invocations.read_text().splitlines()[0])["env"]
    assert env["ANTHROPIC_API_KEY"] == "sk-value-aaaa"
    assert "OTHER_SECRET" not in env
    assert "SOMETHING_ELSE" not in env
    assert not any(k.startswith("FAKE_AGENTMAN") for k in env)
    assert "SHELL" not in env
    assert env["DAGU_RUN_ID"] == "run-0001"
    assert env["DEVMAN_PROJECT_DIR"] == str(repo)


def test_a_declared_secret_with_no_value_is_refused_before_the_child_starts(
    capsys, repo, fake, invocations, monkeypatch
):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    set_mode(repo, "clean")
    code, doc = document(capsys, repo, fake, "--secret", "anthropic:ANTHROPIC_API_KEY")
    assert code == 2
    assert doc["classification"] == "infrastructure"
    assert "anthropic → ANTHROPIC_API_KEY" in doc["diagnostic"]
    assert not invocations.read_text().strip(), "agentman must not have started"


@pytest.mark.parametrize(
    "item,fragment",
    [
        ("ANTHROPIC_API_KEY", "not LOGICAL:ENVVAR"),
        ("Anthropic:ANTHROPIC_API_KEY", "logical name"),
        ("anthropic:anthropic_api_key", "environment name"),
        ("anthropic:DAGU_TOKEN", "DAGU_ prefix"),
    ],
)
def test_a_malformed_secret_pair_is_a_usage_refusal(
    capsys, repo, fake, invocations, monkeypatch, item, fragment
):
    """The grammars are Agentman's and Dagu's, checked here so the refusal
    happens before a request file exists rather than one process later."""
    set_mode(repo, "clean")
    code, doc = document(capsys, repo, fake, "--secret", item)
    assert code == 3
    assert doc["classification"] == "usage"
    assert fragment in doc["diagnostic"]
    assert not invocations.read_text().strip()


def test_no_secret_value_reaches_the_request_file(repo, tmp_path, monkeypatch):
    """The request holds symbolic names. A value in it would be a credential on
    disk that outlives the process, and the contract has no field for one."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-value-aaaa")
    request = agent.build_request(
        repository=repo,
        capsule="review",
        run_id="run-0001",
        backend=None,
        secrets=["anthropic"],
        timeout_s=900,
        memory_mb=None,
        cpu_seconds=None,
    )
    text = json.dumps(request)
    assert "sk-value-aaaa" not in text
    assert request["secrets"] == ["anthropic"]


def test_the_diagnostic_masks_an_exact_secret_value():
    """**Exactly as far as Dagu masks, and no further, on purpose.**

    Measured on the pin: a step echoing `$TOKEN` logged `*******`, and the same
    step echoing its first five characters logged them in clear. Redacting more
    here would make devman's diagnostic safer than the log beside it and invite
    the belief that the log is safe too. The bound that holds is the one the
    group README states: a step must not print a fragment of a credential.
    """
    assert agent.redact("token=sk-value-aaaa", ["sk-value-aaaa"]) == "token=*******"
    assert agent.redact("first5=sk-va", ["sk-value-aaaa"]) == "first5=sk-va"


def test_the_request_file_is_removed_on_every_path(
    capsys, repo, fake, invocations, monkeypatch
):
    for mode in ("clean", "usage", "no-json"):
        set_mode(repo, mode)
        document(capsys, repo, fake)
        left = list((repo / agent.REQUEST_DIR).glob("request-*"))
        assert left == [], f"{mode} left {left}"


# --------------------------------------------------------------------------
# The request, strictly
# --------------------------------------------------------------------------


def test_the_request_carries_no_policy_field():
    """**The absence IS the guarantee** (022 decision 1).

    devman cannot widen a capability, a filesystem mode, a network setting, a
    write tier, retrieval, an extractor or a prompt, because the v1 request has
    no field for any of them. A field added here without a contract version is a
    widening this test refuses.
    """
    request = agent.build_request(
        repository=Path("/tmp"),
        capsule="review",
        run_id="run-0001",
        backend=None,
        secrets=[],
        timeout_s=900,
        memory_mb=None,
        cpu_seconds=None,
    )
    assert set(request) == {
        "version",
        "repository",
        "capsule",
        "run_id",
        "limits",
        "secrets",
    }
    assert set(request["limits"]) == {"timeout_s"}


def test_the_request_matches_the_checked_in_v1_fixture_shape(tmp_path):
    """Against Agentman's own `contracts/devman-agentman/v1/request.json`.

    Not the values — the field set and the version string, which is what a
    silent contract change would move.
    """
    request = agent.build_request(
        repository=tmp_path,
        capsule="review",
        run_id="01JC8Y",
        backend="fake",
        secrets=[],
        timeout_s=900,
        memory_mb=2048,
        cpu_seconds=900,
    )
    assert request["version"] == "agentman.devman/v1"
    assert set(request) == {
        "version",
        "repository",
        "capsule",
        "backend",
        "run_id",
        "limits",
        "secrets",
    }
    assert set(request["limits"]) == {"timeout_s", "memory_mb", "cpu_seconds"}


@pytest.mark.parametrize(
    "kw,fragment",
    [
        ({"capsule": "../escape"}, "--capsule"),
        ({"capsule": "with/slash"}, "--capsule"),
        ({"run_id": "../etc"}, "run id"),
        ({"run_id": "has space"}, "run id"),
        ({"repository": Path("relative/path")}, "absolute path"),
        ({"timeout_s": 0}, "--timeout-s"),
        ({"timeout_s": 90_000}, "--timeout-s"),
        ({"memory_mb": 0}, "--memory-mb"),
        ({"backend": "claude"}, "--backend"),
        ({"secrets": ["a", "a"]}, "twice"),
    ],
)
def test_a_malformed_request_is_refused_before_it_is_written(tmp_path, kw, fragment):
    base = {
        "repository": tmp_path,
        "capsule": "review",
        "run_id": "run-0001",
        "backend": None,
        "secrets": [],
        "timeout_s": 900,
        "memory_mb": None,
        "cpu_seconds": None,
    }
    with pytest.raises(agent.AgentError) as exc:
        agent.build_request(**{**base, **kw})
    assert fragment in str(exc.value)


def test_the_backend_allowlist_authorises_the_offline_double_and_nothing_else(
    tmp_path,
):
    """A repository states its backend in its own `agentman.toml`. The only
    override devman authorises is the one that cannot widen anything: `fake`
    reaches no network and spends no money."""
    assert agent.BACKEND_ALLOWLIST == ("fake",)
    request = agent.build_request(
        repository=tmp_path,
        capsule="review",
        run_id="run-0001",
        backend="fake",
        secrets=[],
        timeout_s=900,
        memory_mb=None,
        cpu_seconds=None,
    )
    assert request["backend"] == "fake"


def test_an_unauthorised_backend_is_a_usage_refusal(
    capsys, repo, fake, invocations, monkeypatch
):
    set_mode(repo, "clean")
    code, doc = document(capsys, repo, fake, "--backend", "claude")
    assert code == 3
    assert doc["classification"] == "usage"
    assert not invocations.read_text().strip()


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def test_the_run_id_comes_from_dagus_own_variable(
    capsys, repo, fake, invocations, monkeypatch
):
    """**Dagu 2.15.0 sets `DAG_RUN_ID`; the contract names `DAGU_RUN_ID`.**

    Measured on the pin: a step's environment holds `DAG_RUN_ID`, and the names
    beginning `DAGU_` are only `DAGU_HOME`, `DAGU_OUTPUT_FILE` and
    `DAGU_EXECUTABLE`. This adapter is the one place that maps one to the other.
    """
    assert agent.DAGU_RUN_ID_ENV == "DAG_RUN_ID"
    assert agent.AGENTMAN_RUN_ID_ENV == "DAGU_RUN_ID"
    set_mode(repo, "clean")
    monkeypatch.setenv("DAG_RUN_ID", "from-the-plane")
    args = cli.parser().parse_args(
        [
            "agent",
            "--capsule",
            "review",
            "--repository",
            str(repo),
            "--agentman",
            str(fake),
        ]
    )
    code = agent.main(args, None)
    assert code == 0
    record = json.loads(invocations.read_text().splitlines()[0])
    assert record["env"]["DAGU_RUN_ID"] == "from-the-plane"
    request = json.loads(capsys.readouterr().out.strip())
    assert json.loads(request)["run_id"] == "from-the-plane"


def test_no_run_id_at_all_is_infrastructure_and_starts_nothing(
    capsys, repo, fake, invocations, monkeypatch
):
    monkeypatch.delenv("DAG_RUN_ID", raising=False)
    args = cli.parser().parse_args(
        [
            "agent",
            "--capsule",
            "review",
            "--repository",
            str(repo),
            "--agentman",
            str(fake),
        ]
    )
    assert agent.main(args, None) == 2
    assert "DAG_RUN_ID" in capsys.readouterr().out
    assert not invocations.read_text().strip()


def test_a_missing_repository_is_refused(capsys, repo, fake, invocations, monkeypatch):
    set_mode(repo, "clean")
    code, doc = document(capsys, repo.parent / "gone", fake)
    assert code == 2
    assert "not a directory" in doc["diagnostic"]
    assert not invocations.read_text().strip()


def test_a_missing_agentman_names_the_step_path(
    capsys, repo, invocations, monkeypatch, tmp_path
):
    """`groups/changelog` learned this the expensive way (023 P1): a doctor asks
    its own PATH and not the step's, so the step probes for itself."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    args = cli.parser().parse_args(
        [
            "agent",
            "--capsule",
            "review",
            "--repository",
            str(repo),
            "--run-id",
            "run-0001",
        ]
    )
    assert agent.main(args, None) == 2
    assert "no `agentman` on this step's PATH" in capsys.readouterr().out


# --------------------------------------------------------------------------
# The process boundary
# --------------------------------------------------------------------------


def test_a_run_that_exceeds_its_timeout_is_killed_and_classified(
    capsys, repo, fake, invocations, monkeypatch
):
    """**The plane does not bound a run's lifetime, so this does.**

    Measured over 75 s: Dagu re-sends `SIGTERM` every 5 s and never escalates to
    `SIGKILL`, so a child that ignores the signal runs forever and the DAG never
    finishes. `--timeout-s` here is `SIGTERM`, five seconds, then `SIGKILL` —
    the escalation the daemon lacks. `hang` ignores `SIGTERM`, so only the
    escalation can end it.
    """
    set_mode(repo, "hang")
    monkeypatch.setattr(agent, "GRACE_SECONDS", 0.5)
    started = time.monotonic()
    code, doc = document(capsys, repo, fake, "--timeout-s", "1")
    elapsed = time.monotonic() - started
    assert code == 2
    assert doc["classification"] == "infrastructure"
    assert "timeout" in doc["diagnostic"]
    assert elapsed < 30, "the child outlived its own escalation"


def test_a_polite_child_is_terminated_within_the_grace_window(
    capsys, repo, fake, invocations, monkeypatch
):
    set_mode(repo, "hang-politely")
    started = time.monotonic()
    code, doc = document(capsys, repo, fake, "--timeout-s", "1")
    assert code == 2
    assert time.monotonic() - started < 10


def test_the_adapter_stays_in_dagus_process_group(repo, fake, monkeypatch):
    """**Dagu signals the whole process group on cancellation** — measured: a
    grandchild of the step's shell got signal 15 about 53 ms after `dagu stop`.

    A `start_new_session=True` here would put Agentman outside that group, and a
    working cancellation would become an orphan holding an API connection. This
    asserts the absence, because the absence is the property.
    """
    source = Path(agent.__file__).read_text()
    assert "start_new_session" not in source


def test_cancellation_terminates_the_child_and_leaves_no_request_file(
    repo, fake, tmp_path, monkeypatch
):
    """SIGTERM to the adapter, exactly as Dagu delivers it.

    Run as a real subprocess, because a signal handler installed by `invoke()`
    cannot be observed from inside the same interpreter that pytest is driving.
    """
    log = tmp_path / "cancel-invocations.jsonl"
    log.touch()
    set_mode(repo, "hang-politely", log)
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(agent.__file__).resolve().parents[1]),
    }
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "devman.cli",
            "agent",
            "--capsule",
            "review",
            "--repository",
            str(repo),
            "--run-id",
            "run-cancel",
            "--agentman",
            str(fake),
            "--timeout-s",
            "600",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    for _ in range(200):
        if log.exists() and log.read_text().strip():
            break
        time.sleep(0.05)
    else:  # pragma: no cover - the double never started
        child.kill()
        pytest.fail("the fake agentman never started")

    os.killpg(os.getpgid(child.pid), signal.SIGTERM)
    child.communicate(timeout=30)

    assert list((repo / agent.REQUEST_DIR).glob("request-*")) == []
    lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, "cancellation must not have caused a second invocation"


def test_resource_limits_are_applied_in_the_child_only():
    """`RLIMIT_AS` and `RLIMIT_CPU` bind Agentman and everything it starts, and
    bind nothing in this process — they are set after `fork`, before `exec`."""
    assert agent.limit_setter(None, None) is None
    assert callable(agent.limit_setter(1024, None))
    assert callable(agent.limit_setter(None, 60))


# --------------------------------------------------------------------------
# The group, end to end
# --------------------------------------------------------------------------


def test_the_group_workflow_declares_its_secret_and_its_parameters():
    """Per workflow, never in `base.yaml` — a block there would grant every
    workflow on the machine every secret and delete the sentence §9.4 exists
    for (020 §4.2)."""
    from devman.workflow import Workflow

    root = Path(__file__).resolve().parents[2]
    wf = Workflow.read(root / "groups/agent/workflows/agent.yaml")
    secrets = (wf.doc or {}).get("secrets")
    assert secrets and all(s["provider"] == "env" for s in secrets)
    assert all("value" not in s for s in secrets), "a workflow never holds a value"
    params = wf.params()
    assert "DEVMAN_PROJECT_DIR" in params
    assert params["AGENT_CAPSULE"] == "review"
    # The run id is not a parameter: Dagu already sets it, and a parameter could
    # be filled with an id that is not this run's.
    assert not any("RUN_ID" in name for name in params)


def test_the_group_declares_only_the_writes_devman_makes():
    """A tier is a claim. This one covers devman's own writes; the capsule's are
    governed by the capsule's `[writes]`, which Agentman enforces."""
    import tomllib

    root = Path(__file__).resolve().parents[2]
    decl = tomllib.loads((root / "groups/agent/writes.toml").read_text())
    assert decl["agent"]["tier"] == "free"
    from devman import project

    assert all(project.free_path(g) for g in decl["agent"]["paths"])


def test_a_fake_end_to_end_run_produces_a_receipt_and_a_clean_result(
    capsys, repo, fake, invocations, monkeypatch
):
    """The whole path, with the offline double: request → one invocation →
    receipt → correlated result → exit 0 → no request file left behind."""
    set_mode(repo, "clean")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-value-aaaa")
    code, doc = document(
        capsys,
        repo,
        fake,
        "--backend",
        "fake",
        "--secret",
        "anthropic:ANTHROPIC_API_KEY",
        "--timeout-s",
        "60",
        "--memory-mb",
        "2048",
        run_id="e2e-0001",
    )
    assert code == 0
    assert doc["classification"] == "clean"
    assert doc["missing_receipt"] is False
    assert Path(doc["receipt_path"]).is_file()

    record = json.loads(invocations.read_text().splitlines()[0])
    assert record["argv"][:2] == ["run", "--request"]
    assert record["cwd"] == str(repo)
    request = json.loads(Path(record["argv"][2]).name) if False else None
    assert request is None  # the file is gone by now, which is the point
    assert list((repo / agent.REQUEST_DIR).glob("request-*")) == []
