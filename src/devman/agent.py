"""`devman agent` — one admitted run, translated into one Agentman invocation.

    devman run agent → dagu enqueue → the llm queue → this process → agentman

**THIS IS THE FOURTH COMMAND, AND §10 SAID THERE WERE THREE.** The charter's
amendment (§10, project 022) states the reason: `run`, `show` and `doctor` are
all *about* the plane, and this one runs *inside* it — it is the step of a
workflow rather than a thing a developer types. It exists because the
translation it performs is execution-plane work, and law 7 says core logic is
Python: building a strict request, filtering an environment down to a declared
allowlist, bounding a process, verifying a receipt and classifying an exit code
are five things nobody can test in a Dagu step's shell.

**WHAT THIS FILE MUST NEVER GROW.** Agentman owns capsule composition,
capability grants, filesystem, network and write-tier policy, backend selection
inside the resolved capsule, typed validation, repair attempts, and the
receipt. Nothing here reads a `capsule.toml`, and nothing here may widen a
grant. The request carries references and never policy, which is the property
that makes that guarantee structural rather than a promise.

---------------------------------------------------------------------------
THE FIVE MEASUREMENTS THIS FILE IS BUILT ON (022, `EVIDENCE.md`)

1. **Dagu 2.15.0 sets `DAG_RUN_ID` in a step's environment, not `DAGU_RUN_ID`.**
   Measured: a step printing `env | grep '^DAGU'` shows exactly `DAGU_HOME`,
   `DAGU_OUTPUT_FILE` and `DAGU_EXECUTABLE`, and `$DAG_RUN_ID` holds the run id.
   The Agentman contract names `DAGU_RUN_ID`. **This file is the one place that
   maps one to the other**, so neither side carries the other's spelling.

2. **Dagu cancels with `SIGTERM`, to the whole process group.** Measured: a
   grandchild of the step's shell received signal 15 about 53 ms after
   `dagu stop`, and the daemon logged
   `stop-mode=graceful signal=terminated allow-override=true`. So the Agentman
   child and its backend do receive the signal, and this process receives it at
   the same moment. It must therefore clean up rather than assume it will run
   its `finally` at leisure.

3. **Dagu never escalates to `SIGKILL`.** Measured over 75 s against a child
   that ignores `SIGTERM`: Dagu re-sent `SIGTERM` every 5 s
   (`max-cleanup-time=5s`, the default) and the DAG never finished. **So the
   plane cannot bound an Agentman run's lifetime and this process must.**
   `--timeout-s` is enforced here, with a real kill, and it is not decoration.

4. **Dagu masks a resolved secret's EXACT value, and only that.** Measured: a
   step echoing `$PROBE_TOKEN` logged `*******`, and the same step echoing its
   first five characters logged them in clear. Redaction here states the same
   limit rather than claiming more.

5. **A scheduled run bypasses its queue** (020, and re-measured on this pin:
   two DAGs naming a `max_concurrency: 1` queue ran four times concurrently
   under `schedule:`). `groups/agent/` therefore ships no `schedule:` at all,
   and every Agentman run reaches Dagu through `devman run`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from types import FrameType

from .registry import Registry, RegistryError
from .workflow import PROJECT_DIR

#: The versioned boundary this file implements, both ways. A document carrying
#: any other value is refused rather than coerced: `agentman/contracts/
#: devman-agentman/v1/README.md` says a changed field needs a new version, so a
#: version devman does not know is a contract devman cannot read.
CONTRACT_VERSION = "agentman.devman/v1"

#: Dagu's own name for the run id in a step's environment (measurement 1).
DAGU_RUN_ID_ENV = "DAG_RUN_ID"

#: The Agentman contract's name for the same value. This process sets it.
AGENTMAN_RUN_ID_ENV = "DAGU_RUN_ID"

#: A logical secret name. Agentman's `Secret.name` pattern, stated here so the
#: refusal happens before a request file exists.
SECRET_NAME = re.compile(r"^[a-z][a-z0-9_.-]*$")

#: A target environment variable. Agentman's `Secret.environment` pattern.
#: Dagu's own `secretRef.name` is wider (`^[A-Za-z_][A-Za-z0-9_]*$`) and
#: additionally forbids a `DAGU_` prefix, so a name accepted here is accepted by
#: both — which is the point of stating the narrower one.
SECRET_ENV = re.compile(r"^[A-Z][A-Z0-9_]*$")

#: The contract's own grammars, so a malformed value is a devman refusal rather
#: than an Agentman usage error discovered one process later.
CAPSULE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")

#: **THE WHOLE BACKEND POLICY, AND IT IS ONE NAME.**
#:
#: A repository states its backend in its own `agentman.toml`, and that is
#: composition — Agentman's, not the plane's. The only override devman
#: authorises is the offline test double, because it is the one change that
#: cannot widen anything: `fake` reaches no network and spends no money. An
#: override to a real backend would let a workflow parameter choose what a run
#: costs, which is the opposite of a narrowing.
BACKEND_ALLOWLIST = ("fake",)

#: Where the request file goes. Inside `.devman/.runs/`, which the plane created,
#: git ignores and the watcher ignores — so writing here cannot fire a run
#: (§9.2, §8's second loop).
REQUEST_DIR = Path(".devman/.runs/agent")

#: How long a terminated child gets before it is killed. Dagu's own default
#: cleanup window (measurement 3), reused so the two layers do not disagree
#: about what "graceful" means.
GRACE_SECONDS = 5.0

#: The classifications the v1 result schema permits.
CLASSIFICATIONS = ("clean", "finding", "infrastructure", "usage", "missing_receipt")


class AgentError(RegistryError):
    """A devman-side refusal, carrying the exit code the contract gives it.

    `2` is infrastructure — the machine is not able to run this. `3` is usage —
    the request is wrong and running it again would be wrong the same way.
    Every message names the field, as `src/devman/` requires.
    """

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def usage(message: str) -> AgentError:
    return AgentError(message, 3)


def infra(message: str) -> AgentError:
    return AgentError(message, 2)


# --------------------------------------------------------------------------
# The request
# --------------------------------------------------------------------------


def parse_secret(item: str) -> tuple[str, str]:
    """One `--secret logical:ENVVAR` pair, or a refusal naming the half at fault.

    **The pair is the mapping, and it is stated rather than discovered.** A
    capsule declares `name → environment` in its own `capsule.toml`, and
    Agentman refuses a request naming a secret the capsule did not declare.
    devman cannot read that file — it is Agentman's — so devman does not guess
    it. The workflow states the pair, this process checks its grammar, and
    Agentman remains the authority on whether the capsule declared it.
    """
    logical, sep, env = item.partition(":")
    if not sep:
        raise usage(f"--secret '{item}' is not LOGICAL:ENVVAR")
    if not SECRET_NAME.fullmatch(logical):
        raise usage(
            f"--secret '{item}': the logical name '{logical}' does not match"
            f" {SECRET_NAME.pattern}"
        )
    if not SECRET_ENV.fullmatch(env):
        raise usage(
            f"--secret '{item}': the environment name '{env}' does not match"
            f" {SECRET_ENV.pattern}"
        )
    if env.startswith("DAGU_"):
        # Dagu's `secretRef.name` carries `not: {pattern: '^DAGU_'}`, so a
        # workflow declaring this could never have resolved the value. Refusing
        # here names the reason; refusing there names a schema.
        raise usage(
            f"--secret '{item}': Dagu refuses a secret named with a DAGU_ prefix,"
            " so this workflow could never supply a value"
        )
    return logical, env


def build_request(
    *,
    repository: Path,
    capsule: str,
    run_id: str,
    backend: str | None,
    secrets: list[str],
    timeout_s: int,
    memory_mb: int | None,
    cpu_seconds: int | None,
) -> dict:
    """The v1 request document, checked field by field before it is written.

    **It holds no secret VALUE, no queue, no capability, no filesystem mode, no
    network flag, no write tier, no retrieval policy, no extractor and no
    prompt.** That absence is the reason this boundary cannot widen a capsule:
    there is no field through which a widening could travel.
    """
    if not CAPSULE_NAME.fullmatch(capsule):
        raise usage(f"--capsule '{capsule}' does not match {CAPSULE_NAME.pattern}")
    if not RUN_ID.fullmatch(run_id):
        raise usage(f"the run id '{run_id}' does not match {RUN_ID.pattern}")
    if not repository.is_absolute():
        raise usage(f"--repository '{repository}' is not an absolute path")
    if not repository.is_dir():
        raise infra(f"--repository '{repository}' is not a directory")
    if backend is not None and backend not in BACKEND_ALLOWLIST:
        raise usage(
            f"--backend '{backend}' is not one devman authorises:"
            f" {', '.join(BACKEND_ALLOWLIST)}\n"
            "  a repository states its backend in its own agentman.toml, and the"
            " plane may only narrow that choice to the offline double"
        )
    if timeout_s <= 0 or timeout_s > 86_400:
        raise usage(f"--timeout-s {timeout_s} is outside the contract's 1..86400")
    for name, value in (("--memory-mb", memory_mb), ("--cpu-seconds", cpu_seconds)):
        if value is not None and value <= 0:
            raise usage(f"{name} {value} must be greater than zero")
    if len(secrets) != len(set(secrets)):
        raise usage(f"--secret names a logical secret twice: {', '.join(secrets)}")

    limits: dict[str, object] = {"timeout_s": timeout_s}
    if memory_mb is not None:
        limits["memory_mb"] = memory_mb
    if cpu_seconds is not None:
        limits["cpu_seconds"] = cpu_seconds

    request: dict[str, object] = {
        "version": CONTRACT_VERSION,
        "repository": str(repository),
        "capsule": capsule,
        "run_id": run_id,
        "limits": limits,
        "secrets": sorted(secrets),
    }
    if backend is not None:
        request["backend"] = backend
    return request


# --------------------------------------------------------------------------
# The bounded child
# --------------------------------------------------------------------------


def child_env(repository: Path, run_id: str, mapping: dict[str, str]) -> dict[str, str]:
    """The environment the Agentman process gets, built up rather than filtered.

    **THIS IS THE SECRET ALLOWLIST, AND STARTING FROM EMPTY IS WHAT MAKES IT
    ONE.** Dagu resolves every secret a workflow declares into the step's
    environment, and a step may declare more than one. Copying this process's
    environment and removing what it should not carry would let any name nobody
    thought of through — the same silent-default shape §12 rule 4 refuses. So
    nothing is inherited except the six names a program needs to run at all,
    and every credential arrives because `--secret` named it.

    `SHELL` is deliberately absent, for `run.child_env`'s reason: it is read by
    whatever process happens to be running, and a login shell is not a property
    of the work.
    """
    env: dict[str, str] = {}
    for name in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TERM"):
        value = os.environ.get(name)
        if value:
            env[name] = value

    env[PROJECT_DIR] = str(repository)
    # Measurement 1: the plane's own name for this value is `DAG_RUN_ID`, and
    # the contract's is `DAGU_RUN_ID`. One translation, in one place.
    env[AGENTMAN_RUN_ID_ENV] = run_id

    missing = []
    for logical, target in sorted(mapping.items()):
        value = os.environ.get(target)
        if not value:
            missing.append(f"{logical} → {target}")
            continue
        env[target] = value
    if missing:
        # Before the child starts, and before any money is spent. Dagu's own
        # `secrets:` block already fails a run whose provider has no value; this
        # catches the case where the workflow named a pair the block does not
        # declare, which Dagu has no way to notice.
        raise infra(
            "these declared secrets have no value in this step's environment:"
            f" {', '.join(missing)}\n"
            "  the workflow's secrets: block names the provider, and the machine"
            " supplies the value (§9.4)"
        )
    return env


def limit_setter(memory_mb: int | None, cpu_seconds: int | None):
    """The `preexec_fn` that bounds the child, or `None` when nothing is bounded.

    **The limits are applied in the child, after `fork` and before `exec`**, so
    they bind the Agentman process and everything it starts, and they bind
    nothing in this process. `RLIMIT_AS` is the address-space bound `memory_mb`
    names; `RLIMIT_CPU` is processor seconds, which is not wall clock — the wall
    clock bound is `--timeout-s`, enforced by `wait()` above, because a process
    blocked on a socket burns no CPU and would otherwise never reach either.

    This process is NOT put in a new session. Dagu signals the whole process
    group on cancellation (measurement 2), and a new session would put the
    Agentman child outside the group that gets the signal — turning a working
    cancellation into an orphan holding an API connection.
    """
    if memory_mb is None and cpu_seconds is None:
        return None

    def apply() -> None:  # pragma: no cover - runs only in the forked child
        if memory_mb is not None:
            limit = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        if cpu_seconds is not None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))

    return apply


def agentman_binary(stated: str | None) -> str:
    """The Agentman entrypoint. Named, or found on the step's PATH."""
    if stated:
        return stated
    found = shutil.which("agentman")
    if not found:
        raise infra(
            "no `agentman` on this step's PATH\n"
            "  the adopting repository provides it; a doctor asks its own PATH"
            " and not this step's (023 P1)"
        )
    return found


