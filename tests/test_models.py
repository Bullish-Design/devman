# tests/test_models.py
from __future__ import annotations
import pytest
from pathlib import Path

from devman.models import ProjectConfig, TemplateEngine, GenerationPlan, FileSnapshot
from devman.exceptions import InvalidProjectNameError, TemplateNotFoundError


class TestProjectConfig:
    """Test ProjectConfig validation and behavior."""

    def test_valid_config(self):
        """Test creating a valid project config."""
        config = ProjectConfig(project_name="my-awesome-lib")
        assert config.project_slug == "my-awesome-lib"
        assert config.package_name == "my_awesome_lib"
        assert config.python_version == "3.11"
        assert config.use_nix is True

    def test_custom_package_name(self):
        """Test using a custom package name."""
        config = ProjectConfig(project_name="my-project", package_name="custom_package")
        assert config.project_slug == "my-project"
        assert config.package_name == "custom_package"

    def test_slug_generation(self):
        """Test automatic slug generation from project name."""
        config = ProjectConfig(project_name="My-Cool-Project")  # Valid format
        assert config.project_slug == "my-cool-project"
        assert config.package_name == "my_cool_project"

    def test_invalid_project_name_empty(self):
        """Test that empty project names are rejected."""
        with pytest.raises(InvalidProjectNameError, match="Project name cannot be empty"):
            ProjectConfig(project_name="")

    def test_invalid_project_name_format(self):
        """Test that invalid project name formats are rejected."""
        with pytest.raises(InvalidProjectNameError, match="Project name must start"):
            ProjectConfig(project_name="123-invalid")

    def test_invalid_project_name_reserved(self):
        """Test that reserved names are rejected."""
        with pytest.raises(InvalidProjectNameError, match="reserved"):
            ProjectConfig(project_name="python")

    def test_invalid_python_version(self):
        """Test that invalid Python versions are rejected."""
        with pytest.raises(InvalidProjectNameError, match="Python version must be"):
            ProjectConfig(project_name="valid-project", python_version="2.7")

    def test_invalid_package_name(self):
        """Test that invalid package names are rejected."""
        with pytest.raises(InvalidProjectNameError, match="Package name must"):
            ProjectConfig(project_name="valid-project", package_name="123invalid")


class TestFileSnapshot:
    """Test FileSnapshot model."""

    def test_text_snapshot(self):
        """Test creating a text file snapshot."""
        content = "print('hello world')"
        snapshot = FileSnapshot(content=content, size=len(content), is_binary=False)
        assert snapshot.content == content
        assert snapshot.size == len(content)
        assert not snapshot.is_binary

    def test_binary_snapshot(self):
        """Test creating a binary file snapshot."""
        snapshot = FileSnapshot(content="<binary file: 1024 bytes>", size=1024, is_binary=True)
        assert snapshot.is_binary
        assert snapshot.size == 1024


class TestGenerationPlan:
    """Test GenerationPlan functionality."""

    def test_empty_plan(self, tmp_path):
        """Test creating an empty generation plan."""
        plan = GenerationPlan(destination=tmp_path / "test", template_path="/tmp/template", files={})
        assert plan.destination == tmp_path / "test"
        assert len(plan.files) == 0
        assert len(plan.conflicts) == 0

    def test_conflict_detection(self, tmp_path):
        """Test conflict detection with existing files."""
        # Create existing file
        existing_file = tmp_path / "existing.txt"
        existing_file.write_text("existing content")

        # Create plan with conflicting file
        files = {
            "existing.txt": FileSnapshot(content="new content", size=11, is_binary=False),
            "new.txt": FileSnapshot(content="new file", size=8, is_binary=False),
        }

        plan = GenerationPlan(destination=tmp_path, template_path="/tmp/template", files=files)

        conflicts = plan.analyze_conflicts(force=False)
        assert "existing.txt" in conflicts
        assert "new.txt" not in conflicts
        assert len(conflicts) == 1

    def test_no_conflicts_with_force(self, tmp_path):
        """Test that force mode ignores conflicts."""
        # Create existing file
        existing_file = tmp_path / "existing.txt"
        existing_file.write_text("existing content")

        files = {"existing.txt": FileSnapshot(content="new content", size=11, is_binary=False)}

        plan = GenerationPlan(destination=tmp_path, template_path="/tmp/template", files=files)

        conflicts = plan.analyze_conflicts(force=True)
        assert len(conflicts) == 0

    def test_get_summary(self, tmp_path):
        """Test generation plan summary."""
        files = {
            "file1.txt": FileSnapshot(content="content1", size=8, is_binary=False),
            "file2.txt": FileSnapshot(content="content2", size=8, is_binary=False),
        }

        plan = GenerationPlan(destination=tmp_path / "test", template_path="/tmp/template", files=files)

        summary = plan.get_summary()
        assert summary["total_files"] == 2
        assert summary["conflicts"] == 0
        assert str(tmp_path / "test") in summary["destination"]


class TestTemplateEngine:
    """Test TemplateEngine functionality."""

    @pytest.fixture
    def minimal_template(self, tmp_path):
        """Create a minimal test template."""
        template_dir = tmp_path / "test-template"
        template_dir.mkdir()

        # Create copier.yml - ADD _templates_suffix
        (template_dir / "copier.yml").write_text("""
_templates_suffix: .j2

project_name:
  type: str
  help: Project name

python_version:
  type: str
  default: "3.11"
""")

        # Create a simple template file
        (template_dir / "README.md.j2").write_text("""
# {{ project_name }}

This is a {{ project_name }} project using Python {{ python_version }}.
""")

        # Create a Python file template
        (template_dir / "src" / "{{ project_slug }}" / "__init__.py.j2").parent.mkdir(parents=True)
        (template_dir / "src" / "{{ project_slug }}" / "__init__.py.j2").write_text("""
\"\"\"{{ project_name }} package.\"\"\"
__version__ = "0.1.0"
""")

        return template_dir

    def test_template_validation_success(self, minimal_template):
        """Test successful template validation."""
        engine = TemplateEngine()
        # Should not raise any exceptions
        validated_path = engine._validate_template_path(minimal_template)
        assert validated_path == minimal_template

    def test_template_validation_missing(self, tmp_path):
        """Test template validation with missing template."""
        engine = TemplateEngine()
        missing_path = tmp_path / "nonexistent"

        with pytest.raises(TemplateNotFoundError):
            engine._validate_template_path(missing_path)

    def test_create_plan(self, minimal_template, tmp_path):
        """Test creating a generation plan."""
        engine = TemplateEngine()
        config = ProjectConfig(project_name="test-project", python_version="3.11")
        destination = tmp_path / "output"

        plan = engine.create_plan(minimal_template, destination, config)

        # Check that files were generated
        assert len(plan.files) >= 2  # At least README.md and __init__.py
        assert "README.md" in plan.files

        # Check content substitution
        readme_content = plan.files["README.md"].content
        assert "test-project" in readme_content
        assert "Python 3.11" in readme_content

        # Check that no conflicts initially
        assert len(plan.conflicts) == 0

    def test_create_plan_with_conflicts(self, minimal_template, tmp_path):
        """Test plan creation with existing files."""
        # Create destination with existing file
        destination = tmp_path / "output"
        destination.mkdir()
        (destination / "README.md").write_text("existing readme")

        engine = TemplateEngine()
        config = ProjectConfig(project_name="test-project")

        plan = engine.create_plan(minimal_template, destination, config)

        # Should detect conflict
        assert "README.md" in plan.conflicts
        assert len(plan.conflicts) == 1

