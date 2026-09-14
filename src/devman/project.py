"""The projection (CONCEPT.md §9.2, §11 Stage 3) — the producer, in Python.

    <state>/projects/<project>/metadata.json
    <registry>/projects/<project>/workflows/<workflow>.yaml   the generated file
    <registry>/dags/<project>.<workflow>.yaml   -> the line above

The compatibility `project apply` command may split `state` and `registry`
(§11 Stage 3). It publishes the canonical bundle from `reconcile.py`; this
module keeps the fixed registry metadata layout and body renderer.

**This used to be shell inside `modules/devenv.nix`, and four of project 009's
findings were one consequence of that.** The module decided the directory
variable with `grep -q 'DEVMAN_SELF_DIR'`, decided whether to add an `env:`
block with `grep -q '^env:'`, built JSON with `@PATH@` substitution, and
validated no identity at all. Meanwhile this package already answered every one
of those questions correctly, from a parsed document:

    is this a cross-repository parent?      Workflow.triggers_other_dags()
    does an `env:` block define a name?     workflow._env_holds()
    is this name legal?                     devman_contract.identity_fault()

So a comment mentioning `DEVMAN_SELF_DIR` changed the emitted variable (P1-1 —
`plane-report.yaml` shipped the wrong one for a whole stage), a body with any
`env:` block silently lost its directory variable (P1-1's severe case), a path
holding a quote or a colon-space corrupted the entry or the YAML (P2-1), and a
file Dagu cannot load was published and only discovered when somebody ran it
(P2-2). Delete the duplication and the four symptoms go with it.

**The plane still never parses a workflow to understand it (§7.2).** It reads
one document to decide what its own header must say, and it never edits the
body: the generated file is a header followed by the source, byte for byte. The
shell-entry guard depends on that tail equality, so this is a rule and not a
convenience — `test_the_rendered_file_ends_with_the_source_body` is what keeps
it true.

**It refuses rather than merging.** `REPORT.md` P1-1 asked for the required
variable to be merged into an existing `env:` value. Merging means editing the
body, which breaks both of the paragraphs above. A refusal costs the author one
line in their own file, and a silent omission cost this repository a stage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

import yaml

from .workflow import PROJECT_DIR, SELF_DIR, Workflow, _env_holds

# The registry entry's schema. SCHEMA 4 records the compatibility publisher's
# policy and renderer identity in `plan`. The old Nix plan held the resolved
# workflows, triggers, and renderer path; the canonical resolver now supplies
# those bytes at publication time.
#
# The change exists so that `plan` equality implies every derived field is
# unchanged. Under schema 3 it did not: the script's path changed when a group
# file changed but NOT when `triggers.toml` changed, because triggers reached
# the entry by a different route. The guard therefore had to compare the whole
# entry, which forced the entry to be rendered twice — once by bash with
# `@PATH@` substitution and once here — and that is P2-1's actual cause.
SCHEMA = 4


class ProjectionError(Exception):
    """A refusal the author must see. It names the file and the line to add."""


# ---------------------------------------------------------------------------
# the entry
#
# THE LAYOUT IS FIXED, AND THAT IS A REQUIREMENT RATHER THAN A STYLE.
#
# The shell-entry guard slices three fields out of this text without forking:
# `"path": "`, `"plan": "` and `"local": [` are the anchors it cuts on
# (`modules/devenv.nix`). `json.dumps` of the whole object would be free to
# reorder or re-indent, so the layout is written out and each VALUE is encoded
# by `json.dumps`. That closes P2-1's JSON half — a path holding a quote, a
# backslash or a newline is encoded properly — while keeping the three anchors
# where the guard expects them.
#
# `local` is written in the order the caller gave it, which is the order the
# hook's glob produced. The guard compares that string to the one it built
# itself, so echoing the order is what makes the comparison exact without
# either side having to agree on a sort.


def entry_text(
    *,
    project: str,
    root: Path,
    groups: list[str],
    plan: str,
    local: list[str],
    workflows: dict,
    triggers: object,
    writes: object = None,
    overlay: str = "~/.config/devman",
    links: object = None,
) -> str:
    return (
        "{\n"
        f'  "schema": {SCHEMA},\n'
        f'  "project": {json.dumps(project)},\n'
        f'  "path": {json.dumps(str(root))},\n'
        f'  "groups": {json.dumps(groups)},\n'
        f'  "plan": {json.dumps(plan)},\n'
        f'  "local": [{", ".join(json.dumps(n) for n in local)}],\n'
        f'  "workflows": {json.dumps(workflows, sort_keys=True)},\n'
        f'  "triggers": {json.dumps(triggers, sort_keys=True)},\n'
        f'  "writes": {json.dumps(writes, sort_keys=True)},\n'
        f'  "overlay": {json.dumps(overlay)},\n'
        f'  "links": {json.dumps(links or {}, sort_keys=True)}\n'
        "}\n"
    )


# WHY `writes` DOES NOT BUMP THE SCHEMA, AND `triggers` DID (015).
#
# Schema 2 added `workflows` and schema 3 added `triggers`, and both bumped
# because a RUN-TIME reader depends on them: `run.resolve()` reads `workflows`
# and the watcher reads `triggers`. An older reader that silently missed either
# would dispatch the wrong thing, which is the failure §15.7 exists to prevent.
#
# `writes` has no run-time reader. It is written by the projection and read by
# `doctor`, which is the same binary. An older `doctor` ignores the key and
# loses a check it never had — degradation without misbehaviour, which is what
# the version number is for. Bumping would instead make every already-projected
# entry on this machine report "a newer devman wrote these entries" until every
# shell is re-entered, for a field nothing at run time reads.


# ---------------------------------------------------------------------------
# the renderer


def render(
    source: Path,
    root: Path,
    *,
    text: str | None = None,
    source_label: str | None = None,
) -> str:
    """The generated file for one workflow: a header, then the body unchanged.

    | Source state | Emitted | Why |
    |---|---|---|
    | `triggers_other_dags()` | `DEVMAN_SELF_DIR` | §11: a parent must not hold the name it passes to its children |
    | otherwise | `DEVMAN_PROJECT_DIR` | §7.2, the ordinary case |
    | no top-level `env:` | the header `env:` block | decided from the parsed document, not from a grep |
    | `env:` states the required name with this project's path | nothing | already correct; a duplicate key would make the file fail to load |
    | `env:` states it with a different value | **refused** | never silently trust a reserved name |
    | `env:` states the other reserved name | **refused** | §11's two names are not interchangeable |
    | `env:` states neither | **refused**, naming the line to add | P1-1's severe case |
    | own `working_dir` / `log_dir` | left alone | the header adds; it never overwrites |

    Every emitted scalar goes through `yaml.safe_dump`, never `printf`. That is
    P2-1's YAML half: a path holding `: `, `#`, a quote, a backslash, a newline
    or a control character has to round-trip.

    The renderer is **total** for every path, including the three characters the
    shell-entry guard refuses in a repository root. Defence in depth: the hook's
    refusal protects the guard's forkless comparison, and this encoding protects
    the output. Neither substitutes for the other, and this is reachable from
    the tests without the hook.
    """
    wf = Workflow.read(source) if text is None else _read_text(source, text)
    if wf.error:
        raise ProjectionError(
            f"refusing to project {source}\n"
            f"  {wf.error}\n"
            "  fix the source; the plane publishes no file it cannot read"
        )

    doc = wf.doc or {}
    dir_var = SELF_DIR if wf.triggers_other_dags() else PROJECT_DIR
    other = PROJECT_DIR if dir_var is SELF_DIR else SELF_DIR

    header: dict[str, object] = {}
    env = doc.get("env")
    if env is None:
        header["env"] = [{dir_var: str(root)}]
    elif _env_holds(env, other):
        raise ProjectionError(
            f"refusing to project {source}\n"
            f"  its env: block states {other}, and this workflow needs {dir_var}\n"
            + (
                "  a workflow that triggers other workflows names its own"
                " directory DEVMAN_SELF_DIR (§11)\n"
                if dir_var is SELF_DIR
                else "  only a workflow that triggers other workflows names"
                " DEVMAN_SELF_DIR (§11)\n"
            )
            + f"  write:   - {dir_var}: {root}"
        )
    elif _env_holds(env, dir_var):
        stated = _env_value(env, dir_var)
        if stated != str(root):
            raise ProjectionError(
                f"refusing to project {source}\n"
                f"  its env: block states {dir_var}: {stated}\n"
                f"  this project is registered at {root}\n"
                "  a reserved name is the plane's to fill — remove the line, or"
                " correct it (§7.1)"
            )
    else:
        raise ProjectionError(
            f"refusing to project {source}\n"
            f"  it has a top-level env: block and states no {dir_var}\n"
            "  the header cannot add one without editing your document, and a"
            " workflow with no directory variable runs in a directory named"
            f" literally ${{{dir_var}}} (§7.2, §9.2)\n"
            f"  add this line to its env: block:   - {dir_var}: {root}"
        )

    # The header adds; it never overwrites (§11's cross-repo workflow states its
    # own). Decided from the parsed document, not from `grep '^working_dir:'`.
    if "working_dir" not in doc:
        header["working_dir"] = str(root)
    if "log_dir" not in doc:
        header["log_dir"] = str(root / ".devman" / ".runs" / "logs")

    # The source path goes into a COMMENT, so every line of it has to stay
    # commented. Measured by `test_every_supported_path_round_trips_through_the
    # _yaml[newline]`: a source path holding a newline put its second line at
    # column 0, and the generated file stopped being loadable YAML — the
    # renderer producing exactly the unloadable file it refuses in its input.
    display_source = str(source) if source_label is None else source_label
    where = "\n".join(f"#   {line}" for line in display_source.splitlines() or [""])
    banner = (
        "# devman: generated projection — do not edit.\n"
        "# Edit the source and re-enter the shell:\n"
        f"{where}\n"
    )
    block = yaml.safe_dump(
        header, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    # The body last, and unchanged. The guard's tail-equality test depends on
    # it, and §7.2 forbids the projection editing a workflow at all.
    return banner + block + wf.text


def _read_text(source: Path, text: str) -> Workflow:
    """`render()` on text the caller already holds — the unit tests' path."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Workflow(Path(source), text, None, f"not loadable as YAML: {exc}")
    if doc is not None and not isinstance(doc, dict):
        return Workflow(Path(source), text, None, "the document is not a mapping")
    return Workflow(Path(source), text, doc or {})


