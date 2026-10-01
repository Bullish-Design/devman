"""Phase A of the M14 devman cutover: write `links.yaml` beside each central
`devenv.local.nix`, without touching the Nix file.

Converts every central project directory under the overlay root, not only
the 65 live ones (decision D-d: convert all of them, scope the gate and the
new flow to the 65 live projects). A directory with no `devenv.local.nix`
is not a central project and is skipped.

`canonical = "repo"` is refused loudly (decisions.md revision 16): it
inverts the two sides, which Linkman's first invariant forbids, and zero
live declarations use it. `.git/info/exclude` never enters `links.yaml`: it
stays devman's under D5.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

from devman_link.config import evaluate_central_file
from devman_link.declarations import Declaration
from devman_link.errors import LinkError

DEFAULT_OVERLAY = Path("~/.config/devman").expanduser()

# Revision 7 deleted `type:`; the trailing slash carries the kind. These are
# the nine view keys the M14 readiness review found live on this machine —
# an unrecognised view is refused rather than guessed (guide rule 8).
DIRECTORY_VIEWS = frozenset(
    {".agents", ".claude/skills", ".claude", ".loci", ".devman/workflows"}
)
FILE_VIEWS = frozenset({".envrc", "devenv.local.nix", ".claude/settings.local.json"})

BOOTSTRAP_VIEW = "devenv.local.nix"


class ConversionError(RuntimeError):
    """A declaration the converter refuses to guess about."""


def _segments_to_repo_name(path: str, project: str) -> str:
    """Replace a whole path segment equal to `project` with `${repo.name}`.

    A whole-segment match, never a substring match: a project literally
    named the same as some unrelated path component must not be rewritten
    by accident.
    """
    return "/".join(
        "${repo.name}" if segment == project else segment for segment in path.split("/")
    )


def _central_target(declaration: Declaration, overlay: Path, project: str) -> str:
    overlay = overlay.resolve()
    default = f"projects/{project}/repo/{declaration.view}"
    rendered = (declaration.path or default).replace("${project}", project)
    absolute = (overlay / rendered).resolve()
    try:
        tail = str(absolute.relative_to(overlay))
    except ValueError as exc:
        raise ConversionError(
            f"{project}:{declaration.view}: central path {absolute} escapes the"
            f" overlay {overlay}"
        ) from exc
    tail = _segments_to_repo_name(tail, project)
    return f"${{vars.central}}/{tail}"


def _external_target(declaration: Declaration, project: str) -> str:
    # `Declaration.read` already expands `~` for an external path (declarations.py).
    rendered = declaration.path.replace("${project}", project)
    if not rendered.startswith("/"):
        raise ConversionError(
            f"{project}:{declaration.view}: external path {rendered!r} is not"
            " absolute after expansion"
        )
    home = str(Path.home())
    rendered = _segments_to_repo_name(rendered, project)
    if rendered == home or rendered.startswith(home + "/"):
        return "${env.HOME}" + rendered[len(home) :]
    return rendered


def convert_declarations(
    raw_declarations: dict[str, object], *, overlay: Path, project: str
) -> dict[str, dict[str, str]]:
    """Turn one project's raw `devman.link` value into Linkman link entries."""
    links: dict[str, dict[str, str]] = {}
    for view, raw in raw_declarations.items():
        declaration = Declaration.read(view, raw)
        if declaration.canonical == "repo":
            raise ConversionError(
                f'{project}:{view} declares canonical="repo"; refused at cutover'
                " (decisions.md revision 16) — it inverts the two sides, which"
                " Linkman's first invariant forbids"
            )
        if view not in DIRECTORY_VIEWS and view not in FILE_VIEWS:
            raise ConversionError(
                f"{project}:{view}: unrecognised view; the converter refuses"
                " rather than guess its kind (guide rule 8)"
            )
        if declaration.canonical == "external":
            target = _external_target(declaration, project)
        else:
            target = _central_target(declaration, overlay, project)
        if view in DIRECTORY_VIEWS and not target.endswith("/"):
            target += "/"
        links[view] = {"target": target}

    if BOOTSTRAP_VIEW not in links:
        # `config.py:262-270` synthesizes this declaration for 72 of 77
        # projects today; the converter writes it explicitly for all of them.
        links[BOOTSTRAP_VIEW] = {
            "target": "${vars.central}/projects/${repo.name}/" + BOOTSTRAP_VIEW
        }
    return links


def build_links_yaml(links: dict[str, dict[str, str]]) -> dict[str, object]:
    return {
        "version": 1,
        "vars": {"central": "${env.HOME}/.config/devman"},
        "links": dict(sorted(links.items())),
    }


def central_projects(overlay: Path) -> list[tuple[str, Path]]:
    """Every central directory holding a `devenv.local.nix`, sorted by name."""
    projects_dir = overlay / "projects"
    found = []
    for entry in sorted(projects_dir.iterdir()):
        nix_file = entry / "devenv.local.nix"
        if entry.is_dir() and nix_file.is_file():
            found.append((entry.name, nix_file))
    return found


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert_all(overlay: Path = DEFAULT_OVERLAY, *, dry_run: bool = False) -> list[str]:
    """Convert every central project. Returns the project names converted.

    Checksums every `devenv.local.nix` before and after and raises if any of
    them moved — the converter reads the Nix file, and never writes it.
    """
    projects = central_projects(overlay)
    before = {nix_file: _checksum(nix_file) for _project, nix_file in projects}

    converted: list[str] = []
    for project, nix_file in projects:
        try:
            raw = evaluate_central_file(nix_file, project)
            links = convert_declarations(raw, overlay=overlay, project=project)
        except (LinkError, ConversionError) as exc:
            raise ConversionError(f"cannot convert {project}: {exc}") from exc
        document = build_links_yaml(links)
        if not dry_run:
            out = nix_file.with_name("links.yaml")
            out.write_text(yaml.safe_dump(document, sort_keys=False))
        converted.append(project)

    after = {nix_file: _checksum(nix_file) for _project, nix_file in projects}
    moved = [str(path) for path in before if before[path] != after.get(path)]
    if moved:
        raise ConversionError(
            "the converter changed a Nix file it must only read:\n"
            + "\n".join(f"  {path}" for path in moved)
        )
    return converted


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Write links.yaml beside every central devenv.local.nix."
    )
    ap.add_argument("--all", action="store_true", help="convert every central project")
    ap.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="run the converter and checksum check, write nothing",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.all:
        print("convert: pass --all", file=sys.stderr)
        return 1
    try:
        converted = convert_all(args.overlay, dry_run=args.dry_run)
    except ConversionError as exc:
        print(f"convert: {exc}", file=sys.stderr)
        return 1
    mode = "would write" if args.dry_run else "wrote"
    print(f"convert: {mode} links.yaml for {len(converted)} project(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
