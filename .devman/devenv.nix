# .devman/devenv.nix
{ pkgs, lib, config, inputs, ... }:

{
  env.GREET = "DevMan";

  packages = [
    pkgs.git
    pkgs.jujutsu
    pkgs.just
    pkgs.ruff
    pkgs.uv
    pkgs.copier
  ];

  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
  };

  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  enterShell = ''
    hello
    echo "Python $(python --version)"
    echo "UV $(uv --version)"
    echo "Copier $(copier --version)"
    echo
    export PATH="${pkgs.ruff}/bin:$PATH"
  '';

  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';
}
