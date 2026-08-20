"""Narrow round-trip prototype for model-owned Python declarations."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

import tree_sitter_python
from pydantic import BaseModel, ConfigDict, Field
from pydantree_sitter import Language, M, OutputModel, Span, capture, source_meta
from templateer.api import TemplateRegistry

ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = ROOT / "templates"
PYTHON_LANGUAGE = Language.from_module(tree_sitter_python)


class FunctionSpan(OutputModel):
    """Pydantree row for every function declaration."""

    __match__ = M("module", ..., "function_definition")
    model_config = {"arbitrary_types_allowed": True}

    name: str = capture("name")
    span: Span = source_meta()


class ClassSpan(OutputModel):
    """Pydantree row for every class declaration."""

    __match__ = M("module", ..., "class_definition")
    model_config = {"arbitrary_types_allowed": True}

    name: str = capture("name")
    span: Span = source_meta()


class DerivedDeclaration(BaseModel):
    """Regenerable declaration fields."""

    model_config = ConfigDict(extra="forbid")

    source: str
    signature: str
    docstring: str | None
    body: str
    imports: list[str]
    fingerprint: str
    start_byte: int
    end_byte: int


class ModuleDerived(BaseModel):
    """Regenerable module-level material."""

    model_config = ConfigDict(extra="forbid")

    docstring: str | None
    future_imports: list[str]
    constants: list[str]


class UnitBase(BaseModel):
    """Fields common to every active unit."""

    model_config = ConfigDict(extra="forbid")

    unit_id: str
    module: str
    qualified_name: str
    parent_id: str | None = None
    spec: str
    examples: list[str] = Field(default_factory=list)

    @property
    def location(self) -> str:
        return f"{self.module}::{self.qualified_name}"


class ModuleUnit(UnitBase):
    """One module's module-level material."""

    kind: Literal["module"] = "module"
    derived: ModuleDerived


class ClassUnit(UnitBase):
    """One class shell. Methods remain separate child units."""

    kind: Literal["class"] = "class"
    derived: DerivedDeclaration


class FunctionUnit(UnitBase):
    """One top-level function."""

    kind: Literal["function"] = "function"
    derived: DerivedDeclaration


class MethodUnit(UnitBase):
    """One class method."""

    kind: Literal["method"] = "method"
    derived: DerivedDeclaration


DeclarationUnit = Annotated[
    ClassUnit | FunctionUnit | MethodUnit,
    Field(discriminator="kind"),
]
ActiveUnit = Annotated[
    ModuleUnit | ClassUnit | FunctionUnit | MethodUnit,
    Field(discriminator="kind"),
]


class Tombstone(BaseModel):
    """Recoverable record for a deleted declaration."""

    model_config = ConfigDict(extra="forbid")

    unit: DeclarationUnit
    removed_from: str
    reason: str


class UnitStore(BaseModel):
    """Disposable spike-local store."""

    model_config = ConfigDict(extra="forbid")

    units: list[ActiveUnit]
    tombstones: list[Tombstone] = Field(default_factory=list)

    def by_id(self) -> dict[str, ActiveUnit]:
        return {unit.unit_id: unit for unit in self.units}

    def declarations(self) -> list[DeclarationUnit]:
        return [unit for unit in self.units if unit.kind != "module"]


class StructuralDiff(BaseModel):
    """Exact change report keyed by durable unit identifiers."""

    changed: list[str] = Field(default_factory=list)
    moved: list[str] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)


class UnsupportedEditError(RuntimeError):
    """The edit has no safe unit route."""

    def __init__(self, message: str, owner: str) -> None:
        super().__init__(f"{message}; owner={owner}")
        self.owner = owner


class PromotionRejectedError(RuntimeError):
    """The convergence guard rejected a promoted spec."""

    def __init__(self, location: str) -> None:
        super().__init__(
            f"promotion did not reproduce edited declaration; owner={location}"
        )
        self.owner = location


