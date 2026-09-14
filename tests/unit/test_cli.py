"""The command surface, and the one import that is no longer eager.

`cli.py` imports four of its five handler modules at the top of the file and
`doctor` inside `handler()`. That is a measured saving — 52 ms of every devman
process, and the dispatch path used to start two — and it costs one property:
an import error in `doctor.py` no longer reaches anybody who runs any OTHER
command. These tests are what pay that back.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from devman import cli

pytestmark = pytest.mark.unit

# `agent` is §10's fourth command, amended in by project 022: it runs INSIDE
# a workflow rather than being typed at one. The list stays closed either way,
# and this is one of the two places that spell it.
SUBCOMMANDS = ("run", "show", "doctor", "watch", "project", "agent", "link")


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_every_subcommand_module_imports(command):
    """**The check the eager import used to be.**

    `from . import doctor` at the top of `cli.py` meant `devman --help` proved
    that `doctor.py` at least imports. Deferring it moved that proof here, where
    it is stated rather than incidental — and where it covers all five rather
    than the four that happen to be spelled in one line. The public `link`
    command uses the independent `devman_link` component.
    """
    module = "devman_link" if command == "link" else f"devman.{command}"
    assert importlib.import_module(module) is not None


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_every_subcommand_resolves_to_a_handler(command):
    """`handler()` and the parser must name the same five commands. A command
    the parser accepts and `handler()` does not know is a `KeyError` at the
    moment somebody runs it, which is later, elsewhere and unexplained (E5)."""
    assert callable(cli.handler(command))


def test_the_parser_and_the_handler_agree_on_the_whole_list():
    """Neither side may grow a command alone. §10's list is closed, and the two
    places that spell it are here and in `parser()`."""
    sub = next(
        action
        for action in cli.parser()._actions
        if isinstance(action, __import__("argparse")._SubParsersAction)
    )
    assert set(sub.choices) == set(SUBCOMMANDS)


def test_doctor_is_not_imported_until_it_is_asked_for():
    """The saving itself, asserted on the module object rather than on a clock.

    A timing assertion would be flaky and would not say what went wrong. This
    says exactly what the change is: `cli` holds no reference to `doctor`, so
    importing `cli` cannot pull `urllib.request` and `concurrent.futures` in
    with it.
    """
    assert not hasattr(cli, "doctor")


def _write_manifest(root, project):
    manifest = root / ".devman/project.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        f'schema = 1\nproject = "{project}"\ngroups = []\npolicy = "stable"\n'
    )


def test_link_all_sweeps_explicit_manifest_inventory(monkeypatch, tmp_path, capsys):
    first = tmp_path / "zulu-checkout"
    second = tmp_path / "alpha-checkout"
    first.mkdir()
    second.mkdir()
    _write_manifest(first, "zulu")
    _write_manifest(second, "alpha")
    (tmp_path / "not-a-project").mkdir()

    calls = []

    def fake_run(command, *, root, overlay, project):
        calls.append((command, root, overlay, project))
        return SimpleNamespace(exit_code=0)

    monkeypatch.setattr(cli.devman_link, "run", fake_run)
    monkeypatch.setattr(cli.devman_link, "format_results", lambda _outcome: ["ok"])

    args = SimpleNamespace(projects_root=[str(tmp_path)], overlay=None, project=None)
    assert cli._link_all(args) == 0
    assert [
        (command, root.name, project) for command, root, _overlay, project in calls
    ] == [
        ("status", "alpha-checkout", None),
        ("status", "zulu-checkout", None),
    ]
    assert capsys.readouterr().out.splitlines() == ["ok", "ok"]


def test_link_all_reports_bad_manifest_and_continues(monkeypatch, tmp_path, capsys):
    valid = tmp_path / "valid-checkout"
    invalid = tmp_path / "invalid-checkout"
    valid.mkdir()
    invalid.mkdir()
    _write_manifest(valid, "valid")
    manifest = invalid / ".devman/project.toml"
    manifest.parent.mkdir()
    manifest.write_text("schema = [")

    calls = []

    def fake_run(command, *, root, overlay, project):
        calls.append(root)
        return SimpleNamespace(exit_code=0)

    monkeypatch.setattr(cli.devman_link, "run", fake_run)
    monkeypatch.setattr(cli.devman_link, "format_results", lambda _outcome: ["ok"])

    args = SimpleNamespace(projects_root=[str(tmp_path)], overlay=None, project=None)
    assert cli._link_all(args) == 1
    assert calls == [valid.resolve()]
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["ok"]
    assert "cannot inspect manifest-backed project" in captured.err


def test_link_all_requires_an_explicit_inventory_root():
    with pytest.raises(cli.RegistryError, match="explicit --projects-root"):
        cli._manifest_candidates([])


def test_parser_accepts_multiple_project_inventory_roots():
    args = cli.parser().parse_args(
        [
            "link",
            "status",
            "--all",
            "--projects-root",
            "first",
            "--projects-root",
            "second",
        ]
    )
    assert args.all is True
    assert args.projects_root == ["first", "second"]


def test_link_all_blocks_duplicate_manifest_identities(monkeypatch, tmp_path, capsys):
    first = tmp_path / "first-checkout"
    second = tmp_path / "second-checkout"
    first.mkdir()
    second.mkdir()
    _write_manifest(first, "same")
    _write_manifest(second, "same")

    monkeypatch.setattr(
        cli.devman_link,
        "run",
        lambda *_args, **_kwargs: pytest.fail("duplicate identity was run"),
    )

    args = SimpleNamespace(projects_root=[str(tmp_path)], overlay=None, project=None)
    assert cli._link_all(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("duplicate manifest identity 'same'") == 2


def test_link_status_all_rejects_a_named_project():
    args = SimpleNamespace(
        link_command="status",
        all=True,
        project="named",
        root=".",
        overlay=None,
        projects_root=[],
    )
    with pytest.raises(cli.RegistryError, match="mutually exclusive"):
        cli._link_command(args, object())
