from pathlib import Path
from types import SimpleNamespace
import sys
import types

import tomli
from typer.testing import CliRunner

sys.modules.setdefault("tomllib", tomli)
sys.modules.setdefault("tomli_w", types.SimpleNamespace(dump=lambda *args, **kwargs: None))
sys.modules.setdefault("watchfiles", types.SimpleNamespace(Change=object, watch=lambda *args, **kwargs: iter(())))

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

    def fake_run_copier_instantiation(
        template_path: Path,
        target_path: Path,
        force: bool = False,
    ) -> None:
        calls["template_path"] = template_path
        calls["target_path"] = target_path
        calls["force"] = force

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
    assert calls["force"] is False



def test_instantiate_command_passes_force_flag(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def fake_from_toml_file(config_path: Path) -> object:
        return SimpleNamespace()

    def fake_resolve_template_path(template: str, config: object) -> Path:
        return tmp_path / "templates" / template

    def fake_run_copier_instantiation(
        template_path: Path,
        target_path: Path,
        force: bool = False,
    ) -> None:
        calls["force"] = force

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
        [
            "instantiate",
            "module-template",
            str(target_path),
            "--config",
            str(config_path),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert calls["force"] is True

def test_instantiate_command_handles_missing_config(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    result = runner.invoke(app, ["instantiate", "module-template", str(tmp_path / "out"), "--config", str(missing)])

    assert result.exit_code == 1
    assert "Watch config not found" in result.stdout


def test_watch_init_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    output_path = tmp_path / "devman-watch.toml"
    output_path.write_text("[settings]\ndebounce_ms = 123\n", encoding="utf-8")

    result = runner.invoke(app, ["watch-init", "--output", str(output_path)])

    assert result.exit_code == 1
    assert "Refusing to overwrite existing file" in result.stdout
    assert output_path.read_text(encoding="utf-8") == "[settings]\ndebounce_ms = 123\n"


def test_watch_init_force_overwrites_existing_file(tmp_path: Path) -> None:
    output_path = tmp_path / "devman-watch.toml"
    output_path.write_text("[settings]\ndebounce_ms = 123\n", encoding="utf-8")

    result = runner.invoke(app, ["watch-init", "--output", str(output_path), "--force"])

    assert result.exit_code == 0
    assert "Created starter config" in result.stdout
    generated = output_path.read_text(encoding="utf-8")
    assert 'name = "python-module"' in generated
    assert 'debounce_ms = 500' in generated


def test_update_command_no_op_file_type_renders_version_line(monkeypatch) -> None:
    def fake_update_file_type(file_type: str, target_version: str | None = None, dry_run: bool = False) -> dict:
        assert file_type == "pyproject.toml"
        assert target_version is None
        assert dry_run is False
        return {
            "success": True,
            "message": "Already at version v1.2.3",
            "current_version": "v1.2.3",
            "target_version": "v1.2.3",
            "changes": [],
            "dry_run": False,
        }

    fake_update_module = types.SimpleNamespace(
        update_file_type=fake_update_file_type,
        update_project=lambda *args, **kwargs: {"success": False},
    )
    monkeypatch.setitem(sys.modules, "devman.update", fake_update_module)

    result = runner.invoke(app, ["update", "pyproject.toml"])

    assert result.exit_code == 0
    assert "OK" in result.stdout
    assert "Updated: v1.2.3 -> v1.2.3" in result.stdout
    assert "Changes:" not in result.stdout



def test_watch_command_configures_logging_before_start(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def fake_from_toml_file(config_path: Path) -> object:
        calls["config_path"] = config_path
        return SimpleNamespace(settings=SimpleNamespace(log_level="DEBUG"), patterns=[])

    class FakeWatcher:
        def __init__(self, config: object, repo_root: Path) -> None:
            calls["watcher_config"] = config
            calls["repo_root"] = repo_root

        def run(self) -> None:
            calls["ran"] = True

    def fake_configure_watch_logging(level_name: str) -> None:
        calls["log_level"] = level_name

    monkeypatch.setattr(
        "devman.watcher.config.DevmanWatchConfig.from_toml_file",
        fake_from_toml_file,
    )
    monkeypatch.setattr("devman.watcher.engine.DevmanWatcher", FakeWatcher)
    monkeypatch.setattr("devman.cli._configure_watch_logging", fake_configure_watch_logging)

    config_path = tmp_path / "devman-watch.toml"
    result = runner.invoke(app, ["watch", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["config_path"] == config_path.resolve()
    assert calls["log_level"] == "DEBUG"
    assert calls["repo_root"] == Path.cwd()
    assert calls["ran"] is True


def test_configure_watch_logging_sets_level_and_does_not_duplicate_handlers() -> None:
    import logging

    from devman.cli import _configure_watch_logging

    logger = logging.getLogger("devman.watcher")
    original_handlers = list(logger.handlers)
    original_level = logger.level

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    try:
        _configure_watch_logging("warning")
        first_handlers = list(logger.handlers)
        assert logger.level == logging.WARNING
        assert len(first_handlers) == 1
        assert isinstance(first_handlers[0], logging.StreamHandler)
        assert first_handlers[0].formatter is not None

        _configure_watch_logging("error")
        second_handlers = list(logger.handlers)
        assert logger.level == logging.ERROR
        assert len(second_handlers) == 1
        assert second_handlers[0] is first_handlers[0]
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        for handler in original_handlers:
            logger.addHandler(handler)
        logger.setLevel(original_level)
