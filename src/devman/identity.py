"""Resolve repository project identity at the Devman command boundary.

The repository manifest is the source of project identity.  The literal
``devman.project`` forms remain a compatibility read for repositories that do
not have the manifest yet.  This module does not infer identity from a path or
write any repository or machine state.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .contract import MANIFEST_NAME, ContractError, ProjectManifest
from .registry import RegistryError, identity_fault


class IdentityError(RegistryError):
    """A repository does not state one usable project identity."""


class LinkConfigurationError(RegistryError):
    """The central link declaration cannot be used safely."""


@dataclass(frozen=True, slots=True)
class ProjectIdentity:
    """The identity selected for one repository command."""

    project: str
    root: Path
    source: str
    manifest: ProjectManifest | None
    compatibility: str | None


@dataclass(frozen=True, slots=True)
class LinkConfiguration:
    """The validated central configuration used by one link command."""

    project: str
    root: Path
    overlay: Path
    central_file: Path
    declarations: dict[str, dict[str, object]]


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


def central_link_file(overlay: Path | str, project: str) -> Path:
    """Return the one central bootstrap file for ``project``."""

    fault = identity_fault("project", project)
    if fault:
        raise LinkConfigurationError(
            f"invalid field 'project' {project!r}: {fault}\n"
            "repair: use the manifest identity or a valid --project"
        )
    return (
        Path(os.path.expandvars(str(overlay))).expanduser().resolve()
        / "projects"
        / project
        / "devenv.local.nix"
    )


def _link_declarations(raw: object, *, source: str) -> dict[str, dict[str, object]]:
    if not isinstance(raw, Mapping):
        raise LinkConfigurationError(
            f"{source} must evaluate to a devman.link attribute set\n"
            "repair: keep one devman.link block with canonical, path, and"
            " optional template fields"
        )
    normalized: dict[str, dict[str, object]] = {}
    for view, value in raw.items():
        if not isinstance(view, str) or not isinstance(value, Mapping):
            raise LinkConfigurationError(
                f"{source} has an invalid link declaration for {view!r}\n"
                "repair: use one attribute set per relative view path"
            )
        unknown = [
            field
            for field in value
            if not isinstance(field, str)
            or field not in {"canonical", "path", "template"}
        ]
        if unknown:
            fields = ", ".join(repr(field) for field in unknown)
            raise LinkConfigurationError(
                f"{source} link {view!r} has unknown field(s): {fields}\n"
                "repair: use only canonical, path, and optional template"
            )
        canonical = value.get("canonical", "central")
        if not isinstance(canonical, str) or canonical not in {
            "central",
            "repo",
            "external",
        }:
            raise LinkConfigurationError(
                f"{source} link {view!r} has invalid field 'canonical':"
                f" {canonical!r}\n"
                "repair: set canonical to central, repo, or external"
            )
        path = value.get("path", "")
        if not isinstance(path, str):
            raise LinkConfigurationError(
                f"{source} link {view!r} has non-string field 'path'\n"
                "repair: set path to a relative or external string path"
            )
        template = value.get("template")
        if template is not None and not isinstance(template, str):
            raise LinkConfigurationError(
                f"{source} link {view!r} has non-string field 'template'\n"
                "repair: set template to a string or remove the field"
            )
        normalized[view] = {
            "canonical": canonical,
            "path": path,
            "template": template,
        }
    return normalized


def _nix_quote(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def evaluate_central_file(path: Path, project: str) -> object:
    """Evaluate one central module and return its ``devman.link`` value."""

    executable = shutil.which("nix-instantiate")
    if executable is None:
        raise LinkConfigurationError(
            f"cannot evaluate central configuration {path}: nix-instantiate is not on PATH\n"
            "repair: enter a Nix environment that provides nix-instantiate"
        )
    expression = (
        "let\n"
        f"  module = import {_nix_quote(str(path))} {{\n"
        f"    config = {{ devman = {{ project = {_nix_quote(project)}; }}; }};\n"
        "  };\n"
        "in builtins.toJSON module.devman.link\n"
    )
    try:
        result = subprocess.run(
            [executable, "--eval", "--strict", "--raw", "--expr", expression],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LinkConfigurationError(
            f"cannot evaluate central configuration {path}: {exc}\n"
            "repair: fix the Nix expression, then run link status again"
        ) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise LinkConfigurationError(
            f"cannot evaluate central configuration {path}: {detail or result.returncode}\n"
            "repair: fix the central devenv.local.nix expression, then run link status again"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LinkConfigurationError(
            f"central configuration {path} returned invalid JSON: {exc}\n"
            "repair: keep devman.link as a valid Nix attribute set"
        ) from exc


def validate_link_configuration(
    root: Path | str,
    overlay: Path | str,
    project: str,
    declarations: object | None = None,
    *,
    evaluator: Callable[[Path, str], object] | None = None,
) -> LinkConfiguration:
    """Validate central links before the public link command uses them."""

    repository = Path(root).expanduser().resolve()
    overlay_root = Path(os.path.expandvars(str(overlay))).expanduser().resolve()
    central = central_link_file(overlay_root, project)
    if not repository.is_dir():
        raise LinkConfigurationError(
            f"project repository root does not exist: {repository}\n"
            "repair: pass the real checkout path with --root"
        )
    if not central.is_file():
        raise LinkConfigurationError(
            f"bootstrap central target does not exist: {central}\n"
            "repair: create the central devenv.local.nix before linking it"
        )
    try:
        central.resolve().relative_to(overlay_root)
    except ValueError as exc:
        raise LinkConfigurationError(
            f"bootstrap central target escapes overlayDir: {central}\n"
            "repair: keep the central file below $HOME/.config/devman"
        ) from exc

    expected = (
        None
        if declarations is None
        else _link_declarations(declarations, source="declared links")
    )
    expected_bootstrap = (
        expected.pop("devenv.local.nix", None) if expected is not None else None
    )
    actual = _link_declarations(
        (evaluator or evaluate_central_file)(central, project),
        source=f"central configuration {central}",
    )
    actual_bootstrap = actual.pop("devenv.local.nix", None)
    if expected is not None and actual != expected:
        raise LinkConfigurationError(
            f"central configuration {central} does not resolve to the manifest"
            f" identity {project!r}\n"
            f"  expected links: {json.dumps(expected, sort_keys=True)}\n"
            f"  actual links: {json.dumps(actual, sort_keys=True)}\n"
            "repair: make devenv.local.nix use the manifest identity through"
            " config.devman.project, then re-enter the shell"
        )

    if (
        expected_bootstrap is not None
        and actual_bootstrap is not None
        and expected_bootstrap != actual_bootstrap
    ):
        raise LinkConfigurationError(
            f"central bootstrap declarations disagree for {central}\n"
            f"  declared: {json.dumps(expected_bootstrap, sort_keys=True)}\n"
            f"  central: {json.dumps(actual_bootstrap, sort_keys=True)}\n"
            "repair: keep devenv.local.nix pointed at the central project file"
        )
    bootstrap = (
        expected_bootstrap
        or actual_bootstrap
        or {
            "canonical": "central",
            "path": f"projects/{project}/devenv.local.nix",
            "template": None,
        }
    )
    all_declarations = dict(actual)
    all_declarations["devenv.local.nix"] = bootstrap
    from . import link

    for view, raw in all_declarations.items():
        try:
            declaration = link.Declaration.read(view, raw)
            resolved = link.resolve(
                declaration,
                overlay=overlay_root,
                root=repository,
                project=project,
            )
        except link.LinkError as exc:
            raise LinkConfigurationError(
                f"invalid central link {view!r} for repository root {repository}: {exc}\n"
                "repair: keep views below the repository, central paths below"
                " overlayDir, and external paths outside both roots"
            ) from exc
        if view == "devenv.local.nix" and resolved.canonical_path != central.resolve():
            raise LinkConfigurationError(
                f"bootstrap link points to {resolved.canonical_path}, not {central}\n"
                "repair: point devenv.local.nix at the central project configuration"
            )
    return LinkConfiguration(
        project=project,
        root=repository,
        overlay=overlay_root,
        central_file=central,
        declarations=all_declarations,
    )
