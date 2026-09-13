"""The machine-local link adapter, as an independent component (038 Stage 16).

It makes the files a repository needs reach it from where they belong. The
boundary test decides where each one lives: a file that would still be true for
another clone stays in the repository, and a file that is true for this user or
this machine goes central and reaches the repository as a symlink (AGENTS.md
law 10, and 025 §P0).

The one human-authored declaration is the central Nix file,
``$HOME/.config/devman/projects/<project>/devenv.local.nix``, holding one
``devman.link`` attribute set. That interface does not change.

The component depends on ``devman_contract`` and the standard library. It reads
no compatibility registry, no active workflow generation, no workflow file, and
no Dagu run. ``nix/link-adapter.nix`` builds it from those two packages alone,
so an import of ``devman`` fails that build rather than passing unnoticed.
"""

from .api import DEFAULT_OVERLAY, OPERATIONS, LinkOutcome, format_results, run
from .config import (
    LinkConfiguration,
    central_link_file,
    evaluate_central_file,
    validate_link_configuration,
)
from .declarations import CANONICAL_KINDS, Declaration
from .errors import (
    IdentityError,
    LinkAdapterError,
    LinkConfigurationError,
    LinkError,
)
from .identity import ProjectIdentity, resolve_project_identity
from .paths import ResolvedLink, resolve
from .reconcile import STATES, LinkResult, inspect, reconcile, status
from .state import STATE_FILE

__all__ = [
    "CANONICAL_KINDS",
    "DEFAULT_OVERLAY",
    "OPERATIONS",
    "STATES",
    "STATE_FILE",
    "Declaration",
    "IdentityError",
    "LinkAdapterError",
    "LinkConfiguration",
    "LinkConfigurationError",
    "LinkError",
    "LinkOutcome",
    "LinkResult",
    "ProjectIdentity",
    "ResolvedLink",
    "central_link_file",
    "evaluate_central_file",
    "format_results",
    "inspect",
    "reconcile",
    "resolve",
    "resolve_project_identity",
    "run",
    "status",
    "validate_link_configuration",
]
