{
  description = "devman - development automation plane";

  # The development environment is driven by `devenv.yaml` and entered with
  # `devenv shell`. It is not duplicated here: an earlier `devShells` output
  # re-declared a partial copy of devenv.yaml's inputs and had been broken for
  # some time in two independent ways, which is what an unused second path
  # looks like.
  #
  # What this flake carries is the Dagu package (`nix/dagu.nix`), the two module
  # interfaces, and the workflow groups:
  #
  #   nixosModules.default   one Dagu service, queues, state paths, ports
  #   modules/               the repo interface, imported via devenv.yaml
  #   groups/                workflow content, shadowed by name (§7.2, §7.3)
  #
  # Note what is NOT here: the NixOS module takes `pkgs` from the importing
  # machine and the devenv module takes `pkgs` from the consuming repo. Neither
  # reads this flake's own `nixpkgs` input. That input serves `packages` and
  # `checks` only, and §3.1's first rule is what keeps one flake able to serve
  # two nixpkgs without either constraining the other.

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

      checks = forAllSystems (pkgs:
        {
          # Every shipped workflow must load. Dagu rejects an unknown top-level
          # key outright and rejects a top-level `name:`, and neither failure is
          # visible until something tries to run the file (A5).
          groups-validate = pkgs.runCommand "devman-groups-validate"
            {
              nativeBuildInputs = [ (pkgs.callPackage ./nix/dagu.nix { }) ];
            } ''
            export HOME=$TMPDIR
            export DAGU_HOME=$TMPDIR/dagu
            mkdir -p "$DAGU_HOME"
            fail=0
            for f in ${./groups}/*/workflows/*.yaml; do
              echo "validating ''${f#${./groups}/}"
              dagu validate "$f" || fail=1
            done
            [ "$fail" = 0 ]
            touch $out
          '';
        }
        // nixpkgs.lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
          # The machine module, run rather than evaluated (§9, rule 7). One VM,
          # one lingering user, one projection built by hand — because the
          # devenv half cannot run inside a NixOS test — and one real run.
          dagu-service = pkgs.testers.runNixOSTest (import ./nix/tests/dagu-service.nix {
            module = ./nix/nixos-module.nix;
            groups = ./groups;
          });
        });
    };
}
