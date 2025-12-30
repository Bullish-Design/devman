{
  description = "llm-core";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    devenv.url = "github:cachix/devenv";
  };

  outputs = { self, nixpkgs, devenv }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devenvModules.base = import ./devenv/base.nix;

      packages = forAllSystems (system: let pkgs = nixpkgs.legacyPackages.${system}; in {
        default = pkgs.stdenv.mkDerivation {
          name = "llm-core";
          src = ./.;
          installPhase = "mkdir -p $out";
        };
      });
    };
}
