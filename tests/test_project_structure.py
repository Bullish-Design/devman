# tests/test_project_structure.py
from pathlib import Path


def test_schemas_module_exists():
    schemas_init = Path("src/devman/schemas/__init__.py")
    assert schemas_init.exists()


def test_fixture_yaml_exists():
    fixture = Path("tests/fixtures/copier.yaml")
    assert fixture.exists()


def test_watcher_package_exists():
    watcher_init = Path("src/devman/watcher/__init__.py")
    assert watcher_init.exists()


def test_watcher_modules_exist():
    watcher_dir = Path("src/devman/watcher")
    expected_modules = (
        "config.py",
        "engine.py",
        "handlers.py",
        "toml_gen.py",
    )

    for module in expected_modules:
        assert (watcher_dir / module).exists()


def test_copier_importable():
    import copier
    assert copier.__version__
