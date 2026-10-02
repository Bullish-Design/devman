"""The central guard — project 041's predicate over `~/.config/devman`.

Every test here builds its own `fleet` and `central` under `tmp_path`. The
live machine holds 325 real symlinks and the orchestrator is landing a lane
that changes that count while this project runs — a test asserting a live
count would pass today and fail within the hour. See CONCEPT.md §3.3 and
DECISIONS.md D1.

The C3 tests need a real `git` repository, and that is not negotiable: C3's
whole reason to exist is the difference between "on disk" and "on trunk", and
that difference does not exist without a real repository underneath it. So
they are **not** stubbed. They carry `needs_git`, and the C1 tests carry
`needs_nix`, because the `nix flake check` sandbox has neither binary on PATH
— `test_local_sources` elsewhere in this suite hit the same wall.

The distinction matters. A stub would make these tests pass everywhere while
asserting nothing, which is `AGENTS.md` property 4's own failure mode. A skip
keeps the assertion real wherever the binary exists — including `base:unit`,
the gate a developer actually runs — and only declines to report a red in a
sandbox that could never have run it. The flake check is already red for an
unrelated reason owned by the Linkman cutover; a second red that means nothing
would make the first one harder to see.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from devman import central, cli

pytestmark = pytest.mark.unit

# `test_link_adapter.py` already skips on a missing `nix-instantiate` this way;
# these follow it. A skip is not a stub: wherever the binary exists — which is
# `base:unit`, the gate a developer actually runs — the assertion runs for real
# against a real repository. The skip only stops the sandboxed `nix flake check`
# driver, which has neither binary, from reporting a red that means nothing.
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs a git binary")
needs_nix = pytest.mark.skipif(
    shutil.which("nix-instantiate") is None, reason="needs a Nix evaluator"
)


# ---------------------------------------------------------------------------
# fixture builders


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _init_central(root: Path, trunk: str = "main") -> None:
    """A real git repository, colocated-jj in spirit: `main` starts with one
    empty commit so a later branch can diverge from it."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", trunk)
    _git(root, "config", "user.email", "central-verify@example.com")
    _git(root, "config", "user.name", "central-verify tests")
    _git(root, "commit", "-q", "--allow-empty", "-m", "init")
    (root / "gitman.toml").write_text(f'trunk = "{trunk}"\n')


def _commit_on_trunk(root: Path, rel: str, text: str = "x\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"add {rel}")


def _current_branch(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit_on_a_lane(
    root: Path, rel: str, text: str = "x\n", *, lane: str = "m14-residue"
) -> None:
    """Branch off trunk, commit the file there, and leave `@` on the lane.

    This is the colocated-working-copy fact D11 and §3.5 rest on: the file
    is on disk right now, because the working copy *is* the lane's commit,
    and `main` never advances to include it. Re-entrant on `lane`: a test
    adding a second file to the same lane does not re-create the branch.
    """
    if _current_branch(root) != lane:
        _git(root, "checkout", "-q", "-b", lane)
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"add {rel} on the lane")


def _symlink(fleet: Path, repo: str, rel: str, target: Path) -> None:
    link = fleet / repo / rel
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)


def _snapshot(*roots: Path) -> set[tuple[str, str]]:
    """Every path under `roots`, with enough of its identity to catch a write:
    a symlink's raw target, or a regular file/dir's kind. Good enough to prove
    "nothing changed" without hashing file content neither test needs touched.
    """
    out: set[tuple[str, str]] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            rel = str(path.relative_to(root))
            if path.is_symlink():
                out.add((rel, f"symlink:{os.readlink(path)}"))
            elif path.is_dir():
                out.add((rel, "dir"))
            else:
                out.add((rel, f"file:{path.stat().st_size}"))
    return out


# ---------------------------------------------------------------------------
# C2 — target exists


def test_c2_fires_on_a_view_whose_target_is_absent(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    central_root.mkdir()
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )

    views = central.reverse_index(fleet=fleet, central=central_root)
    missing = central.check_c2_missing(views)

    assert [v.repo for v in missing] == ["linkman"]


