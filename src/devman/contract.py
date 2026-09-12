"""Portable Devman contract records.

The repository manifest carries project facts. A plane generation carries
machine facts. A projection record joins both identities without storing a
machine path in the repository.

This module has no Dagu, Nix, or repository-task dependency. Vendomat can use
the records while it builds and activates a plane.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .registry import identity_fault

MANIFEST_NAME = ".devman/project.toml"
CONTRACT_SCHEMA = 1
_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_POLICY_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_GENERATION_DIGEST_FIELDS = (
    "renderer_digest",
    "policy_digest",
    "dagu_digest",
    "toolchain_digest",
)


class ContractError(ValueError):
    """A manifest or identity record does not satisfy the contract."""


def digest_bytes(value: bytes) -> str:
    """Return the stable digest spelling used by contract records."""

    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def digest_file(path: Path) -> str:
    """Digest one file without interpreting its contents."""

    try:
        return digest_bytes(path.read_bytes())
    except OSError as exc:
        raise ContractError(f"cannot digest '{path}': {exc}") from exc


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest_mapping(value: Mapping[str, object]) -> str:
    """Digest a mapping with one canonical JSON representation."""

    return digest_bytes(_canonical_json(dict(value)))


def digest_blobs(blobs: Mapping[str, bytes]) -> str:
    """Digest named source bytes in sorted, length-delimited order.

    Lengths prevent a pair of adjacent names or bodies from becoming an
    ambiguous byte stream. Names must be relative because a source digest must
    not depend on a machine-local absolute path.
    """

    encoded = bytearray()
    for name in sorted(blobs):
        path = Path(name)
        if not name or path.is_absolute() or ".." in path.parts:
            raise ContractError(
                f"source digest name '{name}' must be a relative path without '..'"
            )
        name_bytes = name.encode("utf-8")
        body = blobs[name]
        encoded.extend(len(name_bytes).to_bytes(8, "big"))
        encoded.extend(name_bytes)
        encoded.extend(len(body).to_bytes(8, "big"))
        encoded.extend(body)
    return digest_bytes(bytes(encoded))


def _require_text(raw: Mapping[str, object], field: str, source: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str):
        raise ContractError(f"{source}: field '{field}' must be a string")
    return value


def _validate_reference(field: str, value: str, source: str) -> None:
    if not value:
        raise ContractError(f"{source}: field '{field}' must not be empty")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise ContractError(
            f"{source}: field '{field}' must not contain a control character"
        )
    if "/" in value or "\\" in value:
        raise ContractError(f"{source}: field '{field}' must be a name, not a path")
    if not _REFERENCE_PATTERN.fullmatch(value):
        raise ContractError(
            f"{source}: field '{field}' must start with a letter or digit and"
            " contain only letters, digits, '.', '-' or '_'"
        )


def _validate_digest(field: str, value: object, source: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ContractError(f"{source}: field '{field}' must be a sha256 digest")
    return value


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    """The portable facts a repository declares to the Devman plane."""

    schema: int
    project: str
    groups: tuple[str, ...]
    policy: str

    def __post_init__(self) -> None:
        if self.schema != CONTRACT_SCHEMA:
            raise ContractError(
                f"field 'schema' has unsupported value {self.schema!r};"
                f" supported schema is {CONTRACT_SCHEMA}"
            )
        fault = identity_fault("project", self.project)
        if fault:
            raise ContractError(f"field 'project' is invalid: {fault}")
        if len(set(self.groups)) != len(self.groups):
            raise ContractError("field 'groups' must not contain duplicate names")
        for group in self.groups:
            _validate_reference("groups", group, "manifest")
        if _POLICY_DIGEST_PATTERN.fullmatch(self.policy) is None:
            _validate_reference("policy", self.policy, "manifest")

    @classmethod
    def from_mapping(cls, raw: object, *, source: str = "manifest") -> ProjectManifest:
        """Parse and validate one decoded TOML table."""

        if not isinstance(raw, dict):
            raise ContractError(f"{source}: the document must be a table")
        expected = {"schema", "project", "groups", "policy"}
        unknown = sorted(set(raw) - expected)
        if unknown:
            raise ContractError(f"{source}: unknown field(s): {', '.join(unknown)}")
        schema = raw.get("schema")
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise ContractError(f"{source}: field 'schema' must be an integer")
        if schema != CONTRACT_SCHEMA:
            raise ContractError(
                f"{source}: field 'schema' has unsupported value {schema!r};"
                f" supported schema is {CONTRACT_SCHEMA}"
            )
        project = _require_text(raw, "project", source)
        fault = identity_fault("project", project)
        if fault:
            raise ContractError(f"{source}: field 'project' is invalid: {fault}")
        groups = raw.get("groups")
        if not isinstance(groups, list) or not all(
            isinstance(group, str) for group in groups
        ):
            raise ContractError(f"{source}: field 'groups' must be an array of strings")
        if len(set(groups)) != len(groups):
            raise ContractError(
                f"{source}: field 'groups' must not contain duplicate names"
            )
        for group in groups:
            _validate_reference("groups", group, source)
        policy = _require_text(raw, "policy", source)
        if _POLICY_DIGEST_PATTERN.fullmatch(policy) is None:
            _validate_reference("policy", policy, source)
        return cls(schema, project, tuple(groups), policy)

    @classmethod
    def from_text(cls, text: str, *, source: str = "manifest") -> ProjectManifest:
        """Parse and validate TOML text."""

        try:
            raw = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ContractError(f"{source}: invalid TOML: {exc}") from exc
        return cls.from_mapping(raw, source=source)

    @classmethod
    def from_file(cls, path: Path) -> ProjectManifest:
        """Read and validate ``.devman/project.toml``."""

        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ContractError(f"{path}: manifest does not exist") from exc
        except OSError as exc:
            raise ContractError(f"{path}: cannot read manifest: {exc}") from exc
        return cls.from_text(text, source=str(path))

    @classmethod
    def from_root(cls, root: Path) -> ProjectManifest:
        return cls.from_file(root / MANIFEST_NAME)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "project": self.project,
            "groups": list(self.groups),
            "policy": self.policy,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_mapping())

    @property
    def digest(self) -> str:
        """The identity of the manifest content, not its machine path."""

        return digest_bytes(self.canonical_bytes())

    def to_toml(self) -> str:
        """Render the stable four-field manifest without a TOML dependency."""

        groups = ", ".join(
            json.dumps(group, ensure_ascii=False) for group in self.groups
        )
        return (
            f"schema = {self.schema}\n"
            f"project = {json.dumps(self.project, ensure_ascii=False)}\n"
            f"groups = [{groups}]\n"
            f"policy = {json.dumps(self.policy, ensure_ascii=False)}\n"
        )


@dataclass(frozen=True, slots=True)
class PlaneGeneration:
    """The immutable identities that define one installed plane generation."""

    generation: int
    devman_runtime: str
    renderer_digest: str
    policy_digest: str
    dagu_digest: str
    toolchain_digest: str
    contract_schema: int = CONTRACT_SCHEMA

    def __post_init__(self) -> None:
        if self.generation < 0:
            raise ContractError("field 'generation' must be zero or greater")
        if not self.devman_runtime or "/" in self.devman_runtime:
            raise ContractError(
                "field 'devman_runtime' must be a non-empty runtime identity"
            )
        if self.contract_schema != CONTRACT_SCHEMA:
            raise ContractError(
                f"field 'contract_schema' has unsupported value"
                f" {self.contract_schema!r}"
            )
        for field in _GENERATION_DIGEST_FIELDS:
            _validate_digest(field, getattr(self, field), "generation")

    @classmethod
    def from_mapping(
        cls, raw: object, *, source: str = "generation"
    ) -> PlaneGeneration:
        if not isinstance(raw, dict):
            raise ContractError(f"{source}: the document must be an object")
        required = {
            "generation",
            "devman_runtime",
            *_GENERATION_DIGEST_FIELDS,
            "contract_schema",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise ContractError(f"{source}: missing field(s): {', '.join(missing)}")
        unknown = sorted(set(raw) - required)
        if unknown:
            raise ContractError(f"{source}: unknown field(s): {', '.join(unknown)}")
        generation = raw["generation"]
        schema = raw["contract_schema"]
        if isinstance(generation, bool) or not isinstance(generation, int):
            raise ContractError(f"{source}: field 'generation' must be an integer")
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise ContractError(f"{source}: field 'contract_schema' must be an integer")
        runtime = raw["devman_runtime"]
        if not isinstance(runtime, str):
            raise ContractError(f"{source}: field 'devman_runtime' must be a string")
        values = {
            field: _validate_digest(field, raw[field], source)
            for field in _GENERATION_DIGEST_FIELDS
        }
        return cls(generation, runtime, **values, contract_schema=schema)

    def to_mapping(self) -> dict[str, object]:
        return {
            "generation": self.generation,
            "devman_runtime": self.devman_runtime,
            "renderer_digest": self.renderer_digest,
            "policy_digest": self.policy_digest,
            "dagu_digest": self.dagu_digest,
            "toolchain_digest": self.toolchain_digest,
            "contract_schema": self.contract_schema,
        }

    @property
    def digest(self) -> str:
        return digest_mapping(self.to_mapping())


@dataclass(frozen=True, slots=True)
class ProjectionRecord:
    """The inputs that produced one project's generated projection."""

    project: str
    manifest_digest: str
    policy_digest: str
    plane_generation: int
    renderer_digest: str
    source_digest: str
    overlay_digest: str | None = None
    contract_schema: int = CONTRACT_SCHEMA

    def __post_init__(self) -> None:
        fault = identity_fault("project", self.project)
        if fault:
            raise ContractError(f"field 'project' is invalid: {fault}")
        if self.plane_generation < 0:
            raise ContractError("field 'plane_generation' must be zero or greater")
        if self.contract_schema != CONTRACT_SCHEMA:
            raise ContractError(
                f"field 'contract_schema' has unsupported value"
                f" {self.contract_schema!r}"
            )
        for field in (
            "manifest_digest",
            "policy_digest",
            "renderer_digest",
            "source_digest",
        ):
            _validate_digest(field, getattr(self, field), "projection")
        if self.overlay_digest is not None:
            _validate_digest("overlay_digest", self.overlay_digest, "projection")

    @classmethod
    def from_mapping(
        cls, raw: object, *, source: str = "projection"
    ) -> ProjectionRecord:
        if not isinstance(raw, dict):
            raise ContractError(f"{source}: the document must be an object")
        required = {
            "project",
            "manifest_digest",
            "policy_digest",
            "plane_generation",
            "renderer_digest",
            "source_digest",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise ContractError(f"{source}: missing field(s): {', '.join(missing)}")
        allowed = required | {"overlay_digest", "contract_schema"}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ContractError(f"{source}: unknown field(s): {', '.join(unknown)}")
        generation = raw["plane_generation"]
        if isinstance(generation, bool) or not isinstance(generation, int):
            raise ContractError(
                f"{source}: field 'plane_generation' must be an integer"
            )
        schema = raw.get("contract_schema", CONTRACT_SCHEMA)
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise ContractError(f"{source}: field 'contract_schema' must be an integer")
        return cls(
            project=_require_text(raw, "project", source),
            manifest_digest=_validate_digest(
                "manifest_digest", raw["manifest_digest"], source
            ),
            policy_digest=_validate_digest(
                "policy_digest", raw["policy_digest"], source
            ),
            plane_generation=generation,
            renderer_digest=_validate_digest(
                "renderer_digest", raw["renderer_digest"], source
            ),
            source_digest=_validate_digest(
                "source_digest", raw["source_digest"], source
            ),
            overlay_digest=(
                None
                if raw.get("overlay_digest") is None
                else _validate_digest("overlay_digest", raw["overlay_digest"], source)
            ),
            contract_schema=schema,
        )

    def to_mapping(self) -> dict[str, object]:
        value: dict[str, object] = {
            "project": self.project,
            "manifest_digest": self.manifest_digest,
            "policy_digest": self.policy_digest,
            "plane_generation": self.plane_generation,
            "renderer_digest": self.renderer_digest,
            "source_digest": self.source_digest,
            "contract_schema": self.contract_schema,
        }
        if self.overlay_digest is not None:
            value["overlay_digest"] = self.overlay_digest
        return value

    @property
    def digest(self) -> str:
        return digest_mapping(self.to_mapping())

    def matches(
        self,
        generation: PlaneGeneration,
        manifest: ProjectManifest,
        *,
        source_digest: str,
        overlay_digest: str | None = None,
    ) -> bool:
        """Return whether the record still describes the requested inputs."""

        return (
            self.project == manifest.project
            and self.manifest_digest == manifest.digest
            and self.policy_digest == generation.policy_digest
            and self.plane_generation == generation.generation
            and self.renderer_digest == generation.renderer_digest
            and self.source_digest == source_digest
            and self.overlay_digest == overlay_digest
        )
