"""Central project resolution and rendering for the machine plane.

This module is the pure Devman side of the plane boundary. It reads a portable
project manifest, resolves group and overlay sources, and returns a complete
projection bundle. It does not write a repository, start Dagu, or activate a
generation. Vendomat owns those machine operations.

The compatibility ``project apply`` path publishes through this same module.
It keeps the old registry shape only until the machine-plane activation path
replaces it.
"""

from __future__ import annotations

import base64
import importlib.metadata
import json
import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from devman_contract import (
    PlaneGeneration,
    ProjectionRecord,
    ProjectManifest,
    digest_blobs,
    digest_bytes,
    digest_file,
)

from .project import (
    ProjectionError,
    entry_text,
    render,
    resolve_triggers,
    resolve_writes,
)
from .registry import DAG_SEPARATOR, identity_fault

RECONCILIATION_SCHEMA = 1
INSPECTION_SCHEMA = 1
MANIFEST_RELATIVE = ".devman/project.toml"


class ReconcileError(ProjectionError):
    """A central resolution or rendering refusal."""


@dataclass(frozen=True)
class ResolvedWorkflow:
    """One workflow after group and central-overlay precedence is applied."""

    name: str
    source: Path
    source_label: str
    group: str
    shadows: tuple[str, ...]

    def metadata(self) -> dict[str, object]:
        return {
            "group": self.group,
            "shadows": list(self.shadows),
            "source": str(self.source),
        }


@dataclass(frozen=True)
class PolicyResolution:
    """The resolved policy inputs used for one project."""

    policy: str
    groups: tuple[str, ...]
    groups_root: Path
    workflows: dict[str, ResolvedWorkflow]
    triggers: object
    writes: object
    digest: str


@dataclass(frozen=True)
class ProjectionBundle:
    """A serialisable, fully rendered project projection.

    ``files`` are regular files relative to a generation's registry root.
    ``links`` are the Dagu flat view and are created by Vendomat only after all
    workflow files pass validation.
    """

    project: str
    generation: PlaneGeneration
    record: ProjectionRecord
    files: dict[str, bytes]
    links: dict[str, str]
    sources: dict[str, str]

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": RECONCILIATION_SCHEMA,
            "project": self.project,
            "generation": self.generation.to_mapping(),
            "record": self.record.to_mapping(),
            "files": {
                name: base64.b64encode(body).decode("ascii")
                for name, body in sorted(self.files.items())
            },
            "links": dict(sorted(self.links.items())),
            "sources": dict(sorted(self.sources.items())),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_mapping(), sort_keys=True, indent=2) + "\n"


@dataclass(frozen=True)
class ProjectionInspection:
    """The identities needed before a project needs a new render."""

    project: str
    generation: PlaneGeneration
    record: ProjectionRecord
    sources: dict[str, str]

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": INSPECTION_SCHEMA,
            "project": self.project,
            "generation": self.generation.to_mapping(),
            "record": self.record.to_mapping(),
            "sources": dict(sorted(self.sources.items())),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_mapping(), sort_keys=True, indent=2) + "\n"


def renderer_digest() -> str:
    """Return the identity of the packaged Python renderer.

    The digest covers the Devman Python package rather than the process PATH.
    A source change therefore changes the identity even when a machine keeps
    the same executable name.
    """

    package = Path(__file__).resolve().parent
    blobs = {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in package.glob("*.py")
        if path.is_file()
    }
    return digest_blobs(blobs)


def runtime_version() -> str:
    """Return the installed Devman version for generation metadata."""

    try:
        return importlib.metadata.version("devman")
    except importlib.metadata.PackageNotFoundError:
        return "source"


