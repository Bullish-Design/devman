# src/devman/schemas/questions.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BaseQuestion(BaseModel):
    """Base class for all copier question types."""

    type: str
    help: str | None = None
    default: Any | None = None
    when: str | bool | None = None  # Jinja2 condition or boolean
    validator: str | None = None  # Regex pattern
    placeholder: str | None = None
    multiline: bool | None = None


class StrQuestion(BaseQuestion):
    """String input question."""

    type: Literal["str"] = "str"
    default: str | None = None
    multiline: bool = False


class IntQuestion(BaseQuestion):
    """Integer input question."""

    type: Literal["int"] = "int"
    default: int | None = None


class FloatQuestion(BaseQuestion):
    """Float input question."""

    type: Literal["float"] = "float"
    default: float | None = None


class BoolQuestion(BaseQuestion):
    """Boolean yes/no question."""

    type: Literal["bool"] = "bool"
    default: bool = False


class ChoiceQuestion(BaseQuestion):
    """Multiple choice question."""

    type: Literal["str"] = "str"
    choices: list[str] | dict[str, str] = Field(default_factory=list)
    default: str | None = None


class YamlQuestion(BaseQuestion):
    """YAML-structured input question."""

    type: Literal["yaml"] = "yaml"
    default: dict[str, Any] | list[Any] | None = None


class JsonQuestion(BaseQuestion):
    """JSON-structured input question."""

    type: Literal["json"] = "json"
    default: dict[str, Any] | list[Any] | None = None


# Type alias for all question types
Question = (
    StrQuestion
    | IntQuestion
    | FloatQuestion
    | BoolQuestion
    | ChoiceQuestion
    | YamlQuestion
    | JsonQuestion
)
