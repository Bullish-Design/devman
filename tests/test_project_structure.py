# tests/test_project_structure.py
from pathlib import Path


def test_schemas_module_exists():
    schemas_init = Path("src/devman/schemas/__init__.py")
    assert schemas_init.exists()


def test_fixture_yaml_exists():
    fixture = Path("tests/fixtures/copier.yaml")
    assert fixture.exists()


def test_copier_importable():
    import copier
    assert copier.__version__
