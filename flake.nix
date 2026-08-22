{
  description = "devman - development automation plane";

  # The development environment is driven by `devenv.yaml` and entered with
  # `devenv shell`. It is not duplicated here: an earlier `devShells` output
  # re-declared a partial copy of devenv.yaml's inputs and had been broken for
  # some time in two independent ways, which is what an unused second path
  # looks like.
  #
  # What this flake carries is the Dagu package (`nix/dagu.nix`) plus the two
  # module interfaces. nixpkgs has no Dagu at any version, so the plane
  # packages it once and both interfaces call the same file:
  #
  #   nixosModules.default   one Dagu service, queues, base config
  #   modules/               the repo interface, imported via devenv.yaml
  #
  # Both modules are INVESTIGATION B SCRATCH — the smallest honest pair that
  # answers whether one flake can carry both at one version (§12.3). They are
  # not stage 1. See .scratch/projects/006-automation-plane/FINDINGS.md, B1–B4.
  #
  # Note what is NOT here: the NixOS module takes `pkgs` from the importing
  # machine and the devenv module takes `pkgs` from the consuming repo. Neither
  # reads this flake's own `nixpkgs` input. That input serves `packages` and
  # `checks` only.

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # For a machine that already composes its own nixpkgs.
      overlays.default = final: _prev: {
        dagu = final.callPackage ./nix/dagu.nix { };
      };

      # The machine interface (§4). Evaluated under the importing machine's
      # nixpkgs, never this flake's.
      nixosModules.default = ./nix/nixos-module.nix;
      nixosModules.devman-dagu = ./nix/nixos-module.nix;

      packages = forAllSystems (pkgs: {
        dagu = pkgs.callPackage ./nix/dagu.nix { };
        default = pkgs.callPackage ./nix/dagu.nix { };
      });
    };
}
