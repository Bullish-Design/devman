"""The one identity grammar, shared by every component that names a project.

This module moved out of `src/devman/registry.py` at 038 Stage 16, unchanged,
so that `devman_link` can validate a name without importing the registry.
`devman.registry` re-exports all three names.
"""

from __future__ import annotations

import re

# THE IDENTITY GRAMMAR (009 P1-5). One definition, from the same measured Dagu
# character set as the DAG-name codec in `devman.registry`. The leading
# character is restricted so that `-flag` and `.hidden` cannot be names.
#
# It is duplicated at the Nix boundary in `modules/devenv.nix`, because §3.1
# says what the two interfaces share must be TEXT and a Python function is not
# text. `tests/fixtures/identity.json` is the shared table that proves the two
# copies agree; three readers assert against it.
IDENTITY_GRAMMAR = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
IDENTITY_PATTERN = re.compile(IDENTITY_GRAMMAR)


def identity_fault(kind: str, value: str) -> str | None:
    """Why this project or workflow name may not become an identity, or `None`.

    **The grammar, at both boundaries** (009 P1-5). Before this, `devman.project`
    was a bare `types.str` and the codec validated one condition — a dot in the
    workflow half. So `bad@project` registered, `run.resolve()` returned
    `bad@project.check`, and the pinned Dagu refused it. Worse characters reached
    path construction: `projects/$proj`, `dags/$proj.$workflow.yaml` and the
    sweep loops in `modules/devenv.nix`. A slash, an empty name, or `..` selects
    a registry subpath.

    The character set is measured rather than chosen: Dagu 2.15.0 allows
    alphanumerics, dashes, dots and underscores in a name and refuses everything
    else (S-11). The leading character is restricted further, so `-flag` and
    `.hidden` cannot be names.

    The named refusals below are already excluded by the pattern. They are
    refused **with their own message anyway**, because "does not match a regex"
    does not tell an author what to do.

    `tests/fixtures/identity.json` is the shared table. §3.1 says what the two
    interfaces share must be text, so the table is what keeps this function and
    `modules/devenv.nix`'s assertion in agreement.
    """
    where = f"a {kind} name"
    if value == "":
        return (
            f"{where} cannot be empty — it would select the registry directory itself"
        )
    if value in (".", ".."):
        return (
            f"'{value}' cannot be {where} — it selects a registry path rather"
            " than naming an entry in it"
        )
    if "/" in value or "\\" in value:
        return (
            f"'{value}' cannot be {where} — it holds a path separator, and the"
            " name becomes a registry directory and a DAG file name (§9.2)"
        )
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        return (
            f"{where} cannot hold a control character — every reader of the"
            " registry is line-oriented (§9.2)"
        )
    if not IDENTITY_PATTERN.match(value):
        return (
            f"'{value}' cannot be {where}\n"
            "  a name holds letters, digits, '.', '-' and '_', and starts with a"
            " letter or a digit\n"
            "  Dagu 2.15.0 refuses every other character in a DAG name (S-11),"
            " and the name becomes a path (§9.2)"
        )
    return None