@dataclass
class Declaration:
    """Parsed declaration before it enters the typed store."""

    module: str
    qualified_name: str
    kind: Literal["class", "function", "method"]
    source: str
    signature: str
    docstring: str | None
    body: str
    fingerprint: str
    start_byte: int
    end_byte: int
    used_names: set[str]
    imports: list[str] = field(default_factory=list)
    parent_location: str | None = None

    @property
    def location(self) -> str:
        return f"{self.module}::{self.qualified_name}"


@dataclass
class ParsedModule:
    """One parsed source module and its extracted declarations."""

    name: str
    source: str
    docstring_source: str | None
    future_imports: list[str]
    actual_imports: list[str]
    constants: list[str]
    declarations: list[Declaration]
    import_bindings: dict[str, str]


def sha256(text: str) -> str:
    """Return a stable hexadecimal content hash."""

    return hashlib.sha256(text.encode()).hexdigest()


def stable_id(location: str, fingerprint: str) -> str:
    """Create a durable identifier at the first observed location."""

    identity = location + "\0" + fingerprint
    return f"u-{sha256(identity)[:16]}"


def source_spec(source: str, summary: str) -> str:
    """Create the deterministic promotion test double's authored spec."""

    return json.dumps(
        {"summary": summary, "source_contract": source},
        sort_keys=True,
        separators=(",", ":"),
    )


def derive_from_spec(spec: str, previous_source: str) -> str:
    """Re-derive source from a deterministic source-backed spec."""

    data = json.loads(spec)
    return str(data.get("source_contract", previous_source))


def promote_spec(old_spec: str, old_source: str, edited_source: str) -> str:
    """Promote an edited declaration into its authored spec."""

    if "PROMOTION_MUST_FAIL" in edited_source:
        return old_spec
    summary = json.loads(old_spec).get("summary", "Preserve declaration intent.")
    return source_spec(edited_source, summary)


