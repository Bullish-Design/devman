"""Event parsing, matching, coalescing, and the watchexec command line.

**Nothing here starts watchexec.** The supervisor loop is a process test and
belongs to `nix/tests/`; what is testable here is every decision it makes before
it spawns anything — which repositories are watched, which glob fires which
workflow, and how one save's several events become one run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import ORDINARY

from devman import registry, watch

pytestmark = pytest.mark.unit

PY_TRIGGERS = {"group": "format", "map": {"**/*.py": "format"}}


def event(*paths: str) -> str:
    """One watchexec `json-stdio` line per path, as the dispatcher reads them."""
    return "\n".join(
        json.dumps({"tags": [{"kind": "path", "absolute": p, "filetype": "file"}]})
        for p in paths
    )


# ---------------------------------------------------------------------------
# changed_paths() — reading one batch


def test_changed_paths_reads_every_absolute_path():
    assert watch.changed_paths(event("/a/x.py", "/a/y.py")) == ["/a/x.py", "/a/y.py"]


def test_changed_paths_ignores_a_line_that_is_not_json():
    """The dispatcher reads a stream it does not own. A batch it cannot parse
    must cost the events in it, never the process."""
    raw = event("/a/x.py") + "\nnot json at all\n\n"
    assert watch.changed_paths(raw) == ["/a/x.py"]


def test_changed_paths_ignores_tags_that_are_not_paths():
    raw = json.dumps(
        {"tags": [{"kind": "source", "source": "filesystem"}, {"kind": "path"}]}
    )
    assert watch.changed_paths(raw) == []


def test_an_empty_batch_is_no_paths():
    assert watch.changed_paths("") == []


# ---------------------------------------------------------------------------
# watch_map() — what the registry says to watch


def test_a_project_with_no_triggers_is_not_watched(plane):
    """Reactivity is opt-in, by taking a group whose `triggers.toml` names the
    globs (§8). A project that takes no such group is absent from the map, not
    present with an empty one."""
    plane.add("quiet", workflows={"check": ORDINARY})
    assert watch.watch_map(plane.reg) == []


def test_globs_are_grouped_by_the_workflow_they_fire(plane):
    plane.add(
        "p",
        workflows={"format": ORDINARY},
        triggers={"group": "format", "map": {"**/*.py": "format", "*.pyi": "format"}},
    )
    (entry,) = watch.watch_map(plane.reg)
    assert entry.workflow == "format"
    assert entry.globs == ["**/*.py", "*.pyi"]
    assert entry.group == "format"


def test_a_project_whose_path_is_gone_is_skipped(plane):
    """**This is not a tidiness rule.** watchexec exits immediately when any
    `--watch` path does not exist, the supervisor exits with it,
    `Restart=on-failure` tries five times, and the unit is left **failed** — 30
    seconds from the first restart, with every other repository's saves going
    nowhere, and nothing brings it back (`STAGE_5_LOG.md`, S2)."""
    plane.add("here", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    plane.add(
        "gone", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS, make_dir=False
    )

    assert [e.project for e in watch.watch_map(plane.reg)] == ["here"]


def test_unwatchable_names_the_repository_that_is_missing(plane):
    """watchexec's own message never says which path it was. `watch_map` drops
    it so the watcher still starts; this is what makes the smaller watch set a
    sentence rather than a silence."""
    plane.add(
        "gone", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS, make_dir=False
    )
    assert [p.name for p in watch.unwatchable(plane.reg)] == ["gone"]


def test_a_stale_project_with_no_triggers_is_not_unwatchable(plane):
    """It was never watched, so nothing was lost. §10 check 5 owns it instead."""
    plane.add("gone", workflows={"check": ORDINARY}, make_dir=False)
    assert watch.unwatchable(plane.reg) == []


# ---------------------------------------------------------------------------
# match() — coalescing at the detector


def test_a_save_matching_a_glob_fires_its_workflow(plane):
    proj = plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    hits = watch.match(plane.reg, [str(proj.path / "src" / "a.py")])
    assert [(e.project, e.workflow) for e, _ in hits] == [("p", "format")]


def test_one_batch_fires_one_run_per_workflow(plane):
    """A save that touches three files is one run rather than three. That is
    coalescing at the detector, and it is **not** the loop break: the loop break
    is the workflow's own content-hash precondition (§8, E1). A batch is not a
    time window and swallows no later edit."""
    proj = plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    paths = [str(proj.path / f"{n}.py") for n in ("a", "b", "c")]

    hits = watch.match(plane.reg, paths)

    assert len(hits) == 1
    assert hits[0][1] == paths[0]


def test_two_projects_in_one_batch_each_fire(plane):
    a = plane.add("a", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    b = plane.add("b", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)

    hits = watch.match(plane.reg, [str(a.path / "x.py"), str(b.path / "y.py")])

    assert sorted(e.project for e, _ in hits) == ["a", "b"]


def test_a_path_matching_no_glob_fires_nothing(plane):
    proj = plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    assert watch.match(plane.reg, [str(proj.path / "README.md")]) == []


def test_a_path_outside_every_project_fires_nothing(plane, tmp_path):
    plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    assert watch.match(plane.reg, [str(tmp_path / "elsewhere" / "a.py")]) == []


def test_a_glob_is_matched_against_the_path_relative_to_the_repository(plane):
    """`groups/<group>/triggers.toml` states the glob relative to the
    repository's root, so a rooted glob must not match a nested file."""
    proj = plane.add(
        "p",
        workflows={"format": ORDINARY},
        triggers={"group": "format", "map": {"src/**/*.py": "format"}},
    )
    assert watch.match(plane.reg, [str(proj.path / "src" / "a.py")]) != []
    assert watch.match(plane.reg, [str(proj.path / "other" / "a.py")]) == []


