"""Required edit cases for the agent-factory round-trip spike."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from prototype import (
    PromotionRejectedError,
    StructuralDiff,
    UnitStore,
    UnsupportedEditError,
    format_python,
    ingest_tree,
    initial_ingest,
    render_tree,
    save_store,
    sha256,
)

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "fixtures" / "original" / "catalog.py"


def original_sources() -> dict[str, str]:
    """Load the fixed initial source tree."""

    return {"catalog": ORIGINAL.read_text()}


def _remove_block(source: str, start: str, end: str) -> str:
    before, remainder = source.split(start, 1)
    _, after = remainder.split(end, 1)
    return before.rstrip() + "\n\n\n" + end + after


def _case_dir(artifacts: Path | None, name: str) -> Path | None:
    if artifacts is None:
        return None
    target = artifacts / "cases" / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def _save_sources(root: Path, label: str, sources: dict[str, str]) -> None:
    directory = root / label
    directory.mkdir(parents=True, exist_ok=True)
    for module, source in sorted(sources.items()):
        (directory / f"{module}.py").write_text(source)


def _save_success(
    root: Path | None,
    before: UnitStore,
    after: UnitStore,
    edited: dict[str, str],
    rendered: dict[str, str],
    report: StructuralDiff,
) -> None:
    if root is None:
        return
    save_store(before, root / "store-before.json")
    save_store(after, root / "store-after.json")
    _save_sources(root, "edited", edited)
    _save_sources(root, "rendered", rendered)
    (root / "structural-diff.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )


def _result(
    name: str,
    passed: bool,
    report: StructuralDiff | None = None,
    **details: object,
) -> dict[str, object]:
    result: dict[str, object] = {"case": name, "passed": passed, **details}
    if report is not None:
        result["structural_diff"] = report.model_dump(mode="json")
    return result


def _unit_at(store: UnitStore, location: str):
    matches = [unit for unit in store.declarations() if unit.location == location]
    if len(matches) != 1:
        raise AssertionError(f"expected one unit at {location}, got {len(matches)}")
    return matches[0]


def initial_identity(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    store = initial_ingest(sources)
    rendered = render_tree(store)
    repeated = render_tree(store)
    formatting_stable = all(
        format_python(source, f"{module}.py") == source
        for module, source in rendered.items()
    )
    passed = rendered == sources and repeated == rendered and formatting_stable
    root = _case_dir(artifacts, "initial-identity")
    if root is not None:
        save_store(store, root / "store.json")
        _save_sources(root, "original", sources)
        _save_sources(root, "rendered", rendered)
    return _result(
        "initial-identity",
        passed,
        byte_identity_percent=100 if passed else 0,
        deterministic_repeat=repeated == rendered,
        formatting_stable=formatting_stable,
        original_hash=sha256(sources["catalog"]),
        rendered_hash=sha256(rendered["catalog"]),
    )


def body_change(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    edited = {
        "catalog": sources["catalog"].replace(
            'return " ".join(value.strip().lower().split())',
            'return " ".join(value.strip().casefold().split())',
        )
    }
    after, report, rendered = ingest_tree(before, edited)
    before_unit = _unit_at(before, "catalog::normalize_name")
    after_unit = _unit_at(after, "catalog::normalize_name")
    promotion_converged = (
        before_unit.spec != after_unit.spec
        and after_unit.derived.source in rendered["catalog"]
    )
    _save_success(
        _case_dir(artifacts, "body-change"), before, after, edited, rendered, report
    )
    return _result(
        "body-change",
        rendered == edited and len(report.changed) == 1 and promotion_converged,
        report,
        preserved="casefold" in rendered["catalog"],
        promotion_converged=promotion_converged,
    )


def signature_parameter(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    edited = {
        "catalog": sources["catalog"].replace(
            "def normalize_name(value: str) -> str:",
            "def normalize_name(value: str, *, strict: bool = False) -> str:",
        )
    }
    after, report, rendered = ingest_tree(before, edited)
    before_unit = _unit_at(before, "catalog::normalize_name")
    after_unit = _unit_at(after, "catalog::normalize_name")
    promotion_converged = (
        before_unit.spec != after_unit.spec
        and after_unit.derived.source in rendered["catalog"]
    )
    _save_success(
        _case_dir(artifacts, "signature-parameter"),
        before,
        after,
        edited,
        rendered,
        report,
    )
    return _result(
        "signature-parameter",
        rendered == edited and len(report.changed) == 1 and promotion_converged,
        report,
        preserved="strict: bool = False" in rendered["catalog"],
        promotion_converged=promotion_converged,
    )


def docstring_change(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    edited = {
        "catalog": sources["catalog"].replace(
            '"""Return a normalized catalog name."""',
            '"""Return a case-insensitive normalized catalog name."""',
        )
    }
    after, report, rendered = ingest_tree(before, edited)
    before_unit = _unit_at(before, "catalog::normalize_name")
    after_unit = _unit_at(after, "catalog::normalize_name")
    promotion_converged = (
        before_unit.spec != after_unit.spec
        and after_unit.derived.source in rendered["catalog"]
    )
    _save_success(
        _case_dir(artifacts, "docstring-change"),
        before,
        after,
        edited,
        rendered,
        report,
    )
    return _result(
        "docstring-change",
        rendered == edited and len(report.changed) == 1 and promotion_converged,
        report,
        preserved="case-insensitive" in rendered["catalog"],
        promotion_converged=promotion_converged,
    )


def add_function(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    addition = '''

def summarize(values: Iterable[str]) -> str:
    """Return normalized values as one comma-separated string."""
    return ", ".join(normalize_name(value) for value in values)
'''
    edited_source = sources["catalog"].replace(
        "\n\n@dataclass(frozen=True, slots=True)\nclass Catalog:",
        addition + "\n\n@dataclass(frozen=True, slots=True)\nclass Catalog:",
    )
    edited = {"catalog": format_python(edited_source, "catalog.py")}
    after, report, rendered = ingest_tree(before, edited)
    _save_success(
        _case_dir(artifacts, "add-function"), before, after, edited, rendered, report
    )
    added_locations = [after.by_id()[unit_id].location for unit_id in report.added]
    return _result(
        "add-function",
        rendered == edited and "catalog::summarize" in added_locations,
        report,
        added_locations=added_locations,
    )


def delete_function(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    marker = "def build_catalog(values: Iterable[str], limit: int = DEFAULT_LIMIT) -> Catalog:"
    edited_source = _remove_block(sources["catalog"], marker, "def normalize_name")
    edited_source = edited_source.replace("from collections.abc import Iterable\n", "")
    edited = {"catalog": format_python(edited_source, "catalog.py")}
    after, report, rendered = ingest_tree(before, edited)
    _save_success(
        _case_dir(artifacts, "delete-function"), before, after, edited, rendered, report
    )
    tombstones = [item.removed_from for item in after.tombstones]
    return _result(
        "delete-function",
        rendered == edited and "catalog::build_catalog" in tombstones,
        report,
        tombstones=tombstones,
        recoverable=any(
            "def build_catalog" in item.unit.derived.source for item in after.tombstones
        ),
    )


def rename_method(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    edited = {"catalog": sources["catalog"].replace("def require(", "def resolve(")}
    after, report, rendered = ingest_tree(before, edited)
    _save_success(
        _case_dir(artifacts, "rename-method"), before, after, edited, rendered, report
    )
    moved_locations = [after.by_id()[unit_id].location for unit_id in report.moved]
    return _result(
        "rename-method",
        rendered == edited and "catalog::Catalog.resolve" in moved_locations,
        report,
        moved_locations=moved_locations,
    )


def cross_file_move(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    marker = "def normalize_name(value: str) -> str:"
    catalog = _remove_block(sources["catalog"], marker, "@dataclass")
    catalog = catalog.replace(
        "from dataclasses import dataclass\n",
        "from dataclasses import dataclass\nfrom normalization import normalize_name\n",
    )
    normalization = '''"""Normalize catalog names."""

from __future__ import annotations


def normalize_name(value: str) -> str:
    """Return a normalized catalog name."""
    return " ".join(value.strip().lower().split())
'''
    edited = {
        "catalog": format_python(catalog, "catalog.py"),
        "normalization": format_python(normalization, "normalization.py"),
    }
    after, report, rendered = ingest_tree(before, edited)
    _save_success(
        _case_dir(artifacts, "cross-file-move"), before, after, edited, rendered, report
    )
    moved_locations = [after.by_id()[unit_id].location for unit_id in report.moved]
    return _result(
        "cross-file-move",
        rendered == edited and "normalization::normalize_name" in moved_locations,
        report,
        moved_locations=moved_locations,
        unit_churn={
            "changed": len(report.changed),
            "moved": len(report.moved),
            "added": len(report.added),
            "removed": len(report.removed),
        },
    )


def collated_import_rejected(artifacts: Path | None = None) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    edited = {
        "catalog": sources["catalog"].replace(
            "from collections.abc import Iterable",
            "from typing import Iterable",
        )
    }
    root = _case_dir(artifacts, "collated-import-rejected")
    failure_dir = root / "failure" if root is not None else None
    try:
        ingest_tree(before, edited, failure_dir=failure_dir)
    except UnsupportedEditError as error:
        if root is not None:
            save_store(before, root / "store-preserved.json")
            _save_sources(root, "edited-preserved", edited)
        return _result(
            "collated-import-rejected",
            error.owner == "catalog::build_catalog",
            owner=error.owner,
            error=str(error),
        )
    return _result("collated-import-rejected", False, error="edit was accepted")


def failed_promotion_preserves_source(
    artifacts: Path | None = None,
) -> dict[str, object]:
    sources = original_sources()
    before = initial_ingest(sources)
    edited_source = sources["catalog"].replace(
        'return " ".join(value.strip().lower().split())',
        '# PROMOTION_MUST_FAIL\n    return " ".join(value.strip().casefold().split())',
    )
    edited = {"catalog": format_python(edited_source, "catalog.py")}
    root = _case_dir(artifacts, "failed-promotion-preserves-source")
    failure_dir = root / "failure" if root is not None else None
    old_hash = sha256(before.model_dump_json())
    try:
        ingest_tree(before, edited, failure_dir=failure_dir)
    except PromotionRejectedError as error:
        if root is not None:
            save_store(before, root / "store-preserved.json")
            _save_sources(root, "edited-preserved", edited)
        return _result(
            "failed-promotion-preserves-source",
            sha256(before.model_dump_json()) == old_hash
            and "PROMOTION_MUST_FAIL" in edited["catalog"],
            owner=error.owner,
            source_preserved=True,
            store_preserved=True,
        )
    return _result(
        "failed-promotion-preserves-source", False, error="promotion was accepted"
    )


CASES: list[Callable[[Path | None], dict[str, object]]] = [
    initial_identity,
    body_change,
    signature_parameter,
    docstring_change,
    add_function,
    delete_function,
    rename_method,
    cross_file_move,
    collated_import_rejected,
    failed_promotion_preserves_source,
]


def run_all(artifacts: Path | None = None) -> list[dict[str, object]]:
    """Run every required case in a fixed order."""

    initial = CASES[0](artifacts)
    if not initial["passed"]:
        return [initial]
    return [initial, *(case(artifacts) for case in CASES[1:])]
