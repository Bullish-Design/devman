"""Portable Devman contract records — the compatibility import path.

The records moved to the standalone `devman_contract` package at 038 Stage 16,
so that the independent `devman_link` adapter can read a manifest without
importing the Devman CLI. Nothing changed but the import path, and this module
keeps the old one working for every caller inside and outside this repository.
"""

from __future__ import annotations

from devman_contract.manifest import (
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
    "MANIFEST_NAME",
    "ContractError",
    "PlaneGeneration",
    "ProjectManifest",
    "ProjectionRecord",
    "digest_blobs",
    "digest_bytes",
    "digest_file",
    "digest_mapping",
]
