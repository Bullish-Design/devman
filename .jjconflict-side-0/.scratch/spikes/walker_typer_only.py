"""ABANDONED. Click-free walker -- kept as measured evidence, do not use.

Avoids typer.main.get_command() to stay clear of click. It cannot be made
correct: it reimplements typer's own parameter resolution, and parity.py
showed it wrong in every round -- 43 discrepancies, then 13, then 6. The
final 6 are all cases where this file disagrees with the real --help and
the click route matches it exactly. See SPIKES.md spike B.
"""

import importlib, inspect, json, sys


def _params(callback):
    """Split a command callback's signature into positionals and options.

    Reimplements the parts of typer's parameter resolution devman needs. Four
    behaviours matter, and all four were found by parity.py rather than by
    reading code -- see SPIKES.md spike B:

      1. Two declaration styles coexist in the family.
           legacy     x: str = typer.Option("--x")      copyroom, repoman
           annotated  x: Annotated[str, typer.Option()] gitman, docman, testee
         Both may carry decls; merge them, do not pick one.
      2. Empty param_decls means typer derives the flag from the parameter
         name, stripping trailing underscores: all_ -> --all, not --all-.
      3. Short-only decls ('-r',) still get the derived long form.
      4. A bare annotated parameter with no default is a positional argument.
    """
    import typing
    from typer.models import ArgumentInfo, OptionInfo
    pos, opts = [], []
    if callback is None:
        return pos, opts
    try:
        hints = typing.get_type_hints(callback, include_extras=True)
    except Exception:
        hints = {}

    def derived(name):
        return "--" + name.rstrip("_").replace("_", "-")

    for name, p in inspect.signature(callback).parameters.items():
        infos = []
        if isinstance(p.default, (ArgumentInfo, OptionInfo)):
            infos.append(p.default)
        infos += [m for m in getattr(hints.get(name), "__metadata__", ())
                  if isinstance(m, (ArgumentInfo, OptionInfo))]
        if not infos:
            # bare parameter: positional when it has no default, else an option
            if p.default is inspect.Parameter.empty:
                pos.append(name)
            else:
                opts.append(derived(name))
            continue
        if any(isinstance(i, ArgumentInfo) for i in infos):
            pos.append(name)
            continue
        decls = {d for i in infos for d in (i.param_decls or []) if d.startswith("-")}
        if not any(d.startswith("--") for d in decls):
            decls.add(derived(name))       # short-only, or none at all
        opts.extend(decls)
    return pos, sorted(set(opts))


def walk(app, prefix=""):
    out = {}
    for info in getattr(app, "registered_commands", []):
        cb = info.callback
        name = info.name or (cb.__name__.replace("_", "-") if cb else "?")
        pos, opts = _params(cb)
        out[f"{prefix}{name}"] = {"kind": "leaf", "positional": pos, "options": opts}
    for grp in getattr(app, "registered_groups", []):
        sub = grp.typer_instance
        gname = grp.name or (sub.info.name if sub is not None else "?")
        children = []
        if sub is not None:
            children = [i.name or (i.callback.__name__.replace("_", "-"))
                        for i in getattr(sub, "registered_commands", [])]
            children += [g.name or (g.typer_instance.info.name)
                         for g in getattr(sub, "registered_groups", [])]
            out.update(walk(sub, prefix=f"{prefix}{gname} "))
        out[f"{prefix}{gname}"] = {"kind": "group", "children": sorted(children)}
    return out


def main():
    mod = sys.argv[1]
    attr = sys.argv[2] if len(sys.argv) > 2 else "app"
    try:
        app = getattr(importlib.import_module(mod), attr)
        typer = importlib.import_module("typer")
        print(json.dumps({"ok": True, "typer": typer.__version__,
                          "commands": walk(app)}, indent=2))
    except BaseException as e:
        # Never raise: a tool devman cannot read is a gap in the report,
        # never a failed build.
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


main()
