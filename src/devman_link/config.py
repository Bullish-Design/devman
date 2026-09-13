"""The central link configuration: one Nix file, evaluated with one identity.

The one human-authored link declaration is
``$HOME/.config/devman/projects/<project>/devenv.local.nix``, holding one
``devman.link`` attribute set.  B does not change that interface.  The adapter
evaluates the file with the selected identity supplied as
``config.devman.project``, reads ``devman.link`` and nothing else, and refuses
every unsafe result by name.

Evaluating one module is not evaluating the repository environment.  The
adapter does not read a workflow, a generation, or the compatibility registry to
make a link.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from devman_contract import identity_fault

from .declarations import Declaration
from .errors import LinkConfigurationError, LinkError
from .paths import resolve


@dataclass(frozen=True, slots=True)
class LinkConfiguration:
    """The validated central configuration used by one link command."""

    project: str
    root: Path
    overlay: Path
    central_file: Path
    declarations: dict[str, dict[str, object]]


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


def _link_expression(path: Path, project: str) -> str:
    """Build the expression that reads one central file's ``devman.link``.

    **It supplies the arguments the module declares, and no others.** Passing a
    fixed ``{ config }`` refused four real central files, because they take
    ``lib`` to write ``lib.mkForce`` beside their link block — and Nix refuses a
    function called without a required argument before anything can read
    ``devman.link``. The refusal named the central file and said to fix the
    expression, so it sent a reader to repair a file that was correct.

    ``builtins.functionArgs`` is what the module system itself uses to decide
    what to pass. ``lib`` comes from the channel when one is reachable, and
    ``tryEval`` keeps an unreachable channel from becoming this error again: a
    file that declares ``lib`` and never uses it still evaluates.
    """

    return (
        "let\n"
        f"  file = import {_nix_quote(str(path))};\n"
        "  wanted = builtins.functionArgs file;\n"
        "  channel = builtins.tryEval (import <nixpkgs/lib>);\n"
        "  lib = if channel.success then channel.value else { };\n"
        f"  config = {{ devman = {{ project = {_nix_quote(project)}; }}; }};\n"
        "  supplied = { inherit config; }\n"
        "    // (if wanted ? lib then { inherit lib; } else { })\n"
        "    // (if wanted ? options then { options = { }; } else { })\n"
        "    // (if wanted ? pkgs then { pkgs = { }; } else { });\n"
        "in builtins.toJSON (file supplied).devman.link\n"
    )


def evaluate_central_file(path: Path, project: str) -> object:
    """Evaluate one central module and return its ``devman.link`` value."""

    executable = shutil.which("nix-instantiate")
    if executable is None:
        raise LinkConfigurationError(
            f"cannot evaluate central configuration {path}: nix-instantiate is not on PATH\n"
            "repair: enter a Nix environment that provides nix-instantiate"
        )
    expression = _link_expression(path, project)
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
    for view, raw in all_declarations.items():
        try:
            declaration = Declaration.read(view, raw)
            resolved = resolve(
                declaration,
                overlay=overlay_root,
                root=repository,
                project=project,
            )
        except LinkError as exc:
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
