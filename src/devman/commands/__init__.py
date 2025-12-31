"""Command handlers for llm-core."""

from .doctor import run as doctor
from .up import run as up

__all__ = ["doctor", "up"]
