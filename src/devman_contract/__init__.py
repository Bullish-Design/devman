"""The portable Devman contract, importable without the Devman CLI.

Two independent components read these records: the `devman` command and the
`devman_link` adapter (038 Stage 16). The package holds no Dagu, Nix, registry,
or repository-task dependency, so a component can take the identity grammar and
the manifest without taking the plane.

`devman.registry` and `devman.contract` re-export every name here, so the older
import paths keep working.
"""

from .identity import IDENTITY_GRAMMAR, IDENTITY_PATTERN, identity_fault
from .manifest import (
    CONTRACT_SCHEMA,
    MANIFEST_NAME,
    ContractError,
    PlaneGeneration,
    ProjectionRecord,
    ProjectManifest,
    digest_blobs,
    digest_bytes,
    digest_file,
    digest_mapping,
)

__all__ = [
    "CONTRACT_SCHEMA",
    "IDENTITY_GRAMMAR",
    "IDENTITY_PATTERN",
    "MANIFEST_NAME",
    "ContractError",
    "PlaneGeneration",
    "ProjectManifest",
    "ProjectionRecord",
    "digest_blobs",
    "digest_bytes",
    "digest_file",
    "digest_mapping",
    "identity_fault",
]