# --------------------------------------------------------------------------
# The result
# --------------------------------------------------------------------------


def redact(text: str, values: list[str]) -> str:
    """Replace each secret value with `*******`, exactly as Dagu does.

    **AND NO MORE THAN DAGU DOES, ON PURPOSE (measurement 4).** Dagu masks the
    exact resolved value and leaves a partial or an encoded one in clear. Doing
    better here would make devman's diagnostic safer than the log beside it and
    invite the belief that the log is safe too. The bound that actually holds is
    the one `groups/agent/README.md` states: a step must not print a fragment of
    a credential, because nothing masks a fragment.
    """
    for value in sorted((v for v in values if v), key=len, reverse=True):
        text = text.replace(value, "*******")
    return text


def result(
    *,
    run_id: str,
    capsule: str,
    agentman_exit_code: int,
    exit_code: int,
    classification: str,
    diagnostic: str,
    message: str | None = None,
    receipt_path: str | None = None,
    chat_path: str | None = None,
    missing_receipt: bool = True,
) -> dict:
    """One v1 `DevmanAgentmanResult`, for every outcome this adapter can have.

    **THERE IS NO SECOND ENVELOPE, AND THAT IS A DECISION RATHER THAN AN
    OMISSION** (022, decision 4). A devman-side failure — a malformed request, a
    missing secret, a timeout, a cancellation — never reached Agentman, so there
    is no Agentman code to report. Inventing a devman-only document shape for
    those cases would give the caller two schemas to read and a reason to guess
    which one it has. Instead every outcome is the contract's own document, the
    cause is in `diagnostic`, which the schema gives 8192 characters for exactly
    this, and `missing_receipt` is true because no validated work was proven.
    """
    assert classification in CLASSIFICATIONS
    return {
        "version": CONTRACT_VERSION,
        "run_id": run_id,
        "capsule": capsule,
        "agentman_exit_code": agentman_exit_code,
        "exit_code": exit_code,
        "classification": classification,
        "message": message,
        "diagnostic": diagnostic[:8192],
        "receipt_path": receipt_path,
        "chat_path": chat_path,
        "missing_receipt": missing_receipt,
    }


