"""Git's exclude file, projected from one central per-project file.

`.git/info/exclude` is machine-local by the boundary test: it is true for this
checkout on this machine, so it goes central and reaches the repository as a
symlink (AGENTS.md law 10). One central `projects/<project>/.local.gitignore`
owns it.

A linked worktree keeps `.git` as a FILE naming its git directory, and that
directory names the common one. Following both is what stops a worktree getting
its own second exclude file that nothing else reads.
"""

from __future__ import annotations

from pathlib import Path

from .errors import LinkError
from .paths import ResolvedLink, local_gitignore_key, local_gitignore_path
from .state import State, content_hash


def git_exclude_path(root: Path) -> Path | None:
    """Return the exclude file for a normal checkout or linked worktree.

    `None` means the repository has no Git marker at all — a gitman or jj
    workspace, which must not get a second exclude link.
    """
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


def exclusion_entries(links: list[ResolvedLink]) -> list[str]:
    """The run directory, plus every view whose canonical side is not the repo."""
    entries = [".devman/.runs/"]
    entries.extend(
        link.declaration.view
        for link in links
        if link.declaration.canonical in {"central", "external"}
    )
    return list(dict.fromkeys(entries))


def append_entries(path: Path, entries: list[str]) -> bool:
    """Append the missing entries only. This never rewrites an author's line."""
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


def ensure_local_gitignore(
    root: Path,
    overlay: Path,
    project: str,
    links: list[ResolvedLink],
    state: State,
    *,
    link_path,
) -> bool:
    """Project Git's exclude file from one central per-project file."""
    exclude = git_exclude_path(root)
    if exclude is None:
        return False

    canonical = local_gitignore_path(overlay.resolve(), project)
    key = local_gitignore_key(project)
    entries = exclusion_entries(links)
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
