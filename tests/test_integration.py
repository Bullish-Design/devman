# tests/test_integration.py
"""Integration tests for the complete template workflow."""

from pathlib import Path
from typer.testing import CliRunner

from devman.cli import app
from devman.schemas import CopierConfig


def test_full_workflow_local_template(tmp_path: Path):
    """Test complete workflow: create template, validate, instantiate."""

    # Step 1: Create a template
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    template_content_dir = template_dir / "template"
    template_content_dir.mkdir()

    # Create copier.yaml
    config = CopierConfig(
        subdirectory="template",
        templates_suffix=".jinja",
        questions={
            "project_name": {
                "type": "str",
                "default": "my_project",
            },
        },
        tasks=["echo 'Created {{ project_name }}'"],
    )
    config.to_yaml_file(template_dir / "copier.yaml")

    # Create template file (with .jinja suffix so copier renders it)
    (template_content_dir / "README.md.jinja").write_text("# {{ project_name }}")

    # Step 2: Validate template
    from devman.templates import TemplateReference, TemplateValidator

    ref = TemplateReference(source_type="file", location=str(template_dir))
    issues = TemplateValidator.validate(ref)

    assert len(issues["errors"]) == 0

    # Step 3: Instantiate via CLI
    dest_dir = tmp_path / "new_project"

    runner = CliRunner()
    result = runner.invoke(app, [
        "new",
        str(template_dir),
        str(dest_dir),
        "--data", "project_name=TestProject",
    ])

    assert result.exit_code == 0
    assert dest_dir.exists()

    # Step 4: Verify instantiated content
    readme = dest_dir / "README.md"
    assert readme.exists()
    assert "# TestProject" in readme.read_text()


def test_round_trip_copier_yaml(tmp_path: Path):
    """Test that copier.yaml can be loaded and saved without data loss."""

    original_yaml = tmp_path / "original.yaml"
    config = CopierConfig(
        subdirectory="src",
        templates_suffix=".j2",
        skip_if_exists=["README.md"],
        questions={
            "name": {"type": "str", "help": "Name"},
            "version": {"type": "str", "default": "0.1.0"},
        },
        tasks=["git init"],
    )
    config.to_yaml_file(original_yaml)

    # Reload and save again
    loaded = CopierConfig.from_yaml_file(original_yaml)
    resaved_yaml = tmp_path / "resaved.yaml"
    loaded.to_yaml_file(resaved_yaml)

    # Content should be equivalent
    assert original_yaml.read_text() == resaved_yaml.read_text()


def test_example_fixture_is_valid():
    """Ensure example fixture is valid and can be used."""
    fixture_path = Path("tests/fixtures")

    from devman.templates import TemplateValidator

    issues = TemplateValidator.validate_structure(fixture_path)

    assert len(issues["errors"]) == 0, f"Fixture has errors: {issues['errors']}"