def resolve_policy(
    manifest: ProjectManifest,
    policy_root: Path,
) -> PolicyResolution:
    """Resolve group files, triggers, writes, and central policy identity."""

    root = policy_root.expanduser().resolve()
    groups_root = root / "groups"
    if not groups_root.is_dir():
        raise ReconcileError(
            f"cannot resolve policy '{manifest.policy}'\n"
            f"  group root is not a directory: {groups_root}"
        )

    workflows: dict[str, ResolvedWorkflow] = {}
    trigger_source: dict[str, object] | None = None
    writes: dict[str, object] = {}
    policy_blobs: dict[str, bytes] = {
        "policy": manifest.policy.encode(),
    }

    for group in manifest.groups:
        group_dir = groups_root / group
        if not group_dir.is_dir():
            raise ReconcileError(
                f"cannot resolve project '{manifest.project}'\n"
                f"  group '{group}' does not exist under {groups_root}"
            )

        workflow_dir = group_dir / "workflows"
        for source in (
            sorted(workflow_dir.glob("*.yaml")) if workflow_dir.is_dir() else ()
        ):
            name = source.stem
            _validate_workflow_name(name, manifest.project)
            previous = workflows.get(name)
            shadows = () if previous is None else previous.shadows + (previous.group,)
            workflows[name] = ResolvedWorkflow(
                name=name,
                source=source,
                source_label=_relative_label(root, source),
                group=group,
                shadows=shadows,
            )
            policy_blobs[_relative_label(root, source)] = source.read_bytes()

        trigger_file = group_dir / "triggers.toml"
        if trigger_file.is_file():
            raw = _read_toml(trigger_file, "triggers")
            if not isinstance(raw, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in raw.items()
            ):
                raise ReconcileError(
                    f"cannot resolve triggers for group '{group}'\n"
                    "  triggers.toml must map glob strings to workflow names"
                )
            trigger_source = {"group": group, "map": raw}
            policy_blobs[_relative_label(root, trigger_file)] = (
                trigger_file.read_bytes()
            )

        writes_file = group_dir / "writes.toml"
        if writes_file.is_file():
            raw_writes = _read_toml(writes_file, "writes")
            if not isinstance(raw_writes, dict) or not all(
                isinstance(key, str) and isinstance(value, dict)
                for key, value in raw_writes.items()
            ):
                raise ReconcileError(
                    f"cannot resolve writes for group '{group}'\n"
                    "  writes.toml must hold one table per workflow"
                )
            writes.update(raw_writes)
            policy_blobs[_relative_label(root, writes_file)] = writes_file.read_bytes()

    # The generation has one policy identity for the whole machine. Include
    # every semantic group source so two projects selecting different groups
    # still share one generation identity and a policy edit is visible to all
    # affected projections.
    policy_blobs = {"policy": manifest.policy.encode()}
    for source in sorted(groups_root.rglob("*")):
        if source.is_file() and source.suffix in {".yaml", ".toml"}:
            policy_blobs[_relative_label(root, source)] = source.read_bytes()

    return PolicyResolution(
        policy=manifest.policy,
        groups=manifest.groups,
        groups_root=groups_root,
        workflows=workflows,
        triggers=trigger_source,
        writes=writes or None,
        digest=digest_blobs(policy_blobs),
    )


def resolve_project(
    root: Path,
    *,
    policy_root: Path,
    overlay_root: Path,
) -> tuple[
    ProjectManifest,
    PolicyResolution,
    dict[str, ResolvedWorkflow],
    str | None,
    object,
    object,
]:
    """Resolve one manifest and apply the central per-project overlay."""

    project_root = root.expanduser().resolve()
    if not project_root.is_dir():
        raise ReconcileError(f"project root is not a directory: {project_root}")
    manifest = ProjectManifest.from_root(project_root)
    policy = resolve_policy(manifest, policy_root)

    selected = dict(policy.workflows)
    overlay = (
        overlay_root.expanduser().resolve()
        / "projects"
        / manifest.project
        / "workflows"
    )
    overlay_digest: str | None = None
    overlay_blobs: dict[str, bytes] = {}
    if overlay.is_dir():
        for source in sorted(overlay.glob("*.yaml")):
            name = source.stem
            _validate_workflow_name(name, manifest.project)
            previous = selected.get(name)
            shadows = (
                (previous.group,) + previous.shadows if previous is not None else ()
            )
            selected[name] = ResolvedWorkflow(
                name=name,
                source=source,
                source_label=_relative_label(
                    overlay_root.expanduser().resolve(), source
                ),
                group="overlay",
                shadows=shadows,
            )
            overlay_blobs[f"workflows/{name}.yaml"] = source.read_bytes()
    for local_name in ("triggers.toml", "writes.toml"):
        local_path = project_root / ".devman" / local_name
        if local_path.is_file():
            overlay_blobs[f"local/{local_name}"] = local_path.read_bytes()
    if overlay_blobs:
        overlay_digest = digest_blobs(overlay_blobs)

    local_triggers = _local_layer(project_root, "triggers.toml")
    triggers = _merge_local_triggers(policy.triggers, local_triggers)
    local_writes = _local_layer(project_root, "writes.toml")
    writes = _merge_local_writes(policy.writes, local_writes)
    return manifest, policy, selected, overlay_digest, triggers, writes


