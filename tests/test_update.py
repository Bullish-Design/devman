from datetime import datetime
from pathlib import Path
import sys
import types

import tomli

sys.modules.setdefault("tomllib", tomli)
sys.modules.setdefault("tomli_w", types.SimpleNamespace(dump=lambda *args, **kwargs: None))

from devman.update import update_file_type, update_project


def _dump_minimal_toml(data: dict, file_obj) -> None:
    for section, values in data.items():
        file_obj.write(f"[{section}]\n".encode("utf-8"))
        for key, value in values.items():
            file_obj.write(f'{key} = "{value}"\n'.encode("utf-8"))
from devman.constants import CONFIG_SUBPATH
from devman.update import update_file_type


def test_update_file_type_returns_full_payload_for_no_op(monkeypatch, tmp_path: Path) -> None:
    store_root = tmp_path / ".devman-store"
    type_path = store_root / "pyproject.toml"
    config_path = type_path / CONFIG_SUBPATH
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "[template]\n"
        'devman_version = "v1.2.3"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    result = update_file_type("pyproject.toml", target_version="v1.2.3", dry_run=True)

    assert result == {
        "success": True,
        "message": "Already at version v1.2.3",
        "current_version": "v1.2.3",
        "target_version": "v1.2.3",
        "changes": [],
        "dry_run": True,
    }


def test_update_file_type_writes_timezone_aware_updated_at(monkeypatch, tmp_path: Path) -> None:
    store_root = tmp_path / ".devman-store"
    type_path = store_root / "pyproject.toml"
    config_path = type_path / ".devman" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "[template]\n"
        'devman_version = "v1.2.2"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        "devman.update.run_checked_subprocess",
        lambda *args, **kwargs: types.SimpleNamespace(stdout="updated"),
    )
    monkeypatch.setattr("devman.update.tomli_w.dump", _dump_minimal_toml)

    update_file_type("pyproject.toml", target_version="v1.2.3", dry_run=False)

    config = tomli.loads(config_path.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(config["template"]["updated_at"]).tzinfo is not None


def test_update_project_writes_timezone_aware_updated_at(monkeypatch, tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    metadata_file = project_path / ".devman-project.toml"
    metadata_file.write_text(
        "[template]\n"
        'name = "pyproj"\n'
        'version = "v1.2.2"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "devman.update.run_checked_subprocess",
        lambda *args, **kwargs: types.SimpleNamespace(stdout="updated"),
    )
    monkeypatch.setattr("devman.update.tomli_w.dump", _dump_minimal_toml)

    update_project(project_path, target_version="v1.2.3", dry_run=False)

    metadata = tomli.loads(metadata_file.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(metadata["template"]["updated_at"]).tzinfo is not None
