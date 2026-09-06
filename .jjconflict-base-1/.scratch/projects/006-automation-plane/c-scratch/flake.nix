# Investigation C scratch flake — C7 only.
#
# The question: on activation, does NixOS restart a systemd USER service whose
# unit file changed? §5.2 requires it. Investigation B confirmed that
# `restartTriggers` renders `X-Restart-Triggers` into the user unit and left
# "who acts on it" unmeasured.
#
# The test uses a `specialisation`, not a second nixosConfiguration, so the two
# generations differ in exactly one thing: the queues in Dagu's config.yaml.
# Everything else -- including the test harness's own plumbing -- is identical,
# so a restart that happens can only be the unit file change.
#
# Throwaway. Nothing here ships. Nothing here touches the machine: the VM runs
# from `nix build`, and the real Dagu instance and the real registry are never
# reached.
{
  description = "Investigation C — C7, does activation restart a user service";

  inputs = {
    # The machine's own nixpkgs, as B pinned it. Same tree nixos-rebuild uses,
    # already in the store, so evaluating it costs no fetch.
    machine-nixpkgs.url = "path:/nix/store/ifpab9hxqmk2biwy594da8ipxzsp3y4s-source";
    machine-nixpkgs.flake = false;
  };

  outputs = { self, machine-nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import "${machine-nixpkgs}" { inherit system; config = { }; overlays = [ ]; };

      # The devman NixOS module, read straight out of this worktree.
      devmanModule = ../../../../nix/nixos-module.nix;

      node = { lib, config, ... }: {
        imports = [ devmanModule ];

        services.devman-dagu.enable = true;
        services.devman-dagu.queues = { exclusive = 1; };

        # A user with a running user manager. logind lists lingering users, and
        # switch-to-configuration only visits the users logind lists.
        users.users.tester = {
          isNormalUser = true;
          uid = 1000;
          linger = true;
        };

        # The only difference between the two generations.
        specialisation.newqueues.configuration = {
          services.devman-dagu.queues = { exclusive = 1; light = 4; heavy = 2; };
        };

        # `dagu` on PATH, so the divergence probe can run the CLI as the developer would.
        environment.systemPackages = [ pkgs.curl pkgs.jq config.services.devman-dagu.package ];

        virtualisation.memorySize = 2048;
        virtualisation.diskSize = 4096;
        system.stateVersion = lib.mkDefault "25.05";
      };
    in
    {
      checks.${system}.c7 = pkgs.testers.runNixOSTest {
        name = "c7-user-service-restart";
        nodes.machine = node;
        testScript = builtins.readFile ./c7-test.py;
      };
    };
}
