# src/devman/schemas/tasks.py
from __future__ import annotations


from pydantic import BaseModel


class Task(BaseModel):
    """Represents a copier pre/post-copy task."""

    command: str | list[str]
    when: str | bool | None = None  # Jinja2 condition


class TaskList(BaseModel):
    """Container for multiple tasks."""

    tasks: list[Task]

    @classmethod
    def from_strings(cls, task_strings: list[str]) -> TaskList:
        """Convert list of command strings to Task objects."""
        return cls(tasks=[Task(command=cmd) for cmd in task_strings])

    def to_yaml_format(self) -> list[str | dict]:
        """Convert to copier.yaml format (list of strings or dicts)."""
        result = []
        for task in self.tasks:
            if task.when is None:
                result.append(task.command)
            else:
                # Dict format with when condition
                result.append(
                    {
                        "command": task.command,
                        "when": task.when,
                    }
                )
        return result
