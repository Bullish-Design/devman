# A NixOS test for the machine interface (CONCEPT.md §4).
#
# It proves the things a `nix eval` cannot: that the unit starts, that
# ExecStartPre writes config.yaml with the registry root expanded, that Dagu
# discovers a projected workflow through two chained file symlinks, and that a
# run lands its `working_dir`, its log tree and its `metadata.jsonl` in the
# project that triggered it.
#
# The devenv half cannot run in here — a NixOS test has no network and devenv
# would need to evaluate a whole second nixpkgs — so the projection is built by
# hand, in exactly the shape `modules/devenv.nix` writes it. What that half
# does is proved by entering shells instead; see STAGE_1_LOG.md, S10.
{ module, groups }:

{ lib, ... }:

{
  name = "devman-dagu-service";

  nodes.machine = { config, pkgs, ... }: {
    imports = [ module ];

    services.devman-dagu = {
      enable = true;
      lingerUsers = [ "tester" ];
      # A queue set the test can recognise, so it can tell this config.yaml
      # from Dagu's own default.
      queues = { light = 4; exclusive = 1; };
    };

    users.users.tester = {
      isNormalUser = true;
      uid = 1000;
    };

    virtualisation.memorySize = 2048;
    virtualisation.diskSize = 4096;
    system.stateVersion = lib.mkDefault "25.05";
  };

  testScript = ''
    import json

    GROUPS = "${groups}"
    HOME = "/home/tester"
    REG = HOME + "/.local/share/devman"
    PROJ = HOME + "/work/demo"
    # DAGU_HOME matters: without it the CLI picks its own default home, reads a
    # different config.yaml, and lists Dagu's bundled examples instead of the
    # registry.
    ENV = f"XDG_RUNTIME_DIR=/run/user/1000 HOME={HOME} DAGU_HOME={HOME}/.local/share/dagu "

    def tester(cmd):
        return machine.succeed(f"su tester -c '{ENV}{cmd}' 2>&1")

    machine.start()
    machine.wait_for_unit("multi-user.target")

    with subtest("linger is set declaratively, so the user manager runs unattended"):
        machine.succeed("loginctl show-user tester -p Linger | grep -x Linger=yes")

    with subtest("the user service is up"):
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}systemctl --user is-active dagu' 2>&1", timeout=60
        )

    with subtest("ExecStartPre wrote both files, with $HOME expanded"):
        cfg = tester("cat ~/.local/share/dagu/config.yaml")
        print(cfg)
        assert f"dags_dir: '{REG}/dags'" in cfg, "registry root was not expanded"
        assert "@DEVMAN_REGISTRY@" not in cfg
        assert "recursive: true" in cfg and "symlinks: true" in cfg
        assert "DEVMAN_" in cfg
        base = tester("cat ~/.local/share/dagu/base.yaml")
        print(base)
        assert "working_dir: ''${DEVMAN_PROJECT_DIR}" in base
        assert "devman-record-run" in base

    with subtest("both registry directories exist before anything registers"):
        tester(f"test -d {REG}/projects && test -d {REG}/dags")

    with subtest("a projection in the devenv module's shape is discovered"):
        # The names are the codec's: `<project>.<workflow>` (§9.2, S-12). This
        # subtest is the only place the dotted name meets a real Dagu service
        # rather than `dagu validate` — enqueue, the scheduler, `status`,
        # `log_dir` and base.yaml's exit handler all resolve it below.
        tester(f"mkdir -p {PROJ} {REG}/projects/demo/workflows")
        tester(
            f"ln -sfn {GROUPS}/base/workflows/check.yaml "
            f"{REG}/projects/demo/workflows/check.yaml"
        )
        tester(
            f"ln -sfn ../projects/demo/workflows/check.yaml {REG}/dags/demo.check.yaml"
        )
        # A probe of our own, because the group file calls `devenv tasks run`
        # and there is no devenv in this VM. Written as root and handed over,
        # because a redirect inside `su -c` belongs to the outer shell.
        machine.succeed(
            f"install -o tester -g users -m 644 /dev/null {PROJ}/probe.yaml"
        )
        machine.succeed(
            f"printf 'queue: light\\nsteps:\\n  - name: where\\n"
            f"    run: pwd\\n' > {PROJ}/probe.yaml"
        )
        tester(f"ln -sfn {PROJ}/probe.yaml {REG}/projects/demo/workflows/probe.yaml")
        tester(f"ln -sfn ../projects/demo/workflows/probe.yaml {REG}/dags/demo.probe.yaml")
        listed = tester("dagu ls")
        print(listed)
        assert "demo.check" in listed, "the chained group symlink was not discovered"
        assert "demo.probe" in listed
        assert "example-" not in listed, "Dagu seeded its examples into the registry"

    with subtest("a run lands in the project that triggered it"):
        tester(
            f"DEVMAN_PROJECT_DIR={PROJ} dagu enqueue demo.probe -- DEVMAN_PROJECT_DIR={PROJ}"
        )
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}test -f {PROJ}/.devman/.runs/metadata.jsonl'", timeout=90
        )
        status = tester("dagu status demo.probe")
        print(status)
        assert "Succeeded" in status
        assert f"{PROJ}/.devman/.runs/logs/" in status, "log_dir did not follow the project"

    with subtest("base.yaml's exit handler recorded the run"):
        line = tester(f"cat {PROJ}/.devman/.runs/metadata.jsonl").strip().splitlines()[-1]
        print(line)
        rec = json.loads(line)
        assert rec["dag"] == "demo.probe"
        assert rec["status"] == "succeeded"
        assert rec["log"].startswith(PROJ + "/.devman/.runs/logs/")
        assert rec["run_id"] and rec["attempt"] and rec["started_at"]

    with subtest("the ports the module declares are the ports Dagu binds"):
        machine.succeed("ss -ltnp | grep 127.0.0.1:8080")
        machine.succeed("ss -ltnp | grep 127.0.0.1:50055")

    # ---------------------------------------------------------------------
    # STAGE 3 — the CLI (§10) and the watcher (§8), from the same module.

    with subtest("the CLI is on PATH, wrapped with this machine's directories"):
        # The registry entry the devenv module would have written. The CLI reads
        # it; the projection above is what it points at.
        entry = json.dumps({
            "schema": 3, "project": "demo", "path": PROJ,
            "groups": ["base"], "plan": "", "local": ["probe"],
            "workflows": {"check": {"group": "base", "shadows": [], "source": ""}},
            "triggers": None,
        })
        machine.succeed(
            f"install -o tester -g users -m 644 /dev/null {REG}/projects/demo/metadata.json"
        )
        machine.succeed(f"echo '{entry}' > {REG}/projects/demo/metadata.json")
        shown = tester("cd " + PROJ + " && devman show probe")
        assert "run: pwd" in shown, "devman show did not print the resolved file"

    with subtest("devman run triggers, and the run lands in the project"):
        # No DAGU_HOME and no DEVMAN_PROJECT_DIR in this environment: the CLI
        # states both itself, which is the whole of S2 and A3.
        out = machine.succeed(
            f"su tester -c 'cd {PROJ} && HOME={HOME} XDG_RUNTIME_DIR=/run/user/1000 "
            f"devman run probe' 2>&1"
        )
        print(out)
        assert "Enqueued" in out
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}test $(wc -l < {PROJ}/.devman/.runs/metadata.jsonl) -ge 2'",
            timeout=90,
        )

    with subtest("devman run refuses when the project directory is gone (S15)"):
        machine.succeed(f"echo '{entry.replace(PROJ, PROJ + '-gone')}' > {REG}/projects/demo/metadata.json")
        refusal = machine.fail(
            f"su tester -c 'cd {PROJ} && HOME={HOME} devman run probe -p demo' 2>&1"
        )
        print(refusal)
        assert "refusing" in refusal
        machine.succeed(f"echo '{entry}' > {REG}/projects/demo/metadata.json")

    with subtest("devman doctor reports nothing on a healthy plane"):
        report = machine.succeed(
            f"su tester -c '{ENV}devman doctor' 2>&1"
        )
        print(report)
        assert "Nothing to report" in report
        assert "ok  plane" in report, "doctor could not read the running service"

    with subtest("the watcher is a second user service, and it watches nothing yet"):
        unit = tester("systemctl --user cat devman-watch")
        assert "devman watch" in unit
        # No project declares triggers, so the supervisor says so and waits. It
        # stays active: the registry is what it is waiting for.
        tester("systemctl --user start devman-watch || true")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}journalctl --user -u devman-watch | grep -q \"Nothing to watch yet\"'",
            timeout=60,
        )
        tester("systemctl --user is-active devman-watch")

    with subtest("the watcher picks up a new reactive project without a restart (S16)"):
        # The supervisor re-reads the registry every five seconds. Nothing below
        # restarts the unit, and the assertion at the end is that it did not.
        before = tester("systemctl --user show devman-watch -p NRestarts -p ExecMainStartTimestamp")
        reactive = json.dumps({
            "schema": 3, "project": "demo", "path": PROJ,
            "groups": ["base"], "plan": "", "local": ["probe"],
            "workflows": {"probe": {"group": "base", "shadows": [], "source": ""}},
            "triggers": {"group": "base", "map": {"**/*.py": "probe"}},
        })
        machine.succeed(f"echo '{reactive}' > {REG}/projects/demo/metadata.json")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}grep -q \"\\\"project\\\": \\\"demo\\\"\" {REG}/watch/state.json'",
            timeout=60,
        )
        after = tester("systemctl --user show devman-watch -p NRestarts -p ExecMainStartTimestamp")
        assert before == after, f"the unit restarted: {before} -> {after}"
        watching = json.loads(tester(f"cat {REG}/watch/state.json"))
        assert "--watch" in watching["command"], watching["command"]
        assert PROJ in watching["command"], watching["command"]

    with subtest("a save in that project fires the workflow, with nothing restarted"):
        tester(f"touch {PROJ}/hello.py")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}test -f {REG}/watch/fired.jsonl'", timeout=90
        )
        fired = json.loads(tester(f"tail -1 {REG}/watch/fired.jsonl"))
        print(fired)
        assert fired["project"] == "demo" and fired["workflow"] == "probe"
        assert fired["outcome"] == "enqueued", fired

    with subtest("doctor still tells a dead watcher from a watching one"):
        report = tester("devman doctor || true")
        assert "ok  watcher" in report, report
        tester("systemctl --user stop devman-watch")
        report = tester("devman doctor || true")
        assert "it is NOT running" in report, report
    # ---------------------------------------------------------------------
    # 009 P1-3 — the daemon's own enqueues take the daemon's own shell.

    with subtest("the service process holds no SHELL"):
        # `devman run` clears SHELL for the CLI, the watcher and the hook. A
        # SCHEDULED run has no such path: Dagu enqueues it from this process, so
        # the unit has to unset it. `environment.SHELL = null` would remove
        # nothing — the variable is inherited from the user manager — hence
        # `serviceConfig.UnsetEnvironment`.
        pid = tester("systemctl --user show dagu -p MainPID --value").strip()
        environ = machine.succeed(f"tr '\\0' '\\n' < /proc/{pid}/environ")
        print(environ)
        assert "SHELL=" not in environ, "the daemon would hand its own SHELL to a scheduled run"

    with subtest("a SCHEDULED run gets the declared default_shell (S9, S13)"):
        # `$EPOCHREALTIME` is the exact construct that failed in S9: bash sets
        # it, and the shell a step actually ran under was the enqueueing
        # process's. Under `default_shell` bash this step passes; under the
        # user manager's zsh, or any POSIX shell, it does not.
        #
        # No `devenv tasks run` here: the VM has no devenv. Same shape as
        # `probe.yaml` above.
        machine.succeed(f"install -o tester -g users -m 644 /dev/null {PROJ}/tick.yaml")
        # It states its own `working_dir` and `log_dir`, exactly as the
        # projection writes them for a scheduled workflow. The daemon has one
        # environment for the whole machine, so a file inheriting base.yaml's
        # `''${DEVMAN_PROJECT_DIR}` would run in a directory of that literal
        # name (STAGE_4_LOG.md S2, closed by STAGE_6_LOG.md S2).
        # The `env:` block is not decoration. base.yaml's exit handler appends to
        # `$DEVMAN_PROJECT_DIR/.devman/.runs/metadata.jsonl` as a SHELL variable,
        # and the daemon's environment holds no such name — so without this the
        # handler writes to `/.devman/...`, fails, and the run reports `failed`
        # although every step succeeded. Measured while writing this subtest.
        machine.succeed(
            f"printf 'env:\\n  - DEVMAN_PROJECT_DIR: {PROJ}\\n"
            f"working_dir: {PROJ}\\nlog_dir: {PROJ}/.devman/.runs/logs\\n"
            f"queue: light\\nschedule: \"* * * * *\"\\nsteps:\\n"
            f"  - name: epochrealtime\\n"
            f"    run: test -n \"$EPOCHREALTIME\"\\n' > {PROJ}/tick.yaml"
        )
        tester(f"ln -sfn {PROJ}/tick.yaml {REG}/projects/demo/workflows/tick.yaml")
        tester(f"ln -sfn ../projects/demo/workflows/tick.yaml {REG}/dags/demo.tick.yaml")
        # The scheduler reads the DAG directory itself; restart so it picks the
        # new file up without waiting for a rescan.
        tester("systemctl --user restart dagu")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}dagu status demo.tick' 2>&1 | grep -q 'epochrealtime'",
            timeout=180,
        )
        status = tester("dagu status demo.tick")
        print(status)
        # The STEP is the assertion. `$EPOCHREALTIME` is set by bash and by
        # nothing else here, so a succeeded step is `default_shell` governing a
        # run the daemon enqueued for itself.
        assert "epochrealtime" in status and "[succeeded]" in status, status
        assert "Result: Succeeded" in status, status

        # THIS SUBTEST RUNS LAST, ON PURPOSE. A per-minute schedule keeps
        # enqueueing while the rest of the script runs, and `doctor` reads one
        # queued item with nothing running as a wedged queue — correctly.
        # Removing the file does not empty the queue either: an item already
        # dispatched outlives its DAG. Ordering is the only clean answer.
  '';
}
