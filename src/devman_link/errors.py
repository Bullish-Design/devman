"""The refusals the link adapter shows a developer.

Every one of them names what is wrong and what to do about it. A refusal is the
point of the component: AGENTS.md law 4 prefers a loud refusal to a silent
default, because a run that reports success while linking the wrong file is the
failure the link plane exists to prevent.
"""

from __future__ import annotations


class LinkAdapterError(Exception):
    """The base refusal. A caller outside this package catches this one."""


class LinkError(LinkAdapterError):
    """A link-plane refusal that must be shown to the developer."""


class IdentityError(LinkAdapterError):
    """A repository does not state one usable project identity."""


class LinkConfigurationError(LinkAdapterError):
    """The central link declaration cannot be used safely."""
