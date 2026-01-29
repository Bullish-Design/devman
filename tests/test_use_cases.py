# tests/test_use_cases.py
from pathlib import Path

from result import Ok

from devman.application.use_cases import (
    FindDevmanCommand,
    FindDevmanUseCase,
    RunDevenvCommand,
    RunDevenvUseCase,
    ValidateTemplateCommand,
    ValidateTemplateUseCase,
)
from devman.domain.models import DevmanDirectory, ProjectRoot
from devman.domain.protocols import CommandResult, CommandError
from devman.domain.templates import TemplateReference


def test_find_devman_use_case_success(tmp_path: Path):
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()

    use_case = FindDevmanUseCase()
    command = FindDevmanCommand(start_path=tmp_path)
    result = use_case.execute(command)

    assert result.is_ok()
    assert result.unwrap().devman_directory.path == devman_dir


def test_find_devman_use_case_not_found(tmp_path: Path):
    use_case = FindDevmanUseCase()
    command = FindDevmanCommand(start_path=tmp_path)
    result = use_case.execute(command)

    assert result.is_err()


def test_validate_template_use_case(tmp_path: Path):
    fixture = Path("tests/fixtures")
    template_ref = TemplateReference(source_type="file", location=str(fixture))

    use_case = ValidateTemplateUseCase()
    command = ValidateTemplateCommand(template_reference=template_ref)
    result = use_case.execute(command)

    assert result.is_valid


class FakeExecutor:
    """Fake CommandExecutor for testing."""

    def __init__(self, result):
        self._result = result

    def execute(self, args, cwd=None):
        return self._result


def test_run_devenv_use_case_with_injected_executor(tmp_path: Path):
    devman_dir = tmp_path / ".devman"
    devman_dir.mkdir()

    fake = FakeExecutor(Ok(CommandResult(exit_code=0, stdout="ok")))
    use_case = RunDevenvUseCase(executor=fake)
    command = RunDevenvCommand(
        devenv_args=["up"],
        devman_directory=DevmanDirectory(path=devman_dir),
    )
    result = use_case.execute(command)

    assert result.is_ok()
    assert result.unwrap().exit_code == 0
