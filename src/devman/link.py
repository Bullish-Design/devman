"""Reconcile the link plane declared by a project.

The declaration names the view path.  A central link stores its canonical
content under the overlay and exposes it in the project.  A repository link
keeps its canonical content in the project and exposes it under
``projects/<project>/repo`` in the overlay.  An external link stores its
canonical content at an absolute path outside both roots.

The reconciler never removes a real view.  It promotes that content first and
records the canonical content hash after every successful link.  A later
promotion refuses when the canonical side changed since that record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .registry import identity_fault

STATE_FILE = ".devman-link-state.json"
STATES = ("ok", "repoint", "promote", "link", "create")


class LinkError(Exception):
    """A link-plane refusal that must be shown to the developer."""


@dataclass(frozen=True)
class Declaration:
    view: str
    canonical: str = "central"
    path: str = ""
    template: str | None = None

    @classmethod
    def read(cls, view: str, raw: object) -> Declaration:
        if not isinstance(raw, dict):
            raise LinkError(f"link {view!r} must be an attribute set")
        canonical = raw.get("canonical", "central")
        path = raw.get("path", "")
        template = raw.get("template")
        if canonical not in {"central", "repo", "external"}:
            raise LinkError(
                f"link {view!r} states canonical={canonical!r}; use central, repo, or external"
            )
        if not isinstance(path, str) or not isinstance(view, str):
            raise LinkError(f"link {view!r} has a non-string path")
        if template is not None and not isinstance(template, str):
            raise LinkError(f"link {view!r} has a non-string template")
        if template is not None and canonical != "central":
            raise LinkError(
                f"link {view!r} uses template={template!r}, but templates are"
                ' allowed only for canonical="central" links'
            )
        _relative(view, f"view {view!r}")
        if canonical == "external":
            path = os.path.expanduser(path)
        elif path:
            _relative(path, f"path for {view!r}")
        return cls(view, canonical, path, template)


@dataclass(frozen=True)
class ResolvedLink:
    declaration: Declaration
    project: str
    overlay: Path
    root: Path
    view_path: Path
    canonical_path: Path

    @property
    def key(self) -> str:
        return f"{self.project}:{self.declaration.view}"


@dataclass(frozen=True)
class LinkResult:
    link: ResolvedLink
    state: str
    detail: str = ""


def _relative(value: str, label: str) -> None:
    path = Path(value)
    if value in {"", "."}:
        raise LinkError(f"{label} must name a path")
    if path.is_absolute() or ".." in path.parts:
        raise LinkError(f"{label} must be relative and stay inside its root")


def _expanded_path(root: Path, value: str, project: str, label: str) -> Path:
    rendered = value.replace("${project}", project)
    _relative(rendered, label)
    root = root.resolve()
    path = (root / rendered).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise LinkError(f"{label} escapes {root}") from exc
    if path == root:
        raise LinkError(f"{label} must name a path below {root}")
    return path


def _view_path(root: Path, view: str) -> Path:
    """Resolve a view while refusing a symlinked parent outside the repo."""
    root = root.resolve()
    path = root / view
    parent = path.parent.resolve()
    try:
        parent.relative_to(root)
    except ValueError as exc:
        raise LinkError(f"view {view!r} escapes project repository {root}") from exc
    return path


def resolve(
    declaration: Declaration, *, overlay: Path, root: Path, project: str
) -> ResolvedLink:
    """Resolve both sides without inferring identity from a directory name."""
    root = root.resolve()
    overlay = overlay.resolve()
    view = _view_path(root, declaration.view)
    default = f"projects/{project}/repo/{declaration.view}"
    if declaration.canonical == "external":
        rendered = declaration.path.replace("${project}", project)
        rendered = os.path.expandvars(os.path.expanduser(rendered))
        candidate = Path(rendered)
        if not candidate.is_absolute():
            raise LinkError(
                f"path for {declaration.view!r} must be absolute after expansion"
            )
        external = candidate.resolve()
        for name, boundary in (("project repository", root), ("overlay", overlay)):
            boundary = boundary.resolve()
            if external == boundary or boundary in external.parents:
                raise LinkError(
                    f"external path for {declaration.view!r} resolves inside the"
                    f" {name}: {external}"
                )
        return ResolvedLink(
            declaration, project, overlay, root, view, external
        )
    central = _expanded_path(
        overlay,
        declaration.path or default,
        project,
        f"path for {declaration.view!r}",
    )
    if declaration.canonical == "central":
        return ResolvedLink(
            declaration, project, overlay, root, view, central
        )
    return ResolvedLink(
        declaration,
        project,
        overlay,
        root,
        central,
        view,
    )


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            rel = child.relative_to(path).as_posix().encode()
            digest.update(
                b"d\0" + rel + b"\0" if child.is_dir() else b"f\0" + rel + b"\0"
            )
            if child.is_symlink():
                digest.update(b"l\0" + os.readlink(child).encode() + b"\0")
            elif child.is_file():
                digest.update(child.read_bytes())
        return digest.hexdigest()
    if path.is_symlink():
        digest.update(b"l\0" + os.readlink(path).encode())
    else:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_state(overlay: Path) -> dict[str, dict[str, str]]:
    try:
        raw = json.loads((overlay / STATE_FILE).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_state(overlay: Path, state: dict[str, dict[str, str]]) -> None:
    overlay.mkdir(parents=True, exist_ok=True)
    temporary = overlay / f".{STATE_FILE}.new"
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, overlay / STATE_FILE)


def _git_exclude_path(root: Path) -> Path | None:
    """Return the exclude file for a normal checkout or linked worktree."""
    marker = root / ".git"
    if marker.is_dir():
        return marker / "info" / "exclude"
    if not marker.is_file():
        return None

    lines = marker.read_text().splitlines()
    if not lines or not lines[0].startswith("gitdir:"):
        raise LinkError(f"cannot read linked-worktree metadata from {marker}")
    git_dir = Path(lines[0].partition(":")[2].strip())
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    git_dir = git_dir.resolve()
    commondir = git_dir / "commondir"
    if commondir.is_file():
        common = Path(commondir.read_text().strip())
        if not common.is_absolute():
            common = git_dir / common
        git_dir = common.resolve()
    return git_dir / "info" / "exclude"


def _exclusion_entries(links: list[ResolvedLink]) -> list[str]:
    entries = [".devman/.runs/"]
    entries.extend(
        link.declaration.view
        for link in links
        if link.declaration.canonical in {"central", "external"}
    )
    return list(dict.fromkeys(entries))


def _append_exclusion_entries(path: Path, entries: list[str]) -> bool:
    try:
        contents = path.read_text()
    except FileNotFoundError:
        contents = ""
    current = contents.splitlines()
    additions = [entry for entry in entries if entry not in current]
    if not additions:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        if contents and not contents.endswith("\n"):
            stream.write("\n")
        for entry in additions:
            stream.write(f"{entry}\n")
    return True


def _local_gitignore_path(overlay: Path, project: str) -> Path:
    return _expanded_path(
        overlay,
        f"projects/{project}/.local.gitignore",
        project,
        f"local gitignore for {project!r}",
    )


def _local_gitignore_key(project: str) -> str:
    return f"{project}:.git/info/exclude"


def _link_path(
    view: Path,
    canonical: Path,
    *,
    promoted: bool = False,
    backup: bool = True,
) -> None:
    view.parent.mkdir(parents=True, exist_ok=True)
    if view.is_symlink():
        view.unlink()
    elif view.exists():
        if not promoted:
            raise LinkError(f"refusing to replace real view {view}")
        if backup:
            backup_path = view.with_name(f"{view.name}.devman-promoted")
            if backup_path.exists() or backup_path.is_symlink():
                raise LinkError(
                    f"refusing to replace {view}; promotion backup already"
                    f" exists at {backup_path}"
                )
            os.replace(view, backup_path)
        else:
            view.unlink()
    view.symlink_to(canonical)


def _ensure_local_gitignore(
    root: Path,
    overlay: Path,
    project: str,
    links: list[ResolvedLink],
    state: dict[str, dict[str, str]],
) -> bool:
    """Project Git's exclude file from one central per-project file."""
    exclude = _git_exclude_path(root)
    if exclude is None:
        return False

    canonical = _local_gitignore_path(overlay.resolve(), project)
    key = _local_gitignore_key(project)
    entries = _exclusion_entries(links)
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
        actual_hash = _content_hash(canonical)
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
        _link_path(exclude, canonical, promoted=True, backup=False)
        changed = True
    elif exclude.is_symlink():
        target = exclude.resolve(strict=False)
        if target != canonical:
            _link_path(exclude, canonical)
            changed = True
    else:
        _link_path(exclude, canonical)
        changed = True

    if _append_exclusion_entries(canonical, entries):
        changed = True
    record = {
        "canonical": str(canonical),
        "hash": _content_hash(canonical),
    }
    if state.get(key) != record:
        changed = True
    state[key] = record
    return changed


