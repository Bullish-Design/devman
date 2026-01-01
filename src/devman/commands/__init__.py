"""Command handlers for devman operations."""

from .bootstrap import bootstrap
from .doctor import doctor
from .down import down
from . import index
from .init import init
from .switch import switch
from . import up

__all__ = [
    "bootstrap",
    "doctor",
    "down",
    "index",
    "init",
    "switch",
    "up",
]
