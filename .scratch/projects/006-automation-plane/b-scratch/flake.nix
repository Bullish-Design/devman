# Investigation B scratch flake — one devman, several nixpkgs.
#
# This exists to answer B1, B2, and B3 without touching the machine. It imports
# devman's `nixosModules.default` into test NixOS configurations, each built
# against a different nixpkgs, and builds `nix/dagu.nix` under each.
#
#   machine     the running machine's own nixpkgs, taken from the flake
#               registry (26.11, rev d407951, the tree nixos-rebuild uses)
#   unstable    devman's own flake input, github:NixOS/nixpkgs/nixos-unstable
#   rolling     github:cachix/devenv-nixpkgs/rolling, the tree this repo's
#               devenv.yaml pins and therefore what `modules/` evaluates under
#
# `rolling` is NOT a nixpkgs checkout. It is a wrapper flake: it takes
# `nixpkgs-src` (plain nixpkgs), applies patches to it with `applyPatches`, and
# exposes the result as `legacyPackages.<system>`. So it has no
# `nixos/lib/eval-config.nix` at its root, and reaching its package set needs
# import-from-derivation. `rolling-src` below is the unpatched tree underneath
# it, which is what the NixOS half can be evaluated against.
#
# Throwaway. Nothing here ships.
{
  description = "Investigation B — one flake, two module interfaces, several nixpkgs";

  inputs = {
    devman.url = "path:/home/andrew/.paseo/worktrees/1n48r26y/special-dragon";

    # The machine's nixpkgs, as the registry resolves it. `nixos-version` says
    # rev d407951447dcd00442e97087bf374aad70c04cea; this is that tree, already
    # in the store, so evaluating it costs no fetch.
    machine-nixpkgs.url = "path:/nix/store/ifpab9hxqmk2biwy594da8ipxzsp3y4s-source";
    machine-nixpkgs.flake = false;

    unstable.follows = "devman/nixpkgs";

    # Locked to the rev in the repo's devenv.lock, so this flake sees exactly
    # the package set the repo's devenv shell sees.
    rolling.url = "github:cachix/devenv-nixpkgs/rolling";
    rolling-src.follows = "rolling/nixpkgs-src";
  };

  outputs = { self, devman, machine-nixpkgs, unstable, rolling, rolling-src, ... }:
    let
      system = "x86_64-linux";

      # Plain nixpkgs trees — these carry nixos/lib/eval-config.nix.
      trees = {
        machine = machine-nixpkgs;
        unstable = unstable;
        rolling-src = rolling-src;
      };

      # Package sets, one per tree, plus rolling's patched set.
      pkgsSets =
        builtins.mapAttrs (_: tree: import "${tree}" { inherit system; config = { }; overlays = [ ]; }) trees
        // { rolling = rolling.legacyPackages.${system}; };

      # A NixOS configuration built from a bare nixpkgs tree, so `machine` can
      # be a non-flake source and still work. `extra` is B3's collision probe.
      testConfig = tree: extra: import "${tree}/nixos/lib/eval-config.nix" {
        inherit system;
        modules = extra ++ [
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
    in
    {
      # B1 — the same module file, evaluated under each tree.
      nixosConfigurations =
        builtins.mapAttrs (_: tree: testConfig tree [ ]) trees
        # B3 — the same module plus one reference the other tree cannot satisfy.
        // builtins.listToAttrs (builtins.concatMap
          (name: map
            (d: {
              name = "${name}-${d}";
              value = testConfig trees.${name} [ (import ./collide.nix { direction = d; }) ];
            }) [ "newer-than-machine" "older-than-unstable" ])
          (builtins.attrNames trees));

      # B2 — the same nix/dagu.nix under each package set, rolling included.
      packages.${system} = builtins.mapAttrs
        (_: pkgs: pkgs.callPackage "${devman}/nix/dagu.nix" { })
        pkgsSets;
    };
}
