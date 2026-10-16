{
  description = "devman - compile, route and show Dagu workflows";

  # The development shell comes from `devenv.yaml`, not from this flake.
  # Outputs after Stage 1: the packages, one overlay, the Home Manager module
  # and two checks. Stage 7 adds the library check.

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  # The Python build chain (decision 2026-10-15). These three inputs live here
  # and nowhere else: a second copy in `devenv.yaml` broke independently in the
  # old repository. The devenv shell uses `uv` and does not need them.
  inputs.pyproject-nix = {
    url = "github:pyproject-nix/pyproject.nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };
  inputs.uv2nix = {
    url = "github:pyproject-nix/uv2nix";
    inputs.pyproject-nix.follows = "pyproject-nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };
  inputs.pyproject-build-systems = {
    url = "github:pyproject-nix/build-system-pkgs";
    inputs.pyproject-nix.follows = "pyproject-nix";
    inputs.uv2nix.follows = "uv2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  # Used by `checks.hm-module` only.
  inputs.home-manager = {
    url = "github:nix-community/home-manager";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, home-manager, uv2nix, pyproject-nix, pyproject-build-systems, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      mkDagu = pkgs: pkgs.callPackage ./nix/dagu.nix { };
      mkDevman = pkgs: pkgs.callPackage ./nix/package.nix {
        dagu = mkDagu pkgs;
        inherit uv2nix pyproject-nix pyproject-build-systems;
      };
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
            # The locked runtime dependencies plus the dev group (pytest).
            testEnv = (mkDevman pkgs).testEnv;
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
            { nativeBuildInputs = [ testEnv (mkDagu pkgs) pkgs.watchexec ]; }
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
