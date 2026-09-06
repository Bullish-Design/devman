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

        Dagu accepts **five** spellings, not the four this said until S-10.
        devman's own files use the first:

            params:                 params:  {A: x, B: y}
              - A: x                params:  "A=x B=y"
              - B: y                params:  [A=x, B=y]

        The fifth is the inline typed definition, and reading it as one of the
        others is the failure S-10 measured:

            params:
              - name: A
                type: string
                default: x

        **A list item holding a `name` key is a definition of the parameter that
        key names — never a parameter called `name`.** That is Dagu's own rule,
        not an inference: `- name: FOO` alone is refused with "parameter "FOO"
        must define at least one field in addition to name", so a list-form
        parameter simply cannot be called `name`. Read as a plain mapping the
        item above yields three parameters — `name`, `type` and `default` — and
        loses `A` entirely, which made `holds_project_dir()` miss a file that
        declares `DEVMAN_PROJECT_DIR` and §11's refusal never fire.

        `default` carries the value, and Dagu keeps it a scalar: an `object` or
        `array` default is refused at validation. A definition without one
        declares the parameter empty, which `run.resolve()` already refuses to
        enqueue (§8).

        `params:` is also the only parameter surface. `param_schema`,
        `param_defs`, `params_json` and `default_params` name Dagu's internal
        representations and are rejected as top-level keys, so there is no
        externally-schema'd form for devman to fail to resolve (S-10).

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
                    if "name" in item:
                        out[str(item["name"])] = _scalar(item.get("default"))
                    else:
                        for k, v in item.items():
                            out[str(k)] = _scalar(v)
                elif isinstance(item, str) and "=" in item:
                    k, _, v = item.partition("=")
                    out[k.strip()] = v.strip().strip("\"'")
        return out

    # -- the steps, as Dagu validates them ----------------------------------

    def steps(self) -> list[dict]:
        """The direct steps, as mappings. A `steps:` that is not a sequence has none.

        **Dagu's loader and Dagu's validator disagree here, and devman follows
        the validator.** A `steps:` written as a mapping of name to step RUNS —
        `dagu dry` executed one and reported success — while `dagu validate`
        refuses the same file: "entrypoint document steps must be a non-empty
        sequence" (`STAGE_7_LOG.md`, S-8). Reading the mapping form here would
        make devman more permissive than the validator §10 check 1 already runs
        over every projected file, so a file Dagu calls invalid stays invalid,
        and `doctor` is what says so.
        """
        raw = (self.doc or {}).get("steps")
        if not isinstance(raw, list):
            return []
        return [s for s in raw if isinstance(s, dict)]

    # -- §11's rule, mechanically -------------------------------------------

    def child_runs(self) -> list[dict]:
        """Every step that runs a child DAG in place (`action: dag.run`)."""
        return [s for s in self.steps() if s.get("action") == "dag.run"]

    def triggers_other_dags(self) -> bool:
        """True when any step uses `action: dag.run` — a cross-repo parent."""
        return bool(self.child_runs())

    def unbounded_fanout(self) -> list[str]:
        """Why this file can start any number of child runs at once — empty when
        it states a bound, and empty when it starts at most one.

        **A `dag.run` child takes no slot in any queue.** Measured on the pinned
        Dagu 2.15.0: two children both naming `gpu`, limit 1, started 12 ms apart
        and ran concurrently under `dag.run`, while the same two through
        `dag.enqueue` serialised and the scheduler logged the admission
        (`STAGE_7_LOG.md`, S-8). A child is executed inline by its parent and
        never reaches the queue that would have admitted it. So a queue name in
        a child throttles nothing here, and the only bound is one the parent
        states:

            type: chain              one step at a time
            max_active_steps: N      N steps at a time
            parallel.max_concurrent  N children out of one step

        **Dagu's default is none of the three.** A file stating no `type` runs
        its steps concurrently, and a `parallel:` block with no `max_concurrent`
        starts every item at once — both measured in the same entry. The
        machine's `base.yaml` states no `type` either, so nothing supplies one.

        This reports an UNSTATED bound and never a stated one it disagrees with:
        `max_active_steps: 4` is not a finding, because the author said 4 and
        §15.7 forbids devman deciding 4 is too many.
        """
        doc = self.doc or {}
        children = self.child_runs()
        why = []
        for step in children:
            par = step.get("parallel")
            if par is None:
                continue
            # A list is `parallel:`'s shorthand for its items, so it carries no
            # limit either. Only the mapping form can hold one.
            if not (isinstance(par, dict) and par.get("max_concurrent") is not None):
                name = step.get("name") or step.get("id") or "?"
                why.append(f"step '{name}' fans out with no parallel.max_concurrent")
        if (
            len(children) > 1
            and doc.get("type") != "chain"
            and "max_active_steps" not in doc
        ):
            why.append(
                f"{len(children)} dag.run steps, and neither type: chain nor"
                " max_active_steps"
            )
        return why

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
        """Every queue this file names — the DAG's own, and any child it enqueues.

        Dagu accepts a queue name the machine does not declare **silently**, and
        the throttle it applies is not the one §15.4 recorded: the name becomes a
        queue of its own at concurrency **1**, shared by every DAG that names it
        (`STAGE_7_LOG.md`, S-9). So a typo does not free a workflow, it
        serialises one — a misspelt `light` runs one at a time instead of four,
        beside anything else carrying the same misspelling. Either way nothing
        says so at run time, which is why `doctor` checks every name.

        **THERE IS NO STEP-LEVEL `queue:` ON THE PIN, AND THIS READ ONE UNTIL
        S-11.** Dagu 2.15.0 refuses the key outright — "'spec.step' has invalid
        keys: queue" — so a file spelling it that way never runs at all, and it
        is §10 check 1's finding rather than check 2's. The one place a step can
        name a queue is `with.queue`, and Dagu accepts it on `dag.enqueue`
        alone:

            dag.enqueue + with.queue   accepted
            dag.run     + with.queue   refused — "dag.run does not support
                                       with.queue"

        That refusal is S-8's own finding, stated by the validator: a `dag.run`
        child is executed in place and never reaches a queue, so it cannot name
        one. `dag.enqueue` is the path that does admit through the queue, so its
        name is the one `doctor` check 2 must see — and the name it saw before
        S-11 was one Dagu would have rejected.
        """
        doc = self.doc or {}
        names = []
        if isinstance(doc.get("queue"), str):
            names.append(doc["queue"])
        for step in self.steps():
            args = step.get("with")
            if isinstance(args, dict) and isinstance(args.get("queue"), str):
                names.append(args["queue"])
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
