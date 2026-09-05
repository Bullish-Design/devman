"""The command surface, and the one import that is no longer eager.

`cli.py` imports four of its five handler modules at the top of the file and
`doctor` inside `handler()`. That is a measured saving — 52 ms of every devman
process, and the dispatch path used to start two — and it costs one property:
an import error in `doctor.py` no longer reaches anybody who runs any OTHER
command. These tests are what pay that back.
"""

from __future__ import annotations

import importlib

import pytest

from devman import cli

pytestmark = pytest.mark.unit

SUBCOMMANDS = ("run", "show", "doctor", "watch", "project")


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_every_subcommand_module_imports(command):
    """**The check the eager import used to be.**

    `from . import doctor` at the top of `cli.py` meant `devman --help` proved
    that `doctor.py` at least imports. Deferring it moved that proof here, where
    it is stated rather than incidental — and where it covers all five rather
    than the four that happen to be spelled in one line.
    """
    assert importlib.import_module(f"devman.{command}") is not None


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
