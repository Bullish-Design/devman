"""Resolve repository project identity at the link adapter boundary.

The repository manifest is the source of project identity.  The literal
``devman.project`` forms remain a compatibility read for repositories that do
not have the manifest yet.  This module does not infer identity from a path or
write any repository or machine state.

It moved here from ``devman.identity`` at 038 Stage 16 so that the adapter owns
one identity resolver and copies no parser.  The old ``devman.identity`` shim
is removed after all callers move to this component.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from devman_contract import (
    MANIFEST_NAME,
    ContractError,
    ProjectManifest,
    identity_fault,
)

from .errors import IdentityError


@dataclass(frozen=True, slots=True)
class ProjectIdentity:
    """The identity selected for one repository command."""

    project: str
    root: Path
    source: str
    manifest: ProjectManifest | None
    compatibility: str | None


@dataclass(frozen=True, slots=True)
class _LegacyIdentity:
    value: str
    source: str


_LITERAL = r'"((?:\\.|[^"\\])*)"'
_IDENTIFIER = r"([A-Za-z_][A-Za-z0-9_-]*)"
_ASSIGNMENT = re.compile(
    rf"(?<![\w.])(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(?:{_LITERAL})\s*;"
)
_DIRECT_PROJECT = re.compile(
    rf"(?<![\w.])devman\s*\.\s*project\s*=\s*(?:{_LITERAL}|{_IDENTIFIER})\s*;"
)
_PROJECT_IN_ATTRSET = re.compile(
    rf"(?<![\w.])project\s*=\s*(?:{_LITERAL}|{_IDENTIFIER})\s*;"
)


def _refusal(root: Path, detail: str, repair: str) -> IdentityError:
    return IdentityError(
        f"cannot resolve project identity for repository root {root}\n"
        f"  {detail}\n"
        f"  repair: {repair}"
    )


def _validate_identity(value: object, *, field: str, root: Path) -> str:
    if not isinstance(value, str):
        raise _refusal(
            root,
            f"field '{field}' must be a string",
            "set a string project identity in .devman/project.toml or pass --project",
        )
    fault = identity_fault("project", value)
    if fault:
        raise _refusal(
            root,
            f"field '{field}' has invalid project identity {value!r}: {fault}",
            "set field 'project' to a valid Dagu name, or pass a matching --project",
        )
    return value


def _strip_comments(text: str) -> str:
    """Remove Nix line comments without changing quoted string contents."""

    output: list[str] = []
    quoted = False
    escaped = False
    comment = False
    for char in text:
        if comment:
            if char == "\n":
                comment = False
                output.append(char)
            continue
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            output.append(char)
        elif char == "#":
            comment = True
        else:
            output.append(char)
    return "".join(output)


def _attrset_body(text: str, start: int) -> str | None:
    """Return the body of the brace at ``start`` when it is balanced."""

    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    return None


def _nix_string(raw: str) -> str:
    """Decode the common quoted Nix spelling used for project names."""

    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw


def _literal_bindings(text: str) -> dict[str, str]:
    return {
        match.group("name"): _nix_string(match.group(2))
        for match in _ASSIGNMENT.finditer(text)
    }


def _project_expression(
    match: re.Match[str], bindings: Mapping[str, str]
) -> str | None:
    expression = match.group(0).partition("=")[2].strip()
    expression = expression.removesuffix(";").strip()
    if expression.startswith('"') and expression.endswith('"'):
        return _nix_string(expression[1:-1])
    return bindings.get(expression)


def _legacy_identities(root: Path) -> list[_LegacyIdentity]:
    """Read literal project values from the old Nix compatibility surface."""

    candidates: list[_LegacyIdentity] = []
    for filename in ("devenv.nix", "devenv.local.nix"):
        path = root / filename
        if not path.is_file() and not path.is_symlink():
            continue
        try:
            text = _strip_comments(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise _refusal(
                root,
                f"cannot read compatibility file {path}: {exc}",
                f"repair or remove {path}, then state identity in {MANIFEST_NAME}",
            ) from exc
        bindings = _literal_bindings(text)
        for match in _DIRECT_PROJECT.finditer(text):
            value = _project_expression(match, bindings)
            if value is not None:
                candidates.append(_LegacyIdentity(value, f"{path}: devman.project"))
        for match in re.finditer(r"(?<![\w.])devman\s*=\s*\{", text):
            body = _attrset_body(text, match.end() - 1)
            if body is None:
                raise _refusal(
                    root,
                    f"compatibility field 'devman' in {path} is not balanced",
                    f"repair {path} or add {MANIFEST_NAME} with field 'project'",
                )
            for assignment in _PROJECT_IN_ATTRSET.finditer(body):
                value = _project_expression(assignment, bindings)
                if value is not None:
                    candidates.append(_LegacyIdentity(value, f"{path}: devman.project"))
    return candidates


def _compatibility_identity(
    root: Path, candidates: list[_LegacyIdentity]
) -> tuple[str | None, tuple[str, ...]]:
    if not candidates:
        return None, ()
    checked = [
        _LegacyIdentity(
            _validate_identity(item.value, field="devman.project", root=root),
            item.source,
        )
        for item in candidates
    ]
    values = {item.value for item in checked}
    if len(values) != 1:
        details = "; ".join(f"{item.source}={item.value!r}" for item in checked)
        raise _refusal(
            root,
            f"compatibility identity has multiple values: {details}",
            f"leave one literal devman.project value, or add one {MANIFEST_NAME}",
        )
    return checked[0].value, tuple(item.source for item in checked)


def _read_manifest(root: Path) -> ProjectManifest | None:
    path = root / MANIFEST_NAME
    if not path.exists() and not path.is_symlink():
        return None
    try:
        return ProjectManifest.from_file(path)
    except ContractError as exc:
        raise _refusal(
            root,
            str(exc),
            f"repair {path} so its schema and field 'project' are valid",
        ) from exc


def resolve_project_identity(
    root: Path | str, explicit: str | None = None
) -> ProjectIdentity:
    """Resolve one project without using the repository directory name.

    An explicit identity wins, but an available manifest still has to agree
    with it.  A manifest is authoritative when it exists.  The old Nix value
    is used only when the manifest is absent, unless it is present alongside a
    manifest and must be checked for drift.
    """

    repository = Path(root).expanduser().resolve()
    manifest = _read_manifest(repository)
    legacy = _legacy_identities(repository)
    compatibility, _sources = _compatibility_identity(repository, legacy)

    if (
        manifest is not None
        and compatibility is not None
        and manifest.project != compatibility
    ):
        raise _refusal(
            repository,
            f"manifest identity: {manifest.project!r}\n"
            f"  compatibility identity: {compatibility!r}",
            "make field 'project' in .devman/project.toml and devman.project"
            " match, then enter the repository shell again",
        )

    if explicit is not None:
        selected = _validate_identity(explicit, field="--project", root=repository)
        if manifest is not None and selected != manifest.project:
            raise _refusal(
                repository,
                f"manifest identity: {manifest.project!r}\n"
                f"  explicit --project identity: {selected!r}",
                "pass --project with the manifest identity, or repair field"
                " 'project' in .devman/project.toml",
            )
        source = "explicit"
    elif manifest is not None:
        selected = manifest.project
        source = "manifest"
    elif compatibility is not None:
        selected = compatibility
        source = "compatibility"
    else:
        raise _refusal(
            repository,
            f"{MANIFEST_NAME} is absent and no literal devman.project exists",
            f"add {MANIFEST_NAME} with field 'project', or pass --project for a"
            " manifest-free compatibility repository",
        )

    return ProjectIdentity(
        project=selected,
        root=repository,
        source=source,
        manifest=manifest,
        compatibility=compatibility,
    )
