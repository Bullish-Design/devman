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

  scripts.devman.exec = ''
    (cd .. && uv sync)
    devman "$@"
  '';

  scripts.test.exec = ''
    (cd .. && uv sync --extra dev)
    (cd .. && pytest)
  '';
}
