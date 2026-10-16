{
  description = "devman - compile, route and show Dagu workflows";

  # The development shell comes from `devenv.yaml`, not from this flake.
  # Outputs after Stage 0: the packages, one overlay and the Python check.
  # Stage 1 adds the Home Manager module and its check. Stage 7 adds the
  # library check.

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, ... }:
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

      overlays.default = final: _prev: {
        dagu = mkDagu final;
        devman = mkDevman final;
      };

      checks = forAllSystems (pkgs: {
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
