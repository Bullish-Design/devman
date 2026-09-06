"""Normalize catalog names."""

from __future__ import annotations


def normalize_name(value: str) -> str:
    """Return a normalized catalog name."""
    return " ".join(value.strip().lower().split())
