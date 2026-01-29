# src/devman/schemas/questions.py
from __future__ import annotations

from typing import Annotated, Any, Literal

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

    type: Literal["choice"] = "choice"
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


# With distinct type values, we can now use Pydantic discriminated unions.
Question = Annotated[
    StrQuestion
    | IntQuestion
    | FloatQuestion
    | BoolQuestion
    | ChoiceQuestion
    | YamlQuestion
    | JsonQuestion,
    Field(discriminator="type"),
]


def parse_question(name: str, spec: dict[str, Any]) -> Question:
    """
    Parse raw question dict into typed Question object.

    Uses the 'type' field to select the correct Question class.
    For backward compatibility, type="str" with a "choices" key
    is automatically upgraded to type="choice".

    Raises:
        ValueError: If spec cannot be parsed into a known question type
    """
    if not isinstance(spec, dict):
        raise ValueError(
            f"Question '{name}' must be a dictionary, got {type(spec).__name__}"
        )

    q_type = spec.get("type", "str")

    # Backward compatibility: str + choices -> choice
    if q_type == "str" and "choices" in spec:
        spec = {**spec, "type": "choice"}
        return ChoiceQuestion(**spec)

    type_map: dict[str, type[BaseQuestion]] = {
        "str": StrQuestion,
        "int": IntQuestion,
        "float": FloatQuestion,
        "bool": BoolQuestion,
        "choice": ChoiceQuestion,
        "yaml": YamlQuestion,
        "json": JsonQuestion,
    }

    cls = type_map.get(q_type)
    if cls is None:
        raise ValueError(f"Question '{name}' has unknown type: {q_type}")

    return cls(**spec)
