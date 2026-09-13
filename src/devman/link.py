"""The link plane — the compatibility import path.

The implementation moved to the independent `devman_link` component at 038
Stage 16, and the duplicate copy that lived here was removed at Stage 17. What
is left is a re-export, and it exists for exactly one caller: `devman.watch`,
which reconciles a project's links on the event path and must not grow a second
interpretation of canonical, view, or promotion state.

**Fold this into `devman.watch` and delete the module when that file is free to
edit.** It has unrelated worktree changes that Project 038 must not disturb, so
the import stayed rather than the implementation.

Every name here is the component's own. There is one reconciler.
"""

from __future__ import annotations

from devman_link import (
    STATES,
    Declaration,
    LinkError,
    LinkResult,
    ResolvedLink,
    inspect,
    reconcile,
    resolve,
    status,
)
from devman_link.state import STATE_FILE

__all__ = [
    "STATES",
    "STATE_FILE",
    "Declaration",
    "LinkError",
    "LinkResult",
    "ResolvedLink",
    "inspect",
    "reconcile",
    "resolve",
    "status",
]