def test_c2_does_not_fire_when_the_target_exists(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    target = central_root / "projects/linkman/devenv.local.nix"
    target.parent.mkdir(parents=True)
    target.write_text("{}\n")
    _symlink(fleet, "linkman", "devenv.local.nix", target)

    views = central.reverse_index(fleet=fleet, central=central_root)

    assert central.check_c2_missing(views) == []


# ---------------------------------------------------------------------------
# C3 — target reachable from trunk, the assertion the project exists for


@needs_git
def test_c3_fires_on_a_view_whose_target_exists_but_is_not_on_trunk(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _init_central(central_root)
    _commit_on_a_lane(central_root, "projects/linkman/devenv.local.nix")
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )

    views = central.reverse_index(fleet=fleet, central=central_root)
    lane_only = central.check_c3_lane_only(views, central_root, "main")

    assert [v.repo for v in lane_only] == ["linkman"]


@needs_git
def test_c3_does_not_fire_when_the_target_is_on_trunk(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _init_central(central_root)
    _commit_on_trunk(central_root, "projects/linkman/devenv.local.nix")
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )

    views = central.reverse_index(fleet=fleet, central=central_root)
    lane_only = central.check_c3_lane_only(views, central_root, "main")

    assert lane_only == []


@needs_git
def test_c3_does_not_double_report_a_target_c2_already_found_missing(tmp_path):
    """A view whose target does not exist on disk at all is neither "on
    trunk" nor "lane-only" — it is C2's finding. Reporting it twice would
    double one defect into two lines."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _init_central(central_root)
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )

    views = central.reverse_index(fleet=fleet, central=central_root)

    assert central.check_c3_lane_only(views, central_root, "main") == []


@needs_git
def test_exposure_message_names_repositories_and_the_shell_entry_consequence(
    tmp_path,
):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _init_central(central_root)
    for repo in ("linkman", "mnemonix", "scopeman"):
        _commit_on_a_lane(central_root, f"projects/{repo}/devenv.local.nix")
        _symlink(
            fleet,
            repo,
            "devenv.local.nix",
            central_root / f"projects/{repo}/devenv.local.nix",
        )

    views = central.reverse_index(fleet=fleet, central=central_root)
    lane_only = central.check_c3_lane_only(views, central_root, "main")
    message = central.exposure_message(lane_only, central_root)

    assert "3 live views in 3 repositories are still lane-only" in message
    assert "linkman, mnemonix, scopeman cannot enter a devenv shell" in message


# ---------------------------------------------------------------------------
# C4 — every links.yaml pairs with a devenv.local.nix


def test_c4_fires_on_a_project_with_links_yaml_and_no_devenv_local_nix(tmp_path):
    central_root = tmp_path / "central"
    links = central_root / "projects/docman-fixture/links.yaml"
    links.parent.mkdir(parents=True)
    links.write_text("links: {}\n")

    findings = central.check_c4_pairing(central_root)

    assert findings == ["docman-fixture: has links.yaml, no devenv.local.nix"]


def test_c4_does_not_fire_when_the_pair_is_complete(tmp_path):
    central_root = tmp_path / "central"
    project_dir = central_root / "projects/linkman"
    project_dir.mkdir(parents=True)
    (project_dir / "links.yaml").write_text("links: {}\n")
    (project_dir / "devenv.local.nix").write_text("{}\n")

    assert central.check_c4_pairing(central_root) == []


# ---------------------------------------------------------------------------
# C1 — the central Nix evaluates


@needs_nix
def test_c1_fires_on_a_devenv_local_nix_that_does_not_evaluate(tmp_path):
    central_root = tmp_path / "central"
    nix_file = central_root / "projects/linkman/devenv.local.nix"
    nix_file.parent.mkdir(parents=True)
    nix_file.write_text("{ this is not valid nix")

    findings = central.check_c1_nix_eval(central_root)

    assert len(findings) == 1
    assert "linkman" in findings[0]


@needs_nix
def test_c1_does_not_fire_on_a_devenv_local_nix_that_evaluates(tmp_path):
    central_root = tmp_path / "central"
    nix_file = central_root / "projects/linkman/devenv.local.nix"
    nix_file.parent.mkdir(parents=True)
    nix_file.write_text("{ pkgs }: { }\n")

    assert central.check_c1_nix_eval(central_root) == []


# ---------------------------------------------------------------------------
# the CLI: phase split (DECISIONS.md D3), exit codes, stdin, no writes


def _args(**overrides):
    base = {"phase": None, "overlay": None, "fleet_root": None, "json": False}
    base.update(overrides)
    return SimpleNamespace(**base)


def _central_verify(tmp_path, **overrides):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    fleet.mkdir(exist_ok=True)
    central_root.mkdir(exist_ok=True)
    args = _args(overlay=str(central_root), fleet_root=str(fleet), **overrides)
    return cli._central_verify(args, None), fleet, central_root


@needs_git
def test_phase_pre_does_not_run_c3(tmp_path, capsys):
    """A lane-only view must not be reported, let alone block, in `--phase
    pre` — C3 running there would refuse the one operation (landing) that
    fixes what it detects (DECISIONS.md D3)."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _init_central(central_root)
    _commit_on_a_lane(
        central_root, "projects/linkman/devenv.local.nix", "{ pkgs }: { }\n"
    )
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )

    args = _args(phase="pre", overlay=str(central_root), fleet_root=str(fleet))
    code = cli._central_verify(args, None)

    out = capsys.readouterr().out
    assert code == 0
    assert "C3" not in out
    assert "lane-only" not in out


