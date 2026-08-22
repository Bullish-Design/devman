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
  # One Dagu instance, started with `devenv up`. `start-all` runs the
  # scheduler, the coordinator, and the web UI in one process. Put DAGs in
  # `.devenv/state/dagu/dags/` and open http://127.0.0.1:8080.
  env.DAGU_HOME = daguHome;
  processes.dagu.exec = "dagu start-all";

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

  # https://devenv.sh/tasks/
  # No tasks yet. The plane's own workflows call `devenv tasks run <name>`;
  # what those names are is the repository's business, not devman's.

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