def _record(link: ResolvedLink, state: dict[str, dict[str, str]]) -> None:
    state[link.key] = {
        "canonical": str(link.canonical_path),
        "hash": _content_hash(link.canonical_path),
    }


def _record_available(
    links: list[ResolvedLink], state: dict[str, dict[str, str]]
) -> bool:
    """Record canonical paths that appeared while reconciling earlier views."""
    changed = False
    for link in links:
        if link.canonical_path.exists() and link.key not in state:
            _record(link, state)
            changed = True
    return changed


def _user_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


def inspect(link: ResolvedLink) -> LinkResult:
    view = link.view_path
    if view.is_symlink():
        target = view.resolve(strict=False)
        if target == link.canonical_path and link.canonical_path.exists():
            return LinkResult(link, "ok")
        if target == link.canonical_path:
            return LinkResult(link, "create", "canonical target is absent")
        return LinkResult(link, "repoint", f"points to {target}")
    if view.exists():
        return LinkResult(link, "promote")
    if link.canonical_path.exists():
        return LinkResult(link, "link")
    return LinkResult(link, "create")


def _copy_content(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if destination.exists() and not destination.is_dir():
            raise LinkError(
                f"cannot promote directory {source} into file {destination}"
            )
        shutil.copytree(source, destination, dirs_exist_ok=True)
        return
    if destination.exists() and destination.is_dir():
        raise LinkError(f"cannot promote file {source} into directory {destination}")
    temporary = destination.with_name(f".{destination.name}.promote")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def _create_canonical(link: ResolvedLink, *, as_directory: bool = False) -> None:
    path = link.canonical_path
    if link.declaration.canonical == "external":
        path.mkdir(parents=True, exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if link.declaration.view == "devenv.local.nix":
        path.write_text(
            "{ config, ... }:\n\n"
            "{\n"
            "  devman.link = {\n"
            '    ".envrc" = { canonical = "central"; path = "common/envrc"; };\n'
            '    ".loci" = { canonical = "external"; path = "~/Notes/1_Projects/${config.devman.project}"; };\n'
            '    ".agents" = { canonical = "central"; path = "projects/${config.devman.project}/agents"; };\n'
            '    ".claude/skills" = { canonical = "central"; path = "projects/${config.devman.project}/agents/skills"; };\n'
            "  };\n"
            "}\n"
        )
        return
    if link.declaration.template:
        copyroom = shutil.which("copyroom")
        if copyroom is None:
            raise LinkError(
                f"cannot render template {link.declaration.template!r} for {link.key};"
                " copyroom is not on PATH"
            )
        result = subprocess.run(
            [copyroom, "new", link.declaration.template, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise LinkError(
                f"copyroom could not render {link.declaration.template!r} for"
                f" {link.key}: {detail or f'exit {result.returncode}'}"
            )
        return
    if as_directory or "/" in link.declaration.view:
        path.mkdir(exist_ok=True)
    else:
        path.touch()


def _link(link: ResolvedLink, *, promoted: bool = False) -> None:
    _link_path(link.view_path, link.canonical_path, promoted=promoted)


def reconcile(
    declarations: dict[str, object],
    *,
    overlay: Path,
    root: Path,
    project: str,
) -> list[LinkResult]:
    """Apply declarations and return one result per view."""
    state = _read_state(overlay)
    results: list[LinkResult] = []
    all_links = [
        resolve(
            Declaration.read(view, raw), overlay=overlay, root=root, project=project
        )
        for view, raw in declarations.items()
    ]
    canonical_paths = [link.canonical_path for link in all_links]
    directory_paths = {
        candidate
        for candidate in canonical_paths
        for other in canonical_paths
        if other != candidate and candidate in other.parents
    }
    resolved_links = all_links
    changed = False
    for link in all_links:
        result = inspect(link)
        if result.state == "ok":
            if link.canonical_path.exists() and link.key not in state:
                _record(link, state)
                changed = True
            results.append(result)
            continue
        if result.state == "promote":
            if link.canonical_path.exists():
                previous = state.get(link.key, {})
                expected = previous.get("hash")
                actual = _content_hash(link.canonical_path)
                if not expected or expected != actual:
                    raise LinkError(
                        f"refusing promotion for {link.key}: canonical changed"
                        " since the link was made; review both sides"
                    )
            _copy_content(link.view_path, link.canonical_path)
            _link(link, promoted=True)
        elif result.state == "create":
            _create_canonical(link, as_directory=link.canonical_path in directory_paths)
            _link(link)
        else:
            if not link.canonical_path.exists():
                _create_canonical(
                    link, as_directory=link.canonical_path in directory_paths
                )
            _link(link)
        _record(link, state)
        changed = True
        if _record_available(all_links, state):
            changed = True
        results.append(result)
    if _ensure_local_gitignore(
        root.resolve(), overlay, project, resolved_links, state
    ):
        changed = True
    if changed:
        _write_state(overlay, state)
    return results


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", help="project identity; default from devenv.nix")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--overlay", help="config repository root")


def main(args, reg) -> int:
    if getattr(args, "link_command", "") == "status" and getattr(args, "all", False):
        rc = 0
        for project in sorted(reg.projects()):
            args.project = project
            args.root = "."
            rc = max(rc, _main_one(args, reg))
        return rc
    return _main_one(args, reg)


def _main_one(args, reg) -> int:
    project = args.project
    root = Path(args.root).resolve()
    try:
        if project is None:
            project = _project_from_nix(root)
        registered = reg.project(project)
        if args.root == ".":
            root = registered.path.resolve()
        raw = getattr(registered, "links", None) or {}
        overlay = _user_path(
            args.overlay or getattr(registered, "overlay", "~/.config/devman")
        )
        resolved = [
            resolve(
                Declaration.read(view, value),
                overlay=overlay,
                root=root,
                project=project,
            )
            for view, value in raw.items()
        ]
        results = (
            [inspect(item) for item in resolved]
            if args.link_command == "status"
            else reconcile(raw, overlay=overlay, root=root, project=project)
        )
    except LinkError as exc:
        print(f"devman: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"devman: link reconciliation failed: {exc}", file=sys.stderr)
        return 2
    for result in results:
        print(f"{result.state:7} {result.link.key}  {result.link.view_path}")
    return (
        1
        if args.link_command == "status"
        and any(result.state != "ok" for result in results)
        else 0
    )


def cli(argv: list[str] | None = None) -> int:
    from .registry import DEFAULT_REGISTRY, DEFAULT_STATE, Registry

    parser = argparse.ArgumentParser(prog="devman-link")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    # Only `reg.project()`/`reg.projects()` are read here — metadata.json, so
    # the state root, not the registry root (§11 Stage 3).
    parser.add_argument("--state", default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest="link_command", required=True)
    add_arguments(sub.add_parser("reconcile"))
    status = sub.add_parser("status")
    add_arguments(status)
    status.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    return main(args, Registry(args.registry, args.state))


def _project_from_nix(root: Path) -> str:
    """Read an explicit literal identity or a literal-bound Nix variable.

    This intentionally supports only the small identity grammar the module
    exposes. It never derives an identity from the repository directory name.
    """
    import re

    def strip_comments(text: str) -> str:
        return re.sub(r"(?m)#.*$", "", text)

    def attrset_body(text: str, start: int) -> str:
        depth = 0
        quoted = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start + 1 : index]
        return ""

    candidates: list[str] = []
    for name in ("devenv.nix", "devenv.local.nix"):
        path = root / name
        if not path.is_file():
            continue
        text = strip_comments(path.read_text())
        bindings = dict(
            re.findall(
                r"(?m)^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*\"([^\"]*)\"\s*;",
                text,
            )
        )
        candidates.extend(
            re.findall(r"\bdevman\s*\.\s*project\s*=\s*\"([^\"]+)\"", text)
        )
        for match in re.finditer(r"\bdevman\s*=\s*\{", text):
            body = attrset_body(text, match.end() - 1)
            for value, variable in re.findall(
                r"(?m)^\s*project\s*=\s*(?:\"([^\"]+)\"|([A-Za-z_][A-Za-z0-9_-]*))\s*;",
                body,
            ):
                candidates.append(value or bindings.get(variable, ""))

    matches = sorted({candidate for candidate in candidates if candidate})
    if not matches:
        raise LinkError(
            "cannot determine project identity from explicit devman.project;"
            " pass --project, or state one literal identity or a variable assigned"
            " a literal string in devenv.nix"
        )
    if len(matches) != 1:
        raise LinkError(
            "ambiguous project identity: found "
            + ", ".join(repr(match) for match in matches)
            + "; pass --project or leave exactly one explicit devman.project"
        )
    fault = identity_fault("project", matches[0])
    if fault:
        raise LinkError(f"invalid explicit project identity {matches[0]!r}: {fault}")
    return matches[0]
