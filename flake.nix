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
  };

  outputs = inputs@{ self, nixpkgs, devenv, codex-cli, claude-code, ... }:
    let
      lib = nixpkgs.lib;
      mkDevmanCore = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python313;
        in
        python.pkgs.buildPythonApplication {
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
            tomli-w
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
      mkDevmanEnv = {
        system,
        withCodexCli ? true,
        withClaudeCode ? true,
      }:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          devman-core = mkDevmanCore system;
          toolPaths = [
            devman-core
          ]
          ++ lib.optional withCodexCli codex-cli.packages.${system}.default
          ++ lib.optional withClaudeCode claude-code.packages.${system}.default;
          description = "devman with codex-cli and claude-code";
        in
        pkgs.buildEnv {
          name = "devman-env";
          paths = toolPaths;
          meta = {
            inherit description;
            mainProgram = "devman";
          };
        };
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
          devman-core = mkDevmanCore system;
        in
        ({
          devman = devman-core;
          devman-tools = mkDevmanEnv { inherit system; };
          default = mkDevmanEnv { inherit system; };
          codex-cli = codex-cli.packages.${system}.default;
          claude-code = claude-code.packages.${system}.default;
        })
      );

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          inputs = {
            inherit nixpkgs devenv codex-cli claude-code;
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

      lib.mkDevmanEnv = mkDevmanEnv;
    };
}
