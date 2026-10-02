"""The devman command (CONCEPT.md §10).

    devman run <workflow>      trigger a workflow in the current project
    devman show <workflow>     print the resolved file, to start an override
    devman doctor              diagnose the plane
    devman watch               the watcher's entry point — systemd runs this
    devman project apply       the projection — the devenv module runs this

**Three commands and TWO that are machinery.** §10's list is the developer's
surface and it is closed: there is no `list`, no `status`, no `register` and no
`unregister`, because registration is automatic and has no manual path (§5.2),
and the rest is what `doctor` reports. `watch` is the fourth, and it is not a
fourth *command* in that sense — it is the watcher service's entry point (§8),
run by systemd rather than by a person, and it exists here rather than as a
shell script in the machine module so that exactly one implementation reads the
registry.

`project` joined it at stage 3 of project 009, in the same frame and for the
same reason. The projection used to be shell inside `modules/devenv.nix`, which
duplicated four decisions this package already made correctly from a parsed
document — and each duplicate was a finding (P1-1, P1-5, P2-1, P2-2). A
The compatibility `project apply` command remains a narrow publication
boundary. A repository's shell entry invokes the packaged `devman` renderer
directly, so the guard and the machine-plane commands use the same resolver.
`doctor` and the unit tests exercise that same package surface. No person types
the compatibility command.

**The name.** `devman 0.2.0` owned this name and shipped its own `doctor`,
`init`, `up`, `down`, `switch`, `bootstrap` and `index` (§3.3). It was removed
from the profile at stage 1 and the removal was activated, so the name is free
(`STAGE_1_LOG.md`, S11).

**Where it ships from.** `nixosModules.default` only. §3.1's second rule says
what the two interfaces share must be text, and a Python CLI is not text;
`nix/dagu.nix` is the single measured exception. Installing it from the devenv
module as well would also put two `devman` binaries on one PATH, resolved by
profile order, which is the hazard §3.3 exists to record. A devenv shell
inherits the machine profile's PATH, so a machine-side install reaches every
repository shell on that machine anyway.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import devman_link
from devman_contract import ContractError, ProjectManifest

from . import agent, central, project, run, show, watch
from .registry import (
    DEFAULT_DAGU_HOME,
    DEFAULT_REGISTRY,
    DEFAULT_STATE,
    Registry,
    RegistryError,
    report,
)

# `doctor` IS DELIBERATELY NOT IMPORTED HERE (012, Part B candidate 2).
#
# It is the heaviest module in the package and the only one no automatic caller
# ever reaches. `doctor` needs `urllib.request` to poll the Dagu server and
# `concurrent.futures` to validate 171 projected files in parallel; both are
# right for what it does, and both are paid by every OTHER command as soon as
# this line imports it.
#
# Measured on this machine, hyperfine, 30 runs, `python -c 'import …'` against a
# 25 ms interpreter floor:
#
#   devman.registry     53 ms      devman.watch    66 ms
#   devman.workflow     68 ms      devman.run      78 ms
#   devman.project      84 ms      devman.doctor  127 ms
#   devman.cli (all five)                         133 ms
#   the same without doctor                        81 ms
#
# **52 ms of every devman process was doctor, and the dispatch path starts two
# of them.** Deferring the other four saves nothing measurable — 82 ms against
# 81 — because `project` and `run` already pull the registry, the workflow
# reader and yaml, which the parser needs anyway. So exactly one module moves,
# and it moves into the one branch that uses it.
#
# THE COST, STATED. `devman --help` no longer imports `doctor`, so a broken
# import in that file reaches a person only when they run `devman doctor`.
# `tests/unit/test_cli.py::test_every_subcommand_module_imports` is what keeps
# that from being silent.


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="devman", description=__doc__.splitlines()[0])
    # Global, because the NixOS module wraps this binary with them when a
    # machine moves either directory. They are flags rather than `DEVMAN_*`
    # variables on purpose: Dagu passes every `DEVMAN_*` in the enqueueing
    # process's environment through to the run, and §7.1's shared contract is
    # closed.
    ap.add_argument(
        "--registry", default=DEFAULT_REGISTRY, help="the registry root (§9.2)"
    )
    ap.add_argument(
        "--state",
        default=DEFAULT_STATE,
        help="the state root — metadata.json and kept triggers/writes copies (§11 Stage 3)",
    )
    ap.add_argument(
        "--dagu-home", default=DEFAULT_DAGU_HOME, help="the plane's DAGU_HOME (S2)"
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="trigger a workflow in the current project")
    p_run.add_argument("workflow")
    p_run.add_argument("params", nargs="*", metavar="NAME=VALUE")
    p_run.add_argument(
        "-p", "--project", help="name a project instead of using the current directory"
    )
    p_run.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the trigger and enqueue nothing",
    )

    p_show = sub.add_parser("show", help="print the resolved workflow file")
    p_show.add_argument("workflow", nargs="?")
    p_show.add_argument(
        "-p", "--project", help="name a project instead of using the current directory"
    )
    p_show.add_argument(
        "--path", action="store_true", help="print the resolved path, not the file"
    )

    p_doc = sub.add_parser("doctor", help="diagnose the plane")
    p_doc.add_argument(
        "--prune",
        action="store_true",
        help="remove stale registry entries (§10 check 5)",
    )

    p_central = sub.add_parser(
        "central-verify",
        help="verify `~/.config/devman`'s live symlinks (project 041)",
    )
    p_central.add_argument(
        "--phase",
        choices=("pre", "post"),
        help=(
            "'pre' runs C1+C2+C4 — the content is wrong, so a land must"
            " block on these. 'post' runs C3 and C5 — neither must ever"
            " block a land: C3's content has not reached safety yet and"
            " landing is its cure, so blocking would refuse the one"
            " operation that fixes what it detects (DECISIONS.md D3); C5's"
            " empty surface is not caused by a lane and not cured by"
            " landing one, so blocking an unrelated land over it would only"
            " hold every future land hostage to an onboarding that needs a"
            " separate fix. Omit to run all five assertions."
        ),
    )
    p_central.add_argument(
        "--overlay",
        default=str(central.DEFAULT_CENTRAL),
        help="the central configuration root",
    )
    p_central.add_argument(
        "--fleet-root",
        default=str(central.DEFAULT_FLEET),
        help="the fleet root to walk for live symlinks into the overlay",
    )
    p_central.add_argument(
        "--json",
        action="store_true",
        help="print one JSON object instead of plain text",
    )

    p_watch = sub.add_parser("watch", help="the watcher service's entry point (§8)")
    p_watch.add_argument(
        "--dispatch", action="store_true", help="handle one batch of events on stdin"
    )
    p_watch.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the watchexec command and run nothing",
    )
    p_watch.add_argument(
        "--watchexec-arg",
        action="append",
        default=[],
        metavar="ARG",
        help="pass one more argument to watchexec",
    )
    p_watch.add_argument(
        "--poll-seconds",
        type=float,
        default=watch.POLL_SECONDS,
        metavar="SECONDS",
        help="how often to re-read the registry for a changed watch set (§8, S16)",
    )

    # THE FOURTH COMMAND, AND §10 SAID THERE WERE THREE (022).
    #
    # The other three are ABOUT the plane: a developer types them and reads the
    # answer. This one runs INSIDE it — it is the step of `groups/agent/`'s
    # workflow, translating one admitted run into one Agentman invocation. The
    # charter amendment says why it is a command rather than a devenv task: the
    # translation is execution-plane work, so the plane owns it, and law 7 says
    # core logic is Python rather than shell.
    p_agent = sub.add_parser(
        "agent", help="run one Agentman capsule for this admitted run (§10, 022)"
    )
    agent.add_arguments(p_agent)

    p_project = sub.add_parser(
        "project", help="the projection — machinery, run by the devenv module (§9.2)"
    )
    p_project_sub = p_project.add_subparsers(dest="project_command", required=True)
    project.add_arguments(
        p_project_sub.add_parser("apply", help="rebuild this repository's projection")
    )
    project.add_render_arguments(
        p_project_sub.add_parser(
            "render", help="render one project for a machine-plane generation"
        )
    )
    project.add_inspect_arguments(
        p_project_sub.add_parser(
            "inspect", help="inspect one project for a machine-plane generation"
        )
    )

    p_link = sub.add_parser("link", help="reconcile this repository's links (§5)")
    p_link_sub = p_link.add_subparsers(dest="link_command", required=True)
    for name in ("reconcile", "status"):
        p_link_one = p_link_sub.add_parser(name)
        p_link_one.add_argument(
            "--project", help="project identity; the manifest is authoritative"
        )
        p_link_one.add_argument("--root", default=".", help="repository root")
        p_link_one.add_argument("--overlay", help="config repository root")
        p_link_one.add_argument(
            "--json",
            action="store_true",
            help="print one JSON object per declaration, instead of plain text",
        )
        if name == "status":
            p_link_one.add_argument(
                "--all",
                action="store_true",
                help="report every manifest-backed project",
            )
            p_link_one.add_argument(
                "--projects-root",
                action="append",
                default=[],
                metavar="DIR",
                help="explicit inventory root for --all; repeat for more roots",
            )

    return ap


def handler(command: str):
    """The function that runs one subcommand.

    `doctor` is imported HERE rather than at the top of the file, for the reason
    the import block states. The other four are already imported, so this is a
    lookup for them and an import for one.
    """
    if command == "doctor":
        from . import doctor

        return doctor.main
    if command == "link":
        # The public identity boundary, not a module's `main`. It resolves the
        # identity and then calls the independent adapter (038 Stage 16).
        return _link_command
    if command == "central-verify":
        return _central_verify
    return {
        "agent": agent.main,
        "run": run.main,
        "show": show.main,
        "watch": watch.main,
        "project": project.main,
    }[command]


def _manifest_candidates(
    projects_roots: list[str],
) -> tuple[dict[str, Path], list[tuple[Path, str]]]:
    """Find direct child checkouts with manifests under explicit roots."""
    if not projects_roots:
        raise RegistryError(
            "link status --all needs an explicit --projects-root"
            "\n  pass the directory that contains the project checkouts"
        )

    candidates: dict[str, Path] = {}
    seen_checkouts: set[Path] = set()
    owners: dict[str, Path] = {}
    blocked: set[str] = set()
    errors: list[tuple[Path, str]] = []
    for raw_root in projects_roots:
        inventory = Path(raw_root).expanduser().resolve()
        if not inventory.is_dir():
            raise RegistryError(
                f"cannot sweep project manifests under {inventory}"
                f"\n  it is not a directory"
            )
        try:
            children = sorted(inventory.iterdir())
        except OSError as exc:
            raise RegistryError(
                f"cannot sweep project manifests under {inventory}\n  {exc}"
            ) from exc
        for child in children:
            if not child.is_dir():
                continue
            checkout = child.resolve()
            if checkout in seen_checkouts:
                continue
            seen_checkouts.add(checkout)
            manifest_path = checkout / ".devman" / "project.toml"
            if not manifest_path.is_file():
                continue
            try:
                manifest = ProjectManifest.from_file(manifest_path)
            except (ContractError, UnicodeError) as exc:
                errors.append((checkout, f"cannot read its manifest\n  {exc}"))
                continue
            if manifest.project in blocked:
                errors.append(
                    (
                        checkout,
                        f"duplicate manifest identity {manifest.project!r}"
                        f"\n  also declared by {owners[manifest.project]}",
                    )
                )
                continue
            previous = owners.get(manifest.project)
            if previous is not None and previous != checkout:
                candidates.pop(manifest.project, None)
                errors.append(
                    (
                        checkout,
                        f"duplicate manifest identity {manifest.project!r}"
                        f"\n  also declared by {previous}",
                    )
                )
                errors.append(
                    (
                        previous,
                        f"duplicate manifest identity {manifest.project!r}"
                        f"\n  also declared by {checkout}",
                    )
                )
                blocked.add(manifest.project)
                continue
            owners[manifest.project] = checkout
            candidates[manifest.project] = checkout

    if not candidates and not errors:
        raise RegistryError(
            "the project manifest inventory is empty"
            "\n  each direct child checkout must contain .devman/project.toml"
        )
    return candidates, errors


def _link_all(args) -> int:
    """Report every manifest-backed project, and keep going past a refusal."""
    candidates, errors = _manifest_candidates(args.projects_root)
    worst = 0
    for root, detail in errors:
        report(
            RegistryError(
                f"cannot inspect manifest-backed project at {root}\n  {detail}"
            )
        )
        worst = 1

    overlay = args.overlay or devman_link.DEFAULT_OVERLAY
    as_json = getattr(args, "json", False)
    rows: list[dict[str, object]] = []
    for _project, root in sorted(candidates.items()):
        try:
            outcome = devman_link.run(
                "status", root=root, overlay=overlay, project=None
            )
        except devman_link.LinkAdapterError as exc:
            report(exc)
            worst = max(worst, 1)
            continue
        if as_json:
            rows.extend(devman_link.format_results_json(outcome))
        else:
            for line in devman_link.format_results(outcome):
                print(line)
        worst = max(worst, outcome.exit_code)
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    return worst


def _link_reconcile_with_linkman(args) -> int:
    """`DEVMAN_LINK_ENGINE=linkman`: reconcile through concept §14 (Lane 7).

    `devman.linking` imports `linkman`, which needs `pydantic` — present in
    the dev venv's `cutover` extra, absent from the Nix-shipped CLI's closure
    until Lane 9 rewires `nix/link-adapter.nix`. The import stays inside this
    function so the flag defaulting off never pays for it, and the shipped
    binary never needs it to run at all.
    """
    from . import linking

    try:
        result = linking.reconcile_with_linkman(
            args.root,
            overlay=args.overlay or devman_link.DEFAULT_OVERLAY,
            project=args.project,
        )
    except linking.LinkingError as exc:
        report(exc)
        return 1

    apply_result = result.apply_result
    if getattr(args, "json", False):
        print(
            json.dumps(apply_result.model_dump(mode="json"), indent=2, sort_keys=True)
        )
    else:
        for applied in apply_result.applied:
            actions = ",".join(applied.actions)
            print(f"{actions:20} {applied.link_rel}")
        for refusal in apply_result.refused:
            print(f"refuse               {refusal.link_rel}")
        for failure in apply_result.failed:
            print(f"fail                 {failure.link_rel}: {failure.message}")
    if apply_result.failed:
        return 13
    if apply_result.refused:
        return 11
    return 0


def _central_verify(args, _reg: Registry) -> int:
    """`devman central-verify` — project 041's predicate over `~/.config/devman`.

    Exit `0` ok, `1` a finding, `2` infra/config (the overlay is missing, or
    a tool an assertion needs — `nix-instantiate`, `git` — is not on PATH).

    **The phase split is DECISIONS.md D3, and it is load-bearing, not
    cosmetic.** `--phase pre` runs C1 (central Nix evaluates), C2 (every live
    view's target exists) and C4 (every tracked `links.yaml` pairs with a
    `devenv.local.nix`) — these are *the content is wrong*, and landing wrong
    content is worse than not landing, so a `[land.pre_hook]` blocks on them.
    `--phase post` runs C3 and C5. C3 (every live view's target is reachable
    from trunk) is *the content has not reached safety yet*, and **landing is
    its cure** — it must never run in the pre phase, because blocking a land
    on a condition only a land can fix is a deadlock. C5 (every live view's
    target holds content git could ever track, not an empty directory tree)
    is a different, lower-severity case: it is not caused by a lane and not
    cured by landing one — usually it is a project whose onboarding never
    finished — so blocking an unrelated land over it would hold every future
    land hostage to a gap that landing cannot close. It runs in `post`
    because `post` is the phase that can never block, which is the property
    both assertions need, for different reasons. With no `--phase`, all five
    run, for a developer checking the overlay by hand.

    **Reads nothing from stdin.** A gitman land hook pipes a JSON event on
    stdin and sets `GITMAN_HOOK_PHASE` in the environment. This predicate
    answers from the filesystem and `git`'s read-only plumbing alone, so it
    never touches stdin — it neither blocks waiting on an empty pipe nor
    chokes on a populated one.
    """
    overlay = Path(args.overlay).expanduser()
    fleet = Path(args.fleet_root).expanduser()
    as_json = getattr(args, "json", False)

    if not overlay.is_dir():
        print(f"devman central-verify: no overlay at {overlay}", file=sys.stderr)
        return 2

    phase = args.phase
    run_pre = phase in (None, "pre")
    run_post = phase in (None, "post")

    try:
        views = central.reverse_index(fleet=fleet, central=overlay)
        results: dict[str, list[str]] = {}
        if run_pre:
            results["C1"] = central.check_c1_nix_eval(overlay)
            results["C2"] = [
                central.format_view(v) for v in central.check_c2_missing(views)
            ]
            results["C4"] = central.check_c4_pairing(overlay)

        lane_only: list[central.View] = []
        if run_post:
            trunk = central.trunk_name(overlay)
            lane_only = central.check_c3_lane_only(views, overlay, trunk)
            results["C3"] = [central.format_view(v, trunk=trunk) for v in lane_only]
            empty_surface = central.check_c5_empty_surface(views, overlay)
            results["C5"] = [
                central.format_empty_view(v, central=overlay) for v in empty_surface
            ]
    except central.InfraError as exc:
        print(f"devman central-verify: {exc}", file=sys.stderr)
        return 2

    findings = sum(len(lines) for lines in results.values())

    if as_json:
        print(
            json.dumps({"phase": phase, "findings": results}, indent=2, sort_keys=True)
        )
    else:
        for assertion_id, lines in results.items():
            for line in lines:
                print(f"!! {assertion_id}  {line}")
        if lane_only:
            print(central.exposure_message(lane_only, overlay))
        if not findings:
            print(f"devman central-verify: ok ({phase or 'pre+post'})")

    return 1 if findings else 0


def _link_command(args, _reg: Registry) -> int:
    """The public link boundary — identity first, then the independent adapter.

    The adapter is `devman_link`, its own importable and packageable component
    (038 Stage 16). The normal path does not enter `devman.link`, and it reads
    no compatibility registry entry and no active workflow generation.

    `--all` is the one exception, and it scans explicit project-inventory roots
    for the manifests that now state registration. It asks the same adapter
    about every manifest-backed checkout, so there is one identity source and
    one reconciler.
    """
    if getattr(args, "link_command", "") == "status" and getattr(args, "all", False):
        if args.project is not None:
            raise RegistryError(
                "link status --all and --project are mutually exclusive"
            )
        return _link_all(args)

    if (
        args.link_command == "reconcile"
        and os.environ.get("DEVMAN_LINK_ENGINE") == "linkman"
    ):
        return _link_reconcile_with_linkman(args)

    root = args.root
    outcome = devman_link.run(
        args.link_command,
        root=root,
        overlay=args.overlay or devman_link.DEFAULT_OVERLAY,
        project=args.project,
    )
    if getattr(args, "json", False):
        print(
            json.dumps(
                devman_link.format_results_json(outcome), indent=2, sort_keys=True
            )
        )
    else:
        for line in devman_link.format_results(outcome):
            print(line)
    return outcome.exit_code


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    reg = Registry(args.registry, args.state)
    try:
        return handler(args.command)(args, reg)
    except (RegistryError, devman_link.LinkAdapterError) as exc:
        report(exc)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
