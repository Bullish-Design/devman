"""Unsafe comparison schema with source and ordinary strings."""

from pydantic import BaseModel, ConfigDict


class MixedModel(BaseModel):
    """Mix source and ordinary data under identity escaping."""

    model_config = ConfigDict(extra="forbid")

    label: str
    section: str
