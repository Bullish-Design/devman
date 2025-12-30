{
  description = "devman - DevEnv project templating system for NixOS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    devenv = {
      url = "github:cachix/devenv";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    codex-cli = {
      url = "github:sadjow/codex-cli-nix?ref=main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    claude-code = {
      url = "github:sadjow/claude-code-nix?ref=main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    opencode = {
      url = "github:sst/opencode?ref=v1.0.217";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, devenv, codex-cli, claude-code, opencode }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python313;
          devman-core = python.pkgs.buildPythonApplication {
            pname = "devman";
            version = "0.1.1";
            format = "pyproject";
            src = ./.;

            nativeBuildInputs = with python.pkgs; [
              hatchling
            ];

            propagatedBuildInputs = with python.pkgs; [
              typer
              rich
              pathlib-abc
              jinja2
              pydantic
              pyyaml
            ];

            doCheck = false;

            meta = with pkgs.lib; {
              description = "DevEnv project templating system for NixOS development environments";
              homepage = "https://github.com/Bullish-Design/devman";
              license = licenses.mit;
              maintainers = [ ];
              mainProgram = "devman";
            };
          };
        in
        {
          devman = devman-core;
          default = pkgs.buildEnv {
            name = "devman-full";
            paths = [
              devman-core
              codex-cli.packages.${system}.default
              claude-code.packages.${system}.default
              opencode.packages.${system}.default
            ];
            meta = {
              description = "devman with codex-cli, claude-code, and opencode";
              mainProgram = "devman";
            };
          };
          codex-cli = codex-cli.packages.${system}.default;
          claude-code = claude-code.packages.${system}.default;
          opencode = opencode.packages.${system}.default;
        }
      );

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inputs = {
            inherit nixpkgs devenv codex-cli claude-code opencode;
          };
        in
        {
          default = devenv.lib.mkShell {
            inherit pkgs;
            modules = [
              { _module.args = { inherit inputs; }; }
              ./devenv.nix
            ];
          };
        }
      );

      homeManagerModules.default = { config, lib, pkgs, ... }: {
        options.programs.devman = {
          enable = lib.mkEnableOption "devman";
        };

        config = lib.mkIf config.programs.devman.enable {
          home.packages = [ self.packages.${pkgs.system}.default ];
        };
      };
    };
}
