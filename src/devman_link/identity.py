"""Resolve repository project identity at the link adapter boundary.

The repository manifest is the source of project identity.  An explicit
``--project`` value remains available for a manifest-free compatibility
repository.  This module does not infer identity from a path or write any
repository or machine state.

It moved here from ``devman.identity`` at 038 Stage 16 so that the adapter owns
one identity resolver and copies no parser.  The old ``devman.identity`` shim
is removed after all callers move to this component.
"""

from __future__ import annotations

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
    with it.  A manifest is authoritative when it exists.  A manifest-free
    repository must supply an explicit identity.
    """

    repository = Path(root).expanduser().resolve()
    manifest = _read_manifest(repository)

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
    else:
        raise _refusal(
            repository,
            f"{MANIFEST_NAME} is absent",
            f"add {MANIFEST_NAME} with field 'project', or pass --project for a"
            " manifest-free compatibility repository",
        )

    return ProjectIdentity(
        project=selected,
        root=repository,
        source=source,
        manifest=manifest,
    )