@needs_git
def test_phase_post_does_not_run_c1_c2_c4(tmp_path, capsys):
    """`--phase post` runs C3 alone. A missing target (C2) and a dead
    `links.yaml` pairing (C4) must not appear — those belong to `pre`."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    central_root.mkdir()
    # C2: a dangling view.
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )
    # C4: a dead fixture pairing.
    links = central_root / "projects/docman-fixture/links.yaml"
    links.parent.mkdir(parents=True)
    links.write_text("links: {}\n")

    args = _args(phase="post", overlay=str(central_root), fleet_root=str(fleet))
    code = cli._central_verify(args, None)

    out = capsys.readouterr().out
    assert (
        code == 0
    )  # neither C2 nor C4 ran, and no git repo means no C3 finding either
    assert "C2" not in out
    assert "C4" not in out


@needs_git
def test_exit_code_is_zero_when_clean(tmp_path):
    code, _, _ = _central_verify(tmp_path)
    assert code == 0


@needs_git
def test_exit_code_is_one_on_a_finding(tmp_path):
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    fleet.mkdir()
    central_root.mkdir()
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )

    args = _args(overlay=str(central_root), fleet_root=str(fleet))
    code = cli._central_verify(args, None)

    assert code == 1


class _TripwireStdin:
    """Raises if `central-verify` ever reads stdin — it must not, by design:
    the predicate answers from the filesystem, and a gitman land hook pipes a
    JSON event on stdin that this command does not need. This stands in for
    both a populated pipe (any read call fails loudly) and an empty one (no
    read is attempted, so nothing blocks)."""

    def read(self, *a, **k):
        raise AssertionError("central-verify must not read stdin")

    def readline(self, *a, **k):
        raise AssertionError("central-verify must not read stdin")

    def __iter__(self):
        raise AssertionError("central-verify must not read stdin")


@needs_git
def test_it_never_touches_stdin(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _TripwireStdin())
    code, _, _ = _central_verify(tmp_path)
    assert code == 0


@needs_git
def test_it_writes_nothing(tmp_path, capsys):
    """gitman snapshots the workspace before and after a land hook and blocks
    the land on any change outside `allowed_paths`, even when the hook exits
    0. This is that property, asserted directly: a full run must leave both
    the fleet and the overlay byte-for-byte as found."""
    fleet = tmp_path / "fleet"
    central_root = tmp_path / "central"
    _init_central(central_root)
    _commit_on_trunk(
        central_root, "projects/linkman/devenv.local.nix", "{ pkgs }: { }\n"
    )
    _commit_on_a_lane(
        central_root, "projects/mnemonix/devenv.local.nix", "{ pkgs }: { }\n"
    )
    links = central_root / "projects/docman-fixture/links.yaml"
    links.parent.mkdir(parents=True)
    links.write_text("links: {}\n")
    _symlink(
        fleet,
        "linkman",
        "devenv.local.nix",
        central_root / "projects/linkman/devenv.local.nix",
    )
    _symlink(
        fleet,
        "mnemonix",
        "devenv.local.nix",
        central_root / "projects/mnemonix/devenv.local.nix",
    )
    _symlink(
        fleet,
        "scopeman",
        "devenv.local.nix",
        central_root / "projects/scopeman/devenv.local.nix",
    )

    before = _snapshot(fleet, central_root)
    args = _args(overlay=str(central_root), fleet_root=str(fleet))
    cli._central_verify(args, None)
    after = _snapshot(fleet, central_root)

    assert before == after
