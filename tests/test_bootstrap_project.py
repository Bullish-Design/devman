from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import types

import pytest
import tomli

sys.modules.setdefault("tomllib", tomli)
sys.modules.setdefault("tomli_w", types.SimpleNamespace(dump=lambda *args, **kwargs: None))

from devman.bootstrap_project import _build_uv_run_command, _run_checked, bootstrap_project
from devman.constants import TEMPLATES_SUBPATH


def test_build_uv_run_command_uses_current_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/custom/python")

    cmd = _build_uv_run_command("copier", "copy")

    assert cmd == ["/custom/python", "-m", "uv", "run", "--python", "/custom/python", "copier", "copy"]


def test_run_checked_wraps_stderr_context(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(2, ["cmd"], stderr="failure from stderr\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match=r"Test command failed with exit code 2\. stderr: failure from stderr"):
        _run_checked(["cmd"], context="Test command")


def test_bootstrap_project_constructs_uv_commands_with_current_interpreter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "executable", "/runtime/python")
    monkeypatch.setattr("devman.bootstrap_project.Path.home", lambda: tmp_path)

    template_name = "python"
    template_root = tmp_path / ".devman-store" / "devman" / TEMPLATES_SUBPATH / template_name
    template_root.mkdir(parents=True)

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / ".devman-bootstrap.py").write_text("print('ok')", encoding="utf-8")

    calls: list[tuple[list[str], Path | None]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs.get("cwd")))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    bootstrap_project(template_name, target_dir, template_version="v1.2.3")

    assert calls[0][0][:6] == ["/runtime/python", "-m", "uv", "run", "--python", "/runtime/python"]
    assert calls[0][0][6:10] == ["copier", "copy", "--vcs-ref", "v1.2.3"]
    assert calls[0][0][-2:] == [str(template_root), str(target_dir)]

    assert calls[1][0] == [
        "/runtime/python",
        "-m",
        "uv",
        "run",
        "--python",
        "/runtime/python",
        str(target_dir / ".devman-bootstrap.py"),
    ]
    assert calls[1][1] == target_dir
