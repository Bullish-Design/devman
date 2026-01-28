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
    directory = "../";
    venv.enable = true;
    uv.enable = true;
  };

  scripts.hello.exec = ''
    python ${../hello.py} "$@"
  '';
}
