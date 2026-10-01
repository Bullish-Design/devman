"""Phase B of the M14 devman cutover: the byte-identity gate.

For every project in scope: snapshot, run a real `linkman apply`, snapshot
again, and compare raw targets byte for byte — never `realpath`, never
effective-target equality. Trap 6, and §2 of the M14 readiness review, are
the production case this rule exists for.

`.git/info/exclude` is excluded from the population: it stays devman's
under D5. The gate also checks idempotence (a second apply must report zero
mutating actions) and the scope of mutation: nothing outside the managed
symlink set may change. That last check is a byte-content digest of the
*immediate* (non-recursive) entries of each repository root and each
central project directory, excluding the managed names — a full recursive
hash of every dependency tree on this machine (one project measured at
over 200 MB) is neither what the invariant protects nor practical here.

Linkman is not a devman dependency until Lane 7 (see compare.py); this tool
shells out to the sibling checkout's own `linkman` binary for the same
reason.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.cutover.snapshot import (
    DEFAULT_OVERLAY,
    DEFAULT_PROJECTS_ROOT,
    SnapshotEntry,
    project_entries,
)

from devman.cli import _manifest_candidates

DEFAULT_LINKMAN_BIN = Path(
    "~/Documents/Projects/linkman/.devenv/state/venv/bin/linkman"
).expanduser()

MUTATING_ACTIONS = frozenset(
    {"create_target_file", "create_target_dir", "create_link", "repoint_link"}
)


class GateFailureError(RuntimeError):
    """The gate found something it must refuse to pass."""


@dataclass(frozen=True, slots=True)
class Diff:
    project: str
    link_rel: str
    before_raw: str | None
    after_raw: str | None
    approval: str | None = None


def linkman_population(entries: list[SnapshotEntry]) -> list[SnapshotEntry]:
    """Exclude `.git/info/exclude` — devman's under D5, never Linkman's."""
    return [entry for entry in entries if entry.link_rel != ".git/info/exclude"]


def run_apply(linkman_bin: Path, root: Path, overlay: Path, project: str) -> dict:
    result = subprocess.run(
        [
            str(linkman_bin),
            "apply",
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
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        detail = (result.stderr or result.stdout).strip()
        raise GateFailureError(
            f"linkman apply produced no parseable JSON for {project}"
            f" (exit {result.returncode}): {detail}"
        ) from exc
    if payload.get("failed"):
        raise GateFailureError(
            f"linkman apply reported failures for {project}: {payload['failed']}"
        )
    return payload


def mutating_action_count(apply_result: dict) -> int:
    return sum(
        1
        for applied in apply_result["applied"]
        for action in applied["actions"]
        if action in MUTATING_ACTIONS
    )


def _entry_digest(path: Path) -> str:
    if path.is_symlink():
        return f"symlink:{os.readlink(path)}"
    if path.is_file():
        return f"file:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    if path.is_dir():
        return "dir"
    return "special"


def top_level_digest(directory: Path, *, exclude: set[str]) -> dict[str, str]:
    """A byte-content digest of `directory`'s immediate entries, excluding
    `exclude`. Not recursive — see the module docstring.
    """
    if not directory.is_dir():
        return {}
    return {
        entry.name: _entry_digest(entry)
        for entry in sorted(directory.iterdir())
        if entry.name not in exclude
    }


def mutation_scope_digest(
    entries: list[SnapshotEntry], root: Path, overlay: Path, project: str
) -> dict[str, dict[str, str]]:
    """Digest every directory a managed link lives in or points under,
    excluding the managed entries themselves.
    """
    central_dir = (overlay / "projects" / project).resolve()
    repo_root = root.resolve()
    directories = {repo_root}
    for entry in entries:
        directories.add((repo_root / entry.link_rel).parent)
    exclude_by_dir: dict[Path, set[str]] = {
        directory: set() for directory in directories
    }
    for entry in entries:
        link_path = repo_root / entry.link_rel
        exclude_by_dir[link_path.parent].add(link_path.name)
    digest = {
        str(directory): top_level_digest(directory, exclude=exclude_by_dir[directory])
        for directory in directories
    }
    central_exclude = {
        entry.link_rel.split("/", 1)[0]
        for entry in entries
        if entry.raw_target_hex is not None
        and bytes.fromhex(entry.raw_target_hex)
        .decode(errors="replace")
        .startswith(str(central_dir))
    }
    digest[str(central_dir)] = top_level_digest(central_dir, exclude=central_exclude)
    return digest


def gate_project(
    linkman_bin: Path, root: Path, overlay: Path, project: str
) -> tuple[list[Diff], int]:
    """Run the full gate for one project. Returns (diffs, population size)."""
    before = linkman_population(project_entries(project, root, overlay=overlay))
    scope_before = mutation_scope_digest(before, root, overlay, project)

    run_apply(linkman_bin, root, overlay, project)

    after = linkman_population(project_entries(project, root, overlay=overlay))
    scope_after = mutation_scope_digest(after, root, overlay, project)

    if scope_before != scope_after:
        raise GateFailureError(
            f"{project}: apply changed something outside the managed symlink set"
        )

    by_before = {entry.link_rel: entry for entry in before}
    by_after = {entry.link_rel: entry for entry in after}
    if set(by_before) != set(by_after):
        missing = set(by_before) - set(by_after)
        if missing:
            raise GateFailureError(
                f"{project}: path(s) present before are missing after: {missing}"
            )

    diffs = [
        Diff(
            project,
            link_rel,
            by_before[link_rel].raw_target_hex,
            by_after[link_rel].raw_target_hex,
        )
        for link_rel in sorted(by_before)
        if by_before[link_rel].raw_target_hex != by_after[link_rel].raw_target_hex
        or by_before[link_rel].kind != by_after[link_rel].kind
    ]

    second = run_apply(linkman_bin, root, overlay, project)
    mutated = mutating_action_count(second)
    if mutated:
        raise GateFailureError(
            f"{project}: second apply was not idempotent — {mutated} mutating action(s)"
        )

    third = linkman_population(project_entries(project, root, overlay=overlay))
    by_third = {entry.link_rel: entry for entry in third}
    if by_after != by_third:
        raise GateFailureError(f"{project}: a third snapshot differs from the second")

    return diffs, len(after)


def run_gate(
    targets: list[tuple[str, Path]],
    *,
    overlay: Path = DEFAULT_OVERLAY,
    linkman_bin: Path = DEFAULT_LINKMAN_BIN,
) -> tuple[list[Diff], int]:
    all_diffs: list[Diff] = []
    total_population = 0
    for project, root in targets:
        diffs, population = gate_project(linkman_bin, root, overlay, project)
        all_diffs.extend(diffs)
        total_population += population
    return all_diffs, total_population


def _live_candidates(projects_root: Path) -> dict[str, Path]:
    candidates, errors = _manifest_candidates([str(projects_root)])
    if errors:
        detail = "\n".join(f"  {root}: {message}" for root, message in errors)
        raise GateFailureError(f"cannot sweep every project cleanly:\n{detail}")
    return candidates


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Phase B: the byte-identity gate.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="gate every live project")
    group.add_argument("--project", help="gate one live project")
    group.add_argument("--projects", nargs="+", help="gate the named live projects")
    ap.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS_ROOT)
    ap.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    ap.add_argument("--linkman-bin", type=Path, default=DEFAULT_LINKMAN_BIN)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        candidates = _live_candidates(args.projects_root)
    except GateFailureError as exc:
        print(f"gate: {exc}", file=sys.stderr)
        return 1

    if args.all:
        targets = sorted(candidates.items())
    else:
        names = args.projects if args.projects else [args.project]
        missing = [name for name in names if name not in candidates]
        if missing:
            print(
                f"gate: not a live, manifest-backed project: {missing}", file=sys.stderr
            )
            return 1
        targets = [(name, candidates[name]) for name in names]

    try:
        diffs, population = run_gate(
            targets, overlay=args.overlay, linkman_bin=args.linkman_bin
        )
    except GateFailureError as exc:
        print(f"gate: {exc}", file=sys.stderr)
        return 1

    for diff in diffs:
        print(
            f"DIFF  {diff.project}  {diff.link_rel}  before={diff.before_raw!r}"
            f"  after={diff.after_raw!r}  approval={diff.approval or 'NONE'}"
        )
    unapproved = [diff for diff in diffs if diff.approval is None]
    identical = population - len(diffs)
    print(
        f"{population} compared · {identical} identical · {len(diffs)} differing"
        f" · {len(diffs) - len(unapproved)} approved · {len(unapproved)} unapproved"
        f"  => {'PASS' if not unapproved else 'FAIL'}"
    )
    return 1 if unapproved else 0


if __name__ == "__main__":
    sys.exit(main())
