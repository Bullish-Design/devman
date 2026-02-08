from pathlib import Path

from devman.constants import (
    CONFIG_SUBPATH,
    DEFAULT_INSTANCE_STORE,
    DEFAULT_TEMPLATE_STORE,
    DEVMAN_META_DIR_NAME,
    TEMPLATES_SUBPATH,
    get_config_file,
    get_devman_meta_dir,
    get_store_root,
    get_templates_dir,
)


def test_constants_compose_store_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    assert get_store_root() == tmp_path / ".devman-store"
    assert get_devman_meta_dir() == get_store_root() / DEVMAN_META_DIR_NAME
    assert get_templates_dir() == get_devman_meta_dir() / TEMPLATES_SUBPATH
    assert get_config_file() == get_devman_meta_dir() / CONFIG_SUBPATH

    assert DEFAULT_INSTANCE_STORE == "~/.devman-store/instances"
    assert DEFAULT_TEMPLATE_STORE == "~/.devman-store/devman/.devman/.templates"