def _env_value(env: object, name: str) -> str | None:
    """What an `env:` block assigns to `name`. Dagu accepts a map or a list."""
    if isinstance(env, dict):
        return None if name not in env else _text(env[name])
    if isinstance(env, list):
        for item in env:
            if isinstance(item, dict) and name in item:
                return _text(item[name])
            if isinstance(item, str) and item.startswith(name + "="):
                return item.split("=", 1)[1]
    return None


def _text(value: object) -> str:
    return "" if value is None else str(value)


# ---------------------------------------------------------------------------
# the command


def main(args, reg) -> int:
    """Run one projection command from the Devman CLI."""

    from .reconcile import ReconcileError, compatibility_apply

    project_command = getattr(args, "project_command", "apply")
    try:
        if project_command == "apply":
            compatibility_apply(
                Path(args.root),
                policy_root=Path(args.policy_root),
                overlay_root=Path(args.overlay_root),
                registry=reg.root,
                state=reg.state,
                plan=args.plan,
                dagu=args.dagu,
            )
            return 0
        if project_command == "render":
            return render_main(args)
        if project_command == "inspect":
            return inspect_main(args)
    except (ProjectionError, ReconcileError, OSError, ValueError, KeyError) as exc:
        print(f"devman: {exc}", file=sys.stderr)
        return 1
    raise ValueError(f"unknown project command: {project_command}")


