"""The projection (CONCEPT.md §9.2) — the producer, in Python.

    <registry>/projects/<project>/metadata.json
    <registry>/projects/<project>/workflows/<workflow>.yaml   the generated file
    <registry>/dags/<project>.<workflow>.yaml   -> the line above

**This used to be shell inside `modules/devenv.nix`, and four of project 009's
findings were one consequence of that.** The module decided the directory
variable with `grep -q 'DEVMAN_SELF_DIR'`, decided whether to add an `env:`
block with `grep -q '^env:'`, built JSON with `@PATH@` substitution, and
validated no identity at all. Meanwhile this package already answered every one
of those questions correctly, from a parsed document:

    is this a cross-repository parent?      Workflow.triggers_other_dags()
    does an `env:` block define a name?     workflow._env_holds()
    is this name legal?                     registry.identity_fault()

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
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .registry import DAG_SEPARATOR, LEGACY_DAG_SEPARATOR, identity_fault
from .workflow import PROJECT_DIR, SELF_DIR, Workflow, _env_holds

# The registry entry's schema. SCHEMA 4 changes what `plan` means: it was the
# projection script's store path, and it is now the store path of the plan file
# holding everything Nix derived — the groups, the resolved workflows, the
# triggers, and the renderer's own store path.
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
        f'  "triggers": {json.dumps(triggers, sort_keys=True)}\n'
        "}\n"
    )


# ---------------------------------------------------------------------------
# the renderer


def render(source: Path, root: Path, *, text: str | None = None) -> str:
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
    where = "\n".join(f"#   {line}" for line in str(source).splitlines() or [""])
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
# publication


@dataclass
class Plan:
    """Everything Nix derived, read from the plan file (§7.3's outcome).

    One `writeText` holds all of it, so the plan's store path is a hash of all
    of it. Any change to any derived fact changes that path, which is what makes
    the guard's `plan` comparison imply that every derived field is unchanged.
    """

    path: str
    project: str
    groups: list[str]
    workflows: dict[str, dict]
    triggers: object
    renderer: str

    @classmethod
    def read(cls, path: str | os.PathLike[str]) -> Plan:
        raw = json.loads(Path(path).read_text())
        return cls(
            path=str(path),
            project=raw["project"],
            groups=raw.get("groups", []),
            workflows=raw.get("workflows", {}),
            triggers=raw.get("triggers"),
            renderer=raw.get("renderer", ""),
        )


def apply(
    plan: Plan,
    root: Path,
    registry: Path,
    local: list[str],
    *,
    dagu: str | None = None,
) -> None:
    """Rebuild this project's whole projection, then record it.

    Order of operations per workflow (§3.5 of the refactor guide):

      1. validate the project and the workflow identity, BEFORE any path is
         constructed. A name holding `/` or `..` selects a registry subpath
         (009 P1-5).
      2. render every workflow, and validate every one whose bytes changed,
         inside this project's own registry entry
      3. on any failure, refuse — naming the source and quoting Dagu's message.
         **Publish nothing**, which means the previous projection stays exactly
         as it was rather than being swept away by a run that then refused.
      4. only then sweep, `os.replace` each file into place, and write the
         `dags/` links

    **This is P2-2's better fix.** Validating at enqueue moves the refusal to
    whoever triggers the workflow next; validating here moves it to the one
    person who can fix it — the author, at shell entry — and it means every
    runnable link is known valid.
    """
    fault = identity_fault("project", plan.project)
    if fault:
        raise ProjectionError(f"refusing to project '{plan.project}'\n  {fault}")

    entry = registry / "projects" / plan.project
    workflows_dir = entry / "workflows"
    dags = registry / "dags"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    dags.mkdir(parents=True, exist_ok=True)

    # §9.2's run-state layout, repo-side. Dagu creates `log_dir` itself, but
    # `artifacts/` and `reports/` have no other owner and a step that writes a
    # report should not have to create the tree first.
    for name in ("logs", "artifacts", "reports"):
        (root / ".devman" / ".runs" / name).mkdir(parents=True, exist_ok=True)

    sources = _sources(plan, root, local)
    for name in sources:
        fault = identity_fault("workflow", name)
        if fault:
            raise ProjectionError(
                f"refusing to project '{name}' in '{plan.project}'\n  {fault}"
            )
        if DAG_SEPARATOR in name:
            raise ProjectionError(
                f"refusing to project '{name}.yaml' in '{plan.project}'\n"
                f"  a workflow name may not hold a '{DAG_SEPARATOR}'\n"
                f"  a DAG name is <project>{DAG_SEPARATOR}<workflow>, and the"
                " last separator is what makes it injective (§9.2)"
            )

    # WHAT IS ALREADY PUBLISHED, READ BEFORE THE SWEEP REMOVES IT.
    #
    # `dagu validate` is a fork, measured at 71 ms per workflow — 960 ms for
    # this repository's ten, against 250 ms for the same projection with
    # validation stubbed out (`STAGE_9_LOG.md` S-3). That is worth paying when
    # bytes change and not worth paying when they do not, so a file whose
    # rendered bytes are identical to the ones already published is republished
    # without a second validation. It passed when it was written.
    #
    # THE ONE THING THAT INVALIDATES THAT ARGUMENT IS A NEW VALIDATOR, so the
    # recorded `plan` is what decides. It holds the renderer's store path, and
    # the renderer wraps the Dagu that validates — so a new Dagu, a new
    # renderer, or any other derived change gives a new plan path and every file
    # is validated again. Unchanged plan plus unchanged bytes is the only case
    # that skips, and in that case nothing about the file or the validator has
    # moved.
    published = _published(workflows_dir)
    revalidate = _recorded_plan(entry) != plan.path
    binary = dagu or shutil.which("dagu") or "dagu"

    # RENDER AND VALIDATE EVERYTHING BEFORE PUBLISHING ANYTHING.
    #
    # "Publish nothing" has to mean the whole projection, not the one file that
    # failed. Measured while writing this stage: with the sweep first, adding an
    # `env:` block to ONE override refused correctly — and left the repository
    # with none of its ten workflows published, because the sweep had already
    # removed them. A repository whose author makes a typo would lose its
    # nightly `maintain` until they noticed.
    #
    # So the registry is untouched until every file has rendered and every
    # changed file has validated. A refusal now leaves the previous projection
    # exactly as it was: stale, and stated to be stale by the refusal.
    rendered: dict[str, str] = {}
    for name, source in sorted(sources.items()):
        rendered[name] = render(source, root)

    # A DIRECTORY, and the file inside it keeps the workflow's own base name.
    # Dagu derives the DAG name from that base name (S1), so validating
    # `<workflows>/.validate` refused every file with "DAG name is required" —
    # the validator reporting the temporary file's name rather than anything
    # about the workflow. The directory is a dotfile, so the sweep's `*.yaml`
    # glob does not see it.
    staging = workflows_dir / ".validate"
    try:
        staging.mkdir(exist_ok=True)
        for name, text in rendered.items():
            if not (revalidate or published.get(name) != text):
                continue
            checked = staging / f"{name}.yaml"
            checked.write_text(text)
            _validate(binary, checked, sources[name])
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    _sweep(plan.project, workflows_dir, dags)

    for name, text in rendered.items():
        tmp = workflows_dir / f".{name}.yaml.new"
        tmp.write_text(text)
        os.replace(tmp, workflows_dir / f"{name}.yaml")
        link = dags / f"{plan.project}{DAG_SEPARATOR}{name}.yaml"
        _relink(link, f"../projects/{plan.project}/workflows/{name}.yaml")

    # Last, and atomically, exactly as the shell wrote it last: an interrupted
    # projection leaves an entry that does not match and is retried on the next
    # shell entry (§9.3). Since it can no longer be half-written, `projects()`
    # no longer has to treat a parse failure as a normal state — see stage 4.
    text = entry_text(
        project=plan.project,
        root=root,
        groups=plan.groups,
        plan=plan.path,
        local=local,
        workflows=plan.workflows,
        triggers=plan.triggers,
    )
    tmp = entry / ".metadata.json.new"
    tmp.write_text(text)
    os.replace(tmp, entry / "metadata.json")


def _published(workflows_dir: Path) -> dict[str, str]:
    """The bytes already published, by workflow name."""
    out = {}
    for path in workflows_dir.glob("*.yaml"):
        try:
            out[path.stem] = path.read_text()
        except OSError:
            continue
    return out


def _recorded_plan(entry: Path) -> str | None:
    """The `plan` the last projection recorded, or `None` if there is none."""
    try:
        return json.loads((entry / "metadata.json").read_text()).get("plan")
    except (OSError, ValueError):
        return None


def _sources(plan: Plan, root: Path, local: list[str]) -> dict[str, Path]:
    """`<workflow> -> the file that won §7.3`, group files then local overrides.

    The repository's own `.devman/workflows/` is the last layer and shadows
    every group, whole-file.
    """
    out = {n: Path(w["source"]) for n, w in plan.workflows.items()}
    for name in local:
        out[name] = root / ".devman" / "workflows" / f"{name}.yaml"
    return out


def _sweep(project: str, workflows_dir: Path, dags: Path) -> None:
    """The registry is derived, so the projection is rebuilt rather than patched.

    A `dags/` link is removed only when it still points at this project's own
    file, because the legacy shape is ambiguous when one project name is a
    prefix of another and the link target is not.

    BOTH SHAPES ARE SWEPT, AND THE SECOND IS THE MIGRATION (S-12). Sweeping only
    the current shape would leave `dags/<project>-<workflow>.yaml` pointing at a
    live file — a second DAG name for one workflow, which `dagu ls` shows and a
    stale schedule still fires. Drop `-` when `doctor` reports no unmigrated
    workflow.
    """
    for old in sorted(workflows_dir.glob("*.yaml")):
        stem = old.stem
        for sep in (DAG_SEPARATOR, LEGACY_DAG_SEPARATOR):
            link = dags / f"{project}{sep}{stem}.yaml"
            if link.is_symlink() and os.readlink(link) == (
                f"../projects/{project}/workflows/{stem}.yaml"
            ):
                link.unlink()
        old.unlink()


def _relink(link: Path, target: str) -> None:
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def _validate(binary: str, rendered: Path, source: Path) -> None:
    """`dagu validate` on the rendered bytes, before anything can run them.

    One fork per projected workflow, on the guarded path only — the hook decides
    without forking whether this runs at all. The cost is measured in
    `STAGE_9_LOG.md` S-3.
    """
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
        f"  dagu refuses the file this renders:\n"
        + "\n".join(f"    {line}" for line in message.splitlines())
        + "\n  nothing was published; fix the source and enter the shell again"
    )


# ---------------------------------------------------------------------------
# the command
#
# §10's list of three commands is closed and `project` does not join it, for the
# same reason `watch` did not: it is machinery. The projection script runs it at
# shell entry, and no person ever types it.


def main(args, reg) -> int:
    try:
        plan = Plan.read(args.plan)
        apply(
            plan,
            Path(args.root),
            reg.root,
            list(args.local),
            dagu=getattr(args, "dagu", None),
        )
    except ProjectionError as exc:
        print(f"devman: {exc}", file=sys.stderr)
        return 1
    return 0


def cli(argv: list[str] | None = None) -> int:
    """`devman-project` — the narrow entry point the devenv module calls.

    The devenv module cannot call `devman` from PATH. A PATH lookup is a
    run-time fact, so the module could not put the renderer's identity into
    `planFile`, so the guard could not observe it — and upgrading the machine's
    `devman` would change the rendering rules while every repository kept a
    projection produced by the old renderer, with the entry still matching and
    nothing re-projecting. That is `STAGE_7_LOG.md` S-5a again, one layer down.

    So this ships as its own derivation, built under the consuming repository's
    nixpkgs (`nix/renderer.nix`), and its store path is inside `planFile`.
    """
    ap = argparse.ArgumentParser(
        prog="devman-project",
        description="Project one repository into the registry (§9.2).",
    )
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("apply", help="rebuild this repository's projection")
    add_arguments(p)
    p.add_argument("--registry", required=True, help="the registry root (§9.2)")
    args = ap.parse_args(argv)

    class _Reg:
        root = Path(args.registry)

    return main(args, _Reg())


def add_arguments(p: argparse.ArgumentParser) -> None:
    """The arguments `devman project apply` and `devman-project apply` share.

    `--root` and `--local` stay arguments rather than moving into `planFile`,
    because both are run-time facts: where this checkout sits, and which files
    are in its `.devman/workflows/` right now. Everything Nix knows is in the
    plan.
    """
    p.add_argument("--plan", required=True, help="the plan file Nix wrote")
    p.add_argument("--root", required=True, help="this repository's root")
    p.add_argument(
        "--local",
        action="append",
        default=[],
        metavar="NAME",
        help="one workflow name from .devman/workflows/, in glob order",
    )
    p.add_argument("--dagu", help="the dagu binary to validate with")
