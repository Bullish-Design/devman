# tests/test_schemas.py
from pathlib import Path

from devman.schemas.questions import (
    StrQuestion,
    BoolQuestion,
    ChoiceQuestion,
    IntQuestion,
)
from devman.schemas.tasks import Task, TaskList
from devman.schemas import CopierConfig


# --- Question Tests ---

def test_str_question_basic():
    q = StrQuestion(type="str", help="Enter name")
    assert q.type == "str"
    assert q.help == "Enter name"
    assert q.default is None


def test_bool_question_with_default():
    q = BoolQuestion(type="bool", help="Use feature?", default=True)
    assert q.type == "bool"
    assert q.default is True


def test_choice_question_with_list():
    q = ChoiceQuestion(
        type="str",
        help="Select version",
        choices=["3.11", "3.12", "3.13"],
        default="3.13",
    )
    assert len(q.choices) == 3
    assert q.default == "3.13"


def test_choice_question_with_dict():
    q = ChoiceQuestion(
        type="str",
        help="Select license",
        choices={"mit": "MIT License", "apache": "Apache 2.0"},
    )
    assert isinstance(q.choices, dict)


def test_question_with_validator():
    q = StrQuestion(
        type="str",
        help="Enter email",
        validator=r"^[\w\.-]+@[\w\.-]+\.\w+$",
    )
    assert q.validator is not None


def test_question_with_when_condition():
    q = StrQuestion(
        type="str",
        help="Docker image",
        when="{{ use_docker }}",
    )
    assert q.when == "{{ use_docker }}"


def test_int_question():
    q = IntQuestion(type="int", help="Port number", default=8080)
    assert q.type == "int"
    assert q.default == 8080


# --- Task Tests ---

def test_task_simple_command():
    task = Task(command="echo 'Hello'")
    assert task.command == "echo 'Hello'"
    assert task.when is None


def test_task_with_condition():
    task = Task(
        command=["pip", "install", "-e", "."],
        when="{{ use_editable_install }}",
    )
    assert isinstance(task.command, list)
    assert task.when is not None


def test_task_list_from_strings():
    tasks = TaskList.from_strings([
        "git init",
        "echo 'Setup complete'",
    ])
    assert len(tasks.tasks) == 2
    assert tasks.tasks[0].command == "git init"


def test_task_list_to_yaml_format_simple():
    tasks = TaskList.from_strings(["echo 'test'"])
    yaml_format = tasks.to_yaml_format()
    assert yaml_format == ["echo 'test'"]


def test_task_list_to_yaml_format_conditional():
    tasks = TaskList(tasks=[
        Task(command="git init"),
        Task(command="npm install", when="{{ use_npm }}"),
    ])
    yaml_format = tasks.to_yaml_format()
    assert len(yaml_format) == 2
    assert yaml_format[0] == "git init"
    assert yaml_format[1]["command"] == "npm install"
    assert yaml_format[1]["when"] == "{{ use_npm }}"


# --- CopierConfig Tests ---

def test_copier_config_from_yaml_file(tmp_path: Path):
    yaml_content = """
_subdirectory: template
_templates_suffix: .jinja

project_name:
  type: str
  help: Project name

use_docker:
  type: bool
  default: false
"""
    yaml_file = tmp_path / "copier.yaml"
    yaml_file.write_text(yaml_content)

    config = CopierConfig.from_yaml_file(yaml_file)

    assert config.subdirectory == "template"
    assert config.templates_suffix == ".jinja"
    assert "project_name" in config.questions
    assert "use_docker" in config.questions


def test_copier_config_to_yaml_file(tmp_path: Path):
    config = CopierConfig(
        subdirectory="src",
        templates_suffix=".j2",
        questions={
            "name": {"type": "str", "help": "Name"},
        },
        tasks=["echo 'done'"],
    )

    output_file = tmp_path / "output.yaml"
    config.to_yaml_file(output_file)

    assert output_file.exists()

    # Verify round-trip
    reloaded = CopierConfig.from_yaml_file(output_file)
    assert reloaded.subdirectory == "src"
    assert reloaded.templates_suffix == ".j2"


def test_copier_config_validate_questions():
    config = CopierConfig(
        questions={
            "valid": {"type": "str", "help": "Valid"},
            "invalid": "not a dict",
            "missing_type": {"help": "No type"},
        }
    )

    errors = config.validate_questions()

    assert "valid" not in errors
    assert "invalid" in errors
    assert "missing_type" in errors


def test_example_fixture_parsing():
    fixture_path = Path("tests/fixtures/copier.yaml")
    config = CopierConfig.from_yaml_file(fixture_path)

    assert config.subdirectory == "template"
    assert config.templates_suffix == ".jinja"
    assert "project_name" in config.questions
    assert "python_version" in config.questions
    assert len(config.tasks) > 0