def render_main(args) -> int:
    """Render one project for Vendomat without publishing or executing tasks."""

    from devman_contract import ProjectManifest, digest_bytes

    from .reconcile import (
        ReconcileError,
        render_project,
        renderer_digest,
        resolve_policy,
        runtime_version,
    )

    try:
        root = Path(args.root).expanduser().resolve()
        policy_root = Path(args.policy_root).expanduser().resolve()
        overlay_root = Path(args.overlay_root).expanduser().resolve()
        manifest = ProjectManifest.from_root(root)
        policy = resolve_policy(manifest, policy_root)
        generation = _render_generation(
            args, policy.digest, renderer_digest, runtime_version, digest_bytes
        )
        bundle = render_project(
            root,
            policy_root=policy_root,
            overlay_root=overlay_root,
            generation=generation,
        )
        output = getattr(args, "output", None)
        if output:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.new")
            temporary.write_text(bundle.to_json())
            os.replace(temporary, target)
        else:
            print(bundle.to_json(), end="")
    except (ProjectionError, ReconcileError, OSError, ValueError, KeyError) as exc:
        print(f"devman: {exc}", file=sys.stderr)
        return 1
    return 0


def inspect_main(args) -> int:
    """Resolve one project and print its projection identities."""

    from devman_contract import ProjectManifest, digest_bytes

    from .reconcile import (
        ReconcileError,
        inspect_project,
        renderer_digest,
        resolve_policy,
        runtime_version,
    )

    try:
        root = Path(args.root).expanduser().resolve()
        policy_root = Path(args.policy_root).expanduser().resolve()
        overlay_root = Path(args.overlay_root).expanduser().resolve()
        manifest = ProjectManifest.from_root(root)
        policy = resolve_policy(manifest, policy_root)
        generation = _render_generation(
            args, policy.digest, renderer_digest, runtime_version, digest_bytes
        )
        inspection = inspect_project(
            root,
            policy_root=policy_root,
            overlay_root=overlay_root,
            generation=generation,
        )
        output = getattr(args, "output", None)
        text = inspection.to_json()
        if output:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.new")
            temporary.write_text(text)
            os.replace(temporary, target)
        else:
            print(text, end="")
    except (ProjectionError, ReconcileError, OSError, ValueError, KeyError) as exc:
        print(f"devman: {exc}", file=sys.stderr)
        return 1
    return 0


