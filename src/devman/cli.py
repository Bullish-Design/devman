"""The devman command (CONCEPT.md §10).

    devman run <workflow>      trigger a workflow in the current project
    devman show <workflow>     print the resolved file, to start an override
    devman doctor              diagnose the plane
    devman watch               the watcher's entry point — systemd runs this

**Three commands and one that is machinery.** §10's list is the developer's
surface and it is closed: there is no `list`, no `status`, no `register` and no
`unregister`, because registration is automatic and has no manual path (§5.2),
and the rest is what `doctor` reports. `watch` is the fourth, and it is not a
fourth *command* in that sense — it is the watcher service's entry point (§8),
run by systemd rather than by a person, and it exists here rather than as a
shell script in the machine module so that exactly one implementation reads the
registry.

**The name.** `devman 0.2.0` owned this name and shipped its own `doctor`,
`init`, `up`, `down`, `switch`, `bootstrap` and `index` (§3.3). It was removed
from the profile at stage 1 and the removal was activated, so the name is free
(`STAGE_1_LOG.md`, S11).

**Where it ships from.** `nixosModules.default` only. §3.1's second rule says
what the two interfaces share must be text, and a Python CLI is not text;
`nix/dagu.nix` is the single measured exception. Installing it from the devenv
module as well would also put two `devman` binaries on one PATH, resolved by
profile order, which is the hazard §3.3 exists to record. A devenv shell
inherits the machine profile's PATH, so a machine-side install reaches every
repository shell on that machine anyway.
"""

from __future__ import annotations

import argparse
import sys

from . import doctor, run, show, watch
from .registry import DEFAULT_DAGU_HOME, DEFAULT_REGISTRY, Registry, RegistryError


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="devman", description=__doc__.splitlines()[0])
    # Global, because the NixOS module wraps this binary with them when a
    # machine moves either directory. They are flags rather than `DEVMAN_*`
    # variables on purpose: Dagu passes every `DEVMAN_*` in the enqueueing
    # process's environment through to the run, and §7.1's list of four names is
    # closed.
    ap.add_argument("--registry", default=DEFAULT_REGISTRY, help="the registry root (§9.2)")
    ap.add_argument("--dagu-home", default=DEFAULT_DAGU_HOME, help="the plane's DAGU_HOME (S2)")
    sub = ap.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="trigger a workflow in the current project")
    p_run.add_argument("workflow")
    p_run.add_argument("params", nargs="*", metavar="NAME=VALUE")
    p_run.add_argument("-p", "--project", help="name a project instead of using the current directory")
    p_run.add_argument("--print", dest="print_only", action="store_true", help="print the trigger and enqueue nothing")

    p_show = sub.add_parser("show", help="print the resolved workflow file")
    p_show.add_argument("workflow", nargs="?")
    p_show.add_argument("-p", "--project", help="name a project instead of using the current directory")
    p_show.add_argument("--path", action="store_true", help="print the resolved path, not the file")

    p_doc = sub.add_parser("doctor", help="diagnose the plane")
    p_doc.add_argument("--prune", action="store_true", help="remove stale registry entries (§10 check 5)")

    p_watch = sub.add_parser("watch", help="the watcher service's entry point (§8)")
    p_watch.add_argument("--dispatch", action="store_true", help="handle one batch of events on stdin")
    p_watch.add_argument("--print", dest="print_only", action="store_true", help="print the watchexec command and run nothing")
    p_watch.add_argument("--watchexec-arg", action="append", default=[], metavar="ARG", help="pass one more argument to watchexec")

    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    reg = Registry(args.registry)
    handler = {"run": run.main, "show": show.main, "doctor": doctor.main, "watch": watch.main}
    try:
        return handler[args.command](args, reg)
    except RegistryError as exc:
        for line in str(exc).splitlines():
            print(f"devman: {line}" if not line.startswith(" ") else f"devman:{line}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
