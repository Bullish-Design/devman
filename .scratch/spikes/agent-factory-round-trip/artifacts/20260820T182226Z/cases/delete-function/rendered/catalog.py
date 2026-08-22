"""Provide a small searchable catalog."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LIMIT = 10


def normalize_name(value: str) -> str:
    """Return a normalized catalog name."""
    return " ".join(value.strip().lower().split())


@dataclass(frozen=True, slots=True)
class Catalog:
    """Hold normalized catalog entries."""

    entries: list[str]

    def find(self, prefix: str) -> list[str]:
        """Return entries that start with a normalized prefix."""
        wanted = normalize_name(prefix)
        return [entry for entry in self.entries if entry.startswith(wanted)]

    def names(self) -> tuple[str, ...]:
        """Return all catalog names."""
        return tuple(self.entries)

    def require(self, name: str) -> str:
        """Return one entry or raise KeyError."""
        wanted = normalize_name(name)
        for entry in self.entries:
            if entry == wanted:
                return entry
        raise KeyError(wanted)