def render_project(
    root: Path,
    *,
    policy_root: Path,
    overlay_root: Path,
    generation: PlaneGeneration,
    plan: str | None = None,
) -> ProjectionBundle:
    """Resolve and render one project into a Vendomat-consumable bundle."""

    resolved, record, sources = _resolve_identity(
        root,
        policy_root=policy_root,
        overlay_root=overlay_root,
        generation=generation,
    )
    manifest, _policy, workflows, _overlay_digest, triggers, writes = resolved

    rendered: dict[str, bytes] = {}
    for name, workflow in sorted(workflows.items()):
        body = render(workflow.source, root, source_label=workflow.source_label)
        rendered[f"projects/{manifest.project}/workflows/{name}.yaml"] = body.encode()

    local_names = sorted(
        name for name, workflow in workflows.items() if workflow.group == "overlay"
    )
    metadata = entry_text(
        project=manifest.project,
        root=root.expanduser().resolve(),
        groups=list(manifest.groups),
        plan=plan if plan is not None else f"plane:{generation.generation}",
        local=local_names,
        workflows={
            name: workflow.metadata() for name, workflow in sorted(workflows.items())
        },
        triggers=resolve_triggers(triggers, root),
        writes=resolve_writes(writes, root),
        overlay=str(overlay_root.expanduser().resolve()),
        links={},
    )
    rendered[f"projects/{manifest.project}/metadata.json"] = metadata.encode()
    rendered[f"projects/{manifest.project}/projection.json"] = (
        json.dumps(record.to_mapping(), sort_keys=True, indent=2) + "\n"
    ).encode()

    links = {
        f"dags/{manifest.project}{DAG_SEPARATOR}{name}.yaml": (
            f"../projects/{manifest.project}/workflows/{name}.yaml"
        )
        for name in workflows
    }
    return ProjectionBundle(
        project=manifest.project,
        generation=generation,
        record=record,
        files=rendered,
        links=links,
        sources=sources,
    )


def compatibility_apply(
    root: Path,
    *,
    policy_root: Path,
    overlay_root: Path,
    registry: Path,
    state: Path,
    plan: str,
    dagu: str | None = None,
) -> None:
    """Publish one canonical render into the temporary compatibility registry."""

    project_root = root.expanduser().resolve()
    manifest = ProjectManifest.from_root(project_root)
    policy = resolve_policy(manifest, policy_root)
    binary = dagu or shutil.which("dagu") or "dagu"
    dagu_digest = (
        digest_file(Path(binary))
        if Path(binary).is_file()
        else digest_bytes(binary.encode())
    )
    generation = PlaneGeneration(
        generation=0,
        devman_runtime=runtime_version(),
        renderer_digest=renderer_digest(),
        policy_digest=policy.digest,
        dagu_digest=dagu_digest,
        toolchain_digest=digest_bytes(b"compatibility"),
    )
    bundle = render_project(
        project_root,
        policy_root=policy_root,
        overlay_root=overlay_root,
        generation=generation,
        plan=plan,
    )
    _publish_compatibility_bundle(
        bundle,
        project_root,
        registry=registry,
        state=state,
        dagu=binary,
    )


