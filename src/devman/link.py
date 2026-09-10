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
    return path


def resolve(
    declaration: Declaration, *, overlay: Path, root: Path, project: str
) -> ResolvedLink:
    """Resolve both sides without inferring identity from a directory name."""
    view = root.resolve() / declaration.view
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
            declaration, project, overlay.resolve(), root.resolve(), view, external
        )
    central = _expanded_path(
        overlay,
        declaration.path or default,
        project,
        f"path for {declaration.view!r}",
    )
    if declaration.canonical == "central":
        return ResolvedLink(
            declaration, project, overlay.resolve(), root.resolve(), view, central
        )
    return ResolvedLink(
        declaration,
        project,
        overlay.resolve(),
        root.resolve(),
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


def _record(link: ResolvedLink, state: dict[str, dict[str, str]]) -> None:
    state[link.key] = {
        "canonical": str(link.canonical_path),
        "hash": _content_hash(link.canonical_path),
    }


def _user_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


def inspect(link: ResolvedLink) -> LinkResult:
    view = link.view_path
    if view.is_symlink():
        target = view.resolve(strict=False)
        if target == link.canonical_path:
            return LinkResult(link, "ok")
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


def _create_canonical(link: ResolvedLink) -> None:
    path = link.canonical_path
    if link.declaration.canonical == "external":
        path.mkdir(parents=True, exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
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
    if "/" in link.declaration.view:
        path.mkdir(exist_ok=True)
    else:
        path.touch()


def _link(link: ResolvedLink, *, promoted: bool = False) -> None:
    link.view_path.parent.mkdir(parents=True, exist_ok=True)
    if link.view_path.is_symlink():
        link.view_path.unlink()
    elif link.view_path.exists():
        if not promoted:
            raise LinkError(f"refusing to replace real view {link.view_path}")
        backup = link.view_path.with_name(f"{link.view_path.name}.devman-promoted")
        if backup.exists() or backup.is_symlink():
            raise LinkError(
                f"refusing to replace {link.view_path}; promotion backup already"
                f" exists at {backup}"
            )
        os.replace(link.view_path, backup)
    link.view_path.symlink_to(link.canonical_path)


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
    changed = False
    for view, raw in declarations.items():
        link = resolve(
            Declaration.read(view, raw), overlay=overlay, root=root, project=project
        )
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
            _create_canonical(link)
            _link(link)
        else:
            _link(link)
        _record(link, state)
        changed = True
        results.append(result)
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
    if project is None:
        project = _project_from_nix(root)
    try:
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
    parser = argparse.ArgumentParser(prog="devman-link")
    parser.add_argument("--registry", default="~/.local/share/devman")
    sub = parser.add_subparsers(dest="link_command", required=True)
    add_arguments(sub.add_parser("reconcile"))
    status = sub.add_parser("status")
    add_arguments(status)
    status.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    from .registry import Registry

    return main(args, Registry(args.registry))


def _project_from_nix(root: Path) -> str:
    import re

    matches: list[str] = []
    for name in ("devenv.nix", "devenv.local.nix"):
        path = root / name
        if not path.is_file():
            continue
        matches.extend(
            re.findall(r"\bdevman\.project\s*=\s*\"([^\"]+)\"", path.read_text())
        )
    if len(set(matches)) != 1:
        raise LinkError(
            "cannot determine project identity; pass --project or state one"
            " devman.project in devenv.nix"
        )
    return matches[0]
