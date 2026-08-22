{ pkgs, lib, config, inputs, ... }:

let
  # The plane's orchestrator (CONCEPT.md §4). nixpkgs packages no Dagu at any
  # version, so this repo carries the expression and both interfaces call the
  # same file — this shell now, the NixOS module at stage 1 (§3.1).
  dagu = pkgs.callPackage ./nix/dagu.nix { };

  # All Dagu state lives under devenv's state directory: git-ignored,
  # disposable, and rebuilt by re-entering the shell. That is §9.3's
  # "inconvenient, not catastrophic" applied to the investigation setup.
  # DAGU_HOME is the one knob; Dagu derives dags/, logs/, and data/ from it.
  daguHome = "${config.devenv.state}/dagu";
in
{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.ruff
    dagu
    inputs.codex-cli.packages.${pkgs.system}.default
    inputs.claude-code.packages.${pkgs.system}.default
  ];

  # https://devenv.sh/languages/
  # languages.rust.enable = true;
  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
    #ruff.enable = true;

  };
  # https://devenv.sh/processes/
  #
  # `processes.dagu` is DELIBERATELY ABSENT (CONCEPT.md §4, §13 stage 1).
  #
  # It used to start one instance here with `devenv up`, which is how the
  # investigations got a Dagu to measure. It cannot stay. Dagu binds a web port
  # and a coordinator port, and a second instance fails on the coordinator with
  # `bind: address already in use` even when it has its own DAGU_HOME — so a
  # project-local Dagu in THIS repo holds the ports the plane's own user service
  # needs, and criterion 16 says devman adopts itself (D3).
  #
  # Stage 1 installs the service from `nix/nixos-module.nix`. Until then, run a
  # throwaway instance by hand with its own DAGU_HOME rather than restoring this
  # line.
  #
  # DAGU_HOME stays: the client on PATH needs it, and it costs nothing.
  env.DAGU_HOME = daguHome;

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  

  enterShell = ''
    hello
    git --version
    #echo
    # Create a wrapper script to ensure Nix ruff is used
    export PATH="${pkgs.ruff}/bin:$PATH"
    # Remove any pip-installed ruff from the environment
    unset VIRTUAL_ENV_RUFF
    #echo

  '';

  # devman adopts itself (CONCEPT.md §14, criterion 16). Three lines, and the
  # repo's own primitives below.
  #
  # There is no `devman` input in devenv.yaml: this repository IS the plane, so
  # it imports `./modules` directly. Every other repository pins a rev with
  # `git+https` (§3.2), because `git+file` records neither `rev` nor `narHash`
  # and silently follows the branch head (B4).
  # `base` only. This repository carries no Python source, so taking `python`
  # would put a `typecheck` step in its `check` with nothing to type-check —
  # §15.7's "nothing checks that a default still fits", self-inflicted.
  devman = {
    enable = true;
    project = "devman";
    groups = [ "base" ];
  };

  # https://devenv.sh/tasks/
  #
  # The two task names the `base` group calls (groups/base/README.md). devenv
  # owns each implementation; Dagu owns the composition (§6).
  tasks = {
    "base:lint".exec = "ruff check .";
    "base:test".exec = "nix flake check";
  };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
