"""Repository identity and central link configuration — the old import path.

The implementation moved to the independent `devman_link` component at 038
Stage 16. Nothing about the behaviour changed: the manifest stays authoritative,
the central Nix file stays the one human-authored link declaration, and the
identity precedence stays explicit `--project`, then `.devman/project.toml`,
then the old literal `devman.project`, then a loud refusal.

This module keeps the old names importable, so `devman.identity` still means
what `tests/unit/test_identity.py` and the public `devman link` command expect.
"""

from __future__ import annotations

from devman_link import (
    IdentityError,
    LinkConfiguration,
    LinkConfigurationError,
    ProjectIdentity,
    central_link_file,
    evaluate_central_file,
    resolve_project_identity,
    validate_link_configuration,
)

__all__ = [
    "IdentityError",
    "LinkConfiguration",
    "LinkConfigurationError",
    "ProjectIdentity",
    "central_link_file",
    "evaluate_central_file",
    "resolve_project_identity",
    "validate_link_configuration",
]
