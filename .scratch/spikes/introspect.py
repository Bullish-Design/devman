"""Spike B: can devman introspect family CLI facts by walking the Typer app?"""
import importlib, json, sys

TARGETS = [
    ("copyroom", "copyroom.cli", "app"),
    ("gitman",   "gitman.cli",   "app"),
    ("docman",   "docman.cli",   "app"),
    ("repoman",  "repoman.cli",  "app"),
    ("testee",   "testee.cli",   "app"),
]

def walk(app, prefix=""):
    """Return command names from a typer.Typer instance, recursing into groups."""
    out = []
    for info in getattr(app, "registered_commands", []):
        name = info.name or (info.callback.__name__.replace("_", "-") if info.callback else "?")
        out.append(f"{prefix}{name}")
    for grp in getattr(app, "registered_groups", []):
        gname = grp.name or (grp.typer_instance.info.name if grp.typer_instance else "?")
        out.append(f"{prefix}{gname}")
        if grp.typer_instance is not None:
            out.extend(walk(grp.typer_instance, prefix=f"{prefix}{gname} "))
    return out

report = {}
for tool, mod, attr in TARGETS:
    entry = {"module": mod}
    try:
        m = importlib.import_module(mod)
        app = getattr(m, attr)
        cmds = sorted(walk(app))
        entry["ok"] = True
        entry["count"] = len(cmds)
        entry["commands"] = cmds
    except BaseException as e:
        entry["ok"] = False
        entry["error"] = f"{type(e).__name__}: {e}"
    report[tool] = entry

print(json.dumps(report, indent=2))
