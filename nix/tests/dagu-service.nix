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
{ module, groups, fixture, plan }:

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
    FIXTURE = "${fixture}"
    # The plan `modules/devenv.nix` writes, in its shape. The devenv half cannot
    # run in a NixOS test — it would need a whole second nixpkgs and a network —
    # which is the constraint STAGE_1_LOG.md S10 records. What IS real below is
    # everything downstream of the plan: the renderer, `dagu validate`, the
    # published bytes, the link, the entry, and a run.
    PLAN = "${plan}"
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

    with subtest("a save inside a nested checkout fires only the inner project (P1-4)"):
        # 009 P1-4, against the real watcher. `match()` used to accept every
        # registered root containing the path, so one save enqueued a run in the
        # inner repository AND in the one it sits inside — and the outer
        # repository's formatter then rewrote source across the boundary. Both
        # runs reported success.
        inner = f"{PROJ}/nested"
        tester(f"mkdir -p {inner} {REG}/projects/nested/workflows")
        machine.succeed(f"install -o tester -g users -m 644 /dev/null {inner}/probe.yaml")
        machine.succeed(
            f"printf 'queue: light\\nsteps:\\n  - name: where\\n"
            f"    run: pwd\\n' > {inner}/probe.yaml"
        )
        tester(f"ln -sfn {inner}/probe.yaml {REG}/projects/nested/workflows/probe.yaml")
        tester(
            f"ln -sfn ../projects/nested/workflows/probe.yaml"
            f" {REG}/dags/nested.probe.yaml"
        )
        nested = json.dumps({
            "schema": 3, "project": "nested", "path": inner,
            "groups": ["base"], "plan": "", "local": ["probe"],
            "workflows": {"probe": {"group": "base", "shadows": [], "source": ""}},
            "triggers": {"group": "base", "map": {"**/*.py": "probe"}},
        })
        machine.succeed(f"echo '{nested}' > {REG}/projects/nested/metadata.json")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}grep -q \"\\\"project\\\": \\\"nested\\\"\" {REG}/watch/state.json'",
            timeout=60,
        )
        tester(f"truncate -s 0 {REG}/watch/fired.jsonl")

        tester(f"touch {inner}/changed.py")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}grep -q nested {REG}/watch/fired.jsonl'", timeout=90
        )
        # Give the outer project every chance to fire late, then read the whole
        # file: the assertion is that it fired ONCE, for the inner project.
        machine.succeed("sleep 10")
        lines = tester(f"cat {REG}/watch/fired.jsonl").strip().splitlines()
        print(lines)
        owners = {json.loads(line)["project"] for line in lines if line}
        assert owners == {"nested"}, f"the outer project fired too: {owners}"

    with subtest("doctor still tells a dead watcher from a watching one"):
        report = tester("devman doctor || true")
        assert "ok  watcher" in report, report
        tester("systemctl --user stop devman-watch")
        report = tester("devman doctor || true")
        assert "it is NOT running" in report, report
    # ---------------------------------------------------------------------
    # 009 P2-4 — THE VM EXECUTES THE ACTUAL GENERATED PROJECTION.
    #
    # Everything above builds the projection BY HAND, in the shape the module
    # writes. That was the whole gap: `groups-validate` validates SOURCE group
    # YAML, the unit suite could not reach a renderer that lived in shell, and
    # this test supplied `DEVMAN_PROJECT_DIR` itself at enqueue. So nothing
    # tested the producer's bytes, and P1-1, P1-3 and P2-1 all survived a green
    # suite.
    #
    # Stage 3 made the renderer a program. These subtests run it.

    FIX = HOME + "/work/fixture"

    with subtest("the real renderer projects the fixture repository"):
        machine.succeed(f"mkdir -p {FIX}/.devman/workflows")
        machine.succeed(f"cp {FIXTURE}/.devman/workflows/comment-only.yaml {FIX}/.devman/workflows/")
        machine.succeed(f"chown -R tester:users {HOME}/work/fixture")

        out = tester(
            f"devman --registry {REG} project apply --plan {PLAN}"
            f" --root {FIX} --local comment-only"
        )
        print(out)

    with subtest("a comment naming DEVMAN_SELF_DIR does not change the variable (P1-1)"):
        # `comment-only.yaml` is an ordinary workflow whose comment mentions
        # DEVMAN_SELF_DIR. The shell projection decided the variable with
        # `grep -q 'DEVMAN_SELF_DIR'` over the whole file, so it emitted the
        # wrong one — for a whole stage, in this repository's own
        # `plane-report.yaml`.
        projected = tester(f"cat {REG}/projects/fixture/workflows/comment-only.yaml")
        print(projected)
        assert f"DEVMAN_PROJECT_DIR: {FIX}" in projected
        assert "DEVMAN_SELF_DIR:" not in projected
        assert f"working_dir: {FIX}" in projected
        assert f"log_dir: {FIX}/.devman/.runs/logs" in projected
        # The body, last and unchanged. The shell-entry guard's tail-equality
        # test depends on it (STAGE_7_LOG.md S-5a).
        source = machine.succeed(f"cat {FIXTURE}/.devman/workflows/comment-only.yaml")
        assert projected.endswith(source), "the projection does not end with its source"

    with subtest("the emitted file is valid to the pinned Dagu, and discovered"):
        tester(f"dagu validate {REG}/projects/fixture/workflows/comment-only.yaml")
        listed = tester("dagu ls")
        assert "fixture.comment-only" in listed, listed

    with subtest("it runs with NO DEVMAN_ variable supplied at enqueue (P2-4)"):
        # The projection's own `env:` block is the only source of the directory
        # variable here. Every earlier subtest passed it by hand, which is
        # exactly what stopped this being a test of the producer.
        tester("dagu enqueue fixture.comment-only")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}test -f {FIX}/.devman/.runs/metadata.jsonl'", timeout=90
        )
        status = tester("dagu status fixture.comment-only")
        print(status)
        assert "Succeeded" in status, status
        assert f"{FIX}/.devman/.runs/logs/" in status, "log_dir did not follow the project"

        rec = json.loads(tester(f"cat {FIX}/.devman/.runs/metadata.jsonl").strip().splitlines()[-1])
        assert rec["dag"] == "fixture.comment-only"
        assert rec["status"] == "succeeded"
        assert rec["log"].startswith(FIX + "/.devman/.runs/logs/")

        # The step prints $DEVMAN_PROJECT_DIR. Reading it back proves the value
        # reached the step's environment, and not merely the file.
        printed = tester(f"find {FIX}/.devman/.runs/logs -name '*.out' -newer {FIX}/.devman -exec cat {{}} +")
        assert FIX in printed, printed

    with subtest("an env: block naming neither reserved name is refused (P1-1's severe case)"):
        # The shell projection emitted NO header for such a file, so it lost its
        # directory variable silently and ran in a directory named literally
        # after it. Refusing is the fix; merging would mean editing
        # the author's document, which breaks §7.2 and the guard's tail test.
        machine.succeed(f"cp {FIXTURE}/.devman/workflows/env-only.yaml {FIX}/.devman/workflows/")
        machine.succeed(f"chown -R tester:users {HOME}/work/fixture")
        refusal = machine.fail(
            f"su tester -c '{ENV}devman --registry {REG} project apply --plan {PLAN}"
            f" --root {FIX} --local comment-only --local env-only' 2>&1"
        )
        print(refusal)
        assert "env-only.yaml" in refusal
        assert "DEVMAN_PROJECT_DIR" in refusal

    with subtest("the refusal published nothing, and the previous projection stands"):
        # "Publish nothing" means the whole projection. A repository whose author
        # makes one typo must not lose the workflows that were already correct —
        # including any that carry a schedule.
        assert not machine.succeed(
            f"test -e {REG}/projects/fixture/workflows/env-only.yaml && echo yes || echo no"
        ).strip() == "yes"
        still = tester(f"cat {REG}/projects/fixture/workflows/comment-only.yaml")
        assert f"DEVMAN_PROJECT_DIR: {FIX}" in still
        assert "fixture.comment-only" in tester("dagu ls")

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
        # `$EPOCHREALTIME` is set by bash and by nothing else here, so a
        # succeeded step is `default_shell` governing a run the daemon enqueued
        # for itself.
        #
        # THE FILE IS PROJECTED BY THE REAL RENDERER (009 stage 8). It used to
        # be hand-built here, and building it taught the measurement that is now
        # free: a scheduled run needs the projection's `env:` block, not only its
        # `working_dir`, because base.yaml's exit handler appends to
        # `$DEVMAN_PROJECT_DIR/...` as a SHELL variable and the daemon's
        # environment holds no such name. The hand-built version reported
        # `failed` with every step succeeded until it carried one. The renderer
        # emits all three, so this asserts the producer and the shell together.
        #
        # THIS SUBTEST RUNS LAST, ON PURPOSE. A per-minute schedule keeps
        # enqueueing while the rest of the script runs, and `doctor` reads one
        # queued item with nothing running as a wedged queue — correctly.
        # Removing the file does not empty the queue either: an item already
        # dispatched outlives its DAG. Ordering is the only clean answer.
        machine.succeed(f"cp {FIXTURE}/.devman/workflows/tick.yaml {FIX}/.devman/workflows/")
        machine.succeed(f"chown -R tester:users {HOME}/work/fixture")
        tester(
            f"devman --registry {REG} project apply --plan {PLAN}"
            f" --root {FIX} --local comment-only --local tick"
        )
        projected = tester(f"cat {REG}/projects/fixture/workflows/tick.yaml")
        print(projected)
        assert f"DEVMAN_PROJECT_DIR: {FIX}" in projected, "the exit handler would have no path"

        # The scheduler reads the DAG directory itself; restart so it picks the
        # new file up without waiting for a rescan.
        tester("systemctl --user restart dagu")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}dagu status fixture.tick' 2>&1 | grep -q 'epochrealtime'",
            timeout=180,
        )
        status = tester("dagu status fixture.tick")
        print(status)
        assert "epochrealtime" in status and "[succeeded]" in status, status
        assert "Result: Succeeded" in status, status

        # THIS SUBTEST RUNS LAST, ON PURPOSE. A per-minute schedule keeps
        # enqueueing while the rest of the script runs, and `doctor` reads one
        # queued item with nothing running as a wedged queue — correctly.
        # Removing the file does not empty the queue either: an item already
        # dispatched outlives its DAG. Ordering is the only clean answer.
  '';
}
