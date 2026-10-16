{
  description = "devman - compile, route and show Dagu workflows";

  # The development shell comes from `devenv.yaml`, not from this flake.
  # Outputs after Stage 1: the packages, one overlay, the Home Manager module
  # and two checks. Stage 7 adds the library check.

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  # Used by `checks.hm-module` only.
  inputs.home-manager = {
    url = "github:nix-community/home-manager";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, home-manager, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      mkDagu = pkgs: pkgs.callPackage ./nix/dagu.nix { };
      mkDevman = pkgs: pkgs.callPackage ./nix/package.nix { dagu = mkDagu pkgs; };
    in
    {
      packages = forAllSystems (pkgs: rec {
        dagu = mkDagu pkgs;
        devman = mkDevman pkgs;
        default = devman;
      });

      homeManagerModules.default = import ./nix/hm-module.nix { inherit self; };

      overlays.default = final: _prev: {
        dagu = mkDagu final;
        devman = mkDevman final;
      };

      checks = forAllSystems (pkgs: {
        hm-module = import ./nix/hm-module-check.nix {
          inherit self pkgs home-manager;
          dagu = mkDagu pkgs;
        };

        # pytest over src/ and tests/, without the e2e tests (they start a
        # real Dagu server on loopback ports). `base:e2e` runs those.
        python-tests =
          let
            python = pkgs.python313.withPackages (ps: [ ps.pytest ps.pyyaml ]);
            source = nixpkgs.lib.fileset.toSource {
              root = ./.;
              fileset = nixpkgs.lib.fileset.unions [
                ./src
                ./tests
                ./pyproject.toml
              ];
            };
          in
          pkgs.runCommand "devman-python-tests"
            { nativeBuildInputs = [ python (mkDagu pkgs) pkgs.watchexec ]; }
            ''
              export HOME=$TMPDIR
              export DAGU_HOME=$TMPDIR/dagu
              mkdir -p "$DAGU_HOME"
              cp -r ${source} ./suite
              chmod -R u+w ./suite
              cd ./suite
              pytest -m "not e2e"
              touch $out
            '';
      });
    };
}
