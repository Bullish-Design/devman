"""mancore step 7, Fix 1: `_link_reconcile_with_linkman`'s own int return.

It used to mirror linkman's old, retired 10-13 numbering (`13` failed, `11`
refused) instead of mancore's `0/1/2/130` contract. linkman's own `Exit`
enum collapsed both onto `REFUSAL = PARTIAL = DRIFT = 1` at its step 2
migration, so devman's wrapper now returns `1` for both.

Calling `_link_reconcile_with_linkman` imports `devman.linking`, which
imports `linkman`, which needs `pydantic` — not in the dependency list
`base:unit` hands its hermetic interpreter (see `test_linking.py`'s own
docstring). This module skips there and runs for real in the dev venv
(`uv sync --extra cutover`).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("linkman")

import devman.linking as linking  # noqa: E402
from devman import cli  # noqa: E402

pytestmark = pytest.mark.unit


def _args(tmp_path):
    return SimpleNamespace(root=tmp_path, overlay=None, project=None, json=False)


def _fake_result(*, applied=(), refused=(), failed=()):
    apply_result = SimpleNamespace(
        applied=list(applied), refused=list(refused), failed=list(failed)
    )
    return linking.LinkingResult(
        identity=SimpleNamespace(project="demo"), apply_result=apply_result
    )


def test_clean_run_exits_0(monkeypatch, tmp_path):
    monkeypatch.setattr(
        linking, "reconcile_with_linkman", lambda *_a, **_k: _fake_result()
    )
    assert cli._link_reconcile_with_linkman(_args(tmp_path)) == 0


def test_refused_only_exits_1(monkeypatch, tmp_path):
    refusal = SimpleNamespace(link_rel="envrc")
    monkeypatch.setattr(
        linking,
        "reconcile_with_linkman",
        lambda *_a, **_k: _fake_result(refused=[refusal]),
    )
    assert cli._link_reconcile_with_linkman(_args(tmp_path)) == 1


def test_failed_exits_1(monkeypatch, tmp_path):
    failure = SimpleNamespace(link_rel="envrc", message="boom")
    monkeypatch.setattr(
        linking,
        "reconcile_with_linkman",
        lambda *_a, **_k: _fake_result(failed=[failure]),
    )
    assert cli._link_reconcile_with_linkman(_args(tmp_path)) == 1
