{
  description = "devman - compile, route and show Dagu workflows";

  # The development shell comes from `devenv.yaml`, not from this flake.
  # Outputs after Stage 1: the packages, one overlay, the Home Manager module
  # and three checks.

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

        # Compile the seed library for a fixture project: the real guard, the
        # real `config.yaml` template, the real `dagu validate`. The live
        # library sits in the overlay, outside this flake, and equals the seed.
        library-validate =
          let
            devman = mkDevman pkgs;
            dagu = mkDagu pkgs;
            state = "/tmp/lv/state";
            config = pkgs.replaceVars ./dagu/config.yaml {
              host = "127.0.0.1";
              port = "8080";
              coordinatorPort = "50055";
              bash = "${pkgs.bash}/bin/bash";
              stateDir = state;
              baseConfig = "${state}/base.yaml";
              queues = builtins.toJSON [
                { name = "light"; max_concurrency = 4; }
                { name = "normal"; max_concurrency = 2; }
                { name = "heavy"; max_concurrency = 1; }
              ];
            };
          in
          pkgs.runCommand "devman-library-validate" { nativeBuildInputs = [ devman dagu ]; } ''
            export HOME=$TMPDIR DAGU_HOME=$TMPDIR/dagu
            export DEVMAN_OVERLAY=$TMPDIR/overlay DEVMAN_STATE=${state}
            export DEVMAN_DAGU_CONFIG=${config} DEVMAN_BASH=${pkgs.bash}/bin/bash
            export DEVMAN_GUARD=${devman}/share/devman/dagu/guard.sh
            export DEVMAN_BIN=${devman}/bin/devman
            mkdir -p $DEVMAN_OVERLAY/library $DEVMAN_STATE $TMPDIR/work/p/.git
            cp -r ${./tests/fixtures/library}/. $DEVMAN_OVERLAY/library/
            printf '[p]\npath = "%s"\ntake = ["check", "test", "format", "release"]\n' \
              $TMPDIR/work/p > $DEVMAN_OVERLAY/projects.toml
            devman compile --all
            test "$(ls $DEVMAN_STATE/dags/p | wc -l)" = 4
            touch $out
          '';

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
                ./dagu
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
