{ pkgs, config, ... }:

let
  root = config.git.root;
in
{
  packages = with pkgs; [
    git
    just
    jujutsu
    jq
    ripgrep
  ];

  languages.python = {
    enable = true;
    version = "3.13";
    directory = "../";
    venv.enable = true;
    uv.enable = true;
  };

  scripts.devman.exec = ''
    cd "${root}"
    just devman "$@"
  '';

  # devenv.nix defines the stable command interfaces; the Justfile is the
  # experimentation layer for test workflows and output tweaks.
  scripts.test.exec = ''
    cd "${root}"
    just test "$@"
  '';
  
}