def _publish_compatibility_bundle(
    bundle: ProjectionBundle,
    root: Path,
    *,
    registry: Path,
    state: Path,
    dagu: str,
) -> None:
    """Write a canonical bundle in the old registry shape until item 4 lands."""

    project = bundle.project
    workflow_prefix = f"projects/{project}/workflows/"
    rendered = {
        name.removeprefix(workflow_prefix).removesuffix(".yaml"): body.decode()
        for name, body in bundle.files.items()
        if name.startswith(workflow_prefix)
    }
    metadata_path = f"projects/{project}/metadata.json"
    metadata = bundle.files.get(metadata_path)
    if metadata is None:
        raise ReconcileError(
            f"canonical render omitted compatibility metadata for '{project}'"
        )

    registry_entry = registry / "projects" / project
    workflows_dir = registry_entry / "workflows"
    dags = registry / "dags"
    entry = state / "projects" / project
    workflows_dir.mkdir(parents=True, exist_ok=True)
    dags.mkdir(parents=True, exist_ok=True)
    entry.mkdir(parents=True, exist_ok=True)
    for name in ("logs", "artifacts", "reports"):
        (root / ".devman" / ".runs" / name).mkdir(parents=True, exist_ok=True)

    published = _compatibility_published(workflows_dir)
    recorded_plan = _compatibility_recorded_plan(entry)
    plan = json.loads(metadata.decode())["plan"]
    revalidate = recorded_plan != plan
    staging = workflows_dir / ".validate"
    try:
        staging.mkdir(exist_ok=True)
        for name, text in rendered.items():
            if not (revalidate or published.get(name) != text):
                continue
            checked = staging / f"{name}.yaml"
            checked.write_text(text)
            _validate_compatibility(dagu, checked, Path(bundle.sources.get(name, name)))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    for name in sorted(set(published) - set(rendered)):
        (workflows_dir / f"{name}.yaml").unlink(missing_ok=True)
        link = dags / f"{project}.{name}.yaml"
        target = f"../projects/{project}/workflows/{name}.yaml"
        if link.is_symlink() and os.readlink(link) == target:
            link.unlink()

    for name, text in rendered.items():
        temporary = workflows_dir / f".{name}.yaml.new"
        temporary.write_text(text)
        os.replace(temporary, workflows_dir / f"{name}.yaml")

    for relative, target in bundle.links.items():
        _compatibility_relink(registry / relative, target)

    for local_name in ("triggers.toml", "writes.toml"):
        source = root / ".devman" / local_name
        kept = entry / local_name
        if source.is_file():
            kept.write_text(source.read_text())
        else:
            kept.unlink(missing_ok=True)

    temporary = entry / ".metadata.json.new"
    temporary.write_bytes(metadata)
    os.replace(temporary, entry / "metadata.json")


def _compatibility_published(workflows_dir: Path) -> dict[str, str]:
    """Read existing compatibility workflow bytes by name."""

    out = {}
    for path in workflows_dir.glob("*.yaml"):
        try:
            out[path.stem] = path.read_text()
        except OSError:
            continue
    return out


def _compatibility_recorded_plan(entry: Path) -> str | None:
    """Read the last canonical plan identity, if the entry exists."""

    try:
        return json.loads((entry / "metadata.json").read_text()).get("plan")
    except (OSError, ValueError):
        return None


