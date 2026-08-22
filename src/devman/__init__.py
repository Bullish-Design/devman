"""devman — the automation plane's CLI (CONCEPT.md §10).

It reads the registry, resolves a project, and triggers a workflow through a
local `dagu enqueue`. It executes nothing itself: every command the plane runs
is a devenv task in the repository that owns it (§2, §6).
"""

__version__ = "0.3.0"
