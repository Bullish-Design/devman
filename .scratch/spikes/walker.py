"""Out-of-process fact walker. Runs under ANY python that can import the tool."""
import importlib, json, sys

def walk(app, prefix=""):
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

mod, attr = sys.argv[1], sys.argv[2]
try:
    app = getattr(importlib.import_module(mod), attr)
    print(json.dumps({"ok": True, "commands": sorted(walk(app))}))
except BaseException as e:
    print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
    sys.exit(1)
