"""What devman reads out of a workflow file, and nothing more.

**§7.2 says devman never parses a workflow, and this does not break it.** That
sentence forbids the plane from *understanding* a workflow — from carrying an
`x-devman` block, from re-deriving a task graph, from rewriting a file at
projection time. Two things in the charter already read a workflow's text:
§10's `doctor` check 1 runs `dagu validate` over every projected file, and §11's
check must tell a workflow that *holds* `DEVMAN_PROJECT_DIR` from one that
*passes* it to a child.

This module adds the third: the parameters a file declares, because those are
exactly what the trigger is required to fill in (§8). `dagu dry` prints them and
cannot be used — it creates `log_dir`, so it reproduces S15's literally-named
directory (S1).

Everything here tolerates a file it cannot parse. A projected file that fails to
load is a `doctor` finding (§10 check 1), not a crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# §7.1's closed list of four names holds two that are directories, and a trigger
# sets exactly one of them. `DEVMAN_PROJECT_DIR` names the project a run
# targets; `DEVMAN_SELF_DIR` names the directory of a workflow that targets no
# project because it directs others (§11).
PROJECT_DIR = "DEVMAN_PROJECT_DIR"
SELF_DIR = "DEVMAN_SELF_DIR"


@dataclass
class Workflow:
    path: Path
    text: str
    doc: dict | None
    error: str | None = None

    @classmethod
    def read(cls, path: Path) -> Workflow:
        try:
            text = Path(path).read_text()
        except OSError as exc:
            return cls(Path(path), "", None, f"cannot read: {exc}")
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return cls(Path(path), text, None, f"not loadable as YAML: {exc}")
        if doc is not None and not isinstance(doc, dict):
            return cls(Path(path), text, None, "the document is not a mapping")
        return cls(Path(path), text, doc or {})

    # -- parameters ---------------------------------------------------------

    def params(self) -> dict[str, str]:
        """The top-level `params:` block, as `name -> default`.

        Dagu accepts four spellings. devman's own files use the first, which is
        the one the schema documents:

            params:                 params:  {A: x, B: y}
              - A: x                params:  "A=x B=y"
              - B: y                params:  [A=x, B=y]

        A positional parameter has no name and is not returned: devman fills
        parameters by name, and a positional one is the workflow's own business.
        """
        raw = (self.doc or {}).get("params")
        out: dict[str, str] = {}
        if raw is None:
            return out
        if isinstance(raw, dict):
            return {str(k): _scalar(v) for k, v in raw.items()}
        if isinstance(raw, str):
            raw = raw.split()
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    for k, v in item.items():
                        out[str(k)] = _scalar(v)
                elif isinstance(item, str) and "=" in item:
                    k, _, v = item.partition("=")
                    out[k.strip()] = v.strip().strip("\"'")
        return out

    # -- §11's rule, mechanically -------------------------------------------

    def triggers_other_dags(self) -> bool:
        """True when any step uses `action: dag.run` — a cross-repo parent."""
        return any(
            isinstance(s, dict) and s.get("action") == "dag.run"
            for s in (self.doc or {}).get("steps", []) or []
        )

    def holds_project_dir(self) -> list[str]:
        """Where this file defines `DEVMAN_PROJECT_DIR` **for itself** (§11).

        Inside a step's `with.params` the name is correct — that is how a parent
        directs a child, and the rule that forbade mentioning it at all reported
        the only correct cross-repo workflow in this repository as broken
        (`STAGE_2_LOG.md`, S8). So this looks in the four places a file can hold
        the name for itself, and nowhere else.
        """
        doc = self.doc or {}
        found = []
        if PROJECT_DIR in self.params():
            found.append("params")
        if _env_holds(doc.get("env"), PROJECT_DIR):
            found.append("env")
        for field_name in ("working_dir", "log_dir"):
            value = doc.get(field_name)
            if isinstance(value, str) and PROJECT_DIR in value:
                found.append(field_name)
        return found

    def handlers(self) -> list[str]:
        """The `handler_on` events this file defines for itself (§9.2).

        `base.yaml` is inherited **whole-field**, so a DAG that sets
        `handler_on` replaces the machine's exit handler — the one that appends
        a line to the triggering project's `.devman/.runs/metadata.jsonl`.
        Measured: the run succeeds, the logs land in the right project, `dagu
        status` is clean, and the file §9.2 promises survives every retention
        setting simply gains no line (`STAGE_4_LOG.md`, S3).

        Any key counts. Dagu's `handler_on` is one field, so defining `success`
        alone still replaces the whole block, exit handler included.
        """
        raw = (self.doc or {}).get("handler_on")
        if isinstance(raw, dict):
            return sorted(str(k) for k in raw)
        return ["handler_on"] if raw else []

    def queues(self) -> list[str]:
        """Every queue this file names — the DAG's own, and any a step overrides.

        Dagu accepts a queue name that does not exist silently and applies no
        limit at all, so a typo is unobservable (§15.4, A1).
        """
        doc = self.doc or {}
        names = []
        if isinstance(doc.get("queue"), str):
            names.append(doc["queue"])
        for step in doc.get("steps", []) or []:
            if isinstance(step, dict) and isinstance(step.get("queue"), str):
                names.append(step["queue"])
        return names


def _env_holds(env: object, name: str) -> bool:
    """Whether an `env:` block defines `name`. Dagu accepts a map or a list."""
    if isinstance(env, dict):
        return name in env
    if isinstance(env, list):
        return any(
            (isinstance(e, dict) and name in e)
            or (isinstance(e, str) and e.startswith(name + "="))
            for e in env
        )
    return False


def _scalar(value: object) -> str:
    """A parameter default as the string Dagu would hand a step."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
