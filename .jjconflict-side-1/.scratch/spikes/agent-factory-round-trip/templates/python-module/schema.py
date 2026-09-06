"""Typed input for the spike's deterministic module renderer."""

from pydantic import BaseModel, ConfigDict


class PythonModuleModel(BaseModel):
    """Validated ordered sections for one Python module."""

    model_config = ConfigDict(extra="forbid")

    sections: list[str]