def _render_generation(args, policy_digest, renderer, runtime, digest):
    """Build one generation identity for render and inspect."""

    from devman_contract import PlaneGeneration

    return PlaneGeneration(
        generation=args.generation,
        devman_runtime=args.devman_runtime or runtime(),
        renderer_digest=renderer(),
        policy_digest=policy_digest,
        dagu_digest=args.dagu_digest or digest(b"dagu:unspecified"),
        toolchain_digest=args.toolchain_digest or digest(b"toolchain:unspecified"),
    )


def cli(argv: list[str] | None = None) -> int:
    """The narrow `devman-project` entry point used by the compatibility hook."""

    ap = argparse.ArgumentParser(
        prog="devman-project",
        description="Project one repository into the registry (§9.2).",
    )
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("apply", help="rebuild this repository's projection")
    add_arguments(p)
    p.add_argument("--registry", required=True, help="the registry root (§9.2)")
    p.add_argument("--state", required=True, help="the state root (§11 Stage 3)")
    args = ap.parse_args(argv)

    class _Reg:
        root = Path(args.registry)
        state = Path(args.state)

    args.project_command = args.command
    return main(args, _Reg())


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Arguments for the temporary compatibility publication path."""

    p.add_argument("--plan", required=True, help="the shell-entry policy identity")
    p.add_argument("--root", required=True, help="the repository root")
    p.add_argument("--policy-root", required=True, help="the Devman policy checkout")
    p.add_argument(
        "--overlay-root",
        default="~/.config/devman",
        help="the central project overlay root",
    )
    p.add_argument("--dagu", help="the dagu binary to validate with")


def add_render_arguments(p: argparse.ArgumentParser) -> None:
    """Arguments for the public machine-plane renderer boundary."""

    p.add_argument("--root", required=True, help="the repository root")
    p.add_argument("--policy-root", required=True, help="the Devman policy checkout")
    p.add_argument(
        "--overlay-root",
        default="~/.config/devman",
        help="the central project overlay root",
    )
    p.add_argument(
        "--generation", required=True, type=int, help="plane generation number"
    )
    p.add_argument(
        "--devman-runtime", help="runtime identity recorded in the generation"
    )
    p.add_argument("--dagu-digest", help="the packaged Dagu digest")
    p.add_argument("--toolchain-digest", help="the shared toolchain digest")
    p.add_argument("--output", help="write the bundle to this file instead of stdout")


def add_inspect_arguments(p: argparse.ArgumentParser) -> None:
    """Add the identity-only renderer boundary arguments."""

    add_render_arguments(p)


# ---------------------------------------------------------------------------
# §7.3's last layer, for triggers (009 P3-3)
#
# WHY THIS LAYER EXISTS. The group owns the trigger glob and the repository owns
# the task's file domain, and nothing reconciled them. `groups/format` maps
# `**/*.py`; this repository's `pyproject.toml` excludes `.scratch` from Ruff.
# Saving a file under `.scratch` therefore fired `format`, ran the task in full,
# and formatted nothing — 16 times in 252 fires, measured.
#
# The fix could not be "a repository excluding paths from its formatter must
# exclude them from the trigger", because a repository could not exclude
# anything: `groupTriggers` reads only `groups/<group>/triggers.toml`, and there
# was no local layer at all. Workflows resolved group -> group -> local;
# triggers resolved group -> group. This completes the asymmetry rather than
# inventing a mechanism.
#
# WHY IT IS READ HERE AND NOT IN NIX. Which files are in a working tree is a
# RUN-TIME fact — the same reason `.devman/workflows/` is applied here rather
# than at evaluation time. The watcher still reads only the registry entry, so
# there is still exactly one implementation of §7.3.
#
# WHOLE-FILE, PLUS AN IGNORE LIST, AND THE SECOND IS WHY THE FIRST IS NOT
# ENOUGH. §7.3 shadows whole files and this map does too — a `[map]` table
# replaces the group's outright. But whole-file replacement cannot express
# "everything the group says, except this directory", which is the case that
# forced the layer: to drop `.scratch` a repository would have to restate a map
# it does not own and then keep it in step. `ignore` says the narrowing
# directly, and a repository that wants both may state both.
LOCAL_TRIGGERS = "triggers.toml"


def local_triggers(root: Path) -> dict | None:
    """This repository's own trigger layer, or `None` if it ships none."""
    path = root / ".devman" / LOCAL_TRIGGERS
    if not path.is_file():
        return None
    try:
        raw = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProjectionError(
            f"refusing to project '{path}'\n"
            f"  {exc}\n"
            '  it is TOML: `ignore = ["<glob>"]`, and an optional [map] of'
            " <glob> = <workflow>"
        ) from exc
    unknown = sorted(set(raw) - {"ignore", "map"})
    if unknown:
        raise ProjectionError(
            f"refusing to project '{path}'\n"
            f"  it states {', '.join(unknown)}, and this file holds two keys\n"
            "  `ignore`, a list of globs this repository never fires on, and"
            " `map`, a table of <glob> = <workflow> replacing the group's (§8)"
        )
    ignore = raw.get("ignore", [])
    if not isinstance(ignore, list) or not all(isinstance(g, str) for g in ignore):
        raise ProjectionError(
            f"refusing to project '{path}'\n"
            "  `ignore` is a list of glob strings, matched against a path"
            " relative to this repository's root"
        )
    mapping = raw.get("map")
    if mapping is not None and not (
        isinstance(mapping, dict) and all(isinstance(v, str) for v in mapping.values())
    ):
        raise ProjectionError(
            f"refusing to project '{path}'\n"
            "  `[map]` is a table of <glob> = <workflow>, and a workflow is a"
            " name this repository projects (§7.3)"
        )
    return raw


