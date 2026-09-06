"""Probe semantic-promotion orchestration with an adversarial local provider."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_ATTEMPTS = 3
PROVIDER_TIMEOUT_SECONDS = 0.01


class EditKind(StrEnum):
    BODY = "body"
    SIGNATURE = "signature"
    BEHAVIOR = "behavior"
    DOCSTRING = "docstring"
    IMPORT = "import"
    RENAME = "rename"
    MOVE = "move"
    SPLIT = "split"
    MERGE = "merge"
    DELETE = "delete"


class UnitPromotion(BaseModel):
    """One semantic unit change proposed by the provider."""

    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(min_length=1)
    edit_kind: EditKind
    semantic_spec: str = Field(min_length=1)
    examples: list[str] = Field(min_length=1)


class PromotionProposal(BaseModel):
    """Closed provider output schema."""

    model_config = ConfigDict(extra="forbid")

    base_generation_token: str = Field(min_length=1)
    changes: list[UnitPromotion] = Field(min_length=1)


class AttemptRecord(BaseModel):
    """One state-machine attempt."""

    attempt: int
    state: str
    detail: str


class PromotionResult(BaseModel):
    """Terminal promotion result."""

    accepted: bool
    terminal_state: str
    attempts: list[AttemptRecord]
    source_before_hash: str
    source_after_hash: str
    store_before_hash: str
    store_after_hash: str
    edited_source_preserved: bool
    accepted_store_preserved: bool
    proposal: dict[str, Any] | None = None


@dataclass(frozen=True)
class Scenario:
    """Known edit with an orchestration oracle."""

    name: str
    edit_kind: EditKind
    accepted_sources: dict[str, str]
    edited_sources: dict[str, str]
    accepted_store: bytes
    generation_token: str
    expected_specs: dict[str, str]
    required_examples: dict[str, set[str]]

    @property
    def changed_units(self) -> set[str]:
        return set(self.expected_specs)


@dataclass(frozen=True)
class ProviderOutcome:
    """One scripted provider result."""

    kind: Literal["payload", "timeout", "cancel"]
    payload: Any = None


class ScriptedProvider:
    """Return scripted outcomes without network or model access."""

    def __init__(self, outcomes: list[ProviderOutcome]) -> None:
        self.outcomes = outcomes
        self.index = 0

    async def propose(self) -> Any:
        outcome = self.outcomes[min(self.index, len(self.outcomes) - 1)]
        self.index += 1
        if outcome.kind == "timeout":
            await asyncio.Event().wait()
        if outcome.kind == "cancel":
            raise asyncio.CancelledError
        return outcome.payload


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _tree_bytes(sources: dict[str, str]) -> bytes:
    payload = {path: sources[path] for path in sorted(sources)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _format_python(source: str, filename: str) -> str:
    result = subprocess.run(
        ["ruff", "format", "--stdin-filename", filename, "-"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"Ruff rejected {filename}: {result.stderr.strip()}")
    return result.stdout


def _canonical_tree(sources: dict[str, str]) -> dict[str, str]:
    return {
        path: _format_python(source, path) for path, source in sorted(sources.items())
    }


def _valid_examples(scenario: Scenario, proposal: PromotionProposal) -> bool:
    for change in proposal.changes:
        supplied = set(change.examples)
        if any(item.startswith("CONTRADICTS:") for item in supplied):
            return False
        if not scenario.required_examples[change.unit_id].issubset(supplied):
            return False
    return True


def _derive(scenario: Scenario, proposal: PromotionProposal) -> dict[str, str]:
    """Deterministic semantic deriver used only as an orchestration oracle."""

    proposed_specs = {
        change.unit_id: change.semantic_spec for change in proposal.changes
    }
    if proposed_specs == scenario.expected_specs:
        return scenario.edited_sources
    return scenario.accepted_sources


def _accepted_store(scenario: Scenario, proposal: PromotionProposal) -> bytes:
    payload = {
        "generation_token": hashlib.sha256(
            (scenario.generation_token + proposal.model_dump_json()).encode()
        ).hexdigest(),
        "units": {
            change.unit_id: {
                "semantic_spec": change.semantic_spec,
                "examples": change.examples,
            }
            for change in sorted(proposal.changes, key=lambda item: item.unit_id)
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"


def _terminal_rejection(
    *,
    state: str,
    attempts: list[AttemptRecord],
    scenario: Scenario,
    source_before: bytes,
    store_before: bytes,
    proposal: dict[str, Any] | None = None,
) -> PromotionResult:
    return PromotionResult(
        accepted=False,
        terminal_state=state,
        attempts=attempts,
        source_before_hash=_hash_bytes(source_before),
        source_after_hash=_hash_bytes(source_before),
        store_before_hash=_hash_bytes(store_before),
        store_after_hash=_hash_bytes(store_before),
        edited_source_preserved=True,
        accepted_store_preserved=True,
        proposal=proposal,
    )


async def promote(
    scenario: Scenario,
    provider: ScriptedProvider,
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> PromotionResult:
    """Run validation, convergence, and acceptance without mutating inputs."""

    source_before = _tree_bytes(scenario.edited_sources)
    store_before = scenario.accepted_store
    attempts: list[AttemptRecord] = []

    if _canonical_tree(scenario.edited_sources) != scenario.edited_sources:
        attempts.append(
            AttemptRecord(
                attempt=0,
                state="edited-source-not-canonical",
                detail="Ruff would change the edited source",
            )
        )
        return _terminal_rejection(
            state="rejected-invalid-source",
            attempts=attempts,
            scenario=scenario,
            source_before=source_before,
            store_before=store_before,
        )

    last_payload: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            raw = await asyncio.wait_for(
                provider.propose(), timeout=PROVIDER_TIMEOUT_SECONDS
            )
        except TimeoutError:
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state="provider-timeout",
                    detail="provider exceeded the attempt timeout",
                )
            )
            continue
        except asyncio.CancelledError:
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state="cancelled",
                    detail="provider request was cancelled",
                )
            )
            return _terminal_rejection(
                state="rejected-cancelled",
                attempts=attempts,
                scenario=scenario,
                source_before=source_before,
                store_before=store_before,
            )

        if isinstance(raw, dict):
            last_payload = raw
        try:
            proposal = PromotionProposal.model_validate(raw)
        except ValidationError as error:
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state="schema-rejected",
                    detail=str(error),
                )
            )
            continue

        if proposal.base_generation_token != scenario.generation_token:
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state="stale-input",
                    detail="proposal generation token does not match accepted input",
                )
            )
            return _terminal_rejection(
                state="rejected-stale-input",
                attempts=attempts,
                scenario=scenario,
                source_before=source_before,
                store_before=store_before,
                proposal=proposal.model_dump(mode="json"),
            )

        proposed_units = [change.unit_id for change in proposal.changes]
        if len(proposed_units) != len(set(proposed_units)):
            state = "duplicate-unit"
        elif set(proposed_units) < scenario.changed_units:
            state = "partial-output"
        elif set(proposed_units) > scenario.changed_units:
            state = "hallucinated-unit"
        elif set(proposed_units) != scenario.changed_units:
            state = "wrong-unit-set"
        else:
            state = ""
        if state:
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state=state,
                    detail=f"expected={sorted(scenario.changed_units)} got={sorted(proposed_units)}",
                )
            )
            continue

        if any(change.edit_kind != scenario.edit_kind for change in proposal.changes):
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state="wrong-edit-kind",
                    detail=f"expected {scenario.edit_kind.value}",
                )
            )
            continue

        if not _valid_examples(scenario, proposal):
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state="examples-rejected",
                    detail="required example missing or deterministic contradiction found",
                )
            )
            continue

        candidate = _canonical_tree(_derive(scenario, proposal))
        if candidate != scenario.edited_sources:
            attempts.append(
                AttemptRecord(
                    attempt=attempt,
                    state="non-convergent",
                    detail="re-derived files differ from canonical edited source",
                )
            )
            continue

        store_after = _accepted_store(scenario, proposal)
        attempts.append(
            AttemptRecord(
                attempt=attempt,
                state="accepted",
                detail="schema, token, ownership, examples, and convergence passed",
            )
        )
        return PromotionResult(
            accepted=True,
            terminal_state="accepted",
            attempts=attempts,
            source_before_hash=_hash_bytes(source_before),
            source_after_hash=_hash_bytes(source_before),
            store_before_hash=_hash_bytes(store_before),
            store_after_hash=_hash_bytes(store_after),
            edited_source_preserved=True,
            accepted_store_preserved=False,
            proposal=proposal.model_dump(mode="json"),
        )

    return _terminal_rejection(
        state="rejected-attempt-limit",
        attempts=attempts,
        scenario=scenario,
        source_before=source_before,
        store_before=store_before,
        proposal=last_payload,
    )


def _store(name: str) -> bytes:
    return (
        json.dumps(
            {"generation_token": f"token-{name}", "units": {}},
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def _scenario(
    name: str,
    edit_kind: EditKind,
    accepted_sources: dict[str, str],
    edited_sources: dict[str, str],
    expected_specs: dict[str, str],
) -> Scenario:
    return Scenario(
        name=name,
        edit_kind=edit_kind,
        accepted_sources=_canonical_tree(accepted_sources),
        edited_sources=_canonical_tree(edited_sources),
        accepted_store=_store(name),
        generation_token=f"token-{name}",
        expected_specs=expected_specs,
        required_examples={
            unit_id: {f"example:{name}:{unit_id}"} for unit_id in expected_specs
        },
    )


def scenarios() -> list[Scenario]:
    """Return the ten required semantic edit shapes."""

    return [
        _scenario(
            "body",
            EditKind.BODY,
            {"module.py": "def value() -> int:\n    return 1\n"},
            {"module.py": "def value() -> int:\n    return 2\n"},
            {"unit:value": "Return two."},
        ),
        _scenario(
            "signature",
            EditKind.SIGNATURE,
            {"module.py": "def value() -> int:\n    return 1\n"},
            {"module.py": "def value(default: int = 1) -> int:\n    return default\n"},
            {"unit:value": "Return the caller default, which is one by default."},
        ),
        _scenario(
            "behavior",
            EditKind.BEHAVIOR,
            {"module.py": "def sign(value: int) -> int:\n    return 1\n"},
            {
                "module.py": (
                    "def sign(value: int) -> int:\n"
                    "    if value < 0:\n"
                    "        return -1\n"
                    "    return 1\n"
                )
            },
            {"unit:sign": "Return minus one for negative values and one otherwise."},
        ),
        _scenario(
            "docstring",
            EditKind.DOCSTRING,
            {
                "module.py": 'def value() -> int:\n    """Return a value."""\n    return 1\n'
            },
            {"module.py": 'def value() -> int:\n    """Return one."""\n    return 1\n'},
            {"unit:value": "Return one and document that exact result."},
        ),
        _scenario(
            "import",
            EditKind.IMPORT,
            {"module.py": "def root(value: float) -> float:\n    return value**0.5\n"},
            {
                "module.py": (
                    "from math import sqrt\n\n\n"
                    "def root(value: float) -> float:\n"
                    "    return sqrt(value)\n"
                )
            },
            {"unit:root": "Use math.sqrt to return the square root."},
        ),
        _scenario(
            "rename",
            EditKind.RENAME,
            {"module.py": "def old_name() -> int:\n    return 1\n"},
            {"module.py": "def new_name() -> int:\n    return 1\n"},
            {"unit:stable": "Expose this operation as new_name."},
        ),
        _scenario(
            "move",
            EditKind.MOVE,
            {"a.py": "def helper() -> int:\n    return 1\n", "b.py": ""},
            {"a.py": "", "b.py": "def helper() -> int:\n    return 1\n"},
            {"unit:helper": "Place helper in module b."},
        ),
        _scenario(
            "split",
            EditKind.SPLIT,
            {"module.py": "def both() -> tuple[int, int]:\n    return (1, 2)\n"},
            {
                "module.py": (
                    "def one() -> int:\n"
                    "    return 1\n\n\n"
                    "def two() -> int:\n"
                    "    return 2\n"
                )
            },
            {"unit:one": "Return one.", "unit:two": "Return two."},
        ),
        _scenario(
            "merge",
            EditKind.MERGE,
            {
                "module.py": (
                    "def one() -> int:\n"
                    "    return 1\n\n\n"
                    "def two() -> int:\n"
                    "    return 2\n"
                )
            },
            {"module.py": "def both() -> tuple[int, int]:\n    return (1, 2)\n"},
            {"unit:both": "Return one and two as a tuple."},
        ),
        _scenario(
            "delete",
            EditKind.DELETE,
            {"module.py": "def obsolete() -> None:\n    pass\n"},
            {"module.py": ""},
            {"unit:obsolete": "Delete obsolete behavior and retain its tombstone."},
        ),
    ]


def _valid_payload(scenario: Scenario) -> dict[str, Any]:
    return {
        "base_generation_token": scenario.generation_token,
        "changes": [
            {
                "unit_id": unit_id,
                "edit_kind": scenario.edit_kind.value,
                "semantic_spec": semantic_spec,
                "examples": sorted(scenario.required_examples[unit_id]),
            }
            for unit_id, semantic_spec in sorted(scenario.expected_specs.items())
        ],
    }


def _adversarial_cases() -> list[tuple[str, Scenario, list[ProviderOutcome]]]:
    body = scenarios()[0]
    split = scenarios()[7]
    valid_body = _valid_payload(body)
    valid_split = _valid_payload(split)

    partial = json.loads(json.dumps(valid_split))
    partial["changes"] = partial["changes"][:1]
    hallucinated = json.loads(json.dumps(valid_body))
    hallucinated["changes"].append(
        {
            "unit_id": "unit:invented",
            "edit_kind": "body",
            "semantic_spec": "Invent behavior.",
            "examples": ["example:invented"],
        }
    )
    stale = json.loads(json.dumps(valid_body))
    stale["base_generation_token"] = "token-stale"
    contradictory = json.loads(json.dumps(valid_body))
    contradictory["changes"][0]["examples"].append("CONTRADICTS:return one")
    nonconvergent = json.loads(json.dumps(valid_body))
    nonconvergent["changes"][0]["semantic_spec"] = "Return the old value."
    source_backed = json.loads(json.dumps(valid_body))
    source_backed["changes"][0]["source_contract"] = body.edited_sources["module.py"]

    return [
        ("malformed", body, [ProviderOutcome("payload", "not-a-mapping")]),
        ("partial", split, [ProviderOutcome("payload", partial)]),
        ("hallucinated", body, [ProviderOutcome("payload", hallucinated)]),
        ("stale", body, [ProviderOutcome("payload", stale)]),
        ("contradictory", body, [ProviderOutcome("payload", contradictory)]),
        ("timeout", body, [ProviderOutcome("timeout")]),
        ("cancel", body, [ProviderOutcome("cancel")]),
        ("nonconvergent", body, [ProviderOutcome("payload", nonconvergent)]),
        ("undeclared-source-field", body, [ProviderOutcome("payload", source_backed)]),
    ]


async def run_suite(artifacts: Path | None = None) -> dict[str, Any]:
    """Run success and rejection matrices with expected classifications."""

    success_results: dict[str, dict[str, Any]] = {}
    false_rejections = 0
    for scenario in scenarios():
        result = await promote(
            scenario,
            ScriptedProvider([ProviderOutcome("payload", _valid_payload(scenario))]),
        )
        success_results[scenario.name] = result.model_dump(mode="json")
        if not result.accepted:
            false_rejections += 1

    rejection_results: dict[str, dict[str, Any]] = {}
    false_acceptances = 0
    for name, scenario, outcomes in _adversarial_cases():
        result = await promote(scenario, ScriptedProvider(outcomes))
        rejection_results[name] = result.model_dump(mode="json")
        if result.accepted:
            false_acceptances += 1
        if not result.edited_source_preserved or not result.accepted_store_preserved:
            raise AssertionError(f"{name} changed rejected input bytes")

    results: dict[str, Any] = {
        "success_cases": success_results,
        "rejection_cases": rejection_results,
        "metrics": {
            "expected_acceptances": len(success_results),
            "expected_rejections": len(rejection_results),
            "false_acceptances": false_acceptances,
            "false_rejections": false_rejections,
            "orchestration_false_acceptance_rate": (
                false_acceptances / len(rejection_results)
            ),
            "orchestration_false_rejection_rate": (
                false_rejections / len(success_results)
            ),
            "model_quality_false_acceptance_rate": "unknown",
            "model_quality_false_rejection_rate": "unknown",
        },
        "suite_passed": false_acceptances == 0 and false_rejections == 0,
    }

    if artifacts is not None:
        if artifacts.exists() and any(artifacts.iterdir()):
            raise ValueError(f"artifact directory is not fresh: {artifacts}")
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "results.json").write_text(
            json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (artifacts / "environment.json").write_text(
            json.dumps(
                {
                    "command": " ".join(sys.argv),
                    "max_attempts": MAX_ATTEMPTS,
                    "provider_timeout_seconds": PROVIDER_TIMEOUT_SECONDS,
                    "python": platform.python_version(),
                    "provider": "local scripted deterministic provider",
                    "network": "not used",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        failures = artifacts / "failure-proposals"
        failures.mkdir()
        for name, result in rejection_results.items():
            (failures / f"{name}.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    try:
        results = asyncio.run(run_suite(args.artifacts))
    except Exception as error:
        args.artifacts.mkdir(parents=True, exist_ok=True)
        (args.artifacts / "failure.txt").write_text(
            f"status=failed\nerror_type={type(error).__name__}\nerror={error}\n",
            encoding="utf-8",
        )
        raise
    print(json.dumps(results["metrics"], indent=2, sort_keys=True))
    return 0 if results["suite_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
