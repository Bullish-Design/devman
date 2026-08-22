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
        tester(f"mkdir -p {PROJ} {REG}/projects/demo/workflows")
        tester(
            f"ln -sfn {GROUPS}/base/workflows/check.yaml "
            f"{REG}/projects/demo/workflows/check.yaml"
        )
        tester(
            f"ln -sfn ../projects/demo/workflows/check.yaml {REG}/dags/demo-check.yaml"
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
        tester(f"ln -sfn ../projects/demo/workflows/probe.yaml {REG}/dags/demo-probe.yaml")
        listed = tester("dagu ls")
        print(listed)
        assert "demo-check" in listed, "the chained group symlink was not discovered"
        assert "demo-probe" in listed
        assert "example-" not in listed, "Dagu seeded its examples into the registry"

    with subtest("a run lands in the project that triggered it"):
        tester(
            f"DEVMAN_PROJECT_DIR={PROJ} dagu enqueue demo-probe -- DEVMAN_PROJECT_DIR={PROJ}"
        )
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}test -f {PROJ}/.devman/.runs/metadata.jsonl'", timeout=90
        )
        status = tester("dagu status demo-probe")
        print(status)
        assert "Succeeded" in status
        assert f"{PROJ}/.devman/.runs/logs/" in status, "log_dir did not follow the project"

    with subtest("base.yaml's exit handler recorded the run"):
        line = tester(f"cat {PROJ}/.devman/.runs/metadata.jsonl").strip().splitlines()[-1]
        print(line)
        rec = json.loads(line)
        assert rec["dag"] == "demo-probe"
        assert rec["status"] == "succeeded"
        assert rec["log"].startswith(PROJ + "/.devman/.runs/logs/")
        assert rec["run_id"] and rec["attempt"] and rec["started_at"]

    with subtest("the ports the module declares are the ports Dagu binds"):
        machine.succeed("ss -ltnp | grep 127.0.0.1:8080")
        machine.succeed("ss -ltnp | grep 127.0.0.1:50055")
  '';
}
