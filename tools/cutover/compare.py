"""Phase A's dry-run comparison: does the new `links.yaml` agree with the old
Nix declarations, before Linkman ever touches a live symlink?

For each live, manifest-backed project, `devman_link.run("status", ...)`
resolves the original central `devenv.local.nix`, and `linkman config --json`
resolves the `links.yaml` Lane 4's converter just wrote beside it. Any
disagreement is a converter bug or a Linkman gap, fixed before Lane 5.

Linkman is not a devman dependency yet (that lands in Lane 7), and its models
need `pydantic`, which devman's own venv deliberately does not carry before
then. This one-shot tool shells out to the `linkman` binary built by the
sibling checkout's own venv, rather than importing the library into this
process — the same boundary decision D-b protects in production code, kept
here for a dev tool too.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import devman_link
from devman.cli import _manifest_candidates

DEFAULT_OVERLAY = Path("~/.config/devman").expanduser()
DEFAULT_PROJECTS_ROOT = Path("~/Documents/Projects").expanduser()
DEFAULT_LINKMAN_BIN = Path(
    "~/Documents/Projects/linkman/.devenv/state/venv/bin/linkman"
).expanduser()


@dataclass(frozen=True, slots=True)
class Disagreement:
    project: str
    key: str
    devman_link_value: str | None
    linkman_value: str | None


def devman_link_targets(root: Path, overlay: Path, project: str) -> dict[str, str]:
    outcome = devman_link.run("status", root=root, overlay=overlay, project=None)
    return {
        row["view"]: row["canonical"]
        for row in devman_link.format_results_json(outcome)
        if row["view"] != ".git/info/exclude"
    }


def linkman_targets(
    linkman_bin: Path, root: Path, overlay: Path, project: str
) -> dict[str, str]:
    result = subprocess.run(
        [
            str(linkman_bin),
            "config",
            "--repo-root",
            str(root),
            "--overlay",
            str(overlay),
            "--name",
            project,
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"linkman config failed for {project}: {detail}")
    payload = json.loads(result.stdout)
    return {link["link_rel"]: link["target_abs"] for link in payload["links"]}


def compare_project(
    linkman_bin: Path, root: Path, overlay: Path, project: str
) -> list[Disagreement]:
    old = devman_link_targets(root, overlay, project)
    new = linkman_targets(linkman_bin, root, overlay, project)
    disagreements = []
    for key in sorted(set(old) | set(new)):
        old_value = old.get(key)
        new_value = new.get(key)
        if old_value != new_value:
            disagreements.append(Disagreement(project, key, old_value, new_value))
    return disagreements


def _live_candidates(projects_root: Path) -> dict[str, Path]:
    candidates, errors = _manifest_candidates([str(projects_root)])
    if errors:
        detail = "\n".join(f"  {root}: {message}" for root, message in errors)
        raise RuntimeError(f"cannot sweep every project cleanly:\n{detail}")
    return candidates


def compare_all(
    projects_root: Path = DEFAULT_PROJECTS_ROOT,
    *,
    overlay: Path = DEFAULT_OVERLAY,
    linkman_bin: Path = DEFAULT_LINKMAN_BIN,
) -> list[Disagreement]:
    candidates = _live_candidates(projects_root)
    disagreements: list[Disagreement] = []
    for project, root in sorted(candidates.items()):
        disagreements.extend(compare_project(linkman_bin, root, overlay, project))
    return disagreements


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Compare devman_link's declarations against the converted links.yaml."
    )
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="compare every live project")
    group.add_argument("--project", help="compare one live project by name")
    ap.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS_ROOT)
    ap.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    ap.add_argument("--linkman-bin", type=Path, default=DEFAULT_LINKMAN_BIN)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        candidates = _live_candidates(args.projects_root)
    except RuntimeError as exc:
        print(f"compare: {exc}", file=sys.stderr)
        return 1
    if args.project:
        if args.project not in candidates:
            print(
                f"compare: {args.project!r} is not a live, manifest-backed project",
                file=sys.stderr,
            )
            return 1
        targets = [(args.project, candidates[args.project])]
    else:
        targets = sorted(candidates.items())

    disagreements: list[Disagreement] = []
    for project, root in targets:
        try:
            disagreements.extend(
                compare_project(args.linkman_bin, root, args.overlay, project)
            )
        except RuntimeError as exc:
            print(f"compare: {exc}", file=sys.stderr)
            return 1

    for disagreement in disagreements:
        print(
            f"DIFF  {disagreement.project}  {disagreement.key}"
            f"  devman_link={disagreement.devman_link_value!r}"
            f"  linkman={disagreement.linkman_value!r}"
        )
    print(f"{len(targets)} project(s) compared · {len(disagreements)} disagreement(s)")
    return 1 if disagreements else 0


if __name__ == "__main__":
    sys.exit(main())