def resolve_triggers(plan_triggers: object, root: Path) -> object:
    """The group layer, narrowed or replaced by this repository's own.

    The OUTCOME is what reaches the registry entry, exactly as §7.3's workflow
    resolution records its outcome. `source` says which layer decided, because
    "why does saving this file do nothing" is a question `doctor` has to be able
    to answer without reading two files in two places.
    """
    local = local_triggers(root)
    if local is None:
        return plan_triggers

    group = plan_triggers if isinstance(plan_triggers, dict) else {}
    mapping = local.get("map") or group.get("map") or {}
    if not mapping:
        # An `ignore` list with nothing to narrow fires nothing and hides
        # nothing. It is a repository preparing for a group it has not taken,
        # which is legal and worth saying nothing about.
        return None
    return {
        "group": group.get("group", "?") if local.get("map") is None else "(local)",
        "map": mapping,
        "ignore": local.get("ignore", []),
        "source": "local" if local.get("map") is not None else "group+local",
    }


# ---------------------------------------------------------------------------
# Output ownership — what a workflow writes, and under which tier (015)
#
# WHY THIS FILE EXISTS. §12 rule 3 used to refuse every unattended write to
# tracked source, and a flat refusal needs no declaration: nothing was allowed,
# so nothing had to say what it wrote. 015 amended the rule into three tiers —
# free, on a lane, and refused — and a tier is a CLAIM. This is where the claim
# is written down, so `doctor` can read it instead of a reviewer guessing.
#
# WHY IT IS A TOML FILE BESIDE `triggers.toml`, AND NOT A KEY IN THE WORKFLOW.
# The same measurement that put the trigger map here (A5), re-verified in 015:
#
#   * a top-level `writes:` key is rejected — `dagu validate` fails the document
#     with "decoding failed", exactly as it does for any unknown key;
#   * `tags:` IS accepted, and is useless for this — it is a label map with a
#     charset of `a-zA-Z0-9-_.`, so `devman:writes=lane` is refused on the `:`
#     and no glob containing `/` or `*` can be expressed at all.
#
# So the two homes a declaration could have had are closed, and this file takes
# the third — the one §8 already established for the trigger map.
#
# IT IS PER WORKFLOW, KEYED BY THE NAME THE PROJECT PROJECTS. A group ships the
# declaration for the workflows it ships, because the group wrote the steps and
# knows what they touch; a repository narrows or replaces it, exactly as §7.3
# resolves workflows and the local trigger layer resolves triggers.
#
# WHAT IT CANNOT DO, STATED PLAINLY. It cannot prove a workflow writes what it
# says, or that a workflow which declares nothing writes nothing. The amendment
# is weaker than the rule it replaced and this file does not close that gap —
# it makes the claim legible and checkable, which is the difference between a
# reviewer reading a shell script and `doctor` reading a set.
LOCAL_WRITES = "writes.toml"