def format_python(source: str, filename: str) -> str:
    """Apply Ruff as the final render step."""

    result = subprocess.run(
        ["ruff", "format", "--stdin-filename", filename, "-"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ruff format failed for {filename}: {result.stderr.strip()}"
        )
    return result.stdout


def _line_starts(source: str) -> list[int]:
    starts = [0]
    for line in source.splitlines(keepends=True):
        starts.append(starts[-1] + len(line.encode()))
    return starts


def _node_start_byte(node: ast.AST, starts: list[int]) -> int:
    decorators = getattr(node, "decorator_list", [])
    if decorators:
        first = min(decorators, key=lambda item: (item.lineno, item.col_offset))
        return starts[first.lineno - 1] + max(first.col_offset - 1, 0)
    return starts[node.lineno - 1] + node.col_offset


def _source_segment(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise UnsupportedEditError("AST node has no source segment", "<module>")
    return segment


def _signature(node: ast.FunctionDef | ast.ClassDef) -> str:
    clone = copy.deepcopy(node)
    clone.decorator_list = []
    clone.body = [ast.Pass()]
    rendered = ast.unparse(clone)
    return rendered.split("\n    pass", 1)[0]


def _body(source: str, node: ast.FunctionDef | ast.ClassDef) -> str:
    statements = list(node.body)
    if statements and isinstance(statements[0], ast.Expr):
        value = statements[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            statements = statements[1:]
    return "\n".join(_source_segment(source, statement) for statement in statements)


def _fingerprint(node: ast.FunctionDef | ast.ClassDef) -> str:
    clone = copy.deepcopy(node)
    clone.name = "<declaration>"
    return sha256(ast.dump(clone, annotate_fields=True, include_attributes=False))


def _used_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _reject_nested(node: ast.FunctionDef, owner: str) -> None:
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(
            child, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef, ast.Lambda)
        ):
            raise UnsupportedEditError(
                "nested or asynchronous declaration is unsupported", owner
            )
        if isinstance(child, (ast.Yield, ast.YieldFrom)):
            raise UnsupportedEditError("generator declaration is unsupported", owner)


def _span_for(
    rows: list[FunctionSpan] | list[ClassSpan],
    name: str,
    line: int,
    owner: str,
) -> Span:
    matches = [row.span for row in rows if row.name == name and row.span.line == line]
    if len(matches) != 1:
        raise UnsupportedEditError("pydantree span is missing or ambiguous", owner)
    return matches[0]


def _import_details(
    source: str, tree: ast.Module
) -> tuple[list[str], list[str], dict[str, str]]:
    futures: list[str] = []
    imports: list[str] = []
    bindings: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        text = _source_segment(source, node)
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            futures.append(text)
            continue
        imports.append(text)
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = text
        else:
            if node.level:
                raise UnsupportedEditError("relative import is unsupported", "<module>")
            for alias in node.names:
                if alias.name == "*":
                    raise UnsupportedEditError(
                        "wildcard import is unsupported", "<module>"
                    )
                bindings[alias.asname or alias.name] = text
    return sorted(futures), sorted(imports), bindings


def parse_module(module: str, source: str) -> ParsedModule:
    """Parse one module into unit candidates and pydantree byte spans."""

    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise UnsupportedEditError(
            f"Python syntax error: {error.msg}", f"{module}::<module>"
        ) from error

    function_rows = FunctionSpan.extract(source, language=PYTHON_LANGUAGE)
    class_rows = ClassSpan.extract(source, language=PYTHON_LANGUAGE)
    starts = _line_starts(source)
    futures, imports, bindings = _import_details(source, tree)
    docstring_source: str | None = None
    constants: list[str] = []
    declarations: list[Declaration] = []

    first = tree.body[0] if tree.body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        docstring_source = _source_segment(source, first)

    allowed_module = (ast.Expr, ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef):
            raise UnsupportedEditError(
                "asynchronous function is unsupported", f"{module}::{node.name}"
            )
        if isinstance(node, ast.FunctionDef):
            owner = f"{module}::{node.name}"
            _reject_nested(node, owner)
            row_span = _span_for(function_rows, node.name, node.lineno, owner)
            start_byte = _node_start_byte(node, starts)
            declaration_source = source.encode()[
                start_byte : row_span.end_byte
            ].decode()
            declarations.append(
                Declaration(
                    module=module,
                    qualified_name=node.name,
                    kind="function",
                    source=declaration_source,
                    signature=_signature(node),
                    docstring=ast.get_docstring(node, clean=False),
                    body=_body(source, node),
                    fingerprint=_fingerprint(node),
                    start_byte=start_byte,
                    end_byte=row_span.end_byte,
                    used_names=_used_names(node),
                )
            )
            continue
        if isinstance(node, ast.ClassDef):
            class_owner = f"{module}::{node.name}"
            class_span = _span_for(class_rows, node.name, node.lineno, class_owner)
            method_nodes: list[ast.FunctionDef] = []
            for child in node.body:
                if isinstance(child, ast.AsyncFunctionDef):
                    raise UnsupportedEditError(
                        "asynchronous method is unsupported", class_owner
                    )
                if isinstance(child, ast.ClassDef):
                    raise UnsupportedEditError(
                        "nested class is unsupported", class_owner
                    )
                if isinstance(child, ast.FunctionDef):
                    _reject_nested(child, f"{class_owner}.{child.name}")
                    method_nodes.append(child)
            class_start = _node_start_byte(node, starts)
            if method_nodes:
                first_method_start = starts[
                    min(
                        [method_nodes[0], *method_nodes[0].decorator_list],
                        key=lambda item: (item.lineno, item.col_offset),
                    ).lineno
                    - 1
                ]
                shell_source = (
                    source.encode()[class_start:first_method_start].decode().rstrip()
                )
            else:
                shell_source = source.encode()[
                    class_start : class_span.end_byte
                ].decode()
            shell_node = copy.deepcopy(node)
            shell_node.body = [
                child
                for child in shell_node.body
                if not isinstance(child, ast.FunctionDef)
            ]
            declarations.append(
                Declaration(
                    module=module,
                    qualified_name=node.name,
                    kind="class",
                    source=shell_source,
                    signature=_signature(node),
                    docstring=ast.get_docstring(node, clean=False),
                    body=_body(source, shell_node),
                    fingerprint=_fingerprint(shell_node),
                    start_byte=class_start,
                    end_byte=class_span.end_byte,
                    used_names=_used_names(shell_node),
                )
            )
            for method in method_nodes:
                owner = f"{class_owner}.{method.name}"
                row_span = _span_for(function_rows, method.name, method.lineno, owner)
                start_byte = _node_start_byte(method, starts)
                method_source = source.encode()[start_byte : row_span.end_byte].decode()
                declarations.append(
                    Declaration(
                        module=module,
                        qualified_name=f"{node.name}.{method.name}",
                        kind="method",
                        source=method_source,
                        signature=_signature(method),
                        docstring=ast.get_docstring(method, clean=False),
                        body=_body(source, method),
                        fingerprint=_fingerprint(method),
                        start_byte=start_byte,
                        end_byte=row_span.end_byte,
                        used_names=_used_names(method),
                        parent_location=class_owner,
                    )
                )
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            constants.append(_source_segment(source, node))
            continue
        if not isinstance(node, allowed_module):
            raise UnsupportedEditError(
                f"module-level {type(node).__name__} is unsupported",
                f"{module}::<module>",
            )

    for declaration in declarations:
        declaration.imports = sorted(
            {line for name, line in bindings.items() if name in declaration.used_names}
        )

    return ParsedModule(
        name=module,
        source=source,
        docstring_source=docstring_source,
        future_imports=futures,
        actual_imports=imports,
        constants=constants,
        declarations=declarations,
        import_bindings=bindings,
    )


def parse_tree(sources: dict[str, str]) -> dict[str, ParsedModule]:
    """Parse a complete edited tree and derive cross-module imports."""

    parsed = {
        module: parse_module(module, source)
        for module, source in sorted(sources.items())
    }
    top_level: dict[str, list[str]] = {}
    for module, item in parsed.items():
        for declaration in item.declarations:
            if "." not in declaration.qualified_name:
                top_level.setdefault(declaration.qualified_name, []).append(module)
    for module, item in parsed.items():
        for declaration in item.declarations:
            for name in declaration.used_names:
                owners = [owner for owner in top_level.get(name, []) if owner != module]
                if len(owners) == 1:
                    declaration.imports = sorted(
                        {*declaration.imports, f"from {owners[0]} import {name}"}
                    )
                elif len(owners) > 1:
                    raise UnsupportedEditError(
                        f"cross-module symbol {name!r} is ambiguous",
                        declaration.location,
                    )
    return parsed


def _derived(declaration: Declaration, source: str | None = None) -> DerivedDeclaration:
    return DerivedDeclaration(
        source=source if source is not None else declaration.source,
        signature=declaration.signature,
        docstring=declaration.docstring,
        body=declaration.body,
        imports=declaration.imports,
        fingerprint=declaration.fingerprint,
        start_byte=declaration.start_byte,
        end_byte=declaration.end_byte,
    )


def initial_ingest(sources: dict[str, str]) -> UnitStore:
    """Create the first store from a formatted source tree."""

    parsed = parse_tree(sources)
    units: list[ActiveUnit] = []
    location_ids: dict[str, str] = {}
    for module, item in parsed.items():
        module_location = f"{module}::<module>"
        module_id = stable_id(module_location, sha256(item.source))
        location_ids[module_location] = module_id
        units.append(
            ModuleUnit(
                unit_id=module_id,
                module=module,
                qualified_name="<module>",
                spec=source_spec(
                    item.docstring_source or "", "Preserve module material."
                ),
                derived=ModuleDerived(
                    docstring=item.docstring_source,
                    future_imports=item.future_imports,
                    constants=item.constants,
                ),
            )
        )
        for declaration in item.declarations:
            location_ids[declaration.location] = stable_id(
                declaration.location, declaration.fingerprint
            )
    for item in parsed.values():
        for declaration in item.declarations:
            unit_type = {
                "class": ClassUnit,
                "function": FunctionUnit,
                "method": MethodUnit,
            }[declaration.kind]
            units.append(
                unit_type(
                    unit_id=location_ids[declaration.location],
                    module=declaration.module,
                    qualified_name=declaration.qualified_name,
                    parent_id=(
                        location_ids[declaration.parent_location]
                        if declaration.parent_location
                        else location_ids[f"{declaration.module}::<module>"]
                    ),
                    spec=source_spec(
                        declaration.source, f"Preserve {declaration.location}."
                    ),
                    derived=_derived(declaration),
                )
            )
    return UnitStore(units=sorted(units, key=lambda unit: unit.unit_id))


def _module_sections(store: UnitStore, module: str) -> list[str]:
    modules = [
        unit for unit in store.units if unit.kind == "module" and unit.module == module
    ]
    if len(modules) != 1:
        raise RuntimeError(f"expected one module unit for {module}, got {len(modules)}")
    module_unit = modules[0]
    declarations = [unit for unit in store.declarations() if unit.module == module]
    imports = sorted({line for unit in declarations for line in unit.derived.imports})
    sections: list[str] = []
    if module_unit.derived.docstring:
        sections.append(module_unit.derived.docstring)
    if module_unit.derived.future_imports:
        sections.append("\n".join(sorted(module_unit.derived.future_imports)))
    if imports:
        sections.append("\n".join(imports))
    if module_unit.derived.constants:
        sections.append("\n".join(sorted(module_unit.derived.constants)))
    functions = sorted(
        [unit for unit in declarations if unit.kind == "function"],
        key=lambda unit: unit.qualified_name,
    )
    sections.extend(unit.derived.source for unit in functions)
    classes = sorted(
        [unit for unit in declarations if unit.kind == "class"],
        key=lambda unit: unit.qualified_name,
    )
    for class_unit in classes:
        methods = sorted(
            [
                unit
                for unit in declarations
                if unit.kind == "method" and unit.parent_id == class_unit.unit_id
            ],
            key=lambda unit: unit.qualified_name,
        )
        class_source = class_unit.derived.source
        if methods:
            class_source += "\n\n" + "\n\n".join(
                textwrap.indent(method.derived.source, "    ") for method in methods
            )
        sections.append(class_source)
    return sections


def render_tree(store: UnitStore) -> dict[str, str]:
    """Render every module through Templateer and Ruff."""

    registry = TemplateRegistry.from_paths([TEMPLATE_ROOT])
    modules = sorted({unit.module for unit in store.units if unit.kind == "module"})
    rendered: dict[str, str] = {}
    for module in modules:
        raw = registry.render_from_model(
            template_name="python-module",
            model_data={"sections": _module_sections(store, module)},
        )
        rendered[module] = format_python(raw, f"{module}.py")
    return rendered


def structural_diff(before: UnitStore, after: UnitStore) -> StructuralDiff:
    """Compare durable unit keys without text alignment heuristics."""

    old = before.by_id()
    new = after.by_id()
    report = StructuralDiff()
    report.added = sorted(set(new) - set(old))
    report.removed = sorted(set(old) - set(new))
    for unit_id in sorted(set(old) & set(new)):
        old_unit = old[unit_id]
        new_unit = new[unit_id]
        if old_unit.location != new_unit.location:
            report.moved.append(unit_id)
        if old_unit.kind == "module" and new_unit.kind == "module":
            content_changed = old_unit.derived != new_unit.derived
        elif old_unit.kind != "module" and new_unit.kind != "module":
            content_changed = old_unit.derived.source != new_unit.derived.source
        else:
            content_changed = True
        if content_changed:
            report.changed.append(unit_id)
    return report


def _match_declarations(
    before: UnitStore,
    declarations: list[Declaration],
) -> tuple[dict[str, str], set[str], set[str]]:
    old_units = {unit.location: unit for unit in before.declarations()}
    new_by_location = {
        declaration.location: declaration for declaration in declarations
    }
    matches = {
        location: old_units[location].unit_id
        for location in sorted(set(old_units) & set(new_by_location))
    }
    old_unmatched = [
        unit for location, unit in old_units.items() if location not in matches
    ]
    new_unmatched = [
        item for location, item in new_by_location.items() if location not in matches
    ]
    old_by_fingerprint: dict[str, list[DeclarationUnit]] = {}
    new_by_fingerprint: dict[str, list[Declaration]] = {}
    for unit in old_unmatched:
        old_by_fingerprint.setdefault(unit.derived.fingerprint, []).append(unit)
    for declaration in new_unmatched:
        new_by_fingerprint.setdefault(declaration.fingerprint, []).append(declaration)
    bridged_old: set[str] = set()
    bridged_new: set[str] = set()
    for fingerprint in sorted(set(old_by_fingerprint) & set(new_by_fingerprint)):
        old_candidates = old_by_fingerprint[fingerprint]
        new_candidates = new_by_fingerprint[fingerprint]
        if len(old_candidates) != 1 or len(new_candidates) != 1:
            owner = (
                new_candidates[0].location
                if new_candidates
                else old_candidates[0].location
            )
            raise UnsupportedEditError("rename or move identity is ambiguous", owner)
        old_unit = old_candidates[0]
        declaration = new_candidates[0]
        matches[declaration.location] = old_unit.unit_id
        bridged_old.add(old_unit.unit_id)
        bridged_new.add(declaration.location)
    removed = {
        unit.unit_id for unit in old_unmatched if unit.unit_id not in bridged_old
    }
    added = {
        item.location for item in new_unmatched if item.location not in bridged_new
    }
    return matches, removed, added


def _collated_owner(parsed: ParsedModule, expected_imports: set[str]) -> str:
    changed = set(parsed.actual_imports) ^ expected_imports
    for line in sorted(changed):
        bound = [
            name
            for name, import_line in parsed.import_bindings.items()
            if import_line == line
        ]
        for declaration in parsed.declarations:
            if any(name in declaration.used_names for name in bound):
                return declaration.location
    return f"{parsed.name}::<module>"


def ingest_tree(
    before: UnitStore,
    sources: dict[str, str],
    failure_dir: Path | None = None,
) -> tuple[UnitStore, StructuralDiff, dict[str, str]]:
    """Ingest one edited tree transactionally and enforce convergence."""

    try:
        parsed = parse_tree(sources)
        declarations = [
            item for module in parsed.values() for item in module.declarations
        ]
        matches, removed_ids, added_locations = _match_declarations(
            before, declarations
        )
        old_by_id = before.by_id()
        module_ids = {
            unit.module: unit.unit_id for unit in before.units if unit.kind == "module"
        }
        new_units: list[ActiveUnit] = []
        location_ids: dict[str, str] = {}

        for module, item in parsed.items():
            old_modules = [
                unit
                for unit in before.units
                if unit.kind == "module" and unit.module == module
            ]
            if old_modules:
                old_module = old_modules[0]
                if (
                    old_module.derived.docstring != item.docstring_source
                    or old_module.derived.constants != item.constants
                ):
                    raise UnsupportedEditError(
                        "module boilerplate or constant edit is unsupported",
                        old_module.location,
                    )
                module_unit = old_module.model_copy(deep=True)
                module_unit.derived.future_imports = item.future_imports
            else:
                location = f"{module}::<module>"
                module_unit = ModuleUnit(
                    unit_id=stable_id(location, sha256(item.source)),
                    module=module,
                    qualified_name="<module>",
                    spec=source_spec(
                        item.docstring_source or "", "Preserve module material."
                    ),
                    derived=ModuleDerived(
                        docstring=item.docstring_source,
                        future_imports=item.future_imports,
                        constants=item.constants,
                    ),
                )
            module_ids[module] = module_unit.unit_id
            new_units.append(module_unit)

        for declaration in declarations:
            unit_id = matches.get(declaration.location)
            if unit_id is None:
                unit_id = stable_id(declaration.location, declaration.fingerprint)
            location_ids[declaration.location] = unit_id

        for declaration in declarations:
            unit_type = {
                "class": ClassUnit,
                "function": FunctionUnit,
                "method": MethodUnit,
            }[declaration.kind]
            unit_id = location_ids[declaration.location]
            old = old_by_id.get(unit_id)
            new_spec = (
                old.spec
                if old is not None
                else source_spec(
                    declaration.source, f"Preserve {declaration.location}."
                )
            )
            derived_source = declaration.source
            if old is not None and old.derived.source != declaration.source:
                new_spec = promote_spec(
                    old.spec, old.derived.source, declaration.source
                )
                derived_source = derive_from_spec(new_spec, old.derived.source)
                if format_python(
                    derived_source + "\n", "declaration.py"
                ) != format_python(declaration.source + "\n", "declaration.py"):
                    raise PromotionRejectedError(declaration.location)
            unit = unit_type(
                unit_id=unit_id,
                module=declaration.module,
                qualified_name=declaration.qualified_name,
                parent_id=(
                    location_ids[declaration.parent_location]
                    if declaration.parent_location
                    else module_ids[declaration.module]
                ),
                spec=new_spec,
                examples=old.examples if old is not None else [],
                derived=_derived(declaration, derived_source),
            )
            new_units.append(unit)

        tombstones = list(before.tombstones)
        for unit_id in sorted(removed_ids):
            unit = old_by_id[unit_id]
            if unit.kind == "module":
                continue
            tombstones.append(
                Tombstone(
                    unit=unit,
                    removed_from=unit.location,
                    reason="declaration absent from edited source tree",
                )
            )
        candidate = UnitStore(
            units=sorted(new_units, key=lambda unit: unit.unit_id),
            tombstones=tombstones,
        )
        report = structural_diff(before, candidate)
        rendered = render_tree(candidate)

        moved_or_added = bool(report.moved or report.added)
        if not moved_or_added:
            candidate_by_id = candidate.by_id()
            for unit_id, old_unit in old_by_id.items():
                new_unit = candidate_by_id.get(unit_id)
                if (
                    old_unit.kind != "module"
                    and new_unit is not None
                    and new_unit.kind != "module"
                    and old_unit.derived.imports != new_unit.derived.imports
                ):
                    raise UnsupportedEditError(
                        "import requirement is collated; change the owning declaration spec",
                        new_unit.location,
                    )
        for module, item in parsed.items():
            expected_imports = {
                line
                for unit in candidate.declarations()
                if unit.module == module
                for line in unit.derived.imports
            }
            if set(item.actual_imports) != expected_imports and not moved_or_added:
                owner = _collated_owner(item, expected_imports)
                raise UnsupportedEditError(
                    "import block is collated; change the owning declaration requirement",
                    owner,
                )
        if rendered != sources:
            mismatched = sorted(
                module for module in sources if rendered.get(module) != sources[module]
            )
            owner = f"{mismatched[0]}::<module>" if mismatched else "<tree>"
            raise UnsupportedEditError(
                f"rendered bytes do not reproduce edited tree: {', '.join(mismatched)}",
                owner,
            )
        return candidate, report, rendered
    except Exception as error:
        if failure_dir is not None:
            failure_dir.mkdir(parents=True, exist_ok=True)
            artifact = {
                "status": "rejected",
                "error_type": type(error).__name__,
                "error": str(error),
                "edited_hashes": {
                    module: sha256(source) for module, source in sources.items()
                },
                "accepted_store_hash": sha256(before.model_dump_json()),
                "source_preserved": True,
                "store_update_accepted": False,
            }
            (failure_dir / "proposal.json").write_text(
                json.dumps(artifact, indent=2, sort_keys=True) + "\n"
            )
        raise


def save_store(store: UnitStore, path: Path) -> None:
    """Persist a disposable typed store as deterministic JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(store.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
