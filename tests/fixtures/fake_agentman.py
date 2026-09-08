"""A safe stand-in for `agentman run --request`, for the whole `agent` suite.

**IT IS A SUBPROCESS, NOT A MOCK, AND THAT IS THE POINT.** `src/devman/agent.py`
exists to bound a process: it filters an environment, applies `setrlimit`,
enforces a wall clock, forwards a signal and reads one document off stdout. A
patched function proves none of those. This is a real executable that a real
`Popen` runs, so every one of them is exercised.

**It reaches no network, holds no credential and calls no model.** Its behaviour
is chosen entirely by `FAKE_AGENTMAN_MODE` in the environment it is given, which
is also how a test asserts that the adapter passed the environment it meant to.

It records every invocation as one JSON line in `$FAKE_AGENTMAN_LOG`, which is
what `test_exactly_one_invocation` reads: one admitted run must produce exactly
one line.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

CONTRACT_VERSION = "agentman.devman/v1"

#: The control file, relative to the repository the adapter runs the child in.
CONTROL = Path(".devman/.runs/fake-agentman.json")


def control() -> dict:
    try:
        return json.loads(CONTROL.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def result(request: dict, **over) -> dict:
    document = {
        "version": CONTRACT_VERSION,
        "run_id": request["run_id"],
        "capsule": request["capsule"],
        "agentman_exit_code": 0,
        "exit_code": 0,
        "classification": "clean",
        "message": "clean",
        "diagnostic": "clean",
        "receipt_path": None,
        "chat_path": None,
        "missing_receipt": True,
    }
    document.update(over)
    return document


def write_receipt(request: dict, run_id: str | None = None) -> str:
    """Write the receipt Agentman would write, at the path §9.2 reserves."""
    out = Path(request["repository"]) / ".devman/.runs/receipts"
    out.mkdir(parents=True, exist_ok=True)
    identifier = run_id if run_id is not None else request["run_id"]
    path = out / f"agentman-{identifier}.json"
    path.write_text(json.dumps({"run": identifier, "capsule": request["capsule"]}))
    return str(path)


def main(argv: list[str]) -> int:
    settings = control()
    mode = settings.get("mode", "clean")

    log = settings.get("log")
    if log:
        with open(log, "a") as fh:
            fh.write(
                json.dumps(
                    {
                        "argv": argv,
                        "mode": mode,
                        # The environment, so a test can assert the ALLOWLIST
                        # rather than assert that one name arrived. A leak is a
                        # name nobody expected, and only the whole set shows it.
                        "env": dict(os.environ),
                        "cwd": os.getcwd(),
                    }
                )
                + "\n"
            )

    if argv[:2] != ["run", "--request"] or len(argv) != 3:
        print(f"fake agentman: unexpected argv: {argv}", file=sys.stderr)
        return 3
    request = json.loads(Path(argv[2]).read_text())

    if mode == "clean":
        path = write_receipt(request)
        print(json.dumps(result(request, receipt_path=path, missing_receipt=False)))
        return 0
    if mode == "finding":
        path = write_receipt(request)
        print(
            json.dumps(
                result(
                    request,
                    agentman_exit_code=1,
                    exit_code=1,
                    classification="finding",
                    message="issues_found",
                    receipt_path=path,
                    missing_receipt=False,
                )
            )
        )
        return 1
    if mode == "infrastructure":
        print(
            json.dumps(
                result(
                    request,
                    agentman_exit_code=2,
                    exit_code=2,
                    classification="infrastructure",
                    diagnostic="the backend refused",
                )
            )
        )
        return 2
    if mode == "usage":
        print(
            json.dumps(
                result(
                    request,
                    agentman_exit_code=3,
                    exit_code=3,
                    classification="usage",
                    diagnostic="no such capsule",
                )
            )
        )
        return 3
    if mode == "missing-receipt":
        # Exit 0 and no receipt: the failure rule 4 exists to prevent, arriving
        # from Agentman rather than being invented by devman.
        print(
            json.dumps(
                result(
                    request,
                    exit_code=2,
                    classification="missing_receipt",
                    diagnostic="Agentman returned exit 0 without a receipt",
                )
            )
        )
        return 2
    if mode == "lying-receipt":
        # Exit 0, `missing_receipt: false`, and a path that does not exist. This
        # is why devman checks a `false` rather than trusting it.
        print(
            json.dumps(
                result(
                    request,
                    receipt_path=str(
                        Path(request["repository"]) / ".devman/.runs/receipts/nope.json"
                    ),
                    missing_receipt=False,
                )
            )
        )
        return 0
    if mode == "foreign-receipt":
        # A real receipt recording a DIFFERENT run. Correlation, not existence.
        path = write_receipt(request, run_id="some-other-run")
        Path(path).replace(
            Path(request["repository"])
            / ".devman/.runs/receipts"
            / f"agentman-{request['run_id']}.json"
        )
        moved = (
            Path(request["repository"])
            / ".devman/.runs/receipts"
            / f"agentman-{request['run_id']}.json"
        )
        print(
            json.dumps(result(request, receipt_path=str(moved), missing_receipt=False))
        )
        return 0
    if mode == "wrong-version":
        print(json.dumps(result(request, version="agentman.devman/v2")))
        return 0
    if mode == "unknown-field":
        print(json.dumps({**result(request), "surprise": 1}))
        return 0
    if mode == "wrong-run-id":
        print(json.dumps(result(request, run_id="not-this-run")))
        return 0
    if mode == "no-json":
        print("everything is fine")
        return 0
    if mode == "noisy":
        # A dependency's warning ahead of the document. The verdict must survive.
        print("warning: a library said something")
        path = write_receipt(request)
        print(json.dumps(result(request, receipt_path=path, missing_receipt=False)))
        return 0
    if mode == "hang":
        # Ignores SIGTERM, so only the adapter's own SIGKILL escalation ends it.
        signal.signal(signal.SIGTERM, lambda *_: None)
        time.sleep(3600)
        return 0
    if mode == "hang-politely":
        time.sleep(3600)
        return 0

    print(f"fake agentman: unknown mode {mode}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
