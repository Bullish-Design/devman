"""Fact walker v3 — cross-version safe.

Runs under ANY interpreter that can import the target tool.

Two traps this avoids, both found by spike:
  1. typer >= ~0.16 vendors click as the private `typer._click`. A top-level
     `click` may be absent, or present but a DIFFERENT click than typer uses.
  2. Therefore `isinstance(cmd, click.Group)` is unreliable — it returns False
     for a real TyperGroup. Duck-type instead.
"""
import importlib, json, sys

def describe(app):
    import typer
    root = typer.main.get_command(app)
    out = {}

    def is_group(c):
        return isinstance(getattr(c, "commands", None), dict)

    def visit(c, path):
        name = " ".join(path)
        if is_group(c):
            if name:
                out[name] = {"kind": "group", "children": sorted(c.commands)}
            for sub, sc in c.commands.items():
                visit(sc, path + [sub])
        else:
            pos, opts = [], set()
            for p in getattr(c, "params", []):
                kind = getattr(p, "param_type_name", None)
                if kind == "argument":
                    pos.append(p.name)
                elif kind == "option":
                    opts.update(getattr(p, "opts", []))
            out[name] = {"kind": "leaf", "positional": pos,
                         "options": sorted(opts)}
    visit(root, [])
    return out

mod, attr = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "app")
try:
    app = getattr(importlib.import_module(mod), attr)
    typer = importlib.import_module("typer")
    print(json.dumps({"ok": True, "typer": typer.__version__,
                      "commands": describe(app)}, indent=2))
except BaseException as e:
    print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
    sys.exit(1)