# ---------------------------------------------------------------------------
# ownership — one rule, two callers (009 P1-4)
#
# `match()` used to decide containment for itself and accept EVERY registered
# root holding the path. `registry.deepest()` is now the single rule, and
# `project_for()` is its other caller.


def test_a_path_belongs_only_to_its_deepest_project(plane):
    """Reproduced in the review: `outer/inner/changed.py` with both registered
    returned `['inner', 'outer']`. One save, two runs, and the outer
    repository's formatter rewrote source across the nested repository
    boundary."""
    outer = plane.add("outer", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    inner = plane.add(
        "inner",
        path=outer.path / "inner",
        workflows={"format": ORDINARY},
        triggers=PY_TRIGGERS,
    )

    hits = watch.match(plane.reg, [str(inner.path / "changed.py")])

    assert [e.project for e, _ in hits] == ["inner"]


def test_the_inner_projects_trigger_map_decides(plane):
    """Ownership first, then that project's globs. The outer project's map does
    not get a vote on a file the inner project owns."""
    outer = plane.add(
        "outer",
        workflows={"format": ORDINARY},
        triggers={"group": "format", "map": {"**/*.py": "format"}},
    )
    inner = plane.add(
        "inner",
        path=outer.path / "inner",
        workflows={"check": ORDINARY},
        triggers={"group": "g", "map": {"**/*.py": "check"}},
    )

    hits = watch.match(plane.reg, [str(inner.path / "a.py")])

    assert [(e.project, e.workflow) for e, _ in hits] == [("inner", "check")]


def test_a_file_the_inner_project_does_not_own_still_fires_the_outer(plane):
    outer = plane.add("outer", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    plane.add(
        "inner",
        path=outer.path / "inner",
        workflows={"format": ORDINARY},
        triggers=PY_TRIGGERS,
    )

    hits = watch.match(plane.reg, [str(outer.path / "src" / "a.py")])

    assert [e.project for e, _ in hits] == ["outer"]


def test_three_levels_of_nesting_resolve_to_the_deepest(plane):
    top = plane.add("top", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    mid = plane.add(
        "mid",
        path=top.path / "mid",
        workflows={"format": ORDINARY},
        triggers=PY_TRIGGERS,
    )
    low = plane.add(
        "low",
        path=mid.path / "low",
        workflows={"format": ORDINARY},
        triggers=PY_TRIGGERS,
    )

    hits = watch.match(plane.reg, [str(low.path / "a.py")])

    assert [e.project for e, _ in hits] == ["low"]


def test_sibling_projects_are_unaffected(plane):
    a = plane.add("a", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    plane.add("b", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)

    hits = watch.match(plane.reg, [str(a.path / "x.py")])

    assert [e.project for e, _ in hits] == ["a"]


def test_deepest_and_project_for_agree(plane):
    """**This is what keeps the extraction honest.** The two callers disagreed
    for a whole stage. Assert the agreement directly, on a shared table, so they
    cannot drift again."""
    outer = plane.add("outer")
    inner = plane.add("inner", path=outer.path / "inner")
    plane.add("sibling")

    roots = {p.name: p.path for p in plane.reg.projects().values()}
    table = [
        outer.path,
        outer.path / "src",
        inner.path,
        inner.path / "deep" / "deeper",
    ]

    for here in table:
        assert (
            registry.deepest(roots, here.resolve()) == plane.reg.project_for(here).name
        )


def test_match_owns_no_containment_test_of_its_own(plane):
    """The rule lives in `registry.deepest()`. Copying it into `watch.py` would
    recreate 009 P1-4 in a new place."""
    source = Path(watch.__file__).read_text()
    body = source[source.index("def match(") : source.index("def dispatch(")]
    assert "deepest(roots, here)" in body
    assert "by_project[owner]" in body


# ---------------------------------------------------------------------------
# the watchexec command line


def test_the_command_states_the_project_origin(plane):
    """STATE THE ORIGIN, OR WATCHEXEC GOES LOOKING FOR IT. Left to search, one
    watcher over several repositories resolves their common ancestor and walks
    it: the same command line spun a core at 99.4% for over a minute with the
    origin searched, and sat at 0.3% with it given (S5)."""
    plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    argv = watch.watchexec_command(
        plane.reg, watch.watch_map(plane.reg), [], "/tmp/dagu"
    )
    assert f"--project-origin={plane.root}" in argv


def test_the_command_carries_the_three_measured_flags(plane):
    """`--emit-events-to=json-stdio` — `json-stdin` is rejected at start-up.
    `--postpone` — without it every mapped workflow fires whenever the service
    restarts and nobody saved anything. `--on-busy-update=queue` — events during
    a dispatch are handled after it rather than killing it."""
    plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    argv = watch.watchexec_command(
        plane.reg, watch.watch_map(plane.reg), [], "/tmp/dagu"
    )
    assert "--emit-events-to=json-stdio" in argv
    assert "--postpone" in argv
    assert "--on-busy-update=queue" in argv


def test_every_default_ignore_is_passed(plane):
    """watchexec's own project and VCS ignore discovery is switched off by
    `--project-origin`, so no repository's `.gitignore` is read. This list and a
    group's globs are the whole filter — and without the first pattern every run
    is its own next event, whatever the workflow does."""
    plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    argv = watch.watchexec_command(
        plane.reg, watch.watch_map(plane.reg), [], "/tmp/dagu"
    )
    for pattern in watch.DEFAULT_IGNORES:
        assert argv[argv.index(pattern) - 1] == "--ignore"
    assert "**/.devman/.runs/**" in watch.DEFAULT_IGNORES


def test_one_watch_per_repository_however_many_workflows(plane):
    proj = plane.add(
        "p",
        workflows={"format": ORDINARY, "check": ORDINARY},
        triggers={"group": "g", "map": {"**/*.py": "format", "**/*.nix": "check"}},
    )
    argv = watch.watchexec_command(
        plane.reg, watch.watch_map(plane.reg), [], "/tmp/dagu"
    )
    assert argv.count("--watch") == 1
    assert str(proj.path) in argv


def test_the_command_ends_with_the_dispatcher(plane):
    plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    argv = watch.watchexec_command(
        plane.reg, watch.watch_map(plane.reg), [], "/tmp/dagu"
    )
    tail = argv[argv.index("--") :]
    assert tail[1:] == [
        watch.self_binary(),
        "--registry",
        str(plane.root),
        "--dagu-home",
        "/tmp/dagu",
        "watch",
        "--dispatch",
    ]


def test_extra_arguments_reach_watchexec_before_the_separator(plane):
    plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    argv = watch.watchexec_command(
        plane.reg, watch.watch_map(plane.reg), ["--debounce=200"], "/tmp/dagu"
    )
    assert argv.index("--debounce=200") < argv.index("--")


# ---------------------------------------------------------------------------
# what forces a new watchexec, and what does not


def test_only_the_paths_force_a_new_child(plane):
    """The watched PATHS are watchexec's command line, so they are fixed when it
    starts. The MAPPING is re-read per event by the dispatcher, so a changed glob
    needs no restart — `watch_paths` is what the supervisor compares (S16)."""
    plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    before = watch.watch_map(plane.reg)

    plane.add(
        "p",
        workflows={"format": ORDINARY},
        triggers={"group": "format", "map": {"**/*.pyi": "format"}},
    )
    after = watch.watch_map(plane.reg)

    assert watch.watch_paths(after) == watch.watch_paths(before)
    assert watch.watch_shape(after) != watch.watch_shape(before)


def test_watch_shape_carries_everything_the_state_file_reports(plane):
    """So `doctor` never shows a stale glob."""
    proj = plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    assert watch.watch_shape(watch.watch_map(plane.reg)) == [
        ("p", str(proj.path), ("**/*.py",), "format", "format")
    ]


# ---------------------------------------------------------------------------
# the watcher's own state


def test_the_state_file_records_the_watch_set_and_the_command(plane):
    proj = plane.add("p", workflows={"format": ORDINARY}, triggers=PY_TRIGGERS)
    entries = watch.watch_map(plane.reg)
    state = watch.WatchState(plane.reg)

    state.start(entries, ["watchexec", "--watch", str(proj.path)])
    written = state.read()

    assert written["watching"] == [
        {
            "project": "p",
            "path": str(proj.path),
            "globs": ["**/*.py"],
            "workflow": "format",
            "group": "format",
        }
    ]
    assert written["command"][0] == "watchexec"


def test_reading_a_state_file_that_is_not_there_is_none(plane):
    assert watch.WatchState(plane.reg).read() is None


def test_a_corrupt_state_file_reads_as_none(plane):
    state = watch.WatchState(plane.reg)
    state.dir.mkdir(parents=True)
    state.state.write_text("{ half written")
    assert state.read() is None


def test_fired_runs_are_appended_and_read_newest_last(plane):
    state = watch.WatchState(plane.reg)
    for n in range(5):
        state.record("p", "format", f"/p/{n}.py", "enqueued")

    last = state.last_fired(3)

    assert [line["path"] for line in last] == ["/p/2.py", "/p/3.py", "/p/4.py"]
    assert last[0]["outcome"] == "enqueued"


def test_last_fired_with_no_log_is_empty(plane):
    assert watch.WatchState(plane.reg).last_fired(3) == []


def test_nothing_to_watch_says_it_is_not_an_error(plane):
    """Reactivity is opt-in, and a machine where nobody took a reactive group is
    healthy. The supervisor stays up and re-reads the registry, so a repository
    that adopts one is watched without a restart."""
    message = watch.nothing_to_watch(watch.POLL_SECONDS)
    assert "This is not an error" in message
    assert "5s" in message