def _compatibility_relink(link: Path, target: str) -> None:
    """Create one compatibility DAG link without replacing an equal link."""

    if link.is_symlink() and os.readlink(link) == target:
        return
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def _validate_compatibility(binary: str, rendered: Path, source: Path) -> None:
    """Validate one canonical workflow before compatibility publication."""

    result = subprocess.run(
        [binary, "validate", str(rendered)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return
    message = (result.stderr or result.stdout).strip()
    raise ProjectionError(
        f"refusing to publish '{rendered.stem}'\n"
        f"  its source is {source}\n"
        "  dagu refuses the file this renders:\n"
        + "\n".join(f"    {line}" for line in message.splitlines())
        + "\n  nothing was published; fix the source and enter the shell again"
    )


def inspect_project(
    root: Path,
    *,
    policy_root: Path,
    overlay_root: Path,
    generation: PlaneGeneration,
) -> ProjectionInspection:
    """Resolve one project without rendering or writing files."""

    _resolved, record, sources = _resolve_identity(
        root,
        policy_root=policy_root,
        overlay_root=overlay_root,
        generation=generation,
    )
    return ProjectionInspection(
        project=record.project,
        generation=generation,
        record=record,
        sources=sources,
    )


def _resolve_identity(
    root: Path,
    *,
    policy_root: Path,
    overlay_root: Path,
    generation: PlaneGeneration,
) -> tuple[
    tuple[
        ProjectManifest,
        PolicyResolution,
        dict[str, ResolvedWorkflow],
        str | None,
        object,
        object,
    ],
    ProjectionRecord,
    dict[str, str],
]:
    """Resolve the inputs shared by inspection and rendering."""

    resolved = resolve_project(
        root,
        policy_root=policy_root,
        overlay_root=overlay_root,
    )
    manifest, policy, workflows, overlay_digest, triggers, writes = resolved

    if generation.policy_digest != policy.digest:
        raise ReconcileError(
            f"generation {generation.generation} does not match policy for '{manifest.project}'\n"
            f"  generation: {generation.policy_digest}\n"
            f"  resolved:   {policy.digest}"
        )
    current_renderer = renderer_digest()
    if generation.renderer_digest != current_renderer:
        raise ReconcileError(
            f"generation {generation.generation} does not match the packaged renderer\n"
            f"  generation: {generation.renderer_digest}\n"
            f"  renderer:   {current_renderer}"
        )

    source_blobs: dict[str, bytes] = {}
    sources: dict[str, str] = {}
    for name, workflow in sorted(workflows.items()):
        source_blobs[f"workflows/{name}.yaml"] = workflow.source.read_bytes()
        sources[name] = workflow.source_label

    source_digest = digest_blobs(source_blobs)
    record = ProjectionRecord(
        project=manifest.project,
        manifest_digest=manifest.digest,
        policy_digest=policy.digest,
        plane_generation=generation.generation,
        renderer_digest=generation.renderer_digest,
        source_digest=source_digest,
        overlay_digest=overlay_digest,
    )

    return resolved, record, sources


def bundle_from_json(text: str) -> ProjectionBundle:
    """Decode a renderer bundle emitted by ``devman project render``."""

    raw = json.loads(text)
    if raw.get("schema") != RECONCILIATION_SCHEMA:
        raise ReconcileError(
            f"unsupported projection bundle schema: {raw.get('schema')!r}"
        )
    files = {
        name: base64.b64decode(body, validate=True)
        for name, body in raw.get("files", {}).items()
    }
    return ProjectionBundle(
        project=raw["project"],
        generation=PlaneGeneration.from_mapping(raw["generation"]),
        record=ProjectionRecord.from_mapping(raw["record"]),
        files=files,
        links=dict(raw.get("links", {})),
        sources=dict(raw.get("sources", {})),
    )


def inspection_from_json(text: str) -> ProjectionInspection:
    """Decode a read-only inspection emitted by ``devman project inspect``."""

    raw = json.loads(text)
    if raw.get("schema") != INSPECTION_SCHEMA:
        raise ReconcileError(
            f"unsupported projection inspection schema: {raw.get('schema')!r}"
        )
    generation = PlaneGeneration.from_mapping(raw["generation"])
    record = ProjectionRecord.from_mapping(raw["record"])
    if raw.get("project") != record.project:
        raise ReconcileError("projection inspection project does not match its record")
    sources = raw.get("sources", {})
    if not isinstance(sources, dict) or not all(
        isinstance(name, str) and isinstance(source, str)
        for name, source in sources.items()
    ):
        raise ReconcileError("projection inspection sources must map names to strings")
    return ProjectionInspection(
        project=record.project,
        generation=generation,
        record=record,
        sources=dict(sources),
    )


def _validate_workflow_name(name: str, project: str) -> None:
    fault = identity_fault("workflow", name)
    if fault:
        raise ReconcileError(
            f"refusing to resolve workflow '{name}' in '{project}'\n  {fault}"
        )
    if DAG_SEPARATOR in name:
        raise ReconcileError(
            f"refusing to resolve workflow '{name}' in '{project}'\n"
            f"  a workflow name may not hold '{DAG_SEPARATOR}'"
        )


def _relative_label(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _read_toml(path: Path, kind: str) -> object:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ReconcileError(f"cannot read {kind} policy {path}: {exc}") from exc


def _local_layer(root: Path, name: str) -> dict | None:
    path = root / ".devman" / name
    if not path.is_file():
        return None
    raw = _read_toml(path, name)
    if not isinstance(raw, dict):
        raise ReconcileError(f"local {name} must be a TOML table: {path}")
    return raw


def _merge_local_triggers(group: object, local: dict | None) -> object:
    if local is None:
        return group
    if set(local) - {"ignore", "map"}:
        raise ReconcileError("local triggers.toml may only contain ignore and map")
    ignore = local.get("ignore", [])
    mapping = local.get("map")
    if not isinstance(ignore, list) or not all(
        isinstance(item, str) for item in ignore
    ):
        raise ReconcileError("local triggers.toml ignore must be a list of strings")
    if mapping is not None and (
        not isinstance(mapping, dict)
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in mapping.items()
        )
    ):
        raise ReconcileError("local triggers.toml map must map strings to strings")
    group_map = group.get("map", {}) if isinstance(group, dict) else {}
    chosen = mapping if mapping is not None else group_map
    if not chosen:
        return None
    return {
        "group": group.get("group", "?")
        if mapping is None and isinstance(group, dict)
        else "(local)",
        "map": chosen,
        "ignore": ignore,
        "source": "local" if mapping is not None else "group+local",
    }


def _merge_local_writes(group: object, local: dict | None) -> object:
    if local is None:
        return group
    if not all(
        isinstance(key, str) and isinstance(value, dict) for key, value in local.items()
    ):
        raise ReconcileError("local writes.toml must hold one table per workflow")
    merged = dict(group) if isinstance(group, dict) else {}
    merged.update(local)
    return merged or None