def parse_result(stdout: str, run_id: str, capsule: str) -> dict:
    """Read Agentman's one JSON document, strictly.

    `agentman run --request` prints exactly one `DevmanAgentmanResult`. It is
    read from the LAST line that parses as a JSON object, because a backend or a
    dependency may write a warning to stdout ahead of it, and a warning is not a
    reason to lose a run's verdict.

    Every check here can fail, which is the point (§12 rule 4). A process that
    exits 0 and prints something devman cannot read has not reported a clean
    result — it has reported nothing.
    """
    document = None
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            document = candidate
            break
    if document is None:
        raise infra("agentman printed no JSON result document")

    if document.get("version") != CONTRACT_VERSION:
        raise infra(
            f"agentman printed contract version {document.get('version')!r},"
            f" and devman implements {CONTRACT_VERSION!r}"
        )
    unknown = sorted(
        set(document)
        - set(
            result(
                run_id=run_id,
                capsule=capsule,
                agentman_exit_code=0,
                exit_code=0,
                classification="clean",
                diagnostic="",
            )
        )
    )
    if unknown:
        raise infra(f"agentman's result carries unknown field(s): {', '.join(unknown)}")
    if document.get("run_id") != run_id:
        raise infra(
            f"agentman's result names run {document.get('run_id')!r},"
            f" and this run is {run_id!r}"
        )
    if document.get("capsule") != capsule:
        raise infra(
            f"agentman's result names capsule {document.get('capsule')!r},"
            f" and this run asked for {capsule!r}"
        )
    if document.get("classification") not in CLASSIFICATIONS:
        raise infra(
            f"agentman's result classification {document.get('classification')!r}"
            f" is not one of: {', '.join(CLASSIFICATIONS)}"
        )
    for field in ("agentman_exit_code", "exit_code"):
        value = document.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3:
            raise infra(f"agentman's result field {field} is {value!r}, not 0..3")
    return document