# Tier A of §12 rule 3 as amended: agent surface. A declaration of `tier =
# "free"` over a path outside this set is the finding `check_writes` exists to
# make. The list is a PREFIX set on purpose — membership is decidable by reading
# the glob, with no filesystem access and no guessing (§15.7).
FREE_PREFIXES = (".agents/", "docs/", ".devman/", ".loci/", ".gitman/")
# `insitu` is `format`'s bounded exception, kept exactly as narrow as the rule
# it survives from: its own opt-in group, a content hash, and a fixpoint. It is
# an idempotent normalisation of a file the trigger already watched — not new
# content. A declaration that claims it states the glob it normalises.
TIERS = ("free", "lane", "insitu")


def free_path(glob: str) -> bool:
    """Is this declared glob inside tier A's agent surface?"""
    return any(glob.startswith(p) for p in FREE_PREFIXES)


def _validate_writes(raw: dict, where: str) -> dict:
    """Refuse a malformed declaration at projection time, not at audit time.

    A tier is a claim, and a claim nobody can parse is worse than no claim:
    `doctor` would report it as absent and the workflow would look compliant.
    """
    for name, decl in raw.items():
        if not isinstance(decl, dict):
            raise ProjectionError(
                f"refusing to project '{where}'\n"
                f"  [{name}] is a table: `tier` and `paths`"
            )
        tier = decl.get("tier")
        if tier not in TIERS:
            raise ProjectionError(
                f"refusing to project '{where}'\n"
                f"  [{name}] states tier {tier!r}, and a tier is one of:"
                f" {', '.join(TIERS)}\n"
                "  there is no `trunk` tier — an unattended write to trunk is"
                " refused outright (§12 rule 3)"
            )
        paths = decl.get("paths")
        if (
            not isinstance(paths, list)
            or not paths
            or not all(isinstance(g, str) for g in paths)
        ):
            raise ProjectionError(
                f"refusing to project '{where}'\n"
                f"  [{name}] states no `paths`, and a declaration without one"
                " claims a tier for nothing\n"
                "  `paths` is a non-empty list of globs relative to the"
                " repository root"
            )
        unknown = sorted(set(decl) - {"tier", "paths", "lane"})
        if unknown:
            raise ProjectionError(
                f"refusing to project '{where}'\n"
                f"  [{name}] states {', '.join(unknown)}; this table holds"
                " `tier`, `paths` and an optional `lane`"
            )
    return raw


def local_writes(root: Path) -> dict | None:
    """This repository's own ownership layer, or `None` if it ships none."""
    path = root / ".devman" / LOCAL_WRITES
    if not path.is_file():
        return None
    try:
        raw = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProjectionError(
            f"refusing to project '{path}'\n"
            f"  {exc}\n"
            '  it is TOML: one table per workflow, `tier = "free"|"lane"` and'
            " `paths = [...]`"
        ) from exc
    return _validate_writes(raw, str(path))


def resolve_writes(plan_writes: object, root: Path) -> object:
    """The group layer, per workflow, overridden by this repository's own.

    UNLIKE §7.3 AND THE TRIGGER MAP, THIS MERGES PER WORKFLOW RATHER THAN
    WHOLE-FILE. Those two replace outright because a partial trigger map or a
    half-shadowed workflow is hard to predict from either file alone. Here the
    unit is already a workflow: a repository that overrides `[format]` says
    nothing about `[regen]`, and inheriting the group's declaration for a
    workflow it did not mention is the same inheritance §7.3 gives the workflow
    itself. A repository silently losing a group's declaration would be the
    worse surprise, because the audit would then report nothing.
    """
    group = plan_writes if isinstance(plan_writes, dict) else {}
    local = local_writes(root)
    if local is None:
        return group or None
    merged = dict(group)
    merged.update(local)
    return merged or None
