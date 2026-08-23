"""Reading devman's registry (CONCEPT.md §9.2).

The registry is derived and the repository is canonical (§9.3), so everything
here reads and nothing here writes. The one exception is `Registry.unproject`,
which `doctor --prune` calls, and §10 makes that safe for the same reason: a
pruned entry restores itself the next time that repository's shell is entered.

    ~/.local/share/devman/
    ├── projects/<project>/metadata.json               # identity and path
    │   └── workflows/<workflow>.yaml   -> the winner of §7.3's resolution
    └── dags/<project>-<workflow>.yaml  -> the line above

`dags/` is Dagu's flat view; `projects/` is devman's. A DAG is keyed by its
file's base name, so the flat name `<project>-<workflow>` is what `dagu ls`, the
scheduler and `dagu enqueue` all agree on (`STAGE_1_LOG.md`, S1).

**Nothing here walks the disk looking for repositories.** §15.1 forbids it.
Reading devman's own registry is not scanning.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# CONCEPT.md §9.2 and §16: the registry root is `~/.local/share/devman`, and
# nothing else claims it (D1). The NixOS module exposes it as an option, and
# wraps this CLI with `--registry` when a machine moves it.
DEFAULT_REGISTRY = "~/.local/share/devman"

# The plane's Dagu home. Deliberately NOT the ambient `DAGU_HOME`: an unset one
# makes `dagu` build a fresh home and seed five example DAGs, and a wrong one
# sends a trigger to a Dagu that has never heard of the registry (S2). The
# module wraps this CLI with `--dagu-home` when a machine moves it.
DEFAULT_DAGU_HOME = "~/.local/share/dagu"


class RegistryError(Exception):
    """A refusal the developer must see. The CLI prints it and exits 1."""


@dataclass
class Project:
    """One `projects/<project>/metadata.json`, as written by the devenv module."""

    name: str
    path: Path
    groups: list[str] = field(default_factory=list)
    local: list[str] = field(default_factory=list)
    # `<workflow> -> {"group": …, "shadows": […], "source": "/nix/store/…"}`.
    # Schema 2 records the OUTCOME of §7.3's resolution, which is what `doctor`
    # check 4 diffs against and what §12.4's measurement reads (S1, stage 2).
    workflows: dict[str, dict] = field(default_factory=dict)
    # Schema 3 adds `triggers`: which glob fires which workflow, resolved from
    # the groups this project takes (§8). `{"group": …, "map": {glob: workflow}}`,
    # or absent when no group the project takes declares any.
    triggers: dict | None = None
    plan: str = ""
    schema: int = 0
    entry: Path | None = None

    def raw_triggers(self) -> dict | None:
        return self.triggers

    @property
    def exists(self) -> bool:
        """§10 check 5: an entry whose `path` is not a directory is stale."""
        return self.path.is_dir()

    @property
    def runs_dir(self) -> Path:
        return self.path / ".devman" / ".runs"

    def workflow_names(self) -> list[str]:
        """Every workflow this project projects, group-inherited and local."""
        return sorted({*self.workflows, *self.local})


class Registry:
    def __init__(self, root: str | os.PathLike[str] = DEFAULT_REGISTRY) -> None:
        self.root = Path(os.path.expanduser(str(root)))

    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    @property
    def dags_dir(self) -> Path:
        return self.root / "dags"

    def projects(self) -> dict[str, Project]:
        out: dict[str, Project] = {}
        if not self.projects_dir.is_dir():
            return out
        for entry in sorted(self.projects_dir.iterdir()):
            meta = entry / "metadata.json"
            if not meta.is_file():
                continue
            try:
                raw = json.loads(meta.read_text())
            except (OSError, json.JSONDecodeError):
                # A half-written entry is retried on the next shell entry: the
                # projection writes `metadata.json` last, precisely so that an
                # interrupted run leaves an entry that does not match (§9.3).
                continue
            out[entry.name] = Project(
                name=raw.get("project", entry.name),
                path=Path(raw.get("path", "")),
                groups=raw.get("groups", []),
                local=raw.get("local", []),
                workflows=raw.get("workflows", {}),
                triggers=raw.get("triggers"),
                plan=raw.get("plan", ""),
                schema=raw.get("schema", 0),
                entry=entry,
            )
        return out

    def project(self, name: str) -> Project:
        projects = self.projects()
        if name not in projects:
            known = ", ".join(sorted(projects)) or "(the registry is empty)"
            raise RegistryError(
                f"no project named '{name}' in {self.root}\n"
                f"  registered: {known}\n"
                f"  a repository joins by entering its shell once (§5.2)"
            )
        return projects[name]

    def project_for(self, cwd: os.PathLike[str] | str) -> Project:
        """The registered project this directory sits in.

        The deepest match wins, so a repository checked out inside another one
        resolves to itself. Identity is stated rather than inferred from the
        directory name (§9.1); this infers nothing — it compares against paths
        the repositories recorded themselves.
        """
        here = Path(cwd).resolve()
        best: Project | None = None
        for proj in self.projects().values():
            try:
                root = proj.path.resolve()
            except OSError:
                continue
            inside = here == root or root in here.parents
            deeper = best is None or len(str(root)) > len(str(best.path.resolve()))
            if inside and deeper:
                best = proj
        if best is None:
            raise RegistryError(
                f"{here} is not inside a registered repository\n"
                "  enter its devenv shell once to register it (§5.2), or name a\n"
                "  project with --project"
            )
        # A SECOND CHECKOUT INSIDE A REGISTERED ONE IS NOT A SUBDIRECTORY OF IT.
        #
        # `git worktree add .worktrees/feature` puts a whole other working tree
        # under a registered path. Entering its shell is refused, because §9.1
        # refuses a duplicate identity while the first path still exists — so it
        # never registers, and "the deepest registered path containing this
        # directory" answers with the OUTER project. Measured: `devman run
        # check` typed inside such a checkout enqueued a run against the parent
        # checkout, with nothing said (`STAGE_5_LOG.md`, S3).
        #
        # That is the failure this whole design refuses everywhere else: a run
        # that succeeds and does its work in the wrong tree. So it is a refusal,
        # and it names both directories.
        #
        # It walks UP a path the registry already names, one `exists` per level.
        # §15.1 forbids walking the disk to find repositories; this finds none —
        # it asks whether the directory the caller is standing in is its own
        # checkout.
        inner = _checkout_between(here, best.path.resolve())
        if inner is not None:
            raise RegistryError(
                f"refusing to resolve '{best.name}' from this directory\n"
                f"  {inner}\n"
                f"  is a checkout of its own, inside '{best.name}' at"
                f" {best.path}\n"
                "  a run triggered here would do its work in the outer checkout,"
                " not this one\n"
                "  give this checkout a distinct devman.project and enter its"
                " shell (§9.1), or say --project explicitly"
            )
        return best

    def workflow_file(self, project: Project, workflow: str) -> Path:
        """The projected file for one workflow — the winner of §7.3."""
        path = (project.entry or self.projects_dir / project.name) / "workflows"
        path = path / f"{workflow}.yaml"
        if not path.exists():
            names = ", ".join(project.workflow_names()) or "(none)"
            raise RegistryError(
                f"project '{project.name}' has no workflow named '{workflow}'\n"
                f"  it projects: {names}"
            )
        return path

    def dag_name(self, project: Project, workflow: str) -> str:
        """The machine-global DAG name. See `STAGE_1_LOG.md` S1."""
        return f"{project.name}-{workflow}"

    def dag_link_fault(self, project: Project, workflow: str) -> str | None:
        """What `dags/<project>-<workflow>.yaml` points at, when it is not this
        project's own file — and `None` when it is.

        **A DAG name is machine-global and `<project>-<workflow>` is not
        injective.** `devman-b` + `check` and `devman` + `b-check` render the
        same flat name, so the second projection overwrites the first's link and
        Dagu runs **one** file under a name two projects believe is theirs.
        Measured: `devman run check --project devman-b` executed devman's
        `b-check.yaml`, in devman-b's directory, and reported success, while
        `devman show` printed the file that did not run (`STAGE_5_LOG.md`, S6).

        §9.2 half-anticipated this — `unproject` already refuses to remove a
        link that points somewhere else, because "`<project>-<workflow>` is
        ambiguous when one project name is a prefix of another, and the link
        target is not". The link target is the answer here too: it is what the
        projection wrote, so comparing against it needs no second source.
        """
        link = self.dags_dir / f"{self.dag_name(project, workflow)}.yaml"
        want = f"../projects/{project.name}/workflows/{workflow}.yaml"
        try:
            got = os.readlink(link)
        except OSError:
            return "nothing — there is no dags/ link, so Dagu cannot run it by name"
        return None if got == want else got

    def projected_files(self) -> list[tuple[Project, str, Path]]:
        """Every `(project, workflow, projected file)` in the registry."""
        out = []
        for proj in self.projects().values():
            wdir = (proj.entry or self.projects_dir / proj.name) / "workflows"
            if not wdir.is_dir():
                continue
            for f in sorted(wdir.glob("*.yaml")):
                out.append((proj, f.stem, f))
        return out

    def unproject(self, project: Project) -> list[Path]:
        """Remove one project's projection. `doctor --prune` only (§10 check 5).

        A `dags/` link is removed only when it still points at this project's
        own file: `<project>-<workflow>` is ambiguous when one project name is a
        prefix of another, and the link target is not. That is the same rule the
        devenv module's projection script applies.
        """
        removed: list[Path] = []
        entry = project.entry or self.projects_dir / project.name
        wdir = entry / "workflows"
        for f in sorted(wdir.glob("*.yaml")) if wdir.is_dir() else []:
            link = self.dags_dir / f"{project.name}-{f.stem}.yaml"
            want = f"../projects/{project.name}/workflows/{f.stem}.yaml"
            if link.is_symlink() and os.readlink(link) == want:
                link.unlink()
                removed.append(link)
            f.unlink()
            removed.append(f)
        _rmdir(wdir)
        # `metadata.json` goes last, so a prune interrupted half way leaves an
        # entry `doctor` reports again rather than a directory nothing owns.
        meta = entry / "metadata.json"
        if meta.exists():
            meta.unlink()
            removed.append(meta)
        _rmdir(entry)
        return removed


def _checkout_between(here: Path, root: Path) -> Path | None:
    """The outermost directory strictly below `root` that holds its own `.git`.

    `.git` is a directory in an ordinary clone and a **file** in a linked
    worktree, so this tests existence rather than kind. The outermost one is
    returned rather than the nearest, because that is the one that stands
    between the caller and the project the registry would answer with.

    A submodule answers this test too, and that is intended: a run triggered
    inside a submodule and executed in the parent checkout is the same
    ambiguity, and the plane's habit is to make it loud rather than to guess.
    """
    found: Path | None = None
    here = here if here.is_dir() else here.parent
    while here != root and here != here.parent:
        if (here / ".git").exists():
            found = here
        here = here.parent
    return found


def _rmdir(path: Path) -> None:
    """Remove a directory if it is empty. Anything else there is not devman's."""
    with contextlib.suppress(OSError):
        path.rmdir()
