{
  description = "devman - development automation plane";

  # The development environment is driven by `devenv.yaml` and entered with
  # `devenv shell`. It is not duplicated here: an earlier `devShells` output
  # re-declared a partial copy of devenv.yaml's inputs and had been broken for
  # some time in two independent ways, which is what an unused second path
  # looks like.
  #
  # This flake is a placeholder for the plane's own outputs, which arrive at
  # stage 1:
  #
  #   nixosModules.default   one Dagu service, queues, registry paths
  #   modules/               the repo interface, imported via devenv.yaml
  #   packages.default       the devman CLI
  #
  # See .scratch/projects/006-automation-plane/CONCEPT.md §3.1. Nothing is
  # added here until the investigations in KICKOFF_PROMPT.md answer whether one
  # flake can carry both module interfaces (§12.3).

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }: { };
}
