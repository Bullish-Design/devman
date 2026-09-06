"""Probe schema with a validated Python source-fragment field."""

import ast
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def validate_python_fragment(value: str) -> str:
    """Require one syntactically valid Python module fragment."""

    try:
        ast.parse(value)
    except SyntaxError as error:
        raise ValueError(
            f"invalid Python fragment at {error.lineno}:{error.offset}: {error.msg}"
        ) from error
    return value


PythonFragment = Annotated[str, AfterValidator(validate_python_fragment)]


class PythonModuleModel(BaseModel):
    """Ordered validated Python module fragments."""

    model_config = ConfigDict(extra="forbid")

    sections: list[PythonFragment]
