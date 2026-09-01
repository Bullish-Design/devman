"""Reading devman's registry (CONCEPT.md §9.2).

The registry is derived and the repository is canonical (§9.3), so everything
here reads and nothing here writes. The one exception is `Registry.unproject`,
which `doctor --prune` calls, and §10 makes that safe for the same reason: a
pruned entry restores itself the next time that repository's shell is entered.

    ~/.local/share/devman/
    ├── projects/<project>/metadata.json               # identity and path
    │   └── workflows/<workflow>.yaml   -> the winner of §7.3's resolution
    └── dags/<project>.<workflow>.yaml  -> the line above

`dags/` is Dagu's flat view; `projects/` is devman's. A DAG is keyed by its
file's base name, so the flat name is what `dagu ls`, the scheduler and `dagu
enqueue` all agree on (`STAGE_1_LOG.md`, S1). `dag_name()` below is the codec
that renders it, and the separator is a dot because `<project>-<workflow>` was
not injective (S-12).

**Nothing here walks the disk looking for repositories.** §15.1 forbids it.
Reading devman's own registry is not scanning.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
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

# THE DAG IDENTITY CODEC (§9.2, S-12).
#
# A DAG name is machine-global, and `<project>-<workflow>` did not make it
# unique: `devman-b` + `check` and `devman` + `b-check` render one name, so the
# second projection took the first's link and Dagu ran ONE file under a name two
# projects believed was theirs (`STAGE_5_LOG.md`, S6). Measured on this machine
# at 53 projects: no collision, and six one workflow name away — `flora` needs
# only a workflow called `core-check` to take `flora-core`'s DAG.
#
# The separator is a dot, and the character set is measured rather than chosen:
# Dagu 2.15.0 allows alphanumerics, dashes, dots and underscores in a name and
# refuses everything else (S-11). Of those, `-` and `_` are both already in use
# INSIDE project names on this machine, and a dot is not — one project,
# `loci.nvim`, carries a dot, and no workflow name carries one at all.
#
# So the codec joins with a dot and REFUSES a dot in the workflow half. That is
# what makes it injective, in one sentence: the last dot is always the
# separator, so `rsplit` recovers the pair. A project name may hold as many dots
# as it likes, which is what keeps `loci.nvim` spelled the way its author
# spells it.
DAG_SEPARATOR = "."

# The pre-S-12 shape, kept for one release so that a repository which has not
# been re-entered since the codec changed still triggers. `doctor` names every
# one of them, and `run` says so on stderr before it falls back. Delete both
# when `doctor` reports no unmigrated workflow on any machine that matters.
LEGACY_DAG_SEPARATOR = "-"

# THE IDENTITY GRAMMAR (009 P1-5). One definition, from the same measured Dagu
# character set as the codec above. The leading character is restricted so that
# `-flag` and `.hidden` cannot be names.
#
# It is duplicated at the Nix boundary in `modules/devenv.nix`, because §3.1
# says what the two interfaces share must be TEXT and a Python function is not
# text. `tests/fixtures/identity.json` is the shared table that proves the two
# copies agree; three readers assert against it.
IDENTITY_GRAMMAR = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
IDENTITY_PATTERN = re.compile(IDENTITY_GRAMMAR)


class RegistryError(Exception):
    """A refusal the developer must see. The CLI prints it and exits 1."""


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


def deepest(roots: dict[str, Path], here: Path) -> str | None:
    """The key whose root contains `here` most deeply, or `None`.

    **ONE RULE, TWO CALLERS.** `Registry.project_for()` answers it for a
    developer's current directory, and `watch.match()` answers it for a changed
    file. They disagreed until 009 (P1-4): the watcher implemented containment
    independently and accepted EVERY registered root containing the path. With
    `outer/` and `outer/inner/` both registered, one save of
    `outer/inner/changed.py` enqueued a run in each — and the outer repository's
    formatter then rewrote source across the nested repository boundary. Both
    runs reported success.

    Depth is compared on the resolved path, so a symlinked checkout resolves to
    the tree it really is. A root that cannot be resolved is skipped rather than
    raising: a registry entry whose repository has been moved is an ordinary,
    self-healing state (`watch.watch_map()`).
    """
    best: str | None = None
    best_depth = -1
    for key, root in roots.items():
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if here != resolved and resolved not in here.parents:
            continue
        depth = len(resolved.parts)
        if depth > best_depth:
            best, best_depth = key, depth
    return best


def dag_name_fault(workflow: str) -> str | None:
    """Why this workflow name cannot go through the codec, or `None`.

    **The one refusal the codec needs.** A dot in the workflow half would make
    the last dot ambiguous and the name no longer injective — the whole property
    the codec exists to provide. A dot in the PROJECT half is fine and stays
    fine, because the split reads from the right.

    It costs nothing today: no workflow name on this machine holds a dot, and a
    workflow name is a file's base name in `groups/<g>/workflows/` or
    `.devman/workflows/`, so a group author learns at evaluation time rather
    than at run time.
    """
    if DAG_SEPARATOR in workflow:
        return (
            f"'{workflow}' cannot be a workflow name — it holds a"
            f" '{DAG_SEPARATOR}'\n"
            f"  a DAG name is <project>{DAG_SEPARATOR}<workflow>, and the last"
            f" '{DAG_SEPARATOR}' is the separator (§9.2)\n"
            "  rename the file; a project name may hold dots, a workflow name"
            " may not"
        )
    return None


def split_dag_name(name: str) -> tuple[str, str]:
    """The `(project, workflow)` a DAG name was built from.

    The inverse of `Registry.dag_name()`, and the reason the codec is worth
    calling one: reading the pair back needs no registry lookup.
    """
    project, _, workflow = name.rpartition(DAG_SEPARATOR)
    return project, workflow


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


def _field_fault(raw: dict) -> str | None:
    """Whether an entry's fields have the types the readers assume.

    `raw.get` on a list raises `AttributeError`, and every reader of a Project
    assumes `path` is a string and `groups` a list. One entry hand-edited into
    the wrong shape could crash `run`, `show`, `watch` and `doctor` at once, so
    the shape is checked once, here, rather than defended at each use.
    """
    expected = {
        "project": str,
        "path": str,
        "plan": str,
        "groups": list,
        "local": list,
        "workflows": dict,
        "schema": int,
    }
    for field_name, kind in expected.items():
        if field_name not in raw:
            continue
        value = raw[field_name]
        # `bool` is an `int` in Python, and a schema of `true` is not a schema.
        if isinstance(value, bool) and kind is not bool:
            return f"its '{field_name}' is a boolean, not a {kind.__name__}"
        if not isinstance(value, kind):
            return (
                f"its '{field_name}' is a {type(value).__name__}, not a {kind.__name__}"
            )
    return None


@dataclass
class RegistryFault:
    """One entry the registry cannot read, named rather than skipped.

    The registry is derived (§9.3), so every fault here is repaired by entering
    that repository's shell — or by `devman doctor --prune` when the repository
    is gone. Naming it is the whole point: an entry that is skipped silently
    keeps its `dags/` links and its schedules, so its workflows go on running
    while nothing can see the project they belong to.
    """

    name: str
    path: Path
    why: str


class Registry:
    def __init__(self, root: str | os.PathLike[str] = DEFAULT_REGISTRY) -> None:
        self.root = Path(os.path.expanduser(str(root)))

    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    @property
    def dags_dir(self) -> Path:
        return self.root / "dags"

    def load(self) -> tuple[dict[str, Project], list[RegistryFault]]:
        """Every valid project, and every entry that is not one (009 P2-3).

        **This used to skip silently, and the silence was worse than the crash
        it avoided.** Invalid JSON was passed over as if the project did not
        exist — while its `dags/` links and its schedules stayed live. So a
        scheduled workflow kept firing and every registry reader, `doctor`
        included, was blind to it. Then the skip was incomplete: valid JSON that
        was not an object reached `raw.get`, which raises `AttributeError` on a
        list, and could crash `run`, `show`, `watch` and `doctor` together.

        **The comment that justified the silence is gone, and so is its
        premise.** It said a half-written entry is retried on the next shell
        entry, because the projection writes `metadata.json` last. That is still
        true, but since stage 3 the write is `os.replace` of a fully-written
        temporary file (`src/devman/project.py`), so a reader never sees a
        partial one. There is no longer a normal state that produces unreadable
        JSON — which means an unreadable entry is a fault, and faults are named.
        """
        out: dict[str, Project] = {}
        faults: list[RegistryFault] = []
        if not self.projects_dir.is_dir():
            return out, faults
        for entry in sorted(self.projects_dir.iterdir()):
            if not entry.is_dir():
                continue
            meta = entry / "metadata.json"
            if not meta.is_file():
                # Not a fault. The projection creates the directory before it
                # writes the entry, so this is the window §9.3 describes, and
                # the next shell entry closes it.
                continue
            try:
                text = meta.read_text()
            except OSError as exc:
                faults.append(RegistryFault(entry.name, meta, f"cannot read it: {exc}"))
                continue
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                faults.append(
                    RegistryFault(entry.name, meta, f"it is not valid JSON: {exc}")
                )
                continue
            if not isinstance(raw, dict):
                faults.append(
                    RegistryFault(
                        entry.name,
                        meta,
                        f"it is valid JSON but a {type(raw).__name__}, not an object",
                    )
                )
                continue
            fault = _field_fault(raw)
            if fault:
                faults.append(RegistryFault(entry.name, meta, fault))
                continue
            name = raw.get("project", entry.name)
            # Stage 5's grammar, applied to what a legacy entry recorded. A name
            # that cannot be one is a fault rather than a working project: it
            # renders a DAG name the pinned Dagu refuses (§9.2, S-11).
            fault = identity_fault("project", name)
            if fault:
                faults.append(RegistryFault(entry.name, meta, fault.splitlines()[0]))
                continue
            out[entry.name] = Project(
                name=name,
                path=Path(raw.get("path", "")),
                groups=raw.get("groups", []),
                local=raw.get("local", []),
                workflows=raw.get("workflows", {}),
                triggers=raw.get("triggers"),
                plan=raw.get("plan", ""),
                schema=raw.get("schema", 0),
                entry=entry,
            )
        return out, faults

    def projects(self) -> dict[str, Project]:
        """The valid projects. A caller that must report a fault uses `load()`.

        The signature is unchanged on purpose. Every reader wants the valid
        projects, and three of them — `doctor`, `run`/`show` and `watch` — want
        the faults as well, each for a different reason (§8.3 of the 009 guide).
        A wide refactor here would touch every reader for no benefit.
        """
        return self.load()[0]

    def faults(self) -> list[RegistryFault]:
        return self.load()[1]

    def project(self, name: str) -> Project:
        """One project by name, or a refusal that says which problem this is.

        **A corrupt entry and an absent one are different problems and used to
        give one message** (009 P2-3). "no project named 'x'" sent the developer
        to register a repository that is already registered, while the entry
        that was actually wrong went unmentioned. `run` and `show` refuse only
        when the project they were asked for is the corrupt one; every other
        project on the machine keeps working.
        """
        projects, faults = self.load()
        if name not in projects:
            for fault in faults:
                if fault.name == name:
                    raise RegistryError(
                        f"refusing to use '{name}' — its registry entry is"
                        " unreadable\n"
                        f"  {fault.why}\n"
                        f"  {fault.path}\n"
                        "  enter that repository's shell to rewrite it, or"
                        " `devman doctor --prune` if it is gone"
                    )
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

        The rule itself is `deepest()`. This is one of its two callers.
        """
        here = Path(cwd).resolve()
        projects = self.projects()
        owner = deepest({n: p.path for n, p in projects.items()}, here)
        best = projects[owner] if owner else None
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
        """The machine-global DAG name (`STAGE_1_LOG.md` S1, S-12's codec).

        **Injective, and that is the whole point.** The last `DAG_SEPARATOR` is
        always the separator, so no two `(project, workflow)` pairs can render
        one name — `dag_name_fault()` is what keeps the workflow half free of
        one, and the module refuses it at evaluation time as well.

        `<project>-<workflow>` was not injective, and the failure it allowed was
        silent: Dagu ran one file under a name two projects believed was theirs
        (S6).
        """
        return f"{project.name}{DAG_SEPARATOR}{workflow}"

    def legacy_dag_name(self, project: Project, workflow: str) -> str:
        """The pre-S-12 name. Migration only — see `LEGACY_DAG_SEPARATOR`."""
        return f"{project.name}{LEGACY_DAG_SEPARATOR}{workflow}"

    def dag_link_fault(self, project: Project, workflow: str) -> str | None:
        """What `dags/<project>.<workflow>.yaml` points at, when it is not this
        project's own file — and `None` when it is.

        The link target is the answer: it is what the projection wrote, so
        comparing against it needs no second source. §9.2 already used the same
        rule in `unproject`, which refuses to remove a link pointing elsewhere.

        A link that is simply absent because this project has not been
        re-projected since the codec changed is `unmigrated()`'s business, not a
        collision.
        """
        return self._link_fault(self.dag_name(project, workflow), project, workflow)

    def _link_fault(self, dag: str, project: Project, workflow: str) -> str | None:
        link = self.dags_dir / f"{dag}.yaml"
        want = f"../projects/{project.name}/workflows/{workflow}.yaml"
        try:
            got = os.readlink(link)
        except OSError:
            return "nothing — there is no dags/ link, so Dagu cannot run it by name"
        return None if got == want else got

    def unmigrated(self, project: Project, workflow: str) -> bool:
        """True when this workflow still projects only under the pre-S-12 name.

        **This is what stops the codec being a flag day.** The projection runs
        on shell entry, one repository at a time, so the machine holds both
        shapes until every repository has been entered again. Without this the
        codec would refuse every trigger in 52 of 53 repositories the moment it
        landed — the new link does not exist yet, and "there is no dags/ link"
        is indistinguishable from a collision.

        It is deliberately narrow: the new link must be missing AND the old one
        must point at this project's own file. A link pointing anywhere else is
        still a fault, because that is the collision the codec exists to end.
        """
        if self.dag_link_fault(project, workflow) is None:
            return False
        legacy = self.legacy_dag_name(project, workflow)
        return self._link_fault(legacy, project, workflow) is None

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
        own file. The codec makes the name injective, so a link under the
        current shape can only be this project's — but the rule stays, because
        the **legacy** shape below is exactly the ambiguous one, and a prune that
        removed another project's DAG would be the silent wrong-tree failure
        this design refuses everywhere else. That is the same rule the
        projection applies in `project._sweep()` — one rule, two callers, as with
        `deepest()`.

        Both shapes are removed while the machine holds both (S-12).
        """
        removed: list[Path] = []
        entry = project.entry or self.projects_dir / project.name
        wdir = entry / "workflows"
        for f in sorted(wdir.glob("*.yaml")) if wdir.is_dir() else []:
            want = f"../projects/{project.name}/workflows/{f.stem}.yaml"
            for sep in (DAG_SEPARATOR, LEGACY_DAG_SEPARATOR):
                link = self.dags_dir / f"{project.name}{sep}{f.stem}.yaml"
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
