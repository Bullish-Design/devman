# Investigation B scratch flake — three nixpkgs, one devman.
#
# This exists to answer B1 and B2 without touching the machine. It imports
# devman's `nixosModules.default` into three test NixOS configurations, each
# built against a different nixpkgs:
#
#   machine   the running machine's own nixpkgs, taken from the flake registry
#             (26.11, the store path nixos-rebuild would use)
#   unstable  devman's own flake input (github:NixOS/nixpkgs/nixos-unstable)
#   rolling   github:cachix/devenv-nixpkgs/rolling, which is what this repo's
#             devenv.yaml pins and therefore what `modules/` is evaluated under
#
# `rolling` is not a nixpkgs a NixOS machine would use. It is here because B1
# asks whether the SAME module file evaluates under the repo's nixpkgs and the
# machine's, and building a NixOS toplevel under rolling is the cheapest way to
# ask that of the NixOS half.
#
# Throwaway. Nothing here ships.
{
  description = "Investigation B — one flake, two module interfaces, three nixpkgs";

  inputs = {
    devman.url = "path:/home/andrew/.paseo/worktrees/1n48r26y/special-dragon";

    # The machine's nixpkgs, as the registry resolves it. `nixos-version` says
    # rev d407951447dcd00442e97087bf374aad70c04cea; this is that tree, already
    # in the store, so evaluating it costs no fetch.
    machine-nixpkgs.url = "path:/nix/store/ifpab9hxqmk2biwy594da8ipxzsp3y4s-source";
    machine-nixpkgs.flake = false;

    unstable.follows = "devman/nixpkgs";

    # Pinned to the rev in the repo's devenv.lock, so this flake sees exactly
    # the nixpkgs the repo's devenv shell sees.
    rolling.url = "github:cachix/devenv-nixpkgs/rolling";
  };

  outputs = { self, devman, machine-nixpkgs, unstable, rolling, ... }:
    let
      system = "x86_64-linux";

      trees = {
        machine = machine-nixpkgs;
        unstable = unstable;
        rolling = rolling;
      };

      # A NixOS configuration built from a bare nixpkgs tree, so `machine` can
      # be a non-flake source and still work.
      testConfig = tree: import "${tree}/nixos/lib/eval-config.nix" {
        inherit system;
        modules = [
          devman.nixosModules.default
          ({ lib, ... }: {
            services.devman-dagu.enable = true;
            services.devman-dagu.queues = { exclusive = 1; light = 4; };

            # Enough of a machine to make a toplevel. None of it is real.
            boot.loader.grub.devices = [ "/dev/null" ];
            fileSystems."/" = { device = "/dev/null"; fsType = "ext4"; };
            users.users.tester = { isNormalUser = true; uid = 1000; };
            system.stateVersion = lib.mkDefault "25.05";
          })
        ];
      };

      pkgsFor = name: import "${trees.${name}}" { inherit system; config = { }; overlays = [ ]; };
    in
    {
      nixosConfigurations = builtins.mapAttrs (name: _: testConfig name) trees;

      # B2 — the same nix/dagu.nix under each tree.
      packages.${system} = builtins.mapAttrs
        (name: _: (pkgsFor name).callPackage "${devman}/nix/dagu.nix" { })
        trees;
    };
}
