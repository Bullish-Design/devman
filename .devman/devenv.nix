{ pkgs, ... }:

{
  packages = with pkgs; [
    git
    jujutsu
    jq
  ];

  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv = {
      enable = true;
      projectDir = ../src/devman;
    };
  };

  scripts.hello.exec = ''
    python ${../hello.py} "$@"
  '';
}
