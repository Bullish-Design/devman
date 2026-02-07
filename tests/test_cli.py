from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from devman.cli import app


runner = CliRunner()


def test_instantiate_command_runs_copier_path_resolution(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def fake_from_toml_file(config_path: Path) -> object:
        calls["config_path"] = config_path
        return SimpleNamespace()

    def fake_resolve_template_path(template: str, config: object) -> Path:
        calls["template"] = template
        calls["config"] = config
        return tmp_path / "templates" / template

    def fake_run_copier_instantiation(template_path: Path, target_path: Path) -> None:
        calls["template_path"] = template_path
        calls["target_path"] = target_path

    monkeypatch.setattr(
        "devman.watcher.config.DevmanWatchConfig.from_toml_file",
        fake_from_toml_file,
    )
    monkeypatch.setattr(
        "devman.watcher.handlers.resolve_template_path",
        fake_resolve_template_path,
    )
    monkeypatch.setattr(
        "devman.watcher.handlers.run_copier_instantiation",
        fake_run_copier_instantiation,
    )

    config_path = tmp_path / "devman-watch.toml"
    target_path = tmp_path / "output"
    result = runner.invoke(
        app,
        ["instantiate", "module-template", str(target_path), "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "Generated template" in result.stdout
    assert calls["config_path"] == config_path.resolve()
    assert calls["template"] == "module-template"
    assert calls["template_path"] == tmp_path / "templates" / "module-template"
    assert calls["target_path"] == target_path.resolve()


def test_instantiate_command_handles_missing_config(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    result = runner.invoke(app, ["instantiate", "module-template", str(tmp_path / "out"), "--config", str(missing)])

    assert result.exit_code == 1
    assert "Watch config not found" in result.stdout