def verify_receipt(document: dict, repository: Path, run_id: str) -> dict:
    """devman's own receipt check, and it is not a re-reading of Agentman's.

    **A run that reports success while producing no proof is the failure this
    design exists to prevent** (rule 4). Agentman sets `missing_receipt` itself,
    and devman trusts a `true` and checks a `false` — because the direction that
    can hide a failure is the one worth checking.

    Three things have to hold, and each can fail on its own:

    * the file exists;
    * it is inside the repository this run targeted — a receipt written
      somewhere else proves work in the wrong tree, which is exactly §9.2's
      wrong-directory failure wearing a receipt;
    * its `run` field is this run's id, which is what correlates the artifact
      with `DAG_RUN_ID` rather than merely with a file that happens to be there.

    A failure here rewrites `exit_code` to 2 and the classification to
    `missing_receipt`, and leaves `agentman_exit_code` untouched, so the process
    result and the integration finding stay distinguishable.
    """
    if document.get("missing_receipt"):
        return document

    def refuse(why: str) -> dict:
        return {
            **document,
            "exit_code": 2,
            "classification": "missing_receipt",
            "missing_receipt": True,
            "diagnostic": (document.get("diagnostic", "") + f"\ndevman: {why}").strip(),
        }

    stated = document.get("receipt_path")
    if not stated:
        return refuse("agentman reported a receipt and named no path")
    path = Path(stated)
    if not path.is_file():
        return refuse(f"the receipt agentman named does not exist: {path}")
    try:
        path.relative_to(repository)
    except ValueError:
        return refuse(
            f"the receipt {path} is outside the repository this run targeted"
            f" ({repository})"
        )
    try:
        receipt = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return refuse(f"the receipt {path} is not readable JSON: {exc}")
    if not isinstance(receipt, dict) or receipt.get("run") != run_id:
        return refuse(
            f"the receipt {path} records run {receipt.get('run')!r}"
            if isinstance(receipt, dict)
            else f"the receipt {path} is not an object"
        )
    return document


