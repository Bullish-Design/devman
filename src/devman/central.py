"""The predicate for `~/.config/devman` — project 041, "the central guard".

`devman doctor` used to report `ok  link drift  no registered project
declares a link` while 325 live symlinks pointed into the overlay. The check
read `proj.links` from the derived registry, and commit `37050e9`
(2026-09-19) deleted the hook that populated it, so 0 of 48 registry entries
declared a link. The check could not fail. This module replaces its input.

**The view side is the authority. Nothing else is.** `reverse_index()` walks
the fleet for every symlink whose raw target lands inside the overlay. It
does not read the registry (empty, §3.3 of CONCEPT.md), `links.yaml` alone
(a declaration, not a fact — excludes `.loci` and `.git/info/exclude`), or
`.devman-link-state.json` (stale by 34 projects, and D15 below says why this
module never touches it). A repository symlinking into the overlay is live
for this purpose whether or not it has onboarded to the plane — the reverse
index is a reading of the filesystem that owns the fact, so it cannot go
stale the way a record can.

Full design: `.scratch/projects/041-central-autoland/CONCEPT.md` §3, §4, §11;
`.scratch/projects/041-central-autoland/DECISIONS.md` D1, D3, D11, D15.

**Disclosed: read-only raw `git`.** `check_c3_lane_only()` calls
`git -C <central> ls-tree -r --name-only <trunk>`, and `current_lane()` calls
`git -C <central> rev-parse --abbrev-ref HEAD`. gitman ships 24 verbs and none
of them is `diff`, `show` or `reflog`, and none answers "is this path in
trunk's tree" — 035 §10 disclosed the identical choice for the identical
reason. Only `ls-tree`, `ls-files` and `rev-parse` are used here; nothing
that writes. C3 reads trunk through `ls-tree`, never the git index: in a
colocated jj repository the index is jj's export artifact, not a staging area
(035 §2.5).

**C3 does not fire on a target git can never track, and C5 reports that case
instead.** A declared target that is a directory holding no file and no
symlink anywhere below it — or whose only entries `.gitignore` excludes —
cannot be "lane-only" (§3.5 below): git never held it in any lane, so it can
never reach trunk, and C3 would otherwise report it on every run forever.
`_hollow_directory_targets()` is the shared predicate, batched across every
directory view in one pair of `git ls-files` calls rather than walked in
Python — see its docstring for why that matters (16,751 real entries under
one target alone). `check_c5_empty_surface` names the real condition — an
onboarding that likely never finished — rather than blaming a lane for a gap
no lane created.

**This module writes nothing, ever.** It runs as a gitman land hook, and
gitman snapshots the workspace before and after the hook and blocks the land
on any file change outside `allowed_paths` — even when the hook exits 0
(`gitman/src/gitman/hooks.py:filesystem_snapshot`). A predicate that writes
would make its own correctness unlandable.

**`.devman-link-state.json` is read by nothing here and written by nothing
here** (D15). `devman_link.excludes` reads its `{canonical, hash}` baseline to
refuse a two-sided edit of the exclude projection, and regenerating or
discarding it from this module would break that refusal.

**Stated limits** (CONCEPT.md §11; restated here beside the code they bound):

1. The reverse-index walk is bounded to depth 2 below each fleet repository,
   plus the one-level-deeper `.git/info/exclude` case. That bound is what
   keeps the walk at 0.72 s measured on 66 repositories. A view declared
   deeper than two levels is missed; none exists today.
2. It only sees repositories directly under the `fleet` root (the live
   machine fact is `~/Documents/Projects/`). A managed repository outside
   that directory is invisible to it.
3. C1 (`check_c1_nix_eval`) evaluates `builtins.functionArgs (import …)`, the
   same bound the central `devenv.nix`'s own `base:check` task accepts. It
   catches a syntax error and a broken argument contract. It does not catch a
   declaration that evaluates and is wrong.
4. C3 is a reachability test, not a durability test. A stale trunk copy
   behind a newer lane edit reads as safe — that failure is staleness, not a
   brick, and closing it needs a content comparison this module does not do.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_CENTRAL = Path("~/.config/devman").expanduser()
DEFAULT_FLEET = Path("~/Documents/Projects").expanduser()


class InfraError(RuntimeError):
    """The predicate could not run at all — exit 2, not a content finding.

    Raised when a tool an assertion depends on (``nix-instantiate``, `git`)
    is missing from `PATH`. Distinct from a finding: a missing tool says
    nothing about whether the central declarations are correct.
    """


# Pruned at every level of the walk. Matches prototype-v3's SKIP set: version
# control internals, build/dependency caches, and devman's own run history —
# none of them ever holds a symlink a repository's shell entry depends on.
_SKIP = {
    ".git",
    ".jj",
    ".devenv",
    ".direnv",
    ".venv",
    "node_modules",
    "__pycache__",
    ".worktrees",
    ".archive",
    ".runs",
}

# Limit 1 above. Measured at 0.72 s for 325 views across 66 repositories;
# re-measure before raising it.
_MAX_DEPTH = 2


@dataclass(frozen=True, slots=True)
class View:
    """One live symlink whose raw target lands inside the overlay.

    ``target`` is the normalized absolute path the link resolves to one hop
    — not fully resolved, so a target that is itself a symlink is reported at
    the path the fleet repository actually depends on.
    """

    repo: str
    rel: str
    target: str


def reverse_index(
    fleet: Path = DEFAULT_FLEET, central: Path = DEFAULT_CENTRAL
) -> list[View]:
    """Walk the fleet for every symlink pointing into the overlay.

    Ports `.scratch/projects/041-central-autoland/artifacts/prototype-v3-reverse-index.py`.
    The population is the reverse index (DECISIONS.md D1): no registry, no
    ledger, no `links.yaml` is trusted. Depth-bounded at `_MAX_DEPTH` below
    each repository, plus the one `.git/info/exclude` case that lives one
    level deeper than the pruned `.git/` directory (limit 1).
    """
    central_str = str(central.resolve())
    out: list[View] = []
    if not fleet.is_dir():
        return out
    for repo in sorted(
        p for p in fleet.iterdir() if p.is_dir() and p.name not in _SKIP
    ):
        for cur, dirs, files in os.walk(repo, followlinks=False):
            depth = len(Path(cur).relative_to(repo).parts)
            dirs[:] = [] if depth >= _MAX_DEPTH else [d for d in dirs if d not in _SKIP]
            for name in list(dirs) + files:
                p = Path(cur) / name
                if not p.is_symlink():
                    continue
                target = _normalize_target(p)
                if target is None:
                    continue
                if target == central_str or target.startswith(central_str + "/"):
                    out.append(View(repo.name, str(p.relative_to(repo)), target))
        # .git/info/exclude is pruned by the walk above (it lives below the
        # skipped .git/ directory) and is one of the eight known view kinds
        # (CONCEPT.md §3.3), so it is checked explicitly.
        exclude = repo / ".git" / "info" / "exclude"
        if (repo / ".git").is_dir() and exclude.is_symlink():
            target = _normalize_target(exclude)
            if target and (
                target == central_str or target.startswith(central_str + "/")
            ):
                out.append(View(repo.name, ".git/info/exclude", target))
    return out


def _normalize_target(link: Path) -> str | None:
    """The absolute, normalized path a symlink's raw target names.

    Normalized rather than resolved: resolving would follow a second hop and
    report the wrong path if the target is itself a symlink.
    """
    raw = os.readlink(link)
    target = Path(raw) if os.path.isabs(raw) else (link.parent / raw)
    try:
        return os.path.normpath(target)
    except ValueError:
        return None


def trunk_name(central: Path = DEFAULT_CENTRAL) -> str:
    """Read `trunk` from `gitman.toml`. Defaults to ``"main"`` if unstated."""
    config = central / "gitman.toml"
    if not config.is_file():
        return "main"
    match = re.search(r'trunk\s*=\s*"([^"]+)"', config.read_text())
    return match.group(1) if match else "main"


def _git(central: Path, *args: str) -> str:
    """Read-only raw `git`, disclosed in the module docstring. Never a write."""
    try:
        result = subprocess.run(
            ["git", "-C", str(central), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise InfraError("git is not on PATH; cannot read trunk's tree") from exc
    return result.stdout


def tracked_paths(central: Path, trunk: str) -> set[str]:
    """Every path `git ls-tree` reports for `trunk` — never the index (D11)."""
    return set(_git(central, "ls-tree", "-r", "--name-only", trunk).splitlines())


def current_lane(central: Path = DEFAULT_CENTRAL) -> str | None:
    """The branch `@` sits on, for naming the exposure in the post-phase message.

    Best-effort and read-only (`git rev-parse`, in the disclosed list). Naming
    the lane is a nice-to-have (CONCEPT.md §4.4); a failure here must not
    affect any assertion, so this returns ``None`` rather than raising.

    **Measured limit, beyond CONCEPT.md §11.** In a colocated jj repository
    `git`'s own `HEAD` is routinely detached — jj moves its own working-copy
    commit and does not move git's symbolic ref the way a plain `git
    checkout` would. `git rev-parse --abbrev-ref HEAD` then answers the
    literal string ``"HEAD"``, which names nothing a human could act on, so
    it is treated the same as "could not be read" rather than printed.
    """
    try:
        name = _git(central, "rev-parse", "--abbrev-ref", "HEAD").strip()
    except InfraError:
        return None
    return name if name and name != "HEAD" else None


def check_c1_nix_eval(central: Path = DEFAULT_CENTRAL) -> list[str]:
    """C1 — every `projects/*/devenv.local.nix` evaluates under Nix.

    Ports the `base:check` task already written in
    `~/.config/devman/devenv.nix`: `nix-instantiate --eval --strict --expr
    'builtins.functionArgs (import "<path>")'` per file. 015 killed a prior
    candidate for re-implementing a task the repository already had; this
    adopts it instead (DECISIONS.md D12). Measured: 78 files, 2.58 s.
    """
    findings: list[str] = []
    for nix_file in sorted(central.glob("projects/*/devenv.local.nix")):
        expr = f'builtins.functionArgs (import "{nix_file}")'
        try:
            result = subprocess.run(
                ["nix-instantiate", "--eval", "--strict", "--expr", expr],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise InfraError(
                "nix-instantiate is not on PATH; C1 cannot evaluate the"
                " central Nix files"
            ) from exc
        if result.returncode != 0:
            rel = nix_file.relative_to(central)
            detail = (
                result.stderr.strip().splitlines()[-1] if result.stderr else "no output"
            )
            findings.append(f"{rel} does not evaluate under Nix — {detail}")
    return findings


def check_c2_missing(views: list[View]) -> list[View]:
    """C2 — every live view's target exists on disk."""
    return [v for v in views if not os.path.exists(v.target)]


def _hollow_directory_targets(views: list[View], central: Path) -> set[str]:
    """Which directory-shaped targets among `views` hold nothing git could
    ever track on trunk, at any depth.

    A file or a symlink target is always trackable on its own — git's
    object model holds blobs (regular files) and symlinks (mode `120000`);
    a directory is never an object of its own, so a tree of directories
    holding only further directories is invisible to git forever. Only a
    directory target can be hollow, so only directory targets are checked.

    For a directory, the question becomes two of git's own: does it already
    hold a **tracked** path (`git ls-files`), or does it hold an **untracked
    path `.gitignore` would not skip** (`git ls-files --others
    --exclude-standard`)? Either answers yes. A directory whose only content
    `.gitignore` excludes (`projects/*/agents/pi/` and similar,
    `~/.config/devman/.gitignore`) answers no to both, and is treated the
    same as a structurally empty one: an ordinary `gitman land` can no more
    land a gitignored path than it can land one that was never there, so
    neither can reach trunk, which is all C3 asks.

    **Batched, not per-view.** A real target can hold tens of thousands of
    entries (`projects/browsee/agents`, measured at 16,751, mostly the
    gitignored `agents/pi/` runtime cache); a Python `os.walk` plus a `stat`
    per entry cost over half a second there alone, and 132 directory views
    on the live overlay turned that into a 22 s run — a tenfold overshoot of
    the 3.4 s budget. Two `git ls-files` calls across every directory view
    at once, instead of two calls per view, answers in milliseconds: git's
    own traversal is implemented in C and already knows how to skip what
    `.gitignore` excludes.

    **Cached per process, keyed on the directory set.** `check_c3_lane_only`
    and `check_c5_empty_surface` each call this against the same `views`
    within one `central-verify` run; without the cache that is two git
    invocations where one would do. The key is the sorted tuple of directory
    targets, not `id(views)`, so it stays correct if a caller ever builds two
    different view lists that happen to name the same directories.
    """
    central_str = str(central.resolve())
    rel_to_target: dict[str, str] = {}
    for v in views:
        if os.path.isdir(v.target):
            path_str = v.target
            rel = (
                path_str[len(central_str) + 1 :]
                if path_str.startswith(central_str)
                else path_str
            )
            rel_to_target[rel] = path_str
    if not rel_to_target:
        return set()

    present = _hollow_lookup(central, tuple(sorted(rel_to_target)))
    return {target for rel, target in rel_to_target.items() if rel not in present}


@lru_cache(maxsize=8)
def _hollow_lookup(central: Path, rels: tuple[str, ...]) -> frozenset[str]:
    """Which of `rels` (relative paths below `central`) hold any file or
    symlink, tracked or not-ignored-untracked. The non-hollow subset."""
    tracked = _git(central, "ls-files", "--", *rels)
    untracked = _git(central, "ls-files", "--others", "--exclude-standard", "--", *rels)
    present: set[str] = set()
    for line in tracked.splitlines() + untracked.splitlines():
        line = line.strip()
        if not line:
            continue
        for rel in rels:
            if rel in present:
                continue
            if line == rel or line.startswith(rel + "/"):
                present.add(rel)
    return frozenset(present)


def check_c3_lane_only(
    views: list[View], central: Path = DEFAULT_CENTRAL, trunk: str | None = None
) -> list[View]:
    """C3 — every live view's target is reachable from trunk.

    Reads `git ls-tree -r --name-only <trunk>` (D11). A view whose target is
    missing is C2's finding, not this one's — a target that does not exist
    is neither "on trunk" nor "lane-only"; reporting it twice would double
    one defect into two lines.

    **Excludes a target git could never track.** A directory holding no
    file and no symlink anywhere below it — `_hollow_directory_targets` —
    is not "lane-only": git never held it in any lane, so no lane operation
    can be blamed for its absence from trunk, and it will read as a C3
    finding on every run forever otherwise (the defect this function was
    changed to fix). `check_c5_empty_surface` reports the condition that
    actually applies instead.
    """
    trunk = trunk or trunk_name(central)
    central_str = str(central.resolve())
    tracked = tracked_paths(central, trunk)
    hollow = _hollow_directory_targets(views, central)
    findings: list[View] = []
    for v in views:
        if not (v.target == central_str or v.target.startswith(central_str + "/")):
            continue  # an external target: not this repository's to hold
        if not os.path.exists(v.target):
            continue  # C2's finding, not C3's
        if v.target in hollow:
            continue  # nothing git could ever track here; C5's finding, not C3's
        rel = v.target[len(central_str) + 1 :]
        if os.path.isdir(v.target):
            on_trunk = any(x == rel or x.startswith(rel + "/") for x in tracked)
        else:
            on_trunk = rel in tracked
        if not on_trunk:
            findings.append(v)
    return findings


def check_c5_empty_surface(
    views: list[View], central: Path = DEFAULT_CENTRAL
) -> list[View]:
    """C5 — every live view's target holds content on disk, not an empty shell.

    A directory that holds no file and no symlink anywhere below it — see
    `_hollow_directory_targets` — can never be C3's "lane-only", because
    git never held it in any lane. It is not silence, either: a live
    repository still symlinks into it, so an agent reading, say,
    `.agents/skills` there finds no skills. That is degraded, not broken —
    no shell fails on a hollow directory the way it does on a missing one
    (C2) — and its usual cause is an onboarding that never finished: a
    repository with no `.devman/project.toml` whose `devenv` shell entry
    still created a central directory for it, with nothing in it yet.

    Lower severity than C3: C3 names an active hazard (content that a lane
    operation will remove from disk); C5 names a standing gap that no lane
    operation created and none will close by landing — only finishing the
    project's onboarding does.
    """
    hollow = _hollow_directory_targets(views, central)
    return [v for v in views if os.path.exists(v.target) and v.target in hollow]


def check_c4_pairing(central: Path = DEFAULT_CENTRAL) -> list[str]:
    """C4 — every central project with a tracked `links.yaml` has a `devenv.local.nix`.

    Ports prototype-v1's pairing loop. Today it fires 10 times, all dead
    `docman-*`/`roundtrip-debug` fixtures parked in the lane
    `m14-central-dead-fixtures`.
    """
    findings: list[str] = []
    for links_yaml in sorted(central.glob("projects/*/links.yaml")):
        project_dir = links_yaml.parent
        if not (project_dir / "devenv.local.nix").is_file():
            findings.append(f"{project_dir.name}: has links.yaml, no devenv.local.nix")
    return findings


def exposure_message(lane_only: list[View], central: Path = DEFAULT_CENTRAL) -> str:
    """The human-actionable sentence CONCEPT.md §4.4 specifies for C3.

    Names the repositories, not only a count, and separates out the ones
    whose `devenv.local.nix` bootstrap link is lane-only — those cannot enter
    a devenv shell once the lane leaves the working copy (025 §5, §12 limit
    2: Nix reads that file before any shell hook runs, and the failure
    carries a trace nothing can intercept). Naming the lane is a nice-to-have
    and is omitted if it cannot be read.
    """
    if not lane_only:
        return ""
    repos = sorted({v.repo for v in lane_only})
    shell_blocked = sorted({v.repo for v in lane_only if v.rel == "devenv.local.nix"})
    message = (
        f"central-verify: {len(lane_only)} live views in {len(repos)} "
        "repositories are still lane-only."
    )
    if shell_blocked:
        who = ", ".join(shell_blocked)
        lane = current_lane(central)
        trunk = trunk_name(central)
        where = (
            f" if {lane!r} leaves the working copy" if lane and lane != trunk else ""
        )
        message += f" {who} cannot enter a devenv shell{where}."
    return message


def format_view(
    v: View, *, trunk: str | None = None, central: Path = DEFAULT_CENTRAL
) -> str:
    """One `Report`-line rendering of a view, shared by C2 and C3 output."""
    if trunk is None:
        return f"{v.repo}/{v.rel} -> {v.target} (target does not exist)"
    central_str = str(central.resolve())
    shown = (
        v.target[len(central_str) + 1 :]
        if v.target.startswith(central_str)
        else v.target
    )
    return f"{v.repo}/{v.rel} -> {shown} (lane-only, not reachable from {trunk})"


def format_empty_view(v: View, *, central: Path = DEFAULT_CENTRAL) -> str:
    """One `Report`-line rendering of a view, for C5's empty-surface finding.

    Named plainly, not as corruption: the usual cause is a project that
    never finished onboarding, not damage to a project that had. An agent
    reading `{rel}` at this repository finds nothing below it.
    """
    central_str = str(central.resolve())
    shown = (
        v.target[len(central_str) + 1 :]
        if v.target.startswith(central_str)
        else v.target
    )
    return (
        f"{v.repo}/{v.rel} -> {shown} (empty surface: no file or symlink"
        " anywhere below this target — likely an onboarding that never"
        " finished, not damage)"
    )
