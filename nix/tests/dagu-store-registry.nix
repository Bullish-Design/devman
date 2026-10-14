# A NixOS test for a store-path registry (`lib.<system>.mkRegistry`).
#
# `dagu-service.nix` proves the module against a mutable registry directory.
# This test proves the other form: `registryDir` is one read-only store path
# that a Nix build rendered. It proves that:
#
#   * the Dagu user service starts and stays active on that path,
#   * the API on loopback lists a rendered workflow,
#   * a run lands in the project checkout, and the exit handler records it,
#   * the module installs no reload adapter and no path unit for it,
#   * nothing in the registry changed.
{ module, registry }:

{ lib, ... }:

{
  name = "devman-dagu-store-registry";

  nodes.machine = { ... }: {
    imports = [ module ];

    services.devman-dagu = {
      enable = true;
      lingerUsers = [ "tester" ];
      registryDir = "${registry}";
      stateDir = "$HOME/.local/state/devman";
      queues = { light = 4; exclusive = 1; };
    };

    users.users.tester = {
      isNormalUser = true;
      uid = 1000;
    };

    virtualisation.memorySize = 1536;
    virtualisation.diskSize = 2048;
    system.stateVersion = lib.mkDefault "25.05";
  };

  testScript = ''
    import json

    REGISTRY = "${registry}"
    HOME = "/home/tester"
    STATE = HOME + "/.local/state/devman"
    PROJ = HOME + "/work/demo"
    ENV = f"XDG_RUNTIME_DIR=/run/user/1000 HOME={HOME} DAGU_HOME={HOME}/.local/share/dagu "

    def tester(cmd):
        return machine.succeed(f"su tester -c '{ENV}{cmd}' 2>&1")

    machine.start()
    machine.wait_for_unit("multi-user.target")

    with subtest("the registry is the layout the module reads"):
        machine.succeed(f"test -f {REGISTRY}/generation.json")
        generation = json.loads(machine.succeed(f"cat {REGISTRY}/generation.json"))
        assert generation["generation"] == 7, generation
        machine.succeed(f"test -L {REGISTRY}/dags/demo.probe.yaml")
        machine.succeed(f"test -f {REGISTRY}/projects/demo/metadata.json")

    with subtest("the Dagu user service starts on the store path"):
        machine.succeed("loginctl show-user tester -p Linger | grep -x Linger=yes")
        try:
            machine.wait_until_succeeds(
                f"su tester -c '{ENV}systemctl --user is-active dagu' 2>&1", timeout=90
            )
        except Exception:
            # Name the failure in the log before the test stops.
            print(machine.execute(f"su tester -c '{ENV}systemctl --user status dagu --no-pager' 2>&1")[1])
            print(machine.execute(f"su tester -c '{ENV}journalctl --user -u dagu --no-pager' 2>&1")[1])
            raise

    with subtest("the config points at the store path and nothing was created in it"):
        cfg = tester("cat ~/.local/share/dagu/config.yaml")
        print(cfg)
        assert f"dags_dir: '{REGISTRY}/dags'" in cfg
        assert "@DEVMAN_REGISTRY@" not in cfg and "@DAGU_HOME@" not in cfg
        # Dagu 2.15.0 puts its Wiki under dags_dir, which is read-only here.
        assert f"wiki_dir: {HOME}/.local/share/dagu/wiki" in cfg or \
            f"wiki_dir: '{HOME}/.local/share/dagu/wiki'" in cfg
        tester(f"test -d {STATE}/projects")
        # The registry holds exactly what the build wrote.
        top = machine.succeed(f"ls -A {REGISTRY} | sort").split()
        assert top == ["dags", "generation.json", "projects"], top

    with subtest("the API on loopback lists the rendered workflows"):
        machine.wait_until_succeeds("curl -sf http://127.0.0.1:8080/api/v1/health", timeout=60)
        listing = machine.succeed("curl -sf 'http://127.0.0.1:8080/api/v1/dags?perPage=100'")
        print(listing)
        names = {d["dag"]["name"] for d in json.loads(listing)["dags"]}
        for want in ("demo.check", "demo.probe", "beta.check", "beta.format"):
            assert want in names, (want, sorted(names))
        assert not any(n.startswith("example-") for n in names), sorted(names)
        assert "demo.probe" in tester("dagu ls")

    with subtest("a run lands in the project checkout"):
        machine.succeed(f"install -d -o tester -g users {HOME}/work {PROJ}")
        tester(f"DEVMAN_PROJECT_DIR={PROJ} dagu enqueue demo.probe -- DEVMAN_PROJECT_DIR={PROJ}")
        machine.wait_until_succeeds(
            f"su tester -c '{ENV}test -f {PROJ}/.devman/.runs/metadata.jsonl'", timeout=90
        )
        status = tester("dagu status demo.probe")
        print(status)
        assert "Succeeded" in status
        rec = json.loads(machine.succeed(f"tail -n1 {PROJ}/.devman/.runs/metadata.jsonl"))
        assert rec["dag"] == "demo.probe" and rec["status"] == "succeeded", rec

    with subtest("the module installs no reload adapter for a store path"):
        units = tester("systemctl --user list-unit-files --no-legend | grep devman-dagu-reload; true")
        assert units.strip() == "", units
        assert machine.succeed(f"ls -A {REGISTRY}").split() == ["dags", "generation.json", "projects"]
        tester(f"test ! -e {STATE}/reload.pending && test ! -e {STATE}/reload.blocked")

    with subtest("the service stays active and does not restart"):
        machine.sleep(20)
        tester("systemctl --user is-active dagu")
        restarts = tester("systemctl --user show dagu -p NRestarts --value").strip()
        assert restarts == "0", restarts
        assert "demo.probe" in tester("dagu ls")
  '';
}
