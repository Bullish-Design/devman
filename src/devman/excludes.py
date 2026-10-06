"""Git's exclude file, projected straight from `links.yaml`.

Lane 4 of the Linkman cutover (project 044). `linking.py` still drives
Linkman for symlink topology, but the exclude projection reads a project's
`links.yaml` layers itself, here, with no dependency on the `linkman`
package. `devman_link.excludes` keeps the write side: `append_entries`,
`git_exclude_path`, and the promotion rules this module reuses unchanged.

`exclude_entries` reimplements Linkman's declaration contract: layer
reading, link-name validation, variable and token interpolation, and the
external/internal target-scope rule. Linkman revision
`a48d65a582968a022ecf0e9b54c4db1238173eee` is the reference. This module
matches its behaviour, not its code — it never imports `linkman`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path

import yaml

from devman_link.errors import LinkError
from devman_link.excludes import append_entries, git_exclude_path
from devman_link.paths import local_gitignore_key, local_gitignore_path
from devman_link.reconcile import link_path
from devman_link.state import State, content_hash

# devman's own entry. It never appears as a link name (OPEN-QUESTIONS.md O3a).
RUN_DIRECTORY = ".devman/.runs/"

_TOKEN_RE = re.compile(r"\$\{(?P<ns>repo|env|vars)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")
_MAX_DEPTH = 50


class ExcludeError(RuntimeError):
    """A refusal from the links.yaml exclude projection."""


def _check_link_name(name: object, path: Path) -> None:
    """Refuse a link name Linkman could not use either.

    Mirrors `linkman.models.config.LinkmanConfig.link_paths_are_usable`.
    """
    if not isinstance(name, str):
        raise ExcludeError(f"link name {name!r} in {path} must be a string")
    if not name or name in {".", ".."}:
        raise ExcludeError(
            f"link name {name!r} in {path} must be non-empty and not '.' or '..'"
        )
    if Path(name).is_absolute():
        raise ExcludeError(f"link name {name!r} in {path} must be relative")
    if name.startswith("~"):
        raise ExcludeError(f"link name {name!r} in {path} must not start with '~'")
    if ".." in Path(name).parts:
        raise ExcludeError(
            f"link name {name!r} in {path} must not contain '..' components"
        )
    if "\0" in name:
        raise ExcludeError(f"link name {name!r} in {path} must not contain a NUL byte")
    if name == "links.yaml":
        raise ExcludeError(f"link name 'links.yaml' is not allowed in {path}")


def _read_layer(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Read one declaration layer. Return its vars and its link targets.

    Mirrors `linkman.config._read_layer`. Raises `ExcludeError` for a
    malformed file. Lets `PermissionError` and other `OSError` propagate
    unwrapped, as Linkman does.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ExcludeError(f"declaration file not found: {path}") from exc
    except IsADirectoryError as exc:
        raise ExcludeError(f"cannot read declaration file {path}: {exc}") from exc
    except UnicodeError as exc:
        raise ExcludeError(
            f"declaration file is not valid UTF-8: {path}: {exc}"
        ) from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ExcludeError(f"invalid YAML in {path}: {exc}") from exc

    if data is None:
        return {}, {}
    if not isinstance(data, dict):
        raise ExcludeError(f"declaration in {path} must be a mapping")

    for key in data:
        if key not in {"version", "vars", "links"}:
            raise ExcludeError(f"unknown key {key!r} in {path}")

    version = data.get("version", 1)
    if isinstance(version, bool):
        raise ExcludeError(f"version in {path} must be the integer 1, not a boolean")
    if version != 1:
        raise ExcludeError(f"version in {path} must be the integer 1")

    # A bare `vars:` or `links:` line parses as None. Treat that as empty.
    raw_vars = data.get("vars")
    if raw_vars is None:
        raw_vars = {}
    if not isinstance(raw_vars, dict):
        raise ExcludeError(f"vars in {path} must be a mapping")
    variables: dict[str, str] = {}
    for name, value in raw_vars.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ExcludeError(f"vars in {path} must map strings to strings")
        variables[name] = value

    raw_links = data.get("links")
    if raw_links is None:
        raw_links = {}
    if not isinstance(raw_links, dict):
        raise ExcludeError(f"links in {path} must be a mapping")
    links: dict[str, str] = {}
    for name, link in raw_links.items():
        _check_link_name(name, path)
        if not isinstance(link, dict):
            raise ExcludeError(f"link {name!r} in {path} must be a mapping")
        unknown = [key for key in link if key != "target"]
        if unknown:
            raise ExcludeError(
                f"unknown key {unknown[0]!r} for link {name!r} in {path}"
            )
        if "target" not in link:
            raise ExcludeError(f"link {name!r} in {path} has no target")
        target = link["target"]
        if not isinstance(target, str):
            raise ExcludeError(f"target for link {name!r} in {path} must be a string")
        if not target.strip():
            raise ExcludeError(f"target for link {name!r} in {path} must be non-empty")
        if "\0" in target:
            raise ExcludeError(
                f"target for link {name!r} in {path} must not contain a NUL byte"
            )
        links[name] = target

    return variables, links


def _token_value(expression: str, resolve: Callable[[str, str], str]) -> str:
    token = "${" + expression + "}"
    match = _TOKEN_RE.fullmatch(token)
    if match is None:
        namespace, separator, _name = expression.partition(".")
        if separator and namespace not in {"repo", "env", "vars"}:
            raise ExcludeError(f"unknown namespace {namespace!r} in token {token!r}")
        raise ExcludeError(f"invalid interpolation token {token!r}")
    namespace = match.group("ns")
    name = match.group("name")
    value = resolve(namespace, name)
    if "\0" in value:
        raise ExcludeError(f"interpolation name {namespace}.{name} produced a NUL byte")
    return value


def _interpolate(template: str, resolve: Callable[[str, str], str]) -> str:
    """Scan `template` for `${ns.name}` tokens. Resolve each with `resolve`.

    Mirrors `linkman.resolve._interpolate`. There is no escape syntax for a
    literal `$`; every other character copies through unchanged.
    """
    pieces: list[str] = []
    index = 0
    while index < len(template):
        if template.startswith("${", index):
            end = template.find("}", index + 2)
            if end < 0:
                expression = template[index + 2 :]
                raise ExcludeError(f"unclosed interpolation token for {expression!r}")
            expression = template[index + 2 : end]
            pieces.append(_token_value(expression, resolve))
            index = end + 1
            continue
        pieces.append(template[index])
        index += 1
    result = "".join(pieces)
    if "\0" in result:
        raise ExcludeError("interpolated value contains a NUL byte")
    return result


def _resolve_repo_name(name: str, *, root: Path, project: str) -> str:
    builtins = {"root": str(root), "name": project, "parent": str(root.parent)}
    try:
        return builtins[name]
    except KeyError as exc:
        raise ExcludeError(f"unknown repository name {name!r}") from exc


def _resolve_vars(
    variables: Mapping[str, str],
    *,
    root: Path,
    project: str,
    environ: Mapping[str, str] | None,
) -> dict[str, str]:
    """Resolve every declared variable eagerly, memoised, depth-first.

    Mirrors `linkman.resolve.resolve_vars`. Resolves a name no link
    references too, because a later run might add one.
    """
    environment = os.environ if environ is None else environ
    resolved: dict[str, str] = {}
    visiting: list[str] = []

    def resolve_var(name: str) -> str:
        if name in resolved:
            return resolved[name]
        if name not in variables:
            raise ExcludeError(f"unknown variable {name!r}")
        if name in visiting:
            start = visiting.index(name)
            cycle = " -> ".join([*visiting[start:], name])
            raise ExcludeError(f"variable cycle: {cycle}")
        if len(visiting) >= _MAX_DEPTH:
            raise ExcludeError(
                f"variable resolution depth exceeds {_MAX_DEPTH} at {name!r}"
            )

        visiting.append(name)
        try:
            value = _interpolate(variables[name], resolve_name)
            if "\0" in value:
                raise ExcludeError(f"variable {name!r} resolved to a NUL byte")
            resolved[name] = value
            return value
        except ExcludeError as exc:
            raise ExcludeError(f"{exc} while resolving variable {name!r}") from exc
        finally:
            visiting.pop()

    def resolve_name(namespace: str, name: str) -> str:
        if namespace == "repo":
            return _resolve_repo_name(name, root=root, project=project)
        if namespace == "env":
            if name not in environment:
                raise ExcludeError(f"environment variable {name!r} is not set")
            return environment[name]
        if namespace == "vars":
            return resolve_var(name)
        raise ExcludeError(f"unknown namespace {namespace!r} for name {name!r}")

    for name in variables:
        resolve_var(name)
    return resolved


def _interpolate_resolved(
    template: str,
    *,
    root: Path,
    project: str,
    resolved_vars: Mapping[str, str],
    environ: Mapping[str, str] | None,
) -> str:
    """Resolve one string against variables that are already resolved.

    Mirrors `linkman.resolve.interpolate_resolved`. The `vars` lookup here
    is a flat dict read, not a recursive one — every variable was already
    resolved by `_resolve_vars`.
    """
    environment = os.environ if environ is None else environ

    def resolve_name(namespace: str, name: str) -> str:
        if namespace == "repo":
            return _resolve_repo_name(name, root=root, project=project)
        if namespace == "env":
            if name not in environment:
                raise ExcludeError(f"environment variable {name!r} is not set")
            return environment[name]
        if namespace == "vars":
            try:
                return resolved_vars[name]
            except KeyError as exc:
                raise ExcludeError(f"unknown variable {name!r}") from exc
        raise ExcludeError(f"unknown namespace {namespace!r} for name {name!r}")

    return _interpolate(template, resolve_name)


def _resolve_target(
    name: str,
    target: str,
    *,
    root: Path,
    project: str,
    resolved_vars: Mapping[str, str],
    environ: Mapping[str, str] | None,
    source: Path,
) -> Path:
    """Resolve one link's target to an absolute path.

    Mirrors `linkman.topology.build_desired_state`'s per-link resolution.
    """
    try:
        rendered = _interpolate_resolved(
            target,
            root=root,
            project=project,
            resolved_vars=resolved_vars,
            environ=environ,
        ).strip()
    except ExcludeError as exc:
        raise ExcludeError(f"{exc}; link {name!r} is declared in {source}") from exc

    if not rendered:
        raise ExcludeError(f"target for link {name!r} is empty in {source}")
    if "\0" in rendered:
        raise ExcludeError(f"target for link {name!r} contains a NUL byte in {source}")

    target_path = Path(rendered).expanduser()
    if not target_path.is_absolute():
        target_path = root / target_path
    target_abs = target_path.resolve(strict=False)

    # Only the parent is resolved here. The final component is usually the
    # managed symlink itself; resolving it would follow the link out of the
    # repository before this check can catch the escape.
    raw_link = root / name
    link_abs = raw_link.parent.resolve(strict=False) / raw_link.name
    if link_abs == root or not link_abs.is_relative_to(root):
        raise ExcludeError(
            f"link path {name!r} resolves outside the repository root {root};"
            f" source: {source}"
        )
    return target_abs


def exclude_entries(
    root: Path,
    overlay: Path,
    project: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    """The exclude entries this project owns, derived from links.yaml."""
    root = Path(root).expanduser().resolve(strict=False)
    overlay_root = Path(overlay).expanduser().resolve(strict=False)
    repo_layer = root / "links.yaml"
    overlay_layer = overlay_root / "projects" / project / "links.yaml"

    variables: dict[str, str] = {}
    links: dict[str, str] = {}
    var_sources: dict[str, Path] = {}
    link_sources: dict[str, Path] = {}

    for layer_path in (repo_layer, overlay_layer):
        if not os.path.lexists(layer_path):
            continue
        layer_vars, layer_links = _read_layer(layer_path)

        # Linkman has no cross-namespace rule: a link name and a variable
        # name may be the same string with no conflict. They live in
        # separate mappings. These two per-namespace checks are the only
        # duplicate rules — do not add a cross-namespace check.
        for name, value in layer_vars.items():
            previous = var_sources.get(name)
            if previous is not None:
                raise ExcludeError(
                    f"variable {name!r} is declared in both {previous} and {layer_path}"
                )
            variables[name] = value
            var_sources[name] = layer_path

        for name, target in layer_links.items():
            previous = link_sources.get(name)
            if previous is not None:
                raise ExcludeError(
                    f"link path {name!r} is declared in both {previous} and"
                    f" {layer_path}"
                )
            links[name] = target
            link_sources[name] = layer_path

    # Name the declaring files. A variable error carries no link name, so
    # without this the reader cannot tell which layer to open.
    try:
        resolved_vars = _resolve_vars(
            variables, root=root, project=project, environ=environ
        )
    except ExcludeError as exc:
        sources = ", ".join(str(path) for path in sorted(set(var_sources.values())))
        if not sources:
            raise
        raise ExcludeError(f"{exc}; variables are declared in {sources}") from exc

    entries = [RUN_DIRECTORY]
    for name, target in links.items():
        source = link_sources[name]
        target_abs = _resolve_target(
            name,
            target,
            root=root,
            project=project,
            resolved_vars=resolved_vars,
            environ=environ,
            source=source,
        )
        internal = target_abs != root and target_abs.is_relative_to(root)
        if not internal:
            entries.append(name)
    return list(dict.fromkeys(entries))


def ensure_git_exclude(
    root: Path,
    overlay: Path,
    project: str,
    state: State,
    *,
    link_path: Callable[..., None] = link_path,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Project Git's exclude file from one central per-project file."""
    exclude = git_exclude_path(root)
    if exclude is None:
        return False

    canonical = local_gitignore_path(overlay.resolve(), project)
    key = local_gitignore_key(project)
    entries = exclude_entries(root, overlay, project, environ=environ)
    changed = False

    if not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        if exclude.exists() and not exclude.is_symlink():
            canonical.write_text(exclude.read_text())
        else:
            canonical.touch()
        changed = True

    previous = state.get(key, {})
    expected_hash = previous.get("hash")
    if exclude.exists() and not exclude.is_symlink():
        actual_hash = content_hash(canonical)
        if expected_hash and expected_hash != actual_hash:
            raise LinkError(
                "refusing promotion for "
                f"{project}:.git/info/exclude: central .local.gitignore and"
                " the repository exclude file both changed; review both sides"
            )
        if not expected_hash and exclude.read_text() != canonical.read_text():
            raise LinkError(
                "refusing promotion for "
                f"{project}:.git/info/exclude: central .local.gitignore and"
                " the repository exclude file differ without a recorded baseline"
            )
        if expected_hash and exclude.read_text() != canonical.read_text():
            canonical.write_text(exclude.read_text())
            changed = True
        link_path(exclude, canonical, promoted=True, backup=False)
        changed = True
    elif exclude.is_symlink():
        target = exclude.resolve(strict=False)
        if target != canonical:
            link_path(exclude, canonical)
            changed = True
    else:
        link_path(exclude, canonical)
        changed = True

    if append_entries(canonical, entries):
        changed = True
    record = {"canonical": str(canonical), "hash": content_hash(canonical)}
    if state.get(key) != record:
        changed = True
    state[key] = record
    return changed
