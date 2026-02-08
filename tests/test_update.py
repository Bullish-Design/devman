from pathlib import Path
import sys
import types

import tomli

sys.modules.setdefault("tomllib", tomli)
sys.modules.setdefault("tomli_w", types.SimpleNamespace(dump=lambda *args, **kwargs: None))

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
