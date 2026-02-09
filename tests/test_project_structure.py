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


def test_seed_templates_include_devenv_and_python() -> None:
    seed_templates_dir = Path("src/devman/seed_templates")

    assert (seed_templates_dir / "devenv.nix" / "copier.yml").exists()
    assert (seed_templates_dir / "python" / "copier.yml").exists()


def test_python_seed_template_structure() -> None:
    python_template = Path("src/devman/seed_templates/python/{{project_name}}")
    expected_paths = (
        ".devman-project.toml.jinja",
        "README.md.jinja",
        "Justfile.jinja",
        "pyproject.toml.jinja",
        "devenv.nix.jinja",
        "src/{{package_name}}/__init__.py.jinja",
        "src/{{package_name}}/__main__.py.jinja",
    )

    for rel_path in expected_paths:
        assert (python_template / rel_path).exists()


def test_copier_importable():
    import copier
    assert copier.__version__
