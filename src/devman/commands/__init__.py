"""Command handlers for devman operations."""

from .bootstrap import bootstrap
from .doctor import doctor
from .down import down
from .index import index_list, index_rebuild, index_status
from .init import init
from .switch import switch
from .up import up

__all__ = [
    "bootstrap",
    "doctor",
    "down",
    "index_list",
    "index_rebuild",
    "index_status",
    "init",
    "switch",
    "up",
]