# --------------------------------------------------------------------------
# The one invocation
# --------------------------------------------------------------------------


def invoke(
    *,
    binary: str,
    request_file: Path,
    env: dict[str, str],
    cwd: Path,
    timeout_s: int,
    memory_mb: int | None,
    cpu_seconds: int | None,
) -> tuple[int, str, str]:
    """Start Agentman **once**, wait, and bound it. Returns `(code, out, err)`.

    **EXACTLY ONE `Popen`, AND NO PATH BACK TO IT.** One admitted run is one
    Agentman invocation: the contract says Agentman's own bounded repair loop
    lives inside that single call, so a second call here would be a second model
    run devman never accounted for. There is no retry in this function, no retry
    around it, and `groups/agent/agent.yaml` states no `retry_policy` — the
    reason is in that group's README.

    The timeout is enforced here because Dagu does not enforce one
    (measurement 3): `SIGTERM`, five seconds, then `SIGKILL`, which is the
    escalation the daemon lacks.
    """
    child = subprocess.Popen(  # noqa: S603 - argv is built, never a shell string
        [binary, "run", "--request", str(request_file)],
        env=env,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=limit_setter(memory_mb, cpu_seconds),
    )

    def stop(_signum: int, _frame: FrameType | None) -> None:
        # Dagu signals the whole process group, so the child already has this
        # signal too (measurement 2). Sending it again is harmless and makes the
        # handler correct when the signal came from anywhere else.
        child.terminate()

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        out, err = child.communicate(timeout=timeout_s)
        return child.returncode, out, err
    except subprocess.TimeoutExpired:
        child.terminate()
        try:
            out, err = child.communicate(timeout=GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            child.kill()
            out, err = child.communicate()
        raise infra(
            f"agentman exceeded its {timeout_s}s timeout and was terminated\n"
            "  the plane does not bound a run's lifetime: Dagu re-sends SIGTERM"
            " every 5s and never escalates (022, measurement 3)\n"
            f"  {err.strip()[-2000:]}"
        ) from None
    finally:
        signal.signal(signal.SIGTERM, previous)


def execute(args, values: list[str]) -> tuple[dict, int]:
    """Resolve, refuse, invoke, verify. The whole adapter in one call."""
    repository = Path(args.repository or os.environ.get(PROJECT_DIR) or "").expanduser()
    if not str(repository):
        raise infra(
            f"neither --repository nor {PROJECT_DIR} names a directory\n"
            "  the projection writes that variable, and a trigger passes it"
            " (§7.2)"
        )
    run_id = args.run_id or os.environ.get(DAGU_RUN_ID_ENV) or ""
    if not run_id:
        raise infra(
            f"neither --run-id nor {DAGU_RUN_ID_ENV} names this run\n"
            f"  Dagu 2.15.0 sets {DAGU_RUN_ID_ENV} in a step's environment, and"
            f" the contract calls the same value {AGENTMAN_RUN_ID_ENV}"
            " (022, measurement 1)"
        )

    mapping = dict(parse_secret(item) for item in args.secret)
    request = build_request(
        repository=repository,
        capsule=args.capsule,
        run_id=run_id,
        backend=args.backend,
        secrets=list(mapping),
        timeout_s=args.timeout_s,
        memory_mb=args.memory_mb,
        cpu_seconds=args.cpu_seconds,
    )
    if args.print_request:
        print(json.dumps(request, indent=2, sort_keys=True))
        return {}, 0

    env = child_env(repository, run_id, mapping)
    values.extend(env[target] for target in mapping.values())
    binary = agentman_binary(args.agentman)

    directory = repository / REQUEST_DIR
    directory.mkdir(parents=True, exist_ok=True)
    # `mkstemp` is 0600 and this process owns removal. The request holds only
    # symbolic names, so it is not a credential store — the mode and the
    # `finally` are there because a file nobody removes is a file somebody
    # eventually reads, and the run id and capsule are still this run's business.
    handle, name = tempfile.mkstemp(
        dir=directory, prefix=f"request-{run_id}-", suffix=".json"
    )
    request_file = Path(name)
    try:
        with os.fdopen(handle, "w") as fh:
            json.dump(request, fh, indent=2, sort_keys=True)
        code, out, err = invoke(
            binary=binary,
            request_file=request_file,
            env=env,
            cwd=repository,
            timeout_s=args.timeout_s,
            memory_mb=args.memory_mb,
            cpu_seconds=args.cpu_seconds,
        )
    finally:
        request_file.unlink(missing_ok=True)

    if code < 0:
        raise infra(f"agentman was killed by signal {-code}\n  {err.strip()[-2000:]}")
    document = parse_result(out, run_id, args.capsule)
    document = verify_receipt(document, repository, run_id)
    if document["exit_code"] != code and not document["missing_receipt"]:
        # The contract says `exit_code` is what the caller acts on and the
        # process code carries the same verdict. A disagreement is not something
        # to average out.
        raise infra(
            f"agentman exited {code} and its result reports"
            f" exit_code {document['exit_code']}"
        )
    return document, document["exit_code"]


def main(args, reg: Registry) -> int:
    """Print one v1 result document, always, and exit with its `exit_code`.

    `reg` is unused: this command runs inside a workflow step, where the
    directory and the run id arrive from Dagu rather than from the registry.
    The signature is the one `cli.handler` dispatches to.
    """
    values: list[str] = []
    try:
        document, code = execute(args, values)
    except AgentError as exc:
        document = result(
            run_id=args.run_id or os.environ.get(DAGU_RUN_ID_ENV) or "unknown",
            capsule=args.capsule,
            agentman_exit_code=exc.exit_code,
            exit_code=exc.exit_code,
            classification="usage" if exc.exit_code == 3 else "infrastructure",
            diagnostic=redact(str(exc), values),
        )
        code = exc.exit_code
    if document:
        print(json.dumps(redact(json.dumps(document), values)))
    return code


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--capsule", required=True, help="the Agentman capsule to run")
    p.add_argument(
        "--backend",
        help=f"narrow the capsule's backend. Only: {', '.join(BACKEND_ALLOWLIST)}",
    )
    p.add_argument(
        "--secret",
        action="append",
        default=[],
        metavar="LOGICAL:ENVVAR",
        help="one declared secret, by symbolic name and target variable (§9.4)",
    )
    p.add_argument(
        "--timeout-s", type=int, default=900, help="the wall-clock bound, enforced here"
    )
    p.add_argument("--memory-mb", type=int, help="RLIMIT_AS for the child")
    p.add_argument("--cpu-seconds", type=int, help="RLIMIT_CPU for the child")
    p.add_argument("--repository", help=f"defaults to ${PROJECT_DIR}")
    p.add_argument("--run-id", help=f"defaults to ${DAGU_RUN_ID_ENV}")
    p.add_argument("--agentman", help="the entrypoint, when it is not on PATH")
    p.add_argument(
        "--print-request",
        action="store_true",
        help="print the request and invoke nothing",
    )
