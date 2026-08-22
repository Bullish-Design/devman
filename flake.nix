{
  description = "devman - development automation plane";

  # The development environment is driven by `devenv.yaml` and entered with
  # `devenv shell`. It is not duplicated here: an earlier `devShells` output
  # re-declared a partial copy of devenv.yaml's inputs and had been broken for
  # some time in two independent ways, which is what an unused second path
  # looks like.
  #
  # What this flake carries today is the Dagu package (`nix/dagu.nix`). nixpkgs
  # has no Dagu at any version, so the plane packages it once and both
  # interfaces call the same file. The rest arrives at stage 1:
  #
  #   nixosModules.default   one Dagu service, queues, registry paths
  #   modules/               the repo interface, imported via devenv.yaml
  #
  # See .scratch/projects/006-automation-plane/CONCEPT.md §3.1. Nothing else is
  # added here until the investigations in KICKOFF_PROMPT.md answer whether one
  # flake can carry both module interfaces (§12.3).

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

      packages = forAllSystems (pkgs: {
        dagu = pkgs.callPackage ./nix/dagu.nix { };
        default = pkgs.callPackage ./nix/dagu.nix { };
      });
    };
}
